from app import db

class Task(db.Model):
    __tablename__ = 'tasks'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id', ondelete='CASCADE'))
    task_type = db.Column(db.String(50), nullable=False)
    sent = db.Column(db.Integer, nullable=True, server_default='0')
    status = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    device = db.relationship('Device', back_populates='tasks')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'device_id': self.device_id,
            'task_type': self.task_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent': self.sent,
            'status': self.status
        }