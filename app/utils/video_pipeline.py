import cv2
import time
import queue
import threading
import traceback
import os
import requests
import numpy as np
from typing import Callable, Dict, Any, Optional, Tuple, List
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
    source: str
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    prefetch: int = 10
    model_behaviors: Dict[str, ModelBehavior] = Field(default_factory=dict)
    count_line: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    metrics_enabled: bool = True
    classes_filter: Optional[List[int]] = None


class SourceHandler:
    """
    Gestisce input da webcam o da stream HTTP MJPEG.
    """
    def __init__(self, source: str, width: Optional[int] = None,
                 height: Optional[int] = None, fps: Optional[int] = None):
        self.source = source
        self.cap = None
        self.width = width
        self.height = height
        self.fps = fps
        self.is_http = source.startswith(('http://', 'https://'))
        if self.is_http:
            self.session = requests.Session()
            self.stream_req = self.session.get(source, stream=True)
            self.buffer = b''
        else:
            idx = int(source) if source.isdigit() else source
            self.cap = cv2.VideoCapture(idx)
            if width:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height:
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if fps:
                self.cap.set(cv2.CAP_PROP_FPS, fps)

    def read(self) -> Optional[np.ndarray]:
        if self.is_http:
            for chunk in self.stream_req.iter_content(chunk_size=1024):
                self.buffer += chunk
                a = self.buffer.find(b'\xff\xd8')
                b = self.buffer.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = self.buffer[a:b+2]
                    self.buffer = self.buffer[b+2:]
                    return cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            return None
        else:
            ok, frame = self.cap.read()
            return frame if ok else None

    def release(self):
        if self.cap:
            self.cap.release()
        if self.is_http:
            self.stream_req.close()
            self.session.close()


class Tracker:
    """
    Aggrega conteggi tra più modelli per ogni classe.
    Per tracciamento avanzato, integra SORT/DeepSORT.
    """
    def __init__(self):
        self.history: Dict[str, int] = {}

    def update(self, detections: Dict[str, int]) -> Dict[str, int]:
        for cls, cnt in detections.items():
            self.history[cls] = self.history.get(cls, 0) + cnt
        return dict(self.history)


