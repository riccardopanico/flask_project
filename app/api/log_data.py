import os
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from app import db
from app.models.log_data import LogData
from app.models.device import Device
from app.models.variables import Variables

log_data_blueprint = Blueprint('log_data', __name__)

@log_data_blueprint.route('/', methods=['GET'])
@jwt_required()
def get_logs():
    """Recupera i log con filtri e paginazione."""
    data = request.get_json() or {}

    Session = sessionmaker(bind=db.engine)
    try:
        with Session() as session:
            query = session.query(LogData)

            device_id     = data.get('device_id', None)
            user_id       = data.get('user_id', None)
            variable_id   = data.get('variable_id', None)
            variable_code = data.get('variable_code', None)
            start_date    = data.get('start_date', None)
            end_date      = data.get('end_date', None)
            limit         = int(data.get('limit', 100))
            offset        = int(data.get('offset', 0))

            if device_id is not None:
                query = query.filter(LogData.device_id == device_id)
            if user_id is not None:
                query = query.filter(LogData.user_id == user_id)
            if variable_id is not None:
                query = query.filter(LogData.variable_id == variable_id)
            if variable_code:
                query = query.join(Variables).filter(Variables.variable_code == variable_code)

            if start_date:
                try:
                    start = datetime.fromisoformat(start_date)
                    query = query.filter(LogData.created_at >= start)
                except ValueError:
                    return jsonify({"success": False, "error": "Formato start_date non valido."}), 400

            if end_date:
                try:
                    end = datetime.fromisoformat(end_date)
                    query = query.filter(LogData.created_at <= end)
                except ValueError:
                    return jsonify({"success": False, "error": "Formato end_date non valido."}), 400

            total = query.count()
            logs = query.order_by(LogData.created_at.asc()).offset(offset).limit(limit).all()

            logs_data = []
            for log in logs:
                logs_data.append({
                    **log.to_dict(),
                    "interconnection_id":       log.device.interconnection_id if log.device else None,
                    "variable_code":            log.variable.variable_code if log.variable else None,
                    "variable_name":            log.variable.variable_name if log.variable else None,
                })

            return jsonify({"success": True, "data": logs_data, "total": total}), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Errore del database durante l'accesso ai log: {e}")
        return jsonify({"success": False, "error": "Si è verificato un errore nel database."}), 500
    except Exception as e:
        current_app.logger.error(f"Errore imprevisto durante l'accesso ai log: {e}")
        return jsonify({"success": False, "error": "Si è verificato un errore imprevisto."}), 500

@log_data_blueprint.route('/<int:log_id>', methods=['GET'])
@jwt_required()
def get_log(log_id):
    """Recupera un singolo log."""
    Session = sessionmaker(bind=db.engine)
    try:
        with Session() as session:
            log = session.query(LogData).get(log_id)
            if not log:
                return jsonify({"success": False, "error": "Log non trovato."}), 404

            log_data = {
                **log.to_dict(),
                "interconnection_id":       log.device.interconnection_id if log.device else None,
                "variable_code":            log.variable.variable_code if log.variable else None,
                "variable_name":            log.variable.variable_name if log.variable else None,
            }
            return jsonify({"success": True, "data": log_data}), 200

    except SQLAlchemyError as e:
        current_app.logger.error(f"Errore del database per il log {log_id}: {e}")
        return jsonify({"success": False, "error": "Si è verificato un errore nel database."}), 500
    except Exception as e:
        current_app.logger.error(f"Errore imprevisto per il log {log_id}: {e}")
        return jsonify({"success": False, "error": "Si è verificato un errore imprevisto."}), 500
