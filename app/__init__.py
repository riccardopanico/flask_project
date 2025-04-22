import os
import threading
import glob
import importlib.util
import queue
import atexit
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from config import ProductionConfig, DevelopmentConfig

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
    if 'MODULES' not in app.config:
        app.config['MODULES'] = config_class.MODULES

    # logger
    lvl = logging.DEBUG if app.debug else logging.INFO
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5)
    fh.setLevel(lvl)
    fh.setFormatter(fmt)
    app.logger.setLevel(lvl)
    app.logger.addHandler(fh)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    run_from_cli = os.getenv("FLASK_RUN_FROM_CLI") == "true"
    modules_to_import = {'models': os.path.join(os.path.dirname(__file__), 'models', '*.py')}
    if not run_from_cli:
        modules_to_import.update({
            'api': os.path.join(os.path.dirname(__file__), 'api', '*.py'),
            'jobs': os.path.join(os.path.dirname(__file__), 'jobs', '*.py'),
            'threads': os.path.join(os.path.dirname(__file__), 'threads', '*.py'),
        })

    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})

    for key, path in modules_to_import.items():
        cfg = app.config['MODULES'].get(key, {})
        if not cfg.get('enabled', False):
            continue

        enabled = cfg.get('modules', [])
        if key == 'threads':
            imported = []
            for file_path in glob.glob(path):
                name = os.path.basename(file_path)[:-3]
                if name not in enabled:
                    continue
                imported.append(name)
                spec = importlib.util.spec_from_file_location(name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'run'):
                    if name == 'camera_monitor':
                        cm = module.run(app)
                        app.camera_monitor = cm
                        app.logger.info("CameraMonitor avviato")
                    else:
                        t = threading.Thread(target=module.run, args=(app,), daemon=True, name=f"{name}_thread")
                        t.start()
                        app.logger.info(f"Started thread {name}")

            # handle streamlit_manager explicitly
            if 'streamlit_manager' in enabled and 'streamlit_manager' not in imported:
                from .utils.streamlit_manager import run as sl_run
                sm = sl_run(app)
                app.streamlit_manager = sm
                app.logger.info("StreamlitManager avviato")

        else:
            for file_path in glob.glob(path):
                name = os.path.basename(file_path)[:-3]
                if name not in enabled:
                    continue
                spec = importlib.util.spec_from_file_location(name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if key == 'api':
                    bp = getattr(module, f"{name}_blueprint", None)
                    if bp:
                        prefix = cfg.get('prefix', '/api')
                        app.register_blueprint(bp, url_prefix=f"{prefix}/{name}")

                elif key == 'jobs' and hasattr(module, 'run'):
                    scheduler.add_job(
                        module.run,
                        'interval',
                        seconds=cfg.get('interval').total_seconds(),
                        id=name,
                        max_instances=cfg.get('max_instances'),
                        args=(app,),
                        name=f"{name}_job"
                    )
                    app.logger.info(f"Scheduled job {name}")

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    if hasattr(app, 'streamlit_manager'):
        atexit.register(lambda: app.streamlit_manager.stop())

    return app
