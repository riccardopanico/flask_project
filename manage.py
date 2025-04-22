import os
from flask_migrate import Migrate
from app import create_app, db

# Crea l'applicazione utilizzando la funzione create_app
app = create_app()
migrate = Migrate(app, db)

@app.cli.command("init-db")
def init_db():
    """Initialize the database."""
    db.create_all()
    print("Database initialized successfully!")

if __name__ == '__main__':
    app.run(
        threaded=True,
        host='0.0.0.0',
        port=5000,
        debug=app.config['DEBUG']
    )
