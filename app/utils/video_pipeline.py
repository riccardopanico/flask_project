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
    model_behaviors: Dict[str, ModelBehavior] = Field(default_factory=dict)
    count_line: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    metrics_enabled: bool = True
    classes_filter: Optional[List[int]] = None
    model_config = { 'arbitrary_types_allowed': True }

class SourceHandler:
    """
    Gestisce input da webcam o da stream HTTP MJPEG.
    """
    def __init__(self,
                 source: str,
                 width: Optional[int] = None,
                 height: Optional[int] = None,
                 fps: Optional[int] = None):
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
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Bassa latenza per webcam

    def read(self) -> Optional[np.ndarray]:
        if self.is_http:
            for chunk in self.stream_req.iter_content(chunk_size=1024):
                self.buffer += chunk
                a = self.buffer.find(b'\xff\xd8')
                b = self.buffer.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = self.buffer[a:b+2]
                    self.buffer = self.buffer[b+2:]
                    return cv2.imdecode(np.frombuffer(jpg, np.uint8),
                                         cv2.IMREAD_COLOR)
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
        # coda tra lettura e inferenza
        self._frame_q = queue.Queue(maxsize=self.config.prefetch)
        self._stop = threading.Event()
        self._seq = 0
        self._metrics = {
            "frames_received": 0,
            "frames_processed": 0,
            "inference_times": [],
            "last_error": None
        }
        # callback
        self._callbacks = {
            "on_frame": [], "on_inference": [],
            "on_count": [], "on_error": []
        }
        self.tracker = Tracker()
        self._load_models()
        # supporto flessibile sorgente
        self.pipeline_source: Optional[VideoPipeline] = (
            self.config.source
            if isinstance(self.config.source, VideoPipeline)
            else None
        )
        self.source_handler: Optional[SourceHandler] = None
        # streaming buffer & stats
        self._last_frame: Optional[bytes] = None
        self.clients_active = 0
        self.frames_served  = 0
        self.bytes_served   = 0

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
            try:
                cb(*args)
            except Exception as e:
                self._log(f"Callback error[{event}]: {e}")

    def update_config(self, **kwargs):
        old = self.config
        self.config = self.config.copy(update=kwargs)
        if "model_behaviors" in kwargs:
            self._load_models()
        if "source" in kwargs and kwargs["source"] != old.source:
            if self.source_handler:
                self.source_handler.release()
            self.pipeline_source = (
                kwargs["source"]
                if isinstance(kwargs["source"], VideoPipeline)
                else None
            )
            self.source_handler = None
        self._log(f"Config aggiornata: {kwargs}")

    def start(self):
        # init handler se serve
        if not self.pipeline_source and not self.source_handler:
            cfg = self.config
            self.source_handler = SourceHandler(
                cfg.source, cfg.width, cfg.height, cfg.fps
            )
        self._stop.clear()
        threading.Thread(target=self._read,    daemon=True, name="VP-Read").start()
        threading.Thread(target=self._process, daemon=True, name="VP-Proc").start()
        self._log("Pipeline avviata")

    def stop(self):
        self._stop.set()
        if self.source_handler:
            self.source_handler.release()
        self._log("Pipeline arrestata")

    def _read(self):
        while not self._stop.is_set():
            # sorgente flessibile
            if self.pipeline_source:
                fb = self.pipeline_source._last_frame
                if not fb:
                    time.sleep(0.05)
                    continue
                img = cv2.imdecode(np.frombuffer(fb, np.uint8), cv2.IMREAD_COLOR)
            else:
                img = self.source_handler.read()
                if img is None:
                    time.sleep(0.05)
                    continue

            try:
                _, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])  # Riduci qualità JPEG
                fr = Frame(data=buf.tobytes(), timestamp=time.time(), seq=self._seq)
                self._seq += 1
                self._frame_q.put(fr, timeout=0.1)
                self._metrics["frames_received"] += 1
                self._emit("on_frame", fr)
            except queue.Full:
                continue  # Salta frame se la coda è piena

    def _process(self):
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=8)  # Processing parallelo

        def process_frame(fr):
            try:
                img = cv2.imdecode(np.frombuffer(fr.data, np.uint8), cv2.IMREAD_COLOR)
                start = time.time()
                total_counts: Dict[str, int] = {}

                for path, mi in self.models.items():
                    beh = mi["beh"]
                    res = mi["model"](img, conf=beh.confidence, iou=beh.iou, verbose=False, device='cuda')[0]  # Passa a GPU
                    self._emit("on_inference", fr, path, res)
                    if beh.draw:
                        img = res.plot()
                    if beh.count and hasattr(res, "boxes"):
                        cnts: Dict[str, int] = {}
                        for b in res.boxes:
                            cid = int(b.cls)
                            if (self.config.classes_filter and cid not in self.config.classes_filter):
                                continue
                            name = res.names[cid]
                            cnts[name] = cnts.get(name, 0) + 1
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

        while not self._stop.is_set():
            try:
                fr = self._frame_q.get(timeout=0.1)
                executor.submit(process_frame, fr)  # Esegui inferenza in parallelo
            except queue.Empty:
                continue

    def stream_response(self):
        """
        MJPEG stream con rate-limit, timeout inattività,
        e monitoraggio risorse per client.
        """
        from flask import Response, stream_with_context, request

        client_fps = float(request.args.get('fps',
                              self.config.fps or 10))
        inactivity = float(request.args.get('timeout', 10))

        self.clients_active += 1
        last_access = [time.time()]
        boundary = b'--frame'

        def gen():
            try:
                while not self._stop.is_set():
                    frame = self._last_frame
                    if frame:
                        yield (boundary +
                               b'\r\nContent-Type: image/jpeg\r\n\r\n' +
                               frame + b'\r\n')
                        self.frames_served += 1
                        self.bytes_served += len(frame)
                        last_access[0] = time.time()

                    if time.time() - last_access[0] > inactivity:
                        break

                    time.sleep(1.0 / client_fps)
            finally:
                self.clients_active -= 1

        return Response(
            stream_with_context(gen()),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    def health(self) -> Dict[str, Any]:
        return {
            "running":        not self._stop.is_set(),
            "frames_received": self._metrics["frames_received"],
            "frames_processed": self._metrics["frames_processed"],
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
