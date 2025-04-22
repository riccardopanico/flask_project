import os
import cv2
import time
import threading
import streamlit as st
import torch
from ultralytics import YOLO
from datetime import datetime
from queue import Queue

class CameraMonitor:
    def __init__(self, app):
        self.app = app
        self.cameras = {}
        self.inference_queues = {}
        self.video_queues = {}
        self.running = False
        self.thread = None
        self.model = None
        self.inference_params = {
            "confidence": 0.5,
            "iou_threshold": 0.45,
            "device": "cuda" if torch.cuda.is_available() else "cpu",
            "frame_skip": 1
        }
        self.detection_stats = {
            "total_objects": 0,
            "class_counts": {},
            "last_update": None
        }

    def discover_cameras(self):
        """Scans for available IP cameras and webcams"""
        available = []
        # Check local webcams
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append({
                    "id": f"webcam_{i}",
                    "name": f"Webcam {i}",
                    "type": "webcam",
                    "index": i
                })
                cap.release()
        
        # Add some example IP cameras (you should replace these with your actual IP cameras)
        available.extend([
            {
                "id": "ip_cam_1",
                "name": "IP Camera 1",
                "type": "ip",
                "url": "rtsp://admin:password@192.168.1.100:554/stream1"
            },
            {
                "id": "ip_cam_2",
                "name": "IP Camera 2",
                "type": "ip",
                "url": "rtsp://admin:password@192.168.1.101:554/stream1"
            }
        ])
        return available

    def load_model(self, model_path):
        """Loads the YOLO model"""
        try:
            self.model = YOLO(model_path)
            return True
        except Exception as e:
            st.error(f"Error loading model: {str(e)}")
            return False

    def update_inference_params(self, params):
        """Updates inference parameters"""
        self.inference_params.update(params)

    def process_frame(self, frame, camera_id):
        """Processes a single frame with YOLO"""
        if self.model is None:
            return frame, []

        results = self.model(
            frame,
            conf=self.inference_params["confidence"],
            iou=self.inference_params["iou_threshold"],
            device=self.inference_params["device"]
        )

        # Update detection statistics
        if results[0].boxes is not None:
            for box in results[0].boxes:
                class_id = int(box.cls[0])
                class_name = self.model.names[class_id]
                self.detection_stats["total_objects"] += 1
                self.detection_stats["class_counts"][class_name] = self.detection_stats["class_counts"].get(class_name, 0) + 1
            self.detection_stats["last_update"] = datetime.now()

        return results[0].plot(), results[0].boxes

    def camera_worker(self, camera_info):
        """Worker thread for each camera"""
        camera_id = camera_info["id"]
        cap = cv2.VideoCapture(
            camera_info["index"] if camera_info["type"] == "webcam" else camera_info["url"]
        )

        while self.running and cap.isOpened():
            success, frame = cap.read()
            if not success:
                time.sleep(0.1)
                continue

            # Process frame with YOLO
            processed_frame, detections = self.process_frame(frame, camera_id)
            
            # Put frame in queue for display
            self.video_queues[camera_id].put((processed_frame, detections))
            
            time.sleep(1/30)  # Cap at 30 FPS

        cap.release()

    def run(self):
        """Main thread function"""
        st.title("Camera Monitoring System")
        
        # Sidebar configuration
        with st.sidebar:
            st.header("Configuration")
            
            # Model selection
            model_path = st.file_uploader("Upload YOLO model", type=["pt"])
            if model_path:
                if not self.model:
                    self.load_model(model_path)
            
            # Inference parameters
            st.subheader("Inference Parameters")
            self.inference_params["confidence"] = st.slider("Confidence Threshold", 0.0, 1.0, 0.5)
            self.inference_params["iou_threshold"] = st.slider("IoU Threshold", 0.0, 1.0, 0.45)
            self.inference_params["frame_skip"] = st.slider("Process every N frames", 1, 10, 1)
            
            # Camera selection
            st.subheader("Available Cameras")
            available_cameras = self.discover_cameras()
            selected_cameras = st.multiselect(
                "Select cameras to monitor",
                [cam["name"] for cam in available_cameras],
                default=[cam["name"] for cam in available_cameras[:1]]
            )

        # Main content area
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.header("Camera Feeds")
            # Create placeholders for each selected camera
            camera_placeholders = {}
            for camera in available_cameras:
                if camera["name"] in selected_cameras:
                    camera_placeholders[camera["id"]] = st.empty()
                    self.video_queues[camera["id"]] = Queue(maxsize=1)
                    if camera["id"] not in self.cameras:
                        self.cameras[camera["id"]] = threading.Thread(
                            target=self.camera_worker,
                            args=(camera,),
                            daemon=True
                        )
                        self.cameras[camera["id"]].start()

        with col2:
            st.header("Detection Statistics")
            stats_placeholder = st.empty()
            
            # Start/Stop button
            if st.button("Start Monitoring"):
                self.running = True
                for camera_id, thread in self.cameras.items():
                    if not thread.is_alive():
                        thread.start()
            
            if st.button("Stop Monitoring"):
                self.running = False
                for thread in self.cameras.values():
                    thread.join()
                self.cameras.clear()

        # Update displays
        while self.running:
            # Update camera feeds
            for camera_id, placeholder in camera_placeholders.items():
                if not self.video_queues[camera_id].empty():
                    frame, detections = self.video_queues[camera_id].get()
                    placeholder.image(frame, channels="BGR", use_column_width=True)
            
            # Update statistics
            with stats_placeholder.container():
                st.metric("Total Objects Detected", self.detection_stats["total_objects"])
                st.write("Class Distribution:")
                for class_name, count in self.detection_stats["class_counts"].items():
                    st.write(f"- {class_name}: {count}")
                if self.detection_stats["last_update"]:
                    st.write(f"Last Update: {self.detection_stats['last_update'].strftime('%H:%M:%S')}")
            
            time.sleep(0.1)

def run(app):
    """Entry point for the thread"""
    monitor = CameraMonitor(app)
    monitor.run() 