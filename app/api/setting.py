from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app.models.variables import Variables
from app import db

setting_blueprint = Blueprint('setting', __name__)

# Definisci una singola funzione per gestire sia GET che POST
@setting_blueprint.route('/', methods=['GET', 'POST'])
@jwt_required()
def setting():
    # Configura il sessionmaker per l'uso delle sessioni
    Session = sessionmaker(bind=db.engine)

    try:
        with Session() as session:
            request_data = request.get_json()
            setting_code = request_data.get('setting')

            if not setting_code:
                return jsonify({"messaggio": "Parametro 'setting' mancante!"}), 400

            if request.method == 'GET':
                # Recupera l'impostazione richiesta
                impostazione = session.query(Variables).filter_by(variable_code=setting_code).first()
                if impostazione:
                    response_data = {
                        "codice": impostazione.variable_code,
                        "descrizione": impostazione.variable_name,
                        "valore": impostazione.get_value()
                    }
                    return jsonify(response_data), 200
                else:
                    return jsonify({}), 404

            elif request.method == 'POST':
                valore = request_data.get('valore')
                if valore is None or len(str(valore)) == 0:
                    return jsonify({"messaggio": "Parametro 'valore' mancante!"}), 400

                # Aggiorna l'impostazione nel database in modo generico
                impostazione = session.query(Variables).filter_by(variable_code=setting_code).first()
                if not impostazione:
                    return jsonify({"messaggio": "Nessuna variabile trovata!"}), 404
                else:
                    impostazione.set_value(valore)
                    session.commit()
                    return jsonify({"messaggio": "Variabile impostata!"}), 200

    except (SQLAlchemyError, Exception) as e:
        debug_mode = current_app.debug
        error_response = {"msg": "Errore interno del server"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500
