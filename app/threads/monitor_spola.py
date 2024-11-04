import time
import json
from datetime import datetime
from app import db
from app.models.impostazioni import Impostazioni
from app.models.log_orlatura import LogOrlatura
from sqlalchemy.orm import sessionmaker
from websocket import create_connection, WebSocketConnectionClosedException

HOST = '0.0.0.0'
PORT = 8765

# Thread per monitorare il consumo di filo e confrontarlo con il parametro spola
def run(app):
    with app.app_context():
        Session = sessionmaker(bind=db.engine)
        ws = None

        while True:
            try:
                # Verifica se la connessione WebSocket è aperta, altrimenti prova a riconnettere
                if ws is None or ws.connected is False:
                    try:
                        uri = f"ws://{HOST}:{PORT}"
                        ws = create_connection(uri)
                        print(f"Connessione WebSocket aperta con il server: {uri}")
                    except Exception as e:
                        print(f"Errore durante la connessione al WebSocket server: {e}")
                        time.sleep(5)
                        continue

                session = Session()
                try:
                    # Ottieni il valore del parametro spola dalle impostazioni
                    parametro_spola = session.query(Impostazioni).filter_by(codice='parametro_spola').first()
                    if parametro_spola:
                        valore_spola = float(parametro_spola.valore)
                    else:
                        print("Parametro spola non trovato nel database.")
                        time.sleep(5)  # Riprova dopo un minuto
                        continue

                    # Ottieni la data di riferimento per il calcolo del consumo
                    data_cambio_spola = session.query(Impostazioni).filter_by(codice='data_cambio_spola').first()
                    if data_cambio_spola:
                        data_riferimento = datetime.strptime(data_cambio_spola.valore, "%d/%m/%Y %H:%M:%S")
                    else:
                        print("Data cambio spola non trovata nel database.")
                        time.sleep(5)  # Riprova dopo un minuto
                        continue

                    # Calcola la somma del consumo di filo da data_riferimento ad oggi
                    consumo_totale = session.query(db.func.sum(LogOrlatura.consumo)).filter(LogOrlatura.data >= data_riferimento).scalar()
                    consumo_totale = consumo_totale if consumo_totale else 0.0

                    # Controlla se il consumo totale supera il valore del parametro spola
                    if consumo_totale > valore_spola:
                        print(f"Attenzione: il consumo totale di {consumo_totale} cm ha superato il valore di spola di {valore_spola} cm.")
                        # Invia un messaggio al server websocket
                        message = json.dumps({
                            "action": "alert_spola",
                            "consumo_totale": consumo_totale,
                            "valore_spola": valore_spola
                        })
                        send_message_to_websocket(ws, message)
                    else:
                        print(f"Consumo totale: {consumo_totale} cm. Valore spola: {valore_spola} cm. Periodo di riferimento: dal {data_riferimento.strftime('%d/%m/%Y %H:%M:%S')} ad ora ({datetime.now().strftime('%d/%m/%Y %H:%M:%S')})")

                    # Attendi prima di eseguire nuovamente il controllo
                    time.sleep(5)  # Verifica ogni 5 secondi

                except Exception as e:
                    print(f"Errore durante il controllo del consumo di filo: {e}")
                    time.sleep(30)  # In caso di errore, attende 30 secondi prima di riprovare
                finally:
                    # Chiudi la sessione per garantire che le modifiche vengano viste
                    session.close()

            except WebSocketConnectionClosedException as e:
                print(f"Connessione WebSocket chiusa inaspettatamente: {e}")
                ws = None
            except Exception as e:
                print(f"Errore generale nel thread: {e}")
                if ws:
                    ws.close()
                    ws = None
                time.sleep(10)  # Attendi prima di provare a riconnettere

# Funzione per inviare un messaggio al server WebSocket
def send_message_to_websocket(ws, message):
    try:
        ws.send(message)
        print(f"Messaggio inviato al WebSocket server: {message}")
    except WebSocketConnectionClosedException as e:
        print(f"Errore durante l'invio del messaggio al WebSocket server: Connessione chiusa: {e}")
    except Exception as e:
        print(f"Errore durante l'invio del messaggio al WebSocket server: {e}")
