import time
import json
from datetime import datetime
from app import db, websocket_queue
from app.models.impostazioni import Impostazioni
from app.models.log_orlatura import LogOrlatura
from sqlalchemy.orm import sessionmaker

# Thread per monitorare il consumo di filo e confrontarlo con il parametro spola e l'olio
def run(app):
    SLEEP_TIME = 60
    with app.app_context():
        while True:
            try:
                Session = sessionmaker(bind=db.engine)
                session = Session()
                
                # Ottieni tutti i parametri necessari dalle impostazioni in un'unica query
                impostazioni = session.query(Impostazioni).filter(Impostazioni.codice.in_([
                    'parametro_spola', 'parametro_olio', 'data_cambio_spola', 'data_cambio_olio', 'livello_olio', 'alert_spola', 'alert_olio'
                ])).all()
                impostazioni = {impostazione.codice: impostazione for impostazione in impostazioni}
                
                # Ottieni e calcola i valori
                parametro_spola = float(impostazioni['parametro_spola'].valore)
                parametro_olio = float(impostazioni['parametro_olio'].valore)
                data_cambio_spola = datetime.strptime(impostazioni['data_cambio_spola'].valore, "%d/%m/%Y %H:%M:%S")
                data_cambio_olio = datetime.strptime(impostazioni['data_cambio_olio'].valore, "%d/%m/%Y %H:%M:%S")
                livello_olio = float(impostazioni['livello_olio'].valore)
                
                # Controllo del consumo per la spola
                consumo_totale = session.query(db.func.sum(LogOrlatura.consumo)).filter(LogOrlatura.data >= data_cambio_spola).scalar() or 0.0
                if consumo_totale > parametro_spola:
                    print(f"Attenzione: il consumo totale di {consumo_totale} cm ha superato il valore di spola di {parametro_spola} cm.")
                    impostazioni['alert_spola'].valore = '1'
                    websocket_queue.put("alert_spola")
                else:
                    print(f"Consumo totale: {consumo_totale} cm. Valore spola: {parametro_spola} cm. Periodo di riferimento: dal {data_cambio_spola.strftime('%d/%m/%Y %H:%M:%S')} ad ora ({datetime.now().strftime('%d/%m/%Y %H:%M:%S')})")
                
                # Controllo del livello di olio
                tempo_passato = (datetime.now() - data_cambio_olio).total_seconds() / 3600  # Tempo passato in ore
                if livello_olio < parametro_olio:
                    print(f"Attenzione: il livello dell'olio {livello_olio} è inferiore al valore minimo di {parametro_olio}.")
                    impostazioni['alert_olio'].valore = '1'
                    websocket_queue.put("alert_olio")
                else:
                    print(f"Livello olio: {livello_olio}. Valore minimo richiesto: {parametro_olio}. Tempo passato: {tempo_passato:.2f} ore. Periodo di riferimento: dal {data_cambio_olio.strftime('%d/%m/%Y %H:%M:%S')} ad ora ({datetime.now().strftime('%d/%m/%Y %H:%M:%S')})")
                
                # Commit delle modifiche per gli alert
                session.commit()
                
                # Attendi prima di eseguire nuovamente il controllo
                time.sleep(SLEEP_TIME)

            except Exception as e:
                print(f"Errore durante il controllo del consumo di filo e dell'olio: {e}")
                time.sleep(SLEEP_TIME)
            finally:
                # Chiudi la sessione per garantire che le modifiche vengano viste
                session.close()
