# app/__init__.py
import os
import threading
import glob
import importlib.util
import queue
import atexit
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from config import ProductionConfig, DevelopmentConfig
from app.utils.streamlit_manager import StreamlitManager

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
websocket_queue = queue.Queue()

def create_app():
    env = os.getenv("FLASK_ENV", "development").lower()
    print(f"L'ambiente di esecuzione corrente è: {env}")
    config_class = ProductionConfig if env == "production" else DevelopmentConfig

    app = Flask(__name__)
    app.config.from_object(config_class)

    log_level = logging.DEBUG if app.debug else logging.WARNING
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh = RotatingFileHandler('app.log', maxBytes=10 * 1024 * 1024, backupCount=5)
    fh.setLevel(log_level)
    fh.setFormatter(fmt)
    app.logger.setLevel(log_level)
    app.logger.addHandler(fh)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    run_from_cli = os.getenv("FLASK_RUN_FROM_CLI") == "true"
    modules_to_import = {
        'models': os.path.join(os.path.dirname(__file__), 'models', '*.py')
    }
    if not run_from_cli:
        modules_to_import.update({
            'api':     os.path.join(os.path.dirname(__file__), 'api',    '*.py'),
            'jobs':    os.path.join(os.path.dirname(__file__), 'jobs',   '*.py'),
            'threads': os.path.join(os.path.dirname(__file__), 'threads','*.py'),
        })

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
                bp_name = f"{module_name}_blueprint"
                if hasattr(module, bp_name):
                    bp = getattr(module, bp_name)
                    app.register_blueprint(bp, url_prefix=f'/api/{module_name}')

            elif key == 'models':
                importlib.import_module(f'app.models.{module_name}')

            elif key == 'jobs':
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'run'):
                    interval = getattr(module, 'JOB_INTERVAL', timedelta(minutes=15))
                    scheduler.add_job(
                        module.run,
                        'interval',
                        seconds=interval.total_seconds(),
                        id=module_name,
                        max_instances=10,
                        args=(app,),
                    )

    # threads
    if 'threads' in modules_to_import:
        enabled_threads = app.config.get('ENABLED_THREADS', [])
        sm = StreamlitManager(app)

        for file_path in glob.glob(modules_to_import['threads']):
            module_name = os.path.basename(file_path)[:-3]
            if module_name not in enabled_threads:
                continue

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if getattr(module, 'STREAMLIT_APP', False):
                cfg = app.config['MODULES']['threads']['config'][module_name]
                cfg['script_path'] = file_path
                sm.start_app(module_name, cfg)
            elif hasattr(module, 'run'):
                t = threading.Thread(target=module.run, args=(app,), daemon=True)
                t.start()
                app.logger.info(f"Thread '{module_name}' avviato")

        sm.start()

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

    return app
