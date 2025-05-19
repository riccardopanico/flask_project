from app import db
from sqlalchemy.orm import relationship

class LogData(db.Model):
    __tablename__ = 'log_data'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id', ondelete='CASCADE'))
    variable_id = db.Column(db.Integer, db.ForeignKey('variables.id', ondelete='CASCADE'))
    numeric_value = db.Column(db.Float)
    boolean_value = db.Column(db.Integer)
    string_value = db.Column(db.String(4000))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    sent = db.Column(db.Integer, nullable=True, server_default='0')

    # Relazioni
    user = relationship('User', back_populates='log_data', lazy='joined')
    device = relationship('Device', back_populates='log_data', lazy='joined')
    variable = relationship('Variables', back_populates='log_data', lazy='joined')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'device_id': self.device_id,
            'variable_id': self.variable_id,
            'numeric_value': self.numeric_value,
            'boolean_value': self.boolean_value,
            'string_value': self.string_value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'sent': self.sent
        }

    def get_value(self):
        if self.boolean_value is not None:
            return bool(self.boolean_value)
        if self.string_value is not None:
            return self.string_value
        if self.numeric_value is not None:
            return self.numeric_value
        return None

    @staticmethod
    def get_last_value(variable_id):
        rec = LogData.query.filter_by(variable_id=variable_id).order_by(LogData.created_at.desc()).first()
        if not rec:
            return None
        return rec.get_value()