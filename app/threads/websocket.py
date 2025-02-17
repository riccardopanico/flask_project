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
from app.models.dipendenti import Dipendente
from app.jobs.sincronizza_dipendenti import run as sincronizzaDipendenti
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
from datetime import datetime
import signal
import weakref
# import gpiod as GPIO
import os
from flask import current_app
import lgpio
import time

# Apri il GPIO chip
CHIP_ID = 0  # gpiochip0
PIN_BUZZER = 26
# Apri il chip GPIO
h = lgpio.gpiochip_open(CHIP_ID)
# Imposta il pin come output
lgpio.gpio_claim_output(h, PIN_BUZZER)

def bip(n=1):
    for _ in range(n):
        lgpio.gpio_write(h, PIN_BUZZER, 1)  # Accendi il buzzer
        time.sleep(0.1)
        lgpio.gpio_write(h, PIN_BUZZER, 0)  # Spegni il buzzer
        time.sleep(0.05)

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
        current_app.logger.warning("Messaggio non in formato JSON, ignorato.")
        return None

# Handler per ogni connessione WebSocket
async def socket_handler(websocket, path):
    current_app.logger.info(f"Client connesso: {websocket.remote_address}")
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            current_app.logger.info(f"Ricevuto: {message}")
            data = parse_json_message(message)
            if data is None:
                continue
            try:
                if "action" in data:
                    action = data["action"]
                    if action == "ping":
                        await websocket.send(json.dumps({"message": "pong"}))
                    elif action == "poweroff":
                        current_app.logger.info("Esecuzione comando poweroff...")
                        subprocess.run(["clear"], shell=True)
                        subprocess.run(["sudo", "systemctl", "stop", "getty@tty1.service"], shell=False)
                        subprocess.run(["sudo", "systemctl", "stop", "flask.service"], shell=False)
                        subprocess.run(["sudo", "systemctl", "stop", "chromium-kiosk.service"], shell=False)
                        subprocess.run(["sudo", "poweroff", "--no-wall"], shell=False)
                    elif action == "reboot":
                        current_app.logger.info("Esecuzione comando reboot...")
                        subprocess.run(["clear"], shell=True)
                        subprocess.run(["sudo", "systemctl", "stop", "getty@tty1.service"], shell=False)
                        subprocess.run(["sudo", "systemctl", "stop", "flask.service"], shell=False)
                        subprocess.run(["sudo", "systemctl", "stop", "chromium-kiosk.service"], shell=False)
                        subprocess.run(["sudo", "reboot", "--no-wall"], shell=False)
                    elif action == 'registraBadge':
                        if "badge" in data and data["badge"]:
                            success, message = await asyncio.to_thread(registraBadge, data["badge"])
                            await websocket.send(json.dumps({
                                "message": message,
                                "icon": "success" if success else "error",
                                "autoclose": success,
                                "timer": 3000
                            }))
                    elif action == 'sincronizzaDipendenti':
                        try:
                            await asyncio.to_thread(sincronizzaDipendenti, current_app)
                            message = "Sincronizzazione completata con successo."
                            success = True
                        except Exception as e:
                            message = f"Errore durante la sincronizzazione: {str(e)}"
                            success = False
                        await websocket.send(json.dumps({
                            "message": message,
                            "icon": "success" if success else "error",
                            "autoclose": success,
                            "timer": 3000
                        }))
                    else:
                        current_app.logger.warning(f"Azione non riconosciuta: {action}")
                    await websocket.send(json.dumps({"status": "readyForNext"}))
                else:
                    current_app.logger.warning("Messaggio JSON non valido, manca la chiave 'action'.")
            except Exception as e:
                current_app.logger.error(f"Errore nella gestione del messaggio: {e}")
    except websockets.exceptions.ConnectionClosed as e:
        current_app.logger.info(f"Connessione chiusa: {e}")
    except Exception as e:
        current_app.logger.error(f"Connessione chiusa o errore generico: {e}")
    finally:
        connected_clients.discard(websocket)
        current_app.logger.info(f"Client disconnesso: {websocket.remote_address}")

def registraBadge(badge_value):
    with current_app.app_context():
        session = db.session  # Ottiene la sessione attiva
        try:
            badge_variable = session.query(Variables).filter_by(variable_code="badge").first()

            if badge_variable:
                dipendente = session.query(Dipendente).filter_by(badge=badge_value).first()
                if dipendente:
                    nome_cognome = f"{dipendente.nome} {dipendente.cognome}"
                    nome_oscurato = dipendente.nome[0] + "*" * (len(dipendente.nome) - 1)
                    cognome_oscurato = dipendente.cognome[0] + "*" * (len(dipendente.cognome) - 1)
                    current_app.logger.info(f"Badge registrato: {badge_value} per {nome_cognome}")
                    badge_variable.set_value(badge_value)
                    session.commit()
                    bip(1)
                    return True, f"Timbratura alle {datetime.now().strftime('%H:%M')} <br> {nome_oscurato} {cognome_oscurato}"
                else:
                    bip(3)
                    current_app.logger.warning(f"Nessun dipendente trovato con il badge: {badge_value}")
                    return False, "Errore: Dipendente non trovato"
            else:
                current_app.logger.error("Errore: Variabile 'badge' non trovata nel database.")
                return False, "Errore: Variabile 'badge' non trovata"
        except Exception as e:
            session.rollback()  # Rollback in caso di errore
            current_app.logger.error(f"Errore nel salvataggio del badge: {e}")
            return False, f"Errore interno: {str(e)}"
        finally:
            session.close()  # Chiude la sessione

