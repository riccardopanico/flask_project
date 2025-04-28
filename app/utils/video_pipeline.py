import cv2
import time
import threading
import traceback
import os
import requests
import queue
import uuid
import numpy as np
from typing import Callable, Dict, Any, Optional, Tuple, List, Union
from pydantic import BaseModel, Field


class Frame(BaseModel):
    data: bytes
    timestamp: float
    seq: int
    meta: Optional[Dict[str, Any]] = None


class ModelBehavior(BaseModel):
    draw: bool = False
    count: bool = False
    confidence: float = 0.5
    iou: float = 0.45


class PipelineConfig(BaseModel):
    source: Union[str, 'VideoPipeline']
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    prefetch: int = 10
    skip_on_full_queue: bool = True
    quality: int = 70        # JPEG quality 0–100
    use_cuda: bool = True
    max_workers: int = 8
    model_behaviors: Dict[str, ModelBehavior] = Field(default_factory=dict)
    count_line: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    metrics_enabled: bool = True
    classes_filter: Optional[List[int]] = None

    # necessario per pydantic a gestire il tipo VideoPipeline
    model_config = {'arbitrary_types_allowed': True}


class SourceHandler:
    """
    Lettura da webcam (VideoCapture) o da HTTP MJPEG.
    """
    def __init__(self, source: str, width=None, height=None, fps=None):
        self.source = source
        self.is_http = source.startswith(('http://', 'https://'))
        if self.is_http:
            self.session = requests.Session()
            self.resp = self.session.get(source, stream=True)
            self.boundary = self._find_boundary()
            self.buffer = b''
        else:
            idx = int(source) if source.isdigit() else source
            self.cap = cv2.VideoCapture(idx)
            if width:  self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
            if height: self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if fps:    self.cap.set(cv2.CAP_PROP_FPS,          fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def _find_boundary(self) -> bytes:
        content_type = self.resp.headers.get('Content-Type', '')
        if 'boundary=' in content_type:
            b = content_type.split('boundary=')[-1]
            if not b.startswith('--'):
                b = '--' + b
            return b.encode()
        return b'--frame'

    def read(self) -> Optional[bytes]:
        if self.is_http:
            try:
                # leggiamo un frame alla volta dal flusso MJPEG
                while True:
                    line = self.resp.raw.readline()
                    if not line:
                        return None
                    if self.boundary in line:
                        # intestazioni
                        headers = {}
                        while True:
                            h = self.resp.raw.readline()
                            if not h or h.strip() == b'':
                                break
                            key, val = h.decode().split(":", 1)
                            headers[key.strip()] = val.strip()
                        length = int(headers.get('Content-Length', '0'))
                        if length > 0:
                            img = self.resp.raw.read(length)
                            return img
            except Exception:
                return None
        else:
            ok, frame = self.cap.read()
            if not ok:
                return None
            _, buf = cv2.imencode('.jpg', frame)
            return buf.tobytes()

    def release(self):
        if self.is_http:
            try:
                self.resp.close()
                self.session.close()
            except:
                pass
        else:
            self.cap.release()


class Tracker:
    """
    Aggrega conteggi cumulativi per ciascuna classe.
    """
    def __init__(self):
        self.history: Dict[str,int] = {}

    def update(self, detections: Dict[str,int]) -> Dict[str,int]:
        for cls, cnt in detections.items():
            self.history[cls] = self.history.get(cls, 0) + cnt
        return dict(self.history)


class VideoPipeline:
    """
    - Se config.source è stringa: crea un SourceHandler proprio (webcam o HTTP).
    - Se config.source è VideoPipeline: si collega ai suoi frame già elaborati.
    - Mantiene una coda interna tra ingest e process.
    - Se non ci sono modelli/count_line, entra in passthrough.
    - Serve MJPEG a N client tramite queue dedicate.
    """
    def __init__(self, config: PipelineConfig, logger: Optional[Any]=None):
        self.config = config
        self._log = logger.info if logger else print
        self._setup()

    def _setup(self):
        # coda ingest → process
        self._frame_q     = queue.Queue(maxsize=self.config.prefetch)
        self._stop        = threading.Event()
        self._seq         = 0
        self._last_frame  = None
        self._metrics     = {
            "frames_received":   0,
            "frames_processed":  0,
            "inference_times":   [],
            "last_error":        None
        }
        self.clients_active = 0
        self.frames_served  = 0
        self.bytes_served   = 0

        # tracker conteggi
        self.tracker = Tracker()
        # carica i modelli
        self._load_models()

        # sorgente: pipeline chaining oppure SourceHandler
        if isinstance(self.config.source, VideoPipeline):
            self.pipeline_source = self.config.source
            self.source_handler = None
        else:
            self.pipeline_source = None
            self.source_handler = None  # verrà creato in start()

        # code per client MJPEG
        self._clients: Dict[str, queue.Queue] = {}
        # passthrough se non ho modelli/count_line
        self._processing_enabled = bool(self.config.model_behaviors) or bool(self.config.count_line)

    def _load_models(self):
        from ultralytics import YOLO
        self.models: Dict[str,Dict[str,Any]] = {}
        for path, beh in self.config.model_behaviors.items():
            if not os.path.isfile(path):
                self._log(f"Model not found: {path}")
                continue
            if not (beh.draw or beh.count):
                continue
            try:
                m = YOLO(path, verbose=False)
                self.models[path] = {"model": m, "beh": beh}
                self._log(f"Loaded {os.path.basename(path)}")
            except Exception as e:
                self._log(f"Error loading {path}: {e}")

    def register_callback(self, event: str, fn: Callable):
        setattr(self, f"_{event}_cb", getattr(self, f"_{event}_cb", []) + [fn])

    def _emit(self, event: str, *args):
        for cb in getattr(self, f"_{event}_cb", []):
            try: cb(*args)
            except Exception as e: self._log(f"Callback {event} error: {e}")

    def start(self):
        # crea il SourceHandler se serve
        if not self.pipeline_source and not self.source_handler:
            src = str(self.config.source)
            self.source_handler = SourceHandler(
                src,
                self.config.width,
                self.config.height,
                self.config.fps
            )

        self._stop.clear()
        threading.Thread(target=self._ingest_loop, daemon=True, name="VP-Ingest").start()
        if self._processing_enabled:
            threading.Thread(target=self._process_loop, daemon=True, name="VP-Proc").start()
        else:
            threading.Thread(target=self._passthrough_loop, daemon=True, name="VP-Pass").start()

        self._log("Pipeline started")

    def stop(self):
        self._stop.set()
        if self.source_handler:
            self.source_handler.release()
        self._log("Pipeline stopped")

    def _ingest_loop(self):
        while not self._stop.is_set():
            if self.pipeline_source:
                data = self.pipeline_source._last_frame
            else:
                data = self.source_handler.read()
            if not data:
                time.sleep(0.005)
                continue

            self._metrics["frames_received"] += 1
            f = Frame(data=data, timestamp=time.time(), seq=self._seq)
            self._seq += 1

            try:
                self._frame_q.put(
                    f,
                    block=not self.config.skip_on_full_queue,
                    timeout=0.01
                )
            except queue.Full:
                if not self.config.skip_on_full_queue:
                    time.sleep(0.005)

    def _passthrough_loop(self):
        while not self._stop.is_set():
            try:
                fr = self._frame_q.get(timeout=0.01)
            except queue.Empty:
                continue
            self._last_frame = fr.data
            self._metrics["frames_processed"] += 1
            self._broadcast(fr.data)

    def _process_loop(self):
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=self.config.max_workers)

        def worker(fr: Frame):
            try:
                img = cv2.imdecode(np.frombuffer(fr.data, np.uint8), cv2.IMREAD_COLOR)
                start = time.time()
                counts: Dict[str,int] = {}

                for path, info in self.models.items():
                    beh = info["beh"]
                    dev = 'cuda' if self.config.use_cuda else 'cpu'
                    res = info["model"](img,
                                        conf=beh.confidence,
                                        iou=beh.iou,
                                        verbose=False,
                                        device=dev)[0]
                    self._emit('on_inference', fr, path, res)
                    if beh.draw:
                        img = res.plot()
                    if beh.count:
                        for b in res.boxes:
                            cid = int(b.cls)
                            if self.config.classes_filter and cid not in self.config.classes_filter:
                                continue
                            name = res.names[cid]
                            counts[name] = counts.get(name,0) + 1

                tracked = self.tracker.update(counts)
                self._emit('on_count', fr, tracked)

                dt = (time.time() - start) * 1000
                self._metrics["inference_times"].append(dt)

                _, buf = cv2.imencode('.jpg', img,
                                      [int(cv2.IMWRITE_JPEG_QUALITY),
                                       self.config.quality])
                data = buf.tobytes()
                self._last_frame = data
                self._metrics["frames_processed"] += 1
                self._broadcast(data)

            except Exception:
                self._metrics["last_error"] = traceback.format_exc()

        while not self._stop.is_set():
            try:
                fr = self._frame_q.get(timeout=0.01)
            except queue.Empty:
                continue
            executor.submit(worker, fr)

    def _broadcast(self, frame: bytes):
        for q in list(self._clients.values()):
            try:
                q.put_nowait(frame)
            except queue.Full:
                try: q.get_nowait()
                except: pass
                q.put_nowait(frame)

    def stream_response(self):
        from flask import Response, stream_with_context, request

        client_id = str(uuid.uuid4())
        q = queue.Queue(maxsize=1)
        self._clients[client_id] = q
        self.clients_active += 1

        fps     = float(request.args.get('fps', self.config.fps or 30))
        timeout = float(request.args.get('timeout', 10))
        boundary = b'--frame'

        def gen():
            last_access = time.time()
            try:
                while not self._stop.is_set():
                    try:
                        frame = q.get(timeout=timeout)
                        last_access = time.time()
                    except queue.Empty:
                        break
                    yield boundary + b'\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                    self.frames_served += 1
                    self.bytes_served += len(frame)
                    time.sleep(1.0 / fps)
            finally:
                self.clients_active -= 1
                self._clients.pop(client_id, None)

        return Response(
            stream_with_context(gen()),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    def health(self) -> Dict[str, Any]:
        return {
            "running":        not self._stop.is_set(),
            **self._metrics,
            "clients_active": self.clients_active
        }

    def metrics(self) -> Dict[str, Any]:
        avg = (np.mean(self._metrics["inference_times"])
               if self._metrics["inference_times"] else 0)
        return {
            "avg_inf_ms":    avg,
            "counters":      self.tracker.history,
            "frames_served": self.frames_served,
            "bytes_served":  self.bytes_served,
            "last_error":    self._metrics["last_error"]
        }

    def export_config(self) -> Dict[str, Any]:
        return self.config.dict()
