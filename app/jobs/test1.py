# import random
# import string
# from flask import current_app

# def generate_random_token(length=6):
#     return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# def run(app):
#     with app.app_context():
#         api_manager = current_app.api_manager
#         api_manager.access_token = generate_random_token()
#         api_manager.refresh_token = generate_random_token()
