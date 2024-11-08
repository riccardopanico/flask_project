import asyncio
import websockets
import json
import subprocess
from app import db, websocket_queue
from app.models.impostazioni import Impostazioni
from app.models.log_orlatura import LogOrlatura
from app.models.campionatura import Campionatura
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
from datetime import datetime

HOST = '0.0.0.0'  
PORT = 8765  
connected_clients = set()

# Handler per ogni connessione WebSocket
async def socket_handler(websocket, path):
    print(f"Client connesso: {websocket.remote_address}")
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
    except Exception as e:
        print(f"Connessione chiusa o errore generico: {e}")
    finally:
        connected_clients.remove(websocket)
        print(f"Client disconnesso: {websocket.remote_address}")

async def check_queue_messages(app):
    with app.app_context():
        while True:
            try:
                # Ottiene il messaggio dalla coda (bloccante finché non arriva un messaggio)
                message = await asyncio.to_thread(websocket_queue.get)
                
                Session = sessionmaker(bind=db.engine)
                session = Session()

                if message == "alert_spola":
                    print("Alert spola attivato, invio messaggio ai client connessi...")
                    await broadcast_message(json.dumps({"action": "alert_spola"}))
                    alert_spola = session.query(Impostazioni).filter_by(codice='alert_spola').first()
                    alert_spola.valore = '0'
                    session.commit()
                if message == "alert_olio":
                    print("Alert spola attivato, invio messaggio ai client connessi...")
                    await broadcast_message(json.dumps({"action": "alert_olio"}))
                    alert_olio = session.query(Impostazioni).filter_by(codice='alert_olio').first()
                    alert_olio.valore = '0'
                    session.commit()
                elif message == "dati_orlatura":
                    print("Ottengo dati orlatura, invio messaggio ai client connessi...")
                    
                    # Adattamento delle query da Laravel a Python
                    id_macchina = session.query(Impostazioni).filter_by(codice='id_macchina').first().valore
                    commessa = session.query(Impostazioni).filter_by(codice='commessa').first().valore

                    # Query per dati totali
                    dati_totali = session.query(
                        func.sum(LogOrlatura.consumo).label('consumo_totale'),
                        func.sum(LogOrlatura.tempo).label('tempo_totale')
                    ).filter(LogOrlatura.id_macchina == id_macchina).first()

                    consumo_totale = float(round(dati_totali.consumo_totale or 0, 2))
                    tempo_totale = float(round(dati_totali.tempo_totale or 0, 2))

                    # Query per dati commessa
                    dati_commessa = session.query(
                        func.sum(LogOrlatura.consumo).label('consumo_commessa'),
                        func.sum(LogOrlatura.tempo).label('tempo_commessa')
                    ).filter(
                        LogOrlatura.id_macchina == id_macchina,
                        LogOrlatura.commessa == commessa
                    ).first()

                    # Query per dati campionatura
                    dati_campionatura = session.query(
                        func.sum(LogOrlatura.consumo).label('consumo_campionatura'),
                        func.sum(LogOrlatura.tempo).label('tempo_campionatura')
                    ).filter(
                        LogOrlatura.id_macchina == id_macchina,
                        LogOrlatura.data.between(
                            session.query(Campionatura.start).order_by(Campionatura.id.desc()).first()[0],
                            db.func.coalesce(session.query(Campionatura.stop).order_by(Campionatura.id.desc()).first()[0], datetime.now())
                        )
                    ).first()

                    consumo_campionatura = float(round(dati_campionatura.consumo_campionatura or 0, 2))
                    tempo_campionatura = float(round(dati_campionatura.tempo_campionatura or 0, 2))

                    consumo_commessa = float(round(dati_commessa.consumo_commessa or 0, 2))
                    tempo_commessa = float(round(dati_commessa.tempo_commessa or 0, 2))

                    dati_orlatura = {
                        "consumo_totale": consumo_totale,
                        "tempo_totale": tempo_totale,
                        "consumo_commessa": consumo_commessa,
                        "tempo_commessa": tempo_commessa,
                        "consumo_campionatura": consumo_campionatura,
                        "tempo_campionatura": tempo_campionatura
                    }

                    await broadcast_message(json.dumps({"action": "dati_orlatura", "data": dati_orlatura}))
                    session.commit()
            except Exception as e:
                print(f"Errore durante l'invio dell'alert spola: {e}")
            finally:
                if 'session' in locals():
                    session.close()

# Invia un messaggio a tutti i client connessi
async def broadcast_message(message):
    if connected_clients:
        await asyncio.gather(*[client.send(message) for client in connected_clients if client.open])

# Avvia il server WebSocket
async def start_websocket_server():
    async with websockets.serve(
        socket_handler, HOST, PORT,
        ping_interval=None,  # Disabilita il ping di keepalive
        ping_timeout=None,   # Disabilita il timeout per il ping
        max_size=None,       # Nessun limite alla dimensione del messaggio
        max_queue=100,       # Aumenta la dimensione della coda
        compression=None     # Disabilita la compressione per migliorare la stabilità
    ):
        print(f"Server WebSocket avviato su ws://{HOST}:{PORT}")
        await asyncio.Future()  # Mantiene il server in esecuzione

def run(app):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Avvia il server WebSocket e il task di controllo alert_spola
    loop.create_task(start_websocket_server())
    loop.create_task(check_queue_messages(app))
    loop.run_forever()
