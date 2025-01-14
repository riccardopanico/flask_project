from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from app.models.device import Device
from app.models.user import User
from app.models.variables import Variables
from app.models.log_data import LogData
from datetime import datetime

device_blueprint = Blueprint('device', __name__)

@device_blueprint.route('/<int:interconnection_id>/log_data', methods=['GET'])
@jwt_required()
def get_device_logs(interconnection_id):
    try:
        last_sync_date = request.args.get('last_sync_date')

        Session = sessionmaker(bind=db.engine)
        with Session() as session:
            device = session.query(Device).filter_by(interconnection_id=interconnection_id).first()
            if not device:
                return jsonify({"success": False, "error": "Dispositivo non trovato."}), 404

            logs_query = session.query(LogData).filter_by(device_id=device.id)
            if last_sync_date:
                try:
                    last_sync_date = datetime.fromisoformat(last_sync_date)
                    logs_query = logs_query.filter(LogData.created_at > last_sync_date)
                except ValueError:
                    return jsonify({"success": False, "error": "Formato della data non valido per last_sync_date."}), 400

            logs = logs_query.order_by(LogData.created_at.asc()).all()

            logs_data = [log.to_dict() for log in logs]

            return jsonify({"success": True, "message": "Log recuperati con successo.", "data": logs_data}), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Errore del database per il dispositivo {interconnection_id}: {str(e)}")
        return jsonify({"success": False, "error": "Si è verificato un errore nel database."}), 500

    except Exception as e:
        current_app.logger.error(f"Errore imprevisto per il dispositivo {interconnection_id}: {str(e)}")
        return jsonify({"success": False, "error": "Si è verificato un errore imprevisto."}), 500
