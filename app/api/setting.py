
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app.models.impostazioni import Impostazioni
from app import db

setting_blueprint = Blueprint('setting', __name__)

@setting_blueprint.route('/get_setting', methods=['GET'])
@jwt_required()
def get_setting():
    # Configura il sessionmaker per l'uso delle sessioni
    Session = sessionmaker(bind=db.engine)

    try:
        with Session() as session:
            # Ottieni il parametro 'setting' dalla richiesta
            request_data = request.get_json()
            setting = request_data.get('setting')

            if not setting:
                return jsonify({"messaggio": "Parametro 'setting' mancante!"}), 400

            # Recupera l'impostazione richiesta
            impostazione = session.query(Impostazioni).filter_by(codice=setting).first()

            if impostazione:
                response_data = {
                    "codice": impostazione.codice,
                    "descrizione": impostazione.descrizione,
                    "valore": impostazione.valore
                }
                return jsonify(response_data), 200
            else:
                return jsonify({}), 404

    except (SQLAlchemyError, Exception) as e:
        debug_mode = current_app.debug
        error_response = {"msg": "Errore interno del server"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500


@setting_blueprint.route('/set_setting', methods=['POST'])
@jwt_required()
def set_setting():
    # Configura il sessionmaker per l'uso delle sessioni
    Session = sessionmaker(bind=db.engine)

    try:
        with Session() as session:
            request_data = request.get_json()
            setting = request_data.get('setting')
            valore = request_data.get('valore')

            # Verifica che i parametri 'setting' e 'valore' siano presenti e validi
            if not setting:
                return jsonify({"messaggio": "Parametro 'setting' mancante!"}), 400

            if not valore or len(valore) == 0:
                return jsonify({"messaggio": "Parametro 'valore' mancante!"}), 400

            # Aggiorna l'impostazione nel database in modo generico
            result = session.query(Impostazioni).filter_by(codice=setting).update({"valore": valore})

            if not result:
                return jsonify({"messaggio": "Nessuna variabile trovata!"}), 404
            else:
                session.commit()
                return jsonify({"messaggio": "Variabile impostata!"}), 200

    except (SQLAlchemyError, Exception) as e:
        debug_mode = current_app.debug
        error_response = {"msg": "Errore interno del server"}
        if debug_mode:
            error_response["error"] = str(e)
        return jsonify(error_response), 500
