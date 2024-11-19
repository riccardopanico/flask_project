from app import db
from datetime import datetime

class Impostazioni(db.Model):
    __tablename__ = 'impostazioni'

    codice = db.Column(db.String(50), primary_key=True)
    descrizione = db.Column(db.String(255), nullable=False)
    valore = db.Column(db.String(4000), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'codice': self.codice,
            'descrizione': self.descrizione,
            'valore': self.valore,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }
