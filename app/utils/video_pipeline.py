# app/utils/video_pipeline.py

import cv2, time, queue, threading, traceback, os
from typing import Callable, Dict, Any, Optional, Tuple, List
import numpy as np
from pydantic import BaseModel, Field

class Frame(BaseModel):
    data: bytes
    timestamp: float
    seq: int
    meta: Optional[Dict[str,Any]] = None

class ModelBehavior(BaseModel):
    draw:       bool    = False
    count:      bool    = False
    confidence: float   = 0.5
    iou:        float   = 0.45

class PipelineConfig(BaseModel):
    source:   str
    width:    Optional[int] = None
    height:   Optional[int] = None
    fps:      Optional[int] = None
    prefetch: int           = 10
    model_behaviors: Dict[str, ModelBehavior] = Field(default_factory=dict)
    count_line: Optional[Tuple[Tuple[int,int],Tuple[int,int]]] = None
    metrics_enabled: bool = True
    classes_filter: Optional[List[int]] = None

class VideoPipeline:
    def __init__(self, config: PipelineConfig, logger: Optional[Any]=None):
        self.config = config
        self._log = logger.info if logger else lambda m: print(f"[VP] {m}")
        self._setup()

    def _setup(self):
        self._frame_q     = queue.Queue(maxsize=self.config.prefetch)
        self._processed_q = queue.Queue(maxsize=self.config.prefetch)
        self._stop        = threading.Event()
        self._seq         = 0
        self._counters    = {}
        self._metrics     = {
            "frames_received":0,
            "frames_processed":0,
            "inference_times":[],
            "last_error":None
        }
        self._callbacks   = {"on_frame":[], "on_inference":[], "on_count":[], "on_error":[]}
        self._load_models()
        self._cap = None   # verrà inizializzato in start()

    def _load_models(self):
        from ultralytics import YOLO
        self.models = {}
        for path, beh in self.config.model_behaviors.items():
            if not os.path.isfile(path):
                self._log(f"Modello NON trovato: {path}")
                continue
            if not (beh.draw or beh.count):
                continue
            try:
                m = YOLO(path)
                self.models[path] = {"model": m, "beh": beh}
                self._log(f"Caricato {path} (draw={beh.draw}, count={beh.count})")
            except Exception as e:
                self._log(f"Errore caricamento {path}: {e}")

    def register_callback(self, event: str, fn: Callable):
        if event not in self._callbacks:
            raise KeyError(f"Evento sconosciuto: {event}")
        self._callbacks[event].append(fn)

    def _emit(self, event: str, *args):
        for cb in self._callbacks[event]:
            try: cb(*args)
            except Exception as e: self._log(f"Callback error[{event}]: {e}")

    def update_config(self, **kwargs):
        self.config = self.config.copy(update=kwargs)
        if "model_behaviors" in kwargs:
            self._load_models()
        self._log(f"Config aggiornata: {kwargs}")

    def start(self):
        """Apre la camera e avvia i thread."""
        # 1) apri una sola volta la camera
        self._cap = cv2.VideoCapture(
            int(self.config.source) if self.config.source.isdigit()
            else self.config.source
        )
        # imposta solo se specificato
        if self.config.width:  self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.config.width)
        if self.config.height: self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        if self.config.fps:    self._cap.set(cv2.CAP_PROP_FPS,          self.config.fps)

        self._stop.clear()
        threading.Thread(target=self._read,    daemon=True, name="VP-Read").start()
        threading.Thread(target=self._process, daemon=True, name="VP-Proc").start()
        self._log("Pipeline avviata")

    def stop(self):
        self._stop.set()
        if self._cap and self._cap.isOpened():
            self._cap.release()
        self._log("Pipeline arrestata")

    def camera_info(self) -> Dict[str,Any]:
        """Legge le info dalla camera già aperta."""
        if not self._cap or not self._cap.isOpened():
            return {"error": "camera non disponibile"}
        # width=3, height=4, fps=5, fourcc=6     (cv2.CAP_PROP_*)
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        f = float(self._cap.get(cv2.CAP_PROP_FPS))
        fourcc_int = int(self._cap.get(cv2.CAP_PROP_FOURCC))
        fourcc = "".join(chr((fourcc_int >> 8*i) & 0xFF) for i in range(4))
        return {"width": w, "height": h, "fps": f, "fourcc": fourcc}

    def _read(self):
        """Legge frame da self._cap."""
        cap = self._cap
        if not cap or not cap.isOpened():
            self._log("Errore apertura camera in _read()")
            return
        w,h,f = cap.get(3), cap.get(4), cap.get(5)
        self._log(f"Camera aperta: {w:.0f}×{h:.0f}@{f:.1f}FPS")

        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            _, buf = cv2.imencode('.jpg', frame)
            fr = Frame(data=buf.tobytes(), timestamp=time.time(), seq=self._seq)
            self._seq += 1
            try:
                self._frame_q.put(fr, timeout=0.1)
                self._metrics["frames_received"] += 1
                self._emit("on_frame", fr)
            except queue.Full:
                continue

    def _process(self):
        import numpy as _np
        while not self._stop.is_set():
            try:
                fr = self._frame_q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if not self.models:
                    out = fr.data
                else:
                    img = cv2.imdecode(_np.frombuffer(fr.data, _np.uint8), cv2.IMREAD_COLOR)
                    start = time.time()
                    for path, mi in self.models.items():
                        beh = mi["beh"]
                        res = mi["model"](img, conf=beh.confidence, iou=beh.iou)[0]
                        self._emit("on_inference", fr, path, res)
                        if beh.draw:
                            img = res.plot()
                        if beh.count and hasattr(res, "boxes"):
                            cnts: Dict[str,int] = {}
                            for b in res.boxes:
                                cls = int(b.cls)
                                if self.config.classes_filter and cls not in self.config.classes_filter:
                                    continue
                                nm = res.names[cls]
                                cnts[nm] = cnts.get(nm,0) + 1
                            self._counters.update(cnts)
                            self._emit("on_count", fr, path, cnts)
                    dt = (time.time()-start)*1000
                    self._metrics["inference_times"].append(dt)
                    _, buf2 = cv2.imencode('.jpg', img)
                    out = buf2.tobytes()

                fr.data = out
                self._processed_q.put(fr)
                self._metrics["frames_processed"] += 1

            except Exception:
                err = traceback.format_exc()
                self._metrics["last_error"] = err
                self._emit("on_error", err)

    def output_generator(self):
        b = b'--frame'
        while not self._stop.is_set():
            try:
                fr = self._processed_q.get(timeout=0.1)
                yield b + b'\r\nContent-Type: image/jpeg\r\n\r\n' + fr.data + b'\r\n'
            except queue.Empty:
                continue

    def stream_response(self):
        from flask import Response, stream_with_context
        return Response(
            stream_with_context(self.output_generator()),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    def health(self) -> Dict[str,Any]:
        return {
            "running":    not self._stop.is_set(),
            "received":   self._metrics["frames_received"],
            "processed":  self._metrics["frames_processed"],
            "queue_depth":self._frame_q.qsize(),
        }

    def metrics(self) -> Dict[str,Any]:
        import numpy as _np
        avg = (_np.mean(self._metrics["inference_times"]) 
               if self._metrics["inference_times"] else 0)
        return {
            "avg_inf_ms": avg,
            "counters":   self._counters,
            "last_error": self._metrics["last_error"]
        }

    def export_config(self) -> Dict[str,Any]:
        return self.config.dict()
