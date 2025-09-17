from app import db
from datetime import datetime

class Quote(db.Model):
    __tablename__ = 'quotes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quote_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(20), default='draft')  # draft, sent, approved, rejected
    total_amount = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='MXN')
    markup_percentage = db.Column(db.Float, default=10.0)  # 10% por defecto
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Nuevos campos de pago y facturación
    status = db.Column(db.String(20), default='draft')  # draft, sent, approved, paid, cancelled
    payment_method = db.Column(db.String(50), nullable=True)  # tarjeta, transferencia, etc.
    payment_reference = db.Column(db.String(100), nullable=True)
    invoice_number = db.Column(db.String(50), nullable=True)
    invoice_date = db.Column(db.DateTime, nullable=True)
    invoice_file = db.Column(db.String(500), nullable=True)  # Ruta al PDF de factura
    
    # Relación con items
    items = db.relationship('QuoteItem', backref='quote', lazy=True, cascade='all, delete-orphan')
    
    def calculate_total(self):
        self.total_amount = sum(item.total_price for item in self.items)
        return self.total_amount
    
    def to_dict(self):
        return {
            'id': self.id,
            'quote_number': self.quote_number,
            'status': self.status,
            'total_amount': self.total_amount,
            'currency': self.currency,
            'markup_percentage': self.markup_percentage,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'items_count': len(self.items),
            'items': [item.to_dict() for item in self.items]
        }

class QuoteItem(db.Model):
    __tablename__ = 'quote_items'
    
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def calculate_total(self):
        self.total_price = self.unit_price * self.quantity
        return self.total_price
    
    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'total_price': self.total_price,
            'product': self.product.to_dict() if self.product else None
        }