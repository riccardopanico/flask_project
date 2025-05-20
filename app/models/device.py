import json
from app import db

class Device(db.Model):
    __tablename__ = 'devices'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    interconnection_id = db.Column(db.Integer, unique=True, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    mac_address = db.Column(db.String(17), nullable=True)
    ip_address = db.Column(db.String(45), nullable=False)
    config = db.Column(db.Text, nullable=True)
    gateway = db.Column(db.String(45), nullable=True)
    subnet_mask = db.Column(db.String(45), nullable=True)
    dns_address = db.Column(db.String(45), nullable=True)
    port_address = db.Column(db.String(5), nullable=True)
    username = db.Column(db.String(255), nullable=True)
    password = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship('User', back_populates='devices')
    variables = db.relationship('Variables', back_populates='device', passive_deletes=True)
    log_data = db.relationship('LogData', back_populates='device', passive_deletes=True)
    tasks = db.relationship('Task', back_populates='device', passive_deletes=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'interconnection_id': self.interconnection_id,
            'user_id': self.user_id,
            'mac_address': self.mac_address,
            'ip_address': self.ip_address,
            'gateway': self.gateway,
            'subnet_mask': self.subnet_mask,
            'dns_address': self.dns_address,
            'port_address': self.port_address,
            'username': self.username,
            'password': self.password,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'config': json.loads(self.config)
        }
