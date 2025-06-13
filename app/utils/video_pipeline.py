import cv2
import time
import threading
import traceback
import os
import requests
import queue
import uuid
import numpy as np
from typing import Optional, List, Tuple, Dict, Any, Union, Callable
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor
from ultralytics import YOLO
# from ultralytics.solutions.object_counter import ObjectCounter
from app.utils.ObjectCounter import ObjectCounter
from collections import defaultdict

from ultralytics.utils import LOGGER
LOGGER.setLevel('ERROR')

class Frame(BaseModel):
    data: bytes
    timestamp: float
    seq: int
    meta: Optional[Dict[str, Any]] = None


class TrackingSettings(BaseModel):
    show: bool = False
    show_labels: bool = True
    show_conf: bool = True
    verbose: bool = False
    tracker: str = "botsort.yaml"


class ModelCountingSettings(BaseModel):
    region: List[Tuple[int, int]]
    show_in: bool = False
    show_out: bool = False
    show: bool = False
    id_timeout: float = 5.0
    min_frames_before_count: int = 3
    tracking: TrackingSettings = Field(default_factory=TrackingSettings)


class ModelSettings(BaseModel):
    path: str
    draw: bool = False
    confidence: float = 0.5
    iou: float = 0.45
    classes_filter: Optional[List[str]] = None
    counting: Optional[ModelCountingSettings] = None


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
    source_name: Optional[str] = None
    log_level: Optional[str] = "INFO"
    enable_counting: Optional[bool] = True
    show_window: Optional[bool] = False
    tracker: Optional[str] = 'botsort.yaml'

    model_config = {'arbitrary_types_allowed': True}

class SourceHandler:
    def __init__(self, source: str, width=None, height=None, fps=None):
        self.is_http = source.startswith(('http://', 'https://'))
        self.is_file = (not self.is_http) and os.path.isfile(source)
        self.source = source
        self.frames_read = 0

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
            
            if self.is_file:
                self.frames_read += 1
            
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

class EnhancedObjectCounter(ObjectCounter):
    def __init__(self, **kwargs):
        self.id_timeout = kwargs.pop('id_timeout', 5.0)
        self.min_frames_before_count = kwargs.pop('min_frames_before_count', 3)
        self.on_count_callback = kwargs.pop('on_count_callback', None)
        super().__init__(**kwargs)
        self.id_timestamps = {}
        self.id_directions = {}
        self.id_positions = defaultdict(list)
        self.last_cleanup_time = time.time()
        self.cleanup_interval = 1.0
        self._callback_executor = ThreadPoolExecutor(max_workers=2)

    def display_output(self, plot_im):
        pass

    def display_counts(self, plot_im):
        # Sovrascrive il metodo della classe padre per non mostrare i conteggi in alto a destra
        pass

    def extract_tracks(self, im0):
        pass

    def set_external_results(self, result):
        boxes = result.boxes
        self.track_data = boxes
        self.tracks = [result]
        self.boxes = boxes.xyxy.cpu()
        self.clss = [int(c) for c in boxes.cls.cpu().tolist()]
        self.track_ids = (
            boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(self.boxes)
        )
        self.confs = boxes.conf.cpu().tolist()

    def _trigger_count_event(self, track_id, cls, direction, position, now):
        if not self.on_count_callback:
            return

        count_data = {
            'track_id': track_id,
            'class': self.names[cls],
            'direction': direction,
            'timestamp': now,
            'position': position,
            'model_path': getattr(self, 'model_path', None)
        }

        if not all(k in count_data for k in ('track_id', 'class', 'direction', 'timestamp')):
            return

        def safe_callback(data):
            try:
                self.on_count_callback(data)
            except Exception as e:
                print(f"[WARN] Count callback failed: {e}")

        self._callback_executor.submit(safe_callback, count_data)

    def _update_counts(self, track_id, cls, direction, current_centroid, now):
        if direction == 'in':
            self.in_count += 1
            self.classwise_counts[self.names[cls]]['IN'] += 1
        else:
            self.out_count += 1
            self.classwise_counts[self.names[cls]]['OUT'] += 1

        self.counted_ids.append(track_id)
        self.id_timestamps[track_id] = now
        self.id_directions[track_id] = direction

        self._trigger_count_event(track_id, cls, direction, current_centroid, now)

    def count_objects(self, current_centroid, track_id, prev_position, cls):
        if prev_position is None:
            return
        positions = self.id_positions[track_id]
        positions.append(current_centroid)
        if len(positions) > 30:
            positions.pop(0)
        if len(positions) < self.min_frames_before_count:
            return

        line = self.LineString(self.region)
        if line.intersects(self.LineString([prev_position, current_centroid])):
            is_vertical = (
                abs(self.region[0][0] - self.region[1][0]) < abs(self.region[0][1] - self.region[1][1])
            )
            oldest = positions[0]
            direction = 'in' if (current_centroid[0] > oldest[0] if is_vertical else current_centroid[1] > oldest[1]) else 'out'
            now = time.time()
            if track_id in self.id_directions:
                prev_dir = self.id_directions[track_id]
                prev_ts = self.id_timestamps[track_id]
                if prev_dir == direction or now - prev_ts < self.id_timeout:
                    return
            self._update_counts(track_id, cls, direction, current_centroid, now)

    def cleanup_expired_ids(self):
        now = time.time()
        if now - self.last_cleanup_time < self.cleanup_interval:
            return
        self.last_cleanup_time = now
        expired = [tid for tid, ts in self.id_timestamps.items() if now - ts > self.id_timeout]
        for tid in expired:
            if tid in self.counted_ids:
                self.counted_ids.remove(tid)
            self.id_timestamps.pop(tid, None)
            self.id_directions.pop(tid, None)
            self.id_positions.pop(tid, None)

    def process(self, im0):
        self.cleanup_expired_ids()
        if not hasattr(self, 'track_data') or self.boxes is None:
            return None
        return super().process(im0)

