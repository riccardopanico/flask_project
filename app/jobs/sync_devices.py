import os
import time
import requests
from flask import current_app
from app import db
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app.models.user import User
from app.models.device import Device

__ACTIVE__ = True

def fetch_data():
    API_BASE_URL = os.getenv('TAP_IN_RESTART_API_BASE_URL')
    if not API_BASE_URL:
        raise ValueError("TAP_IN_RESTART_API_BASE_URL non è impostata nella configurazione dell'applicazione")
    API_ENDPOINT = f"{API_BASE_URL}/device"
    response = requests.get(API_ENDPOINT)
    if response.status_code == 200:
        return response.json().get('data', [])
    else:
        raise Exception(f"Errore durante la richiesta: {response.status_code}")

def run(app):
    SLEEP_TIME = 10
    with app.app_context():
        while True:
            try:
                Session = sessionmaker(bind=db.engine)
                session = Session()
                data_records = fetch_data()

                for record in data_records:
                    # Validazione delle chiavi necessarie per l'utente
                    required_keys_user = ['username', 'password', 'user_type']
                    for key in required_keys_user:
                        if key not in record:
                            print(f"Chiave mancante: {key} nel record: {record}")
                            continue

                    # Controlla se l'utente esiste già
                    if session.query(User).filter_by(username=record['username']).first():
                        print(f"L'utente {record['username']} esiste già.")
                        continue

                    # Crea un nuovo utente
                    new_user = User(username=record['username'], user_type=record['user_type'])
                    new_user.set_password(record['password'])
                    new_user.name = record.get('name')
                    new_user.last_name = record.get('last_name')
                    new_user.email = record.get('email')
                    session.add(new_user)
                    session.flush()  # Ottiene l'ID del nuovo utente senza effettuare il commit

                    # Se l'utente è un dispositivo, crea anche il dispositivo associato
                    if record['user_type'] == 'device':
                        required_keys_device = ['device_id', 'ip_address', 'mac_address']
                        for key in required_keys_device:
                            if key not in record:
                                print(f"Chiave mancante per il dispositivo: {key} nel record: {record}")
                                continue

                        new_device = Device(
                            user_id=new_user.id,
                            device_id=record['device_id'],
                            mac_address=record['mac_address'],
                            ip_address=record['ip_address'],
                            gateway=record.get('gateway'),
                            subnet_mask=record.get('subnet_mask'),
                            dns_address=record.get('dns_address')
                        )
                        session.add(new_device)

                # Commit delle modifiche
                session.commit()
                print("Inserimento dei record completato con successo.")

                # Attendi prima di ripetere il processo
                time.sleep(SLEEP_TIME)

            except (SQLAlchemyError, Exception) as e:
                session.rollback()
                print(f"Errore durante l'inserimento dei record: {str(e)}")
                time.sleep(SLEEP_TIME)
            finally:
                # Chiudi la sessione per garantire che le modifiche vengano viste
                session.close()
