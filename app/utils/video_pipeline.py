# app/utils/video_pipeline.py

import cv2
import time
import threading
import traceback
import os
import requests
import queue
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
            self.req = self.session.get(source, stream=True)
            self.buffer = b''
        else:
            idx = int(source) if source.isdigit() else source
            self.cap = cv2.VideoCapture(idx)
            if width:  self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
            if height: self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if fps:    self.cap.set(cv2.CAP_PROP_FPS,          fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def read(self) -> Optional[bytes]:
        if self.is_http:
            # restituisce direttamente JPEG bytes
            for chunk in self.req.iter_content(1024):
                self.buffer += chunk
                a = self.buffer.find(b'\xff\xd8')
                b = self.buffer.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = self.buffer[a:b+2]
                    self.buffer = self.buffer[b+2:]
                    return jpg
            return None
        else:
            ok, frame = self.cap.read()
            if not ok:
                return None
            # encode JPEG con qualità base (100)
            _, buf = cv2.imencode('.jpg', frame)
            return buf.tobytes()

    def release(self):
        if not self.is_http and hasattr(self, 'cap'):
            self.cap.release()
        elif self.is_http:
            self.req.close()
            self.session.close()


class Tracker:
    """Aggrega conteggi cumulativi per classe."""
    def __init__(self):
        self.history: Dict[str,int] = {}

    def update(self, detections: Dict[str,int]) -> Dict[str,int]:
        for cls, cnt in detections.items():
            self.history[cls] = self.history.get(cls,0) + cnt
        return dict(self.history)


class VideoPipeline:
    def __init__(self, config: PipelineConfig, logger: Optional[Any]=None):
        self.config = config
        self._log = logger.info if logger else print
        self._setup()

    def _setup(self):
        # coda tra read e process
        self._frame_q     = queue.Queue(maxsize=self.config.prefetch)
        self._stop        = threading.Event()
        self._seq         = 0
        self._last_frame  = None
        self._metrics     = {"frames_received":0,
                             "frames_processed":0,
                             "inference_times":[],
                             "last_error":None}
        self.clients_active = 0
        self.frames_served  = 0
        self.bytes_served   = 0

        self.tracker = Tracker()
        self._load_models()

        # se source è un'altra pipeline, usalo come sorgente
        self.pipeline_source = (
            self.config.source
            if isinstance(self.config.source, VideoPipeline)
            else None
        )
        self.source_handler = None

        # decide se attivare la fase di process
        self._processing_enabled = bool(self.config.model_behaviors) or bool(self.config.count_line)

    def _load_models(self):
        from ultralytics import YOLO
        self.models: Dict[str,Dict[str,Any]] = {}
        for path, beh in self.config.model_behaviors.items():
            if not os.path.isfile(path):
                self._log(f"Model not found: {path}")
                continue
            if not(beh.draw or beh.count):
                continue
            try:
                m = YOLO(path, verbose=False)
                self.models[path] = {"model":m, "beh":beh}
                self._log(f"Loaded {os.path.basename(path)}")
            except Exception as e:
                self._log(f"Error loading {path}: {e}")

    def register_callback(self, event: str, fn: Callable):
        # eventi: on_frame, on_inference, on_count, on_error
        if event not in ['on_frame','on_inference','on_count','on_error']:
            raise KeyError(f"Unknown event {event}")
        getattr(self, '_'+event+'_cb', []).append(fn)

    def _emit(self, event:str, *args):
        for cb in getattr(self, '_'+event+'_cb', []):
            try: cb(*args)
            except: self._log(f"Callback {event} error")

    def update_config(self, **kwargs):
        # aggiorna runtime config e ricarica modelli se serve
        self.config = self.config.copy(update=kwargs)
        if 'model_behaviors' in kwargs:
            self._load_models()
            self._processing_enabled = bool(self.config.model_behaviors) or bool(self.config.count_line)
        self._log(f"Config updated: {kwargs}")

    def start(self):
        # init source handler
        if not self.pipeline_source and not self.source_handler:
            c = self.config
            self.source_handler = SourceHandler(c.source, c.width, c.height, c.fps)

        self._stop.clear()
        # thread di lettura SEMPRE
        threading.Thread(target=self._read_loop, daemon=True, name="VP-Read").start()

        if self._processing_enabled:
            # thread process parallelo
            threading.Thread(target=self._process_loop, daemon=True, name="VP-Proc").start()
        else:
            # passthrough: trasferisci direttamente a last_frame
            threading.Thread(target=self._passthrough_loop, daemon=True, name="VP-Pass").start()

        self._log("Pipeline started")

    def stop(self):
        self._stop.set()
        if self.source_handler:
            self.source_handler.release()
        self._log("Pipeline stopped")

    def _read_loop(self):
        while not self._stop.is_set():
            # sorgente flessibile
            if self.pipeline_source:
                data = self.pipeline_source._last_frame
            else:
                data = self.source_handler.read()

            if data is None:
                time.sleep(0.005)
                continue

            self._metrics["frames_received"] += 1
            f = Frame(data=data, timestamp=time.time(), seq=self._seq); self._seq+=1
            self._emit('on_frame', f)

            # push in coda
            try:
                self._frame_q.put(f, block=not self.config.skip_on_full_queue, timeout=0.01)
            except queue.Full:
                if not self.config.skip_on_full_queue:
                    time.sleep(0.005)

    def _passthrough_loop(self):
        """Modalità senza processing: aggiorna last_frame appena arriva."""
        while not self._stop.is_set():
            try:
                f = self._frame_q.get(timeout=0.01)
            except queue.Empty:
                continue
            # senza alcuna elaborazione, mantieni JPEG bytes 
            self._last_frame = f.data
            self._metrics["frames_processed"] += 1

    def _process_loop(self):
        """Modalità elaborazione: inferenza parallela e postprocess."""
        from concurrent.futures import ThreadPoolExecutor
        exec = ThreadPoolExecutor(max_workers=self.config.max_workers)

        def worker(f:Frame):
            try:
                img = cv2.imdecode(np.frombuffer(f.data, np.uint8), cv2.IMREAD_COLOR)
                start = time.time()
                counts:Dict[str,int] = {}
                # inferenze
                for path,info in self.models.items():
                    beh = info["beh"]
                    dev = 'cuda' if self.config.use_cuda else 'cpu'
                    res = info["model"](img, conf=beh.confidence, iou=beh.iou,
                                        verbose=False, device=dev)[0]
                    self._emit('on_inference', f, path, res)
                    if beh.draw:
                        img = res.plot()
                    if beh.count:
                        for box in res.boxes:
                            cid = int(box.cls)
                            if self.config.classes_filter and cid not in self.config.classes_filter:
                                continue
                            name = res.names[cid]; counts[name]=counts.get(name,0)+1
                # linea + tracking
                if self.config.count_line:
                    self.tracker.update(dict())  # (potresti aggiungere logica)
                tracked = self.tracker.update(counts)
                self._emit('on_count', f, tracked)

                dt = (time.time()-start)*1000
                self._metrics["inference_times"].append(dt)

                # ricodifica JPEG finale
                _, buf = cv2.imencode('.jpg', img,
                                      [int(cv2.IMWRITE_JPEG_QUALITY),
                                       self.config.quality])
                self._last_frame = buf.tobytes()
                self._metrics["frames_processed"] += 1

            except Exception as e:
                self._metrics["last_error"] = traceback.format_exc()
                self._emit('on_error', e)

        while not self._stop.is_set():
            try:
                fr = self._frame_q.get(timeout=0.01)
            except queue.Empty:
                continue
            exec.submit(worker, fr)

    def stream_response(self):
        from flask import Response, stream_with_context, request
        fps = float(request.args.get('fps', self.config.fps or 30))
        timeout = float(request.args.get('timeout', 10))
        self.clients_active += 1
        last_time = time.time()
        boundary = b'--frame'

        def gen():
            try:
                while not self._stop.is_set():
                    if self._last_frame:
                        yield boundary + b'\r\nContent-Type: image/jpeg\r\n\r\n' + self._last_frame + b'\r\n'
                        self.frames_served += 1
                        self.bytes_served += len(self._last_frame)
                        last_time = time.time()
                    if time.time()-last_time > timeout:
                        break
                    time.sleep(1.0/fps)
            finally:
                self.clients_active -= 1

        return Response(stream_with_context(gen()),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    def health(self) -> Dict[str,Any]:
        return {
            "running": not self._stop.is_set(),
            **self._metrics,
            "clients_active": self.clients_active
        }

    def metrics(self) -> Dict[str,Any]:
        avg = np.mean(self._metrics["inference_times"]) if self._metrics["inference_times"] else 0
        return {
            "avg_inf_ms": avg,
            "counters": self.tracker.history,
            "frames_served": self.frames_served,
            "bytes_served": self.bytes_served,
            "last_error": self._metrics["last_error"]
        }

    def export_config(self) -> Dict[str,Any]:
        return self.config.dict()
