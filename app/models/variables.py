from sqlalchemy.orm import sessionmaker
from app import db
from app.models.log_data import LogData

class Variables(db.Model):
    __tablename__ = 'variables'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    variable_name = db.Column(db.String(255), nullable=False)
    variable_code = db.Column(db.String(255), unique=True, nullable=False)
    boolean_value = db.Column(db.Integer)
    string_value = db.Column(db.String(255))
    numeric_value = db.Column(db.Float)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
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
        elif self.string_value is not None:
            return self.string_value
        elif self.numeric_value is not None:
            return self.numeric_value
        return None

    def set_value(self, value):
        if value is None:
            raise ValueError("Il valore non può essere None.")

        # Resetta tutti i campi prima di impostare un nuovo valore
        self.boolean_value = None
        self.string_value = None
        self.numeric_value = None

        # Imposta il campo appropriato in base al tipo di valore
        if isinstance(value, bool):
            self.boolean_value = int(value)
        elif isinstance(value, str):
            self.string_value = value
        elif isinstance(value, (int, float)):
            self.numeric_value = value
        else:
            raise TypeError("Tipo di valore non supportato. Deve essere bool, str, int o float.")

        db.session.add(self)
        db.session.commit()

        log_entry = LogData(
            user_id = Variables.query.filter_by(variable_code='user_id').first().get_value(),
            device_id=self.device_id,
            variable_id=self.id,
            numeric_value=self.numeric_value if isinstance(value, (int, float)) else None,
            boolean_value=self.boolean_value if isinstance(value, bool) else None,
            string_value=self.string_value if isinstance(value, str) else None
        )
        db.session.add(log_entry)
        db.session.commit()
