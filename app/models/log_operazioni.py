from app import db
from datetime import datetime

class LogOperazioni(db.Model):
    __tablename__ = 'log_operazioni'

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    id_macchina = db.Column(db.Integer, nullable=False)
    id_operatore = db.Column(db.Integer, nullable=False)
    codice = db.Column(db.String(100), nullable=False)
    valore = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)
