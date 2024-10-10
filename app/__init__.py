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

    # Configura e avvia APScheduler con un executor che usa un pool di thread
    executors = {
        'default': ThreadPoolExecutor(10),  # Fino a 10 thread per eseguire job in parallelo
    }

    scheduler = BackgroundScheduler(executors=executors)
    scheduler.add_job(scheduled_task, 'interval', minutes=1, max_instances=3)
    scheduler.start()

    # Assicurati che lo scheduler venga chiuso correttamente quando l'app si arresta
    atexit.register(lambda: scheduler.shutdown())

    return app