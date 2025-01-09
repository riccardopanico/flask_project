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
            return jsonify({"success": False, "error": "Nessuna variabile trovata per questo dispositivo."}), 404
        return jsonify({"success": True, "data": [variable.to_dict() for variable in variables]}), 200
    except SQLAlchemyError as e:
        current_app.logger.error(f"Errore del database: {str(e)}")
        return jsonify({"success": False, "error": "Si è verificato un errore durante il recupero delle variabili del dispositivo."}), 500

@device_blueprint.route('/<int:device_id>/log_data', methods=['GET'])
@jwt_required()
def get_device_logs(device_id):
    try:
        last_sync_date = request.args.get('last_sync_date')

        Session = sessionmaker(bind=db.engine)
        with Session() as session:
            device = session.query(Device).filter_by(id=device_id).first()
            if not device:
                return jsonify({"success": False, "error": "Dispositivo non trovato."}), 404

            logs_query = session.query(LogData).filter_by(device_id=device_id)
            if last_sync_date:
                logs_query = logs_query.filter(LogData.created_at > last_sync_date)

            logs = logs_query.order_by(LogData.created_at.asc()).all()
            logs_data = [log.to_dict() for log in logs]

            return jsonify({"success": True, "message": "Log recuperati con successo.", "data": logs_data}), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Errore del database durante l'elaborazione dei log per il dispositivo {device_id}: {str(e)}")
        return jsonify({"success": False, "error": "Si è verificato un errore del database."}), 500
    except Exception as e:
        current_app.logger.error(f"Errore durante l'elaborazione dei log per il dispositivo {device_id}: {str(e)}")
        return jsonify({"success": False, "error": "Si è verificato un errore imprevisto durante l'elaborazione dei log."}), 500
