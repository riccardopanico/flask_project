import time
import threading

def scheduled_task():
    print(f"RP Debug: Task avviato - Thread ID: {threading.get_ident()} - Ora: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    time.sleep(60) 
    print(f"RP Debug: Esecuzione del task programmato - Thread ID: {threading.get_ident()} - Ora: {time.strftime('%Y-%m-%d %H:%M:%S')}")