from app import db
from sqlalchemy import Column, Integer, String, DateTime, func

class Task(db.Model):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, nullable=False)
    task_type = Column(String(50), nullable=False)
    sent = Column(Integer, nullable=True, server_default='0')
    status = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "task_type": self.task_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent": self.sent,
            "status": self.status
        }
