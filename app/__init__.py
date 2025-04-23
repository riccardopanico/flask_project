# app/__init__.py
import os
import threading
import glob
import importlib.util
import importlib
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

# ---- import per VideoPipeline ----
from app.utils.video_pipeline import VideoPipeline, PipelineConfig

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
websocket_queue = queue.Queue()

def configure_logging(app):
    lvl = logging.DEBUG if app.debug else logging.INFO
    fmt = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    formatter = logging.Formatter(fmt)

    # reset handlers
    if app.logger.hasHandlers():
        app.logger.handlers.clear()

    # file handler
    fh = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5)
    fh.setFormatter(formatter)
    fh.setLevel(lvl)
    app.logger.addHandler(fh)

    # console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(lvl)
    app.logger.addHandler(ch)

    app.logger.setLevel(lvl)
    app.logger.propagate = False

def create_app():
    # 1) ENV & config
    env = os.getenv("FLASK_ENV", "development").lower()
    print(f"L'ambiente di esecuzione corrente è: {env}")
    cfg_cls = ProductionConfig if env == "production" else DevelopmentConfig

    app = Flask(__name__)
    app.config.from_object(cfg_cls)

    # 2) Logger
    configure_logging(app)

    # 3) Flask extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    
    # 4) inizializza pipeline una volta
    cfg = PipelineConfig(**app.config['PIPELINE_CONFIG'])
    app.video_pipeline = VideoPipeline(app, cfg)
    app.video_pipeline.start()

    # 5) Scheduler & Streamlit
    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})
    app.streamlit_manager = StreamlitManager(app)

    # 6) Caricamento dinamico di api, models, jobs, threads
    run_cli = os.getenv("FLASK_RUN_FROM_CLI") == "true"
    patterns = {
        'api':     os.path.join(os.path.dirname(__file__), 'api',    '*.py'),
        'models':  os.path.join(os.path.dirname(__file__), 'models',  '*.py'),
        'jobs':    os.path.join(os.path.dirname(__file__), 'jobs',    '*.py'),
        'threads': os.path.join(os.path.dirname(__file__), 'threads', '*.py'),
    }
    if run_cli:
        patterns = {'models': patterns['models']}

    for key, pattern in patterns.items():
        cfg = app.config['MODULES'][key]
        if not cfg.get('enabled', False):
            continue

        for path in glob.glob(pattern):
            name = os.path.basename(path)[:-3]
            modules = cfg.get('modules')
            if modules is not None and name not in modules:
                continue

            spec   = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if key == 'api':
                bp = getattr(module, f"{name}_blueprint", None)
                if bp:
                    prefix = cfg.get('prefix', '/api')
                    app.logger.info(f"Register API: {name}")
                    app.register_blueprint(bp, url_prefix=f"{prefix}/{name}")
            elif key == 'models':
                importlib.import_module(f"app.models.{name}")
                app.logger.debug(f"Loaded model: {name}")
            elif key == 'jobs' and hasattr(module, 'run'):
                interval = cfg.get('interval', timedelta(minutes=15))
                scheduler.add_job(
                    module.run,
                    'interval',
                    seconds=interval.total_seconds(),
                    id=name,
                    max_instances=cfg.get('max_instances', 1),
                    args=(app,),
                )
                app.logger.info(f"Scheduled job: {name}")
            elif key == 'threads':
                # se definito run(app) nel modulo, avvialo come thread
                if hasattr(module, 'run'):
                    t = threading.Thread(
                        target=module.run,
                        args=(app,),
                        daemon=True, name=name
                    )
                    t.start()
                    app.logger.info(f"Thread '{name}' running")

    # 7) Start scheduler
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))

    # 8) Avvia anche tutti gli Streamlit registrati
    app.streamlit_manager.start()
    atexit.register(lambda: app.streamlit_manager.stop())

    return app
