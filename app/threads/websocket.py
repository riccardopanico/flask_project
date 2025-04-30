import asyncio
import websockets
import json
from flask import Flask
from app import websocket_queue
from app.utils.video_pipeline import VideoPipeline, PipelineConfig

HOST = '0.0.0.0'
PORT = 8765

_connected = set()    # client WebSocket attivi
_app: Flask = None    # sarà settata in run()
_loop: asyncio.AbstractEventLoop = None
_server = None


def error_response(action: str, error: str, success=False):
    return json.dumps({"action": action, "success": success, "error": error})


def success_response(action: str, source_id: str, extra: dict = None):
    base = {"action": action, "success": True, "source_id": source_id}
    if extra:
        base.update(extra)
    return json.dumps(base)


async def socket_handler(ws, path):
    _connected.add(ws)
    try:
        async for msg in ws:
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                await ws.send(error_response("invalid", "invalid JSON"))
                continue

            action = data.get("action")
            sid = data.get("source_id")
            cfg = data.get("config")

            with _app.app_context():
                cfgs = _app.config.get("PIPELINE_CONFIGS", {})

                if action == "list_cameras":
                    cams = []
                    for src in cfgs:
                        vp = _app.video_pipelines.get(src)
                        status = "running" if vp and not vp._stop.is_set() else "stopped"
                        clients = vp.clients_active if vp else 0
                        cams.append({"name": src, "status": status, "clients": clients})
                    await ws.send(json.dumps({"action": "list_cameras", "data": cams}))

                elif action == "start":
                    if not sid:
                        await ws.send(error_response(action, "missing source_id")); continue
                    if sid in cfgs:
                        if sid not in _app.video_pipelines:
                            pipeline_cfg = PipelineConfig(**cfgs[sid])
                            vp = VideoPipeline(pipeline_cfg, logger=_app.logger)
                            _app.video_pipelines[sid] = vp
                        _app.video_pipelines[sid].start()
                        await ws.send(success_response("start", sid))
                    else:
                        await ws.send(error_response(action, "unknown source_id"))

                elif action == "stop":
                    if not sid:
                        await ws.send(error_response(action, "missing source_id")); continue
                    vp = _app.video_pipelines.get(sid)
                    if vp:
                        vp.stop()
                        _app.video_pipelines.pop(sid, None)
                        await ws.send(success_response("stop", sid))
                    else:
                        await ws.send(error_response(action, "not running"))

                elif action == "update_config":
                    if not sid or not cfg:
                        await ws.send(error_response(action, "missing parameters")); continue
                    vp = _app.video_pipelines.get(sid)
                    if not vp:
                        await ws.send(error_response(action, "not running")); continue
                    try:
                        vp.update_config(**cfg)
                        await ws.send(success_response("update_config", sid))
                    except Exception as e:
                        await ws.send(error_response(action, str(e)))

                elif action == "get_health":
                    if not sid:
                        await ws.send(error_response(action, "missing source_id")); continue
                    vp = _app.video_pipelines.get(sid)
                    if vp:
                        h = vp.health()
                        await ws.send(json.dumps({"action": "health", "data": h, "source_id": sid}))
                    else:
                        await ws.send(error_response(action, "not running"))

                elif action == "get_metrics":
                    if not sid:
                        await ws.send(error_response(action, "missing source_id")); continue
                    vp = _app.video_pipelines.get(sid)
                    if vp:
                        m = vp.metrics()
                        await ws.send(json.dumps({"action": "metrics", "data": m, "source_id": sid}))
                    else:
                        await ws.send(error_response(action, "not running"))

                elif action == "get_config":
                    if not sid:
                        await ws.send(error_response(action, "missing source_id")); continue
                    vp = _app.video_pipelines.get(sid)
                    if vp:
                        c = vp.export_config()
                        await ws.send(json.dumps({"action": "get_config", "data": c, "source_id": sid}))
                    else:
                        await ws.send(error_response(action, "not running"))

                else:
                    await ws.send(error_response("unknown", "unknown action"))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _connected.discard(ws)


async def _broadcast(msg: str):
    if _connected:
        await asyncio.gather(*[ws.send(msg) for ws in _connected if ws.open], return_exceptions=True)


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
