# app/utils/api_client.py - VERSIÓN CORREGIDA
import time
import uuid
import requests
from flask import current_app
from app.utils.cache_manager import token_cache

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
        # Convertir URLs relativas
        if not url.startswith('http'):
            if url.startswith('/'):
                url = f"https://api.ingrammicro.com{url}"
            else:
                url = f"https://api.ingrammicro.com/{url}"
        
        # FIX para peticiones POST con params
        if method.upper() == 'POST' and 'params' in kwargs:
            params = kwargs['params']
            if params:
                params_str = '&'.join([f"{k}={v}" for k, v in params.items()])
                url = f"{url}?{params_str}" if '?' not in url else f"{url}&{params_str}"
            del kwargs['params']  # Eliminar para evitar duplicados
        
        headers = APIClient.get_headers()
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
        kwargs['headers'] = headers
        
        print(f"🔧 URL final: {method} {url}")  # Para debug
        
        return requests.request(method, url, **kwargs)
        
    # MÉTODO CORREGIDO para precios
    @staticmethod
    def get_product_price_and_availability(sku):
        """Get real-time price and availability for a product - VERSIÓN CORREGIDA"""
        try:
            # URL con parámetros incluidos directamente
            url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability?includeAvailability=true&includePricing=true&includeProductAttributes=true"
            payload = {
                "products": [{"ingramPartNumber": sku}]
            }
            
            # SIN params - solo json payload
            response = APIClient.make_request("POST", url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            if isinstance(data, list) and data:
                return data[0]
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"API Error for SKU {sku}: {str(e)}")
            return None
    
    @staticmethod
    def search_products(query, page=1, page_size=25, filters=None):
        """Search products with advanced filtering"""
        try:
            url = "https://api.ingrammicro.com/resellers/v6/catalog"
            params = {
                "pageNumber": page,
                "pageSize": page_size,
                "searchString": query,
                "searchInDescription": "true"
            }
            
            if filters:
                if filters.get('vendor'):
                    params['vendor'] = filters['vendor']
                if filters.get('category'):
                    params['category'] = filters['category']
            
            response = APIClient.make_request("GET", url, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Search API Error: {str(e)}")
            return None
    
    @staticmethod
    def get_product_details(sku):
        """Get detailed product information"""
        try:
            url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{sku}"
            response = APIClient.make_request("GET", url)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Product Details API Error: {str(e)}")
            return None