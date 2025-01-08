from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from datetime import timedelta
from app.models.tasks import Task

JOB_INTERVAL = timedelta(seconds=5)

def run(app):
    with app.app_context():
        try:
            if current_app.debug:
                current_app.logger.debug("Sincronizzazione dei task non inviati al data center in corso...")

            Session = sessionmaker(bind=db.engine)
            with Session() as session:
                unsent_tasks = session.query(Task).filter(Task.sent == 0).all()
                if not unsent_tasks:
                    current_app.logger.debug("Nessun task da sincronizzare con il data center.")
                    return

                task_data = [task.to_dict() for task in unsent_tasks]

                api_manager = app.api_device_manager.get(device.username)
                if not api_manager:
                    current_app.logger.info(f"Device manager non trovato per il dispositivo {device.username}. Creazione in corso...")
                    api_manager = ApiDeviceManager(
                        ip_address=device.ip_address,
                        username=device.username,
                        password=device.password
                    )
                    app.api_device_manager[device.username] = api_manager

                response = api_manager.call('/task', params={'tasks': task_data}, method='POST')

                if response['success']:
                    task_ids = [task.id for task in unsent_tasks]
                    session.query(Task).filter(Task.id.in_(task_ids)).update({Task.sent: 1}, synchronize_session=False)
                    session.commit()
                    current_app.logger.info("I task sono stati inviati e aggiornati con successo nel data center.")
                else:
                    current_app.logger.error(f"Errore durante la sincronizzazione dei task: {response['error']}")

        except SQLAlchemyError as e:
            current_app.logger.error(f"Errore durante la sincronizzazione dei task: {str(e)}")
        except Exception as e:
            current_app.logger.critical(f"Errore critico durante la sincronizzazione dei task: {str(e)}")
