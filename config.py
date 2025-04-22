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

    CAMERA_RTSP_URLS = {
        'camera1': 'http://192.168.0.92:8080/video',
    }
    MAX_CAMERAS = 10
    CAMERA_FRAME_RATE = 30
    CAMERA_QUEUE_SIZE = 1

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
            'modules': ['inference_monitor'],
            'config': {
                'inference_monitor': {
                    'script_path': os.path.join(BASE_DIR, 'app', 'threads', 'inference_monitor.py'),
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

    ENABLED_API     = MODULES['api']['modules']
    ENABLED_MODELS  = MODULES['models']['modules']
    ENABLED_JOBS    = MODULES['jobs']['modules']
    ENABLED_THREADS = MODULES['threads']['modules']

class ProductionConfig(Config):
    DEBUG = False

class DevelopmentConfig(Config):
    DEBUG = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=30)
