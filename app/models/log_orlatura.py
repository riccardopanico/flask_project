from app import db
from sqlalchemy import Column, Integer, String, DateTime, func
from datetime import datetime

class LogOrlatura(db.Model):
    __tablename__ = 'log_orlatura'

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_macchina = Column(db.Integer, nullable=False)
    id_operatore = Column(db.String(50), nullable=False)
    consumo = Column(db.Numeric(precision=11, scale=2), nullable=False, default=0.00)
    tempo = Column(db.Integer, nullable=False, default=0)
    commessa = Column(db.String(255), nullable=False)
    data = Column(db.DateTime, nullable=False, server_default=func.now(), default=datetime.now)
    created_at = Column(db.DateTime, server_default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'id_macchina': self.id_macchina,
            'id_operatore': self.id_operatore,
            'consumo': str(self.consumo),
            'tempo': self.tempo,
            'commessa': self.commessa,
            'data': self.data.isoformat() if self.data else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
