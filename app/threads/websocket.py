import asyncio
import json
import threading
import websockets
from flask import Flask, current_app
from app import websocket_queue, db
from app.models.device import Device
from app.models.log_data import LogData
from app.models.variables import Variables
from app.utils.video_pipeline import VideoPipeline, PipelineSettings

HOST, PORT = '0.0.0.0', 8765
BATCH_LATENCY_MS = 100

_connected = set()
_app: Flask = None
_batch_buffer = []


def ws_response(action: str, success: bool = True, source_id: str = None, data=None, error: str = None):
    msg = {'action': action, 'success': success}
    if source_id: msg['source_id'] = source_id
    if data is not None: msg['data'] = data
    if not success and error: msg['error'] = error
    return json.dumps(msg)


async def _broadcast(msg: str):
    if _connected:
        await asyncio.gather(
            *[ws.send(msg) for ws in _connected if ws.open],
            return_exceptions=True
        )


async def _batch_flusher():
    while True:
        await asyncio.sleep(BATCH_LATENCY_MS / 1000)
        if _batch_buffer:
            batch = json.dumps(_batch_buffer)
            _batch_buffer.clear()
            await _broadcast(batch)


async def socket_handler(ws, path):
    _connected.add(ws)
    try:
        async for raw in ws:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send(ws_response('invalid', False, error='Invalid JSON'))
                continue

            action = payload.get('action')
            sid = payload.get('source_id')
            cfgs = _app.config.get('PIPELINE_CONFIGS', {})

            with _app.app_context():
                if action == 'list_cameras':
                    cams = [{
                        'name': src,
                        'status': 'running' if (vp := _app.video_pipelines.get(src)) and not vp._stop.is_set() else 'stopped',
                        'clients': vp.clients_active if vp else 0
                    } for src in cfgs]
                    await ws.send(ws_response('list_cameras', True, data=cams))
                    continue

                if action == 'start':
                    if sid not in cfgs:
                        await ws.send(ws_response('start', False, error='unknown source_id'))
                        continue
                    if sid not in _app.video_pipelines:
                        pc = PipelineSettings(**cfgs[sid])
                        vp = VideoPipeline(pc, logger=_app.logger)

                        def _count_cb(data):
                            try:
                                with _app.app_context():
                                    device = Device.query.filter_by(interconnection_id=sid).first()
                                    if not device:
                                        _app.logger.error(f"Device not found for interconnection_id: {sid}")
                                        return

                                    # Funzione helper per gestire le variabili
                                    def get_or_create_variable(code, name, value_type='string'):
                                        var = Variables.query.filter_by(device_id=device.id, variable_code=code).first()
                                        if not var:
                                            var = Variables(device_id=device.id, variable_code=code, variable_name=name)
                                            db.session.add(var)
                                            db.session.commit()
                                        return var

                                    # Gestione dei dati
                                    track_var = get_or_create_variable('track_id', 'Track ID', 'numeric')
                                    track_var.set_value(data.get('track_id'))

                                    class_var = get_or_create_variable('class', 'Class')
                                    class_var.set_value(data.get('class'))

                                    direction_var = get_or_create_variable('direction', 'Direction')
                                    direction_var.set_value(data.get('direction'))

                                    # if isinstance(data.get('position'), tuple):
                                    #     pos_x_var = get_or_create_variable('position_x', 'Position X', 'numeric')
                                    #     pos_x_var.set_value(float(data['position'][0]))
                                    #     pos_y_var = get_or_create_variable('position_y', 'Position Y', 'numeric')
                                    #     pos_y_var.set_value(float(data['position'][1]))

                                    model_var = get_or_create_variable('model_path', 'Model Path')
                                    model_var.set_value(data.get('model_path'))

                                    # Aggiungi i dati al batch buffer
                                    _batch_buffer.append({
                                        'action': 'get_metrics',
                                        'source_id': sid,
                                        'data': _app.video_pipelines[sid].metrics()
                                    })
                            except Exception as e:
                                _app.logger.error(f"Error in count callback: {str(e)}")

                        vp.register_callback('count', _count_cb)
                        _app.video_pipelines[sid] = vp

                    _app.video_pipelines[sid].start()
                    await ws.send(ws_response('start', True, sid))
                    continue

                if action == 'stop':
                    vp = _app.video_pipelines.pop(sid, None)
                    if not vp:
                        await ws.send(ws_response('stop', False, error='not running'))
                        continue
                    vp.stop()
                    await ws.send(ws_response('stop', True, sid))
                    continue

                if action == 'update_config':
                    vp = _app.video_pipelines.get(sid)
                    cfg = payload.get('config') or {}
                    if not vp or not cfg:
                        await ws.send(ws_response('update_config', False, error='invalid parameters'))
                        continue
                    try:
                        vp.update_config(**cfg)
                        await ws.send(ws_response('update_config', True, sid))
                    except Exception as e:
                        await ws.send(ws_response('update_config', False, sid, error=str(e)))
                    continue

                if action in ('get_health', 'get_metrics', 'get_config'):
                    vp = _app.video_pipelines.get(sid)
                    if not vp:
                        await ws.send(ws_response(action, False, error='not running'))
                        continue
                    method = vp.health if action == 'get_health' else vp.metrics if action == 'get_metrics' else vp.export_config
                    await ws.send(ws_response(action, True, sid, method()))
                    continue

                await ws.send(ws_response(action, False, error='unknown action'))
    finally:
        _connected.discard(ws)


async def _queue_reader():
    while True:
        msg = await asyncio.to_thread(websocket_queue.get)
        _batch_buffer.append(msg)


async def _start_server():
    _app.logger.info(f'WebSocket server running on ws://{HOST}:{PORT}')
    asyncio.create_task(_batch_flusher())
    async with websockets.serve(socket_handler, HOST, PORT):
        await asyncio.Future()


def run(app: Flask):
    global _app
    _app = app

    def runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_start_server())
        finally:
            loop.close()

    threading.Thread(target=runner, name="WebSocketThread", daemon=False).start()