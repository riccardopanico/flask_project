import asyncio
import websockets
import json
import subprocess

HOST = '0.0.0.0'  
PORT = 8765  
connected_clients = set()

async def socket_handler(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Ricevuto: {message}")
            try:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    print("Messaggio non in formato JSON, ignorato.")
                    continue
                if "action" in data:
                    action = data["action"]
                    if action == "ping":
                        await websocket.send(json.dumps({"message": "pong"}))
                    elif action == "poweroff":
                        print("Esecuzione comando poweroff...")
                        subprocess.run(["clear"], shell=True)
                        subprocess.run(["sudo", "systemctl", "stop", "getty@tty1.service"], shell=False)
                        subprocess.run(["sudo", "poweroff", "--no-wall"], shell=False)
                        await websocket.send(json.dumps({"action": "poweringOff"}))
                    elif action == "reboot":
                        print("Esecuzione comando reboot...")
                        subprocess.run(["clear"], shell=True)
                        subprocess_result = subprocess.run(["sudo", "systemctl", "stop", "getty@tty1.service"], shell=False)
                        if subprocess_result.returncode == 0:
                            subprocess_result = subprocess.run(["sudo", "reboot", "--no-wall"], shell=False)
                        await websocket.send(json.dumps({"action": "rebooting"}))
                    else:
                        print(f"Azione non riconosciuta: {action}")
                    await websocket.send(json.dumps({"action": "readyForNext"}))
                else:
                    print("Messaggio JSON non valido, manca la chiave 'action'.")
            except Exception as e:
                print(f"Errore nella gestione del messaggio: {e}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connessione chiusa: {e}")
    finally:
        connected_clients.remove(websocket)
        print("Client disconnesso")

async def start_websocket_server():
    async with websockets.serve(socket_handler, HOST, PORT):
        print(f"Server WebSocket avviato su ws://{HOST}:{PORT}")
        await asyncio.Future()  

async def broadcast_message(message):
    if connected_clients:
        await asyncio.wait([client.send(message) for client in connected_clients])

def run(app):
    with app.app_context():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_websocket_server())