from flask import Blueprint, current_app, jsonify, request
from app.utils.video_pipeline import VideoPipeline, PipelineConfig

ip_camera_blueprint = Blueprint('ip_camera', __name__, url_prefix='/api/ip_camera')

@ip_camera_blueprint.route('/start/<source_id>', methods=['POST'])
def start(source_id):
    cfgs = current_app.config.get('PIPELINE_CONFIGS', {})
    if source_id not in cfgs:
        return jsonify(success=False, error="Config non trovata"), 404

    if source_id not in current_app.video_pipelines:
        cfg_raw = cfgs[source_id]

        # Controllo: se vogliamo leggere da un'altra pipeline già esistente
        if isinstance(cfg_raw.get('source'), str) and cfg_raw['source'].startswith('http'):
            # Estrai quale altra pipeline vogliamo usare come sorgente
            parts = cfg_raw['source'].split('/')
            if len(parts) >= 5 and parts[-2] == 'stream':
                source_pipeline_id = parts[-1]  # es: 'default'

                if source_pipeline_id in current_app.video_pipelines:
                    # IMPORTANTISSIMO: imposta direttamente la VideoPipeline come sorgente!
                    cfg_raw['source'] = current_app.video_pipelines[source_pipeline_id]
                else:
                    return jsonify(success=False, error=f"Pipeline sorgente {source_pipeline_id} non avviata"), 400

        cfg = PipelineConfig(**cfg_raw)
        vp = VideoPipeline(cfg, logger=current_app.logger)
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
    current_app.video_pipelines.pop(source_id, None)
    return jsonify(success=True), 200

# Stream MJPEG per una pipeline
@ip_camera_blueprint.route('/stream/<source_id>')
def stream(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non inizializzata"), 404

    return vp.stream_response()

# Health check della pipeline
@ip_camera_blueprint.route('/healthz/<source_id>')
def healthz(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404

    return jsonify(success=True, **vp.health()), 200

# Metriche della pipeline
@ip_camera_blueprint.route('/metrics/<source_id>')
def metrics(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404

    return jsonify(success=True, **vp.metrics()), 200

# Aggiorna configurazione runtime
@ip_camera_blueprint.route('/config/<source_id>', methods=['PATCH'])
def update_config(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404

    try:
        update = request.get_json(force=True)
        vp.update_config(**update)
        return jsonify(success=True), 200
    except Exception as e:
        current_app.logger.error(f"Errore update config: {e}")
        return jsonify(success=False, error=str(e)), 400
