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

    # Config pipeline singola
    PIPELINE_CONFIG = {
        "source": "0",          # Indice webcam o url
        "width": None,          # Larghezza frame (opzionale)
        "height": None,         # Altezza frame (opzionale)
        "fps": None,            # FPS desiderati (opzionale)
        "prefetch": 10,         # Frame buffer tra read e process
        "skip_on_full_queue": True,  # Se la coda è piena, salta frame
        "quality": 100,          # Compressione JPEG (%)
        "use_cuda": True,       # Usa la GPU per l'inferenza
        "max_workers": 1,       # Numero thread per inferenza parallela
        "model_behaviors": {},
        "count_line": None,         # Linea per conteggio attraversamenti
        "metrics_enabled": True,    # Abilita metriche
        "classes_filter": None      # Filtra solo alcune classi se serve
    }

    # Configurazione multi-pipeline
    PIPELINE_CONFIGS = {
        "default": PIPELINE_CONFIG,
        "external_rtsp": {
            "source": "http://pendelcam.kip.uni-heidelberg.de/mjpg/video.mjpg",
            "model_behaviors": {
                os.path.join(DATA_DIR, "models", "scarpe_25k_305ep.pt"): {
                    "draw": True,
                    "count": False,
                    "confidence": 0.5,
                    "iou": 0.5
                },
                os.path.join(DATA_DIR, "models", "yolo11n.pt"): {
                    "draw": True,
                    "count": False,
                    "confidence": 0.5,
                    "iou": 0.5
                },
            }
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
            'modules': ['ip_camera', 'yolo_tools'],
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
