from app import db

class Variables(db.Model):
    __tablename__ = 'variables'
    __table_args__ = (
        db.UniqueConstraint('device_id', 'variable_code', name='uq_device_variable'),
        {'extend_existing': True}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id', ondelete='CASCADE'), nullable=False)
    variable_name = db.Column(db.String(255), nullable=False)
    variable_code = db.Column(db.String(255), nullable=False)
    boolean_value = db.Column(db.Integer)
    string_value = db.Column(db.String(4000))
    numeric_value = db.Column(db.Float)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    device = db.relationship('Device', back_populates='variables')
    log_data = db.relationship('LogData', back_populates='variable', passive_deletes=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'device_id': self.device_id,
            'variable_name': self.variable_name,
            'variable_code': self.variable_code,
            'boolean_value': self.boolean_value,
            'string_value': self.string_value,
            'numeric_value': self.numeric_value
        }

    def get_value(self):
        if self.boolean_value is not None:
            return bool(self.boolean_value)
        if self.string_value is not None:
            return self.string_value
        if self.numeric_value is not None:
            return self.numeric_value
        return None

    def set_value(self, value):
        self.boolean_value = None
        self.string_value = None
        self.numeric_value = None
        if isinstance(value, bool):
            self.boolean_value = int(value)
        elif isinstance(value, str):
            self.string_value = value
        elif isinstance(value, (int, float)):
            self.numeric_value = value
        else:
            raise TypeError('Value must be bool, str, int or float')
        db.session.add(self)
        db.session.commit()

        from app.models.log_data import LogData
        user_var = Variables.query.filter_by(variable_code='user_id').first()
        user_id = user_var.get_value() if user_var else None
        entry = LogData(
            user_id=user_id,
            device_id=self.device_id,
            variable_id=self.id,
            numeric_value=self.numeric_value,
            boolean_value=self.boolean_value,
            string_value=self.string_value
        )
        db.session.add(entry)
        db.session.commit()