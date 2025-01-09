import os
import requests
from flask import current_app
from app import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import sessionmaker
from datetime import timedelta
from app.models.user import User
from app.models.device import Device
from app.utils.api_device_manager import ApiDeviceManager

JOB_INTERVAL = timedelta(seconds=5)

def run(app):
    with app.app_context():
        try:
            if current_app.debug:
                current_app.logger.debug("Sincronizzazione dei dispositivi in corso...")
            Session = sessionmaker(bind=db.engine)
            session = Session()

            response = app.api_oracle_manager.call('device', method='GET')
            if not isinstance(response, dict):
                raise ValueError(f"Risposta non valida: {response}")

            if response.get('success'):
                data_records = response.get('data', [])
            else:
                raise Exception(f"Errore durante la richiesta: {response.get('error')}")

            # Lista per tracciare gli ID dei dispositivi sincronizzati
            synchronized_device_ids = []

            for record in data_records:
                # Converti tutte le chiavi del record in minuscolo
                record = {key.lower(): value for key, value in record.items()}

                # Aggiungi il device_id alla lista dei dispositivi sincronizzati
                synchronized_device_ids.append(record['device_id'])

                # Sincronizza il dispositivo basato sul device_id
                device = session.query(Device).filter_by(device_id=record['device_id']).first()

                # Ottieni l'API manager associato al dispositivo
                api_manager = app.api_device_manager.get(record['username'])
                if api_manager:
                    api_manager.ip_address = device.ip_address
                    api_manager.username = device.username
                    api_manager.password = device.password
                else:
                    current_app.logger.info(f"Device manager non trovato per il dispositivo {device.username}. Creazione in corso...")
                    api_manager = ApiDeviceManager(
                        ip_address=device.ip_address,
                        username=device.username,
                        password=device.password
                    )
                    app.api_device_manager[device.username] = api_manager

                if not device:
                    # Crea un nuovo dispositivo e utente associato
                    user = session.query(User).filter_by(username=record['username']).first()
                    if not user:
                        user = User(username=record['username'], user_type=record['user_type'])
                        user.set_password(record['password'])
                        user.name = record.get('name')
                        user.last_name = record.get('last_name')
                        user.email = record.get('email')
                        session.add(user)
                        session.flush()  # Ottiene l'ID del nuovo utente senza effettuare il commit
                        current_app.logger.debug(f"Creato nuovo utente: {record['username']}")

                    device = Device(user_id=user.id, device_id=record['device_id'])
                    session.add(device)
                    current_app.logger.debug(f"Creato nuovo dispositivo associato all'utente: {record['username']} con ID dispositivo: {record['device_id']}")

                    api_response = api_manager.call(
                        'auth/register',
                        params={
                            'username': record['username'],
                            'password': record['password'],
                            'user_type': record['user_type'],
                            'device_id': record['device_id'],
                            'ip_address': record['ip_address']
                        },
                        method='POST'
                    )

                    if api_response.get('success'):
                        if current_app.debug:
                            current_app.logger.debug(f"Aggiornamento delle credenziali per il dispositivo {device.username} avvenuto con successo.")
                    else:
                        current_app.logger.warning(f"Aggiornamento delle credenziali per il dispositivo {device.username} fallito: {api_response.get('error')}")

                else:
                    # Aggiorna i dati del dispositivo e dell'utente associato
                    user = session.query(User).filter_by(id=device.user_id).first()
                    if user:
                        if user.username != record['username']:
                            existing_user = session.query(User).filter_by(username=record['username']).first()
                            if existing_user and existing_user.id != user.id:
                                if current_app.debug:
                                    current_app.logger.warning(f"Errore: L'username '{record['username']}' è già in uso da un altro utente.")
                                continue
                            user.username = record['username']
                        user.user_type = record.get('user_type', user.user_type)
                        if 'password' in record and record['password']:
                            if user.password_hash is None or not user.check_password(record['password']):
                                user.set_password(record['password'])

                                api_response = api_manager.call(
                                    'auth/update_credentials',
                                    params={'new_password': record['password'], 'new_username': record['username']},
                                    method='POST'
                                )
                                if api_response.get('success'):
                                    if current_app.debug:
                                        current_app.logger.info(f"Password aggiornata correttamente per dispositivo: {record['device_id']}")
                                else:
                                    if current_app.debug:
                                        current_app.logger.error(f"Errore durante l'aggiornamento della password per dispositivo {record['device_id']}: {api_response.get('error')}")

                        user.name = record.get('name', user.name)
                        user.last_name = record.get('last_name', user.last_name)
                        user.email = record.get('email', user.email)
                        if current_app.debug:
                            current_app.logger.debug(f"Dati utente aggiornati: {record['username']}")

                # Aggiorna i dati del dispositivo se necessario
                device.mac_address = record.get('mac_address', device.mac_address)
                device.ip_address = record.get('ip_address', device.ip_address)
                device.gateway = record.get('gateway', device.gateway)
                device.subnet_mask = record.get('subnet_mask', device.subnet_mask)
                device.dns_address = record.get('dns_address', device.dns_address)
                device.username = record.get('username', device.username)
                device.password = record.get('password', device.password)

                current_app.logger.debug(f"Dati dispositivo aggiornati per ID dispositivo: {record['device_id']}")

            # Rimuovi i dispositivi e utenti di tipo "device" non sincronizzati
            devices_to_remove = session.query(Device).join(User).filter(
                Device.device_id.notin_(synchronized_device_ids),
                User.user_type == 'device'
            ).all()
            for device in devices_to_remove:
                if current_app.debug:
                    current_app.logger.debug(f"Rimozione dispositivo non sincronizzato: {device.device_id}")
                # Rimuovi il manager API associato, se presente
                if device.username in app.api_device_manager:
                    del app.api_device_manager[device.username]
                    if current_app.debug:
                        current_app.logger.debug(f"Rimosso ApiDeviceManager per dispositivo: {device.device_id}")
                # Rimuovi il dispositivo
                session.delete(device)

                # Rimuovi l'utente associato, se di tipo "device"
                user = session.query(User).filter_by(id=device.user_id, user_type='device').first()
                if user:
                    session.delete(user)
                    if current_app.debug:
                        current_app.logger.debug(f"Rimosso utente associato al dispositivo: {device.device_id}")

            session.commit()
            if current_app.debug:
                current_app.logger.info("Sincronizzazione dei record completata con successo.")
        except IntegrityError as e:
            session.rollback()
            if current_app.debug:
                current_app.logger.error(f"Errore di integrità durante la sincronizzazione dei record: {str(e)}")
        except (SQLAlchemyError, Exception) as e:
            session.rollback()
            if current_app.debug:
                current_app.logger.error(f"Errore durante la sincronizzazione dei record: {str(e)}")
        finally:
            session.close()
