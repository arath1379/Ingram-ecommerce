# app/utils/cache_manager.py - VERSIÓN CORRECTA
import time

class TokenCache:
    def __init__(self):
        self.token = None
        self.expires_at = 0
    
    def set_token(self, token, expires_in):
        """Set the token and expiration time."""
        self.token = token
        self.expires_at = time.time() + expires_in - 60  # 60 seconds buffer
    
    def get_token(self):
        """Get the current token."""
        return self.token
    
    def is_valid(self):
        """Check if the token is still valid."""
        return self.token and time.time() < self.expires_at
    
    def clear(self):
        """Clear the token cache."""
        self.token = None
        self.expires_at = 0

# Create a global instance
token_cache = TokenCache()