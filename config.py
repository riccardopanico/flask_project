import os
from datetime import timedelta
from dotenv import load_dotenv

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

    MODULES = {
        "api": {"enabled": True, "prefix": "/api", "modules": ['log_data', 'auth']},
        "models": {"enabled": True, "modules": ["device", "task", "log_data", "variables"]},
        "jobs": {
            "enabled": True,
            "interval": timedelta(seconds=15),
            "max_instances": 10,
            "modules": ["sync_devices_from_cloud", "sync_logs_to_cloud", "sync_logs_from_device"],
        },
        "threads": {
            "enabled": True,
            "modules": [],
            "config": {},
        },
        "utils": {"enabled": True, "modules": []},
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
