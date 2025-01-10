from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from app import db
from app.models.user import User
from app.models.device import Device
from app.models.variables import Variables
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

auth_blueprint = Blueprint('auth', __name__)

@auth_blueprint.route('/register', methods=['POST'])
def register():
    Session = sessionmaker(bind=db.engine)
    with Session() as session:
        try:
            current_app.logger.info("Inizio registrazione utente.")
            data = request.get_json()

            # Valida i campi richiesti per la registrazione dell'utente
            required_user_fields = ['username', 'password', 'user_type']
            missing_fields = [key for key in required_user_fields if key not in data]
            if missing_fields:
                current_app.logger.warning(f"Campi mancanti: {missing_fields}")
                return jsonify({"success": False, "message": f"Campi mancanti: {', '.join(missing_fields)}"}), 400

            # Controlla se il nome utente esiste già
            if session.query(User).filter_by(username=data['username']).first():
                current_app.logger.warning("Il nome utente esiste già.")
                return jsonify({"success": False, "message": "L'utente esiste già."}), 400

            # Valida i campi aggiuntivi se user_type è 'device'
            if data['user_type'] == 'device':
                required_device_fields = ['device_id', 'ip_address']
                missing_device_fields = [key for key in required_device_fields if key not in data]
                if missing_device_fields:
                    current_app.logger.warning(f"Campi dispositivo mancanti: {missing_device_fields}")
                    return jsonify({"success": False, "message": f"Campi mancanti: {', '.join(missing_device_fields)}"}), 400

            # Crea l'utente
            new_user = User(username=data['username'], user_type=data['user_type'])
            new_user.set_password(data['password'])
            session.add(new_user)
            session.flush()  # Assicurati che new_user.id sia disponibile

            current_app.logger.info(f"Utente creato: {data['username']}")

            # # Se user_type è 'device', crea un dispositivo associato
            # if 'user_type' in data and data['user_type'] in ['device', 'datacenter']:
            #     new_device = Device(
            #         user_id=new_user.id,
            #         ip_address=data.get('ip_address'),
            #         mac_address=data.get('mac_address'),
            #         gateway=data.get('gateway'),
            #         subnet_mask=data.get('subnet_mask'),
            #         dns_address=data.get('dns_address'),
            #         username=data.get('username'),
            #         password=data.get('password'),
            #         device_id=data.get('device_id')
            #     )
            #     session.add(new_device)
            #     current_app.logger.info(f"Dispositivo creato per l'utente: {data['username']}")

            # Esegui il commit della transazione
            session.commit()
            current_app.logger.info("Registrazione completata con successo.")

            return jsonify({"success": True, "message": "Utente creato con successo."}), 201
        except (SQLAlchemyError, Exception) as e:
            session.rollback()
            current_app.logger.error(f"Errore durante la registrazione: {str(e)}")
            return jsonify({"success": False, "message": "Errore interno del server."}), 500


@auth_blueprint.route('/login', methods=['POST'])
def login():
    Session = sessionmaker(bind=db.engine)
    with Session() as session:
        try:
            current_app.logger.info("Inizio del login utente.")
            data = request.get_json()
            user = session.query(User).filter_by(username=data['username']).first()

            if user and user.check_password(data['password']):
                access_token = create_access_token(identity={'id': user.id, 'username': user.username})
                refresh_token = create_refresh_token(identity={'id': user.id, 'username': user.username})
                current_app.logger.info(f"Login riuscito per l'utente: {user.username}")
                return jsonify({"success": True, "access_token": access_token, "refresh_token": refresh_token}), 200
            else:
                current_app.logger.warning("Tentativo di login fallito: credenziali non valide.")
                return jsonify({"success": False, "message": "Utente o password non corretti"}), 401
        except Exception as e:
            current_app.logger.error(f"Errore durante il login: {str(e)}")
            return jsonify({"success": False, "message": "Errore interno del server"}), 500

@auth_blueprint.route('/token/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    try:
        current_app.logger.info("Richiesta di refresh token ricevuta.")
        current_user = get_jwt_identity()
        new_access_token = create_access_token(identity=current_user)
        current_app.logger.info(f"Token aggiornato per l'utente: {current_user}")
        return jsonify({"success": True, "access_token": new_access_token}), 200
    except Exception as e:
        current_app.logger.error(f"Errore durante il refresh del token: {str(e)}")
        return jsonify({"success": False, "message": "Errore interno del server"}), 500

@auth_blueprint.route('/update_credentials', methods=['POST'])
@jwt_required()
def update_credentials():
    Session = sessionmaker(bind=db.engine)
    with Session() as session:
        try:
            current_app.logger.info("Inizio aggiornamento credenziali utente.")
            current_user = get_jwt_identity()
            data = request.get_json()

            new_password = data.get('new_password')
            new_username = data.get('new_username')

            if not new_password and not new_username:
                current_app.logger.warning("Richiesta di aggiornamento credenziali senza nuovi dati.")
                return jsonify({"success": False, "message": "È necessario fornire almeno una nuova credenziale."}), 400

            user = session.query(User).filter_by(id=current_user['id']).first()
            if not user:
                current_app.logger.warning(f"Utente non trovato con ID: {current_user['id']}")
                return jsonify({"success": False, "message": "Utente non trovato."}), 404

            if new_password:
                user.set_password(new_password)
                current_app.logger.info(f"Password aggiornata per l'utente: {user.username}")

            if new_username:
                existing_user = session.query(User).filter_by(username=new_username).first()
                if existing_user:
                    current_app.logger.warning("Tentativo di aggiornare lo username con un nome già in uso.")
                    return jsonify({"success": False, "message": "Il nuovo username è già in uso."}), 400
                user.username = new_username
                current_app.logger.info(f"Username aggiornato per l'utente: {new_username}")

            devices = session.query(Device).filter_by(user_id=user.id).all()
            for device in devices:
                if new_username:
                    device.username = new_username
                if new_password:
                    device.password = new_password
                current_app.logger.info(f"Credenziali aggiornate per il dispositivo: {device.device_id}")

            session.commit()
            current_app.logger.info("Aggiornamento credenziali completato con successo.")
            return jsonify({"success": True, "message": "Credenziali aggiornate con successo."}), 200

        except (SQLAlchemyError, Exception) as e:
            session.rollback()
            current_app.logger.error(f"Errore durante l'aggiornamento delle credenziali: {str(e)}")
            return jsonify({"success": False, "message": "Errore interno del server"}), 500
