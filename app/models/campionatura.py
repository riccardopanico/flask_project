from app import db
from datetime import datetime

class Campionatura(db.Model):
    __tablename__ = 'campionatura'

    id = db.Column(db.Integer, primary_key=True)
    campione = db.Column(db.String(100), nullable=False)
    start = db.Column(db.DateTime, nullable=False, default=datetime.now)
    stop = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, campione, start=None, stop=None):
        self.campione = campione
        self.start = start if start else datetime.now()
        self.stop = stop
