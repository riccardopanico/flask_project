from app import db

class Dipendente(db.Model):
    __tablename__ = 'dipendenti'

    id = db.Column(db.Integer, primary_key=True)
    badge = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(50), nullable=False)
    cognome = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<Dipendente {self.nome} {self.cognome} (Badge: {self.badge})>"

    def to_dict(self):
        """Converte l'oggetto in dizionario per facilitarne l'uso in API"""
        return {
            "id": self.id,
            "badge": self.badge,
            "nome": self.nome,
            "cognome": self.cognome
        }
