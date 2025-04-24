from flask import Blueprint, current_app, jsonify, request

ip_camera_blueprint = Blueprint('ip_camera', __name__, url_prefix='/api/ip_camera')

@ip_camera_blueprint.route('/stream', methods=['GET'])
def stream():
    """MJPEG stream del flusso elaborato."""
    vp = current_app.video_pipeline
    return vp.stream_response()

@ip_camera_blueprint.route('/config', methods=['GET', 'POST'])
def config():
    """GET=leggi config, POST=override dinamico."""
    vp = current_app.video_pipeline
    if request.method == 'GET':
        return jsonify(success=True, config=vp.export_config()), 200

    data = request.get_json(force=True)
    if not isinstance(data, dict):
        return jsonify(success=False, error="JSON invalido"), 400
    try:
        vp.update_config(**data)
        return jsonify(success=True, config=vp.export_config()), 200
    except Exception as e:
        current_app.logger.error(f"Config update error: {e}", exc_info=True)
        return jsonify(success=False, error="Errore interno"), 500

@ip_camera_blueprint.route('/healthz', methods=['GET'])
def healthz():
    vp = current_app.video_pipeline
    return jsonify(success=True, **vp.health()), 200

@ip_camera_blueprint.route('/metrics', methods=['GET'])
def metrics():
    vp = current_app.video_pipeline
    return jsonify(success=True, **vp.metrics()), 200

@ip_camera_blueprint.route('/info', methods=['GET'])
def info():
    """
    Restituisce i metadati della camera aperta:
    width, height, fps, fourcc.
    """
    vp = current_app.video_pipeline
    info = vp.camera_info()
    return jsonify(success=True, camera=info), 200
