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

# Inizializzazione delle estensioni Flask
db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()

def create_app():
    # Ottieni l'ambiente dal file di configurazione o da una variabile di ambiente
    env = os.getenv("FLASK_ENV", "production").lower()
    print(f"L'ambiente di esecuzione corrente è: {env}")
    # Imposta la configurazione in base all'ambiente
    config_class = DevelopmentConfig if env == "development" else ProductionConfig
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inizializza estensioni con l'app Flask
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    # Registra blueprint delle API
    from app.api.device import device_blueprint
    app.register_blueprint(device_blueprint, url_prefix='/api/device')

    # Importa modelli per le migrazioni
    from app.models.device import Device

    # Configura APScheduler
    scheduler = BackgroundScheduler(executors={'default': ThreadPoolExecutor(50)})

    # Carica dinamicamente tutti i job dalla cartella jobs e aggiungili al scheduler
    jobs_path = os.path.join(os.path.dirname(__file__), 'jobs', '*.py')
    for job_file in glob.glob(jobs_path):
        module_name = os.path.basename(job_file)[:-3]
        spec = importlib.util.spec_from_file_location(module_name, job_file)
        job_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(job_module)
        if hasattr(job_module, 'run'):
            scheduler.add_job(job_module.run, 'interval', seconds=60, max_instances=10)

    scheduler.start()

    # Avvio dei thread per ogni file nella cartella threads
    threads_path = os.path.join(os.path.dirname(__file__), 'threads', '*.py')
    for thread_file in glob.glob(threads_path):
        module_name = os.path.basename(thread_file)[:-3]
        spec = importlib.util.spec_from_file_location(module_name, thread_file)
        thread_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(thread_module)
        if hasattr(thread_module, 'run'):
            thread = threading.Thread(target=thread_module.run)
            thread.daemon = True  # Il thread si chiuderà automaticamente quando l'app si chiude
            thread.start()

    # Assicurati che lo scheduler venga chiuso correttamente quando l'app si arresta
    atexit.register(lambda: scheduler.shutdown())

    return app
