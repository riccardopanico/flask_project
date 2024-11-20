from app import db

class Impostazioni(db.Model):
    __tablename__ = 'impostazioni'

    codice = db.Column(db.String(50), primary_key=True)
    descrizione = db.Column(db.String(255), nullable=False)
    valore = db.Column(db.String(4000), nullable=True)

    def to_dict(self):
        return {
            'codice': self.codice,
            'descrizione': self.descrizione,
            'valore': self.valore
        }
