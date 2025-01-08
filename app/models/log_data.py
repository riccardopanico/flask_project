from app import db

class LogData(db.Model):
    __tablename__ = 'log_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    variable_id = db.Column(db.Integer, db.ForeignKey('variables.id'))
    numeric_value = db.Column(db.Float)
    boolean_value = db.Column(db.Integer)
    string_value = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    sent = db.Column(db.Integer, nullable=True, server_default='0')

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "variable_id": self.variable_id,
            "numeric_value": self.numeric_value,
            "boolean_value": self.boolean_value,
            "string_value": self.string_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent": self.sent,
        }

    @staticmethod
    def get_last_value(variable_id):
        record = LogData.query.filter_by(variable_id=variable_id).order_by(LogData.created_at.desc()).first()
        if record:
            return record.numeric_value or bool(record.boolean_value) or record.string_value
        return None
