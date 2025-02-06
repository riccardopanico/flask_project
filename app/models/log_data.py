from app import db

class LogData(db.Model):
    __tablename__ = 'log_data'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))  # Relazione con User: log generato da un utente
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id', ondelete='CASCADE'))  # Relazione con Device: log relativo a un dispositivo
    variable_id = db.Column(db.Integer, db.ForeignKey('variables.id', ondelete='CASCADE'))  # Relazione con Variables: log relativo a una variabile
    numeric_value = db.Column(db.Float)
    boolean_value = db.Column(db.Integer)
    string_value = db.Column(db.String(4000))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    sent = db.Column(db.Integer, nullable=True, server_default='0')

    # Relazione con Variables: accesso bidirezionale ai log relativi
    variable = db.relationship('Variables', back_populates='log_data')

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
