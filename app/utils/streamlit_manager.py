import os
import subprocess
import psutil
from typing import Optional

class StreamlitManager:
    def __init__(self, config_dir: str = '.', logger: Optional[object] = None):
        self.registry = {}   # {name: cfg}
        self.procs    = {}   # {name: subprocess.Popen}
        self.log_dir  = os.path.join(config_dir, 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        self.logger   = logger  # può essere Flask logger o custom

    def register(self, name, cfg):
        """Registra un'app Streamlit con il suo nome e configurazione"""
        self.registry[name] = cfg

    def is_streamlit_running(self, port):
        """Controlla se Streamlit è già attivo su quella porta"""
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline')
                if not cmdline:
                    continue
                if 'streamlit' in cmdline and f'--server.port={port}' in cmdline:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    def get_running_ports(self):
        """Ritorna un elenco delle porte Streamlit attive (per debug)"""
        ports = []
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info.get('cmdline')
                if not cmdline or 'streamlit' not in cmdline:
                    continue
                for arg in cmdline:
                    if arg.startswith('--server.port='):
                        ports.append(arg.split('=')[1])
            except Exception:
                continue
        return ports

    def start(self):
        """Avvia tutte le app Streamlit registrate"""
        for name, cfg in self.registry.items():
            script = cfg.get('script_path')
            port   = cfg.get('port')
            if not script or not os.path.exists(script):
                self._log(f"[STREAMLIT] Script mancante per {name}", level="error")
                continue
            if not port:
                self._log(f"[STREAMLIT] Porta non specificata per {name}", level="error")
                continue
            if self.is_streamlit_running(port):
                self._log(f"[STREAMLIT] {name} già attivo su porta {port}, salto avvio.", level="warning")
                continue

            log_path = os.path.join(self.log_dir, f"{name}.log")
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
                self._log(f"[STREAMLIT] {name} avviato: http://localhost:{port}")
            except Exception as e:
                self._log(f"[STREAMLIT] Errore avviando {name}: {e}", level="error")

    def stop(self):
        """Termina tutti i processi Streamlit avviati"""
        for name, p in self.procs.items():
            try:
                p.terminate()
                self._log(f"[STREAMLIT] {name} terminato.")
            except Exception as e:
                self._log(f"[STREAMLIT] Errore terminando {name}: {e}", level="warning")

    def _log(self, msg, level="info"):
        if self.logger:
            getattr(self.logger, level, self.logger.info)(msg)
        else:
            print(f"[{level.upper()}] {msg}")
