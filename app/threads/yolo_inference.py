import os
import glob
import time
import shutil
import yaml
import subprocess
import cv2
import queue
import threading
import io
from datetime import datetime
import torch
import streamlit as st
import numpy as np
from ultralytics import YOLO
from contextlib import redirect_stdout
from flask import current_app
from config.config import Config

class YOLOInferenceThread:
    def __init__(self, app):
        self.app = app
        self.config = app.config
        self.running = False
        self.thread = None
        self.video_queues = {}
        self.video_threads = {}
        self.video_writers = {}
        self.detection_stats = {
            "total_objects": 0,
            "class_counts": {},
            "last_update": None
        }

    def list_available_cameras(self, max_cameras=10):
        available = []
        # Check local webcams
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append({
                    "id": f"webcam_{i}",
                    "name": f"Webcam {i}",
                    "type": "webcam",
                    "index": i
                })
                cap.release()
        
        # Add IP cameras from config
        for cam_id, url in self.config.CAMERA_RTSP_URLS.items():
            available.append({
                "id": cam_id,
                "name": f"IP Camera {cam_id}",
                "type": "ip",
                "url": url
            })
        return available

    def load_model(self, model_path):
        try:
            return YOLO(model_path)
        except Exception as e:
            st.error(f"Error loading model: {str(e)}")
            return None

    def process_frame(self, frame, model, params):
        if model is None:
            return frame, []

        results = model(
            frame,
            conf=params["confidence"],
            iou=params["iou_threshold"],
            device=params["device"]
        )

        # Update detection statistics
        if results[0].boxes is not None:
            for box in results[0].boxes:
                class_id = int(box.cls[0])
                class_name = model.names[class_id]
                self.detection_stats["total_objects"] += 1
                self.detection_stats["class_counts"][class_name] = self.detection_stats["class_counts"].get(class_name, 0) + 1
            self.detection_stats["last_update"] = datetime.now()

        return results[0].plot(), results[0].boxes

    def camera_worker(self, camera_info, model, params):
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
            processed_frame, detections = self.process_frame(frame, model, params)
            
            # Put frame in queue for display
            self.video_queues[camera_id].put((processed_frame, detections))
            
            time.sleep(1/30)  # Cap at 30 FPS

        cap.release()

    def run_training(self, model_path, dataset_path, params):
        model = YOLO(model_path)
        train_args = {
            "data": dataset_path,
            "epochs": params["epochs"],
            "batch": params["batch_size"],
            "imgsz": params["img_size"],
            "device": params["device"],
            "project": os.path.join(self.config.OUTPUT_DIR, "training"),
            "name": datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        
        with st.spinner("Training in progress..."):
            results = model.train(**train_args)
            st.success("Training completed!")
            return results

    def run(self):
        st.title("YOLO Model Inference & Training")
        
        # Sidebar configuration
        with st.sidebar:
            st.header("Configuration")
            
            # Model selection
            model_path = st.file_uploader("Upload YOLO model", type=["pt"])
            model = None
            if model_path:
                model = self.load_model(model_path)
            
            # Inference parameters
            st.subheader("Inference Parameters")
            inference_params = {
                "confidence": st.slider("Confidence Threshold", 0.0, 1.0, self.config.INFERENCE_CONFIDENCE),
                "iou_threshold": st.slider("IoU Threshold", 0.0, 1.0, self.config.INFERENCE_IOU),
                "device": st.selectbox("Device", ["cuda", "cpu"], index=0 if self.config.INFERENCE_DEVICE == "cuda" else 1),
                "frame_skip": st.slider("Process every N frames", 1, 10, self.config.INFERENCE_FRAME_SKIP)
            }
            
            # Camera selection
            st.subheader("Available Cameras")
            available_cameras = self.list_available_cameras()
            selected_cameras = st.multiselect(
                "Select cameras to monitor",
                [cam["name"] for cam in available_cameras],
                default=[cam["name"] for cam in available_cameras[:1]]
            )

            # Training section
            st.subheader("Training")
            if st.checkbox("Show Training Options"):
                train_params = {
                    "epochs": st.number_input("Epochs", 1, 1000, self.config.TRAIN_EPOCHS),
                    "batch_size": st.number_input("Batch Size", 1, 128, self.config.TRAIN_BATCH_SIZE),
                    "img_size": st.number_input("Image Size", 32, 1280, self.config.TRAIN_IMG_SIZE, 32),
                    "device": st.selectbox("Training Device", ["cuda", "cpu"], index=0 if self.config.TRAIN_DEVICE == "cuda" else 1)
                }
                
                dataset_path = st.file_uploader("Upload Dataset Config", type=["yaml"])
                if st.button("Start Training") and dataset_path:
                    self.run_training(model_path, dataset_path, train_params)

        # Main content area
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.header("Camera Feeds")
            # Create placeholders for each selected camera
            camera_placeholders = {}
            for camera in available_cameras:
                if camera["name"] in selected_cameras:
                    camera_placeholders[camera["id"]] = st.empty()
                    self.video_queues[camera["id"]] = queue.Queue(maxsize=1)
                    if camera["id"] not in self.cameras:
                        self.cameras[camera["id"]] = threading.Thread(
                            target=self.camera_worker,
                            args=(camera, model, inference_params),
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
    """Run the YOLO inference app"""
    with app.app_context():
        app.logger.info("Starting YOLO inference app")
        
        # Get configuration from app
        config = app.config['MODULES']['threads']['config']['yolo_inference']
        
        # Initialize YOLO model
        model = YOLO('yolov8n.pt')
        
        # Streamlit app
        st.title("YOLO Object Detection")
        
        # Camera selection
        camera_index = st.selectbox("Select Camera", options=[0, 1, 2])
        
        # Start video capture
        cap = cv2.VideoCapture(camera_index)
        
        # Create placeholder for video
        placeholder = st.empty()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                st.error("Failed to read from camera")
                break
                
            # Run YOLO inference
            results = model(frame)
            
            # Draw results
            annotated_frame = results[0].plot()
            
            # Display the frame
            placeholder.image(annotated_frame, channels="BGR")
            
            # Add a small delay
            time.sleep(0.1)
            
        cap.release() 