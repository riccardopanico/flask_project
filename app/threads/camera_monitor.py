import cv2
import time
import threading
from queue import Queue
from flask import current_app

class CameraMonitor:
    def __init__(self, app):
        self.app = app
        self.cameras = {}
        self.threads = {}
        self.running = False
        self.lock = threading.Lock()

    def discover_cameras(self):
        """Discover available RTSP cameras from configuration"""
        with self.app.app_context():
            self.app.logger.info(f"Camera monitor initialized with {len(self.app.config['CAMERA_RTSP_URLS'])} RTSP cameras")
            
            # Check RTSP cameras
            for cam_id, url in self.app.config['CAMERA_RTSP_URLS'].items():
                self.app.logger.debug(f"Checking RTSP camera {cam_id} at {url}")
                try:
                    cap = cv2.VideoCapture(url)
                    if cap.isOpened():
                        self.cameras[cam_id] = {
                            'type': 'rtsp',
                            'url': url,
                            'queue': Queue(maxsize=self.app.config['CAMERA_QUEUE_SIZE'])
                        }
                        self.app.logger.info(f"RTSP camera {cam_id} found and added")
                    else:
                        self.app.logger.warning(f"RTSP camera {cam_id} found but could not be opened")
                    cap.release()
                except Exception as e:
                    self.app.logger.error(f"Error checking RTSP camera {cam_id}: {str(e)}")

            self.app.logger.info(f"Camera discovery complete. Found {len(self.cameras)} cameras")

    def camera_worker(self, cam_id):
        """Worker thread for a camera"""
        camera = self.cameras[cam_id]
        cap = None
        
        while self.running:
            try:
                if cap is None or not cap.isOpened():
                    cap = cv2.VideoCapture(camera['url'])
                    if not cap.isOpened():
                        self.app.logger.error(f"Failed to open RTSP camera {cam_id}")
                        time.sleep(5)  # Wait before retrying
                        continue
                
                ret, frame = cap.read()
                if ret:
                    if not camera['queue'].full():
                        camera['queue'].put(frame)
                else:
                    self.app.logger.warning(f"Failed to read frame from RTSP camera {cam_id}")
                    cap.release()
                    cap = None
                    time.sleep(1)
                
                time.sleep(1/self.app.config['CAMERA_FRAME_RATE'])
            except Exception as e:
                with self.app.app_context():
                    self.app.logger.error(f"Error in RTSP camera {cam_id}: {str(e)}")
                if cap is not None:
                    cap.release()
                    cap = None
                time.sleep(1)

        if cap is not None:
            cap.release()

    def start(self):
        """Start the camera monitor"""
        with self.app.app_context():
            self.running = True
            self.discover_cameras()
            
            for cam_id in self.cameras:
                self.app.logger.info(f"Starting worker for RTSP camera {cam_id}")
                thread = threading.Thread(target=self.camera_worker, args=(cam_id,), daemon=True)
                thread.start()
                self.threads[cam_id] = thread
                self.app.logger.info(f"Started worker thread for RTSP camera {cam_id}")
            
            self.app.logger.info(f"Camera monitor started with {len(self.cameras)} RTSP cameras")

    def stop(self):
        """Stop the camera monitor"""
        self.running = False
        for thread in self.threads.values():
            thread.join(timeout=1)
        self.threads.clear()
        self.cameras.clear()

    def get_camera_status(self):
        """Get the status of all cameras"""
        with self.lock:
            return {
                cam_id: {
                    'type': cam['type'],
                    'queue_size': cam['queue'].qsize(),
                    'thread_alive': self.threads[cam_id].is_alive() if cam_id in self.threads else False
                }
                for cam_id, cam in self.cameras.items()
            }

    def get_latest_frame(self, cam_id):
        """Get the latest frame from a camera"""
        if cam_id in self.cameras:
            camera = self.cameras[cam_id]
            if not camera['queue'].empty():
                return camera['queue'].get()
        return None

def run(app):
    """Run the camera monitor"""
    camera_monitor = CameraMonitor(app)
    camera_monitor.start()
    return camera_monitor 