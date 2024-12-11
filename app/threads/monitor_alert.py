import time
import json
from datetime import datetime
from app import db, websocket_queue
from app.models.variables import Variables
from app.models.log_orlatura import LogOrlatura
from sqlalchemy.orm import sessionmaker

# Thread per monitorare il consumo di filo e confrontarlo con il parametro spola e l'olio
def run(app):
    SLEEP_TIME = 5
    with app.app_context():
        while True:
            try:
                Session = sessionmaker(bind=db.engine)
                session = Session()

                # Ottieni tutti i parametri necessari dalle variables in un'unica query
                variable_codes = [
                    'parametro_spola', 'parametro_olio', 'data_cambio_spola', 'data_cambio_olio', 'livello_olio',
                    'alert_spola', 'alert_olio', 'parametro_spola_attivo', 'parametro_olio_attivo'
                ]
                variables = {var.variable_code: var for var in session.query(Variables).filter(Variables.variable_code.in_(variable_codes)).all()}

                # Verifica se i controlli di spola e olio sono attivi
                if variables.get('parametro_spola_attivo') and variables['parametro_spola_attivo'].get_value() == 1:
                    # Controllo del consumo per la spola
                    parametro_spola = float(variables['parametro_spola'].get_value())
                    data_cambio_spola = datetime.strptime(variables['data_cambio_spola'].get_value(), "%d/%m/%Y %H:%M:%S")
                    consumo_totale = session.query(db.func.sum(LogOrlatura.consumo)).filter(LogOrlatura.data >= data_cambio_spola).scalar() or 0.0

                    if consumo_totale > parametro_spola:
                        print(f"Attenzione: il consumo totale di {consumo_totale} cm ha superato il valore di spola di {parametro_spola} cm.")
                        websocket_queue.put("alert_spola")
                    else:
                        print(f"Consumo totale: {consumo_totale} cm. Valore spola: {parametro_spola} cm. Periodo di riferimento: dal {data_cambio_spola.strftime('%d/%m/%Y %H:%M:%S')} ad ora ({datetime.now().strftime('%d/%m/%Y %H:%M:%S')})")

                if variables.get('parametro_olio_attivo') and variables['parametro_olio_attivo'].get_value() == 1:
                    # Controllo del livello di olio
                    parametro_olio = float(variables['parametro_olio'].get_value())  # Valore in ore
                    data_cambio_olio = datetime.strptime(variables['data_cambio_olio'].get_value(), "%d/%m/%Y %H:%M:%S")
                    tempo_passato_ore = (datetime.now() - data_cambio_olio).total_seconds() / 3600

                    if tempo_passato_ore > parametro_olio:
                        print(f"Attenzione: il tempo passato di {tempo_passato_ore:.2f} ore ha superato il limite di {parametro_olio} ore per l'olio.")
                        websocket_queue.put("alert_olio")
                    else:
                        print(f"Tempo passato: {tempo_passato_ore:.2f} ore. Valore limite olio: {parametro_olio} ore. Periodo di riferimento: dal {data_cambio_olio.strftime('%d/%m/%Y %H:%M:%S')} ad ora ({datetime.now().strftime('%d/%m/%Y %H:%M:%S')})")

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
