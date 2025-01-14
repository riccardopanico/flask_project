import asyncio
import websockets
import json
import subprocess
from app import db, websocket_queue
from app.models.variables import Variables
from app.models.log_data import LogData
from app.models.campionatura import Campionatura
from app.models.user import User
from app.models.device import Device
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
from datetime import datetime
import signal
import weakref

HOST = '0.0.0.0'
PORT = 8765
connected_clients = weakref.WeakSet()
loop = None
server = None

# Funzione per validare e caricare i messaggi JSON
def parse_json_message(message):
    try:
        return json.loads(message)
    except json.JSONDecodeError:
        print("Messaggio non in formato JSON, ignorato.")
        return None

# Handler per ogni connessione WebSocket
async def socket_handler(websocket, path):
    print(f"Client connesso: {websocket.remote_address}")
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Ricevuto: {message}")
            data = parse_json_message(message)
            if data is None:
                continue
            try:
                if "action" in data:
                    action = data["action"]
                    if action == "ping":
                        await websocket.send(json.dumps({"message": "pong"}))
                    elif action == "poweroff":
                        print("Esecuzione comando poweroff...")
                        subprocess.run(["clear"], shell=True)
                        subprocess.run(["sudo", "systemctl", "stop", "getty@tty1.service"], shell=False)
                        subprocess.run(["sudo", "systemctl", "stop", "flask.service"], shell=False)
                        subprocess.run(["sudo", "systemctl", "stop", "chromium-kiosk.service"], shell=False)
                        subprocess.run(["sudo", "poweroff", "--no-wall"], shell=False)
                    elif action == "reboot":
                        print("Esecuzione comando reboot...")
                        subprocess.run(["clear"], shell=True)
                        subprocess.run(["sudo", "systemctl", "stop", "getty@tty1.service"], shell=False)
                        subprocess.run(["sudo", "systemctl", "stop", "flask.service"], shell=False)
                        subprocess.run(["sudo", "systemctl", "stop", "chromium-kiosk.service"], shell=False)
                        subprocess.run(["sudo", "reboot", "--no-wall"], shell=False)
                    else:
                        print(f"Azione non riconosciuta: {action}")
                    await websocket.send(json.dumps({"action": "readyForNext"}))
                else:
                    print("Messaggio JSON non valido, manca la chiave 'action'.")
            except Exception as e:
                print(f"Errore nella gestione del messaggio: {e}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connessione chiusa: {e}")
    except Exception as e:
        print(f"Connessione chiusa o errore generico: {e}")
    finally:
        connected_clients.discard(websocket)
        print(f"Client disconnesso: {websocket.remote_address}")

