import time
import uuid
import requests
from flask import current_app
from app.models.cache_manager import token_cache

class APIClient:
    @staticmethod
    def get_token():
        """Obtiene y refresca el token de Ingram (cached)."""
        if token_cache.is_valid():
            return token_cache.get_token()
            
        url = "https://api.ingrammicro.com/oauth/oauth20/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": current_app.config['INGRAM_CLIENT_ID'],
            "client_secret": current_app.config['INGRAM_CLIENT_SECRET']
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        res = requests.post(url, data=data, headers=headers)
        res.raise_for_status()
        token_data = res.json()

        token_cache.set_token(
            token_data["access_token"], 
            int(token_data.get("expires_in", 86399))
        )
        return token_cache.get_token()

    @staticmethod
    def get_headers():
        """Construye headers requeridos por Ingram."""
        correlation_id = str(uuid.uuid4()).replace("-", "")[:32]
        return {
            "Authorization": f"Bearer {APIClient.get_token()}",
            "IM-CustomerNumber": current_app.config['INGRAM_CUSTOMER_NUMBER'],
            "IM-SenderID": current_app.config['INGRAM_SENDER_ID'],
            "IM-CorrelationID": correlation_id,
            "IM-CountryCode": current_app.config['INGRAM_COUNTRY_CODE'],
            "Accept-Language": current_app.config['INGRAM_LANGUAGE'],
            "Content-Type": "application/json"
        }

    @staticmethod
    def make_request(method, url, **kwargs):
        """Realiza una solicitud a la API de Ingram."""
        headers = APIClient.get_headers()
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
        kwargs['headers'] = headers
        
        return requests.request(method, url, **kwargs)