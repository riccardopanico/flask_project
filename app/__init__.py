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
import logging
from logging.handlers import RotatingFileHandler
from config.config import ProductionConfig, DevelopmentConfig
import importlib.util
import glob
import queue
from app.utils.api_device_manager import ApiDeviceManager
from app.utils.api_oracle_manager import ApiOracleManager

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

    # Configurazione logger personalizzato
    log_level = logging.DEBUG if app.debug else logging.INFO
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = RotatingFileHandler('app.log', maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(log_formatter)
    app.logger.setLevel(log_level)
    app.logger.addHandler(file_handler)

    # Inizializza estensioni con l'app Flask
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)


    run_from_cli = os.getenv("FLASK_RUN_FROM_CLI") == "true"
    modules_to_import = {
        'models': os.path.join(os.path.dirname(__file__), 'models', '*.py')
    }
    if not run_from_cli:
        modules_to_import.update({
            'api': os.path.join(os.path.dirname(__file__), 'api', '*.py'),
            'jobs': os.path.join(os.path.dirname(__file__), 'jobs', '*.py'),
            'threads': os.path.join(os.path.dirname(__file__), 'threads', '*.py')
        })

        # Inizializzazione di ApiDeviceManager e ApiOracleManager
        app.api_device_manager = None
        app.api_datacenter_manager = None
        app.api_oracle_manager = None
        with app.app_context():
            from app.models.device import Device  # Importa qui per evitare il ciclo
            from app.models.user import User  # User contiene il tipo di utente

            # Ottieni tutti i dispositivi associati a utenti di tipo 'device'
            devices = Device.query.join(User).filter(User.id == Device.user_id, User.user_type == 'device').all()
            app.api_device_manager = {
                device.username: ApiDeviceManager(
                    ip_address=device.ip_address,
                    username=device.username,
                    password=device.password
                ) for device in devices
            }

            # Ottieni il primo record associato a un utente di tipo 'datacenter'
            datacenter_device = Device.query.join(User).filter(User.id == Device.user_id, User.user_type == 'datacenter').first()
            if datacenter_device:
                app.api_datacenter_manager = ApiDeviceManager(
                    ip_address=datacenter_device.ip_address,
                    username=datacenter_device.username,
                    password=datacenter_device.password
                )
            else:
                app.api_datacenter_manager = None
                app.logger.warning("Nessun dispositivo trovato per il tipo 'datacenter'.")

            app.api_oracle_manager = ApiOracleManager()

    # Inizializzazione di Scheduler
    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})
    for key, path in modules_to_import.items():
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
