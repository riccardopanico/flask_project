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
    MODELS_DIR = os.path.join(DATA_DIR, 'models')
    DATASETS_DIR = os.path.join(DATA_DIR, 'datasets')
    OUTPUT_DIR = os.path.join(DATA_DIR, 'output')
    TEMP_DIR = os.path.join(DATA_DIR, 'temp')
    LOGS_DIR = os.path.join(DATA_DIR, 'logs')
    CONFIG_DIR = os.path.join(DATA_DIR, 'config')

    for d in [MODELS_DIR, DATASETS_DIR, OUTPUT_DIR, TEMP_DIR, LOGS_DIR, CONFIG_DIR]:
        os.makedirs(d, exist_ok=True)

    CAMERA_RTSP_URLS = {
        'camera1': 'http://192.168.0.92:8080/video',
    }
    MAX_CAMERAS = 10
    CAMERA_FRAME_RATE = 30
    CAMERA_QUEUE_SIZE = 1

    YOLO_MODEL_PATH = os.getenv('YOLO_MODEL_PATH', os.path.join(MODELS_DIR, 'yolov8n.pt'))
    YOLO_TRAIN_CONFIG = os.getenv('YOLO_TRAIN_CONFIG', os.path.join(CONFIG_DIR, 'yolo_train.yaml'))
    YOLO_VAL_CONFIG = os.getenv('YOLO_VAL_CONFIG', os.path.join(CONFIG_DIR, 'yolo_val.yaml'))

    TRAIN_BATCH_SIZE = int(os.getenv('TRAIN_BATCH_SIZE', '16'))
    TRAIN_EPOCHS = int(os.getenv('TRAIN_EPOCHS', '100'))
    TRAIN_IMG_SIZE = int(os.getenv('TRAIN_IMG_SIZE', '640'))
    TRAIN_DEVICE = os.getenv('TRAIN_DEVICE', 'cuda')

    INFERENCE_CONFIDENCE = float(os.getenv('INFERENCE_CONFIDENCE', '0.5'))
    INFERENCE_IOU = float(os.getenv('INFERENCE_IOU', '0.45'))
    INFERENCE_DEVICE = os.getenv('INFERENCE_DEVICE', 'cuda')
    INFERENCE_FRAME_SKIP = int(os.getenv('INFERENCE_FRAME_SKIP', '1'))

    THREAD_POOL_SIZE = int(os.getenv('THREAD_POOL_SIZE', '4'))

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', os.path.join(LOGS_DIR, 'app.log'))

    MODULES = {
        'api': {
            'enabled': True,
            'prefix': '/api',
            'modules': []
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
            'modules': [
                'camera_monitor',
                'streamlit_manager'
            ],
            'config': {
                'camera_monitor': {
                    'port': 8505,
                    'headless': True,
                    'enableCORS': False,
                    'enableXsrfProtection': False
                },
                'streamlit_manager': {
                    # no per‐module config needed; manager reads its own THREADS config
                }
            }
        },
        'utils': {
            'enabled': True,
            'modules': []
        }
    }

class ProductionConfig(Config):
    DEBUG = False

class DevelopmentConfig(Config):
    DEBUG = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=30)
