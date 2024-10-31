import time
import asyncio
import json
from datetime import datetime
from app import db
from app.models.impostazioni import Impostazioni
from app.models.log_orlatura import LogOrlatura
from app.threads.websocket import broadcast_message

# Thread per monitorare il consumo di filo e confrontarlo con il parametro spola
def run(app):
    with app.app_context():
        while True:
            try:
                # Ottieni il valore del parametro spola dalle impostazioni
                parametro_spola = Impostazioni.query.filter_by(codice='parametro_spola').first()
                if parametro_spola:
                    valore_spola = float(parametro_spola.valore)
                else:
                    print("Parametro spola non trovato nel database.")
                    time.sleep(60)  # Riprova dopo un minuto
                    continue

                # Ottieni la data di riferimento per il calcolo del consumo
                data_cambio_spola = Impostazioni.query.filter_by(codice='data_cambio_spola').first()
                if data_cambio_spola:
                    data_riferimento = datetime.strptime(data_cambio_spola.valore, "%d/%m/%Y %H:%M:%S")
                else:
                    print("Data cambio spola non trovata nel database.")
                    time.sleep(60)  # Riprova dopo un minuto
                    continue

                # Calcola la somma del consumo di filo da data_riferimento ad oggi
                consumo_totale = db.session.query(db.func.sum(LogOrlatura.consumo)).filter(LogOrlatura.data >= data_riferimento).scalar()
                consumo_totale = consumo_totale if consumo_totale else 0.0

                # Controlla se il consumo totale supera il valore del parametro spola
                if consumo_totale > valore_spola:
                    print(f"Attenzione: il consumo totale di {consumo_totale} cm ha superato il valore di spola di {valore_spola} cm.")
                    # Invia un messaggio al websocket
                    message = json.dumps({
                        "alert": "consumo_superato",
                        "consumo_totale": consumo_totale,
                        "valore_spola": valore_spola
                    })
                    asyncio.run(broadcast_message(message))

                # Attendi prima di eseguire nuovamente il controllo
                time.sleep(5)  # Verifica ogni 5 secondi

            except Exception as e:
                print(f"Errore durante il controllo del consumo di filo: {e}")
                time.sleep(30)  # In caso di errore, attende 30 secondi prima di riprovare
