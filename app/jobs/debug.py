from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from datetime import timedelta
from app.models.tasks import Task

JOB_INTERVAL = timedelta(seconds=2)

def run(app):
    with app.app_context():
        current_app.logger.debug(f"Start job {__name__}...")
