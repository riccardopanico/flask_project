import os
from datetime import timedelta
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from app.models.tasks import Task

JOB_INTERVAL = timedelta(minutes=5)

def run(app):
    with app.app_context():
        current_app.logger.info("🔁 [Job] Avvio controllo stato interventi in sospeso.")
        Session = sessionmaker(bind=db.engine)
        session = Session()

        try:
            current_app.logger.debug("🔍 Query: recupero task PENDING dal DB...")
            pending = session.query(Task).filter(Task.status == 'PENDING').all()

            if not pending:
                current_app.logger.info("✅ Nessun task in stato PENDING trovato.")
                return

            current_app.logger.info(f"📋 Trovati {len(pending)} task PENDING.")
            task_ids = [str(t.id) for t in pending]
            ids_csv = ','.join(task_ids)
            current_app.logger.debug(f"🔗 Lista task da inviare: {ids_csv}")

            # --- Chiamata all’API ORDS ---
            current_app.logger.debug("🌐 Invio richiesta POST a ORDS (form-urlencoded)...")
            response = app.api_oracle_manager.call(
                'task/status',
                method='POST',
                params={'task_ids': ids_csv}
            )
            current_app.logger.debug(f"📨 Risposta ricevuta da ORDS: {response}")

            if not isinstance(response, dict):
                current_app.logger.error(f"❌ Risposta non JSON: {response}")
                return

            items = response.get('items')
            if not isinstance(items, list):
                current_app.logger.error(f"❌ 'items' non è una lista valida: {items}")
                return

            current_app.logger.info(f"📦 Ricevuti {len(items)} task da aggiornare.")
            # --- Loop aggiornamento task ---
            for entry in items:
                current_app.logger.debug(f"➡️ Processing entry: {entry}")
                tid = entry.get('task_id')
                st  = entry.get('task_state')

                if not tid or not st:
                    current_app.logger.warning(f"⚠️ Entry incompleta: {entry}")
                    continue

                current_app.logger.debug(f"🔄 Cerco task con ID {tid} nel DB...")
                task = session.get(Task, tid)
                if not task:
                    current_app.logger.warning(f"⚠️ Nessun task trovato con ID {tid}.")
                    continue

                current_app.logger.info(f"✅ Task {tid} aggiornato da '{task.status}' a '{st}'")
                task.status = st
                session.add(task)

            current_app.logger.debug("💾 Commit delle modifiche al DB...")
            session.commit()
            current_app.logger.info("✅ Controllo completato con successo.")

        except Exception as e:
            current_app.logger.error(f"🔥 Errore critico nel job: {e}")
            session.rollback()
        finally:
            current_app.logger.debug("🔚 Chiusura sessione DB.")
            session.close()
