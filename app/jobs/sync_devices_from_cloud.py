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

JOB_INTERVAL = timedelta(seconds=8)

def initialize_api_manager(app, device, record):
    with app.app_context():
        old_username = device.username if device else None
        api_manager = app.api_device_manager.get(old_username)

        if device is None:
            current_app.logger.info(f"Creazione di un nuovo ApiDeviceManager per il dispositivo: {record['interconnection_id']}")
            api_manager = ApiDeviceManager(
                ip_address=record['ip_address'],
                username=record['username'],
                password=record['password']
            )
            app.api_device_manager[record['username']] = api_manager

        elif api_manager is not None and api_manager.username == record['username']:
            current_app.logger.info(f"Utilizzo dell'ApiDeviceManager esistente per il dispositivo: {record['interconnection_id']}")

        elif api_manager is not None and api_manager.username != record['username']:
            current_app.logger.info(f"ApiDeviceManager con username cambiato: {record['interconnection_id']}")
            current_app.logger.info(f"Usando vecchie credenziali per aggiornare il dispositivo: {device.interconnection_id}")

        elif api_manager is None:
            current_app.logger.info(f"Creazione di un nuovo ApiDeviceManager per il dispositivo: {record['interconnection_id']}. Il manager non esisteva.")
            api_manager = ApiDeviceManager(
                ip_address=record.get('ip_address', device.ip_address if device else None),
                username=record.get('username', device.username if device else None),
                password=record.get('password', device.password if device else None)
            )
            app.api_device_manager[record['username']] = api_manager
        else:
            current_app.logger.info(f"(Anomalia) Dispositivo con api_manager Non Trovato per il dispositivo: {record['interconnection_id']}")

        return api_manager

def run(app):
    with app.app_context():
        try:
            current_app.logger.info("Inizio sincronizzazione dispositivi.")
            Session = sessionmaker(bind=db.engine)
            session = Session()

            # Chiamata all'API per ottenere i dispositivi
            response = app.api_oracle_manager.call('device', method='GET')
            if not isinstance(response, dict):
                raise ValueError(f"Risposta non valida: {response}")

            if response.get('success'):
                data_records = response.get('data', [])
            else:
                raise Exception(f"Errore durante la richiesta: {response.get('error')}")

            synchronized_interconnection_ids = []

            for record in data_records:
                record = {key.lower(): value for key, value in record.items()}
                synchronized_interconnection_ids.append(record['interconnection_id'])

                # Recupera o inizializza il dispositivo
                device = session.query(Device).filter_by(interconnection_id=record['interconnection_id']).first()
                old_username = device.username if device else None  # Memorizza il vecchio username
                api_manager = initialize_api_manager(app, device, record)

                if not device:
                    current_app.logger.info(f"Dispositivo non trovato: {record['interconnection_id']}. Creazione in corso...")

                    # Creazione di un nuovo utente
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

                    # Creazione di un nuovo dispositivo
                    device = Device(user_id=user.id, interconnection_id=record['interconnection_id'], ip_address=record['ip_address'])
                    session.add(device)
                    current_app.logger.info(f"Dispositivo creato: {record['interconnection_id']}")

                    # Registra il dispositivo tramite api_manager
                    try:
                        api_response = api_manager.call(
                            'auth/register',
                            params={
                                'user': {
                                    'username': record['username'],
                                    'password': record['password'],
                                    'user_type': 'datacenter'
                                },
                                'device': {
                                    'interconnection_id': record['interconnection_id'],
                                    'mac_address': record.get('mac_address'),
                                    'ip_address': record['ip_address'],
                                    'gateway': record.get('gateway'),
                                    'subnet_mask': record.get('subnet_mask'),
                                    'dns_address': record.get('dns_address'),
                                    'port_address': record.get('port_address'),
                                    'username': record['username'],
                                    'password': record['password']
                                }
                            },
                            method='POST',
                            requires_auth=False
                        )
                    except Exception as e:
                        current_app.logger.warning(f"Errore durante la registrazione del dispositivo {record['interconnection_id']}: {e}")

                    if not api_response.get('success'):
                        current_app.logger.warning(f"Registrazione fallita per il dispositivo {record['interconnection_id']}: {api_response.get('error')}")

                else:
                    # Aggiorna l'utente associato al dispositivo
                    user = session.query(User).filter_by(id=device.user_id).first()
                    if user:
                        if user.username != record['username']:
                            existing_user = session.query(User).filter_by(username=record['username']).first()
                            if existing_user and existing_user.id != user.id:
                                current_app.logger.warning(f"Errore: Username '{record['username']}' già in uso.")
                                continue
                            user.username = record['username']

                        user.user_type = record.get('user_type', user.user_type)
                        if record['password'] and not user.check_password(record['password']) or old_username != record['username']:
                            current_app.logger.info(f"Aggiornamento delle credenziali per l'utente: {user.username}")
                            try:
                                api_response = api_manager.call(
                                    'auth/update_credentials',
                                    params={
                                        'new_password': record['password'],
                                        'new_username': record['username']
                                    },
                                    method='POST'
                                )
                            except Exception as e:
                                current_app.logger.warning(f"Errore durante l'aggiornamento delle credenziali per l'utente: {user.username}: {e}")

                            if api_response.get('success'):
                                user.set_password(record['password'])
                                user.username = record['username']

                                api_manager.username = record['username']
                                api_manager.password = record['password']

                                if old_username != record['username'] and old_username in app.api_device_manager:
                                    del app.api_device_manager[old_username]
                                    app.api_device_manager[record['username']] = api_manager
                                    current_app.logger.info(f"Rimosso ApiDeviceManager per il vecchio username: {old_username} e aggiunto per il nuovo username: {record['username']}")
                                current_app.logger.info(f"ApiDeviceManager e utente aggiornati per il dispositivo: {device.interconnection_id}")
                            else:
                                current_app.logger.warning(f"Errore durante l'aggiornamento delle credenziali per l'utente: {user.username}")

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
                    current_app.logger.info(f"Dispositivo aggiornato: {device.interconnection_id}")

            # Rimuovi dispositivi non sincronizzati
            devices_to_remove = session.query(Device).join(User).filter(
                Device.interconnection_id.notin_(synchronized_interconnection_ids),
                User.user_type == 'device'
            ).all()
            for device in devices_to_remove:
                current_app.logger.info(f"Rimozione dispositivo non sincronizzato: {device.interconnection_id}")
                if device.username in app.api_device_manager:
                    del app.api_device_manager[device.username]
                    current_app.logger.info(f"ApiDeviceManager rimosso per dispositivo: {device.interconnection_id}")
                session.delete(device)

                user = session.query(User).filter_by(id=device.user_id, user_type='device').first()
                if user:
                    session.delete(user)
                    current_app.logger.info(f"Utente rimosso per il dispositivo: {device.interconnection_id}")

            session.commit()
            current_app.logger.info("Sincronizzazione completata con successo.")
        except IntegrityError as e:
            session.rollback()
            current_app.logger.error(f"Errore di integrità durante la sincronizzazione: {e}", exc_info=True)
        except (SQLAlchemyError, Exception) as e:
            session.rollback()
            current_app.logger.error(f"Errore durante la sincronizzazione: {e}", exc_info=True)
        finally:
            session.close()
