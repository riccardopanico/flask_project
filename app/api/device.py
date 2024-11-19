from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import requests
from app import db
from app.models.user import User
from app.models.device import Device
from app.models.log_orlatura import LogOrlatura  # Assuming there's a model to represent the log_orlatura table

# Create a blueprint for device-related routes
device_blueprint = Blueprint('device', __name__)

@device_blueprint.route('/device_profile', methods=['GET'])
@jwt_required()
def device_profile():
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
            
            return jsonify({
                'id': device.id,
                'user_id': device.user_id,
                'nome': device.nome,
                'descrizione': device.descrizione,
                'created_at': device.created_at.isoformat() if device.created_at else None,
                'updated_at': device.updated_at.isoformat() if device.updated_at else None,
                'deleted_at': device.deleted_at.isoformat() if device.deleted_at else None
            }), 200

    except (SQLAlchemyError, Exception) as e:
        debug_mode = current_app.debug
        error_response = {"msg": "Errore interno del server"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500

@device_blueprint.route('/log_orlatura', methods=['GET'])
@jwt_required()
def log_orlatura():
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
            
            # Lettura dei dati dalla tabella log_orlatura per il dispositivo specifico
            query = session.query(LogOrlatura).filter_by(id_macchina=device.id)

            # Aggiunta di filtri per range di date se forniti nel payload
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            if start_date:
                query = query.filter(LogOrlatura.data >= db.func.to_timestamp(start_date, 'YYYY-MM-DD"T"HH24:MI:SS'))
            if end_date:
                query = query.filter(LogOrlatura.data <= db.func.to_timestamp(end_date, 'YYYY-MM-DD"T"HH24:MI:SS'))

            logs = query.all()

            if not logs:
                return jsonify({"msg": "No logs found for the device"}), 404

            # Serializza i dati per il ritorno come JSON
            log_data = [log.to_dict() for log in logs]
            
            return jsonify(log_data), 200

    except (SQLAlchemyError, Exception) as e:
        debug_mode = current_app.debug
        error_response = {"msg": "Errore interno del server"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500

@device_blueprint.route('/log_orlatura_proxy', methods=['GET'])
@jwt_required()
def log_orlatura_proxy():
    try:
        # Ottieni i parametri della richiesta originale
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        headers = {
            "Authorization": request.headers.get("Authorization")
        }

        # Costruisci l'URL per la rotta /log_orlatura
        base_url = request.host_url.rstrip('/')
        log_orlatura_url = f"{base_url}/log_orlatura"

        # Aggiungi i parametri di query se esistono
        params = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        # Effettua una richiesta GET all'endpoint log_orlatura
        response = requests.get(log_orlatura_url, headers=headers, params=params)

        # Restituisci la risposta originale
        return (response.content, response.status_code, response.headers.items())

    except Exception as e:
        debug_mode = current_app.debug
        error_response = {"msg": "Errore interno del server"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500
