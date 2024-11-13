from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.device import Device
from datetime import datetime

device_blueprint = Blueprint('device', __name__)

@device_blueprint.route('/profile', methods=['GET'])
@jwt_required()
def get_device_profile():
    try:
        current_user = get_jwt_identity()

        # Assicurati che l'utente sia un dispositivo
        if current_user['user_type'] != 'device':
            return jsonify({"msg": "Unauthorized"}), 403

        device = Device.query.get(current_user['id'])
        if not device:
            return jsonify({"msg": "Device not found"}), 404
        return jsonify(device.to_dict()), 200
    except Exception as e:
        if current_app.config.get("DEBUG", False):
            return jsonify({"msg": "Internal Server Error", "error": str(e)}), 500
        else:
            return jsonify({"msg": "Internal Server Error"}), 500
