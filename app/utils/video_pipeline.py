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
from concurrent.futures import ThreadPoolExecutor


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
    quality: int = 100
    use_cuda: bool = True
    max_workers: int = 1
    model_behaviors: Dict[str, ModelBehavior] = Field(default_factory=dict)
    count_line: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    metrics_enabled: bool = True
    classes_filter: Optional[List[int]] = None

    model_config = {'arbitrary_types_allowed': True}


class SourceHandler:
    def __init__(self, source: str, width=None, height=None, fps=None):
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
        ct = self.resp.headers.get('Content-Type', '')
        if 'boundary=' in ct:
            b = ct.split('boundary=')[-1]
            if not b.startswith('--'): b = '--' + b
            return b.encode()
        return b'--frame'

    def read(self) -> Optional[bytes]:
        if self.is_http:
            try:
                while True:
                    line = self.resp.raw.readline()
                    if not line: return None
                    if self.boundary in line:
                        headers = {}
                        while True:
                            h = self.resp.raw.readline()
                            if not h or not h.strip(): break
                            k, v = h.decode().split(':', 1)
                            headers[k.strip()] = v.strip()
                        length = int(headers.get('Content-Length', '0'))
                        if length > 0:
                            return self.resp.raw.read(length)
            except:
                return None
        else:
            ok, frame = self.cap.read()
            if not ok: return None
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
    def __init__(self):
        self.history: Dict[str, int] = {}

    def update(self, detections: Dict[str, int]) -> Dict[str, int]:
        for cls, cnt in detections.items():
            self.history[cls] = self.history.get(cls, 0) + cnt
        return dict(self.history)


