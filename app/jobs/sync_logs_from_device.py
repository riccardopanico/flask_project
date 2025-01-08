from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from app.models.log_data import LogData
from app.models.device import Device
from datetime import timedelta

JOB_INTERVAL = timedelta(seconds=5)

def run(app):
    with app.app_context():
        try:
            if current_app.debug:
                current_app.logger.debug("Sincronizzazione dei log_data presenti in MF1 in corso...")

            Session = sessionmaker(bind=db.engine)
            with Session() as session:
                for device in session.query(Device).all():
                    try:
                        device_manager = app.api_device_manager.get(device.username)
                        if not device_manager:
                            current_app.logger.error(f"Device manager non trovato per il dispositivo {device.username}.")
                            continue

                        last_log = session.query(LogData).filter_by(device_id=device.id).order_by(LogData.created_at.desc()).first()
                        last_sync_date = last_log.created_at.isoformat() if last_log else None

                        response = device_manager.call('log_data', method='GET', params={'last_sync_date': last_sync_date})

                        if response['success']:
                            for log_dict in response['data']:
                                log = LogData(**log_dict)
                                log.device_id = device.id
                                session.add(log)
                            session.commit()
                            current_app.logger.info(f"I log_data del dispositivo {device.ip_address} sono stati sincronizzati con successo.")
                        else:
                            current_app.logger.error(f"Errore durante la sincronizzazione dei log_data del dispositivo {device.ip_address}: {response['error']}")
                    except SQLAlchemyError as e:
                        session.rollback()
                        current_app.logger.error(f"Errore del database per il dispositivo {device.ip_address}: {str(e)}")
                    except Exception as e:
                        session.rollback()
                        current_app.logger.error(f"Errore durante l'elaborazione dei log_data del dispositivo {device.ip_address}: {str(e)}")
        except Exception as e:
            current_app.logger.critical(f"Errore critico durante la sincronizzazione dei log_data: {str(e)}")
