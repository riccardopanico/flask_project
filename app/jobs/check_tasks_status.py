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

            response = app.api_oracle_manager.call('/task', method='POST')

            if response['success']:
                ##
                session.commit()
                if current_app.debug:
                    print("asdasdasdasdasd")
            else:
                if current_app.debug:
                    print(f"Errore durante la sincronizzazione dei task: {response['error']}")

        except SQLAlchemyError as e:
            session.rollback()
            if current_app.debug:
                print(f"Errore durante la sincronizzazione dei task: {str(e)}")
        finally:
            session.close()
