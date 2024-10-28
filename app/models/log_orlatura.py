from app import db
from datetime import datetime

class LogOrlatura(db.Model):
    __tablename__ = 'log_orlatura'

    id = db.Column(db.Integer, primary_key=True)
    id_macchina = db.Column(db.Integer, nullable=False)
    id_operatore = db.Column(db.String(50), nullable=False)
    consumo = db.Column(db.Float(precision=11, scale=2), nullable=False, default=0.00)
    tempo = db.Column(db.Integer, nullable=False, default=0)
    commessa = db.Column(db.String(255), nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
