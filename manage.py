from flask_script import Manager, Server
from flask_migrate import Migrate, MigrateCommand
from app import create_app, db

# Creazione dell'applicazione
app = create_app()

# Inizializza Migrate
migrate = Migrate(app, db)

# Creazione del gestore per i comandi del terminale
manager = Manager(app)

# Aggiungi il comando per gestire le migrazioni
manager.add_command('db', MigrateCommand)

# Comando per avviare l'applicazione con parametri definiti
server = Server(host='0.0.0.0', port=5000, threaded=True)
manager.add_command("runserver", server)

if __name__ == '__main__':
    manager.run()
