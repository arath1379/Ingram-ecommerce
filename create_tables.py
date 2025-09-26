# create_tables.py
from app import create_app, db
from app.models.user import User
from app.models.product import Product
from app.models.favorite import Favorite
from app.models.cart import Cart, CartItem

app = create_app()

with app.app_context():
    db.create_all()
    print("✅ Todas las tablas han sido creadas")