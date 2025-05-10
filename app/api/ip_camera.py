import os
from flask import Blueprint, current_app, jsonify, request, render_template, abort
from datetime import datetime
from app.utils.video_pipeline import VideoPipeline, PipelineSettings

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
    """REST fallback per avviare la pipeline (ma preferite WS)."""
    cfgs = current_app.config.get('PIPELINE_CONFIGS', {})
    if source_id not in cfgs:
        return jsonify(success=False, error="Config non trovata"), 404

    # se non esiste la pipeline, la creo
    if source_id not in current_app.video_pipelines:
        cfg = PipelineSettings(**cfgs[source_id])
        vp = VideoPipeline(cfg, logger=current_app.logger)
        # registro i callback di log
        vp.register_callback('on_frame', lambda fr, sid=source_id:
            _log_event(sid, 'frame', fr.seq, {'timestamp': fr.timestamp})
        )
        vp.register_callback('on_inference', lambda fr, path, res, sid=source_id:
            _log_event(sid, 'inference', fr.seq, {
                'model': os.path.basename(path),
                'boxes': [
                    {'cls': int(b.cls), 'conf': float(b.conf), 'xyxy': b.xyxy.tolist()}
                    for b in res.boxes
                ]
            })
        )
        vp.register_callback('on_count', lambda fr, counts, sid=source_id:
            _log_event(sid, 'count', fr.seq, {'counts': counts})
        )
        vp.register_callback('on_error', lambda err, sid=source_id:
            _log_event(sid, 'error', None, {'error': str(err)})
        )
        current_app.video_pipelines[source_id] = vp

    current_app.video_pipelines[source_id].start()
    _log_event(source_id, 'pipeline_started')
    return jsonify(success=True), 200

@ip_camera_blueprint.route('/stop/<source_id>', methods=['POST'])
def stop(source_id):
    """REST fallback per fermare la pipeline."""
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non esistente"), 404

    vp.stop()
    current_app.video_pipelines.pop(source_id, None)
    _log_event(source_id, 'pipeline_stopped')
    return jsonify(success=True), 200

@ip_camera_blueprint.route('/stream/<source_id>')
def stream(source_id):
    """Stream MJPEG: serve solo se la pipeline è già in esecuzione."""
    vp = current_app.video_pipelines.get(source_id)
    if not vp or vp._stop.is_set():
        abort(404)
    return vp.stream_response()

@ip_camera_blueprint.route('/healthz/<source_id>')
def healthz(source_id):
    """Health check via REST."""
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404
    status = vp.health()
    _log_event(source_id, 'health_check', details=status)
    return jsonify(success=True, **status), 200

@ip_camera_blueprint.route('/metrics/<source_id>')
def metrics(source_id):
    """Metrics via REST."""
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404
    mets = vp.metrics()
    _log_event(source_id, 'metrics', details=mets)
    return jsonify(success=True, **mets), 200

@ip_camera_blueprint.route('/config/<source_id>', methods=['GET', 'PATCH'])
def config(source_id):
    """
    - GET: ritorna la config corrente (export_config).
    - PATCH: aggiorna via REST (fallback).
    """
    vp = current_app.video_pipelines.get(source_id)
    if not vp:
        return jsonify(success=False, error="Pipeline non trovata"), 404

    if request.method == 'GET':
        cfg = vp.export_config()
        return jsonify(success=True, config=cfg), 200

    # PATCH
    try:
        payload = request.get_json(force=True)
        vp.update_config(**payload)
        _log_event(source_id, 'config_updated', details=payload)
        return jsonify(success=True), 200
    except Exception as e:
        current_app.logger.error(f"Errore update config: {e}")
        _log_event(source_id, 'config_error', details={'error': str(e)})
        return jsonify(success=False, error=str(e)), 400
