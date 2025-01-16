from flask import current_app
from sqlalchemy.exc import SQLAlchemyError, DataError
from sqlalchemy.orm import sessionmaker
from app import db
from app.models.log_data import LogData
from app.models.device import Device
from app.models.variables import Variables
from app.utils.api_oracle_manager import ApiOracleManager
from datetime import timedelta

JOB_INTERVAL = timedelta(seconds=15)

def run(app):
    """Job per inviare i log salvati a Oracle in un'unica chiamata e aggiornarne lo stato."""
    with app.app_context():
        try:
            current_app.logger.info("Inizio del lavoro di invio dei log a Oracle...")

            Session = sessionmaker(bind=db.engine)
            with Session() as session:
                logs_to_send = session.query(LogData).filter(LogData.sent == 0).all()

                if not logs_to_send:
                    current_app.logger.info("Nessun log da inviare trovato.")
                    return

                api_oracle_manager = ApiOracleManager()

                log_payloads = []
                for log in logs_to_send:
                    try:
                        device = session.query(Device).filter(Device.id == log.device_id).first()
                        variable = session.query(Variables).filter(Variables.id == log.variable_id).first()

                        if not device or not variable:
                            current_app.logger.warning(f"Dispositivo o variabile non trovati per il log {log.id}.")
                            continue

                        log_payloads.append({
                            "user_id": log.user_id,
                            "device_id": device.interconnection_id,  # Usa il valore di interconnection_id
                            "variable_code": variable.variable_code,  # Usa il valore di variable_code
                            "variable_name": variable.variable_name,
                            "numeric_value": log.numeric_value,
                            "boolean_value": log.boolean_value,
                            "string_value": log.string_value,
                            "created_at": log.created_at.isoformat()
                        })
                    except AttributeError as attr_err:
                        current_app.logger.error(f"Errore di attributo per il log {log.id}: {attr_err}")
                        continue

                if not log_payloads:
                    current_app.logger.info("Nessun log valido da inviare.")
                    return

                try:
                    current_app.logger.debug(f"Invio dei log: {log_payloads}")
                    response = api_oracle_manager.call(
                        url='/device/data',
                        params={"logs": log_payloads},
                        method='POST'
                    )

                    if response['success']:
                        for log in logs_to_send:
                            log.sent = 1
                            session.add(log)
                        session.commit()
                        current_app.logger.info("Tutti i log sono stati inviati con successo.")
                    else:
                        current_app.logger.error(
                            f"Errore nell'invio dei log: {response['error']}"
                        )
                except SQLAlchemyError as db_error:
                    session.rollback()
                    current_app.logger.error(f"Errore del database durante l'invio dei log: {db_error}", exc_info=True)
                except DataError as data_error:
                    session.rollback()
                    current_app.logger.error(f"Errore di dati durante l'invio dei log: {data_error}", exc_info=True)
                except Exception as sync_error:
                    session.rollback()
                    current_app.logger.error(f"Errore imprevisto durante l'invio dei log: {sync_error}", exc_info=True)

        except Exception as critical_error:
            current_app.logger.critical(f"Errore critico nel lavoro di invio dei log: {critical_error}", exc_info=True)
