from flask import current_app
import time

def run(app):
    while (True):
        with app.app_context():
            api_manager = current_app.api_manager
            print(api_manager.access_token)
            print(api_manager.refresh_token)
            time.sleep(1)
