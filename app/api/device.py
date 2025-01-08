from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models.device import Device
from app.models.user import User
from app.models.variables import Variables
from app.models.log_data import LogData
from datetime import timedelta

# Create a blueprint for device-related routes
device_blueprint = Blueprint('device', __name__)

# Route to get all devices
@device_blueprint.route('/', methods=['GET'])
@jwt_required()
def get_all_devices():
    try:
        devices = Device.query.all()
        return jsonify([device.to_dict() for device in devices]), 200
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error: {str(e)}")
        return jsonify({"error": "An error occurred while fetching devices."}), 500

# Route to get device by ID
@device_blueprint.route('/<int:device_id>', methods=['GET'])
@jwt_required()
def get_device(device_id):
    try:
        device = Device.query.get(device_id)
        if not device:
            return jsonify({"error": "Device not found."}), 404
        return jsonify(device.to_dict()), 200
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error: {str(e)}")
        return jsonify({"error": "An error occurred while fetching the device."}), 500

# Route to get variables associated with a device
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

# Route to get log data for a device
@device_blueprint.route('/<int:device_id>/log_data', methods=['GET'])
@jwt_required()
def get_device_log_data(device_id):
    try:
        log_data = LogData.query.filter_by(device_id=device_id).all()
        if not log_data:
            return jsonify({"error": "No log data found for this device."}), 404
        return jsonify([log.to_dict() for log in log_data]), 200
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error: {str(e)}")
        return jsonify({"error": "An error occurred while fetching log data."}), 500

# Route to create a new device
@device_blueprint.route('/', methods=['POST'])
@jwt_required()
def create_device():
    try:
        data = request.json
        new_device = Device(
            device_id=data['device_id'],
            user_id=data['user_id'],
            mac_address=data['mac_address'],
            ip_address=data['ip_address'],
            gateway=data.get('gateway', '192.168.1.1'),
            subnet_mask=data.get('subnet_mask', '255.255.255.0'),
            dns_address=data.get('dns_address', '8.8.8.8'),
            port_address=data.get('port_address', 80)
        )
        db.session.add(new_device)
        db.session.commit()
        return jsonify(new_device.to_dict()), 201
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "An error occurred while creating the device."}), 500
    except KeyError as e:
        return jsonify({"error": f"Missing required field: {str(e)}"}), 400

# Route to delete a device
@device_blueprint.route('/<int:device_id>', methods=['DELETE'])
@jwt_required()
def delete_device(device_id):
    try:
        device = Device.query.get(device_id)
        if not device:
            return jsonify({"error": "Device not found."}), 404
        db.session.delete(device)
        db.session.commit()
        return jsonify({"message": "Device deleted successfully."}), 200
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "An error occurred while deleting the device."}), 500

# Route to update a device
@device_blueprint.route('/<int:device_id>', methods=['PUT'])
@jwt_required()
def update_device(device_id):
    try:
        data = request.json
        device = Device.query.get(device_id)
        if not device:
            return jsonify({"error": "Device not found."}), 404

        device.mac_address = data.get('mac_address', device.mac_address)
        device.ip_address = data.get('ip_address', device.ip_address)
        device.gateway = data.get('gateway', device.gateway)
        device.subnet_mask = data.get('subnet_mask', device.subnet_mask)
        device.dns_address = data.get('dns_address', device.dns_address)
        device.port_address = data.get('port_address', device.port_address)

        db.session.commit()
        return jsonify(device.to_dict()), 200
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "An error occurred while updating the device."}), 500

# Route to synchronize log_data
@device_blueprint.route('/synchronize/log_data', methods=['POST'])
@jwt_required()
def synchronize_log_data():
    try:
        with current_app.app_context():
            Session = sessionmaker(bind=db.engine)
            with Session() as session:
                devices = session.query(Device).all()
                for device in devices:
                    try:
                        device_manager = current_app.api_device_manager.get(device.username)
                        if not device_manager:
                            current_app.logger.error(f"Device manager not found for device {device.username}.")
                            continue

                        response = device_manager.call('log_data', method='GET')

                        if response['success']:
                            for log_dict in response['data']:
                                log = LogData(**log_dict)
                                log.device_id = device.id
                                session.add(log)
                            session.commit()
                            current_app.logger.info(f"Log data synchronized successfully for device {device.ip_address}.")
                        else:
                            current_app.logger.error(f"Error synchronizing log data for device {device.ip_address}: {response['error']}")
                    except SQLAlchemyError as e:
                        session.rollback()
                        current_app.logger.error(f"Database error for device {device.ip_address}: {str(e)}")
                    except Exception as e:
                        session.rollback()
                        current_app.logger.error(f"Error processing log data for device {device.ip_address}: {str(e)}")
        return jsonify({"message": "Log data synchronization completed."}), 200
    except Exception as e:
        current_app.logger.critical(f"Critical error during log data synchronization: {str(e)}")
        return jsonify({"error": "An error occurred during log data synchronization."}), 500

@device_blueprint.route('/<int:device_id>/log_data', methods=['POST'])
@jwt_required()
def get_device_logs_by_date(device_id):
    try:
        data = request.json
        last_sync_date = data.get('last_sync_date')

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
