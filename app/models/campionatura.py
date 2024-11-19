from app import db
from datetime import datetime

class Campionatura(db.Model):
    __tablename__ = 'campionatura'

    id = db.Column(db.Integer, primary_key=True)
    campione = db.Column(db.String(255), nullable=False)
    start = db.Column(db.DateTime, nullable=False, default=datetime.now)
    stop = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'campione': self.campione,
            'start': self.start.isoformat(),
            'stop': self.stop.isoformat() if self.stop else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }