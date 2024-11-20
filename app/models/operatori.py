from app import db

class Operatori(db.Model):
    __tablename__ = 'operatori'

    id = db.Column(db.String(50), primary_key=True)
    nome = db.Column(db.String(50), nullable=True)
    cognome = db.Column(db.String(50), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'cognome': self.cognome
        }