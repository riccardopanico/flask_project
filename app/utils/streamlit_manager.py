# app/utils/streamlit_manager.py
import os
import subprocess
from flask import current_app

class StreamlitManager:
    def __init__(self, app):
        self.app = app
        self.procs = {}

    def start_app(self, name, cfg):
        script = cfg['script_path']
        port   = cfg['port']
        cmd = [
            "streamlit", "run", script,
            "--server.port", str(port),
            "--server.headless", str(cfg.get('headless', True)).lower(),
            "--server.enableCORS", str(cfg.get('enableCORS', False)).lower(),
            "--server.enableXsrfProtection", str(cfg.get('enableXsrfProtection', False)).lower()
        ]
        with self.app.app_context():
            current_app.logger.info(f"[STREAMLIT] Starting {name} on port {port}")
        try:
            p = subprocess.Popen(cmd)
            self.procs[name] = p
            with self.app.app_context():
                current_app.logger.info(f"[STREAMLIT] App {name} avviata: http://localhost:{port}")
        except Exception as e:
            with self.app.app_context():
                current_app.logger.error(f"[STREAMLIT] Errore avviando {name}: {e}")

    def start(self):
        cfgs = self.app.config['MODULES']['threads']['config']
        for name, cfg in cfgs.items():
            if name == 'camera_monitor':
                continue
            script = cfg.get('script_path')
            if script and os.path.exists(script):
                self.start_app(name, cfg)
            else:
                with self.app.app_context():
                    current_app.logger.error(f"[STREAMLIT] Missing script for {name}")

    def stop(self):
        for p in self.procs.values():
            p.terminate()
