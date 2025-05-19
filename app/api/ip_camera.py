import os
from flask import Blueprint, current_app, jsonify, request, render_template, abort
from datetime import datetime
from typing import Any
from app.utils.video_pipeline import VideoPipeline, PipelineSettings
from ultralytics import YOLO

ip_camera_blueprint = Blueprint('ip_camera', __name__, url_prefix='/api/ip_camera')

@ip_camera_blueprint.route('/monitor')
def render_monitor():
    return render_template("ip_camera_monitor.html")

@ip_camera_blueprint.route('/stream/<source_id>')
def stream(source_id):
    vp = current_app.video_pipelines.get(source_id)
    if not vp or vp._stop.is_set():
        abort(404)
    return vp.stream_response()

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
#bè'!#bè'!#bè'!
#bè'!#bè'!#bè'!
#bè'!#bè'!#bè'!
#bè'!#bè'!#bè'!
#bè'!#bè'!#bè'!
#bè'!#bè'!#bè'!

#bè'!#bè'!#bè'!
#bè'!#bè'!#bè'!
#bè'!#bè'!#bè'!
#bè'!#bè'!#bè'!
#bè'!#bè'!#bè'!
#bè'!#bè'!#bè'!