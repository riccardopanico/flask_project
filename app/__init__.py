import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
import atexit
from config.config import DevelopmentConfig
from app.scheduler.jobs import scheduled_task

# Inizializzazione delle estensioni Flask
db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()

def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inizializza estensioni con l'app Flask
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # Registra blueprint delle API
    from app.api.device import device_blueprint
    app.register_blueprint(device_blueprint, url_prefix='/api/device')

    # Importa modelli per le migrazioni
    from app.models.device import Device

    # Configura APScheduler
    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})
    # scheduler.add_job(scheduled_task, 'interval', seconds=1, max_instances=10)
    scheduler.start()

    # Assicurati che lo scheduler venga chiuso correttamente quando l'app si arresta
    atexit.register(lambda: scheduler.shutdown())

    return app