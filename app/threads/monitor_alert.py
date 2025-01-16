import time
import json
from datetime import datetime
from app import db, websocket_queue
from app.models.variables import Variables
from app.models.log_data import LogData
from sqlalchemy.orm import sessionmaker
from flask import current_app

# Thread per monitorare il consumo di filo e confrontarlo con il parametro spola e l'olio
def run(app):
    SLEEP_TIME = 5
    with app.app_context():
        while True:
            try:
                Session = sessionmaker(bind=db.engine)
                with Session() as session:
                    # Ottieni tutti i parametri necessari dalle variables in un'unica query
                    variable_codes = [
                        'parametro_spola', 'parametro_olio', 'data_cambio_spola', 'data_cambio_olio', 'livello_olio',
                        'alert_spola', 'parametro_spola_attivo', 'parametro_olio_attivo'
                    ]
                    variables = {var.variable_code: var for var in session.query(Variables).filter(Variables.variable_code.in_(variable_codes)).all()}

                    # Recupera l'ID della variabile consumo
                    consumo_var_id = session.query(Variables).filter_by(variable_code='encoder_consumo').first().id

                    # Verifica se i controlli di spola sono attivi
                    if variables.get('parametro_spola_attivo') and variables['parametro_spola_attivo'].get_value():
                        parametro_spola = float(variables['parametro_spola'].get_value())
                        data_cambio_spola = datetime.strptime(variables['data_cambio_spola'].get_value(), "%d/%m/%Y %H:%M:%S")

                        # Calcola il consumo totale dal cambio spola ad ora
                        consumo_totale = session.query(db.func.sum(LogData.numeric_value)).filter(
                            LogData.variable_id == consumo_var_id,
                            LogData.created_at >= data_cambio_spola
                        ).scalar() or 0.0

                        if consumo_totale > parametro_spola:
                            current_app.logger.warning(f"Attenzione: il consumo totale di {consumo_totale:.2f} cm ha superato il valore di spola di {parametro_spola:.2f} cm.")
                            websocket_queue.put("alert_spola")
                        else:
                            current_app.logger.info(f"Consumo totale: {consumo_totale:.2f} cm. Valore spola: {parametro_spola:.2f} cm. Periodo: dal {data_cambio_spola} ad ora ({datetime.now()})")

                    # Recupera l'ID della variabile operatività
                    operativita_var_id = session.query(Variables).filter_by(variable_code='encoder_operativita').first().id

                    # Verifica se i controlli di olio sono attivi
                    if variables.get('parametro_olio_attivo') and variables['parametro_olio_attivo'].get_value():
                        parametro_olio = float(variables['parametro_olio'].get_value())
                        data_cambio_olio = datetime.strptime(variables['data_cambio_olio'].get_value(), "%d/%m/%Y %H:%M:%S")

                        # Calcola il tempo operativo accumulato dal cambio olio ad ora
                        tempo_operativo_totale = session.query(db.func.sum(LogData.numeric_value)).filter(
                            LogData.variable_id == operativita_var_id,
                            LogData.created_at >= data_cambio_olio
                        ).scalar() or 0.0

                        tempo_operativo_totale = tempo_operativo_totale / 3600  # Converti da secondi a ore

                        if tempo_operativo_totale > parametro_olio:
                            current_app.logger.warning(f"Attenzione: il tempo operativo di {tempo_operativo_totale:.2f} ore ha superato il limite di {parametro_olio:.2f} ore per l'olio.")
                            websocket_queue.put("alert_olio")
                        else:
                            current_app.logger.info(f"Tempo operativo totale: {tempo_operativo_totale:.2f} ore. Valore limite olio: {parametro_olio:.2f} ore. Periodo: dal {data_cambio_olio} ad ora ({datetime.now()})")

                    # Commit delle modifiche per gli alert
                    session.commit()

                    # Attendi prima di eseguire nuovamente il controllo
                    time.sleep(SLEEP_TIME)

            except Exception as e:
                current_app.logger.error(f"Errore durante il controllo del consumo di filo e dell'olio: {e}")
                time.sleep(SLEEP_TIME)
