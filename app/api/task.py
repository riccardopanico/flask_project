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

@task_blueprint.route('/create', methods=['POST'])
@jwt_required()
def create():
    Session = sessionmaker(bind=db.engine)
    try:
        with Session() as session:
            current_user = get_jwt_identity()
            user = session.query(User).get(current_user['id'])
            if not user or user.user_type != 'device':
                return jsonify({"msg": "Unauthorized"}), 403

            device = session.query(Device).filter_by(user_id=user.id).first()
            if not device:
                return jsonify({"msg": "Device not found"}), 404

            data = request.get_json()
            if not data or 'tasks' not in data or not isinstance(data['tasks'], list):
                return jsonify({"msg": "Invalid input"}), 400
            tasks = [Task(**task, device_id=device.device_id) for task in data['tasks']]

            session.add_all(tasks)
            session.commit()
            return jsonify({"msg": "Tasks created successfully", "tasks": [task.to_dict() for task in tasks]}), 201
    except (SQLAlchemyError, Exception) as e:
        debug_mode = current_app.debug
        error_response = {"msg": "Errore interno del server"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500
