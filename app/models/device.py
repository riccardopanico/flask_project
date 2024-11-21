from app import db
from sqlalchemy import func

class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    id_dispositivo = db.Column(db.Integer, nullable=False)
    indirizzo_ip = db.Column(db.String(45), nullable=False)
    indirizzo_mac = db.Column(db.String(17), nullable=False)
    gateway = db.Column(db.String(45), nullable=False)
    subnet_mask = db.Column(db.String(45), nullable=False)
    indirizzo_dns = db.Column(db.String(45), nullable=False)
    porta_comunicazione = db.Column(db.Integer, nullable=False)
    protocollo_comunicazione = db.Column(db.String(10), nullable=False)
    id_cespite = db.Column(db.Integer, nullable=False)
    matricola = db.Column(db.String(50), nullable=False)
    numero_inventario = db.Column(db.String(50), nullable=False)
    data_collaudo = db.Column(db.DateTime, nullable=False)
    data_ultima_manutenzione = db.Column(db.DateTime, nullable=False)
    data_installazione = db.Column(db.DateTime, nullable=False)
    descrizione = db.Column(db.String(255), nullable=True)
    modello = db.Column(db.String(50), nullable=False)
    data_garanzia = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'id_dispositivo': self.id_dispositivo,
            'indirizzo_ip': self.indirizzo_ip,
            'indirizzo_mac': self.indirizzo_mac,
            'gateway': self.gateway,
            'subnet_mask': self.subnet_mask,
            'indirizzo_dns': self.indirizzo_dns,
            'porta_comunicazione': self.porta_comunicazione,
            'protocollo_comunicazione': self.protocollo_comunicazione,
            'id_cespite': self.id_cespite,
            'matricola': self.matricola,
            'numero_inventario': self.numero_inventario,
            'data_collaudo': self.data_collaudo.isoformat() if self.data_collaudo else None,
            'data_ultima_manutenzione': self.data_ultima_manutenzione.isoformat() if self.data_ultima_manutenzione else None,
            'data_installazione': self.data_installazione.isoformat() if self.data_installazione else None,
            'descrizione': self.descrizione,
            'modello': self.modello,
            'data_garanzia': self.data_garanzia.isoformat() if self.data_garanzia else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
