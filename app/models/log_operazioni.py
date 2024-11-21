from app import db
from datetime import datetime
from sqlalchemy import func

class LogOperazioni(db.Model):
    __tablename__ = 'log_operazioni'

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, nullable=False, server_default=func.now(), default=datetime.now)
    id_macchina = db.Column(db.Integer, nullable=False)
    id_operatore = db.Column(db.String(50), nullable=False)
    codice = db.Column(db.String(255), nullable=False)
    valore = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'data': self.data.isoformat() if self.data else None,
            'id_macchina': self.id_macchina,
            'id_operatore': self.id_operatore,
            'codice': self.codice,
            'valore': self.valore,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }