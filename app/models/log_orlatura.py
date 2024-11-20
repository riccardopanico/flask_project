from app import db
from datetime import datetime
from sqlalchemy import func

class LogOrlatura(db.Model):
    __tablename__ = 'log_orlatura'

    id = db.Column(db.Integer, primary_key=True)
    id_macchina = db.Column(db.Integer, nullable=False)
    id_operatore = db.Column(db.String(50), nullable=False)
    consumo = db.Column(db.Numeric(precision=11, scale=2), nullable=False, default=0.00)
    tempo = db.Column(db.Integer, nullable=False, default=0)
    commessa = db.Column(db.String(255), nullable=False)
    data = db.Column(db.DateTime, nullable=False, server_default=func.now(), default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'id_macchina': self.id_macchina,
            'id_operatore': self.id_operatore,
            'consumo': str(self.consumo),
            'tempo': self.tempo,
            'commessa': self.commessa,
            'data': self.data.isoformat() if self.data else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }
