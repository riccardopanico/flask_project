import time

def run():
    while True:
        print(f"Thread di esempio in esecuzione alle: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        # Logica che deve essere eseguita continuamente
        time.sleep(5)  # Esegui l'operazione ogni 5 secondi
