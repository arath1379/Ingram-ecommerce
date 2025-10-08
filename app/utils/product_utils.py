# app/utils/product_utils.py - VERSIÓN EXTENDIDA
from flask import current_app
from collections import defaultdict
from datetime import datetime, timedelta
from app.models.api_client import APIClient
import re
import time
import requests
import json
from typing import Dict, List, Optional

class ProductUtils:
    # Diccionario de palabras clave y términos relacionados
    KEYWORD_MAPPING = {
        'laptop': ['laptop', 'notebook', 'portatil'],
        'desktop': ['desktop', 'pc', 'computadora'],
        'monitor': ['monitor', 'pantalla', 'display'],
        'telefono': ['telefono', 'celular', 'smartphone'],
        'tablet': ['tablet', 'ipad', 'tableta'],
    }

    SEARCH_CACHE_DURATION = 300  # 5 minutos
    POPULAR_SEARCHES = defaultdict(int)
    SEARCH_HISTORY = []
    MAX_SEARCH_HISTORY = 50
    
    # Cache para tokens de API
    _token_cache = {
        'token': None,
        'expires_at': 0
    }

    @staticmethod
    def get_local_vendors():
        """Obtiene lista de vendedores locales."""
        return [
            "HP", "Dell", "Lenovo", "Cisco", "Apple", "Microsoft", 
            "Samsung", "ASUS", "Acer", "Logitech", "Kingston"
        ]

    @staticmethod
    def format_currency(amount, currency_code='MXN'):
        """Formatea moneda correctamente."""
        if amount is None or amount == 0:
            return "No disponible"
        
        try:
            amount = float(amount)
            if currency_code in ['MXP', 'MXN']:
                return f"${amount:,.2f} MXN"
            elif currency_code == 'USD':
                return f"USD ${amount:,.2f}"
            else:
                return f"${amount:,.2f} {currency_code}"
        except (ValueError, TypeError):
            return "No disponible"

    @staticmethod
    def normalize_text(text):
        """Normaliza texto para búsqueda."""
        if not text:
            return ""
        text = text.lower()
        replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        return ' '.join(text.split())

    @staticmethod
    def track_search(query):
        """Registra una búsqueda en el historial."""
        if not query.strip():
            return
        clean_query = query.strip().lower()
        ProductUtils.POPULAR_SEARCHES[clean_query] += 1
        if clean_query not in ProductUtils.SEARCH_HISTORY:
            ProductUtils.SEARCH_HISTORY.insert(0, clean_query)
            if len(ProductUtils.SEARCH_HISTORY) > ProductUtils.MAX_SEARCH_HISTORY:
                ProductUtils.SEARCH_HISTORY.pop()

    @staticmethod
    def get_popular_searches(limit=10):
        """Obtiene las búsquedas más populares."""
        return sorted(ProductUtils.POPULAR_SEARCHES.items(), 
                     key=lambda x: x[1], reverse=True)[:limit]

    @staticmethod
    def optimize_search_query(query):
        """Optimiza la query para mejores resultados."""
        if not query:
            return ""
        stop_words = {'el', 'la', 'los', 'las', 'un', 'una', 'de', 'en', 'con'}
        words = query.split()
        filtered_words = [word for word in words if word.lower() not in stop_words]
        return ' '.join(filtered_words).strip()

    # ======================= MÉTODOS API INGRAM MICRO =======================
    
    @staticmethod
    def get_access_token():
        """Obtener token de acceso con cache"""
        current_time = time.time()
        
        # Si el token está válido (con 5 minutos de margen), usarlo
        if (ProductUtils._token_cache['token'] and 
            current_time < ProductUtils._token_cache['expires_at'] - 300):
            return ProductUtils._token_cache['token']
        
        # Solicitar nuevo token
        try:
            auth_url = f"{current_app.config.get('INGRAM_API_BASE_URL')}/oauth/oauth20/token"
            
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': current_app.config.get('INGRAM_CLIENT_ID'),
                'client_secret': current_app.config.get('INGRAM_CLIENT_SECRET')
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            response = requests.post(auth_url, data=auth_data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                expires_in = int(token_data.get('expires_in', 3600))  # Convertir a entero
                
                # Actualizar cache
                ProductUtils._token_cache = {
                    'token': access_token,
                    'expires_at': current_time + expires_in
                }
                
                return access_token
            else:
                print(f"Error obteniendo token: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Excepción obteniendo token: {str(e)}")
            return None
    
    @staticmethod
    def get_api_headers():
        """Headers para llamadas API"""
        token = ProductUtils.get_access_token()
        if not token:
            return None
            
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'IM-CustomerNumber': current_app.config.get('INGRAM_CUSTOMER_NUMBER'),
            'IM-CountryCode': current_app.config.get('INGRAM_COUNTRY_CODE', 'MX'),
            'IM-SenderID': current_app.config.get('INGRAM_SENDER_ID'),
            'IM-CorrelationID': current_app.config.get('INGRAM_CORRELATION_ID'),
            'Accept-Language': 'es-MX'
        }
    
    @staticmethod
    def search_products(query='', vendor='', page=1, page_size=25):
        """Búsqueda de productos desde API de Ingram Micro"""
        try:
            # Registrar búsqueda si hay query
            if query:
                ProductUtils.track_search(query)
                query = ProductUtils.optimize_search_query(query)
            
            headers = ProductUtils.get_api_headers()
            if not headers:
                print("No se pudo obtener headers de API")
                return {'products': [], 'total': 0}
            
            base_url = current_app.config.get('INGRAM_API_BASE_URL')
            endpoint = f"{base_url}/resellers/v6/catalog"
            
            params = {
                'pageSize': page_size,
                'pageNumber': page,
                'showGroupInfo': 'False'
            }
            
            # Agregar filtros de búsqueda
            if query:
                params['keyword'] = query
            if vendor:
                params['vendor'] = vendor
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                products = data.get('catalog', [])
                total_records = data.get('recordsFound', 0)
                
                # Transformar datos para compatibilidad con templates
                processed_products = []
                for product in products:
                    processed_product = {
                        'ingramPartNumber': product.get('ingramPartNumber'),
                        'vendorName': product.get('vendorName'),
                        'description': product.get('description'),
                        'vendorPartNumber': product.get('vendorPartNumber'),
                        'category': product.get('category'),
                        'subCategory': product.get('subCategory'),
                        'upcCode': product.get('upcCode'),
                        'endUserRequired': product.get('endUserRequired', 'False'),
                        'hasDiscounts': product.get('hasDiscounts', 'False'),
                        'productImages': ['/static/images/placeholder.png'],
                        'pricing': {'customerPrice': 0, 'currencyCode': 'MXN'},
                        'availability': {'available': False}
                    }
                    processed_products.append(processed_product)
                
                return {
                    'products': processed_products,
                    'total': total_records
                }
            else:
                print(f"Error en búsqueda: {response.status_code} - {response.text}")
                return {'products': [], 'total': 0}
                
        except Exception as e:
            print(f"Excepción en search_products: {str(e)}")
            return {'products': [], 'total': 0}
    
    @staticmethod
    def get_product_detail(sku):
        """Obtener detalle completo de un producto"""
        try:
            headers = ProductUtils.get_api_headers()
            if not headers:
                return None
            
            base_url = current_app.config.get('INGRAM_API_BASE_URL')
            
            # 1. Obtener detalle básico
            detail_endpoint = f"{base_url}/resellers/v6/catalog/details/{sku}"
            detail_response = requests.get(detail_endpoint, headers=headers, timeout=30)
            
            if detail_response.status_code != 200:
                print(f"Error obteniendo detalle de {sku}: {detail_response.status_code}")
                return None
            
            product_detail = detail_response.json()
            
            # 2. Obtener precios y disponibilidad
            price_data = ProductUtils.get_price_and_availability([sku])
            
            # Combinar datos
            combined_product = {
                'ingramPartNumber': product_detail.get('ingramPartNumber'),
                'vendorPartNumber': product_detail.get('vendorPartNumber'),
                'description': product_detail.get('description'),
                'vendorName': product_detail.get('vendorName'),
                'category': product_detail.get('productCategory'),
                'subCategory': product_detail.get('productSubCategory'),
                'upcCode': product_detail.get('upc'),
                'endUserRequired': str(product_detail.get('indicators', {}).get('endUserRequired', False)),
                'hasWarranty': str(product_detail.get('indicators', {}).get('hasWarranty', False)),
                'productImages': ['/static/images/placeholder.png'],
                'pricing': {'customerPrice': 0, 'currencyCode': 'MXN'},
                'availability': {'available': False},
                'attributes': []
            }
            
            # Agregar datos de precio si están disponibles
            if price_data and len(price_data) > 0 and isinstance(price_data[0], dict):
                price_item = price_data[0]
                
                # Precios
                pricing = price_item.get('pricing', {})
                if isinstance(pricing, dict):
                    customer_pricing = pricing.get('customerPrice', {})
                    if isinstance(customer_pricing, dict):
                        combined_product['pricing'] = {
                            'customerPrice': customer_pricing.get('price', 0),
                            'currencyCode': customer_pricing.get('currencyCode', 'MXN')
                        }
                
                # Disponibilidad
                availability = price_item.get('availability', {})
                if isinstance(availability, dict):
                    combined_product['availability'] = {
                        'available': availability.get('available', False),
                        'quantity': availability.get('quantityAvailable', 0)
                    }
                
                # Atributos
                attributes = price_item.get('productAttributes', [])
                if isinstance(attributes, list):
                    combined_product['attributes'] = [
                        {
                            'name': attr.get('attributeName', ''),
                            'value': attr.get('attributeValue', '')
                        }
                        for attr in attributes if isinstance(attr, dict) and attr.get('attributeName')
                    ]
            
            return combined_product
            
        except Exception as e:
            print(f"Excepción en get_product_detail: {str(e)}")
            return None
    
    @staticmethod
    def get_price_and_availability(part_numbers):
        """Obtener precios y disponibilidad para productos - VERSIÓN CORREGIDA"""
        try:
            if not part_numbers:
                return []
            
            # Usa APIClient en lugar de requests directo
            results = []
            for part_number in part_numbers:
                price_data = APIClient.get_product_price_and_availability(part_number)
                if price_data:
                    results.append(price_data)
            
            return results
                
        except Exception as e:
            print(f"Excepción en get_price_and_availability: {str(e)}")
            return []
    
    @staticmethod
    def quick_search(query):
        """Búsqueda rápida para autocompletado"""
        try:
            if not query or len(query) < 2:
                return {'products': []}
            
            # Búsqueda limitada para autocompletado
            result = ProductUtils.search_products(query=query, page_size=5)
            return {
                'products': result.get('products', [])[:5]
            }
        except Exception as e:
            print(f"Error en quick_search: {str(e)}")
            return {'products': []}