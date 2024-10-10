import time
import threading

def scheduled_task():
    print(f"Esecuzione del task programmato - Thread ID: {threading.get_ident()} - Ora: {time.strftime('%Y-%m-%d %H:%M:%S')}")
