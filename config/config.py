import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)  # Scade dopo 15 minuti
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)  # Scade dopo 30 giorni
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_TYPE = 'Bearer'
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ENABLED_JOBS = ['sync_devices_from_cloud']#, 'send_new_tasks_to_cloud', 'sync_devices_from_cloud',sync_task_to_cloud
    ENABLED_THREADS = []
    ENABLED_MODELS = ['device', 'tasks', 'user', 'variables', 'log_data']
    ENABLED_API = ['auth', 'device', 'setting', 'task', 'variables']

class ProductionConfig(Config):
    DEBUG = False

class DevelopmentConfig(Config):
    DEBUG = True
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=30)
