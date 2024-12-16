import os
import requests
import base64
from requests.exceptions import RequestException

class ApiOracleManager:
    def __init__(self):
        self.api_base_url = os.getenv('API_BASE_URL')
        self.client_id = os.getenv('API_CLIENT_ID')
        self.client_secret = os.getenv('API_CLIENT_SECRET')
        self.token_url = os.getenv('API_TOKEN_URL')

        if not all([self.api_base_url, self.client_id, self.client_secret, self.token_url]):
            raise ValueError("API_BASE_URL, API_CLIENT_ID, API_CLIENT_SECRET e API_TOKEN_URL devono essere impostati nelle variabili d'ambiente.")

        self.access_token = None
        self.headers = {'Content-Type': 'application/json'}

    def _get_access_token(self):
        """Ottiene un nuovo access token."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

        payload = 'grant_type=client_credentials&scope=offline_access'
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {encoded_credentials}',
        }

        try:
            response = requests.post(self.token_url, headers=headers, data=payload)

            if response.status_code == 200:
                data = response.json()
                self.access_token = data['access_token']
                self.headers['Authorization'] = f'Bearer {self.access_token}'
                return {'success': True, 'data': data}
            else:
                return {'success': False, 'error': response.text}
        except RequestException as e:
            return {'success': False, 'error': str(e)}

    def call(self, url, params=None, method='GET'):
        """Esegue una chiamata verso un endpoint esterno protetto."""
        if not self.access_token:
            token_response = self._get_access_token()
            if not token_response['success']:
                raise Exception(f"Errore nel recupero del token: {token_response['error']}")

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
                # Token non valido, rigeneralo
                self._get_access_token()
                return self.call(url, params, method)
            else:
                return {'success': False, 'status': response.status_code, 'error': response.text}

        except RequestException as e:
            return {'success': False, 'status': 500, 'error': str(e)}
