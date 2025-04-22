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
    cfg_cls = ProductionConfig if env == "production" else DevelopmentConfig

    app = Flask(__name__)
    app.config.from_object(cfg_cls)

    # logger
    lvl = logging.DEBUG if app.debug else logging.WARNING
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5)
    fh.setLevel(lvl); fh.setFormatter(fmt); app.logger.addHandler(fh)
    app.logger.setLevel(lvl)

    # init extensions
    db.init_app(app); jwt.init_app(app); migrate.init_app(app, db)

    run_cli = os.getenv("FLASK_RUN_FROM_CLI") == "true"
    patterns = {
        'api':     os.path.join(os.path.dirname(__file__), 'api',    '*.py'),
        'models':  os.path.join(os.path.dirname(__file__), 'models',  '*.py'),
        'jobs':    os.path.join(os.path.dirname(__file__), 'jobs',    '*.py'),
        'threads': os.path.join(os.path.dirname(__file__), 'threads', '*.py'),
    }
    if run_cli:
        patterns = {'models': patterns['models']}

    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})
    sm = StreamlitManager(app)

    for key, pattern in patterns.items():
        mod_cfg = app.config['MODULES'][key]
        if not mod_cfg.get('enabled', False):
            continue

        for path in glob.glob(pattern):
            name = os.path.basename(path)[:-3]
            if mod_cfg.get('modules') and name not in mod_cfg['modules']:
                continue

            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if key == 'api':
                bp = getattr(module, f"{name}_blueprint", None)
                if bp:
                    prefix = mod_cfg.get('prefix', '/api')
                    app.register_blueprint(bp, url_prefix=f"{prefix}/{name}")

            elif key == 'models':
                # only import, no action needed
                pass

            elif key == 'jobs' and hasattr(module, 'run'):
                interval = mod_cfg.get('interval', timedelta(minutes=15))
                scheduler.add_job(
                    module.run,
                    'interval',
                    seconds=interval.total_seconds(),
                    id=name,
                    max_instances=mod_cfg.get('max_instances', 1),
                    args=(app,),
                )
            elif key == 'threads':
                if getattr(module, 'STREAMLIT_APP', False):
                    cfg = mod_cfg['config'].get(name, {})
                    cfg['script_path'] = path  # lo ricaviamo direttamente da glob
                    sm.start_app(name, cfg)
                elif hasattr(module, 'run'):
                    t = threading.Thread(target=module.run, args=(app,), daemon=True)
                    t.start()
                    app.logger.info(f"Thread '{name}' avviato")

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

    return app
