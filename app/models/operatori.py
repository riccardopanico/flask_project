from app import db
from sqlalchemy import func

class Operatori(db.Model):
    __tablename__ = 'operatori'

    id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    nome = db.Column(db.String(50), nullable=True)
    cognome = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'cognome': self.cognome,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }