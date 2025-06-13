import asyncio
import json
import threading
import websockets
import copy
from flask import Flask, current_app
from app import websocket_queue, db
from app.models.device import Device
from app.models.user import User
from app.models.log_data import LogData
from app.models.variables import Variables
from app.utils.video_pipeline import VideoPipeline, PipelineSettings
from typing import Optional

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


def get_or_create_variable(device_id: int, code: str, name: str, value_type: str = 'string'):
    """Helper function to get or create a variable for a device."""
    var = Variables.query.filter_by(device_id=device_id, variable_code=code).first()
    if not var:
        var = Variables(device_id=device_id, variable_code=code, variable_name=name)
        db.session.add(var)
        db.session.commit()
    return var


def get_current_commessa(device_id: int):
    """Ottiene la commessa corrente selezionata per un dispositivo."""
    commessa_var = get_or_create_variable(device_id, 'commessa', 'Commessa Corrente')
    current_commessa_id = commessa_var.get_value()
    return current_commessa_id if current_commessa_id else None


def send_commessa_update(device_id: int, commessa_id: Optional[str], commessa_data: Optional[dict]):
    """Invia un aggiornamento commessa al client."""
    if not commessa_id or not commessa_data:
        # Caso reset: invia dati vuoti per pulire l'interfaccia
        _batch_buffer.append({
            'action': 'update_commessa',
            'source_id': str(device_id),
            'data': {
                'commessa_id': None,
                'commessa_data': None
            }
        })
        _app.logger.info(f"[COMMESSA] Reset commessa inviato al buffer WebSocket per device {device_id}")
    else:
        # Caso normale: invia i dati della commessa
        _batch_buffer.append({
            'action': 'update_commessa',
            'source_id': str(device_id),
            'data': {
                'commessa_id': commessa_id,
                'commessa_data': commessa_data
            }
        })
        _app.logger.info(f"[COMMESSA] Aggiornamento commessa {commessa_id} inviato al buffer WebSocket per device {device_id}")