class VideoPipeline:
    def __init__(self, config: PipelineConfig, logger: Optional[Any] = None):
        self.config = config
        self._log = logger.info if logger else print
        self._setup()

    def _setup(self):
        self._frame_q = queue.Queue(maxsize=self.config.prefetch)
        self._stop = threading.Event()
        self._seq = 0
        self._metrics = {"frames_received": 0, "frames_processed": 0,
                         "inference_times": [], "last_error": None}
        self._callbacks = {"on_frame": [], "on_inference": [],
                           "on_count": [], "on_error": []}
        self.tracker = Tracker()
        self._load_models()
        self.source_handler: Optional[SourceHandler] = None
        # Streaming state
        self._streaming_active = False
        self._last_frame: Optional[bytes] = None

    def _load_models(self):
        from ultralytics import YOLO
        self.models: Dict[str, Dict[str, Any]] = {}
        for path, beh in self.config.model_behaviors.items():
            if not os.path.isfile(path):
                self._log(f"Modello NON trovato: {path}")
                continue
            if not (beh.draw or beh.count):
                continue
            try:
                model = YOLO(path)
                self.models[path] = {"model": model, "beh": beh}
                self._log(f"Caricato {path} (draw={beh.draw}, count={beh.count})")
            except Exception as e:
                self._log(f"Errore caricamento {path}: {e}")

    def register_callback(self, event: str, fn: Callable):
        if event not in self._callbacks:
            raise KeyError(f"Evento sconosciuto: {event}")
        self._callbacks[event].append(fn)

    def _emit(self, event: str, *args):
        for cb in self._callbacks[event]:
            try:
                cb(*args)
            except Exception as e:
                self._log(f"Callback error[{event}]: {e}")

    def update_config(self, **kwargs):
        old_source = self.config.source
        self.config = self.config.copy(update=kwargs)
        if "model_behaviors" in kwargs:
            self._load_models()
        if "source" in kwargs and kwargs["source"] != old_source:
            if self.source_handler:
                self.source_handler.release()
            self.source_handler = None
        self._log(f"Config aggiornata: {kwargs}")

    def start(self):
        if not self.source_handler:
            cfg = self.config
            self.source_handler = SourceHandler(cfg.source, cfg.width, cfg.height, cfg.fps)
        self._stop.clear()
        threading.Thread(target=self._read, daemon=True, name="VP-Read").start()
        threading.Thread(target=self._process, daemon=True, name="VP-Proc").start()
        self._log("Pipeline avviata")

    def stop(self):
        self._stop.set()
        if self.source_handler:
            self.source_handler.release()
        self._log("Pipeline arrestata")

    def _read(self):
        while not self._stop.is_set():
            img = self.source_handler.read()
            if img is None:
                time.sleep(0.05)
                continue
            _, buf = cv2.imencode('.jpg', img)
            fr = Frame(data=buf.tobytes(), timestamp=time.time(), seq=self._seq)
            self._seq += 1
            try:
                self._frame_q.put(fr, timeout=0.1)
                self._metrics["frames_received"] += 1
                self._emit("on_frame", fr)
            except queue.Full:
                continue

    def _process(self):
        while not self._stop.is_set():
            try:
                fr = self._frame_q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                img = cv2.imdecode(np.frombuffer(fr.data, np.uint8), cv2.IMREAD_COLOR)
                start = time.time()
                total_counts: Dict[str, int] = {}
                for path, mi in self.models.items():
                    beh = mi["beh"]
                    res = mi["model"](img, conf=beh.confidence, iou=beh.iou, verbose=False)[0]
                    self._emit("on_inference", fr, path, res)
                    if beh.draw:
                        img = res.plot()
                    if beh.count and hasattr(res, "boxes"):
                        cnts: Dict[str, int] = {}
                        for b in res.boxes:
                            cls_id = int(b.cls)
                            if self.config.classes_filter and cls_id not in self.config.classes_filter:
                                continue
                            cls_name = res.names[cls_id]
                            cnts[cls_name] = cnts.get(cls_name, 0) + 1
                        total_counts.update(cnts)
                tracked = self.tracker.update(total_counts)
                self._emit("on_count", fr, tracked)
                dt = (time.time() - start) * 1000
                self._metrics["inference_times"].append(dt)
                _, buf2 = cv2.imencode('.jpg', img)
                self._last_frame = buf2.tobytes()
                self._metrics["frames_processed"] += 1
            except Exception:
                err = traceback.format_exc()
                self._metrics["last_error"] = err
                self._emit("on_error", err)

    def stream_response(self):
        from flask import Response, stream_with_context

        boundary = b'--frame'
        interval = 1.0 / self.config.fps if self.config.fps else 0.05
        
        def generator():
            self._streaming_active = True
            try:
                while not self._stop.is_set():
                    if self._last_frame:
                        yield boundary + b'\r\nContent-Type: image/jpeg\r\n\r\n' + self._last_frame + b'\r\n'
                    time.sleep(interval)
            finally:
                self._streaming_active = False

        return Response(
            stream_with_context(generator()),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    def health(self) -> Dict[str, Any]:
        return {
            "running": not self._stop.is_set(),
            "received": self._metrics["frames_received"],
            "processed": self._metrics["frames_processed"],
            "queue_depth": self._frame_q.qsize()
        }

    def metrics(self) -> Dict[str, Any]:
        avg = (np.mean(self._metrics["inference_times"]) if self._metrics["inference_times"] else 0)
        return {
            "avg_inf_ms": avg,
            "counters": self.tracker.history,
            "last_error": self._metrics["last_error"]
        }

    def export_config(self) -> Dict[str, Any]:
        return self.config.dict()