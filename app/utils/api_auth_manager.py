import os
import requests
from requests.exceptions import RequestException
from flask import session

class ApiAuthManager:
    def __init__(self):
        self.api_base_url = os.getenv('API_BASE_URL')
        self.username = os.getenv('API_USERNAME')
        self.password = os.getenv('API_PASSWORD')
        self.access_token = session.get('access_token')
        self.refresh_token = session.get('refresh_token')
        self.headers = {'Content-Type': 'application/json'}
        if self.access_token:
            self.headers['Authorization'] = f"Bearer {self.access_token}"

    def perform_login(self):
        url = f"{self.api_base_url}/auth/login"
        credentials = {'username': self.username, 'password': self.password}
        try:
            response = requests.post(url, json=credentials)
            if response.status_code == 200:
                response_data = response.json()
                # Salva i token sia nella sessione di Flask che come attributi della classe
                self.access_token = response_data['access_token']
                self.refresh_token = response_data['refresh_token']
                session['access_token'] = self.access_token
                session['refresh_token'] = self.refresh_token
                self.headers['Authorization'] = f"Bearer {self.access_token}"
                return {'success': True, 'data': response_data}
            else:
                return {'success': False, 'error': response.text}
        except RequestException as e:
            return {'success': False, 'error': str(e)}

    def perform_refresh_token(self):
        if not self.refresh_token:
            return {'success': False, 'error': 'Refresh token not available'}

        url = f"{self.api_base_url}/auth/token/refresh"
        headers = {'Authorization': f"Bearer {self.refresh_token}"}
        try:
            response = requests.post(url, headers=headers)
            if response.status_code == 200:
                response_data = response.json()
                # Aggiorna i token sia nella sessione di Flask che come attributi della classe
                self.access_token = response_data['access_token']
                session['access_token'] = self.access_token
                self.headers['Authorization'] = f"Bearer {self.access_token}"
                return {'success': True, 'data': response_data}
            else:
                return {'success': False, 'error': response.text}
        except RequestException as e:
            return {'success': False, 'error': str(e)}

    def call_external_api(self, url, params=None, method='GET'):
        # Verifica se esiste un access token
        if not self.access_token:
            login_response = self.perform_login()
            if not login_response['success']:
                return {'success': False, 'status': 401, 'error': f"Unable to login: {login_response['error']}"}

        # Usa l'access token aggiornato
        full_url = f"{self.api_base_url}/{url.lstrip('/')}"
        method = method.upper()

        try:
            if method == 'POST':
                response = requests.post(full_url, json=params, headers=self.headers)
            elif method == 'PUT':
                response = requests.put(full_url, json=params, headers=self.headers)
            elif method == 'DELETE':
                response = requests.delete(full_url, json=params, headers=self.headers)
            else:  # Default to GET
                response = requests.get(full_url, params=params, headers=self.headers)

            if response.status_code == 200 or response.status_code == 201:
                return {'success': True, 'data': response.json()}
            elif response.status_code == 401:
                # Token expired, prova a fare il refresh
                refresh_response = self.perform_refresh_token()
                if refresh_response['success']:
                    # Prova a richiamare l'API con il nuovo token aggiornato
                    return self.call_external_api(url, params, method)
                else:
                    return {'success': False, 'status': 401, 'error': f"Unable to refresh or login: {refresh_response['error']}"}
            else:
                return {'success': False, 'status': response.status_code, 'error': response.text}

        except RequestException as e:
            return {'success': False, 'status': 500, 'error': str(e)}
