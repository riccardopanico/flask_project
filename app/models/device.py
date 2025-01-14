from app import db

class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    interconnection_id = db.Column(db.Integer, unique=True, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    mac_address = db.Column(db.String(17), nullable=True)
    ip_address = db.Column(db.String(45), nullable=False)
    gateway = db.Column(db.String(45), nullable=True)
    subnet_mask = db.Column(db.String(45), nullable=True)
    dns_address = db.Column(db.String(45), nullable=True)
    port_address = db.Column(db.String(5), nullable=True)
    username = db.Column(db.String(255), nullable=True)
    password = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relazione con LogData: ogni dispositivo può avere molti dati di log
    log_data = db.relationship('LogData', backref='device', passive_deletes=True)

    # Relazione con Task: ogni dispositivo può avere molti task associati
    tasks = db.relationship('Task', backref='device', passive_deletes=True)

    # Relazione con Variables: ogni dispositivo può avere molte variabili
    variables = db.relationship('Variables', backref='device', passive_deletes=True)

    # Relazione con User: ogni dispositivo appartiene a un utente
    user = db.relationship('User', back_populates='devices')

    def to_dict(self):
        """Rappresentazione del modello come dizionario."""
        return {
            'id': self.id,
            'interconnection_id': self.interconnection_id,
            'user_id': self.user_id,  # Include l'utente associato (se esiste)
            'mac_address': self.mac_address,
            'ip_address': self.ip_address,
            'gateway': self.gateway,
            'subnet_mask': self.subnet_mask,
            'dns_address': self.dns_address,
            'port_address': self.port_address,
            'username': self.username,
            'password': self.password,  # Escludere dalle API pubbliche
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
