from app import create_app, db
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

# Carica le variabili dal file .env
load_dotenv()

# Stampa per verificare se FLASK_ENV è stata caricata
print(f"FLASK_ENV: {os.getenv('FLASK_ENV')}")

app = create_app()
migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run(threaded=True, host='0.0.0.0', port=5000)