class VideoPipeline:
    def __init__(self, config: PipelineSettings, logger: Optional[Any] = None):
        self.config = config
        self._log = logger.info if logger else print
        self._setup()

    def _load_models(self):
        self.models = {}
        for setting in self.config.models:
            path = setting.path
            if not os.path.isfile(path):
                self._log(f"Model not found: {path}")
                continue
            try:
                yolo = YOLO(path, verbose=False)
                self.models[path] = {'yolo': yolo, 'setting': setting}
                self._log(f"Loaded model: {os.path.basename(path)}")
            except Exception as e:
                self._log(f"Error loading {path}: {e}")

    def _setup(self):
        self._load_models()
        self.counters = {}
        for path, info in self.models.items():
            setting = info['setting']
            cinfo = setting.counting
            if not cinfo:
                continue
            region   = cinfo.region
            show_in  = False
            show_out = False
            tck      = cinfo.tracking
            cnt = EnhancedObjectCounter(
                show=False,
                model=None,
                region=region,
                classes=None,
                conf=setting.confidence,
                tracker=tck.tracker,
                show_conf=False,
                show_labels=tck.show_labels,
                verbose=tck.verbose,
                show_in=False,
                show_out=False,
                id_timeout=cinfo.id_timeout,
                min_frames_before_count=cinfo.min_frames_before_count,
                on_count_callback=lambda data, p=path: self._emit('count', {**data, 'model_path': p})
            )
            cnt.names = info['yolo'].names
            cnt.model_path = path
            self.counters[path] = cnt

        self.pipeline_source = self.config.source if isinstance(self.config.source, VideoPipeline) else None
        self.source_handler = None
        self._frame_q = queue.Queue(maxsize=self.config.prefetch)
        self._stop = threading.Event()
        self._seq = 0
        self._last_frame = None
        self._metrics = {'frames_received': 0, 'frames_processed': 0, 'inference_times': [], 'last_error': None}
        self.clients_active = 0
        self.frames_served = 0
        self.bytes_served = 0
        self._clients = {}
        self._on_frame_cb = []
        self._on_inference_cb = []
        self._on_error_cb = []
        self._on_count_cb = []
        self._processing_enabled = bool(self.config.models)

    def register_callback(self, event: str, fn: Callable):
        if event not in ('frame', 'inference', 'error', 'count'):
            raise KeyError(f"Unknown event: {event}")
        getattr(self, f"_on_{event}_cb").append(fn)

    def _emit(self, event: str, *args):
        for cb in getattr(self, f"_on_{event}_cb"): cb(*args)

    def start(self):
        self._stop.clear()
        self._frame_q.queue.clear()
        self._last_frame = None
        self._metrics.update(frames_received=0, frames_processed=0, inference_times=[], last_error=None)
        self.frames_served = 0
        self.bytes_served  = 0
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        if not self.pipeline_source:
            self.source_handler = SourceHandler(str(self.config.source), self.config.width, self.config.height, self.config.fps)
        threading.Thread(target=self._ingest_loop, daemon=True).start()
        threading.Thread(target=self._process_loop, daemon=True).start()
        self._log("Pipeline started")

    def stop(self):
        self._stop.set()
        time.sleep(0.05)
        if self.source_handler:
            self.source_handler.release()
            self.source_handler = None
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._log("Pipeline stopped")

    def _ingest_loop(self):
        last_frame_time = time.time()
        target_fps = None
        
        # Per i file video, usa gli FPS del file o quelli configurati
        if self.source_handler and getattr(self.source_handler, 'is_file', False):
            if hasattr(self.source_handler, 'cap'):
                video_fps = self.source_handler.cap.get(cv2.CAP_PROP_FPS)
                target_fps = self.config.fps if self.config.fps else video_fps
        
        while not self._stop.is_set():
            # Controllo velocità per file video
            if target_fps and target_fps > 0:
                current_time = time.time()
                elapsed = current_time - last_frame_time
                target_interval = 1.0 / target_fps
                
                if elapsed < target_interval:
                    sleep_time = target_interval - elapsed
                    time.sleep(sleep_time)
                
                last_frame_time = time.time()
            
            data = (self.pipeline_source._last_frame if self.pipeline_source
                    else self.source_handler.read())

            if data is None:
                if self.source_handler and getattr(self.source_handler, 'is_file', False):
                    self._log("Fine del file video, stopping pipeline")
                    self.stop()
                    break
                time.sleep(0.005)
                continue

            frm = Frame(data=data, timestamp=time.time(), seq=self._seq)
            self._seq += 1
            self._metrics['frames_received'] += 1
            self._emit('frame', frm)
            try:
                self._frame_q.put(frm,
                    block=not self.config.skip_on_full_queue,
                    timeout=0.01)
            except queue.Full:
                if not self.config.skip_on_full_queue:
                    time.sleep(0.005)

    def _process_loop(self):
        def worker(frm: Frame):
            try:
                orig = cv2.imdecode(np.frombuffer(frm.data, np.uint8), cv2.IMREAD_COLOR)
                if self.config.width and self.config.height:
                    orig = cv2.resize(orig, (self.config.width, self.config.height), interpolation=cv2.INTER_LINEAR)
                canvas = orig.copy()
                start = time.time()
                for path, info in list(self.models.items()):
                    setting = info['setting']
                    model   = info['yolo']
                    classes = None
                    if setting.classes_filter:
                        name_to_idx = {v: k for k,v in model.names.items()}
                        classes = [name_to_idx[c] for c in setting.classes_filter if c in name_to_idx]
                    res = model.track(
                        orig,
                        conf=setting.confidence,
                        iou=setting.iou,
                        classes=classes,
                        verbose=False,
                        device='cuda' if self.config.use_cuda else 'cpu',
                        persist=True,
                        tracker='botsort.yaml'
                    )[0]
                    self._emit('inference', frm, path, res)
                    if path in self.counters:
                        cnt = self.counters[path]
                        cnt.set_external_results(res)
                        out = cnt.process(canvas)
                        if out is not None and hasattr(out, 'plot_im'):
                            canvas = out.plot_im
                    elif setting.draw:
                        overlay = res.plot()[:,:,:3]
                        mask = np.any(overlay != orig, axis=-1)
                        canvas[mask] = overlay[mask]
                dt = (time.time() - start) * 1000
                self._metrics['inference_times'].append(dt)
                _, buf = cv2.imencode('.jpg', canvas, [int(cv2.IMWRITE_JPEG_QUALITY), self.config.quality])
                jpg = buf.tobytes()
                self._last_frame = jpg
                self._metrics['frames_processed'] += 1
                for q in list(self._clients.values()):
                    try: q.put_nowait(jpg)
                    except queue.Full:
                        try: q.get_nowait()
                        except: pass
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
        fallback = np.zeros((480,640,3), np.uint8)
        cv2.putText(fallback,'No signal',(200,240),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
        _, fb = cv2.imencode('.jpg', fallback)
        fb_jpg = fb.tobytes()
        def gen():
            try:
                while not self._stop.is_set():
                    try: frame = q.get(timeout=timeout)
                    except queue.Empty:
                        frame = fb_jpg
                    yield boundary + b'\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                    self.frames_served += 1
                    self.bytes_served += len(frame)
                    time.sleep(1.0 / fps)
            finally:
                self.clients_active -= 1
                self._clients.pop(cid, None)
        return Response(stream_with_context(gen()), mimetype='multipart/x-mixed-replace; boundary=frame')

    def update_config(self, **kwargs):
        reload_models = False
        restart = False
        if 'models' in kwargs:
            self.config.models = [ModelSettings(**m) if isinstance(m, dict) else m for m in kwargs.pop('models')]
            reload_models = True
        for k in ('prefetch','max_workers'):
            if k in kwargs: restart = True
        for k,v in kwargs.items(): setattr(self.config,k,v)
        if reload_models:
            self._load_models()
        if restart:
            self.stop()
            time.sleep(0.05)
            self.start()
        self._log(f"Config updated: {kwargs}, models: {[m.dict() for m in self.config.models]}")
        # aggiorna contatori
        for path in list(self.counters):
            setting = next((m for m in self.config.models if m.path==path), None)
            if not setting or not setting.counting:
                del self.counters[path]
            else:
                cinfo = setting.counting
                cnt = self.counters[path]
                cnt.region = cinfo.region
                cnt.show_in = False
                cnt.show_out = False
                cnt.id_timeout = cinfo.id_timeout
                cnt.min_frames_before_count = cinfo.min_frames_before_count
        for setting in self.config.models:
            path = setting.path
            cinfo = setting.counting
            if cinfo and path not in self.counters:
                region   = cinfo.region
                show_in  = False
                show_out = False
                tck      = cinfo.tracking
                cnt = EnhancedObjectCounter(
                    model=None,
                    region=region,
                    classes=None,
                    conf=setting.confidence,
                    tracker=tck.tracker,
                    show=False,
                    show_conf=False,
                    show_labels=tck.show_labels,
                    verbose=tck.verbose,
                    show_in=False,
                    show_out=False,
                    id_timeout=cinfo.id_timeout,
                    min_frames_before_count=cinfo.min_frames_before_count,
                    on_count_callback=lambda data, p=path: self._emit('count', {**data, 'model_path': p})
                )
                cnt.names = self.models[path]['yolo'].names
                cnt.model_path = path
                self.counters[path] = cnt

    def health(self) -> Dict[str, Any]:
        t = self._metrics['inference_times']
        return {
            'running': not self._stop.is_set(),
            'frames_received': self._metrics['frames_received'],
            'frames_processed': self._metrics['frames_processed'],
            'clients_active': self.clients_active,
            'last_error': self._metrics['last_error'],
            'avg_inf_ms': round(np.mean(t),2) if t else 0,
            'min_inf_ms': round(np.min(t),2) if t else 0,
            'max_inf_ms': round(np.max(t),2) if t else 0
        }

    def metrics(self) -> Dict[str, Any]:
        avg = np.mean(self._metrics['inference_times']) if self._metrics['inference_times'] else 0
        counters = {n: c.in_count + c.out_count for n,c in self.counters.items()}
        return {
            'avg_inf_ms': avg,
            'frames_served': self.frames_served,
            'bytes_served': self.bytes_served,
            'last_error': self._metrics['last_error'],
            'counters': counters
        }

    def export_config(self) -> Dict[str, Any]:
        cfg = self.config.dict()
        cfg['models'] = [m.dict() for m in self.config.models]
        return cfg
