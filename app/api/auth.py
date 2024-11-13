# app/api/auth.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from app import db
from app.models.user import User

auth_blueprint = Blueprint('auth', __name__)

@auth_blueprint.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()

        # Verifica che tutti i campi richiesti siano presenti
        required_keys = ['username', 'password', 'user_type']
        for key in required_keys:
            if key not in data:
                return jsonify({"msg": f"Missing key: {key}"}), 400

        # Controlla se l'utente esiste già
        if User.query.filter_by(username=data['username']).first():
            return jsonify({"msg": "Username already exists"}), 400

        # Crea un nuovo utente
        new_user = User(username=data['username'], user_type=data['user_type'])
        new_user.set_password(data['password'])

        # Salva nel database
        db.session.add(new_user)
        db.session.commit()

        return jsonify({"msg": "User registered successfully"}), 201
    except Exception as e:
        db.session.rollback()
        if current_app.config.get("DEBUG", False):
            return jsonify({"msg": "Internal Server Error", "error": str(e)}), 500
        else:
            return jsonify({"msg": "Internal Server Error"}), 500

@auth_blueprint.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        user = User.query.filter_by(username=data['username']).first()

        if user and user.check_password(data['password']):
            access_token = create_access_token(identity={'id': user.id, 'user_type': user.user_type})
            refresh_token = create_refresh_token(identity={'id': user.id, 'user_type': user.user_type})
            return jsonify(access_token=access_token, refresh_token=refresh_token), 200
        else:
            return jsonify({"msg": "Bad username or password"}), 401
    except Exception as e:
        if current_app.config.get("DEBUG", False):
            return jsonify({"msg": "Internal Server Error", "error": str(e)}), 500
        else:
            return jsonify({"msg": "Internal Server Error"}), 500

@auth_blueprint.route('/token/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    try:
        current_user = get_jwt_identity()
        new_access_token = create_access_token(identity=current_user)
        return jsonify(access_token=new_access_token), 200
    except Exception as e:
        if current_app.config.get("DEBUG", False):
            return jsonify({"msg": "Internal Server Error", "error": str(e)}), 500
        else:
            return jsonify({"msg": "Internal Server Error"}), 500
