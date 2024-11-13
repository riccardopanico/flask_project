from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import sessionmaker
from app import db
from app.models.user import User
from app.models.device import Device

device_blueprint = Blueprint('device', __name__)

@device_blueprint.route('/profile', methods=['GET'])
@jwt_required()
def get_device_profile():
    # Configura il sessionmaker per l'uso delle sessioni
    Session = sessionmaker(bind=db.engine)
    
    try:
        with Session() as session:
            current_user = get_jwt_identity()

            user = session.query(User).get(current_user['id'])
            if not user:
                return jsonify({"msg": "User not found"}), 404

            if user.user_type != 'device':
                return jsonify({"msg": "Unauthorized"}), 403

            device = session.query(Device).filter_by(user_id=user.id).first()
            if not device:
                return jsonify({"msg": "Device not found"}), 404
            
            return jsonify(device.to_dict()), 200

    except Exception as e:
        debug_mode = current_app.config.get("DEBUG", False)
        error_response = {"msg": "Internal Server Error"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500
