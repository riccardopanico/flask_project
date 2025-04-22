import os
import subprocess
import threading
import time
from flask import current_app

class StreamlitManager:
    def __init__(self, app):
        self.app = app
        self.processes = {}
        self.threads = {}
        self.running = False

    def start_app(self, app_name, cfg):
        script = cfg.get('script_path')
        port = cfg.get('port', 8501)
        cmd = [
            "streamlit", "run", script,
            "--server.port", str(port),
            "--server.headless", str(cfg.get('headless', True)).lower(),
            "--server.enableCORS", str(cfg.get('enableCORS', False)).lower(),
            "--server.enableXsrfProtection", str(cfg.get('enableXsrfProtection', False)).lower()
        ]
        with self.app.app_context():
            self.app.logger.info(f"Starting Streamlit app {app_name} on port {port}")
        p = subprocess.Popen(cmd)
        self.processes[app_name] = p

    def stop_app(self, app_name):
        if app_name in self.processes:
            self.processes[app_name].terminate()
            del self.processes[app_name]
            with self.app.app_context():
                self.app.logger.info(f"Stopped {app_name}")

    def monitor_apps(self):
        while self.running:
            with self.app.app_context():
                cfg = self.app.config['MODULES']['threads']['config']
                for name, proc in list(self.processes.items()):
                    if proc.poll() is not None:
                        self.app.logger.warning(f"{name} crashed, restarting...")
                        self.start_app(name, cfg.get(name, {}))
            time.sleep(1)

    def start(self):
        with self.app.app_context():
            self.running = True
            mon = threading.Thread(target=self.monitor_apps, daemon=True)
            mon.start()
            self.threads['monitor'] = mon

            cfg = self.app.config['MODULES']['threads']
            for name in cfg.get('modules', []):
                conf = cfg.get('config', {}).get(name, {})
                if name != 'camera_monitor' and conf.get('script_path') and os.path.exists(conf['script_path']):
                    self.start_app(name, conf)

    def stop(self):
        self.running = False
        for t in self.threads.values():
            t.join(timeout=1)
        for name in list(self.processes):
            self.stop_app(name)

def run(app):
    manager = StreamlitManager(app)
    manager.start()
    return manager
