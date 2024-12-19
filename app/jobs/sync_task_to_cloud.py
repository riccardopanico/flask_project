from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from datetime import timedelta
from app.models.tasks import Task
from app.utils.api_oracle_manager import ApiOracleManager
import os

JOB_INTERVAL = timedelta(seconds=5)
api_oracle_manager = ApiOracleManager()

def send_task(params):
    API_BASE_URL = os.getenv('API_ORACLE_BASE_URL')
    if not API_BASE_URL:
        raise ValueError("API_ORACLE_BASE_URL non è impostata nella configurazione dell'applicazione")
    
    API_ENDPOINT = f"{API_BASE_URL}/task"   
    response = api_oracle_manager.call(API_ENDPOINT, params=params, method='POST')
    # print(f"Response: {response}")
    if response.get('success'):
        print(f"Received data: {response.get('data')}")
        return response.get('data', [])
    else:
        raise Exception(f"Errore durante la richiesta: {response.status_code}")

def run(app):
    with app.app_context():
        try:
            if current_app.debug:
                print("Sincronizzazione dei task in corso...")
            Session = sessionmaker(bind=db.engine)
            session = Session()
            # api_manager = app.api_manager

            # unsent_tasks = session.query(Task).filter(Task.sent == 0).all()
            # if not unsent_tasks:
            #     if current_app.debug:
            #         print("Nessun task da sincronizzare.")
            #     return

            # task_data = [task.to_dict() for task in unsent_tasks]
            # response = api_manager.call_external_api('/task/create', params={'tasks': task_data}, method='POST')
            # Definizione dei parametri da inviare (presi dall'immagine)
            params = {
                'id_fornitore': 1,
                'tipo': 1,
                'descr': 'aaaaaaaaaaaaaaaaaaaa aaaaaaaa',
                'contratto': 2,
                'state_code': 21,
                'motivo': 'test insert interventi motivo',
                'id_cespite': 1
            }
            response = send_task(params)
            print(f"Response: {response.json()}")
            if response['success']:
                task_ids = [task.id for task in unsent_tasks]
                session.query(Task).filter(Task.id.in_(task_ids)).update({Task.sent: 1}, synchronize_session=False)
                session.commit()
                if current_app.debug:
                    print("I task sono stati inviati e aggiornati con successo.")
            else:
                if current_app.debug:
                    print(f"Errore durante la sincronizzazione dei task: {response['error']}")
        except SQLAlchemyError as e:
            session.rollback()
            if current_app.debug:
                print(f"Errore durante la sincronizzazione dei task: {str(e)}")
        finally:
            session.close()
