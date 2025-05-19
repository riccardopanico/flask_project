from flask import Blueprint, request, jsonify, current_app
import json
import requests
import traceback
from datetime import datetime
import os
import cx_Oracle  # Ora importiamo cx_Oracle

DB_CONFIG = {
    'sirio': {
        'USER': 'sirio_raspberry',
        'PASSWORD': 'sirio_raspberry',
        'DSN': cx_Oracle.makedsn('130.61.84.61', '1521', service_name='php.nivadb.nivavcn.oraclevcn.com')
    },
    'ga2': {
        'USER': 'elata',
        'PASSWORD': 'elata',
        'DSN': cx_Oracle.makedsn('130.61.84.61', '1521', service_name='ga2web.nivadb.nivavcn.oraclevcn.com')
    }
}

def get_connection(db_key):
    if db_key not in DB_CONFIG:
        raise ValueError(f"DB key '{db_key}' non definita nella configurazione.")
    conf = DB_CONFIG[db_key]
    return cx_Oracle.connect(user=conf['USER'], password=conf['PASSWORD'], dsn=conf['DSN'])

recipe_blueprint = Blueprint('recipe', __name__)

@recipe_blueprint.route('/tipi_guasto', methods=['POST'])
def tipi_guasto():
    data = request.get_json()
    ID_MACCHINA = data.get('ID_MACCHINA')
    query = """
        SELECT
            H.ID AS ID_MACCHINA_SIRIO,
            H.ID_MACCHINA,
            H.IP_ASSEGNATO,
            G.CODICE AS CODICE_GUASTO,
            G.DESCR AS DESCRIZIONE_GUASTO
        FROM TESEO_HARDWARE H, TESEO_TAB_GUASTI G
        WHERE H.ID_MACCHINA IS NOT NULL
          AND H.IP_ASSEGNATO IS NOT NULL
          AND H.CATEGORIA = G.CATEGORIA
          AND H.ID_MACCHINA = :ID_MACCHINA
        ORDER BY H.ID ASC
    """
    try:
        con = get_connection('sirio')
        cursor = con.cursor()
        cursor.execute(query, {'ID_MACCHINA': ID_MACCHINA})
        rows = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        return jsonify({"success": True, "data": rows}), 200
    except Exception as e:
        current_app.logger.error(f"Errore in tipi_guasto: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        try:
            cursor.close()
            con.close()
        except Exception:
            pass

@recipe_blueprint.route('/fase', methods=['POST'])
def fase():
    data = request.get_json()
    if 'codpref' not in data or 'nlotto' not in data:
        return jsonify({"success": False, "error": "Campi mancanti"}), 400

    try:
        codpref = int(data['codpref'])
        nlotto = int(data['nlotto'])
    except ValueError:
        return jsonify({"success": False, "error": "Valori non validi per codpref o nlotto"}), 400

    query = """
        SELECT S.CODFASE, AF.DESCR AS DESCR_FASE, F.CODLAVOR,
               TO_CHAR(F.DATA, 'YYYY-MM-DD HH24:MI:SS') AS DATA
        FROM FASE_LOTTO_DETT F, SEQ_FASI_LAV S, PROD_LOT_TEST L,
             GRUPPI_MERC G, ARTICOLI A, ANAG_FASI_PROD AF, ORDCLI_PREFISSI OP
        WHERE L.CODART = A.CODART
          AND A.CODGM = G.CODGM
          AND G.CODLAV = S.CODLAV
          AND F.CODFASE = S.CODFASE
          AND OP.CODPREF = :codpref
          AND F.PREFISSO = OP.PREFISSO
          AND F.NLOTTO = :nlotto
          AND AF.CODFASE = S.CODFASE
          AND F.CODFASE IN ('TC', 'T1')
        GROUP BY F.DATA, S.CODFASE, F.CODLAVOR, AF.DESCR
        ORDER BY F.DATA, S.CODFASE, F.CODLAVOR
    """
    try:
        con = get_connection('ga2')
        cursor = con.cursor()
        cursor.execute(query, [codpref, nlotto])
        rows = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        return jsonify({"success": True, "data": rows}), 200
    except Exception as e:
        current_app.logger.error(f"Errore in fase: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        try:
            cursor.close()
            con.close()
        except Exception:
            pass

@recipe_blueprint.route('/situazione', methods=['POST'])
def situazione():
    data = request.get_json()
    if 'codpref' not in data or 'nlotto' not in data or 'codice' not in data:
        return jsonify({"success": False, "error": "Campi mancanti"}), 400

    try:
        codpref = int(data['codpref'])
        nlotto = int(data['nlotto'])
        codice = int(data['codice'])
    except ValueError:
        return jsonify({"success": False, "error": "Valori non validi"}), 400

    queryMateriale = """
        SELECT OCE.CODART AS CODMAT, A.CODGUI,
               NVL((F_CONST_RIGLOT(ODF.PREFISSO, PLT.NLOTTO, OCE.ID)*F_QTORD_LOTTO(ODF.PREFISSO, PLT.NLOTTO)), 0) CONSUMO_LOTTO
        FROM PROD_LOT_TEST PLT, PROD_LOT_RIG PLR, ORDCLI_PREFISSI ODF,
             ORDCLI_ELEM OCE, ARTICOLI A
        WHERE PLT.PREFISSO = ODF.PREFISSO
          AND PLT.PREFISSO = PLR.PREFISSO
          AND PLT.NLOTTO = PLR.NLOTTO
          AND PLR.PREFISSO = OCE.PREFISSO
          AND PLR.NORDCLI = OCE.NORDCLI
          AND PLR.NRIGOCL = OCE.NRIGOCL
          AND A.CODART = OCE.CODART
          AND ODF.CODPREF = :codpref
          AND PLT.NLOTTO = :nlotto
          AND OCE.ID = :codice
    """
    queryPellami = """
        SELECT A.CODART,
               NVL(F_CALC_GIACENZA(A.CODART), 0) QTSIT,
               NVL(F_SIT_ORF(A.CODART), 0) QTORF,
               :consumo_lotto as CONSUMO_LOTTO,
               CASE WHEN F_CALC_GIACENZA(A.CODART) < :consumo_lotto THEN 1 ELSE 0 END as CONSUMO_MINORE_QTSIT
        FROM ARTICOLI A
        WHERE CODART = :materiale
    """
    queryTaglie = """
        SELECT OP.PREFISSO, :nlotto AS NLOTTO, GR.CODMIS, A.CODART,
               NVL(F_CALC_GIACENZA_QT(A.CODART, GR.CODGUI, GR.CODMIS), 0) QTSIT,
               NVL(F_QTORD_CODMIS_LOTTO(PLR.PREFISSO, PLR.NLOTTO, GR.CODGUI, GR.CODMIS), 0) QTORF,
               NVL(F_CONST_RIGLOT(PLR.PREFISSO, PLR.NLOTTO, 12) * F_QTORD_CODMIS_LOTTO(PLR.PREFISSO, PLR.NLOTTO, GR.CODGUI, GR.CODMIS), 0) CONSUMO_LOTTO,
               CASE WHEN NVL(F_CALC_GIACENZA_QT(A.CODART, GR.CODGUI, GR.CODMIS), 0)
                    < NVL(F_CONST_RIGLOT(PLR.PREFISSO, PLR.NLOTTO, 12) * F_QTORD_CODMIS_LOTTO(PLR.PREFISSO, PLR.NLOTTO, GR.CODGUI, GR.CODMIS), 0)
                    THEN 1 ELSE 0 END as CONSUMO_MINORE_QTSIT
        FROM GUIDE_RIGHE GR, ARTICOLI A, ORDCLI_PREFISSI OP, PROD_LOT_RIG PLR
        WHERE A.CODGUI = GR.CODGUI
          AND PLR.PREFISSO = OP.PREFISSO
          AND PLR.NLOTTO = :nlotto
          AND OP.CODPREF = :codpref
          AND A.CODART = :materiale
        ORDER BY GR.CODMIS
    """
    try:
        con = get_connection('ga2')
        cursor = con.cursor()
        cursor.execute(queryMateriale, {'codpref': codpref, 'nlotto': nlotto, 'codice': codice})
        result = cursor.fetchone()
        if result is None:
            return jsonify({"success": True, "data": []}), 200

        materiale = result[0]
        if result[1] is not None:
            # Se CODGUI non è nullo, esegui queryTaglie
            cursor.execute(queryTaglie, {'nlotto': nlotto, 'codpref': codpref, 'materiale': materiale})
        else:
            # Altrimenti, esegui queryPellami
            consumo_lotto = result[2]
            cursor.execute(queryPellami, {'consumo_lotto': consumo_lotto, 'materiale': materiale})
        rows = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        return jsonify({"success": True, "data": rows}), 200
    except Exception as e:
        current_app.logger.error(f"Errore in situazione: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        try:
            cursor.close()
            con.close()
        except Exception:
            pass

@recipe_blueprint.route('/info', methods=['POST'])
def info():
    data = request.get_json()
    if 'codpref' not in data or 'nlotto' not in data:
        return jsonify({"success": False, "error": "Campi mancanti"}), 400

    try:
        codpref = int(data['codpref'])
        nlotto = int(data['nlotto'])
    except ValueError:
        return jsonify({"success": False, "error": "Valori non validi per codpref o nlotto"}), 400

    queryInfo = """
            SELECT
                ocr.prefisso,
                :nlotto as NLOTTO,
                (ocr.codart || '-' || ocr.versione) AS articolo,
                ocr.note AS note_lavorazione
            FROM prod_lot_test plt, PROD_LOT_RIG plr, ordcli_prefissi odf, ordcli_righe ocr, articoli a
                WHERE plt.prefisso = odf.prefisso
                AND plt.prefisso = plr.prefisso
                AND plt.nlotto = plr.nlotto
                AND plr.prefisso = ocr.prefisso
                AND plr.nordcli = ocr.nordcli
                AND plr.nrigocl = ocr.nrigocl
                AND a.codart = ocr.codart
                AND odf.codpref = :codpref
                AND plt.nlotto = :nlotto
        """
    try:
        con = get_connection('ga2')
        cursor = con.cursor()
        cursor.execute(queryInfo, [nlotto, codpref, nlotto])
        result = cursor.fetchone()
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        current_app.logger.error(f"Errore in info: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        try:
            cursor.close()
            con.close()
        except Exception:
            pass

@recipe_blueprint.route('/tecnici', methods=['POST'])
def tecnici():
    data = request.get_json(silent=True) or {}  # Evita errore se non viene inviato JSON
    codice_tecnico = data.get('codice_tecnico')

    query = "SELECT * FROM RUBRICA_INTERVENTI"
    params = {}

    if codice_tecnico:  # Se presente, aggiunge il filtro
        query += " WHERE ID = :codice_tecnico"
        params['codice_tecnico'] = codice_tecnico

    try:
        con = get_connection('ga2')
        cursor = con.cursor()
        cursor.execute(query, params)
        rows = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        if codice_tecnico:
            rows = rows[0]
        return jsonify({"success": True, "data": rows}), 200
    except Exception as e:
        current_app.logger.error(f"Errore in tecnici: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        try:
            cursor.close()
            con.close()
        except Exception:
            pass

@recipe_blueprint.route('/sms', methods=['POST'])
def sms():
    data = request.get_json()
    if 'telefono' not in data or 'messaggio' not in data:
        return jsonify({"success": False, "error": "Campi mancanti"}), 400

    try:
        telefono = data['telefono']
        messaggio = data['messaggio']
        if not telefono.startswith("+39"):
            telefono = "+39" + telefono

        BASEURL = "https://app.esendex.it/API/v1.0/REST/"
        MESSAGE_HIGH_QUALITY = "N"

        def login(username, password):
            url = f"{BASEURL}login?username={username}&password={password}"
            r = requests.get(url)
            if r.status_code != 200:
                return None
            return r.text.split(';')  # [user_key, session_key]

        def send_sms(auth, payload):
            headers = {
                'user_key': auth[0],
                'Session_key': auth[1],
                'Content-type': 'application/json'
            }
            r = requests.post(f"{BASEURL}sms", headers=headers, data=json.dumps(payload, default=str))
            if r.status_code != 201:
                current_app.logger.error(f"Errore invio SMS: {r.status_code} - {r.content}")
                return None
            return r.json()

        # Credenziali per il servizio SMS
        user = "luca.valentino@niva.it"
        password = "Casarano2023$"
        auth = login(user, password)
        if not auth:
            return jsonify({"success": False, "error": "Impossibile effettuare il login per SMS."}), 400

        payload = {
            "message": messaggio,
            "message_type": MESSAGE_HIGH_QUALITY,
            "sender": "Elata",
            "returnCredits": False,
            "recipient": [telefono]
        }
        result_sms = send_sms(auth, payload)
        if not result_sms or result_sms.get("result") != "OK":
            return jsonify({"success": False, "error": "Errore nell'invio dell'SMS."}), 400

        return jsonify({"success": True, "message": "SMS inviato con successo."}), 200
    except Exception as e:
        current_app.logger.error(f"Errore in sms: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400

@recipe_blueprint.route('/operatore', methods=['POST'])
def operatore():
    data = request.get_json()
    if 'codice_operatore' not in data:
        return jsonify({"success": False, "error": "Campi mancanti"}), 400

    try:
        codice_operatore = data['codice_operatore']
        query = "SELECT * FROM ANAGRAFICA WHERE CODICE_OPERATORE = :codice_operatore"
        con = get_connection('ga2')
        cursor = con.cursor()
        cursor.execute(query, [codice_operatore])
        rows = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        return jsonify({"success": True, "data": rows}), 200
    except Exception as e:
        current_app.logger.error(f"Errore in operatore: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        try:
            cursor.close()
            con.close()
        except Exception:
            pass
