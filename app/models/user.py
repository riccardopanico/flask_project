from app import db
from sqlalchemy import Column, Integer, String, DateTime, func
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    badge = Column(db.String(50), nullable=True)
    username = Column(db.String(100), unique=True, nullable=False)
    password_hash = Column(db.String(255), nullable=False)
    user_type = Column(db.String(50), nullable=False)
    name = Column(db.String(100), nullable=True)
    last_name = Column(db.String(100), nullable=True)
    email = Column(db.String(100), nullable=True)
    created_at = Column(db.DateTime, server_default=func.now())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'badge': self.badge,
            'username': self.username,
            'user_type': self.user_type,
            'name': self.name,
            'last_name': self.last_name,
            'email': self.email
        }
