# Flask Project

Questo è un progetto Flask che fornisce un'applicazione web con alcune funzionalità API e task schedulati. L'applicazione è progettata per essere modulare e facilmente scalabile, con una struttura ben organizzata e utilizzando tecnologie popolari come Flask, SQLAlchemy, Flask-JWT-Extended e APScheduler.

## Struttura del Progetto

La struttura del progetto è la seguente:

```
flask_project/
│
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── device.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── device.py
│   └── scheduler/
│       ├── __init__.py
│       └── jobs.py
│
├── config/
│   ├── __init__.py
│   └── config.py
│
├── instance/
│   └── config.py
│
├── flask/
│
├── manage.py
└── requirements.txt
```

- `app/`: Contiene l'applicazione principale Flask, con moduli per le API, i modelli e i task schedulati.
  - `api/`: Contiene i blueprint delle API (es. gestione dei dispositivi).
  - `models/`: Definisce i modelli del database.
  - `scheduler/`: Contiene i task pianificati con APScheduler.
- `config/`: Contiene la configurazione dell'applicazione.
- `instance/`: Contiene la configurazione specifica dell'istanza (file `.env`, configurazioni locali).
- `flask/`: La virtual environment (questa directory non è inclusa nel repository Git).
- `manage.py`: Punto di ingresso per gestire il server Flask e le migrazioni.
- `requirements.txt`: Elenco delle dipendenze del progetto.

## Prerequisiti

- Python 3.x
- Virtualenv
- Redis (se utilizzi Celery per task asincroni)

## Installazione

1. **Clona il repository**
   ```bash
   git clone https://github.com/tuo_username/flask_project.git
   cd flask_project
   ```

2. **Crea un virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Installa le dipendenze**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configura l'ambiente**
   - Crea un file `.env` nella directory principale e aggiungi le variabili di configurazione necessarie (come `SECRET_KEY`, `DATABASE_URL`, etc).

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

- **Registrazione Dispositivo**:
  - Endpoint: `/api/device/register`
  - Metodo: `POST`
  - Dati richiesti: `{ "matricola": "12345", "password": "password123", "ip_address": "192.168.1.1" }`

- **Login Dispositivo**:
  - Endpoint: `/api/device/login`
  - Metodo: `POST`
  - Dati richiesti: `{ "matricola": "12345", "password": "password123" }`

## Schedulazione dei Task

I task sono pianificati utilizzando APScheduler. L'attuale esempio di job esegue un'azione ogni 5 minuti. Il job è definito in `app/scheduler/jobs.py` ed è avviato automaticamente quando l'applicazione Flask viene avviata.

## Contributi

Le richieste di pull sono benvenute. Per modifiche importanti, apri prima un problema per discutere cosa vorresti cambiare.

## Licenza

Questo progetto è sotto la licenza MIT - vedi il file [LICENSE](LICENSE) per i dettagli.

