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
from config import ProductionConfig, DevelopmentConfig
import importlib.util
import glob
import queue

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

    # Inizializza MODULES se non è presente
    if 'MODULES' not in app.config:
        app.config['MODULES'] = config_class.MODULES

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

    # Inizializzazione di Scheduler
    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})
    for key, path in modules_to_import.items():
        module_config = app.config['MODULES'].get(key, {})
        if not module_config.get('enabled', False):
            continue

        enabled_modules = module_config.get('modules', [])
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
                    prefix = module_config.get('prefix', '/api')
                    app.register_blueprint(blueprint, url_prefix=f'{prefix}/{module_name}')
            elif key == 'models':
                importlib.import_module(f'app.models.{module_name}')
            elif key == 'jobs':
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'run'):
                    try:
                        job_config = app.config['MODULES']['jobs']
                        interval = job_config.get('interval', timedelta(minutes=15))
                        max_instances = job_config.get('max_instances', 10)
                        
                        scheduler.add_job(
                            module.run,
                            'interval',
                            seconds=interval.total_seconds(),
                            id=module_name,
                            max_instances=max_instances,
                            args=(app,),
                            name=f"{module_name}_job"
                        )
                        app.logger.info(f"Scheduled {module_name} job with interval {interval}")
                    except Exception as e:
                        app.logger.error(f"Failed to schedule {module_name} job: {str(e)}")
            elif key == 'threads':
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'run'):
                    try:
                        thread = threading.Thread(
                            target=module.run,
                            args=(app,),
                            daemon=True,
                            name=f"{module_name}_thread"
                        )
                        thread.start()
                        app.logger.info(f"Started {module_name} thread")
                    except Exception as e:
                        app.logger.error(f"Failed to start {module_name} thread: {str(e)}")
            elif key == 'utils':
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'init'):
                    module.init(app)

    # Initialize Streamlit Manager if enabled
    if app.config['STREAMLIT'].get('enabled', False):
        from .utils.streamlit_manager import StreamlitManager
        app.streamlit_manager = StreamlitManager(app)
        app.streamlit_manager.start()

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    if hasattr(app, 'streamlit_manager'):
        atexit.register(lambda: app.streamlit_manager.stop())

    return app
