import os
import requests
from requests.exceptions import RequestException
from flask import g

class ApiAuthManager:
    def __init__(self):
        self.api_base_url = os.getenv('API_BASE_URL')
        self.username = os.getenv('API_USERNAME')
        self.password = os.getenv('API_PASSWORD')
        self.access_token = self._get_token('access_token')
        self.refresh_token = self._get_token('refresh_token')
        self.headers = {'Content-Type': 'application/json'}
        if self.access_token:
            self.headers['Authorization'] = f"Bearer {self.access_token}"

    def _get_token(self, token_name):
        # Usa `g` per mantenere i token tra le richieste anche fuori dal contesto di richiesta HTTP
        if hasattr(g, token_name):
            print(f"Token '{token_name}' trovato in g.")
            return getattr(g, token_name)
        else:
            print(f"Token '{token_name}' non trovato in g.")
            return None

    def _set_token(self, token_name, value):
        # Salva il token in `g` per contesto globale
        setattr(g, token_name, value)
        print(f"Token '{token_name}' impostato in g.")

    def perform_login(self):
        url = f"{self.api_base_url}/auth/login"
        credentials = {'username': self.username, 'password': self.password}
        try:
            response = requests.post(url, json=credentials)
            if response.status_code == 200:
                response_data = response.json()
                # Salva i token come attributi della classe e nel contesto globale
                self.access_token = response_data['access_token']
                self.refresh_token = response_data['refresh_token']
                self._set_token('access_token', self.access_token)
                self._set_token('refresh_token', self.refresh_token)
                self.headers['Authorization'] = f"Bearer {self.access_token}"
                print("Login effettuato con successo.")
                return {'success': True, 'data': response_data}
            else:
                print(f"Errore durante il login: {response.text}")
                return {'success': False, 'error': response.text}
        except RequestException as e:
            print(f"Eccezione durante il login: {str(e)}")
            return {'success': False, 'error': str(e)}

    def perform_refresh_token(self):
        if not self.refresh_token:
            print("Refresh token non disponibile.")
            return {'success': False, 'error': 'Refresh token not available'}

        url = f"{self.api_base_url}/auth/token/refresh"
        headers = {'Authorization': f"Bearer {self.refresh_token}"}
        try:
            response = requests.post(url, headers=headers)
            if response.status_code == 200:
                response_data = response.json()
                # Aggiorna i token come attributi della classe e nel contesto globale
                self.access_token = response_data['access_token']
                self._set_token('access_token', self.access_token)
                self.headers['Authorization'] = f"Bearer {self.access_token}"
                print("Refresh token effettuato con successo.")
                return {'success': True, 'data': response_data}
            else:
                print(f"Errore durante il refresh del token: {response.text}")
                return {'success': False, 'error': response.text}
        except RequestException as e:
            print(f"Eccezione durante il refresh del token: {str(e)}")
            return {'success': False, 'error': str(e)}

    def call_external_api(self, url, params=None, method='GET'):
        # Verifica se esiste un access token
        if not self.access_token:
            print("Access token non trovato, tentativo di login.")
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
                print("Chiamata API riuscita.")
                return {'success': True, 'data': response.json()}
            elif response.status_code == 401:
                print("Token scaduto, tentativo di refresh.")
                # Token expired, prova a fare il refresh
                refresh_response = self.perform_refresh_token()
                if refresh_response['success']:
                    # Prova a richiamare l'API con il nuovo token aggiornato
                    return self.call_external_api(url, params, method)
                else:
                    return {'success': False, 'status': 401, 'error': f"Unable to refresh or login: {refresh_response['error']}"}
            else:
                print(f"Errore durante la chiamata API: {response.text}")
                return {'success': False, 'status': response.status_code, 'error': response.text}

        except RequestException as e:
            print(f"Eccezione durante la chiamata API: {str(e)}")
            return {'success': False, 'status': 500, 'error': str(e)}
