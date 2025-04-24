# app/utils/video_pipeline.py

import cv2
import time
import queue
import threading
import traceback
from typing import Callable, Dict, List, Optional, Tuple, Any
import numpy as np
from pydantic import BaseModel


class Frame(BaseModel):
    data: bytes
    timestamp: float
    seq: int
    meta: Optional[Dict[str, Any]] = None


class PipelineConfig(BaseModel):
    source: str = "0"
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    models: List[str] = []
    confidence: float = 0.5
    iou: float = 0.45
    draw_boxes: bool = False
    count_objects: bool = False
    count_line: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    metrics_enabled: bool = True
    classes_filter: Optional[List[int]] = None
    prefetch: int = 10


class VideoPipeline:
    """
    Semplice da istanziare via:
        vp = VideoPipeline(PipelineConfig(...))
        vp.register_callback("on_count", handler)
        vp.start()
    E con:
        resp = vp.stream_response()  # flask.Response MJPEG
    """
    def __init__(
        self,
        config: PipelineConfig,
        logger: Optional[Any] = None
    ):
        self.config = config
        self._log = logger or __import__('logging').getLogger(__name__).info
        self._setup()

    def _setup(self):
        self._frame_q     = queue.Queue(maxsize=self.config.prefetch)
        self._processed_q = queue.Queue(maxsize=self.config.prefetch)
        self._stop        = threading.Event()
        self._seq         = 0
        self._counters: Dict[str,int] = {}
        self._metrics: Dict[str,Any] = {
            "frames_received": 0,
            "frames_processed": 0,
            "inference_times": [],
            "last_error": None
        }
        self._callbacks: Dict[str,List[Callable]] = {
            "on_frame": [], "on_inference": [], "on_count": [], "on_error": []
        }
        self._models_loaded = False
        self._load_models()

    def _load_models(self):
        if not (self.config.draw_boxes or self.config.count_objects):
            return
        from ultralytics import YOLO
        self.models = []
        for p in self.config.models:
            try:
                m = YOLO(p); self.models.append(m)
                self._log(f"[Pipeline] model loaded: {p}")
            except Exception as e:
                self._log(f"[Pipeline] error loading {p}: {e}")
        self._models_loaded = True

    def register_callback(self, event: str, fn: Callable):
        if event not in self._callbacks:
            raise KeyError(f"Unknown event: {event}")
        self._callbacks[event].append(fn)

    def emit(self, event: str, *args):
        for cb in self._callbacks.get(event, []):
            try: cb(*args)
            except Exception as e: self._log(f"[Pipeline] callback error: {e}")

    def update_config(self, **kwargs):
        self.config = self.config.copy(update=kwargs)
        if {"models","draw_boxes","count_objects"} & set(kwargs):
            self._load_models()
        self._log(f"[Pipeline] config updated: {kwargs}")

    def start(self):
        self._stop.clear()
        t1 = threading.Thread(target=self._read,    daemon=True, name="Pipeline-Read")
        t2 = threading.Thread(target=self._process, daemon=True, name="Pipeline-Proc")
        self._workers = [t1, t2]
        for t in self._workers: t.start()
        self._log("[Pipeline] started")

    def stop(self):
        self._stop.set()
        for t in self._workers: t.join(timeout=1)
        self._log("[Pipeline] stopped")

    def _read(self):
        cap = cv2.VideoCapture(
            int(self.config.source) if self.config.source.isdigit()
            else self.config.source
        )
        if self.config.width:  cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.config.width)
        if self.config.height: cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        if self.config.fps:    cap.set(cv2.CAP_PROP_FPS,          self.config.fps)
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        f = cap.get(cv2.CAP_PROP_FPS)
        self._log(f"[Pipeline] opened {w:.0f}×{h:.0f}@{f:.1f}FPS")

        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05); continue
            _, buf = cv2.imencode('.jpg', frame)
            fr = Frame(data=buf.tobytes(), timestamp=time.time(), seq=self._seq)
            self._seq += 1
            try:
                self._frame_q.put(fr, timeout=0.1)
                self._metrics["frames_received"] += 1
                self.emit("on_frame", fr)
            except queue.Full:
                continue
        cap.release()

    def _process(self):
        import numpy as np
        while not self._stop.is_set():
            try:
                fr = self._frame_q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if not (self.config.draw_boxes or self.config.count_objects):
                    out = fr.data
                else:
                    img = cv2.imdecode(np.frombuffer(fr.data, np.uint8), cv2.IMREAD_COLOR)
                    start = time.time()
                    res = [m(img, conf=self.config.confidence, iou=self.config.iou)[0] for m in self.models]
                    dt = (time.time()-start)*1000
                    self._metrics["inference_times"].append(dt)
                    self.emit("on_inference", fr, res)

                    if self.config.draw_boxes:
                        for r in res: img = r.plot()
                    if self.config.count_line:
                        p1, p2 = self.config.count_line
                        cv2.line(img, p1, p2, (0,255,0), 2)
                    if self.config.count_objects:
                        cnts: Dict[str,int] = {}
                        for r in res:
                            for b in r.boxes:
                                c = int(b.cls)
                                if self.config.classes_filter and c not in self.config.classes_filter:
                                    continue
                                nm = r.names[c]
                                cnts[nm] = cnts.get(nm,0)+1
                        for nm, c in cnts.items():
                            self._counters[nm] = self._counters.get(nm,0)+c
                        self.emit("on_count", cnts)

                    _, buf2 = cv2.imencode('.jpg', img)
                    out = buf2.tobytes()

                fr.data = out
                self._processed_q.put(fr)
                self._metrics["frames_processed"] += 1

            except Exception as e:
                err = traceback.format_exc()
                self._metrics["last_error"] = err
                self.emit("on_error", err)

    def output_generator(self):
        b = b'--frame'
        while not self._stop.is_set():
            try:
                fr = self._processed_q.get(timeout=0.1)
            except queue.Empty:
                continue
            yield (b + b'\r\nContent-Type: image/jpeg\r\n\r\n' + fr.data + b'\r\n')

    def stream_response(self):
        """Flask-ready MJPEG response."""
        from flask import Response, stream_with_context
        return Response(
            stream_with_context(self.output_generator()),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    def health(self):
        return {
            "running":    not self._stop.is_set(),
            "received":   self._metrics["frames_received"],
            "processed":  self._metrics["frames_processed"],
            "queue_size": self._frame_q.qsize()
        }

    def metrics(self):
        avg = (np.mean(self._metrics["inference_times"]) 
               if self._metrics["inference_times"] else 0)
        return {
            "avg_inference_ms": avg,
            "counters":         self._counters,
            "last_error":       self._metrics["last_error"]
        }

    def export_config(self):
        return self.config.dict()
