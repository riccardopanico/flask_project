import os
from datetime import timedelta
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from app.models.log_data import LogData
from app.models.tasks import Task
from app.utils.api_oracle_manager import ApiOracleManager

JOB_INTERVAL = timedelta(seconds=15)

def run(app):
    """Invia i log pendenti, marca inviati e salva eventuali task creati."""
    with app.app_context():
        current_app.logger.info("🔁 [Job] Avvio invio log a Oracle.")
        Session = sessionmaker(bind=db.engine)
        session = Session()

        try:
            # 1) Recupera log non ancora inviati
            pending_logs = session.query(LogData).filter(LogData.sent == 0).all()
            if not pending_logs:
                current_app.logger.info("✅ Nessun log pendente.")
                return

            current_app.logger.info(f"📋 {len(pending_logs)} log da inviare.")
            payload = {'logs': []}
            # costruiamo il body JSON
            for log in pending_logs:
                payload['logs'].append({
                    "user_id":       log.user_id,
                    "device_id":     log.device.interconnection_id,
                    "variable_code": log.variable.variable_code,
                    "variable_name": log.variable.variable_name,
                    "numeric_value": log.numeric_value,
                    "boolean_value": log.boolean_value,
                    "string_value":  log.string_value,
                    "created_at":    log.created_at.strftime('%Y-%m-%dT%H:%M:%S')
                })
            current_app.logger.debug(f"📨 Payload JSON: {payload}")

            # 2) Chiamata ad Oracle
            api = ApiOracleManager()
            response = api.call(
                url='device/data',
                params=payload,
                method='POST'
            )
            current_app.logger.debug(f"📥 Risposta Oracle: {response}")

            # 3) Se ok, marca log e salva i task
            if response.get('success'):
                # 3a) aggiorna stato dei log
                for log in pending_logs:
                    log.sent = 1
                    session.add(log)

                # 3b) salva i nuovi Task restituiti
                task_ids = response.get('task_ids', [])
                task_statuses = response.get('task_statuses', [])
                current_app.logger.info(f"🔧 Task creati in Oracle: {task_ids}")

                # assumiamo che i task siano restituiti in ordine corrispondente
                idx = 0
                for log in pending_logs:
                    # solo per i log con variable_code che genera task
                    if log.variable.variable_code in ('richiesta_intervento','richiesta_filato'):
                        if idx < len(task_ids):
                            remote_id = task_ids[idx]
                            status = task_statuses[idx] if idx < len(task_statuses) else 'PENDING'
                            idx += 1

                            # crea il record locale
                            new_task = Task(
                                id=remote_id,                 # usa lo stesso ID remoto
                                device_id=log.device_id,
                                task_type=log.variable.variable_code,
                                sent=0,
                                status=status
                            )
                            session.add(new_task)
                            current_app.logger.info(
                                f"✅ Task locale creato: remote_id={remote_id}, device_id={log.device_id}, status={status}"
                            )
                # 3c) commit finale
                session.commit()
                current_app.logger.info("✅ Tutti i log inviati e task salvati.")

            else:
                # gestione elegante dell'errore in risposta
                code    = response.get('code', '')
                message = response.get('message','Errore sconosciuto')
                current_app.logger.error(f"[{code}] {message}")
                if response.get('error'):
                    current_app.logger.debug(f"Dettaglio: {response['error']}")

        except SQLAlchemyError as db_err:
            session.rollback()
            current_app.logger.error("🔥 Errore DB durante job invio log", exc_info=True)
        except Exception as e:
            session.rollback()
            current_app.logger.critical(f"🔥 Errore critico nel job: {e}", exc_info=True)
        finally:
            session.close()
