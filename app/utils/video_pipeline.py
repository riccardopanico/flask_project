import cv2
import time
import threading
import traceback
import os
import requests
import queue
import uuid
import numpy as np
from typing import Optional, List, Dict, Any, Union, Callable
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor
from ultralytics import YOLO


class Frame(BaseModel):
    data: bytes
    timestamp: float
    seq: int
    meta: Optional[Dict[str, Any]] = None


class ModelSettings(BaseModel):
    path: str
    draw: bool = False
    confidence: float = 0.5
    iou: float = 0.45
    classes_filter: Optional[List[str]] = None


class PipelineSettings(BaseModel):
    source: Union[str, 'VideoPipeline']
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    prefetch: int = 10
    skip_on_full_queue: bool = True
    quality: int = 80
    use_cuda: bool = True
    max_workers: int = 1

    models: List[ModelSettings] = Field(default_factory=list)

    metrics_enabled: bool = True
    classes_filter: Optional[List[int]] = None

    model_config = {'arbitrary_types_allowed': True}


class SourceHandler:
    def __init__(self, source: str, width=None, height=None, fps=None):
        self.is_http = source.startswith(('http://', 'https://'))
        self.source = source
        if self.is_http:
            self.session = requests.Session()
            self.resp = self.session.get(source, stream=True)
            self.boundary = self._find_boundary()
        else:
            idx = int(source) if source.isdigit() else source
            self.cap = cv2.VideoCapture(idx)
            if width:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height:
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if fps:
                self.cap.set(cv2.CAP_PROP_FPS, fps)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def _find_boundary(self) -> bytes:
        ct = self.resp.headers.get('Content-Type', '')
        if 'boundary=' in ct:
            b = ct.split('boundary=')[-1]
            if not b.startswith('--'):
                b = '--' + b
            return b.encode()
        return b'--frame'

    def read(self) -> Optional[bytes]:
        if self.is_http:
            try:
                while True:
                    line = self.resp.raw.readline()
                    if not line:
                        return None
                    if self.boundary in line:
                        headers = {}
                        while True:
                            h = self.resp.raw.readline()
                            if not h or not h.strip():
                                break
                            k, v = h.decode().split(':', 1)
                            headers[k.strip()] = v.strip()
                        length = int(headers.get('Content-Length', '0'))
                        if length > 0:
                            return self.resp.raw.read(length)
            except:
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


