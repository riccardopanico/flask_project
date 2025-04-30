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

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
websocket_queue = queue.Queue()

def configure_logging(app):
    lvl = logging.DEBUG if app.debug else logging.INFO
    fmt = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    formatter = logging.Formatter(fmt)

    if app.logger.hasHandlers():
        app.logger.handlers.clear()

    fh = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5)
    fh.setFormatter(formatter); fh.setLevel(lvl); app.logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(formatter); ch.setLevel(lvl); app.logger.addHandler(ch)

    app.logger.setLevel(lvl)
    app.logger.propagate = False

def create_app():
    # 1. Configurazione ambiente
    env = os.getenv("FLASK_ENV", "development").lower()
    cfg_cls = ProductionConfig if env=="production" else DevelopmentConfig

    app = Flask(__name__, template_folder='templates')
    
    app.config.from_object(cfg_cls)
    configure_logging(app)

    # 2. Inizializza estensioni
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # 3. Registry delle pipeline: nessuna partenza automatica
    app.video_pipelines: Dict[str, Any] = {}

    # 4. Streamlit e scheduler (resta invariato)
    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})
    app.streamlit_manager = StreamlitManager(logger=app.logger)

    # 5. Caricamento dinamico di api/models/jobs/threads
    run_cli = os.getenv("FLASK_RUN_FROM_CLI")=="true"
    base = os.path.dirname(__file__)
    patterns = {
        'api':     os.path.join(base, 'api',    '*.py'),
        'models':  os.path.join(base, 'models',  '*.py'),
        'jobs':    os.path.join(base, 'jobs',    '*.py'),
        'threads': os.path.join(base, 'threads', '*.py'),
    }
    if run_cli:
        patterns={'models':patterns['models']}

    for key, pattern in patterns.items():
        cfg_mod = app.config['MODULES'][key]
        if not cfg_mod.get('enabled', False):
            continue
        for path in glob.glob(pattern):
            name = os.path.basename(path)[:-3]
            if (mods:=cfg_mod.get('modules')) is not None and name not in mods:
                continue

            spec   = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if key=='api':
                bp = getattr(module, f"{name}_blueprint", None)
                if bp:
                    prefix = cfg_mod.get('prefix','/api')
                    app.logger.info(f"Register API: {name}")
                    app.register_blueprint(bp, url_prefix=f"{prefix}/{name}")
            elif key=='models':
                importlib.import_module(f"app.models.{name}")
            elif key=='jobs' and hasattr(module,'run'):
                interval = cfg_mod.get('interval', timedelta(minutes=15))
                scheduler.add_job(
                    module.run,'interval',
                    seconds=interval.total_seconds(),
                    id=name,
                    max_instances=cfg_mod.get('max_instances',1),
                    args=(app,)
                )
            elif key=='threads' and hasattr(module,'run'):
                t = threading.Thread(target=module.run, args=(app,), daemon=True, name=name)
                t.start()

    # 6. Avvia scheduler e Streamlit Manager
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False))
    app.streamlit_manager.start()
    atexit.register(lambda: app.streamlit_manager.stop())

    return app
