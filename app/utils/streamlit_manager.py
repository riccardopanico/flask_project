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

    def start_app(self, app_name, config):
        """Start a Streamlit app with the given configuration"""
        try:
            script_path = f"app/threads/{app_name}.py"
            port = config.get('port', 8501)

            cmd = [
                "streamlit",
                "run",
                script_path,
                "--server.port",
                str(port),
                "--server.headless",
                str(config.get('headless', True)).lower(),
                "--server.enableCORS",
                str(config.get('enableCORS', False)).lower(),
                "--server.enableXsrfProtection",
                str(config.get('enableXsrfProtection', False)).lower()
            ]
            
            with self.app.app_context():
                self.app.logger.info(f"Starting Streamlit app '{app_name}' on port {port}")
                self.app.logger.info(f"Streamlit app URL: http://localhost:{port}")
            process = subprocess.Popen(cmd)
            self.processes[app_name] = process
            return True
        except Exception as e:
            with self.app.app_context():
                self.app.logger.error(f"Error starting Streamlit app {app_name}: {str(e)}")
            return False

    def stop_app(self, app_name):
        """Stop a specific Streamlit app"""
        if app_name in self.processes:
            self.processes[app_name].terminate()
            del self.processes[app_name]
            with self.app.app_context():
                self.app.logger.info(f"Stopped Streamlit app {app_name}")

    def stop_all(self):
        """Stop all running Streamlit apps"""
        for app_name in list(self.processes.keys()):
            self.stop_app(app_name)

    def monitor_apps(self):
        """Monitor and restart Streamlit apps if they crash"""
        while self.running:
            try:
                with self.app.app_context():
                    for app_name, process in list(self.processes.items()):
                        if process.poll() is not None:  # Process has terminated
                            self.app.logger.warning(f"Streamlit app {app_name} stopped, restarting...")
                            config = self.app.config['MODULES']['threads']['config'].get(app_name, {})
                            self.start_app(app_name, config)
            except Exception as e:
                with self.app.app_context():
                    self.app.logger.error(f"Error in monitor_apps: {str(e)}")
            time.sleep(1)

    def start(self):
        """Start the Streamlit manager"""
        with self.app.app_context():
            self.running = True
            # Start monitoring thread
            monitor_thread = threading.Thread(target=self.monitor_apps, daemon=True)
            monitor_thread.start()
            self.threads['monitor'] = monitor_thread

            # Start all configured apps
            thread_config = self.app.config['MODULES']['threads']
            if thread_config.get('enabled', False):
                for app_name in thread_config['modules']:
                    if app_name.endswith('_inference'):  # Only start inference apps
                        config = thread_config['config'].get(app_name, {})
                        if os.path.exists(f"app/threads/{app_name}.py"):
                            self.start_app(app_name, config)
                        else:
                            self.app.logger.error(f"Streamlit script not found for app {app_name}")

    def stop(self):
        """Stop the Streamlit manager and all apps"""
        self.running = False
        self.stop_all()
        for thread in self.threads.values():
            thread.join(timeout=1) 