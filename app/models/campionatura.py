from app import db
from datetime import datetime
from sqlalchemy import func

class Campionatura(db.Model):
    __tablename__ = 'campionatura'

    id = db.Column(db.Integer, primary_key=True)
    campione = db.Column(db.String(255), nullable=False)
    start = db.Column(db.DateTime, nullable=False)
    stop = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'campione': self.campione,
            'start': self.start.isoformat(),
            'stop': self.stop.isoformat() if self.stop else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }