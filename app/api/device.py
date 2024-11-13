from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.user import User
from app.models.device import Device
from datetime import datetime

device_blueprint = Blueprint('device', __name__)

@device_blueprint.route('/profile', methods=['GET'])
@jwt_required()
def get_device_profile():
    try:
        current_user = get_jwt_identity()

        # Recupera l'utente dal database
        user = User.query.get(current_user['id'])
        if not user:
            return jsonify({"msg": "User not found"}), 404

        # Assicurati che l'utente sia un dispositivo
        if user.user_type != 'device':
            return jsonify({"msg": "Unauthorized"}), 403

        # Recupera il dispositivo associato all'utente
        device = Device.query.filter_by(user_id=user.id).first()
        if not device:
            return jsonify({"msg": "Device not found"}), 404
        
        return jsonify(device.to_dict()), 200
    except Exception as e:
        if current_app.config.get("DEBUG", False):
            return jsonify({"msg": "Internal Server Error", "error": str(e)}), 500
        else:
            return jsonify({"msg": "Internal Server Error"}), 500