async def check_queue_messages(app):
    with app.app_context():
        while True:
            try:
                # Ottiene il messaggio dalla coda (bloccante finché non arriva un messaggio)
                message = await asyncio.to_thread(websocket_queue.get)

                Session = sessionmaker(bind=db.engine)
                with Session() as session:
                    if message == "alert_spola":
                        current_app.logger.info("Alert spola attivato, invio messaggio ai client connessi...")
                        await broadcast_message(json.dumps({"action": "alert_spola"}))
                    elif message == "alert_olio":
                        current_app.logger.info("Alert olio attivato, invio messaggio ai client connessi...")
                        await broadcast_message(json.dumps({"action": "alert_olio"}))
                    elif message == "dati_orlatura":
                        current_app.logger.info("Ottengo dati orlatura, invio messaggio ai client connessi...")

                        # Recupera interconnection_id da Variables
                        interconnection_id = int(session.query(Variables).filter_by(variable_code='interconnection_id').first().get_value())
                        current_app.logger.info(f"Interconnection ID recuperato: {interconnection_id}")

                        # Recupera device_id con interconnection_id da Device
                        device_id = session.query(Device).filter_by(interconnection_id=interconnection_id).first().id
                        current_app.logger.info(f"Device ID recuperato: {device_id}")

                        # Recupera commessa_id e valore corrente
                        commessa_var = session.query(Variables).filter_by(variable_code='commessa').first()
                        commessa_id = commessa_var.id if commessa_var else None
                        commessa_value = commessa_var.get_value() if commessa_var else None
                        current_app.logger.info(f"Commessa ID: {commessa_id}, Valore corrente: {commessa_value}")

                        # Recupera l'ID delle variabili per consumo e operatività
                        consumo_var_id = session.query(Variables).filter_by(variable_code='encoder_consumo').first().id
                        operativita_var_id = session.query(Variables).filter_by(variable_code='encoder_operativita').first().id
                        current_app.logger.info(f"ID variabili - Consumo: {consumo_var_id}, Operatività: {operativita_var_id}")

                        # Query per dati totali
                        consumo_totale = session.query(func.sum(LogData.numeric_value)).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == consumo_var_id
                        ).scalar() or 0
                        operativita_totale = session.query(func.sum(LogData.numeric_value)).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == operativita_var_id
                        ).scalar() or 0
                        current_app.logger.info(f"Consumo totale: {consumo_totale}, Operatività totale: {operativita_totale}")

                        # Calcola dati dalla data dell'ultimo log della commessa
                        last_commessa_log = session.query(LogData).filter(
                            LogData.device_id == device_id,
                            LogData.variable_id == commessa_id
                        ).order_by(LogData.created_at.desc()).first()
                        current_app.logger.info(f"Ultimo log di commessa trovato: {last_commessa_log}")

                        if last_commessa_log:
                            start_commessa = last_commessa_log.created_at
                            stop_commessa = datetime.now()

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

                            current_app.logger.info(
                                f"Consumo commessa corrente: {consumo_commessa}, "
                                f"Operatività commessa corrente: {operativita_commessa}"
                            )
                        else:
                            current_app.logger.warning("Nessun log di commessa trovato. Nessun dato calcolato per la commessa corrente.")

                        # Query per dati campionatura
                        last_campionatura = session.query(Campionatura.start, Campionatura.stop).order_by(Campionatura.id.desc()).first()
                        if last_campionatura:
                            start_campionatura = last_campionatura.start
                            stop_campionatura = last_campionatura.stop or datetime.now()
                            current_app.logger.info(f"Ultima campionatura: inizio {start_campionatura}, fine {stop_campionatura}")
                        else:
                            start_campionatura, stop_campionatura = None, None
                            current_app.logger.warning("Nessuna campionatura trovata.")

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
                        current_app.logger.info(f"Consumo campionatura: {consumo_campionatura}, Operatività campionatura: {operativita_campionatura}")

                        # Costruzione del dizionario dati orlatura
                        dati_orlatura = {
                            "consumo_totale": round(consumo_totale, 2),
                            "tempo_totale": round(operativita_totale, 2),
                            "consumo_commessa": round(consumo_commessa, 2),
                            "tempo_commessa": round(operativita_commessa, 2),
                            "consumo_campionatura": round(consumo_campionatura, 2),
                            "tempo_campionatura": round(operativita_campionatura, 2)
                        }
                        current_app.logger.info(f"Dati orlatura costruiti: {dati_orlatura}")

                        # Invio dei dati ai client
                        await broadcast_message(json.dumps({"action": "dati_orlatura", "data": dati_orlatura}))
                        session.commit()
            except Exception as e:
                current_app.logger.error(f"Errore durante l'invio di {message}: {e}")

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
        current_app.logger.info(f"Server WebSocket avviato su ws://{HOST}:{PORT}")
        await server.wait_closed()  # Mantiene il server in esecuzione
    except asyncio.CancelledError:
        current_app.logger.info("Server WebSocket terminato correttamente.")
    except Exception as e:
        current_app.logger.error(f"Errore nel server WebSocket: {e}")

# Definisci un metodo per gestire la chiusura pulita
async def cleanup_and_stop_loop():
    current_app.logger.info("Chiusura del loop di eventi...")
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

    with app.app_context():  # Aggiunta del contesto dell'applicazione
        # Avvia il server WebSocket e il task di controllo alert_spola
        websocket_task = loop.create_task(start_websocket_server())
        queue_task = loop.create_task(check_queue_messages(app))

        bip(2)

        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(cleanup_and_stop_loop())
