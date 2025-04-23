# app/utils/video_pipeline.py
import cv2, time, queue, threading, traceback
from typing import Callable, Dict, List, Optional, Tuple, Any
import numpy as np
from ultralytics import YOLO
from flask import Response
import pydantic

class Frame(pydantic.BaseModel):
    data: bytes
    timestamp: float
    seq: int

class PipelineConfig(pydantic.BaseModel):
    source: str = "0"
    width: Optional[int] = None        # se None, non forza
    height: Optional[int] = None
    fps: Optional[int] = None
    models: List[str] = []
    confidence: float = 0.5
    iou: float = 0.45
    draw_boxes: bool = False
    count_objects: bool = False
    count_line: Optional[Tuple[Tuple[int,int], Tuple[int,int]]] = None
    metrics_enabled: bool = True
    classes_filter: Optional[List[int]] = None
    prefetch: int = 10

class VideoPipeline:
    """Pipeline modulare di streaming + inferenza YOLO, bypass di default."""
    def __init__(self, app, config: PipelineConfig):
        self.app = app
        self.logger = app.logger
        self.config = config
        self._setup()

    def _setup(self):
        # code & metrics
        self._frame_queue     = queue.Queue(maxsize=self.config.prefetch)
        self._processed_queue = queue.Queue(maxsize=self.config.prefetch)
        self._callbacks: Dict[str,List[Callable]] = {
            "on_frame": [], "on_inference": [], "on_count": [], "on_error": []
        }
        self._stop_event = threading.Event()
        self._workers    = []
        self._seq        = 0
        self._counters   = {}
        self._metrics    = {
            "frames_received": 0,
            "frames_processed": 0,
            "inference_times": [],
            "last_error": None
        }
        self._models_loaded = False
        self._load_models()

    def _load_models(self):
        # solo se serve inferenza
        if not (self.config.draw_boxes or self.config.count_objects):
            return
        self.models = []
        for path in self.config.models:
            try:
                m = YOLO(path)
                self.models.append(m)
                self.logger.info(f"Loaded YOLO model: {path}")
            except Exception as e:
                self.logger.error(f"Model load error {path}: {e}")
        self._models_loaded = True

    def register_callback(self, event: str, fn: Callable):
        if event in self._callbacks:
            self._callbacks[event].append(fn)

    def update_config(self, **kwargs):
        """Override dinamici della config."""
        with self.app.app_context():
            try:
                self.config = self.config.copy(update=kwargs)
                # se cambiano i modelli o inferenza, ricaricali
                if "models" in kwargs or kwargs.get("draw_boxes") or kwargs.get("count_objects"):
                    self._load_models()
                self.logger.info(f"Pipeline config updated: {kwargs}")
            except Exception:
                err = traceback.format_exc()
                self._metrics["last_error"] = err
                self.logger.error(err)
                raise

    def start(self):
        """Avvia i due stadi: lettura e processing."""
        self._stop_event.clear()
        threads = [
            threading.Thread(target=self._source_reader, daemon=True, name="source_reader"),
            threading.Thread(target=self._processor,     daemon=True, name="processor"),
        ]
        self._workers = threads
        for t in threads: t.start()
        self.logger.info("VideoPipeline started.")

    def stop(self):
        self._stop_event.set()
        for q in (self._frame_queue, self._processed_queue):
            while not q.empty():
                q.get_nowait()
        for t in self._workers:
            t.join(timeout=1)
        self.logger.info("VideoPipeline stopped.")

    def _source_reader(self):
        """Legge frame dalla source → frame_queue."""
        cap = cv2.VideoCapture(
            int(self.config.source) if self.config.source.isdigit()
            else self.config.source
        )

        # solo se specificati, forza width/height/fps
        if self.config.width is not None:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        if self.config.height is not None:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        if self.config.fps is not None:
            cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        # leggi valori effettivi
        actual_w   = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h   = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        self.logger.info(f"Camera opened at {actual_w:.0f}x{actual_h:.0f} @ {actual_fps:.1f} FPS")

        while not self._stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                self.logger.warning("Source reader: no frame, retrying")
                time.sleep(0.1)
                continue

            _, buf = cv2.imencode('.jpg', frame)
            f = Frame(data=buf.tobytes(), timestamp=time.time(), seq=self._seq)
            self._seq += 1

            try:
                self._frame_queue.put(f, timeout=1/(self.config.fps or 30))
                self._metrics["frames_received"] += 1
                for cb in self._callbacks["on_frame"]:
                    cb(f)
            except queue.Full:
                self.logger.warning("Frame queue full, dropping frame.")

        cap.release()

    def _processor(self):
        """Prende frame → (inferenza) → re-encode → processed_queue."""
        while not self._stop_event.is_set():
            try:
                frame = self._frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                # bypass totale se non serve inferenza
                if not (self.config.draw_boxes or self.config.count_objects):
                    processed_bytes = frame.data
                else:
                    start = time.time()
                    img = cv2.imdecode(
                        np.frombuffer(frame.data, np.uint8),
                        cv2.IMREAD_COLOR
                    )
                    results = []
                    for m in self.models:
                        r = m(img, conf=self.config.confidence, iou=self.config.iou)[0]
                        results.append(r)
                    infer_ms = (time.time()-start)*1000
                    self._metrics["inference_times"].append(infer_ms)

                    # draw boxes
                    if self.config.draw_boxes:
                        for r in results:
                            img = r.plot()

                    # simple line overlay
                    if self.config.count_line:
                        p1, p2 = self.config.count_line
                        cv2.line(img, p1, p2, (0,255,0), 2)

                    # object counting
                    if self.config.count_objects:
                        counts = {}
                        for r in results:
                            for box in r.boxes:
                                cls = int(box.cls)
                                if self.config.classes_filter and cls not in self.config.classes_filter:
                                    continue
                                name = r.names[cls]
                                counts[name] = counts.get(name, 0) + 1
                        for name, c in counts.items():
                            self._counters[name] = self._counters.get(name, 0) + c
                        for cb in self._callbacks["on_count"]:
                            cb(counts)

                    _, buf2 = cv2.imencode('.jpg', img)
                    processed_bytes = buf2.tobytes()
                    # notify inference event
                    for cb in self._callbacks["on_inference"]:
                        cb(frame, results)

                # push downstream
                frame.data = processed_bytes
                self._processed_queue.put(frame)
                self._metrics["frames_processed"] += 1

            except Exception as e:
                err = traceback.format_exc()
                self._metrics["last_error"] = err
                self.logger.error(err)
                for cb in self._callbacks["on_error"]:
                    cb(e)

    def output_generator(self):
        """Generator MJPEG per Flask Response."""
        boundary = b'--frame'
        while not self._stop_event.is_set():
            try:
                frame = self._processed_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            yield (
                boundary + b'\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                frame.data +
                b'\r\n'
            )

    def stream_response(self) -> Response:
        return Response(
            self.output_generator(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    def health(self) -> Dict[str,Any]:
        return {
            "running": not self._stop_event.is_set(),
            "frames_received": self._metrics["frames_received"],
            "frames_processed": self._metrics["frames_processed"],
            "queue_depth": self._frame_queue.qsize(),
        }

    def metrics(self) -> Dict[str,Any]:
        import numpy as _np
        avg = (_np.mean(self._metrics["inference_times"])
               if self._metrics["inference_times"] else 0)
        return {
            "inference_time_avg_ms": avg,
            "last_error": self._metrics["last_error"],
            "counters": self._counters,
        }

    def export_config(self) -> Dict[str,Any]:
        return self.config.dict()
