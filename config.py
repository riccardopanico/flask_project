# config.py

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = 3600
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_TYPE = 'Bearer'
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    os.makedirs(DATA_DIR, exist_ok=True)
    for sub in ['models', 'datasets', 'output', 'temp', 'logs', 'config']:
        os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)

    # Configurazione pipeline singola di default
    PIPELINE_CONFIG = {
        "source": "0",
        "width": 1280,
        "height": 720,
        "fps": 25,
        "prefetch": 10,
        "skip_on_full_queue": True,
        "quality": 85,
        "use_cuda": True,
        "max_workers": 1,
        "model_behaviors": {
            os.path.join(DATA_DIR, "models", "yolo11n.pt"): {
                "draw": True,
                "count": False,
                "confidence": 0.5,
                "iou": 0.5
            }
        },
        "count_line": None,
        "metrics_enabled": True,
        "classes_filter": None
    }

    # Configurazione multipla (multi-camera)
    PIPELINE_CONFIGS = {
        "default": PIPELINE_CONFIG,

        "cam_front_door": {
            "source": "http://0.0.0.0:5000/api/ip_camera/stream/cam_front_door",
            "width": 1280,
            "height": 720,
            "fps": 30,
            "prefetch": 10,
            "skip_on_full_queue": True,
            "quality": 90,
            "use_cuda": True,
            "max_workers": 1,
            "model_behaviors": {
                os.path.join(DATA_DIR, "models", "yolo11n.pt"): {
                    "draw": True,
                    "count": True,
                    "confidence": 0.4,
                    "iou": 0.45
                }
            },
            "count_line": "100,200,400,200",
            "metrics_enabled": True,
            "classes_filter": ["person", "car"]
        },

        "cam_backyard": {
            "source": "http://0.0.0.0:5000/api/ip_camera/stream/cam_backyard",
            "width": 960,
            "height": 540,
            "fps": 20,
            "prefetch": 10,
            "skip_on_full_queue": True,
            "quality": 80,
            "use_cuda": False,
            "max_workers": 1,
            "model_behaviors": {
                os.path.join(DATA_DIR, "models", "yolo11n.pt"): {
                    "draw": True,
                    "count": False,
                    "confidence": 0.6,
                    "iou": 0.5
                }
            },
            "count_line": None,
            "metrics_enabled": True,
            "classes_filter": ["cat", "dog", "bird"]
        },

        "cam_garage": {
            "source": "0",  # USB camera
            "width": 640,
            "height": 480,
            "fps": 15,
            "prefetch": 5,
            "skip_on_full_queue": True,
            "quality": 70,
            "use_cuda": True,
            "max_workers": 1,
            "model_behaviors": {
                os.path.join(DATA_DIR, "models", "scarpe_25k_305ep.pt"): {
                    "draw": True,
                    "count": False,
                    "confidence": 0.5,
                    "iou": 0.5
                }
            },
            "count_line": None,
            "metrics_enabled": True,
            "classes_filter": None
        },

        "external_rtsp": {
            "source": "http://pendelcam.kip.uni-heidelberg.de/mjpg/video.mjpg",
            "width": 800,
            "height": 600,
            "fps": 10,
            "prefetch": 10,
            "skip_on_full_queue": True,
            "quality": 65,
            "use_cuda": False,
            "max_workers": 1,
            "model_behaviors": {
                os.path.join(DATA_DIR, "models", "scarpe_25k_305ep.pt"): {
                    "draw": True,
                    "count": True,
                    "confidence": 0.4,
                    "iou": 0.4
                },
                os.path.join(DATA_DIR, "models", "yolo11n.pt"): {
                    "draw": True,
                    "count": False,
                    "confidence": 0.5,
                    "iou": 0.5
                },
            },
            "count_line": None,
            "metrics_enabled": False,
            "classes_filter": ["person", "car", "truck"]
        }
    }

    MODULES = {
        'api': {
            'enabled': True,
            'prefix': '/api',
            'modules': ['ip_camera']
        },
        'models': {
            'enabled': True,
            'modules': []
        },
        'jobs': {
            'enabled': True,
            'interval': timedelta(minutes=15),
            'max_instances': 10,
            'modules': []
        },
        'threads': {
            'enabled': True,
            'modules': ['ip_camera', 'yolo_tools', 'websocket'],
            'config': {
                'yolo_tools': {
                    'port': 8505,
                    'headless': True,
                    'enableCORS': False,
                    'enableXsrfProtection': False,
                    'runOnSave': False,
                    'browserServerAddress': "",
                    'browserGatherUsageStats': False,
                    'logLevel': "info"
                },
                'ip_camera': {
                    'port': 8506,
                    'headless': True,
                    'enableCORS': False,
                    'enableXsrfProtection': False,
                    'runOnSave': False,
                    'browserServerAddress': "",
                    'browserGatherUsageStats': False,
                    'logLevel': "info"
                }
            }
        },
        'utils': {
            'enabled': True,
            'modules': ['streamlit_manager']
        }
    }

class ProductionConfig(Config):
    DEBUG = False

class DevelopmentConfig(Config):
    DEBUG = True
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(seconds=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=30)
