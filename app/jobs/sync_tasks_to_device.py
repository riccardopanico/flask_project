from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from datetime import timedelta
from app.models.tasks import Task
from app.models.device import Device
from app.models.user import User
from app.utils.api_device_manager import ApiDeviceManager

JOB_INTERVAL = timedelta(seconds=5)

def initialize_api_manager(app, device, record=None):
    with app.app_context():
        current_app.logger.info(f"=== Inizializzazione ApiDeviceManager per dispositivo {device.interconnection_id if device else 'None'} ===")
        current_app.logger.info(f"Stato attuale api_device_manager: {list(app.api_device_manager.keys())}")
        
        # Se il dispositivo è di tipo ip_camera, non creiamo l'ApiDeviceManager
        if record and record.get('user_type') == 'ip_camera':
            current_app.logger.debug(f"Dispositivo {record['interconnection_id']} è di tipo ip_camera, non creo ApiDeviceManager")
            return None

        old_username = device.username if device else None
        current_app.logger.info(f"Username corrente del dispositivo: {old_username}")
        current_app.logger.info(f"Password del dispositivo: {device.password if device else 'None'}")
        
        api_manager = app.api_device_manager.get(old_username)
        current_app.logger.info(f"ApiDeviceManager esistente trovato: {api_manager is not None}")
        if api_manager:
            current_app.logger.info(f"Credenziali ApiDeviceManager esistente - Username: {api_manager.username}, Password presente: {bool(api_manager.password)}")

        if device is None:
            current_app.logger.info(f"Creazione di un nuovo ApiDeviceManager per il dispositivo: {record['interconnection_id']}")
            current_app.logger.info(f"Credenziali da record - IP: {record['ip_address']}, Username: {record['username']}, Password: {record['password']}")
            api_manager = ApiDeviceManager(
                ip_address=record['ip_address'],
                username=record['username'],
                password=record['password']
            )
            app.api_device_manager[record['username']] = api_manager
            current_app.logger.info(f"Nuovo ApiDeviceManager creato e salvato con username: {record['username']}")

        elif api_manager is not None and api_manager.username == device.username:
            current_app.logger.info(f"Utilizzo dell'ApiDeviceManager esistente per il dispositivo: {device.interconnection_id}")
            current_app.logger.info(f"Credenziali attuali - IP: {api_manager.ip_address}, Username: {api_manager.username}, Password presente: {bool(api_manager.password)}")
            current_app.logger.info(f"Credenziali dispositivo - IP: {device.ip_address}, Username: {device.username}, Password: {device.password}")
            
            # Aggiorna le credenziali dell'ApiDeviceManager
            api_manager.ip_address = device.ip_address
            api_manager.username = device.username
            api_manager.password = device.password
            current_app.logger.info(f"Credenziali ApiDeviceManager aggiornate - IP: {api_manager.ip_address}, Username: {api_manager.username}, Password presente: {bool(api_manager.password)}")

        elif api_manager is not None and api_manager.username != device.username:
            current_app.logger.info(f"ApiDeviceManager con username cambiato: {device.interconnection_id}")
            current_app.logger.info(f"Vecchio username: {api_manager.username}, Nuovo username: {device.username}")
            current_app.logger.info(f"Password dispositivo: {device.password}")
            
            # Aggiorna le credenziali dell'ApiDeviceManager
            api_manager.ip_address = device.ip_address
            api_manager.username = device.username
            api_manager.password = device.password
            # Aggiorna il dizionario degli ApiDeviceManager
            if old_username in app.api_device_manager:
                del app.api_device_manager[old_username]
                current_app.logger.info(f"Rimosso ApiDeviceManager per vecchio username: {old_username}")
            app.api_device_manager[device.username] = api_manager
            current_app.logger.info(f"ApiDeviceManager aggiornato con nuove credenziali - IP: {api_manager.ip_address}, Username: {api_manager.username}, Password presente: {bool(api_manager.password)}")

        elif api_manager is None:
            current_app.logger.info(f"Creazione di un nuovo ApiDeviceManager per il dispositivo: {device.interconnection_id}")
            current_app.logger.info(f"Credenziali dispositivo - IP: {device.ip_address}, Username: {device.username}, Password: {device.password}")
            api_manager = ApiDeviceManager(
                ip_address=device.ip_address,
                username=device.username,
                password=device.password
            )
            app.api_device_manager[device.username] = api_manager
            current_app.logger.info(f"Nuovo ApiDeviceManager creato e salvato con username: {device.username}, Password presente: {bool(api_manager.password)}")
        else:
            current_app.logger.warning(f"(Anomalia) Dispositivo con api_manager Non Trovato per il dispositivo: {device.interconnection_id}")

        current_app.logger.info(f"=== Fine inizializzazione ApiDeviceManager per {device.interconnection_id if device else 'None'} ===")
        return api_manager

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

                    current_app.logger.info(f"=== Elaborazione task per device {device.interconnection_id} ===")
                    current_app.logger.info(f"Credenziali dispositivo - IP: {device.ip_address}, Username: {device.username}, Password: {device.password}")

                    # Inizializza l'ApiDeviceManager
                    api_manager = initialize_api_manager(app, device)
                    if not api_manager:
                        current_app.logger.warning(f"Impossibile creare ApiDeviceManager per il dispositivo {device.username}")
                        continue

                    # Log delle credenziali per debug
                    current_app.logger.info(f"Credenziali ApiDeviceManager per {device.username}:")
                    current_app.logger.info(f"- IP: {api_manager.ip_address}")
                    current_app.logger.info(f"- Username: {api_manager.username}")
                    current_app.logger.info(f"- Password: {api_manager.password}")

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

                    try:
                        # Invia i nuovi task con POST
                        if new_tasks:
                            current_app.logger.info(f"Invio {len(new_tasks)} nuovi task al device {device.username}")
                            current_app.logger.info(f"Credenziali usate per la chiamata - Username: {api_manager.username}, Password: {api_manager.password}")
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
                            current_app.logger.info(f"Credenziali usate per la chiamata - Username: {api_manager.username}, Password: {api_manager.password}")
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

                    current_app.logger.info(f"=== Fine elaborazione task per device {device.interconnection_id} ===")

        except SQLAlchemyError as e:
            current_app.logger.error(f"Errore durante la sincronizzazione dei task: {str(e)}")
        except Exception as e:
            current_app.logger.critical(f"Errore critico durante la sincronizzazione dei task: {str(e)}")
