from app import db
from sqlalchemy import Column, Integer, String, DateTime, func

class Device(db.Model):
    __tablename__ = 'devices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(db.Integer, unique=True, nullable=False)
    user_id = Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mac_address = Column(db.String(17), nullable=False)
    ip_address = Column(db.String(45), nullable=False)
    gateway = Column(db.String(45), nullable=False, default='192.168.1.1')
    subnet_mask = Column(db.String(45), nullable=False, default='255.255.255.0')
    dns_address = Column(db.String(45), nullable=False, default='8.8.8.8')
    created_at = Column(db.DateTime, server_default=func.now())

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
