from app import db
from datetime import datetime

class Impostazioni(db.Model):
    __tablename__ = 'impostazioni'

    codice = db.Column(db.String(100), primary_key=True)  # Definisce 'codice' come la chiave primaria
    descrizione = db.Column(db.String(255), nullable=True)
    valore = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)
