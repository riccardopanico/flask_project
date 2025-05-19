from app import db

# Importiamo prima i modelli base senza relazioni
from app.models.user import User
from app.models.device import Device
from app.models.variables import Variables
from app.models.task import Task
from app.models.log_data import LogData

# Ora che tutti i modelli sono importati, possiamo definire le relazioni
User.devices = db.relationship('Device', back_populates='user', passive_deletes=True)
User.log_data = db.relationship('LogData', back_populates='user', passive_deletes=True)

Device.user = db.relationship('User', back_populates='devices')
Device.variables = db.relationship('Variables', back_populates='device', passive_deletes=True)
Device.log_data = db.relationship('LogData', back_populates='device', passive_deletes=True)
Device.tasks = db.relationship('Task', back_populates='device', passive_deletes=True)

Variables.device = db.relationship('Device', back_populates='variables')
Variables.log_data = db.relationship('LogData', back_populates='variable', passive_deletes=True)

Task.device = db.relationship('Device', back_populates='tasks')

LogData.user = db.relationship('User', back_populates='log_data', lazy='joined')
LogData.device = db.relationship('Device', back_populates='log_data', lazy='joined')
LogData.variable = db.relationship('Variables', back_populates='log_data', lazy='joined')
