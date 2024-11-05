import time
import json
from datetime import datetime
from app import db, websocket_queue
from app.models.impostazioni import Impostazioni
from app.models.log_orlatura import LogOrlatura
from sqlalchemy.orm import sessionmaker

# Thread per monitorare il consumo di filo e confrontarlo con il parametro spola
def run(app):
    SLEEP_TIME = 5
    with app.app_context():
        while True:
            try:
                Session = sessionmaker(bind=db.engine)
                session = Session()
                # Ottieni il valore del parametro spola dalle impostazioni
                parametro_spola = session.query(Impostazioni).filter_by(codice='parametro_spola').first()
                if parametro_spola:
                    valore_spola = float(parametro_spola.valore)
                else:
                    print("Parametro spola non trovato nel database.")
                    time.sleep(SLEEP_TIME)
                    continue

                # Ottieni la data di riferimento per il calcolo del consumo
                data_cambio_spola = session.query(Impostazioni).filter_by(codice='data_cambio_spola').first()
                if data_cambio_spola:
                    data_riferimento = datetime.strptime(data_cambio_spola.valore, "%d/%m/%Y %H:%M:%S")
                else:
                    print("Data cambio spola non trovata nel database.")
                    time.sleep(SLEEP_TIME)
                    continue

                # Calcola la somma del consumo di filo da data_riferimento ad oggi
                consumo_totale = session.query(db.func.sum(LogOrlatura.consumo)).filter(LogOrlatura.data >= data_riferimento).scalar()
                consumo_totale = consumo_totale if consumo_totale else 0.0

                # Controlla se il consumo totale supera il valore del parametro spola
                if consumo_totale > valore_spola:
                    print(f"Attenzione: il consumo totale di {consumo_totale} cm ha superato il valore di spola di {valore_spola} cm.")
                    # Imposta l'impostazione di alert_spola a 1
                    alert_spola = session.query(Impostazioni).filter_by(codice='alert_spola').first()
                    if alert_spola:
                        alert_spola.valore = '1'
                        
                    session.commit()
                    websocket_queue.put("alert_spola")
                else:
                    print(f"Consumo totale: {consumo_totale} cm. Valore spola: {valore_spola} cm. Periodo di riferimento: dal {data_riferimento.strftime('%d/%m/%Y %H:%M:%S')} ad ora ({datetime.now().strftime('%d/%m/%Y %H:%M:%S')})")

                # Attendi prima di eseguire nuovamente il controllo
                time.sleep(SLEEP_TIME)

            except Exception as e:
                print(f"Errore durante il controllo del consumo di filo: {e}")
                time.sleep(SLEEP_TIME)
            finally:
                # Chiudi la sessione per garantire che le modifiche vengano viste
                session.close()
