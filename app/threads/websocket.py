import asyncio
import websockets
import threading
import json
import subprocess
from flask import current_app

# Configurazione
# HOST = 'localhost'  # IP locale della macchina
HOST = '0.0.0.0'  # IP pubblico
PORT = 8765  # Porta di comunicazione WebSocket

# Set per tenere traccia dei client connessi
connected_clients = set()

# Funzione per gestire le connessioni WebSocket
async def socket_handler(websocket, path):
    # Aggiungi il client alla lista dei client connessi
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Ricevuto: {message}")
            try:
                # Tenta di decodificare il messaggio come JSON
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    print("Messaggio non in formato JSON, ignorato.")
                    continue
                
                # Controlla e gestisci i comandi nel messaggio JSON
                if "custom_msg" in data:
                    await broadcast_message(json.dumps({
                        "message": data.get("msg", ""),
                        "autoclose": data.get("autoclose", False),
                        "timer": data.get("timer", 0)
                    }))
                if "spegni" in data:
                    subprocess.run(["clear", "&&", "sudo", "systemctl", "stop", "getty@tty1.service", "&&", "sudo", "poweroff", "--no-wall"], shell=True)
                if "riavvia" in data:
                    subprocess.run(["clear", "&&", "sudo", "systemctl", "stop", "getty@tty1.service", "&&", "sudo", "reboot", "--no-wall"], shell=True)
            except Exception as e:
                print(f"Errore nella gestione del messaggio: {e}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connessione chiusa: {e}")
    finally:
        # Rimuovi il client dalla lista quando la connessione si chiude
        connected_clients.remove(websocket)
        print("Client disconnesso")

# Funzione per avviare il server WebSocket
async def start_websocket_server():
    async with websockets.serve(socket_handler, HOST, PORT):
        print(f"Server WebSocket avviato su ws://{HOST}:{PORT}")
        await asyncio.Future()  # Mantieni il server attivo

# Funzione per inviare un messaggio a tutti i client connessi
async def broadcast_message(message):
    if connected_clients:
        await asyncio.wait([client.send(message) for client in connected_clients])

# Funzione per avviare il server WebSocket come thread, utilizzando il contesto dell'app Flask
def run(app):
    # Utilizza il contesto dell'app Flask per accedere ai servizi dell'applicazione
    with app.app_context():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_websocket_server())
