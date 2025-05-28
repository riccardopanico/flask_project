import os
from datetime import timedelta
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from app.models.tasks import Task

JOB_INTERVAL = timedelta(seconds=5)

def run(app):
    with app.app_context():
        current_app.logger.info("🔁 [Job] Avvio controllo stato interventi in sospeso.")
        Session = sessionmaker(bind=db.engine)
        session = Session()

        try:
            # 1) Prendo i task PENDING
            pending = session.query(Task).filter(Task.status == 'PENDING').all()
            if not pending:
                current_app.logger.info("✅ Nessun task PENDING da aggiornare.")
                return

            task_ids = [t.id for t in pending]
            current_app.logger.info(f"📋 Task da verificare: {task_ids}")

            # 2) Chiamata JSON‐POST (ORDS attende JSON body)
            response = app.api_oracle_manager.call(
                'task/status',
                method='POST',
                params={'task_ids': task_ids}
            )
            current_app.logger.debug(f"📨 Risposta ORDS: {response}")

            # 3) Controllo risposta valida
            if not isinstance(response, dict):
                current_app.logger.error(f"❌ Risposta non valida: {response}")
                return
            items = response.get('items', [])
            if not isinstance(items, list):
                current_app.logger.error(f"❌ Campo 'items' mancante o non list: {response}")
                return

            # 4) Aggiorno localmente
            for entry in items:
                tid = entry.get('task_id')
                st  = entry.get('task_state')
                if tid is None or st is None:
                    current_app.logger.warning(f"⚠️ Entry incompleta: {entry}")
                    continue

                task = session.get(Task, tid)
                if not task:
                    current_app.logger.warning(f"⚠️ Task locale non trovato: {tid}")
                    continue

                current_app.logger.info(f"✅ Task {tid}: '{task.status}' → '{st}'")
                task.status = st

            session.commit()
            current_app.logger.info("✅ Tutti i task aggiornati con successo.")

        except Exception as e:
            session.rollback()
            current_app.logger.error(f"🔥 Errore critico nel job: {e}")
        finally:
            session.close()
