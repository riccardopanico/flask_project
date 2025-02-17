import requests
from datetime import timedelta
from app import db
from app.models.log_data import LogData
from app.models.variables import Variables
from flask import current_app

# Definizione dell'intervallo di esecuzione del job
JOB_INTERVAL = timedelta(seconds=15)  # Personalizzabile a seconda delle esigenze

def run(app):
    """Sincronizza le presenze registrate in LogData con il server remoto."""
    with app.app_context():
        current_app.logger.info("Avvio sincronizzazione presenze...")

        # Recupero delle variabili necessarie dal database
        api_base_url = Variables.query.filter_by(variable_code='api_base_url').first()
        id_azienda = Variables.query.filter_by(variable_code='id_azienda').first()
        api_key = Variables.query.filter_by(variable_code='api_key').first()
        badge_variable = Variables.query.filter_by(variable_code='badge').first()

        if not api_base_url or not id_azienda or not api_key:
            current_app.logger.error("Errore: API_BASE_URL, ID_AZIENDA o API_KEY non configurati nel database.")
            return

        try:
            # Recupera le timbrature non ancora inviate
            timbrature = LogData.query.filter_by(sent=0, variable_id=badge_variable.id).all()

            if not timbrature:
                current_app.logger.info("Nessuna timbratura da sincronizzare.")
                return

            for timbratura in timbrature:
                headers = {
                    'data_ora': timbratura.created_at.strftime('%Y-%m-%d %H:%M'),
                    'badge': timbratura.get_value(),
                    'id_azienda': id_azienda.get_value(),
                    'api_key': api_key.get_value()
                }

                response = requests.post(f"{api_base_url.get_value()}/registro_presenze", json=headers)

                if response.ok:
                    try:
                        response_json = response.json()  # Converti la risposta in JSON
                        success = response_json.get('success', False)
                        message = response_json.get('message', 'Nessun messaggio ricevuto')

                        if success:
                            # Se la richiesta ha successo, aggiorna il record come inviato
                            timbratura.sent = 1
                            db.session.commit()  # Commit solo se l'API ha risposto con successo
                            current_app.logger.info(f"Timbratura ID {timbratura.id} inviata con successo. Messaggio: {message}")
                        else:
                            # Se success è False, logga l'errore specifico senza fare commit
                            current_app.logger.error(f"Errore API per timbratura ID {timbratura.id}: {message}")

                    except Exception as json_error:
                        current_app.logger.error(f"Errore nella decodifica JSON per timbratura ID {timbratura.id}: {str(json_error)}")

                else:
                    # Log degli errori HTTP senza interrompere il processo
                    current_app.logger.error(
                        f"Errore HTTP nell'invio della timbratura ID {timbratura.id}: "
                        f"{response.status_code} - {response.text}"
                    )

        except Exception as e:
            current_app.logger.error(f"Errore durante la sincronizzazione: {str(e)}")
