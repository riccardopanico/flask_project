import spidev
import time
import RPi.GPIO as GPIO
from app import db, websocket_queue
from app.models.variables import Variables
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from flask import current_app

# Disabilita gli avvisi GPIO
GPIO.setwarnings(False)

# Imposta GPIO per il pin EN
GPIO.setmode(GPIO.BCM)
EN_PIN = 17
GPIO.setup(EN_PIN, GPIO.OUT)

# Imposta SPI
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 500000
spi.mode = 0b00

# Comandi LS7366R per gestire l'encoder
CLEAR_COUNTER = 0x20
READ_COUNTER = 0x60
WRITE_MDR0 = 0x88  # Comando per scrivere nel registro MDR0
WRITE_MDR1 = 0x90  # Comando per scrivere nel registro MDR1

# Parametri dell'encoder e del rullino
PUNTI_PER_GIRO = 100
DIAMETRO_RULLINO = 11.0
CIRCONFERENZA_RULLINO = 34.55749
LUNGHEZZA_PER_IMPULSO = CIRCONFERENZA_RULLINO / PUNTI_PER_GIRO / 10
fattore_taratura = 1.0
inizio_operativita = None
encoder_fermo = True
ultimo_impulso_time = 0.0
TEMPO_FERMO = 1.0  # Tempo in secondi per considerare l'encoder fermo

# Funzione per scrivere un comando tramite SPI
def write_byte(command, value=None):
    if value is not None:
        spi.xfer2([command, value])
    else:
        spi.xfer2([command])

# Funzione per configurare l'encoder in modalità X4 quadratura
def configure_encoder_x4_mode():
    MDR0_CONFIG = 0x03
    write_byte(WRITE_MDR0, MDR0_CONFIG)

# Funzione per resettare i registri e il contatore
def reset_registers():
    write_byte(WRITE_MDR0, 0x03)
    write_byte(WRITE_MDR1, 0x00)
    write_byte(CLEAR_COUNTER)

# Funzione per leggere il contatore dell'encoder con gestione dell'overflow
def read_counter():
    result = spi.xfer2([READ_COUNTER, 0x00, 0x00, 0x00, 0x00])
    count = (result[1] << 24) | (result[2] << 16) | (result[3] << 8) | result[4]
    if count & 0x80000000:
        count -= 0x100000000
    return count

# Funzione per caricare il fattore di taratura dal database
def load_fattore_taratura_from_db():
    impostazione = Variables.query.filter_by(variable_code='fattore_taratura').first()
    if impostazione:
        return float(impostazione.get_value()) / 100
    return None

# Funzione per salvare i record aggiornando le variabili
def save_record_to_db(impulsi, lunghezza, tempo_operativita):
    try:
        variables = db.session.query(Variables).filter(Variables.variable_code.in_(['interconnection_id', 'commessa', 'badge'])).all()
        variables_dict = {var.variable_code: var.get_value() for var in variables}

        # Aggiorna i valori delle variabili
        encoder_consumo = db.session.query(Variables).filter_by(variable_code='encoder_consumo').first()
        if encoder_consumo:
            encoder_consumo.set_value(lunghezza)

        encoder_operativita = db.session.query(Variables).filter_by(variable_code='encoder_operativita').first()
        if encoder_operativita:
            encoder_operativita.set_value(tempo_operativita)

        encoder_impulsi = db.session.query(Variables).filter_by(variable_code='encoder_impulsi').first()
        if encoder_impulsi:
            encoder_impulsi.set_value(impulsi)

        websocket_queue.put("dati_orlatura")
        current_app.logger.info(f"Impulsi: {impulsi}, Lunghezza: {lunghezza:.6f} cm, Tempo Operatività: {tempo_operativita} s")
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Errore durante il salvataggio del record: {e}")

# Funzione per monitorare l'encoder e salvare periodicamente i dati
def run(app):
    global lettura_precedente_encoder, inizio_operativita, encoder_fermo, ultimo_impulso_time
    lettura_precedente_encoder = 0
    lunghezza_totale_filo = 0.0

    # Usa il contesto dell'applicazione Flask per gestire correttamente le operazioni sul database
    with app.app_context():
        # Carica il fattore di taratura e configura l'encoder
        load_fattore_taratura_from_db()
        reset_registers()
        configure_encoder_x4_mode()

        try:
            while True:
                impulsi_totali = read_counter()
                differenza_impulsi = impulsi_totali - lettura_precedente_encoder
                lettura_precedente_encoder = impulsi_totali

                if differenza_impulsi != 0:
                    # L'encoder è attivo
                    ultimo_impulso_time = time.time()
                    if encoder_fermo:
                        # Se l'encoder era fermo, iniziamo a contare il tempo di operatività
                        inizio_operativita = time.time()
                        encoder_fermo = False

                    lunghezza_aggiornata = differenza_impulsi * LUNGHEZZA_PER_IMPULSO * fattore_taratura
                    lunghezza_totale_filo += lunghezza_aggiornata
                else:
                    # Se l'encoder non genera impulsi per più di TEMPO_FERMO secondi, fermiamo il timer e salviamo i dati
                    if time.time() - ultimo_impulso_time >= TEMPO_FERMO and not encoder_fermo:
                        encoder_fermo = True
                        tempo_operativita = int(time.time() - inizio_operativita)
                        save_record_to_db(impulsi_totali, lunghezza_totale_filo, tempo_operativita)
                        lunghezza_totale_filo = 0.0  # Reset della lunghezza totale dopo il salvataggio

                time.sleep(1)
        finally:
            cleanup()

def cleanup():
    GPIO.cleanup()
    spi.close()
