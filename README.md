# Flask Project Framework

Un framework Flask modulare e automatizzato per lo sviluppo rapido di applicazioni web con supporto integrato per API, job schedulati e thread. Il progetto è progettato per essere estremamente flessibile e automatizzato, permettendo di aggiungere nuove funzionalità semplicemente creando nuovi moduli nelle directory appropriate.

## Struttura del Progetto

```
flask_project/
│
├── app/
│   ├── api/              # API endpoints (automaticamente registrati)
│   │   ├── __init__.py
│   │   └── *.py         # Ogni file diventa un blueprint
│   │
│   ├── jobs/            # Job schedulati (automaticamente registrati)
│   │   ├── __init__.py
│   │   └── *.py         # Ogni file con funzione run() diventa un job
│   │
│   ├── models/          # Modelli del database
│   │   ├── __init__.py
│   │   └── *.py         # Ogni file diventa un modello
│   │
│   ├── threads/         # Thread in background (automaticamente avviati)
│   │   ├── __init__.py
│   │   └── *.py         # Ogni file con funzione run() diventa un thread
│   │
│   ├── utils/           # Utility e helper functions
│   │   └── *.py
│   │
│   └── __init__.py      # Configurazione principale dell'app
│
├── config/
│   ├── __init__.py
│   └── config.py        # Configurazioni dell'applicazione
│
├── .gitignore
├── manage.py            # Punto di ingresso dell'applicazione
├── README.md
└── requirements.txt     # Dipendenze del progetto
```

## Caratteristiche Principali

- **Automatizzazione Completa**: Aggiungi nuovi moduli nelle directory appropriate e vengono automaticamente registrati/avviati
- **API RESTful**: Crea nuovi endpoint semplicemente aggiungendo file nella directory `api/`
- **Job Schedulati**: Aggiungi nuovi job nella directory `jobs/` con una funzione `run()`
- **Thread in Background**: Aggiungi nuovi thread nella directory `threads/` con una funzione `run()`
- **Modelli Database**: Aggiungi nuovi modelli nella directory `models/` per la gestione dei dati
- **Configurazione Flessibile**: Sistema di configurazione basato su ambiente (development, testing, production)

## Prerequisiti

- Python 3.8 o superiore
- pip (gestore pacchetti Python)

## Installazione

1. **Clona il repository**
   ```bash
   git clone https://github.com/tuo_username/flask_project.git
   cd flask_project
   ```

2. **Crea e attiva un ambiente virtuale**
   ```bash
   # Linux/MacOS
   python3 -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Installa le dipendenze**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configura l'ambiente**
   ```bash
   # Crea il file .env
   cp .env.example .env
   # Modifica le variabili nel file .env secondo le tue necessità
   ```

5. **Inizializza il database**
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

## Sviluppo

### Aggiungere Nuove API
1. Crea un nuovo file in `app/api/`
2. Definisci il tuo blueprint
3. Il sistema lo registrerà automaticamente

### Aggiungere Nuovi Job
1. Crea un nuovo file in `app/jobs/`
2. Implementa una funzione `run()`
3. Il sistema lo schedulerà automaticamente

### Aggiungere Nuovi Thread
1. Crea un nuovo file in `app/threads/`
2. Implementa una funzione `run()`
3. Il sistema lo avvierà automaticamente

### Aggiungere Nuovi Modelli
1. Crea un nuovo file in `app/models/`
2. Definisci il tuo modello SQLAlchemy
3. Il sistema lo registrerà automaticamente

## Esecuzione

### Ambiente di Sviluppo
```bash
python manage.py runserver
```

### Ambiente di Produzione
```bash
gunicorn -w 4 -b 0.0.0.0:5000 manage:app
```

## Configurazione

Il progetto utilizza un sistema di configurazione basato su ambiente. Le configurazioni possono essere modificate in:

- `config/config.py`: Configurazioni di base
- `.env`: Variabili d'ambiente specifiche per l'ambiente

## Struttura dei Moduli

### API (`app/api/`)
- Ogni file Python diventa un blueprint
- Automaticamente registrato all'avvio
- Supporto integrato per autenticazione JWT

### Job (`app/jobs/`)
- Ogni file con funzione `run()` diventa un job
- Automaticamente schedulato all'avvio
- Supporto per intervalli e trigger personalizzati

### Thread (`app/threads/`)
- Ogni file con funzione `run()` diventa un thread
- Automaticamente avviato all'avvio
- Gestione automatica del ciclo di vita

### Modelli (`app/models/`)
- Ogni file Python diventa un modello
- Automaticamente registrato con SQLAlchemy
- Supporto per relazioni e migrazioni

## Contribuire

1. Fork il repository
2. Crea un branch per la tua feature (`git checkout -b feature/AmazingFeature`)
3. Commit le tue modifiche (`git commit -m 'Add some AmazingFeature'`)
4. Push sul branch (`git push origin feature/AmazingFeature`)
5. Apri una Pull Request

## Licenza

Questo progetto è sotto la licenza MIT - vedi il file [LICENSE](LICENSE) per i dettagli.

