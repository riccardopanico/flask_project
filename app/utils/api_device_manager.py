import os
import requests
from requests.exceptions import RequestException
from flask import current_app

class ApiDeviceManager:
    def __init__(self, ip_address, username=None, password=None):
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.api_base_url = f"http://{self.ip_address}:5000/api"
        self.access_token = None
        self.refresh_token = None
        self.headers = {'Content-Type': 'application/json'}

        if not self.ip_address:
            raise ValueError("IP_ADDRESS deve essere impostato.")

        if (self.username and not self.password) or (not self.username and self.password):
            raise ValueError("USERNAME e PASSWORD devono essere impostati entrambi o nessuno.")

    def _login(self):
        """Effettua il login e ottiene i token di accesso."""
        url = f"{self.api_base_url}/auth/login"
        credentials = {'username': self.username, 'password': self.password}
        try:
            response = requests.post(url, json=credentials)
            if response.status_code == 200:
                response_data = response.json()
                self.access_token = response_data['access_token']
                self.refresh_token = response_data['refresh_token']
                self.headers['Authorization'] = f"Bearer {self.access_token}"
                return {'success': True, 'data': response_data}
            else:
                return {'success': False, 'error': response.text}
        except RequestException as e:
            return {'success': False, 'error': str(e)}

    def _refresh_token(self):
        """Effettua il refresh del token di accesso."""
        if not self.refresh_token:
            return self._login()

        url = f"{self.api_base_url}/auth/token/refresh"
        headers = {'Authorization': f"Bearer {self.refresh_token}"}
        try:
            response = requests.post(url, headers=headers)
            if response.status_code == 200:
                response_data = response.json()
                self.access_token = response_data['access_token']
                self.headers['Authorization'] = f"Bearer {self.access_token}"
                return {'success': True, 'data': response_data}
            else:
                return self._login()
        except RequestException as e:
            return self._login()

    def call(self, url, params=None, method='GET', requires_auth=True):
        """Esegue una chiamata API verso un endpoint esterno."""
        full_url = f"{self.api_base_url}/{url.lstrip('/')}"
        current_app.logger.debug(f"Chiamata API: {full_url}")
        method = method.upper()

        if requires_auth:
            if not self.access_token:
                login_response = self._login()
                if not login_response['success']:
                    return {'success': False, 'status': 401, 'error': f"Unable to login: {login_response['error']}"}

        try:
            headers = self.headers if requires_auth else {'Content-Type': 'application/json'}
            if method == 'POST':
                response = requests.post(full_url, json=params, headers=headers)
            elif method == 'PUT':
                response = requests.put(full_url, json=params, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(full_url, json=params, headers=headers)
            else:  # Default to GET
                response = requests.get(full_url, params=params, headers=headers)

            if response.status_code in [200, 201]:
                return response.json()
            elif response.status_code == 401 and requires_auth:
                refresh_response = self._refresh_token()
                if refresh_response['success']:
                    return self.call(url, params, method, requires_auth=True)
                else:
                    return {'success': False, 'status': 401, 'error': f"Unable to refresh or login: {refresh_response['error']}"}
            else:
                return {'success': False, 'status': response.status_code, 'error': response.text}

        except RequestException as e:
            return {'success': False, 'status': 500, 'error': str(e)}
