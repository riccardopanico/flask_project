from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models.device import Device
from app.models.user import User
from app.models.variables import Variables
from app.models.log_data import LogData
from datetime import timedelta

device_blueprint = Blueprint('device', __name__)

@device_blueprint.route('/<int:device_id>/variables', methods=['GET'])
@jwt_required()
def get_device_variables(device_id):
    try:
        variables = Variables.query.filter_by(device_id=device_id).all()
        if not variables:
            return jsonify({"error": "No variables found for this device."}), 404
        return jsonify([variable.to_dict() for variable in variables]), 200
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error: {str(e)}")
        return jsonify({"error": "An error occurred while fetching device variables."}), 500

@device_blueprint.route('/<int:device_id>/log_data', methods=['GET'])
@jwt_required()
def get_device_logs(device_id):
    try:
        last_sync_date = request.args.get('last_sync_date')

        Session = sessionmaker(bind=db.engine)
        with Session() as session:
            device = session.query(Device).filter_by(id=device_id).first()
            if not device:
                return jsonify({"error": "Device not found."}), 404

            logs_query = session.query(LogData).filter_by(device_id=device_id)
            if last_sync_date:
                logs_query = logs_query.filter(LogData.created_at > last_sync_date)

            logs = logs_query.order_by(LogData.created_at.asc()).all()
            logs_data = [log.to_dict() for log in logs]

            return jsonify({"message": "Logs fetched successfully.", "data": logs_data}), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error while processing logs for device {device_id}: {str(e)}")
        return jsonify({"error": "A database error occurred."}), 500
    except Exception as e:
        current_app.logger.error(f"Error processing logs for device {device_id}: {str(e)}")
        return jsonify({"error": "An unexpected error occurred while processing the logs."}), 500
