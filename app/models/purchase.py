from app import db
from datetime import datetime
import json

class Purchase(db.Model):
    __tablename__ = 'purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # ✅ CORREGIDO: Agregar user_id como ForeignKey
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    customer_email = db.Column(db.String(120), nullable=False)
    customer_name = db.Column(db.String(200), nullable=False)
    customer_phone = db.Column(db.String(20))
    
    # Información de envío
    shipping_address = db.Column(db.Text)
    shipping_city = db.Column(db.String(100))
    shipping_state = db.Column(db.String(100))
    shipping_zipcode = db.Column(db.String(20))
    shipping_country = db.Column(db.String(100))
    
    # Información de pago
    payment_method = db.Column(db.String(50), nullable=False)  # 'card', 'transfer', etc.
    payment_reference = db.Column(db.String(100))  # Referencia de pago
    payment_status = db.Column(db.String(20), default='pending')  # 'pending', 'completed', 'failed'
    
    # Montos
    subtotal = db.Column(db.Float, nullable=False)
    tax_amount = db.Column(db.Float, default=0.0)
    shipping_cost = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    
    # Estado del pedido
    status = db.Column(db.String(20), default='pending')  # 'pending', 'paid', 'shipped', 'delivered', 'cancelled', 'refunded'
    
    # Información de envío
    tracking_number = db.Column(db.String(100))
    shipping_carrier = db.Column(db.String(100))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    
    # Relaciones
    items = db.relationship('PurchaseItem', backref='purchase', lazy=True, cascade='all, delete-orphan')
    history = db.relationship('PurchaseHistory', backref='purchase', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'customer_email': self.customer_email,
            'customer_name': self.customer_name,
            'status': self.status,
            'total_amount': self.total_amount,
            'created_at': self.created_at.isoformat(),
            'payment_method': self.payment_method
        }

class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    
    # Información del producto
    product_sku = db.Column(db.String(100), nullable=False)
    product_name = db.Column(db.String(300), nullable=False)
    product_description = db.Column(db.Text)
    
    # Precios y cantidades
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    
    # Metadata del producto
    product_data = db.Column(db.Text)  # JSON con datos adicionales del producto
    
    def get_product_data(self):
        if self.product_data:
            return json.loads(self.product_data)
        return {}
    
    def set_product_data(self, data):
        self.product_data = json.dumps(data)

class PurchaseHistory(db.Model):
    __tablename__ = 'purchase_history'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    
    action = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # ✅ CORREGIDO: Hacer user_id nullable=True para notas del sistema
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_name = db.Column(db.String(200))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'description': self.description,
            'user_name': self.user_name,
            'created_at': self.created_at.isoformat()
        }