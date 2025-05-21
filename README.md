# Flask Project

Questo è un progetto Flask che fornisce un'applicazione web con alcune funzionalità API e task schedulati. L'applicazione è progettata per essere modulare e facilmente scalabile, con una struttura ben organizzata e utilizzando tecnologie popolari come Flask, SQLAlchemy, Flask-JWT-Extended e APScheduler.

## Struttura del Progetto

La struttura del progetto è la seguente:

```
flask_project/
│
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── device.py
│   ├── jobs/
│   │   └── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── device.py
│   │   ├── impostazioni.py
│   │   ├── log_operazioni.py
│   │   ├── log_orlatura.py
│   │   └── operatori.py
│   └── threads/
│       ├── __init__.py
│       ├── encoder.py
│       ├── monitor_spola.py
│       └── websocket.py
│
├── config/
│   ├── __init__.py
│   └── config.py
│
├── .gitignore
├── manage.py
├── README.md
└── requirements.txt

```

- `app/`: Contiene l'applicazione principale Flask, con moduli per le API, i modelli, i job e i thread.
  - `api/`: Contiene i blueprint delle API (es. gestione dei dispositivi, operatori, ...) 
  - `jobs/`: Modulo per definire i job o task schedulati, con l'inizializzazione in `__init__.py`.
  - `models/`: Contiene i modelli del database, tra cui impostazioni, log operazioni, log orlatura e operatori.
  - `threads/`: Gestisce i thread dedicati a specifiche operazioni asincrone (es. `encoder.py`, `monitor_spola.py`, `websocket.py`).
- `config/`: Contiene la configurazione principale dell'applicazione.
- `.gitignore`: File per escludere dal repository specifici file o cartelle, come configurazioni locali o file generati automaticamente.
- `manage.py`: Punto di ingresso per gestire il server Flask e altre operazioni di amministrazione.
- `requirements.txt`: Elenco delle dipendenze del progetto.


## Prerequisiti

- Python 3.x
- Virtualenv

## Installazione

1. **Clona il repository**
   ```bash
   git clone https://github.com/tuo_username/flask_project.git
   cd flask_project
   ```

2. **Crea un virtual environment**

   - **Su Linux/MacOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

   - **Su Windows:**
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```


3. **Installa le dipendenze**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configura l'ambiente**
   - Crea un file `.env` nella directory principale e aggiungi le variabili di configurazione necessarie (come `SECRET_KEY`, `DATABASE_URL`, etc).
   - Puoi impostare `LOG_LEVEL` per controllare il livello di verbosità dei log (`DEBUG`, `INFO`, `WARNING`, ...). I log vengono salvati in `data/logs/app.log`.

5. **Inizializza il database**
   ```bash
   flask db init
   flask db migrate -m "Initial migration."
   flask db upgrade
   ```

## Esecuzione del Server

Per avviare il server Flask, esegui:

```bash
python manage.py runserver
```

L'applicazione sarà disponibile all'indirizzo `http://127.0.0.1:5000/`.

## Funzionalità Principali

- **API RESTful**: Gestisce dispositivi industriali, permette la registrazione, l'autenticazione e la gestione tramite token JWT.
- **Autenticazione JWT**: Implementata con Flask-JWT-Extended per gestire token di accesso e refresh.
- **Task Schedulati**: Utilizza APScheduler per eseguire task periodici, come la manutenzione dei dispositivi o altre attività.

## Esempi di API

### **Registrazione Dispositivo** :
  - **Endpoint**: `/api/device/register`
  - **Metodo**: `POST`
  - **Dati richiesti**:
    ```json
    {
      "matricola": "12345",
      "password": "password123",
      "ip_address": "192.168.1.1",
      "device_type": "sensor",
      "status": "active",
      "firmware_version": "1.0.0"
    }
    ```
  - **Risposta** :
    - `201 Created`: `{"msg": "Device registered successfully"}`
    - `400 Bad Request`: `{"msg": "Matricola already exists"}` o `{"msg": "Missing key: [nome_chiave]"}`

### **Login Dispositivo** :
  - **Endpoint**: `/api/device/login`
  - **Metodo**: `POST`
  - **Dati richiesti**:
    ```json
    {
      "matricola": "12345",
      "password": "password123"
    }
    ```
  - **Risposta** :
    - `200 OK`: `{ "access_token": "token_di_accesso", "refresh_token": "token_di_refresh" }`
    - `401 Unauthorized`: `{"msg": "Bad matricola or password"}`

### **Rinnovo del Token di Accesso** :
  - **Endpoint**: `/api/device/token/refresh`
  - **Metodo**: `POST`
  - **Headers richiesti**: `Authorization: Bearer [refresh_token]`
  - **Risposta**:
    - `200 OK`: `{ "access_token": "nuovo_token_di_accesso" }`

### **Profilo del Dispositivo** :
  - **Endpoint**: `/api/device/profile`
  - **Metodo**: `GET`
  - **Headers richiesti**: `Authorization: Bearer [access_token]`
  - **Risposta**:
    - `200 OK`: `{"matricola": "12345", "ip_address": "192.168.1.1", "device_type": "sensor", "status": "active", "firmware_version": "1.0.0", ...}`
    - `404 Not Found`: `{"msg": "Device not found"}`


## Gestione dei Thread

I thread sono gestiti all'interno dell'applicazione per eseguire operazioni asincrone in background, separate dai job schedulati. Ogni file Python nella cartella `app/threads/` rappresenta un thread dedicato, avviato automaticamente all'avvio dell'applicazione Flask. 

I thread permettono di gestire operazioni indipendenti che non devono bloccare il normale flusso dell'applicazione, come l'encoder, il monitoraggio di dispositivi o il websocket. 

- **Inizializzazione** : Durante l'avvio dell'app, ogni file nella directory `threads/` viene importato e, se contiene una funzione `run`, viene eseguito come un thread separato. Questo meccanismo garantisce l'avvio automatico di ogni modulo di thread presente.
- **Esempio** : La funzione `run` presente in ogni modulo di thread esegue operazioni specifiche e riceve l'istanza `app` come argomento, per garantire l'accesso alle configurazioni e alle risorse condivise dell'applicazione.


## Licenza

Questo progetto è sotto la licenza MIT - vedi il file [LICENSE](LICENSE) per i dettagli.

