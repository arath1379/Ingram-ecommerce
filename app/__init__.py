# app/__init__.py
from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy 
from config import Config
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Initialize extensions
login_manager = LoginManager()
mail = Mail()
db = SQLAlchemy()  # Inicializado aquí

def create_app():
    app = Flask(__name__)
    
    # Cargar configuración
    app.config.from_object(Config)

    INGRAM_LANGUAGE = os.getenv("INGRAM_LANGUAGE", "es")
    CACHE_EXPIRY_HOURS = int(os.getenv("CACHE_EXPIRY_HOURS", "2"))
    
    app.config['UNSPLASH_ACCESS_KEY'] = os.environ.get('UNSPLASH_ACCESS_KEY', 'fallback_key_here')
    app.config["INGRAM_LANGUAGE"] = INGRAM_LANGUAGE
    app.config["CACHE_EXPIRY_HOURS"] = CACHE_EXPIRY_HOURS

    # Debug: verificar configuraciones
    print(f"🔧 SQLALCHEMY_DATABASE_URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    print(f"🔧 INGRAM_API_BASE_URL: {app.config.get('INGRAM_API_BASE_URL')}")
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    mail.init_app(app)
    
    # Importar modelos para que SQLAlchemy los detecte
    from app.models.user import User
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
    from app.routes.products import products_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # User loader for Flask-Login
    from app.models.user import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    return app