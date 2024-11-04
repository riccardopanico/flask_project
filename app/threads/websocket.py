import asyncio
import websockets
import json
import subprocess
from app import db
from app.models.impostazioni import Impostazioni
from sqlalchemy.orm import sessionmaker

HOST = '0.0.0.0'  
PORT = 8765  
connected_clients = set()

# Handler per ogni connessione WebSocket
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
                    elif action == "reboot":
                        print("Esecuzione comando reboot...")
                        subprocess.run(["clear"], shell=True)
                        subprocess_result = subprocess.run(["sudo", "systemctl", "stop", "getty@tty1.service"], shell=False)
                        if subprocess_result.returncode == 0:
                            subprocess_result = subprocess.run(["sudo", "reboot", "--no-wall"], shell=False)
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

# Controlla periodicamente se l'alert spola deve essere inviato
async def check_alert_spola(app):
    with app.app_context():
        while True:
            await asyncio.sleep(5)  # Controlla ogni 5 secondi
            try:
                Session = sessionmaker(bind=db.engine)
                session = Session()
                # Ottieni il valore dell'impostazione 'alert_spola'
                alert_spola = session.query(Impostazioni).filter_by(codice='alert_spola').first()
                if alert_spola and alert_spola.valore == '1':
                    print("Alert spola attivato, invio messaggio ai client connessi...")
                    message = json.dumps({"action": "alert_spola"})
                    await broadcast_message(message)
                    # Resetta l'impostazione alert_spola dopo l'invio
                    alert_spola.valore = '0'
                    session.commit()
            except Exception as e:
                print(f"Errore durante il controllo dell'alert spola: {e}")
            finally:
                session.close()

# Invia un messaggio a tutti i client connessi
async def broadcast_message(message):
    if connected_clients:
        await asyncio.gather(*[client.send(message) for client in connected_clients if client.open])

# Avvia il server WebSocket
async def start_websocket_server():
    async with websockets.serve(socket_handler, HOST, PORT):
        print(f"Server WebSocket avviato su ws://{HOST}:{PORT}")
        await asyncio.Future()  # Mantiene il server in esecuzione

def run(app):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Avvia il server WebSocket e il task di controllo alert_spola
    loop.create_task(start_websocket_server())
    loop.create_task(check_alert_spola(app))
    loop.run_forever()
