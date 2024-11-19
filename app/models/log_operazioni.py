from app import db
from datetime import datetime

class LogOperazioni(db.Model):
    __tablename__ = 'log_operazioni'

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, nullable=False, default=datetime.now)
    id_macchina = db.Column(db.Integer, nullable=False)
    id_operatore = db.Column(db.String(50), nullable=False)
    codice = db.Column(db.String(255), nullable=False)
    valore = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'data': self.data.isoformat() if self.data else None,
            'id_macchina': self.id_macchina,
            'id_operatore': self.id_operatore,
            'codice': self.codice,
            'valore': self.valore,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }