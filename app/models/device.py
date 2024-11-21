from app import db
from sqlalchemy import func

class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mac_address = db.Column(db.String(17), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    gateway = db.Column(db.String(45), nullable=False, default='192.168.1.1')
    subnet_mask = db.Column(db.String(45), nullable=False, default='255.255.255.0')
    dns_address = db.Column(db.String(45), nullable=False, default='8.8.8.8')
    created_at = db.Column(db.DateTime, server_default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'user_id': self.user_id,
            'mac_address': self.mac_address,
            'ip_address': self.ip_address,
            'gateway': self.gateway,
            'subnet_mask': self.subnet_mask,
            'dns_address': self.dns_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
