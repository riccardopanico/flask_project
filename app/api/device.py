from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from app import db
from app.models.device import Device
from datetime import datetime

# Blueprint per gestire le operazioni dei dispositivi
device_blueprint = Blueprint('device', __name__)

@device_blueprint.route('/register', methods=['POST'])
def register():
    try:
        data = request.json

        # Verifica che tutti i campi richiesti siano presenti
        required_keys = ['matricola', 'password', 'ip_address']
        for key in required_keys:
            if key not in data:
                return jsonify({"msg": f"Missing key: {key}"}), 400

        # Controlla se la matricola esiste già
        if Device.query.filter_by(matricola=data['matricola']).first():
            return jsonify({"msg": "Matricola already exists"}), 400

        # Crea un nuovo dispositivo
        new_device = Device(
            matricola=data['matricola'],
            ip_address=data['ip_address'],
            device_type=data.get('device_type'),
            status=data.get('status', 'inactive'),
            firmware_version=data.get('firmware_version')
        )
        new_device.set_password(data['password'])  # Hash della password

        # Salva nel database
        db.session.add(new_device)
        db.session.commit()

        return jsonify({"msg": "Device registered successfully"}), 201
    except Exception as e:
        db.session.rollback()  # Rollback per evitare problemi di transazione
        if current_app.config.get("DEBUG", False):
            return jsonify({"msg": "Internal Server Error", "error": str(e)}), 500
        else:
            return jsonify({"msg": "Internal Server Error"}), 500

@device_blueprint.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        device = Device.query.filter_by(matricola=data['matricola']).first()

        if device and device.check_password(data['password']):
            # Aggiorna l'ultimo accesso del dispositivo
            device.last_seen = datetime.utcnow()
            db.session.commit()

            # Genera i token JWT e refresh
            access_token = create_access_token(identity=device.id)
            refresh_token = create_refresh_token(identity=device.id)
            return jsonify(access_token=access_token, refresh_token=refresh_token), 200
        else:
            return jsonify({"msg": "Bad matricola or password"}), 401
    except Exception as e:
        if current_app.config.get("DEBUG", False):
            return jsonify({"msg": "Internal Server Error", "error": str(e)}), 500
        else:
            return jsonify({"msg": "Internal Server Error"}), 500

@device_blueprint.route('/token/refresh', methods=['POST'])
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

@device_blueprint.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    try:
        device_id = get_jwt_identity()
        device = Device.query.get(device_id)
        if not device:
            return jsonify({"msg": "Device not found"}), 404
        return jsonify(device.to_dict()), 200
    except Exception as e:
        if current_app.config.get("DEBUG", False):
            return jsonify({"msg": "Internal Server Error", "error": str(e)}), 500
        else:
            return jsonify({"msg": "Internal Server Error"}), 500