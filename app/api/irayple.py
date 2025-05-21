from flask import Blueprint, current_app, abort, Response
from app.utils.irayple import IraypleStreamer
from app.models.device import Device
from app.models.user import User

irayple_blueprint = Blueprint('irayple', __name__, url_prefix='/api/irayple')

@irayple_blueprint.route('/<cam_id>/stream')
def stream(cam_id: str) -> Response:
    cam_id = str(cam_id)  # garantisce che sia stringa

    registry = current_app.irayple_cameras
    streamer_entry = registry.get(cam_id)

    if streamer_entry:
        streamer, device = streamer_entry
    else:
        device = Device.query.join(User).filter(Device.id == int(cam_id), User.user_type == 'ip_camera').first()
        if not device:
            abort(404, description=f"Camera '{cam_id}' non configurata")

        ip = device.ip_address
        if not ip:
            abort(404, description=f"IP mancante per camera '{cam_id}'")

        streamer = IraypleStreamer(ip=ip, log=current_app.logger)
        registry[cam_id] = (streamer, device)

    if not streamer.is_running():
        streamer.start()

    return streamer.stream_response()

def get_irayple_instance(cam_id: str) -> IraypleStreamer:
    cam_id = str(cam_id)

    registry = current_app.irayple_cameras
    streamer_entry = registry.get(cam_id)

    if streamer_entry:
        streamer, device = streamer_entry
    else:
        device = Device.query.join(User).filter(Device.id == int(cam_id), User.user_type == 'ip_camera').first()
        if not device:
            raise ValueError(f"Camera '{cam_id}' non configurata")

        ip = device.ip_address
        if not ip:
            raise ValueError(f"IP mancante per camera '{cam_id}'")

        streamer = IraypleStreamer(ip=ip, log=current_app.logger)
        registry[cam_id] = (streamer, device)
        current_app.logger.info(f"Started IraypleStreamer for {cam_id}")

    if not streamer.is_running():
        streamer.start()

    return streamer
