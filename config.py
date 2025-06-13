import os
from datetime import timedelta
from dotenv import load_dotenv
from ultralytics import YOLO
import copy

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
    MODELS_DIR = os.path.join(DATA_DIR, "models")
    os.makedirs(DATA_DIR, exist_ok=True)
    for sub in ["models", "datasets", "output", "temp", "logs", "config"]:
        os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_DIR = os.path.join(DATA_DIR, "logs")
    LOG_FILE = os.path.join(LOG_DIR, "app.log")

    

    # PIPELINE_CONFIGS = {
    #     "Gianel - Manovia 1": {
    #         "source": "0",
    #         "width": 640,
    #         "height": 480,
    #         "fps": 30,
    #         "prefetch": 10,
    #         "skip_on_full_queue": True,
    #         "quality": 95,
    #         "use_cuda": True,
    #         "max_workers": 1,
    #         "metrics_enabled": True,
    #         "classes_filter": None,
    #         "models": [
    #             {
    #                 "path": "data/models/yolo11n.pt",
    #                 "draw": True,
    #                 "confidence": 0.4,
    #                 "iou": 0.45,
    #                 "counting": {
    #                     "region": [(320, 0), (320, 480)],
    #                     "show_in": False,
    #                     "show_out": False,
    #                     "tracking": {
    #                         "show": False,
    #                         "show_labels": True,
    #                         "show_conf": True,
    #                         "verbose": False
    #                     }
    #                 }
    #             },
    #             {
    #                 "path": "data/models/GianelModel.pt",
    #                 "draw": True,
    #                 "confidence": 0.4,
    #                 "iou": 0.45,
    #                 "counting": {
    #                     "region": [(320, 0), (320, 480)],
    #                     "show_in": False,
    #                     "show_out": False,
    #                     "tracking": {
    #                         "show": False,
    #                         "show_labels": True,
    #                         "show_conf": True,
    #                         "verbose": False
    #                     }
    #                 }
    #             }
    #         ]
    #     },
    #     "cam_counting_example": {
    #         "source": "0",
    #         "width": 640,
    #         "height": 480,
    #         "fps": 30,
    #         "prefetch": 10,
    #         "skip_on_full_queue": True,
    #         "quality": 95,
    #         "use_cuda": True,
    #         "max_workers": 1,
    #         "metrics_enabled": True,
    #         "classes_filter": None,
    #         "models": [
    #             {
    #                 "path": "data/models/yolo11n.pt",
    #                 "draw": True,
    #                 "confidence": 0.4,
    #                 "iou": 0.45,
    #                 "counting": {
    #                     "region": [(320, 0), (320, 480)],
    #                     "show_in": False,
    #                     "show_out": False,
    #                     "tracking": {
    #                         "show": False,
    #                         "show_labels": True,
    #                         "show_conf": True,
    #                         "verbose": False
    #                     }
    #                 }
    #             }
    #         ]
    #     }
    # }
    
    IRAYPLE_CAMERAS = {
        "1": "192.168.1.123",
        "2": "192.168.1.111",
    }

    COMMESSA_DEFAULT = {
        "descrizione": "Produzione Calzature Lavoro Autunno 2024",
        "articoli": {
            "U_SNK DAY FASTER SC": {
                "codice_articolo": "U_SNK DAY FASTER SC",
                "nome_articolo": "Sneaker Day Faster Safety Collection",
                "totale_da_produrre": 20,
                "prodotti": 0
            },
            "D_SNK P.LIGHT STROBEL": {
                "codice_articolo": "D_SNK P.LIGHT STROBEL", 
                "nome_articolo": "Sneaker Pro Light Strobel Construction",
                "totale_da_produrre": 20,
                "prodotti": 0
            },
            "U_PORT.SPOILER": {
                "codice_articolo": "U_PORT.SPOILER",
                "nome_articolo": "Scarpa Portuale con Spoiler Protettivo",
                "totale_da_produrre": 20,
                "prodotti": 0
            }
        }
    }

    COMMESSE = {
        "053409300172" : copy.deepcopy(COMMESSA_DEFAULT),
        "053409300189" : copy.deepcopy(COMMESSA_DEFAULT),
        "053409300110" : copy.deepcopy(COMMESSA_DEFAULT),
        "053036800137" : copy.deepcopy(COMMESSA_DEFAULT),
        "053036800113" : copy.deepcopy(COMMESSA_DEFAULT),
        "053036800144" : copy.deepcopy(COMMESSA_DEFAULT),
        "053036800175" : copy.deepcopy(COMMESSA_DEFAULT),
        "1234567890" : {
            "descrizione": "Conteggio Persone",
            "articoli": {
                "persona": {
                    "codice_articolo": "persona",
                    "nome_articolo": "Persona",
                    "totale_da_produrre": 100,
                    "prodotti": 0
                }
            }
        }
    }

    MODULES = {
        "api": {"enabled": True, "prefix": "/api", "modules": ["ip_camera", "irayple"]},
        "models": {"enabled": True, "modules": ["device", "task", "log_data", "variables"]},
        "jobs": {
            "enabled": True,
            "interval": timedelta(seconds=15),
            "max_instances": 10,
            "modules": [],
            # "modules": ["sync_devices_from_cloud", "sync_logs_to_cloud", "sync_logs_from_device"],
        },
        "threads": {
            "enabled": True,
            "modules": ["websocket"],
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
    if hasattr(model, 'names'):
        return list(model.names.values())
    return []