class VideoPipeline:
    def __init__(self, config: PipelineConfig, logger: Optional[Any]=None):
        self.config = config
        self._log = logger.info if logger else print
        self._setup()

    def _setup(self):
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

        self.tracker = Tracker()
        self._load_models()

        if isinstance(self.config.source, VideoPipeline):
            self.pipeline_source = self.config.source
            self.source_handler  = None
        else:
            self.pipeline_source = None
            self.source_handler  = None

        self._clients: Dict[str, queue.Queue] = {}
        self._processing_enabled = bool(self.config.model_behaviors) or bool(self.config.count_line)

        self._on_frame_cb     = []
        self._on_inference_cb = []
        self._on_count_cb     = []
        self._on_error_cb     = []

    def _load_models(self):
        from ultralytics import YOLO
        self.models = {}
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
        if event == 'on_frame':     self._on_frame_cb.append(fn)
        elif event == 'on_inference':self._on_inference_cb.append(fn)
        elif event == 'on_count':    self._on_count_cb.append(fn)
        elif event == 'on_error':    self._on_error_cb.append(fn)
        else: raise KeyError(f"Unknown event {event}")

    def _emit(self, event: str, *args):
        lst = getattr(self, f"_{event}_cb")
        for cb in lst:
            try: cb(*args)
            except Exception as e: self._log(f"Callback {event} error: {e}")

    def start(self):
        if self._stop.is_set():
            self._stop.clear()

        # Reset coda, frame e metriche
        self._frame_q = queue.Queue(maxsize=self.config.prefetch)
        self._last_frame = None
        self._metrics["inference_times"].clear()
        self._metrics["frames_received"] = 0
        self._metrics["frames_processed"] = 0
        self.frames_served = 0
        self.bytes_served = 0

        # Ricrea l'executor
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)

        # Reinstanzia sorgente se non è pipeline condivisa
        if not self.pipeline_source:
            src = str(self.config.source)
            self.source_handler = SourceHandler(src,
                                                self.config.width,
                                                self.config.height,
                                                self.config.fps)

        # Avvia i thread
        self._ingest_thread = threading.Thread(target=self._ingest_loop, daemon=True, name="VP-Ingest")
        self._process_thread = threading.Thread(target=self._process_loop, daemon=True, name="VP-Proc")
        self._ingest_thread.start()
        self._process_thread.start()

        # Pulisce le code client
        for q in self._clients.values():
            with q.mutex:
                q.queue.clear()

        self._log("Pipeline started")

    def stop(self):
        self._stop.set()
        time.sleep(0.05)

        if self.source_handler:
            self.source_handler.release()
            self.source_handler = None

        # Stop e join thread
        if hasattr(self, '_ingest_thread'):
            self._ingest_thread.join(timeout=0.5)
            del self._ingest_thread
        if hasattr(self, '_process_thread'):
            self._process_thread.join(timeout=0.5)
            del self._process_thread

        # Shutdown executor
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False, cancel_futures=True)
            del self._executor

        # Reset frame e code client
        self._last_frame = None
        self._frame_q = queue.Queue(maxsize=self.config.prefetch)
        for q in self._clients.values():
            with q.mutex:
                q.queue.clear()

        self._log("Pipeline stopped")

    def _ingest_loop(self):
        while not self._stop.is_set():
            data = self.pipeline_source._last_frame if self.pipeline_source else self.source_handler.read()
            if not data:
                time.sleep(0.005)
                continue

            self._metrics["frames_received"] += 1
            f = Frame(data=data, timestamp=time.time(), seq=self._seq)
            self._seq += 1
            self._emit('on_frame', f)
            try:
                self._frame_q.put(f,
                    block=not self.config.skip_on_full_queue,
                    timeout=0.01)
            except queue.Full:
                if not self.config.skip_on_full_queue:
                    time.sleep(0.005)

    def _process_loop(self):
        def worker(fr: Frame):
            try:
                img = cv2.imdecode(np.frombuffer(fr.data, np.uint8), cv2.IMREAD_COLOR)
                start = time.time()
                counts = {}
                for path, info in self.models.items():
                    beh = info["beh"]
                    dev = 'cuda' if self.config.use_cuda else 'cpu'
                    res = info["model"](img, conf=beh.confidence, iou=beh.iou, verbose=False, device=dev)[0]
                    self._emit('on_inference', fr, path, res)
                    if beh.draw:
                        img = res.plot()
                    if beh.count:
                        filter_set = set(self.config.classes_filter or [])
                        for b in res.boxes:
                            cid = int(b.cls)
                            cls_name = res.names.get(cid, None)
                            if filter_set and cid not in filter_set and cls_name not in filter_set:
                                continue
                            name = cls_name or str(cid)
                            counts[name] = counts.get(name, 0) + 1

                tracked = self.tracker.update(counts)
                self._emit('on_count', fr, tracked)

                dt = (time.time() - start) * 1000
                self._metrics["inference_times"].append(dt)

                _, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), self.config.quality])
                self._last_frame = buf.tobytes()
                self._metrics["frames_processed"] += 1

                for q in list(self._clients.values()):
                    try:
                        q.put_nowait(self._last_frame)
                    except queue.Full:
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            pass
                        q.put_nowait(self._last_frame)

            except Exception as e:
                err = traceback.format_exc()
                self._metrics["last_error"] = err
                self._emit('on_error', err)

        while not self._stop.is_set():
            try:
                fr = self._frame_q.get(timeout=0.01)
                self._executor.submit(worker, fr)
            except queue.Empty:
                continue

    def stream_response(self):
        from flask import Response, stream_with_context, request
        client_id = str(uuid.uuid4())
        q = queue.Queue(maxsize=1)
        self._clients[client_id] = q
        self.clients_active += 1

        fps     = float(request.args.get('fps',    self.config.fps or 30))
        timeout = float(request.args.get('timeout', self.config.count_line and 5 or 10))
        boundary= b'--frame'

        def gen():
            last = time.time()
            try:
                while not self._stop.is_set():
                    try:
                        frame = q.get(timeout=timeout)
                        last = time.time()
                    except queue.Empty:
                        break
                    yield (boundary +
                           b'\r\nContent-Type: image/jpeg\r\n\r\n' +
                           frame + b'\r\n')
                    self.frames_served += 1
                    self.bytes_served += len(frame)
                    time.sleep(1.0/fps)
            finally:
                self.clients_active -= 1
                self._clients.pop(client_id, None)

        return Response(
            stream_with_context(gen()),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    def update_config(self, **kwargs):
        reload = False
        restart = False
        if 'source' in kwargs: del kwargs['source']
        if 'model_behaviors' in kwargs:
            mb = {}
            for p, b in kwargs['model_behaviors'].items():
                mb[p] = ModelBehavior(**b) if isinstance(b, dict) else b
            kwargs['model_behaviors'] = mb
            reload = True
        if 'prefetch' in kwargs or 'max_workers' in kwargs:
            restart = True

        self.config = self.config.copy(update=kwargs)
        if reload:
            self._load_models()
            self._processing_enabled = bool(self.config.model_behaviors) or bool(self.config.count_line)

        if restart:
            self._stop.set()
            time.sleep(0.05)
            self._stop.clear()
            self._frame_q = queue.Queue(maxsize=self.config.prefetch)
            self.start()

        self._log(f"Config updated: {kwargs}")

    def health(self) -> Dict[str, Any]:
        times = self._metrics["inference_times"]
        return {
            "running":        not self._stop.is_set(),
            "frames_received": self._metrics["frames_received"],
            "frames_processed": self._metrics["frames_processed"],
            "clients_active": self.clients_active,
            "last_error": self._metrics["last_error"],
            "avg_inf_ms": round(np.mean(times), 2) if times else 0,
            "min_inf_ms": round(np.min(times), 2) if times else 0,
            "max_inf_ms": round(np.max(times), 2) if times else 0
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
