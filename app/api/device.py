from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import requests
from app import db
from app.models.user import User
from app.models.device import Device
from app.models.tasks import Task
from app.models.log_orlatura import LogOrlatura  # Assuming there's a model to represent the log_orlatura table

# Create a blueprint for device-related routes
device_blueprint = Blueprint('device', __name__)

@device_blueprint.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    # Configura il sessionmaker per l'uso delle sessioni
    Session = sessionmaker(bind=db.engine)

    try:
        with Session() as session:
            current_user = get_jwt_identity()

            # Recupera l'utente corrente
            user = session.query(User).get(current_user['id'])
            if not user:
                return jsonify({"msg": "User not found"}), 404

            # Verifica che l'utente sia del tipo 'device'
            if user.user_type != 'device':
                return jsonify({"msg": "Unauthorized"}), 403

            # Recupera il dispositivo associato all'utente
            device = session.query(Device).filter_by(user_id=user.id).first()
            if not device:
                return jsonify({"msg": "Device not found"}), 404

            # Costruisce la risposta combinando le informazioni utente e dispositivo
            response_data = {
                "id": user.id,
                "badge": user.badge,
                "username": user.username,
                "name": user.name,
                "last_name": user.last_name,
                "email": user.email,
                "user_created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None,
                "device_id": device.device_id,
                "mac_address": device.mac_address,
                "ip_address": device.ip_address,
                "gateway": device.gateway,
                "subnet_mask": device.subnet_mask,
                "dns_address": device.dns_address,
                "device_created_at": device.created_at.strftime("%Y-%m-%d %H:%M:%S") if device.created_at else None
            }

            return jsonify(response_data), 200

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

@device_blueprint.route('/task', methods=['POST'])
@jwt_required()
def create_task():
    # Configura il sessionmaker per l'uso delle sessioni
    Session = sessionmaker(bind=db.engine)

    try:
        data = request.get_json()
        if not data:
            return jsonify({"msg": "Invalid input"}), 400

        id_dispositivo = data.get("id_dispositivo")
        tipo_intervento = data.get("tipo_intervento")

        if not id_dispositivo or not tipo_intervento:
            return jsonify({"msg": "Missing required fields"}), 400

        with Session() as session:
            current_user = get_jwt_identity()

            user = session.query(User).get(current_user['id'])
            if not user:
                return jsonify({"msg": "User not found"}), 404

            if user.user_type != 'device':
                return jsonify({"msg": "Unauthorized"}), 403

            # Creazione del task
            new_task = Task(
                id_dispositivo=id_dispositivo,
                tipo_intervento=tipo_intervento
            )
            session.add(new_task)
            session.commit()

            return jsonify(new_task.to_dict()), 201

    except (SQLAlchemyError, Exception) as e:
        debug_mode = current_app.debug
        error_response = {"msg": "Errore interno del server"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500
