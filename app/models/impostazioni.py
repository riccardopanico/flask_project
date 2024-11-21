from app import db
from sqlalchemy import func

class Impostazioni(db.Model):
    __tablename__ = 'impostazioni'

    codice = db.Column(db.String(50), primary_key=True)
    descrizione = db.Column(db.String(255), nullable=False)
    valore = db.Column(db.String(4000), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now())

    def to_dict(self):
        return {
            'codice': self.codice,
            'descrizione': self.descrizione,
            'valore': self.valore,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
