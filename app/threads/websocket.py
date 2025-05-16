import asyncio
import websockets
import json
from flask import Flask
from app import websocket_queue
from app.utils.video_pipeline import VideoPipeline, PipelineSettings

HOST = '0.0.0.0'
PORT = 8765

_connected = set()
_app: Flask = None
_loop: asyncio.AbstractEventLoop = None
_server = None

def error_response(action: str, error: str, success: bool = False):
    return json.dumps({"action": action, "success": success, "error": error})

def success_response(action: str, source_id: str, extra: dict = None):
    res = {"action": action, "success": True, "source_id": source_id}
    if extra:
        res.update(extra)
    return json.dumps(res)

def ws_response(action: str, success: bool = True, source_id: str = None, data=None, error: str = None):
    res = {
        "action": action,
        "success": success
    }
    if source_id:
        res["source_id"] = source_id
    if data is not None:
        res["data"] = data
    if not success and error:
        res["error"] = error
    return json.dumps(res)

async def socket_handler(ws, path):
    _connected.add(ws)
    try:
        async for msg in ws:
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                await ws.send(ws_response("invalid", success=False, error="Invalid JSON"))
                continue

            action = data.get("action")
            sid = data.get("source_id")
            cfg = data.get("config")

            with _app.app_context():
                cfgs = _app.config.get("PIPELINE_CONFIGS", {})

                if action == "list_cameras":
                    cams = []
                    for src, conf in cfgs.items():
                        vp = _app.video_pipelines.get(src)
                        running = bool(vp and not vp._stop.is_set())
                        cams.append({
                            "name": src,
                            "status": "running" if running else "stopped",
                            "clients": vp.clients_active if vp else 0
                        })
                    await ws.send(ws_response("list_cameras", data=cams))
                    continue

                if action == "start":
                    if not sid:
                        await ws.send(ws_response("start", success=False, error="missing source_id"))
                        continue
                    if sid not in cfgs:
                        await ws.send(ws_response("start", success=False, error="unknown source_id"))
                        continue
                    if sid not in _app.video_pipelines:
                        pc = PipelineSettings(**cfgs[sid])
                        vp = VideoPipeline(pc, logger=_app.logger)
                        _app.video_pipelines[sid] = vp
                    vp = _app.video_pipelines[sid]
                    # Registra il callback per l'evento on_count in forma compatta
                    vp.register_callback('count', lambda data: _app.logger.info(data))
                    vp.start()
                    await ws.send(ws_response("start", source_id=sid))
                    continue

                if action == "stop":
                    if not sid:
                        await ws.send(ws_response("stop", success=False, error="missing source_id"))
                        continue
                    vp = _app.video_pipelines.get(sid)
                    if not vp:
                        await ws.send(ws_response("stop", success=False, error="not running"))
                        continue
                    vp.stop()
                    _app.video_pipelines.pop(sid, None)
                    await ws.send(ws_response("stop", source_id=sid))
                    continue

                if action == "update_config":
                    if not sid or not cfg:
                        await ws.send(ws_response("update_config", success=False, error="missing parameters"))
                        continue
                    vp = _app.video_pipelines.get(sid)
                    if not vp:
                        await ws.send(ws_response("update_config", success=False, error="not running"))
                        continue
                    try:
                        vp.update_config(**cfg)
                        await ws.send(ws_response("update_config", source_id=sid))
                    except Exception as e:
                        await ws.send(ws_response("update_config", success=False, error=str(e)))
                    continue

                if action == "get_health":
                    if not sid:
                        await ws.send(ws_response("get_health", success=False, error="missing source_id"))
                        continue
                    vp = _app.video_pipelines.get(sid)
                    if not vp:
                        await ws.send(ws_response("get_health", success=False, error="not running"))
                        continue
                    h = vp.health()
                    await ws.send(ws_response("get_health", source_id=sid, data=h))
                    continue

                if action == "get_metrics":
                    if not sid:
                        await ws.send(ws_response("get_metrics", success=False, error="missing source_id"))
                        continue
                    vp = _app.video_pipelines.get(sid)
                    if not vp:
                        await ws.send(ws_response("get_metrics", success=False, error="not running"))
                        continue
                    m = vp.metrics()
                    await ws.send(ws_response("get_metrics", source_id=sid, data=m))
                    continue

                if action == "get_config":
                    if not sid:
                        await ws.send(ws_response("get_config", success=False, error="missing source_id"))
                        continue
                    vp = _app.video_pipelines.get(sid)
                    if not vp:
                        await ws.send(ws_response("get_config", success=False, error="not running"))
                        continue
                    c = vp.export_config()
                    await ws.send(ws_response("get_config", source_id=sid, data=c))
                    continue

                await ws.send(ws_response("unknown", success=False, error="Unknown action"))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _connected.discard(ws)

async def _broadcast(msg: str):
    if _connected:
        await asyncio.gather(*[ws.send(msg) for ws in _connected if ws.open],
                             return_exceptions=True)

async def _queue_reader():
    while True:
        message = await asyncio.to_thread(websocket_queue.get)
        await _broadcast(json.dumps(message))

async def _start_server():
    global _server
    _server = await websockets.serve(socket_handler, HOST, PORT)
    _app.logger.info(f"WebSocket server running on ws://{HOST}:{PORT}")
    await _server.wait_closed()

def run(app):
    global _app, _loop
    _app = app
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    _loop.create_task(_start_server())
    _loop.create_task(_queue_reader())
    _loop.run_forever()