class VideoPipeline:
    def __init__(self, config: PipelineSettings, logger: Optional[Any] = None):
        self.config = config
        self._log = logger.info if logger else print
        self._setup()

    def _setup(self):
        self._frame_q = queue.Queue(maxsize=self.config.prefetch)
        self._stop = threading.Event()
        self._seq = 0
        self._last_frame = None
        self._metrics = {
            'frames_received': 0,
            'frames_processed': 0,
            'inference_times': [],
            'last_error': None
        }
        self.clients_active = 0
        self.frames_served = 0
        self.bytes_served = 0

        self._load_models()
        self.pipeline_source = (
            self.config.source
            if isinstance(self.config.source, VideoPipeline)
            else None
        )
        self.source_handler = None

        self._clients: Dict[str, queue.Queue] = {}
        self._on_frame_cb: List[Callable] = []
        self._on_inference_cb: List[Callable] = []
        self._on_error_cb: List[Callable] = []
        self._processing_enabled = bool(self.config.models)

    def _load_models(self):
        self.models: Dict[str, Dict[str, Any]] = {}
        for setting in self.config.models:
            path = setting.path
            if not os.path.isfile(path):
                self._log(f"Model not found: {path}")
                continue
            try:
                yolo = YOLO(path, verbose=False)
                entry = {'yolo': yolo, 'setting': setting}
                self.models[path] = entry
                self._log(f"Loaded model: {os.path.basename(path)}")
            except Exception as e:
                self._log(f"Error loading {path}: {e}")

    def register_callback(self, event: str, fn: Callable):
        if event not in ('frame', 'inference', 'error'):
            raise KeyError(f"Unknown event: {event}")
        getattr(self, f"_on_{event}_cb").append(fn)

    def _emit(self, event: str, *args):
        for cb in getattr(self, f"_on_{event}_cb"): 
            try:
                cb(*args)
            except Exception as e:
                self._log(f"Callback {event} error: {e}")

    def start(self):
        self._stop.clear()
        self._frame_q = queue.Queue(maxsize=self.config.prefetch)
        self._last_frame = None
        self._metrics['frames_received'] = 0
        self._metrics['frames_processed'] = 0
        self.frames_served = 0
        self.bytes_served = 0

        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        if not self.pipeline_source:
            self.source_handler = SourceHandler(
                str(self.config.source),
                self.config.width,
                self.config.height,
                self.config.fps
            )
        threading.Thread(target=self._ingest_loop, daemon=True).start()
        threading.Thread(target=self._process_loop, daemon=True).start()
        self._log("Pipeline started")

    def stop(self):
        self._stop.set()
        time.sleep(0.05)
        if self.source_handler:
            self.source_handler.release()
            self.source_handler = None
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False, cancel_futures=True)
        self._log("Pipeline stopped")

    def _ingest_loop(self):
        while not self._stop.is_set():
            data = (
                self.pipeline_source._last_frame
                if self.pipeline_source
                else self.source_handler.read()
            )
            if not data:
                time.sleep(0.005)
                continue
            frm = Frame(data=data, timestamp=time.time(), seq=self._seq)
            self._seq += 1
            self._metrics['frames_received'] += 1
            self._emit('frame', frm)
            try:
                self._frame_q.put(
                    frm,
                    block=not self.config.skip_on_full_queue,
                    timeout=0.01
                )
            except queue.Full:
                if not self.config.skip_on_full_queue:
                    time.sleep(0.005)

    def _process_loop(self):
        def worker(frm: Frame):
            try:
                # Decodifica il frame JPEG in immagine OpenCV
                orig = cv2.imdecode(np.frombuffer(frm.data, np.uint8), cv2.IMREAD_COLOR)

                # Ridimensionamento se richiesto
                if self.config.width and self.config.height:
                    if orig.shape[1] != self.config.width or orig.shape[0] != self.config.height:
                        orig = cv2.resize(orig, (self.config.width, self.config.height), interpolation=cv2.INTER_LINEAR)

                canvas = orig.copy()
                start = time.time()

                for path, info in list(self.models.items()):
                    setting: ModelSettings = info['setting']
                    model = info['yolo']

                    # Filtro classi (converti nomi in indici)
                    classes = None
                    if setting.classes_filter:
                        name_to_idx = {v: k for k, v in model.names.items()}
                        classes = [name_to_idx[c] for c in setting.classes_filter if c in name_to_idx]

                    # Inference
                    res = model(
                        orig,
                        conf=setting.confidence,
                        iou=setting.iou,
                        classes=classes,
                        verbose=False,
                        device='cuda' if self.config.use_cuda else 'cpu'
                    )[0]

                    self._emit('inference', frm, path, res)

                    # Se disegno attivo
                    if setting.draw:
                        overlay = res.plot()[:, :, :3]
                        mask = np.any(overlay != orig, axis=-1)
                        canvas[mask] = overlay[mask]

                # Tempo di inferenza
                dt = (time.time() - start) * 1000
                self._metrics['inference_times'].append(dt)

                # Codifica JPEG e salva l'ultimo frame
                _, buf = cv2.imencode('.jpg', canvas, [int(cv2.IMWRITE_JPEG_QUALITY), self.config.quality])
                jpg = buf.tobytes()
                self._last_frame = jpg
                self._metrics['frames_processed'] += 1

                # Invia il frame ai client connessi
                for q in list(self._clients.values()):
                    try:
                        q.put_nowait(jpg)
                    except queue.Full:
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            pass
                        q.put_nowait(jpg)

            except Exception:
                err = traceback.format_exc()
                self._metrics['last_error'] = err
                self._emit('error', err)

        while not self._stop.is_set():
            try:
                frm = self._frame_q.get(timeout=0.01)
                self._executor.submit(worker, frm)
            except queue.Empty:
                continue

    def stream_response(self):
        from flask import Response, stream_with_context, request
        cid = str(uuid.uuid4())
        q = queue.Queue(maxsize=1)
        self._clients[cid] = q
        self.clients_active += 1
        fps = float(request.args.get('fps', self.config.fps or 30))
        timeout = float(request.args.get('timeout', 5))
        boundary = b'--frame'
        fallback = np.zeros((480, 640, 3), np.uint8)
        cv2.putText(
            fallback,
            "No signal",
            (200, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )
        _, fb_buf = cv2.imencode('.jpg', fallback)
        fb_jpg = fb_buf.tobytes()

        def gen():
            try:
                while not self._stop.is_set():
                    try:
                        frame = q.get(timeout=timeout)
                    except queue.Empty:
                        frame = fb_jpg
                        self._log("Sending fallback frame")
                    yield (
                        boundary
                        + b'\r\nContent-Type: image/jpeg\r\n\r\n'
                        + frame
                        + b'\r\n'
                    )
                    self.frames_served += 1
                    self.bytes_served += len(frame)
                    time.sleep(1.0 / fps)
            finally:
                self.clients_active -= 1
                self._clients.pop(cid, None)

        return Response(
            stream_with_context(gen()),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    def update_config(self, **kwargs):
        reload_models = False
        restart = False
        if 'models' in kwargs:
            new_list = [
                ModelSettings(**m) if isinstance(m, dict) else m
                for m in kwargs.pop('models')
            ]
            self.config.models = new_list
            reload_models = True
        for key in ('prefetch', 'max_workers'):
            if key in kwargs:
                restart = True
        for k, v in kwargs.items():
            setattr(self.config, k, v)
        if reload_models:
            self._load_models()
        if restart:
            self.stop()
            time.sleep(0.05)
            self.start()
        self._log(f"Config updated: {kwargs}, models: {[m.dict() for m in self.config.models]}")

    def health(self) -> Dict[str, Any]:
        t = self._metrics['inference_times']
        return {
            'running': not self._stop.is_set(),
            'frames_received': self._metrics['frames_received'],
            'frames_processed': self._metrics['frames_processed'],
            'clients_active': self.clients_active,
            'last_error': self._metrics['last_error'],
            'avg_inf_ms': round(np.mean(t), 2) if t else 0,
            'min_inf_ms': round(np.min(t), 2) if t else 0,
            'max_inf_ms': round(np.max(t), 2) if t else 0
        }

    def metrics(self) -> Dict[str, Any]:
        avg = np.mean(self._metrics['inference_times']) if self._metrics['inference_times'] else 0
        return {
            'avg_inf_ms': avg,
            'frames_served': self.frames_served,
            'bytes_served': self.bytes_served,
            'last_error': self._metrics['last_error']
        }

    def export_config(self) -> Dict[str, Any]:
        cfg = self.config.dict()
        cfg['models'] = [m.dict() for m in self.config.models]
        return cfg
