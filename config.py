# config.py (completato per supportare VideoPipeline)
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

def list_yolo_models(model_dir):
    return [
        os.path.join(model_dir, f)
        for f in os.listdir(model_dir)
        if f.endswith('.pt') and os.path.isfile(os.path.join(model_dir, f))
    ]

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

    PIPELINE_CONFIG = {
        "source": os.getenv("PIPELINE_SOURCE", "0"),
        "width": int(os.getenv("PIPELINE_WIDTH")) if os.getenv("PIPELINE_WIDTH") else None,
        "height": int(os.getenv("PIPELINE_HEIGHT")) if os.getenv("PIPELINE_HEIGHT") else None,
        "fps": int(os.getenv("PIPELINE_FPS")) if os.getenv("PIPELINE_FPS") else None,
        "models": list_yolo_models(os.path.join(DATA_DIR, "models")),
        "confidence": float(os.getenv("PIPELINE_CONF", 0.5)),
        "iou": float(os.getenv("PIPELINE_IOU", 0.45)),
        "draw_boxes": os.getenv("PIPELINE_DRAW", "false").lower() == "true",
        "count_objects": os.getenv("PIPELINE_COUNT", "false").lower() == "true",
        "count_line": None,
        "metrics_enabled": True,
        "classes_filter": None,
        "prefetch": int(os.getenv("PIPELINE_PREFETCH", 10))
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
    DEBUG = True

class DevelopmentConfig(Config):
    DEBUG = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=30)
