from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app.models.variables import Variables
from app import db

variable_blueprint = Blueprint('variable', __name__)

@variable_blueprint.route('/<int:device_id>/', methods=['GET', 'POST'])
@jwt_required()
def variable(device_id):
    Session = sessionmaker(bind=db.engine)

    try:
        with Session() as session:
            request_data = request.get_json() if request.method == 'POST' else request.args
            variable_code = request_data.get('variable')

            if not variable_code:
                return jsonify({"message": "Parametro 'variable' mancante!"}), 400

            query = session.query(Variables).filter_by(variable_code=variable_code, device_id=device_id)
            variable_entry = query.first()

            if request.method == 'GET':
                if variable_entry:
                    response_data = {
                        "codice": variable_entry.variable_code,
                        "descrizione": variable_entry.variable_name,
                        "valore": variable_entry.get_value()
                    }
                    return jsonify(response_data), 200
                return jsonify({"message": "Variabile non trovata."}), 404

            if request.method == 'POST':
                valore = request_data.get('valore')
                if valore is None or len(str(valore)) == 0:
                    return jsonify({"message": "Parametro 'valore' mancante!"}), 400

                if not variable_entry:
                    return jsonify({"message": "Variabile non trovata."}), 404

                variable_entry.set_value(valore)
                session.commit()
                return jsonify({"message": "Variabile aggiornata con successo!"}), 200

    except Exception as e:
        current_app.logger.error(f"Errore imprevisto: {str(e)}")
        return jsonify({"message": "Errore interno del server"}), 500
