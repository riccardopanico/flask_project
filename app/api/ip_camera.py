import os
from flask import Blueprint, current_app, jsonify, request, render_template, abort
from datetime import datetime
from typing import Any
from app.utils.video_pipeline import VideoPipeline, PipelineSettings
from ultralytics import YOLO

ip_camera_blueprint = Blueprint('ip_camera', __name__, url_prefix='/api/ip_camera')

def _log_event(source_id: str, event_type: str, seq: int = None, details: dict = None):
    current_app.logger.info({
        "event": event_type,
        "source": source_id,
        "timestamp": datetime.utcnow().isoformat(),
        "seq": seq,
        "details": details or {}
    })


@ip_camera_blueprint.route('/monitor')
def render_monitor():
    return render_template("ip_camera_monitor.html")


@ip_camera_blueprint.route('/camera_monitor')
def render_camera_monitor():
    return render_template("camera_monitor.html")


@ip_camera_blueprint.route('/start/<source_id>', methods=['POST'])
def start(source_id):
    cfgs = current_app.config.get('PIPELINE_CONFIGS', {})
    if source_id not in cfgs:
        return jsonify(success=False, error="Config non trovata"), 404

    if source_id not in current_app.video_pipelines:
        cfg = PipelineSettings(**cfgs[source_id])
        vp = VideoPipeline(cfg, logger=current_app.logger)
        vp.register_callback('frame', lambda fr, sid=source_id: _log_event(sid, 'frame', fr.seq, {'timestamp': fr.timestamp}))
        vp.register_callback('inference', lambda fr, path, res, sid=source_id: _log_event(sid, 'inference', fr.seq, {
            'model': os.path.basename(path),
            'boxes': [{'cls': int(b.cls), 'conf': float(b.conf), 'xyxy': b.xyxy.tolist()} for b in res.boxes]
        }))
        vp.register_callback('error', lambda err, sid=source_id: _log_event(sid, 'error', None, {'error': str(err)}))
        current_app.video_pipelines[source_id] = vp

    current_app.video_pipelines[source_id].start()
    _log_event(source_id, 'pipeline_started')
    return jsonify(success=True), 200


@ip_camera_blueprint.route('/stop/<source_id>', methods=['POST'])
def stop(source_id):
    vp = current_app.video_pipelines.pop(source_id, None)
    if not vp:
        return jsonify(success=False, error="Pipeline non esistente"), 404
    vp.stop()
    _log_event(source_id, 'pipeline_stopped')
    return jsonify(success=True), 200


@ip_camera_blueprint.route('/stream/<source_id>')
def stream(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp or vp._stop.is_set():
        abort(404)
    return vp.stream_response()


@ip_camera_blueprint.route('/healthz/<source_id>')
def healthz(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404
    status = vp.health()
    _log_event(source_id, 'health_check', details=status)
    return jsonify(success=True, **status), 200


@ip_camera_blueprint.route('/metrics/<source_id>')
def metrics(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404
    mets = vp.metrics()
    _log_event(source_id, 'metrics', details=mets)
    return jsonify(success=True, **mets), 200


@ip_camera_blueprint.route('/config/<source_id>', methods=['GET', 'PATCH'])
def config(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404

    if request.method == 'GET':
        return jsonify(success=True, config=vp.export_config()), 200

    try:
        payload = request.get_json(force=True)
        vp.update_config(**payload)
        _log_event(source_id, 'config_updated', details=payload)
        return jsonify(success=True), 200
    except Exception as e:
        current_app.logger.error(f"Errore update config: {e}")
        _log_event(source_id, 'config_error', details={'error': str(e)})
        return jsonify(success=False, error=str(e)), 400


@ip_camera_blueprint.route('/models/list')
def list_models():
    models_dir = current_app.config['MODELS_DIR']
    return jsonify([f'data/models/{f}' for f in os.listdir(models_dir) if f.endswith('.pt')] or [])


@ip_camera_blueprint.route('/model_classes')
def model_classes():
    path = request.args.get('path')
    if not path:
        return jsonify([])
    abs_path = os.path.join(current_app.config['BASE_DIR'], path)
    if not os.path.isfile(abs_path):
        return jsonify([])
    try:
        model = YOLO(abs_path)
        return jsonify(list(model.names.values()) if hasattr(model, 'names') else [])
    except Exception as e:
        current_app.logger.error(f"Errore caricamento classi modello {abs_path}: {e}")
        return jsonify([])
