# import time

# def run(app):
#     # Utilizza il contesto dell'app Flask per accedere ai servizi dell'applicazione
#     with app.app_context():
#         while True:
#             print(f"Thread di esempio in esecuzione alle: {time.strftime('%Y-%m-%d %H:%M:%S')}")
#             # Logica che deve essere eseguita continuamente
#             # Puoi accedere a modelli, database, ecc. con il contesto attivo
#             time.sleep(5)  # Esegui l'operazione ogni 5 secondi
