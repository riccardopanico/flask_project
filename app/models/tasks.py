from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from sqlalchemy import func
from app import db

class Task(db.Model):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    id_dispositivo = Column(Integer, nullable=False)
    tipo_intervento = Column(String(50), nullable=False)
    data_intervento = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "id_dispositivo": self.id_dispositivo,
            "tipo_intervento": self.tipo_intervento,
            "data_intervento": self.data_intervento.isoformat()
        }
