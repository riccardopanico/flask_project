import asyncio
import json
import threading
import websockets
from flask import Flask, current_app
from app import websocket_queue, db
from app.models.device import Device
from app.models.user import User
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


def get_or_create_variable(device_id: int, code: str, name: str, value_type: str = 'string'):
    """Helper function to get or create a variable for a device."""
    var = Variables.query.filter_by(device_id=device_id, variable_code=code).first()
    if not var:
        var = Variables(device_id=device_id, variable_code=code, variable_name=name)
        db.session.add(var)
        db.session.commit()
    return var


def handle_commessa_scaling(device_id: int, sid: str, detected_class: str):
    """
    Gestisce il meccanismo di scaling delle commesse quando viene rilevato un oggetto.
    Incrementa i contatori appropriati e invia aggiornamenti in tempo reale.
    """
    try:
        # Verifica se c'è una commessa attiva
        commessa_var = Variables.query.filter_by(device_id=device_id, variable_code='commessa').first()
        if not (commessa_var and commessa_var.get_value() and str(commessa_var.get_value()).strip()):
            return
        
        commessa_active = str(commessa_var.get_value()).strip()
        
        # Ottieni i dati della commessa dal config
        available_commesse = current_app.config.get('COMMESSE', {})
        commessa_config = available_commesse.get(commessa_active)
        
        if not commessa_config:
            return
        
        # Cerca corrispondenze tra classe rilevata e modelli della commessa
        system_keys = {'codice_commessa', 'descrizione'}
        matched_model = None
        
        for model_key, model_data in commessa_config.items():
            if (model_key not in system_keys and 
                isinstance(model_data, dict) and 
                'nome_articolo' in model_data):
                
                # Mappatura: classe YOLO -> modello commessa
                if detected_class.lower() == model_key.lower():
                    matched_model = model_key
                    break
        
        if not matched_model:
            return
        
        # Ottieni/crea variabile per il contatore di questo modello
        counter_var_code = f'commessa_{commessa_active}_{matched_model}_count'
        counter_var = Variables.query.filter_by(device_id=device_id, variable_code=counter_var_code).first()
        if not counter_var:
            counter_var = Variables(
                device_id=device_id,
                variable_code=counter_var_code,
                variable_name=f'Contatore {matched_model} Commessa {commessa_active}'
            )
            db.session.add(counter_var)
            db.session.commit()
        
        # SEMPRE QUERY FRESCA per evitare cache stale
        fresh_counter = Variables.query.filter_by(device_id=device_id, variable_code=counter_var_code).first()
        if fresh_counter:
            current_count = fresh_counter.get_value() or 0
            if isinstance(current_count, str):
                current_count = int(current_count) if current_count.isdigit() else 0
            new_count = current_count + 1
            fresh_counter.set_value(new_count)
        else:
            current_count = 0
            new_count = 1
            counter_var.set_value(new_count)
        
        # Invia aggiornamento in tempo reale alla GUI
        _batch_buffer.append({
            'action': 'update_commessa_count',
            'source_id': sid,
            'data': {
                'commessa': commessa_active,
                'model_key': matched_model,
                'new_count': new_count,
                'total_required': commessa_config[matched_model].get('totale_da_produrre', 0)
            }
        })
        
    except Exception as e:
        _app.logger.error(f"Error in commessa scaling: {str(e)}")


