from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app import db

class Intervento(db.Model):
    __tablename__ = 'interventi'

    id = Column(Integer, primary_key=True)
    id_dispositivo = Column(Integer, nullable=False)
    tipo_intervento = Column(String(50), nullable=False)
    data_intervento = Column(DateTime, nullable=False, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "id_dispositivo": self.id_dispositivo,
            "tipo_intervento": self.tipo_intervento,
            "data_intervento": self.data_intervento.isoformat()
        }
