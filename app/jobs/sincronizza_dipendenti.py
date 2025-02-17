import requests
from datetime import timedelta
from app import db
from app.models.dipendenti import Dipendente
from app.models.variables import Variables
from flask import current_app

# Intervallo di esecuzione del job
JOB_INTERVAL = timedelta(seconds=15)

def run(app):
    """Sincronizza il modello Dipendente con i dati ottenuti dall'endpoint remoto."""
    with app.app_context():
        current_app.logger.info("🔄 Avvio sincronizzazione dipendenti...")

        # Recupero delle variabili di configurazione dal database
        api_base_url = Variables.query.filter_by(variable_code='api_base_url').first()
        id_azienda = Variables.query.filter_by(variable_code='id_azienda').first()
        api_key = Variables.query.filter_by(variable_code='api_key').first()

        if not api_base_url or not id_azienda or not api_key:
            current_app.logger.error("❌ Errore: API_BASE_URL, ID_AZIENDA o API_KEY non configurati nel database.")
            return

        try:
            # Effettua la richiesta GET all'endpoint remoto
            params = {
                'id_azienda': id_azienda.get_value(),
                'api_key': api_key.get_value()
            }
            response = requests.get(f"{api_base_url.get_value()}/dipendenti", params=params, timeout=10)

            if not response.ok:
                current_app.logger.error(f"❌ Errore HTTP {response.status_code}: {response.text}")
                return

            response_json = response.json()
            success = response_json.get('success', False)
            dipendenti_data = response_json.get('data', [])

            if not success:
                current_app.logger.error(f"❌ Errore API: {response_json.get('message', 'Nessun messaggio ricevuto')}")
                return

            if not dipendenti_data:
                current_app.logger.info("ℹ️ Nessun dipendente da sincronizzare.")
                return

            # Filtra i dati per evitare errori nel database (scarta record senza badge)
            dipendenti_validi = [
                d for d in dipendenti_data if 'ID' in d and 'NOME' in d and 'COGNOME' in d and 'BADGE' in d and d['BADGE']
            ]
            dipendenti_scartati = [
                d for d in dipendenti_data if 'BADGE' not in d or not d['BADGE']
            ]

            if dipendenti_scartati:
                current_app.logger.warning(f"⚠️ {len(dipendenti_scartati)} dipendenti scartati per mancanza del badge: {dipendenti_scartati}")

            # Ottieni gli ID attualmente presenti nel database locale
            dipendenti_esistenti = {d.id: d for d in Dipendente.query.all()}

            nuovi_dipendenti = []
            dipendenti_aggiornati = []
            ids_dipendenti_attivi = set()

            for dipendente in dipendenti_validi:
                dipendente_id = dipendente.get('ID')
                nome = dipendente.get('NOME')
                cognome = dipendente.get('COGNOME')
                badge = dipendente.get('BADGE')

                ids_dipendenti_attivi.add(dipendente_id)  # Salva gli ID attuali per confronto

                if dipendente_id in dipendenti_esistenti:
                    dipendente_esistente = dipendenti_esistenti[dipendente_id]
                    if (dipendente_esistente.nome != nome or
                        dipendente_esistente.cognome != cognome or
                        dipendente_esistente.badge != badge):
                        dipendenti_aggiornati.append({
                            'id': dipendente_id,
                            'nome': nome,
                            'cognome': cognome,
                            'badge': badge
                        })
                else:
                    nuovi_dipendenti.append({
                        'id': dipendente_id,
                        'nome': nome,
                        'cognome': cognome,
                        'badge': badge
                    })

            # Identifica dipendenti da eliminare (non più presenti nell'endpoint)
            dipendenti_da_eliminare = [
                dipendente
                for dipendente in dipendenti_esistenti.values()
                if dipendente.id not in ids_dipendenti_attivi
            ]

            # Aggiornamenti in batch
            try:
                if dipendenti_aggiornati:
                    db.session.bulk_update_mappings(Dipendente, dipendenti_aggiornati)
                    current_app.logger.info(f"✅ {len(dipendenti_aggiornati)} dipendenti aggiornati.")

                if nuovi_dipendenti:
                    db.session.bulk_insert_mappings(Dipendente, nuovi_dipendenti)
                    current_app.logger.info(f"✅ {len(nuovi_dipendenti)} nuovi dipendenti inseriti.")

                if dipendenti_da_eliminare:
                    for dip in dipendenti_da_eliminare:
                        db.session.delete(dip)
                    current_app.logger.info(f"❌ {len(dipendenti_da_eliminare)} dipendenti eliminati.")

                if dipendenti_aggiornati or nuovi_dipendenti or dipendenti_da_eliminare:
                    db.session.commit()
                    current_app.logger.info("✅ Sincronizzazione dipendenti completata con successo.")

            except Exception as db_error:
                db.session.rollback()
                current_app.logger.error(f"❌ Errore nel commit DB: {str(db_error)}")

        except Exception as e:
            current_app.logger.error(f"❌ Errore generico: {str(e)}")
