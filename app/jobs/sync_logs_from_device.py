from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from app.models.log_data import LogData
from app.models.device import Device
from app.models.user import User
from app.utils.api_device_manager import ApiDeviceManager
from datetime import timedelta

JOB_INTERVAL = timedelta(seconds=15)

def run(app):
    """Job per sincronizzare i log da tutti i dispositivi."""
    with app.app_context():
        try:
            current_app.logger.info("Inizio del lavoro di sincronizzazione dei log...")

            Session = sessionmaker(bind=db.engine)
            with Session() as session:
                devices = session.query(Device).join(User).filter(
                    User.user_type == 'device'
                ).all()
                if not devices:
                    current_app.logger.warning("Nessun dispositivo trovato per la sincronizzazione.")
                    return

                for device in devices:
                    try:
                        api_manager = app.api_device_manager.get(device.username)
                        if not api_manager:
                            current_app.logger.info(f"Creazione del ApiManager per il dispositivo {device.username}...")
                            api_manager = ApiDeviceManager(
                                ip_address=device.ip_address,
                                username=device.username,
                                password=device.password
                            )
                            app.api_device_manager[device.username] = api_manager

                        last_log = session.query(LogData).filter_by(device_id=device.id).order_by(LogData.created_at.desc()).first()
                        last_sync_date = last_log.created_at.isoformat() if last_log else None

                        response = api_manager.call(f'/device/{device.interconnection_id}/log_data', method='GET', params={'last_sync_date': last_sync_date})

                        if response['success']:
                            for log_dict in response['data']:
                                log = LogData(
                                    user_id=log_dict.get('user_id'),
                                    device_id=device.id,
                                    variable_id=log_dict.get('variable_id'),
                                    numeric_value=log_dict.get('numeric_value'),
                                    boolean_value=log_dict.get('boolean_value'),
                                    string_value=log_dict.get('string_value'),
                                    created_at=log_dict.get('created_at')
                                )
                                session.add(log)
                            session.commit()
                            current_app.logger.info(f"Log per il dispositivo {device.ip_address} sincronizzati con successo.")
                        else:
                            current_app.logger.error(f"Errore nella sincronizzazione dei log per il dispositivo {device.ip_address}: {response['error']}", exc_info=True)
                    except SQLAlchemyError as db_error:
                        session.rollback()
                        current_app.logger.error(f"Errore del database per il dispositivo {device.ip_address}: {db_error}", exc_info=True)
                    except Exception as sync_error:
                        session.rollback()
                        current_app.logger.error(f"Errore imprevisto durante la sincronizzazione dei log per il dispositivo {device.ip_address}: {sync_error}", exc_info=True)
        except Exception as critical_error:
            current_app.logger.critical(f"Errore critico nel lavoro di sincronizzazione dei log: {critical_error}", exc_info=True)
