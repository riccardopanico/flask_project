import os
import threading
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
import atexit
from config.config import ProductionConfig, DevelopmentConfig
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
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inizializza estensioni con l'app Flask
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # Registra blueprint delle API
    from app.api.device import device_blueprint
    app.register_blueprint(device_blueprint, url_prefix='/api/device')
    from app.api.auth import auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/api/auth')

    # Importa modelli per le migrazioni
    from app.models.device import Device
    from app.models.user import User
    from app.models.log_orlatura import LogOrlatura
    from app.models.log_operazioni import LogOperazioni
    from app.models.impostazioni import Impostazioni
    from app.models.campionatura import Campionatura
    from app.models.tasks import Task
    from app.models.operatori import Operatori

    # Configura APScheduler per la gestione dei job
    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})
    jobs_path = os.path.join(os.path.dirname(__file__), 'jobs', '*.py')
    for job_file in glob.glob(jobs_path):
        module_name = os.path.basename(job_file)[:-3]
        spec = importlib.util.spec_from_file_location(module_name, job_file)
        job_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job_module)
        if getattr(job_module, '__ACTIVE__', True):
            if hasattr(job_module, 'run'):
                job_id = f"job_{module_name}"
                scheduler.add_job(job_module.run, 'interval', seconds=5, id=job_id, max_instances=10)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

    # Avvio dei thread per ogni file nella cartella threads
    threads_path = os.path.join(os.path.dirname(__file__), 'threads', '*.py')
    for thread_file in glob.glob(threads_path):
        module_name = os.path.basename(thread_file)[:-3]
        spec = importlib.util.spec_from_file_location(module_name, thread_file)
        thread_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(thread_module)
        if getattr(thread_module, '__ACTIVE__', True):
            if hasattr(thread_module, 'run'):
                thread = threading.Thread(target=thread_module.run, args=(app,))
                thread.daemon = True
                thread.start()

    return app
