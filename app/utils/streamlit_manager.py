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
            script_path = config.get('script_path')
            port = config.get('port', 8501)
            app_config = config.get('config', {})

            cmd = [
                "streamlit",
                "run",
                script_path,
                "--server.port",
                str(port),
                "--server.headless",
                str(app_config.get('headless', True)).lower(),
                "--server.enableCORS",
                str(app_config.get('enableCORS', False)).lower(),
                "--server.enableXsrfProtection",
                str(app_config.get('enableXsrfProtection', False)).lower()
            ]
            
            current_app.logger.info(f"Starting Streamlit app '{app_name}' on port {port}")
            process = subprocess.Popen(cmd)
            self.processes[app_name] = process
            return True
        except Exception as e:
            current_app.logger.error(f"Error starting Streamlit app {app_name}: {str(e)}")
            return False

    def stop_app(self, app_name):
        """Stop a specific Streamlit app"""
        if app_name in self.processes:
            self.processes[app_name].terminate()
            del self.processes[app_name]
            current_app.logger.info(f"Stopped Streamlit app {app_name}")

    def stop_all(self):
        """Stop all running Streamlit apps"""
        for app_name in list(self.processes.keys()):
            self.stop_app(app_name)

    def monitor_apps(self):
        """Monitor and restart Streamlit apps if they crash"""
        while self.running:
            for app_name, process in list(self.processes.items()):
                if process.poll() is not None:  # Process has terminated
                    current_app.logger.warning(f"Streamlit app {app_name} stopped, restarting...")
                    config = self.app.config['STREAMLIT']['apps'].get(app_name, {})
                    self.start_app(app_name, config)
            time.sleep(1)

    def start(self):
        """Start the Streamlit manager"""
        self.running = True
        # Start monitoring thread
        monitor_thread = threading.Thread(target=self.monitor_apps, daemon=True)
        monitor_thread.start()
        self.threads['monitor'] = monitor_thread

        # Start all configured apps
        streamlit_config = self.app.config['STREAMLIT']
        if streamlit_config.get('enabled', False):
            for app_name, config in streamlit_config['apps'].items():
                if os.path.exists(config.get('script_path', '')):
                    self.start_app(app_name, config)
                else:
                    current_app.logger.error(f"Streamlit script not found for app {app_name}")

    def stop(self):
        """Stop the Streamlit manager and all apps"""
        self.running = False
        self.stop_all()
        for thread in self.threads.values():
            thread.join(timeout=1) 