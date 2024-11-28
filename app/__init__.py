import os
import threading
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from datetime import timedelta
import atexit
from config.config import ProductionConfig, DevelopmentConfig
import importlib.util
import glob
import queue
from app.utils.api_device_manager import ApiDeviceManager

# Inizializzazione delle estensioni Flask
db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()

websocket_queue = queue.Queue()

def create_app():
    # Ottieni l'ambiente dal file di configurazione o da una variabile di ambiente
    env = os.getenv("FLASK_ENV", "development").lower()
    print(f"L'ambiente di esecuzione corrente è: {env}")

    # Imposta la configurazione in base all'ambiente
    config_class = ProductionConfig if env == "production" else DevelopmentConfig

    # Inizializzazione dell'app Flask e delle estensioni
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.api_manager = ApiDeviceManager()

    # Inizializza estensioni con l'app Flask
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # Iterazione unica per registrare blueprint, importare modelli, configurare job e avviare thread
    base_paths = {
        'api': os.path.join(os.path.dirname(__file__), 'api', '*.py'),
        'models': os.path.join(os.path.dirname(__file__), 'models', '*.py'),
        'jobs': os.path.join(os.path.dirname(__file__), 'jobs', '*.py'),
        'threads': os.path.join(os.path.dirname(__file__), 'threads', '*.py')
    }

    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})
    for key, path in base_paths.items():
        enabled_key = f'ENABLED_{key.upper()}'
        enabled_modules = app.config.get(enabled_key, [])

        for file_path in glob.glob(path):
            module_name = os.path.basename(file_path)[:-3]
            if module_name not in enabled_modules:
                continue

            if key == 'api':
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                blueprint_name = f"{module_name}_blueprint"
                if hasattr(module, blueprint_name):
                    blueprint = getattr(module, blueprint_name)
                    app.register_blueprint(blueprint, url_prefix=f'/api/{module_name}')
            elif key == 'models':
                importlib.import_module(f'app.models.{module_name}')
            elif key == 'jobs':
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'run'):
                    job_interval = getattr(module, 'JOB_INTERVAL', timedelta(minutes=15))
                    scheduler.add_job(module.run, 'interval', seconds=job_interval.total_seconds(), id=module_name, max_instances=10, args=(app,))
            elif key == 'threads':
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'run'):
                    thread = threading.Thread(target=module.run, args=(app,))
                    thread.daemon = True
                    thread.start()

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

    return app
