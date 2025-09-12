from flask import current_app
from datetime import datetime, timedelta

class SearchCache:
    def __init__(self):
        self.cache = {}
    
    def get_expiry_hours(self):
        """Obtener la configuración solo cuando se necesite"""
        try:
            return current_app.config['CACHE_EXPIRY_HOURS']
        except RuntimeError:
            # Fallback si no hay contexto de app
            return 24  # Valor por defecto
    
    def save(self, key, data):
        expiry_hours = self.get_expiry_hours()
        self.cache[key] = {
            'data': data,
            'expiry': datetime.now() + timedelta(hours=expiry_hours)
        }
    
    def get(self, key):
        if key in self.cache:
            if datetime.now() < self.cache[key]['expiry']:
                return self.cache[key]['data']
            else:
                del self.cache[key] 
        return None

class TokenCache:
    def __init__(self):
        self.token = None
        self.expiry = 0
    
    def is_valid(self):
        import time
        return self.token and time.time() < self.expiry
    
    def get_token(self):
        return self.token
    
    def set_token(self, token, expires_in):
        import time
        self.token = token
        self.expiry = time.time() + expires_in
# Instancias globales
search_cache = SearchCache()
token_cache = TokenCache()