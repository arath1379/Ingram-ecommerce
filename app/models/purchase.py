from app import db
from datetime import datetime
import json

class Purchase(db.Model):
    __tablename__ = 'purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Relación con usuario
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Información del cliente
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
    payment_method = db.Column(db.String(50), nullable=False)
    payment_reference = db.Column(db.String(100))
    payment_status = db.Column(db.String(20), default='pending')
    
    # Montos
    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    shipping_cost = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    
    # Estado del pedido
    status = db.Column(db.String(20), default='pending')
    
    # Información de envío
    tracking_number = db.Column(db.String(100))
    shipping_carrier = db.Column(db.String(100))
    estimated_delivery = db.Column(db.DateTime)
    
    # Notas
    customer_notes = db.Column(db.Text)
    admin_notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('purchases', lazy=True))
    items = db.relationship('PurchaseItem', backref='purchase', lazy=True, cascade='all, delete-orphan')
    history = db.relationship('PurchaseHistory', backref='purchase', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Purchase {self.order_number} - {self.status}>'
    
    def calculate_totals(self):
        """Calcular totales automáticamente basado en los items"""
        self.subtotal = sum(item.total_price for item in self.items)
        self.tax_amount = self.subtotal * 0.16
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost - self.discount_amount
        return self.total_amount
    
    def add_history(self, action, description, user_id=None, user_name=None):
        """Agregar entrada al historial"""
        history = PurchaseHistory(
            purchase_id=self.id,
            action=action,
            description=description,
            user_id=user_id,
            user_name=user_name
        )
        db.session.add(history)
        return history
    
    def update_status(self, new_status, user_id=None, user_name=None, notes=None):
        """Actualizar estado y agregar al historial"""
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.utcnow()
        
        if new_status == 'paid' and not self.paid_at:
            self.paid_at = datetime.utcnow()
        elif new_status == 'shipped' and not self.shipped_at:
            self.shipped_at = datetime.utcnow()
        elif new_status == 'delivered' and not self.delivered_at:
            self.delivered_at = datetime.utcnow()
        elif new_status == 'cancelled' and not self.cancelled_at:
            self.cancelled_at = datetime.utcnow()
        
        action = f"Estado actualizado: {old_status} → {new_status}"
        description = f"Cambio de estado. Notas: {notes}" if notes else f"Cambio de estado de {old_status} a {new_status}"
        
        self.add_history(action, description, user_id, user_name)
        
        if notes:
            self.admin_notes = notes
    
    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'user_id': self.user_id,
            'customer_email': self.customer_email,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'shipping_address': self.shipping_address,
            'shipping_city': self.shipping_city,
            'shipping_state': self.shipping_state,
            'shipping_zipcode': self.shipping_zipcode,
            'shipping_country': self.shipping_country,
            'payment_method': self.payment_method,
            'payment_reference': self.payment_reference,
            'payment_status': self.payment_status,
            'subtotal': self.subtotal,
            'tax_amount': self.tax_amount,
            'shipping_cost': self.shipping_cost,
            'discount_amount': self.discount_amount,
            'total_amount': self.total_amount,
            'status': self.status,
            'tracking_number': self.tracking_number,
            'shipping_carrier': self.shipping_carrier,
            'customer_notes': self.customer_notes,
            'admin_notes': self.admin_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'shipped_at': self.shipped_at.isoformat() if self.shipped_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'items_count': len(self.items),
            'items': [item.to_dict() for item in self.items]
        }
    
    def get_status_badge_class(self):
        status_classes = {
            'pending': 'bg-warning',
            'confirmed': 'bg-info',
            'paid': 'bg-success',
            'shipped': 'bg-primary',
            'delivered': 'bg-success',
            'cancelled': 'bg-danger',
            'refunded': 'bg-secondary'
        }
        return status_classes.get(self.status, 'bg-secondary')
    
    @classmethod
    def generate_order_number(cls):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f'ORD-{timestamp}'

class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    
    # Relación directa con Product
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    
    # Información del producto
    product_sku = db.Column(db.String(100), nullable=False)
    product_name = db.Column(db.String(300), nullable=False)
    product_description = db.Column(db.Text)
    product_vendor = db.Column(db.String(100))
    product_category = db.Column(db.String(100))
    
    # Precios y cantidades
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    
    # Información adicional
    product_image = db.Column(db.String(500))
    product_url = db.Column(db.String(500))
    
    # Metadata del producto
    product_data = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con Product
    product = db.relationship('Product', backref=db.backref('purchase_items', lazy=True))
    
    def __repr__(self):
        return f'<PurchaseItem {self.product_sku} x {self.quantity}>'
    
    def get_product_data(self):
        if self.product_data:
            try:
                return json.loads(self.product_data)
            except:
                return {}
        return {}
    
    def set_product_data(self, data):
        if isinstance(data, dict):
            self.product_data = json.dumps(data)
        else:
            self.product_data = data
    
    def calculate_total(self):
        self.total_price = self.quantity * self.unit_price
        return self.total_price
    
    def to_dict(self):
        product_data = self.get_product_data()
        
        return {
            'id': self.id,
            'purchase_id': self.purchase_id,
            'product_id': self.product_id,
            'product_sku': self.product_sku,
            'product_name': self.product_name,
            'product_description': self.product_description,
            'product_vendor': self.product_vendor,
            'product_category': self.product_category,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'total_price': self.total_price,
            'product_image': self.product_image,
            'product_url': self.product_url,
            'product_data': product_data,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create_from_product(cls, product, quantity=1, purchase_id=None):
        from app.models.product import Product
        
        if not isinstance(product, Product):
            raise ValueError("Se requiere un objeto Product válido")
        
        unit_price = product.base_price * 1.10
        total_price = unit_price * quantity
        
        item = cls(
            purchase_id=purchase_id,
            product_id=product.id,
            product_sku=product.ingram_part_number,
            product_name=product.description,
            product_description=product.description,
            product_vendor=product.vendor_name,
            product_category=product.category,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
            product_image=product.get_image_url(),
            product_url=f"/product/{product.ingram_part_number}"
        )
        
        metadata = {
            'ingram_part_number': product.ingram_part_number,
            'vendor_name': product.vendor_name,
            'category': product.category,
            'upc': product.upc,
            'base_price': product.base_price,
            'metadata': product.metadata_json
        }
        item.set_product_data(metadata)
        
        return item

class PurchaseHistory(db.Model):
    __tablename__ = 'purchase_history'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    
    # Información de la acción
    action = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Usuario que realizó la acción
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_name = db.Column(db.String(200))
    
    # Datos adicionales
    old_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20))
    
    # ✅ CORREGIDO: Cambiado de 'metadata' a 'history_data'
    history_data = db.Column(db.Text)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('purchase_history', lazy=True))
    
    def __repr__(self):
        return f'<PurchaseHistory {self.action} - {self.created_at}>'
    
    def get_history_data(self):
        if self.history_data:
            try:
                return json.loads(self.history_data)
            except:
                return {}
        return {}
    
    def set_history_data(self, data):
        if isinstance(data, dict):
            self.history_data = json.dumps(data)
        else:
            self.history_data = data
    
    def to_dict(self):
        return {
            'id': self.id,
            'purchase_id': self.purchase_id,
            'action': self.action,
            'description': self.description,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'history_data': self.get_history_data(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'formatted_date': self.created_at.strftime('%d/%m/%Y %H:%M') if self.created_at else None
        }

