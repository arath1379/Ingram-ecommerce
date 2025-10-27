# app/__init__.py - VERSIÓN CORREGIDA
from flask import Flask, request, session
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy 
from config import Config
import os
from dotenv import load_dotenv
from datetime import timedelta
from flask_login import LoginManager, current_user 
from flask_migrate import Migrate

# Cargar variables de entorno
load_dotenv()

# Initialize extensions
login_manager = LoginManager()
mail = Mail()
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    
    # Cargar configuración
    app.config.from_object(Config)
    
    migrate = Migrate(app, db)

    # CONFIGURACIÓN CRÍTICA DE SESIÓN Y SEGURIDAD
    app.config.update(
        # Sesiones y cookies seguras
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=False,  # True en producción con HTTPS
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_DURATION=timedelta(days=1),
        PERMANENT_SESSION_LIFETIME=timedelta(days=1),
        
        # Protección CSRF
        WTF_CSRF_ENABLED=True,
        
        # Configuración de reverse proxy si estás detrás de uno
        PREFERRED_URL_SCHEME='http'
    )

    INGRAM_LANGUAGE = os.getenv("INGRAM_LANGUAGE", "es")
    CACHE_EXPIRY_HOURS = int(os.getenv("CACHE_EXPIRY_HOURS", "2"))
    
    app.config['UNSPLASH_ACCESS_KEY'] = os.environ.get('UNSPLASH_ACCESS_KEY', 'fallback_key_here')
    app.config["INGRAM_LANGUAGE"] = INGRAM_LANGUAGE
    app.config["CACHE_EXPIRY_HOURS"] = CACHE_EXPIRY_HOURS

    # Initialize extensions
    db.init_app(app)
    
    # CONFIGURAR LOGIN_MANAGER ANTES DE TODO
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'danger'
    login_manager.refresh_view = 'auth.login'
    login_manager.needs_refresh_message = 'Por favor vuelve a iniciar sesión.'
    login_manager.needs_refresh_message_category = 'warning'
    
    mail.init_app(app)
    
    # USER LOADER DEBE ESTAR ANTES DE LOS BLUEPRINTS
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = User.query.get(int(user_id))
            return user
        except Exception:
            return None

    # Importar modelos para que SQLAlchemy los detecte
    from app.models.product import Product
    from app.models.favorite import Favorite
    from app.models.quote import Quote, QuoteItem
    
    # Agregar funciones al contexto de Jinja
    @app.context_processor
    def utility_processor():
        def get_image_url_enhanced(product):
            """Función auxiliar para obtener URL de imagen mejorada."""
            if isinstance(product, dict):
                images = product.get('productImages', [])
                if images and isinstance(images, list) and len(images) > 0:
                    return images[0]
            return '/static/images/placeholder.png'
        
        def get_availability_text(product):
            """Función auxiliar para texto de disponibilidad."""
            if isinstance(product, dict):
                availability = product.get('availability', {})
                if isinstance(availability, dict) and availability.get('available'):
                    return "Disponible"
            return "No disponible"
        
        return {
            'get_image_url_enhanced': get_image_url_enhanced,
            'get_availability_text': get_availability_text
        }
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.public_products import public_bp
    from app.routes.client_routes import client_routes_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(client_routes_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app