def update_commessa_count(device_id: int, detected_class: str):
    """Aggiorna il conteggio per una classe specifica nella commessa corrente."""
    try:
        current_commessa_id = get_current_commessa(device_id)
        if not current_commessa_id:
            _app.logger.warning(f"[COMMESSA] Nessuna commessa trovata per device {device_id}")
            return
        
        commesse = _app.config.get('COMMESSE', {})
        if current_commessa_id not in commesse:
            _app.logger.warning(f"[COMMESSA] Commessa {current_commessa_id} non trovata nel config")
            return
        
        commessa_data = commesse[current_commessa_id]
        if 'articoli' not in commessa_data:
            _app.logger.warning(f"[COMMESSA] Nessun articolo trovato nella commessa {current_commessa_id}")
            return
            
        articoli_keys = [code.lower() for code in commessa_data['articoli'].keys()]
        if detected_class.lower() not in articoli_keys:
            _app.logger.debug(f"[COMMESSA] Classe {detected_class} non corrisponde a nessun articolo nella commessa {current_commessa_id}")
            return
            
        for articolo_code, articolo_data in commessa_data['articoli'].items():
            if articolo_code.lower() == detected_class.lower():
                articolo_data['prodotti'] += 1
                _app.logger.info(f"[COMMESSA] Device {device_id} - Commessa {current_commessa_id} - Aggiornato conteggio {articolo_code}: {articolo_data['prodotti']}")
                send_commessa_update(device_id, current_commessa_id, commessa_data)
                break
                
    except Exception as e:
        _app.logger.error(f"[COMMESSA] Errore nell'aggiornamento commesse: {str(e)}", exc_info=True)


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
            sid = str(payload.get('source_id'))

            with _app.app_context():
                if action == 'list_cameras':
                    devices = Device.query.join(User).filter(User.user_type == 'ip_camera').all()
                    cams = [{
                        'name': str(d.id),
                        'description': json.loads(d.config).get('name', str(d.id)),
                        'status': 'running' if (vp := _app.video_pipelines.get(str(d.id))) and not vp._stop.is_set() else 'stopped',
                        'clients': vp.clients_active if vp else 0
                    } for d in devices]
                    await ws.send(ws_response('list_cameras', True, data=cams))
                    continue

                if action == 'start':
                    device = Device.query.join(User).filter(Device.id == int(sid), User.user_type == 'ip_camera').first()
                    if not device:
                        await ws.send(ws_response('start', False, error='unknown source_id'))
                        continue
                    if sid not in _app.video_pipelines:
                        device_cfg = json.loads(device.config)
                        pc = PipelineSettings(**device_cfg)
                        vp = VideoPipeline(pc, logger=_app.logger)

                        def _count_cb(data):
                            try:
                                with _app.app_context():
                                    # Gestione dei dati base
                                    track_var = get_or_create_variable(device.id, 'track_id', 'Track ID', 'numeric')
                                    track_var.set_value(str(data.get('track_id', '')))

                                    class_var = get_or_create_variable(device.id, 'class', 'Class')
                                    detected_class = str(data.get('class', ''))
                                    class_var.set_value(detected_class)

                                    direction_var = get_or_create_variable(device.id, 'direction', 'Direction')
                                    direction_var.set_value(str(data.get('direction', '')))
                                    
                                    model_var = get_or_create_variable(device.id, 'model_path', 'Model Path')
                                    model_var.set_value(str(data.get('model_path', '')))

                                    # Aggiorna il conteggio nella commessa corrente
                                    if detected_class:
                                        _app.logger.info(f"[COMMESSA] Count callback - Device: {device.id}, Class: {detected_class}, Data: {data}")
                                        update_commessa_count(device.id, detected_class)

                                    # # Aggiungi i dati metriche standard
                                    # _batch_buffer.append({
                                    #     'action': 'get_metrics',
                                    #     'source_id': sid,
                                    #     'data': _app.video_pipelines[sid].metrics()
                                    # })
                            except Exception as e:
                                _app.logger.error(f"Error in count callback: {str(e)}")

                        vp.register_callback('count', _count_cb)
                        _app.video_pipelines[sid] = vp

                        _app.video_pipelines[sid].start()
                        
                        # Invia la commessa corrente se esiste
                        current_commessa_id = get_current_commessa(device.id)
                        if current_commessa_id:
                            commesse = _app.config.get('COMMESSE', {})
                            if current_commessa_id in commesse:
                                send_commessa_update(device.id, current_commessa_id, commesse[current_commessa_id])
                        
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

                if action == 'set_commessa':
                    device = Device.query.join(User).filter(Device.id == int(sid), User.user_type == 'ip_camera').first()
                    if not device:
                        await ws.send(ws_response('set_commessa', False, error='unknown source_id'))
                        continue
                    
                    commessa_id = payload.get('commessa_id')
                    if not commessa_id:
                        await ws.send(ws_response('set_commessa', False, error='missing commessa_id'))
                        continue
                    
                    # Verifica che la commessa esista nel config
                    commesse = _app.config.get('COMMESSE', {})
                    if commessa_id not in commesse:
                        await ws.send(ws_response('set_commessa', False, error='commessa not found'))
                        continue
                    
                    # Salva la commessa corrente nel database
                    commessa_var = get_or_create_variable(device.id, 'commessa', 'Commessa Corrente')
                    commessa_var.set_value(commessa_id)
                    
                    # Invia i dati della commessa al client
                    send_commessa_update(device.id, commessa_id, commesse[commessa_id])
                    # await ws.send(ws_response('set_commessa', True, sid))
                    continue

                if action == 'reset_counters':
                    device = Device.query.join(User).filter(Device.id == int(sid), User.user_type == 'ip_camera').first()
                    if not device:
                        await ws.send(ws_response('reset_counters', False, error='unknown source_id'))
                        continue
                    
                    # Reset solo i contatori della commessa corrente
                    current_commessa_id = get_current_commessa(device.id)
                    if not current_commessa_id:
                        await ws.send(ws_response('reset_counters', False, error='no current commessa'))
                        continue
                    
                    # Lavora direttamente su COMMESSE nel config
                    commesse = _app.config.get('COMMESSE', {})
                    if current_commessa_id not in commesse:
                        await ws.send(ws_response('reset_counters', False, error='commessa not found'))
                        continue
                    
                    # Azzera i contatori della commessa corrente
                    commessa_data = commesse[current_commessa_id]
                    if 'articoli' in commessa_data:
                        for articolo_data in commessa_data['articoli'].values():
                            articolo_data['prodotti'] = 0
                    
                    # Invia sempre i dati aggiornati della commessa
                    send_commessa_update(device.id, current_commessa_id, commessa_data)
                    await ws.send(ws_response('reset_counters', True, sid))
                    continue

                if action == 'get_commesse':
                    device = Device.query.join(User).filter(Device.id == int(sid), User.user_type == 'ip_camera').first()
                    if not device:
                        await ws.send(ws_response('get_commesse', False, error='unknown source_id'))
                        continue
                    
                    current_commessa_id = get_current_commessa(device.id)
                    
                    # Invia la commessa corrente se esiste
                    if current_commessa_id:
                        commesse = _app.config.get('COMMESSE', {})
                        if current_commessa_id in commesse:
                            send_commessa_update(device.id, current_commessa_id, commesse[current_commessa_id])
                        else:
                            await ws.send(ws_response('get_commesse', False, error='current commessa not found'))
                    else:
                        await ws.send(ws_response('get_commesse', False, error='no current commessa'))
                    continue

                if action == 'reset_commessa':
                    device = Device.query.join(User).filter(Device.id == int(sid), User.user_type == 'ip_camera').first()
                    if not device:
                        await ws.send(ws_response('reset_commessa', False, error='unknown source_id'))
                        continue
                    
                    # Rimuovi la commessa corrente dal database
                    commessa_var = Variables.query.filter_by(device_id=device.id, variable_code='commessa').first()
                    if commessa_var:
                        db.session.delete(commessa_var)
                        db.session.commit()
                    
                    # Invia sempre send_commessa_update con dati vuoti per resettare l'interfaccia
                    send_commessa_update(device.id, None, None)
                    await ws.send(ws_response('reset_commessa', True, sid))
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
