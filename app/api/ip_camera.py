from flask import Blueprint, current_app, jsonify, request
from app.utils.video_pipeline import VideoPipeline, PipelineConfig

ip_camera_blueprint = Blueprint('ip_camera', __name__, url_prefix='/api/ip_camera')

# Avvia (o riavvia) la pipeline per <source_id>
@ip_camera_blueprint.route('/start/<source_id>', methods=['POST'])
def start(source_id):
    cfgs = current_app.config.get('PIPELINE_CONFIGS', {})
    if source_id not in cfgs:
        return jsonify(success=False, error="Config non trovata"), 404

    # Istanzia se necessario
    if source_id not in current_app.video_pipelines:
        cfg = PipelineConfig(**cfgs[source_id])
        vp = VideoPipeline(cfg, logger=current_app.logger)
        # ES. registra callback custom:
        # vp.register_callback('on_count', lambda fr, counts: current_app.logger.info(f"{source_id}: {counts}"))
        current_app.video_pipelines[source_id] = vp

    vp = current_app.video_pipelines[source_id]
    vp.start()
    return jsonify(success=True), 200

# Ferma e rimuove la pipeline per <source_id>
@ip_camera_blueprint.route('/stop/<source_id>', methods=['POST'])
def stop(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non esistente"), 404

    vp.stop()
    # opzionale: rimuovi dal registry
    current_app.video_pipelines.pop(source_id, None)
    return jsonify(success=True), 200

# Stream MJPEG parametrizzato
@ip_camera_blueprint.route('/stream/<source_id>')
def stream(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non inizializzata"), 404

    return vp.stream_response()

# Health check per pipeline specifica
@ip_camera_blueprint.route('/healthz/<source_id>')
def healthz(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404

    return jsonify(success=True, **vp.health()), 200

# Metriche per pipeline specifica
@ip_camera_blueprint.route('/metrics/<source_id>')
def metrics(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404

    return jsonify(success=True, **vp.metrics()), 200