async def handle_reset_commessa(sid: str):
    """Gestisce il reset completo di una commessa (azzera commessa e tutti i contatori)."""
    try:
        device = Device.query.join(User).filter(Device.id == int(sid), User.user_type == 'ip_camera').first()
        if not device:
            return ws_response('reset_commessa', False, sid, error='Device not found')
        
        # Ottieni la commessa attuale prima di resettarla (per azzerare i contatori)
        commessa_var = Variables.query.filter_by(device_id=device.id, variable_code='commessa').first()
        current_commessa = None
        if commessa_var and commessa_var.get_value():
            current_commessa = str(commessa_var.get_value()).strip() if str(commessa_var.get_value()).strip() else None
        
        # Reset della commessa
        if commessa_var:
            commessa_var.set_value("")
        
        # Reset dei dati commessa
        commessa_data_var = Variables.query.filter_by(device_id=device.id, variable_code='commessa_data').first()
        if commessa_data_var:
            commessa_data_var.set_value("")
        
        # RESET: Azzera tutti i contatori della commessa
        if current_commessa:
            # Trova tutti i contatori esistenti per questo device  
            all_vars = Variables.query.filter_by(device_id=device.id).all()
            
            # Cerchiamo specificamente i contatori della commessa
            counter_prefix = f'commessa_{current_commessa}_'
            counter_suffix = '_count'
            matching_counters = []
            
            for var in all_vars:
                if var.variable_code.startswith(counter_prefix) and var.variable_code.endswith(counter_suffix):
                    matching_counters.append(var)
            
            for counter_var in matching_counters:
                counter_var.set_value(0)
        
        return ws_response('reset_commessa', True, sid)
        
    except Exception as e:
        _app.logger.error(f'[WEBSOCKET] Error resetting commessa: {str(e)}')
        return ws_response('reset_commessa', False, sid, error='Internal server error')


async def handle_reset_counters(sid: str):
    """Gestisce il reset dei soli contatori di una commessa attiva (mantiene la commessa attiva)."""
    try:
        device = Device.query.join(User).filter(Device.id == int(sid), User.user_type == 'ip_camera').first()
        if not device:
            _app.logger.error(f'Device not found for id: {sid}')
            return ws_response('reset_counters', False, sid, error='Device not found')
        
        # Ottieni la commessa attuale
        commessa_var = Variables.query.filter_by(device_id=device.id, variable_code='commessa').first()
        if not commessa_var or not commessa_var.get_value():
            _app.logger.error(f'No active commessa found')
            return ws_response('reset_counters', False, sid, error='No active commessa found')
        
        raw_commessa_value = commessa_var.get_value()
        current_commessa = str(raw_commessa_value).strip() if str(raw_commessa_value).strip() else None
        if not current_commessa:
            _app.logger.error(f'Invalid active commessa - raw: {raw_commessa_value}')
            return ws_response('reset_counters', False, sid, error='Invalid active commessa')
        
        # Azzera tutti i contatori della commessa attiva
        all_vars = Variables.query.filter_by(device_id=device.id).all()
        
        # Cerchiamo specificamente i contatori della commessa
        counter_prefix = f'commessa_{current_commessa}_'
        counter_suffix = '_count'
        matching_counters = []
        
        for var in all_vars:
            if var.variable_code.startswith(counter_prefix) and var.variable_code.endswith(counter_suffix):
                matching_counters.append(var)
        
        reset_count = 0
        for counter_var in matching_counters:
            counter_var.set_value(0)
            reset_count += 1
        
        # Invia aggiornamento alla GUI per tutti i modelli azzerati
        available_commesse = current_app.config.get('COMMESSE', {})
        commessa_config = available_commesse.get(current_commessa)
        if commessa_config:
            system_keys = {'codice_commessa', 'descrizione'}
            for model_key, model_data in commessa_config.items():
                if (model_key not in system_keys and 
                    isinstance(model_data, dict) and 
                    'nome_articolo' in model_data):
                    _batch_buffer.append({
                        'action': 'update_commessa_count',
                        'source_id': sid,
                        'data': {
                            'commessa': current_commessa,
                            'model_key': model_key,
                            'new_count': 0,
                            'total_required': model_data.get('totale_da_produrre', 0)
                        }
                    })
        
        return ws_response('reset_counters', True, sid, data={'reset_count': reset_count})
        
    except Exception as e:
        _app.logger.error(f'Error resetting counters: {str(e)}')
        return ws_response('reset_counters', False, sid, error='Internal server error')


