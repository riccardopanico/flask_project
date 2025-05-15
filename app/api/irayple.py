from flask import Blueprint, current_app, abort, Response
from app.utils.irayple import IraypleStreamer

irayple_blueprint = Blueprint('irayple', __name__, url_prefix='/api/irayple')

@irayple_blueprint.route('/<cam_id>/stream')
def stream(cam_id):
    cameras = current_app.config.get('IRAYPLE_CAMERAS', {})
    ip = cameras.get(cam_id)
    if not ip:
        abort(404, description=f"Camera '{cam_id}' non configurata")

    registry = current_app.irayple_cameras
    streamer = registry.get(cam_id)
    if not streamer:
        streamer = IraypleStreamer(ip=ip, log=current_app.logger)
        registry[cam_id] = streamer

    if not streamer.is_running():
        streamer.start()

    return streamer.stream_response()

def get_irayple_instance(cam_id: str) -> IraypleStreamer:
    cameras = current_app.config.get('IRAYPLE_CAMERAS', {})
    ip = cameras.get(cam_id)
    if not ip:
        raise ValueError(f"Camera '{cam_id}' non configurata")

    registry = current_app.irayple_cameras
    streamer = registry.get(cam_id)
    if not streamer:
        streamer = IraypleStreamer(ip=ip, log=current_app.logger)
        registry[cam_id] = streamer
        current_app.logger.info(f"Started IraypleStreamer for {cam_id}")

    if not streamer.is_running():
        streamer.start()

    return streamer
