from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True)
    matricola = db.Column(db.String(100), unique=True, nullable=False)  # Come username
    password_hash = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)  # Supporto per IPv6
    device_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='inactive')
    firmware_version = db.Column(db.String(50))  # Maggiore spazio per le versioni più lunghe

    def set_password(self, password):
        """Genera l'hash della password e lo salva."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica se la password è corretta."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Device {self.matricola}, IP: {self.ip_address}, Status: {self.status}, Last Seen: {self.last_seen}>"

    def to_dict(self):
        """Converti l'istanza del modello in un dizionario per JSON"""
        return {
            'id': self.id,
            'matricola': self.matricola,
            'ip_address': self.ip_address,
            'device_type': self.device_type,
            'status': self.status,
            'firmware_version': self.firmware_version
        }