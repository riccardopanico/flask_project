# app/utils/streamlit_manager.py

import os
import subprocess
import psutil
from flask import current_app

class StreamlitManager:
    def __init__(self, app):
        self.app = app
        self.registry = {}   # {name: cfg}
        self.procs    = {}   # {name: subprocess.Popen}

    def register(self, name, cfg):
        """Registra un'app Streamlit con il suo nome e configurazione"""
        self.registry[name] = cfg

    def is_streamlit_running(self, port):
        """Controlla se Streamlit è già attivo su quella porta"""
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                if 'streamlit' in proc.info['cmdline'] and f'--server.port={port}' in proc.info['cmdline']:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    def start(self):
        """Avvia tutte le app Streamlit registrate"""
        with self.app.app_context():
            for name, cfg in self.registry.items():
                script = cfg.get('script_path')
                port   = cfg.get('port')
                if not script or not os.path.exists(script):
                    current_app.logger.error(f"[STREAMLIT] Script mancante per {name}")
                    continue

                if self.is_streamlit_running(port):
                    current_app.logger.warning(f"[STREAMLIT] {name} già attivo su porta {port}, salto avvio.")
                    continue

                log_dir = os.path.join(self.app.config.get('DATA_DIR', '.'), 'logs')
                os.makedirs(log_dir, exist_ok=True)
                log_path = os.path.join(log_dir, f"{name}.log")

                cmd = [
                    "streamlit", "run", script,
                    "--server.port", str(port),
                    "--server.headless", str(cfg.get('headless', True)).lower(),
                    "--server.enableCORS", str(cfg.get('enableCORS', False)).lower(),
                    "--server.enableXsrfProtection", str(cfg.get('enableXsrfProtection', False)).lower()
                ]
                try:
                    with open(log_path, "w") as f:
                        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)
                        self.procs[name] = p
                    current_app.logger.info(f"[STREAMLIT] {name} avviato: http://localhost:{port}")
                except Exception as e:
                    current_app.logger.error(f"[STREAMLIT] Errore avviando {name}: {e}")

    def stop(self):
        """Termina tutti i processi Streamlit avviati"""
        with self.app.app_context():
            for name, p in self.procs.items():
                try:
                    p.terminate()
                    current_app.logger.info(f"[STREAMLIT] {name} terminato.")
                except Exception as e:
                    current_app.logger.warning(f"[STREAMLIT] Errore terminando {name}: {e}")
