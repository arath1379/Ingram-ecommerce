import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///ecommerce.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    
    # Uploads
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # Configuraciones de Ingram Micro API
    INGRAM_API_BASE_URL = os.getenv('INGRAM_API_BASE_URL')
    INGRAM_CLIENT_ID = os.getenv('INGRAM_CLIENT_ID') 
    INGRAM_CLIENT_SECRET = os.getenv('INGRAM_CLIENT_SECRET')
    INGRAM_CUSTOMER_NUMBER = os.getenv('INGRAM_CUSTOMER_NUMBER')
    INGRAM_COUNTRY_CODE = os.getenv('INGRAM_COUNTRY_CODE', 'MX')
    INGRAM_SENDER_ID = os.getenv('INGRAM_SENDER_ID')
    INGRAM_CORRELATION_ID = os.getenv('INGRAM_CORRELATION_ID')
    
    # Mantener compatibilidad con configuración anterior
    INGRAM_API_KEY = os.getenv('INGRAM_API_KEY') or os.getenv('INGRAM_CLIENT_ID')
    INGRAM_API_SECRET = os.getenv('INGRAM_API_SECRET') or os.getenv('INGRAM_CLIENT_SECRET')
    
    # Stripe Configuration
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
    
    # 🔥 NUEVAS CONFIGURACIONES PARA IMÁGENES 🔥
    
    # SerpAPI Configuration - Para búsqueda de imágenes con Vendor Part Number
    SERPAPI_KEY = os.getenv('SERPAPI_API_KEY') or os.getenv('SERPAPI_KEY')
    
    # Unsplash API Configuration - Como respaldo
    UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY')
    
    # Proxy/VPN Configuration (opcional)
    PROXY_CONFIG = os.getenv('PROXY_CONFIG')
    
    # Configuración de cache para imágenes
    IMAGE_CACHE_TIMEOUT = int(os.getenv('IMAGE_CACHE_TIMEOUT', 3600))  # 1 hora por defecto