async def check_queue_messages(app):
    with app.app_context():
        while True:
            try:
                # Ottiene il messaggio dalla coda (bloccante finché non arriva un messaggio)
                message = await asyncio.to_thread(websocket_queue.get)

                Session = sessionmaker(bind=db.engine)
                with Session() as session:
                    if message == "alert_spola":
                        print("Alert spola attivato, invio messaggio ai client connessi...")
                        await broadcast_message(json.dumps({"action": "alert_spola"}))
                    elif message == "alert_olio":
                        print("Alert olio attivato, invio messaggio ai client connessi...")
                        await broadcast_message(json.dumps({"action": "alert_olio"}))
                    elif message == "dati_orlatura":
                        print("Ottengo dati orlatura, invio messaggio ai client connessi...")

                        # Recupera interconnection_id da Variables
                        interconnection_id = int(session.query(Variables).filter_by(variable_code='interconnection_id').first().get_value())

                        # Recupera device_id con interconnection_id da Device
                        device_id = session.query(Device).filter_by(interconnection_id=interconnection_id).first().id

                        # Recupera commessa_id e valore corrente
                        commessa_var = session.query(Variables).filter_by(variable_code='commessa').first()
                        commessa_id = commessa_var.id if commessa_var else None
                        commessa_value = commessa_var.get_value() if commessa_var else None

                        # Recupera l'ID delle variabili per consumo e operatività
                        consumo_var_id = session.query(Variables).filter_by(variable_code='encoder_consumo').first().id
                        operativita_var_id = session.query(Variables).filter_by(variable_code='encoder_operativita').first().id

                        # Query per dati totali
                        consumo_totale = session.query(func.sum(LogData.numeric_value)).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == consumo_var_id
                        ).scalar() or 0
                        operativita_totale = session.query(func.sum(LogData.numeric_value)).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == operativita_var_id
                        ).scalar() or 0

                        # Trova i range di tempo per la commessa basato su variable_id e valore corrente
                        commessa_range = session.query(LogData.created_at).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == commessa_id,
                            LogData.string_value == commessa_value
                        ).order_by(LogData.created_at.asc()).first(), session.query(LogData.created_at).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == commessa_id,
                            LogData.string_value == commessa_value
                        ).order_by(LogData.created_at.desc()).first()

                        if commessa_range[0] and commessa_range[1]:
                            start_commessa, stop_commessa = commessa_range[0][0], commessa_range[1][0]
                        else:
                            start_commessa, stop_commessa = None, None

                        # Query per dati commessa usando il range di tempo
                        consumo_commessa = session.query(func.sum(LogData.numeric_value)).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == consumo_var_id,
                            LogData.created_at.between(start_commessa, stop_commessa)
                        ).scalar() or 0
                        operativita_commessa = session.query(func.sum(LogData.numeric_value)).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == operativita_var_id,
                            LogData.created_at.between(start_commessa, stop_commessa)
                        ).scalar() or 0

                        # Query per dati campionatura
                        last_campionatura = session.query(Campionatura.start, Campionatura.stop).order_by(Campionatura.id.desc()).first()
                        if last_campionatura:
                            start_campionatura = last_campionatura.start
                            stop_campionatura = last_campionatura.stop or datetime.now()
                        else:
                            start_campionatura, stop_campionatura = None, None

                        consumo_campionatura = session.query(func.sum(LogData.numeric_value)).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == consumo_var_id,
                            LogData.created_at.between(start_campionatura, stop_campionatura)
                        ).scalar() or 0
                        operativita_campionatura = session.query(func.sum(LogData.numeric_value)).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == operativita_var_id,
                            LogData.created_at.between(start_campionatura, stop_campionatura)
                        ).scalar() or 0

                        # Costruzione del dizionario dati orlatura
                        dati_orlatura = {
                            "consumo_totale": round(consumo_totale, 2),
                            "tempo_totale": round(operativita_totale, 2),
                            "consumo_commessa": round(consumo_commessa, 2),
                            "tempo_commessa": round(operativita_commessa, 2),
                            "consumo_campionatura": round(consumo_campionatura, 2),
                            "tempo_campionatura": round(operativita_campionatura, 2)
                        }

                        # Invio dei dati ai client
                        await broadcast_message(json.dumps({"action": "dati_orlatura", "data": dati_orlatura}))
                        session.commit()
            except Exception as e:
                print(f"Errore durante l'invio dell'alert spola: {e}")

# Invia un messaggio a tutti i client connessi
async def broadcast_message(message):
    if connected_clients:
        await asyncio.gather(*[client.send(message) for client in connected_clients if client.open])

# Avvia il server WebSocket
async def start_websocket_server():
    global server
    try:
        server = await websockets.serve(
            socket_handler, HOST, PORT,
            ping_interval=None,  # Disabilita il ping di keepalive
            ping_timeout=None,   # Disabilita il timeout per il ping
            max_size=None,       # Nessun limite alla dimensione del messaggio
            max_queue=100,       # Aumenta la dimensione della coda
            compression=None     # Disabilita la compressione per migliorare la stabilità
        )
        print(f"Server WebSocket avviato su ws://{HOST}:{PORT}")
        await server.wait_closed()  # Mantiene il server in esecuzione
    except asyncio.CancelledError:
        print("Server WebSocket terminato correttamente.")
    except Exception as e:
        print(f"Errore nel server WebSocket: {e}")

# Definisci un metodo per gestire la chiusura pulita
async def cleanup_and_stop_loop():
    print("Chiusura del loop di eventi...")
    tasks = [task for task in asyncio.all_tasks(loop)]
    for task in tasks:
        task.cancel()  # Cancella tutti i task
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    if server:  # Chiude il server WebSocket se è attivo
        server.close()
        await server.wait_closed()
    loop.stop()

# Funzione principale per avviare il servizio
def run(app):
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Avvia il server WebSocket e il task di controllo alert_spola
    websocket_task = loop.create_task(start_websocket_server())
    queue_task = loop.create_task(check_queue_messages(app))

    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(cleanup_and_stop_loop())
