from flask_migrate import Migrate
from app import create_app, db

# Crea l'applicazione utilizzando la funzione create_app
app = create_app()

# Inizializza Migrate con l'app Flask e il database
migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run(threaded=True, host='0.0.0.0', port=5000)
