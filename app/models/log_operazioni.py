from app import db
from sqlalchemy import Column, Integer, String, DateTime, func
from datetime import datetime

class LogOperazioni(db.Model):
    __tablename__ = 'log_operazioni'

    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(db.DateTime, nullable=False, server_default=func.now(), default=datetime.now)
    id_macchina = Column(db.Integer, nullable=False)
    id_operatore = Column(db.String(50), nullable=False)
    codice = Column(db.String(255), nullable=False)
    valore = Column(db.String(255), nullable=False)
    created_at = Column(db.DateTime, server_default=func.now())

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
