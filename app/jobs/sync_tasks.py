import os
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from app.models.tasks import Task
from app.utils.api_auth_manager import ApiAuthManager

def run(app):
    with app.app_context():
        Session = sessionmaker(bind=db.engine)
        session = Session()
        api_manager = ApiAuthManager()

        try:
            # Recupera i task con la colonna "sent" impostata a 0
            unsent_tasks = session.query(Task).filter(Task.sent == 0).all()
            if not unsent_tasks:
                print("Nessun task da sincronizzare.")
                return

            # Converti i task in un formato serializzabile in JSON
            task_data = [task.to_dict() for task in unsent_tasks]

            # Invia i task all'API
            response = api_manager.call_external_api('/task', params=task_data, method='POST')

            if response['success']:
                # Ottieni tutti gli ID dei task che sono stati inviati
                task_ids = [task.id for task in unsent_tasks]
                # Aggiorna tutti i task come inviati in un'unica operazione
                session.query(Task).filter(Task.id.in_(task_ids)).update({Task.sent: 1}, synchronize_session=False)
                session.commit()
                print("I task sono stati inviati e aggiornati con successo.")
            else:
                print(f"Errore durante la sincronizzazione dei task: {response['error']}")
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Errore durante la sincronizzazione dei task: {str(e)}")
        finally:
            session.close()
