# app/threads/websocket.py

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


async def socket_handler(ws, path):
    """Accoglie comandi dal front-end e risponde."""
    _connected.add(ws)
    try:
        async for msg in ws:
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                await ws.send(json.dumps({"error": "invalid JSON"}))
                continue

            action = data.get("action")
            # 1) lista camere disponibili
            if action == "list_cameras":
                cams = []
                with _app.app_context():
                    cfgs = _app.config.get("PIPELINE_CONFIGS", {})
                    for src in cfgs:
                        vp = _app.video_pipelines.get(src)
                        status = "running" if vp and not vp._stop.is_set() else "stopped"
                        clients = vp.clients_active if vp else 0
                        cams.append({"name": src, "status": status, "clients": clients})
                await ws.send(json.dumps({"action": "list_cameras", "data": cams}))

            # 2) avvia pipeline
            elif action == "start":
                sid = data.get("source_id")
                with _app.app_context():
                    cfgs = _app.config.get("PIPELINE_CONFIGS", {})
                    if sid in cfgs:
                        if sid not in _app.video_pipelines:
                            cfg = PipelineConfig(**cfgs[sid])
                            vp = VideoPipeline(cfg, logger=_app.logger)
                            _app.video_pipelines[sid] = vp
                        _app.video_pipelines[sid].start()
                        await ws.send(json.dumps({"action": "start", "success": True, "source_id": sid}))
                    else:
                        await ws.send(json.dumps({"action": "start", "success": False, "error": "unknown source_id"}))

            # 3) ferma pipeline
            elif action == "stop":
                sid = data.get("source_id")
                with _app.app_context():
                    vp = _app.video_pipelines.get(sid)
                    if vp:
                        vp.stop()
                        _app.video_pipelines.pop(sid, None)
                        await ws.send(json.dumps({"action": "stop", "success": True, "source_id": sid}))
                    else:
                        await ws.send(json.dumps({"action": "stop", "success": False, "error": "not running"}))

            # 4) aggiorna config live
            elif action == "update_config":
                sid = data.get("source_id")
                cfg = data.get("config")
                if not sid or not cfg:
                    await ws.send(json.dumps({"action": "update_config", "success": False, "error": "missing parameters"}))
                    continue
                with _app.app_context():
                    vp = _app.video_pipelines.get(sid)
                    if not vp:
                        await ws.send(json.dumps({"action": "update_config", "success": False, "error": "not running"}))
                        continue
                    try:
                        vp.update_config(**cfg)
                        await ws.send(json.dumps({"action": "update_config", "success": True, "source_id": sid}))
                    except Exception as e:
                        await ws.send(json.dumps({"action": "update_config", "success": False, "error": str(e)}))

            # 5) health check
            elif action == "get_health":
                sid = data.get("source_id")
                with _app.app_context():
                    vp = _app.video_pipelines.get(sid)
                    if vp:
                        h = vp.health()
                        await ws.send(json.dumps({"action": "health", "data": h, "source_id": sid}))
                    else:
                        await ws.send(json.dumps({"action": "health", "error": "not running"}))

            # 6) metriche
            elif action == "get_metrics":
                sid = data.get("source_id")
                with _app.app_context():
                    vp = _app.video_pipelines.get(sid)
                    if vp:
                        m = vp.metrics()
                        await ws.send(json.dumps({"action": "metrics", "data": m, "source_id": sid}))
                    else:
                        await ws.send(json.dumps({"action": "metrics", "error": "not running"}))

            else:
                await ws.send(json.dumps({"error": "unknown action"}))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _connected.discard(ws)


async def _broadcast(msg: str):
    """Invia a tutti i client connessi."""
    if _connected:
        await asyncio.gather(*[ws.send(msg) for ws in _connected if ws.open], return_exceptions=True)


async def _queue_reader():
    """Legge dalla coda websocket_queue e rilancia via WebSocket."""
    while True:
        message = await asyncio.to_thread(websocket_queue.get)
        # ci si aspetta che message sia già un dict JSON-serializable
        await _broadcast(json.dumps(message))


async def _start_server():
    global _server
    _server = await websockets.serve(socket_handler, HOST, PORT)
    _app.logger.info(f"WebSocket server running on ws://{HOST}:{PORT}")
    await _server.wait_closed()


def run(app):
    """Avviato automaticamente da app/__init__.py come thread."""
    global _app, _loop
    _app = app
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    # metti in coda la lettura eventi dalla pipeline
    _loop.create_task(_start_server())
    _loop.create_task(_queue_reader())
    _loop.run_forever()