async def handle_set_commessa(sid: str, payload: dict):
    """Gestisce l'impostazione di una nuova commessa."""
    try:
        device = Device.query.join(User).filter(Device.id == int(sid), User.user_type == 'ip_camera').first()
        if not device:
            _app.logger.warning(f'[WEBSOCKET] Device not found for id: {sid}')
            return ws_response('set_commessa', False, sid, error='Device not found')
        
        commessa_data = payload.get('data', {})
        commessa_value = commessa_data.get('commessa')
        
        if not commessa_value or not isinstance(commessa_value, str) or not commessa_value.strip():
            _app.logger.warning(f'[WEBSOCKET] Invalid commessa value: {commessa_value}')
            return ws_response('set_commessa', False, sid, error='Invalid commessa value')
        
        # Validazione commessa contro config
        commessa_str = str(commessa_value).strip()
        available_commesse = current_app.config.get('COMMESSE', {})
        
        if commessa_str not in available_commesse:
            _app.logger.warning(f'[WEBSOCKET] Commessa {commessa_str} not found in available commesse')
            return ws_response('set_commessa', False, sid, error=f'Commessa {commessa_str} non trovata. Commesse disponibili: {", ".join(available_commesse.keys())}')
        
        commessa_config = available_commesse[commessa_str]
        
        # Trova o crea la variabile commessa per questo device
        commessa_var = get_or_create_variable(device.id, 'commessa', 'Codice Commessa')
        
        # Salva anche i dati completi della commessa in una variabile separata
        commessa_data_var = get_or_create_variable(device.id, 'commessa_data', 'Dati Commessa')
        
        # Imposta i valori
        commessa_var.set_value(commessa_str)
        commessa_data_var.set_value(json.dumps(commessa_config))
        
        # Prepara i dati dei modelli dinamicamente
        modelli = {}
        system_keys = {'codice_commessa', 'descrizione'}
        
        for key, value in commessa_config.items():
            if key not in system_keys and isinstance(value, dict) and 'nome_articolo' in value:
                # Ottieni il contatore attuale per questo modello
                counter_var_code = f'commessa_{commessa_str}_{key}_count'
                counter_var = Variables.query.filter_by(device_id=device.id, variable_code=counter_var_code).first()
                current_count = 0
                if counter_var:
                    count_value = counter_var.get_value()
                    if isinstance(count_value, str) and count_value.isdigit():
                        current_count = int(count_value)
                    elif isinstance(count_value, (int, float)):
                        current_count = int(count_value)
                
                # Aggiungi il contatore attuale ai dati del modello
                model_data = value.copy()
                model_data['prodotti'] = current_count
                modelli[key] = model_data
        
        response_data = {
            'commessa': commessa_str,
            'descrizione': commessa_config.get('descrizione', ''),
            'modelli': modelli
        }
        
        return ws_response('set_commessa', True, sid, data=response_data)
        
    except ValueError as e:
        _app.logger.error(f'[WEBSOCKET] ValueError: {e}')
        return ws_response('set_commessa', False, sid, error='Invalid device ID')
    except Exception as e:
        _app.logger.error(f'[WEBSOCKET] Exception: {str(e)}')
        return ws_response('set_commessa', False, sid, error='Internal server error')


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

                                    # ===== MECCANISMO DI SCALING COMMESSE =====
                                    
                                    handle_commessa_scaling(device.id, sid, detected_class)

                                    # Aggiungi i dati metriche standard
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

                if action == 'set_commessa':
                    response = await handle_set_commessa(sid, payload)
                    await ws.send(response)
                    continue

                if action == 'reset_commessa':
                    response = await handle_reset_commessa(sid)
                    await ws.send(response)
                    continue

                if action == 'reset_counters':
                    response = await handle_reset_counters(sid)
                    await ws.send(response)
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
