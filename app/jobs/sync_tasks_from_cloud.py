import os
from datetime import timedelta
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from app.models.tasks import Task 

# Intervallo di esecuzione del job (es. ogni 5 minuti)
JOB_INTERVAL = timedelta(seconds=5)

def run(app):
    with app.app_context():
        current_app.logger.info("Inizio controllo stato interventi in sospeso.")
        Session = sessionmaker(bind=db.engine)
        session = Session()

        try:
            # 1) Recupera tutti i task locali in stato PENDING
            pending_tasks = session.query(Task).filter(Task.status == 'PENDING').all()
            if not pending_tasks:
                current_app.logger.info("Nessun intervento in stato PENDING da controllare.")
                return

            task_ids = [t.id for t in pending_tasks]
            current_app.logger.debug(f"Task locali da verificare: {task_ids}")

            # 2) Chiamata all’endpoint ORDS via api_oracle_manager
            try:
                response = app.api_oracle_manager.call(
                    'task/status',
                    method='POST',
                    params={'task_ids': task_ids}
                )
            except Exception as e:
                current_app.logger.error(f"Errore chiamata ORDS /task/status: {e}")
                return

            # L’endpoint restituisce i risultati nel campo “items”
            items = response.get('items')
            current_app.logger.debug(items)
            if not isinstance(items, list):
                current_app.logger.error(f"Risposta inattesa da ORDS: {response}")
                return

            # 3) Per ogni task aggiornalo localmente
            for entry in items:
                tid       = entry.get('task_id')
                new_state = entry.get('task_state')
                if tid is None or new_state is None:
                    current_app.logger.warning(f"Voce incompleta in risposta ORDS: {entry}")
                    continue

                try:
                    task = session.query(Task).get(tid)
                    if not task:
                        current_app.logger.warning(f"Task locale non trovato: {tid}")
                        continue

                    task.status = new_state
                    session.add(task)
                    current_app.logger.info(f"Task {tid} aggiornato a '{new_state}'.")
                except SQLAlchemyError as err:
                    current_app.logger.error(f"Errore aggiornamento task {tid}: {err}")
                    session.rollback()  # rollback solo per questo update

            session.commit()
            current_app.logger.info("Controllo stato interventi completato con successo.")

        except Exception as critical:
            session.rollback()
            current_app.logger.error(f"Errore critico durante il controllo interventi: {critical}")

        finally:
            session.close()
