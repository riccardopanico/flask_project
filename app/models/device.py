from app import db
from sqlalchemy import func

class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    device_id = db.Column(db.Integer, nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    mac_address = db.Column(db.String(17), nullable=False)
    gateway = db.Column(db.String(45), nullable=False)
    subnet_mask = db.Column(db.String(45), nullable=False)
    dns_address = db.Column(db.String(45), nullable=False)
    communication_port = db.Column(db.Integer, nullable=False)
    communication_protocol = db.Column(db.String(10), nullable=False)
    asset_id = db.Column(db.Integer, nullable=False)
    registration_number = db.Column(db.String(50), nullable=False)
    inventory_number = db.Column(db.String(50), nullable=False)
    test_date = db.Column(db.DateTime, nullable=False)
    last_maintenance_date = db.Column(db.DateTime, nullable=False)
    installation_date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    model = db.Column(db.String(50), nullable=False)
    serial_number = db.Column(db.String(50), nullable=False)
    warranty_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'device_id': self.device_id,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'gateway': self.gateway,
            'subnet_mask': self.subnet_mask,
            'dns_address': self.dns_address,
            'communication_port': self.communication_port,
            'communication_protocol': self.communication_protocol,
            'asset_id': self.asset_id,
            'registration_number': self.registration_number,
            'inventory_number': self.inventory_number,
            'test_date': self.test_date.isoformat() if self.test_date else None,
            'last_maintenance_date': self.last_maintenance_date.isoformat() if self.last_maintenance_date else None,
            'installation_date': self.installation_date.isoformat() if self.installation_date else None,
            'description': self.description,
            'model': self.model,
            'serial_number': self.serial_number,
            'warranty_date': self.warranty_date.isoformat() if self.warranty_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
