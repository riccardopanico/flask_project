import spidev
import time
import RPi.GPIO as GPIO
from app import db
from app.models.impostazioni import Impostazioni
from app.models.log_orlatura import LogOrlatura
import os
from datetime import datetime

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
lettura_precedente_encoder = 0
lunghezza_totale_filo = 0.0
fattore_taratura = 1.0
inizio_operativita = None
encoder_fermo = True
ultimo_impulso_time = 0.0
TEMPO_FERMO = 2.0  # Tempo in secondi per considerare l'encoder fermo

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
    global fattore_taratura
    impostazione = Impostazioni.query.filter_by(codice='fattore_taratura').first()
    if impostazione:
        fattore_taratura = float(impostazione.valore)

# Funzione per salvare i record nel database
def save_record_to_db(impulsi, lunghezza, tempo_operativita):
    log = LogOrlatura(
        id_macchina=1,
        id_operatore='0010452223',
        consumo=lunghezza,
        tempo=tempo_operativita,
        commessa='Commessa1',
        data=datetime.utcnow()
    )
    db.session.add(log)
    db.session.commit()
    print(f"Impulsi: {impulsi}, Lunghezza: {lunghezza:.6f} cm, Tempo Operatività: {tempo_operativita} s")

# Funzione per monitorare l'encoder e salvare periodicamente i dati
def run():
    global lettura_precedente_encoder, lunghezza_totale_filo, inizio_operativita, encoder_fermo, ultimo_impulso_time

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
            else:
                # Se l'encoder non genera impulsi per più di TEMPO_FERMO secondi, fermiamo il timer
                if time.time() - ultimo_impulso_time >= TEMPO_FERMO and not encoder_fermo:
                    encoder_fermo = True
                    tempo_operativita = int(time.time() - inizio_operativita)
                    save_record_to_db(impulsi_totali, lunghezza_totale_filo, tempo_operativita)

            lunghezza_aggiornata = differenza_impulsi * LUNGHEZZA_PER_IMPULSO * fattore_taratura
            lunghezza_totale_filo += lunghezza_aggiornata

            # Salva i dati ogni 10 secondi se l'encoder è attivo
            if not encoder_fermo:
                tempo_operativita = int(time.time() - inizio_operativita)
                save_record_to_db(impulsi_totali, lunghezza_totale_filo, tempo_operativita)

            time.sleep(10)
    finally:
        cleanup()

# Pulizia GPIO e SPI alla chiusura
def cleanup():
    GPIO.cleanup()
    spi.close()
