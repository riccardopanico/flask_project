from app import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    badge = db.Column(db.String(50), nullable=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    user_type = db.Column(db.String(50), nullable=False)  # "device" o "human"
    name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    devices = db.relationship('Device', back_populates='user')
    log_data = db.relationship('LogData', back_populates='user', passive_deletes=True)

    def set_password(self, password):
        """Hash della password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica della password hashata."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """Rappresentazione del modello come dizionario."""
        return {
            'id': self.id,
            'badge': self.badge,
            'username': self.username,
            'user_type': self.user_type,
            'name': self.name,
            'last_name': self.last_name,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }