from app import db

class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    device_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='inactive')
    firmware_version = db.Column(db.String(50))
    last_seen = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Device {self.user_id}, IP: {self.ip_address}, Status: {self.status}>"

    def to_dict(self):
        """Converti l'istanza del modello in un dizionario per JSON"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'device_type': self.device_type,
            'status': self.status,
            'firmware_version': self.firmware_version,
            'last_seen': self.last_seen.strftime('%Y-%m-%d %H:%M:%S') if self.last_seen else None
        }
