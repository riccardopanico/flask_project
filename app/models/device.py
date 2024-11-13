from app import db

class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    user = db.relationship('User', backref=db.backref('device', uselist=False))
    ip_address = db.Column(db.String(45), nullable=False)
    device_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='inactive')
    firmware_version = db.Column(db.String(50))

    def __repr__(self):
        return f"<Device {self.user.username}, IP: {self.ip_address}, Status: {self.status}>"

    def to_dict(self):
        """Converti l'istanza del modello in un dizionario per JSON"""
        return {
            'id': self.id,
            'matricola': self.user.username,
            'ip_address': self.ip_address,
            'device_type': self.device_type,
            'status': self.status,
            'firmware_version': self.firmware_version
        }
