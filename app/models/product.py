from app import db
from datetime import datetime

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    ingram_part_number = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    vendor_part_number = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    subcategory = db.Column(db.String(100), nullable=True)
    vendor_name = db.Column(db.String(100), nullable=True)
    upc = db.Column(db.String(50), nullable=True)
    base_price = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='MXN')
    image_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    metadata_json = db.Column(db.Text, nullable=True)  # Datos adicionales en JSON
    
    # Relaciones
    favorites = db.relationship('Favorite', backref='product', lazy=True, cascade='all, delete-orphan')
    quote_items = db.relationship('QuoteItem', backref='product', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'ingram_part_number': self.ingram_part_number,
            'description': self.description,
            'vendor_name': self.vendor_name,
            'category': self.category,
            'base_price': self.base_price,
            'currency': self.currency,
            'image_url': self.image_url,
            'upc': self.upc
        }