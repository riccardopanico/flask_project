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
            current_app.logger.info("Inizio sincronizzazione dispositivi.")
            Session = sessionmaker(bind=db.engine)
            session = Session()

            response = app.api_oracle_manager.call('device', method='GET')
            if not isinstance(response, dict):
                raise ValueError(f"Risposta non valida: {response}")

            if response.get('success'):
                data_records = response.get('data', [])
            else:
                raise Exception(f"Errore durante la richiesta: {response.get('error')}")

            synchronized_device_ids = []

            for record in data_records:
                record = {key.lower(): value for key, value in record.items()}
                synchronized_device_ids.append(record['device_id'])

                device = session.query(Device).filter_by(device_id=record['device_id']).first()

                # Gestione di api_manager
                api_manager = app.api_device_manager.get(record['username'])

                if not device:
                    current_app.logger.info(f"Dispositivo non trovato: {record['device_id']}. Creazione in corso...")
                    user = session.query(User).filter_by(username=record['username']).first()
                    if not user:
                        user = User(username=record['username'], user_type=record['user_type'])
                        user.set_password(record['password'])
                        user.name = record.get('name')
                        user.last_name = record.get('last_name')
                        user.email = record.get('email')
                        session.add(user)
                        session.flush()
                        current_app.logger.info(f"Utente creato: {record['username']}")

                    device = Device(user_id=user.id, device_id=record['device_id'])
                    session.add(device)
                    current_app.logger.info(f"Dispositivo creato: {record['device_id']}")

                    # Crea il ApiDeviceManager al momento della creazione
                    api_manager = ApiDeviceManager(
                        ip_address=record['ip_address'],
                        username=record['username'],
                        password=record['password']
                    )
                    app.api_device_manager[record['username']] = api_manager
                    current_app.logger.info(f"ApiDeviceManager creato per il dispositivo: {record['device_id']}")

                    # Registra il dispositivo tramite api_manager
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

                    if not api_response.get('success'):
                        current_app.logger.warning(f"Registrazione fallita per il dispositivo {record['device_id']}: {api_response.get('error')}")

                else:
                    # Aggiorna i dati del dispositivo e dell'utente associato
                    user = session.query(User).filter_by(id=device.user_id).first()
                    if user:
                        if user.username != record['username']:
                            existing_user = session.query(User).filter_by(username=record['username']).first()
                            if existing_user and existing_user.id != user.id:
                                current_app.logger.warning(f"Errore: Username '{record['username']}' già in uso.")
                                continue
                            user.username = record['username']

                        user.user_type = record.get('user_type', user.user_type)
                        if 'password' in record and record['password'] and not user.check_password(record['password']):
                            user.set_password(record['password'])
                            current_app.logger.info(f"Password aggiornata per l'utente: {user.username}")
                            if not api_manager:
                                current_app.logger.warning(f"ApiDeviceManager non trovato per {record['device_id']} ({record['username']}). Aggiornamento credenziali non possibile.")
                            else:
                                api_response = api_manager.call(
                                    'auth/update_credentials',
                                    params={
                                        'new_password': record['password'],
                                        'new_username': record['username']
                                    },
                                    method='POST'
                                )
                                if not api_response.get('success'):
                                    current_app.logger.error(f"Errore aggiornamento credenziali per {record['device_id']}: {api_response.get('error')}")

                        user.name = record.get('name', user.name)
                        user.last_name = record.get('last_name', user.last_name)
                        user.email = record.get('email', user.email)

                    # Aggiorna i dati del dispositivo
                    device.mac_address = record.get('mac_address', device.mac_address)
                    device.ip_address = record.get('ip_address', device.ip_address)
                    device.gateway = record.get('gateway', device.gateway)
                    device.subnet_mask = record.get('subnet_mask', device.subnet_mask)
                    device.dns_address = record.get('dns_address', device.dns_address)
                    device.username = record.get('username', device.username)
                    device.password = record.get('password', device.password)

                    api_manager.ip_address = device.ip_address
                    current_app.logger.info(f"Dispositivo aggiornato: {device.device_id}")

            # Rimuovi dispositivi non sincronizzati
            devices_to_remove = session.query(Device).join(User).filter(
                Device.device_id.notin_(synchronized_device_ids),
                User.user_type == 'device'
            ).all()
            for device in devices_to_remove:
                current_app.logger.info(f"Rimozione dispositivo non sincronizzato: {device.device_id}")
                if device.username in app.api_device_manager:
                    del app.api_device_manager[device.username]
                    current_app.logger.info(f"ApiDeviceManager rimosso per dispositivo: {device.device_id}")
                session.delete(device)

                user = session.query(User).filter_by(id=device.user_id, user_type='device').first()
                if user:
                    session.delete(user)
                    current_app.logger.info(f"Utente rimosso per il dispositivo: {device.device_id}")

            session.commit()
            current_app.logger.info("Sincronizzazione completata con successo.")
        except IntegrityError as e:
            session.rollback()
            current_app.logger.error(f"Errore di integrità durante la sincronizzazione: {str(e)}", exc_info=True)
        except (SQLAlchemyError, Exception) as e:
            session.rollback()
            current_app.logger.error(f"Errore durante la sincronizzazione: {str(e)}", exc_info=True)
        finally:
            session.close()
