import os
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
    with app.app_context():
        try:
            Session = sessionmaker(bind=db.engine)
            session = Session()
            data_records = fetch_data()

            for record in data_records:
                # Converti tutte le chiavi del record in minuscolo
                record = {key.lower(): value for key, value in record.items()}

                # Trova o crea l'utente
                user = session.query(User).filter_by(username=record['username']).first()
                if not user:
                    user = User(username=record['username'], user_type=record['user_type'])
                    session.add(user)
                    print(f"Creato nuovo utente: {record['username']}")

                # Aggiorna i dati dell'utente se necessario
                user.user_type = record.get('user_type', user.user_type)
                user.set_password(record['password'])
                user.name = record.get('name', user.name)
                user.last_name = record.get('last_name', user.last_name)
                user.email = record.get('email', user.email)
                print(f"Dati utente aggiornati: {record['username']}")
                session.flush()  # Ottiene l'ID del nuovo utente senza effettuare il commit

                # Sincronizza il dispositivo se l'utente è di tipo 'device'
                if record['user_type'] == 'device':
                    device = session.query(Device).filter_by(device_id=record['device_id']).first()
                    if not device:
                        device = Device(user_id=user.id, device_id=record['device_id'])
                        session.add(device)
                        print(f"Creato nuovo dispositivo per utente: {record['username']} con ID dispositivo: {record['device_id']}")

                    # Aggiorna i dati del dispositivo se necessario
                    device.mac_address = record.get('mac_address', device.mac_address)
                    device.ip_address = record.get('ip_address', device.ip_address)
                    device.gateway = record.get('gateway', device.gateway)
                    device.subnet_mask = record.get('subnet_mask', device.subnet_mask)
                    device.dns_address = record.get('dns_address', device.dns_address)
                    print(f"Dati dispositivo aggiornati per ID dispositivo: {record['device_id']}")

            session.commit()
            print("Sincronizzazione dei record completata con successo.")
        except (SQLAlchemyError, Exception) as e:
            session.rollback()
            print(f"Errore durante la sincronizzazione dei record: {str(e)}")
        finally:
            session.close()
