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
    ENABLED_JOBS = ['sync_devices', 'sync_tasks']
    ENABLED_THREADS = ['encoder', 'monitor_alert', 'websocket']
    ENABLED_MODELS = ['campionatura', 'device', 'impostazioni', 'log_operazioni', 'log_orlatura', 'tasks', 'user']
    ENABLED_API = ['auth', 'device', 'setting', 'task']

class ProductionConfig(Config):
    DEBUG = False

class DevelopmentConfig(Config):
    DEBUG = True
    JWT_ACCESS_TOKEN_EXPIRES = False  # Nessuna scadenza
    JWT_REFRESH_TOKEN_EXPIRES = False  # Nessuna scadenza
