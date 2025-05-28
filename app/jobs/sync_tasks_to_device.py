from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from datetime import timedelta
from app.models.tasks import Task
from app.models.device import Device
from app.utils.api_device_manager import ApiDeviceManager

JOB_INTERVAL = timedelta(seconds=5)

def run(app):
    with app.app_context():
        try:
            if current_app.debug:
                current_app.logger.debug("Sincronizzazione dei task non inviati al data center in corso...")

            Session = sessionmaker(bind=db.engine)
            with Session() as session:
                # Recupera i task non inviati
                unsent_tasks = session.query(Task).filter(Task.sent == 0).all()
                if not unsent_tasks:
                    current_app.logger.debug("Nessun task da sincronizzare con il data center.")
                    return

                # Raggruppa i task per device_id
                tasks_by_device = {}
                for task in unsent_tasks:
                    if task.device_id not in tasks_by_device:
                        tasks_by_device[task.device_id] = []
                    tasks_by_device[task.device_id].append(task)

                # Per ogni device, invia i suoi task
                for device_id, tasks in tasks_by_device.items():
                    device = session.query(Device).get(device_id)
                    if not device:
                        current_app.logger.error(f"Device {device_id} non trovato per i task")
                        continue

                    # Separa i task in nuovi e da aggiornare
                    new_tasks = []
                    update_tasks = []
                    
                    for task in tasks:
                        task_dict = task.to_dict()
                        # Se il task non ha updated_at, è un nuovo record
                        if not task.updated_at:
                            new_tasks.append(task_dict)
                        else:
                            update_tasks.append(task_dict)

                    api_manager = app.api_device_manager.get(device.username)
                    if not api_manager:
                        current_app.logger.info(f"Device manager non trovato per il dispositivo {device.username}. Creazione in corso...")
                        api_manager = ApiDeviceManager(
                            ip_address=device.ip_address,
                            username=device.username,
                            password=device.password
                        )
                        app.api_device_manager[device.username] = api_manager

                    try:
                        # Invia i nuovi task con POST
                        if new_tasks:
                            current_app.logger.info(f"Invio {len(new_tasks)} nuovi task al device {device.username}")
                            post_response = api_manager.call('/task', params={'tasks': new_tasks}, method='POST')
                            
                            if post_response.get('success'):
                                # Marca i task come inviati
                                task_ids = [task.id for task in tasks if not task.updated_at]
                                session.query(Task).filter(Task.id.in_(task_ids)).update({Task.sent: 1}, synchronize_session=False)
                                current_app.logger.info(f"Nuovi task inviati con successo al device {device.username}")
                            else:
                                current_app.logger.error(f"Errore durante l'invio dei nuovi task al device {device.username}: {post_response.get('error')}")

                        # Aggiorna i task esistenti con PUT
                        if update_tasks:
                            current_app.logger.info(f"Aggiornamento di {len(update_tasks)} task al device {device.username}")
                            put_response = api_manager.call('/task', params={'tasks': update_tasks}, method='PUT')
                            
                            if put_response.get('success'):
                                # Marca i task come inviati
                                task_ids = [task.id for task in tasks if task.updated_at]
                                session.query(Task).filter(Task.id.in_(task_ids)).update({Task.sent: 1}, synchronize_session=False)
                                current_app.logger.info(f"Task aggiornati con successo al device {device.username}")
                            else:
                                current_app.logger.error(f"Errore durante l'aggiornamento dei task al device {device.username}: {put_response.get('error')}")

                        session.commit()

                    except Exception as e:
                        current_app.logger.error(f"Errore durante la comunicazione con il device {device.username}: {str(e)}")
                        continue

        except SQLAlchemyError as e:
            current_app.logger.error(f"Errore durante la sincronizzazione dei task: {str(e)}")
        except Exception as e:
            current_app.logger.critical(f"Errore critico durante la sincronizzazione dei task: {str(e)}")
