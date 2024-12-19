from app import db

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.Integer, nullable=False)
    task_type = db.Column(db.String(50), nullable=False)
    sent_to_cloud = db.Column(db.Integer, nullable=True, server_default='0')
    sent_to_data_center = db.Column(db.Integer, nullable=True, server_default='0')
    sent_to_device = db.Column(db.Integer, nullable=True, server_default='0')
    status = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "device_id": self.device_id,
            "task_type": self.task_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_to_cloud": self.sent_to_cloud,
            "sent_to_data_center": self.sent_to_data_center,
            "sent_to_device": self.sent_to_device,
            "status": self.status
        }
