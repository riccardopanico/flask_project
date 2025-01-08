from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from app import db
from app.models.user import User
from app.models.device import Device
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from datetime import datetime

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
                    return jsonify({"msg": f"Chiave mancante: {key}"}), 400

            if session.query(User).filter_by(username=data['username']).first():
                return jsonify({"msg": "L'utente esiste già"}), 400

            # Validazione per il tipo di utente 'device'
            if data['user_type'] == 'device':
                required_keys = [ 'device_id', 'ip_address' ]
                for key in required_keys:
                    if key not in data:
                        return jsonify({"msg": f"Chiave mancante: {key}"}), 400

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
                    dns_address=data.get('dns_address')
                )
                session.add(new_device)

            session.commit()

            return jsonify({"msg": "Utente creato con successo"}), 201
        except (SQLAlchemyError, Exception) as e:
            session.rollback()
            debug_mode = current_app.debug
            error_response = {"msg": "Errore interno del server"}
            if debug_mode:
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
                return jsonify(access_token=access_token, refresh_token=refresh_token), 200
            else:
                return jsonify({"msg": "Utente o password non corretti"}), 401
        except Exception as e:
            debug_mode = current_app.debug
            error_response = {"msg": "Errore interno del server"}
            if debug_mode:
                error_response["error"] = str(e)
            return jsonify(error_response), 500

@auth_blueprint.route('/token/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    try:
        current_user = get_jwt_identity()
        new_access_token = create_access_token(identity=current_user)
        return jsonify(access_token=new_access_token), 200
    except Exception as e:
        debug_mode = current_app.debug
        error_response = {"msg": "Errore interno del server"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500

@auth_blueprint.route('/update_password', methods=['POST'])
@jwt_required()
def update_password():
    Session = sessionmaker(bind=db.engine)
    with Session() as session:
        try:
            current_user = get_jwt_identity()
            data = request.get_json()

            new_password = data.get('new_password')
            if not new_password:
                return jsonify({"msg": "La nuova password è obbligatoria."}), 400

            user = session.query(User).filter_by(id=current_user['id']).first()
            if not user:
                return jsonify({"msg": "Utente non trovato."}), 404

            user.set_password(new_password)
            session.commit()

            if current_app.debug:
                print(f"Password aggiornata con successo per l'utente: {user.username}")

            return jsonify({"msg": "Password aggiornata con successo."}), 200

        except (SQLAlchemyError, Exception) as e:
            session.rollback()
            debug_mode = current_app.debug
            error_response = {"msg": "Errore interno del server"}
            if debug_mode:
                error_response["error"] = str(e)
            return jsonify(error_response), 500
