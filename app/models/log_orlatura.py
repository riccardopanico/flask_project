from app import db
from datetime import datetime

class LogOrlatura(db.Model):
    __tablename__ = 'log_orlatura'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.Integer, nullable=False)
    id_operatore = db.Column(db.String(50), nullable=False)
    consumo = db.Column(db.Numeric(precision=11, scale=2), nullable=False, default=0.00)
    tempo = db.Column(db.Integer, nullable=False, default=0)
    commessa = db.Column(db.String(255), nullable=False)
    data = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), default=datetime.now)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'id_operatore': self.id_operatore,
            'consumo': str(self.consumo),
            'tempo': self.tempo,
            'commessa': self.commessa,
            'data': self.data.isoformat() if self.data else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
