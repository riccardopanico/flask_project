from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models.user import User
from app.models.device import Device
from app.models.tasks import Task

# Create a blueprint for task-related routes
task_blueprint = Blueprint('task', __name__)

@task_blueprint.route('/task', methods=['POST'])
@jwt_required()
def create_task():
    # Configura il sessionmaker per l'uso delle sessioni
    Session = sessionmaker(bind=db.engine)

    try:
        with Session() as session:
            # Ottieni l'utente corrente
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

            # Ottieni i dati dalla richiesta JSON
            data = request.get_json()
            if not data or 'task_type' not in data:
                return jsonify({"msg": "Invalid input"}), 400

            # Crea un nuovo task
            new_task = Task(
                device_id=device.device_id,
                task_type=data['task_type'],
                sent=data.get('sent', 0),
                status=data.get('status', 'UNASSIGNED')
            )
            session.add(new_task)
            session.commit()

            # Restituisci i dati del task creato
            return jsonify({"msg": "Task created successfully", "task": new_task.to_dict()}), 201

    except (SQLAlchemyError, Exception) as e:
        debug_mode = current_app.debug
        error_response = {"msg": "Errore interno del server"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500
