from app import db
from sqlalchemy import Column, Integer, String, DateTime, func
from datetime import datetime

class LogData(db.Model):
    __tablename__ = 'log_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    device_id = Column(Integer, ForeignKey('devices.id'))
    variable_id = Column(Integer, ForeignKey('variables.id'))
    numeric_value = Column(Float)
    boolean_value = Column(Integer)
    string_value = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())

    @staticmethod
    def get_last_value(variable_id):
        record = LogData.query.filter_by(variable_id=variable_id).order_by(LogData.created_at.desc()).first()
        if record:
            return record.numeric_value or bool(record.boolean_value) or record.string_value
        return None
