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
                print("Sincronizzazione dei task non inviati al data center in corso...")

            Session = sessionmaker(bind=db.engine)
            session = Session()

            unsent_tasks = session.query(Task).filter(Task.sent_to_cloud == 0).all()
            if not unsent_tasks:
                if current_app.debug:
                    print("Nessun task da sincronizzare con il data center.")
                return

            task_data = [task.to_dict() for task in unsent_tasks]

            response = app.api_oracle_manager.call('/task', params={'tasks': task_data}, method='POST')

            if response['success']:
                task_ids = [task.id for task in unsent_tasks]
                session.query(Task).filter(Task.id.in_(task_ids)).update({Task.sent_to_cloud: 1}, synchronize_session=False)
                session.commit()
                if current_app.debug:
                    print("I task sono stati inviati e aggiornati con successo nel data center.")
            else:
                if current_app.debug:
                    print(f"Errore durante la sincronizzazione dei task: {response['error']}")

        except SQLAlchemyError as e:
            session.rollback()
            if current_app.debug:
                print(f"Errore durante la sincronizzazione dei task: {str(e)}")
        finally:
            session.close()
