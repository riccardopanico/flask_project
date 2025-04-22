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
    # 1. ENV & Config
    env = os.getenv("FLASK_ENV", "development").lower()
    print(f"L'ambiente di esecuzione corrente è: {env}")
    config_class = ProductionConfig if env == "production" else DevelopmentConfig

    app = Flask(__name__)
    app.config.from_object(config_class)

    # 2. Logger setup
    lvl = logging.DEBUG if app.debug else logging.WARNING
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5)
    fh.setLevel(lvl); fh.setFormatter(fmt); app.logger.addHandler(fh)
    app.logger.setLevel(lvl)

    # 3. Init extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # 4. Prepare dynamic import patterns
    run_cli = os.getenv("FLASK_RUN_FROM_CLI") == "true"
    patterns = {
        'api':     os.path.join(os.path.dirname(__file__), 'api',    '*.py'),
        'models':  os.path.join(os.path.dirname(__file__), 'models',  '*.py'),
        'jobs':    os.path.join(os.path.dirname(__file__), 'jobs',    '*.py'),
        'threads': os.path.join(os.path.dirname(__file__), 'threads', '*.py'),
    }
    if run_cli:
        # only load models when using flask CLI
        patterns = {'models': patterns['models']}

    # 5. Scheduler and Streamlit manager
    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})
    sm = StreamlitManager(app)

    # 6. Unified loop for api, models, jobs, threads
    for key, pattern in patterns.items():
        cfg = app.config['MODULES'][key]
        if not cfg.get('enabled', False):
            continue

        for path in glob.glob(pattern):
            name = os.path.basename(path)[:-3]
            if cfg.get('modules') and name not in cfg['modules']:
                continue

            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if key == 'api':
                bp = getattr(module, f"{name}_blueprint", None)
                if bp:
                    prefix = cfg.get('prefix', '/api')
                    app.logger.info(f"Registering API blueprint: {name}")
                    app.register_blueprint(bp, url_prefix=f"{prefix}/{name}")

            elif key == 'models':
                # just import models
                app.logger.debug(f"Imported model module: {name}")

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
                # STREAMLIT apps
                if getattr(module, 'STREAMLIT_APP', False):
                    # only start in the reloader child
                    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
                        thread_cfg = cfg['config'].get(name, {})
                        thread_cfg['script_path'] = path
                        sm.start_app(name, thread_cfg)
                # classic background threads
                elif hasattr(module, 'run'):
                    t = threading.Thread(target=module.run, args=(app,), daemon=True, name=name)
                    t.start()
                    app.logger.info(f"Thread '{name}' avviato")

    # 7. Start scheduler
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

    # 8. Start Streamlit apps once (child process only)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        sm.start()
        atexit.register(sm.stop)

    return app
