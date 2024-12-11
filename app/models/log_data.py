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

    @staticmethod
    def get_last_value(variable_id):
        record = LogData.query.filter_by(variable_id=variable_id).order_by(LogData.created_at.desc()).first()
        if record:
            return record.numeric_value or bool(record.boolean_value) or record.string_value
        return None
