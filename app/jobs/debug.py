from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from app import db
from datetime import timedelta
from app.models.tasks import Task

JOB_INTERVAL = timedelta(seconds=2)

def run(app):
    with app.app_context():
        current_app.logger.debug(f"Chiavi disponibili in app.api_device_manager: {list(app.api_device_manager.keys())}")

        for username, api_manager in app.api_device_manager.items():
            current_app.logger.debug(f"Username: {username}")
            current_app.logger.debug(f"Username: {api_manager.username}")
            current_app.logger.debug(f"Password: {api_manager.password}")
            current_app.logger.debug(f"Access Token: {api_manager.access_token}")
            current_app.logger.debug(f"Refresh Token: {api_manager.refresh_token}")
