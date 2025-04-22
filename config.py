import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Base configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    # JWT configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_TYPE = 'Bearer'
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']

    # Data directories
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    MODELS_DIR = os.path.join(DATA_DIR, 'models')
    DATASETS_DIR = os.path.join(DATA_DIR, 'datasets')
    OUTPUT_DIR = os.path.join(DATA_DIR, 'output')
    TEMP_DIR = os.path.join(DATA_DIR, 'temp')
    LOGS_DIR = os.path.join(DATA_DIR, 'logs')
    CONFIG_DIR = os.path.join(DATA_DIR, 'config')

    # Create directories if they don't exist
    for dir_path in [MODELS_DIR, DATASETS_DIR, OUTPUT_DIR, TEMP_DIR, LOGS_DIR, CONFIG_DIR]:
        os.makedirs(dir_path, exist_ok=True)

    # Camera configuration
    CAMERA_RTSP_URLS = {
        'camera1': 'http://192.168.0.92:8080/video',
    }
    MAX_CAMERAS = 10
    CAMERA_FRAME_RATE = 30
    CAMERA_QUEUE_SIZE = 1
    
    # YOLO configuration
    YOLO_MODEL_PATH = os.getenv('YOLO_MODEL_PATH', os.path.join(MODELS_DIR, 'yolov8n.pt'))
    YOLO_TRAIN_CONFIG = os.getenv('YOLO_TRAIN_CONFIG', os.path.join(CONFIG_DIR, 'yolo_train.yaml'))
    YOLO_VAL_CONFIG = os.getenv('YOLO_VAL_CONFIG', os.path.join(CONFIG_DIR, 'yolo_val.yaml'))
    
    # Training configuration
    TRAIN_BATCH_SIZE = int(os.getenv('TRAIN_BATCH_SIZE', '16'))
    TRAIN_EPOCHS = int(os.getenv('TRAIN_EPOCHS', '100'))
    TRAIN_IMG_SIZE = int(os.getenv('TRAIN_IMG_SIZE', '640'))
    TRAIN_DEVICE = os.getenv('TRAIN_DEVICE', 'cuda')
    
    # Inference configuration
    INFERENCE_CONFIDENCE = float(os.getenv('INFERENCE_CONFIDENCE', '0.5'))
    INFERENCE_IOU = float(os.getenv('INFERENCE_IOU', '0.45'))
    INFERENCE_DEVICE = os.getenv('INFERENCE_DEVICE', 'cuda')
    INFERENCE_FRAME_SKIP = int(os.getenv('INFERENCE_FRAME_SKIP', '1'))
    
    # Thread configuration
    THREAD_POOL_SIZE = int(os.getenv('THREAD_POOL_SIZE', '4'))
    
    # Logging configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', os.path.join(LOGS_DIR, 'app.log'))

    # Module configuration
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
            'modules': ['camera_monitor'],
            'config': {
                'camera_monitor': {
                    'port': 8505,
                    'headless': True,
                    'enableCORS': False,
                    'enableXsrfProtection': False
                }
            }
        },
        'utils': {
            'enabled': True,
            'modules': ['streamlit_manager']
        }
    }

    # Streamlit configuration
    STREAMLIT = {
        'enabled': True
    }

class ProductionConfig(Config):
    DEBUG = False
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hour
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

class DevelopmentConfig(Config):
    DEBUG = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=30) 