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
            data = request.get_json()

            required_keys = ['username', 'password', 'user_type']
            for key in required_keys:
                if key not in data:
                    return jsonify({"success": False, "message": f"Chiave mancante: {key}"}), 400

            if session.query(User).filter_by(username=data['username']).first():
                return jsonify({"success": False, "message": "L'utente esiste già"}), 400

            # Validazione per il tipo di utente 'device'
            if data['user_type'] == 'device':
                required_keys = ['device_id', 'ip_address']
                for key in required_keys:
                    if key not in data:
                        return jsonify({"success": False, "message": f"Chiave mancante: {key}"}), 400

            new_user = User(username=data['username'], user_type=data['user_type'])
            new_user.set_password(data['password'])
            session.add(new_user)
            session.flush()  # Rende disponibile l'ID del nuovo utente senza effettuare il commit

            if data['user_type'] == 'device':
                new_device = Device(
                    user_id=new_user.id,
                    ip_address=data.get('ip_address'),
                    mac_address=data.get('mac_address'),
                    gateway=data.get('gateway'),
                    subnet_mask=data.get('subnet_mask'),
                    dns_address=data.get('dns_address'),
                    username=data.get('username'),
                    password=data.get('password'),
                )
                session.add(new_device)

                # Aggiorna la colonna device_id nel modello Variables
                if 'device_id' in data:
                    new_variable = Variables(device_id=new_device.id)  # Assumendo che ci sia un modello Variables
                    session.add(new_variable)

            session.commit()

            return jsonify({"success": True, "message": "Utente creato con successo"}), 201
        except (SQLAlchemyError, Exception) as e:
            session.rollback()
            error_response = {"success": False, "message": "Errore interno del server"}
            current_app.logger.error(f"Errore durante la registrazione: {str(e)}")
            if current_app.debug:
                error_response["error"] = str(e)
            return jsonify(error_response), 500

@auth_blueprint.route('/login', methods=['POST'])
def login():
    Session = sessionmaker(bind=db.engine)
    with Session() as session:
        try:
            data = request.get_json()
            user = session.query(User).filter_by(username=data['username']).first()

            if user and user.check_password(data['password']):
                access_token = create_access_token(identity={'id': user.id, 'username': user.username})
                refresh_token = create_refresh_token(identity={'id': user.id, 'username': user.username})
                return jsonify({"success": True, "access_token": access_token, "refresh_token": refresh_token}), 200
            else:
                return jsonify({"success": False, "message": "Utente o password non corretti"}), 401
        except Exception as e:
            error_response = {"success": False, "message": "Errore interno del server"}
            current_app.logger.error(f"Errore durante il login: {str(e)}")
            if current_app.debug:
                error_response["error"] = str(e)
            return jsonify(error_response), 500

@auth_blueprint.route('/token/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    try:
        current_user = get_jwt_identity()
        new_access_token = create_access_token(identity=current_user)
        return jsonify({"success": True, "access_token": new_access_token}), 200
    except Exception as e:
        error_response = {"success": False, "message": "Errore interno del server"}
        current_app.logger.error(f"Errore durante il refresh del token: {str(e)}")
        if current_app.debug:
            error_response["error"] = str(e)
        return jsonify(error_response), 500

@auth_blueprint.route('/update_credentials', methods=['POST'])
@jwt_required()
def update_credentials():
    Session = sessionmaker(bind=db.engine)
    with Session() as session:
        try:
            current_user = get_jwt_identity()
            data = request.get_json()

            new_password = data.get('new_password')
            new_username = data.get('new_username')

            if not new_password and not new_username:
                return jsonify({"success": False, "message": "È necessario fornire almeno una nuova credenziale."}), 400

            user = session.query(User).filter_by(id=current_user['id']).first()
            if not user:
                return jsonify({"success": False, "message": "Utente non trovato."}), 404

            # Aggiorna la password se fornita
            if new_password:
                user.set_password(new_password)
                current_app.logger.info(f"Password aggiornata per l'utente: {user.username}")

            # Aggiorna lo username se fornito
            if new_username:
                existing_user = session.query(User).filter_by(username=new_username).first()
                if existing_user:
                    return jsonify({"success": False, "message": "Il nuovo username è già in uso."}), 400
                user.username = new_username
                current_app.logger.info(f"Username aggiornato per l'utente: {user.username}")

            # Aggiorna i dispositivi associati
            devices = session.query(Device).filter_by(user_id=user.id).all()
            for device in devices:
                if new_username:
                    device.username = new_username
                if new_password:
                    device.password = new_password
                current_app.logger.info(f"Credenziali aggiornate per il dispositivo: {device.device_id}")

            session.commit()

            return jsonify({"success": True, "message": "Credenziali aggiornate con successo."}), 200

        except (SQLAlchemyError, Exception) as e:
            session.rollback()
            error_response = {"success": False, "message": "Errore interno del server"}
            current_app.logger.error(f"Errore durante l'aggiornamento delle credenziali: {str(e)}")
            if current_app.debug:
                error_response["error"] = str(e)
            return jsonify(error_response), 500
