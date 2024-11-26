from app import db
from sqlalchemy import Column, Integer, String, DateTime, func

class Campionatura(db.Model):
    __tablename__ = 'campionatura'

    id = Column(Integer, primary_key=True, autoincrement=True)
    campione = Column(db.String(255), nullable=False)
    start = Column(db.DateTime, nullable=False)
    stop = Column(db.DateTime, nullable=True)
    created_at = Column(db.DateTime, server_default=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'campione': self.campione,
            'start': self.start.isoformat(),
            'stop': self.stop.isoformat() if self.stop else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
