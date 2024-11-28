from flask_migrate import Migrate
from app import create_app, db
import sys

# Crea l'applicazione utilizzando la funzione create_app
app = create_app()

# Inizializza Migrate con l'app Flask e il database
migrate = Migrate(app, db)

# Controlla se il comando da terminale è "flask" per evitare di avviare il server inutilmente
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        app.run(threaded=True, host='0.0.0.0', port=5000)
