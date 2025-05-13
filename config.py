import os
from datetime import timedelta
from dotenv import load_dotenv
from ultralytics import YOLO

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ACCESS_TOKEN_EXPIRES = 3600
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ["access", "refresh"]

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    for sub in ["models", "datasets", "output", "temp", "logs", "config"]:
        os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)

    PIPELINE_CONFIGS = {

        # 1. Configurazione base: non fa nulla (nessun modello)
        "default": {
            "source": "0",
            "width": 640,
            "height": 480,
            "fps": 30,
            "models": []
        },

        # 2. Solo inferenza (disegna bbox, no conteggio)
        "external_rtsp": {
            "source": "http://pendelcam.kip.uni-heidelberg.de/mjpg/video.mjpg",
            "models": [
                {
                    "path": "data/models/yolo11n.pt",
                    "draw": True,
                    "confidence": 0.5,
                    "iou": 0.45
                }
            ]
        },

        # 3. Inferenza + conteggio attivo
        "cam_counting_example": {
            "source": "http://0.0.0.0:5000/api/ip_camera/irayple",
            "width": 640,
            "height": 480,
            "fps": 30,
            "prefetch": 10,
            "skip_on_full_queue": True,
            "quality": 95,
            "use_cuda": True,
            "max_workers": 1,
            "metrics_enabled": True,
            "classes_filter": None,
            "models": [
                {
                    "path": "data/models/scarpe_25k_305ep.pt",
                    "draw": True,
                    "confidence": 0.1,
                    "iou": 0.45,
                    "counting": {
                        "region": [(100, 0), (100, 480)],
                        "show_in": True,
                        "show_out": True,
                        "tracking": {
                            "show": False,
                            "show_labels": False,
                            "show_conf": False,
                            "verbose": False
                        }
                    }
                },
                {
                    "path": "data/models/yolo11n.pt",
                    "draw": True,
                    "confidence": 0.4,
                    "iou": 0.45,
                    "counting": {
                        "region": [(320, 0), (320, 480)],
                        "show_in": True,
                        "show_out": True,
                        "tracking": {
                            "show": False,
                            "show_labels": False,
                            "show_conf": False,
                            "verbose": False
                        }
                    }
                }
            ]
        }
    }


    MODULES = {
        "api": {"enabled": True, "prefix": "/api", "modules": ["ip_camera"]},
        "models": {"enabled": True, "modules": []},
        "jobs": {
            "enabled": True,
            "interval": timedelta(minutes=15),
            "max_instances": 10,
            "modules": [],
        },
        "threads": {
            "enabled": True,
            "modules": ["yolo_tools", "websocket"],
            "config": {
                "yolo_tools": {
                    "port": 8505,
                    "headless": True,
                    "enableCORS": False,
                    "enableXsrfProtection": False,
                    "runOnSave": False,
                    "browserServerAddress": "",
                    "browserGatherUsageStats": False,
                    "logLevel": "info",
                }
            },
        },
        "utils": {"enabled": True, "modules": ["streamlit_manager"]},
    }


class ProductionConfig(Config):
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=30)

def get_model_classes(model_path):
    model = YOLO(model_path)
    # model.names è un dict: {0: 'person', 1: 'car', ...}
    if hasattr(model, 'names'):
        return list(model.names.values())
    # fallback: nessuna classe trovata
    return []
