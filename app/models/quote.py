from app import db
from datetime import datetime

class Quote(db.Model):
    __tablename__ = 'quotes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quote_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Estados ampliados para el flujo completo
    status = db.Column(db.String(20), default='draft')  # draft, sent, approved, rejected, in_progress, completed, invoiced, paid, cancelled
    
    total_amount = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='MXN')
    markup_percentage = db.Column(db.Float, default=10.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Campos de pago y facturación
    payment_method = db.Column(db.String(50), nullable=True)
    payment_reference = db.Column(db.String(100), nullable=True)
    invoice_number = db.Column(db.String(50), nullable=True)
    invoice_date = db.Column(db.DateTime, nullable=True)
    invoice_file = db.Column(db.String(500), nullable=True)
    
    # Nuevos campos para gestión administrativa
    admin_notes = db.Column(db.Text, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by = db.Column(db.String(100), nullable=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    
    # Relación con items
    items = db.relationship('QuoteItem', backref='quote', lazy=True, cascade='all, delete-orphan')
    history = db.relationship('QuoteHistory', backref='quote', lazy=True, cascade='all, delete-orphan')
    
    def calculate_total(self):
        self.total_amount = sum(item.total_price for item in self.items)
        return self.total_amount
    
    def generate_quote_number(self):
        """Genera número de cotización único"""
        if not self.quote_number:
            year = datetime.now().year
            last_quote = Quote.query.order_by(Quote.id.desc()).first()
            if last_quote and last_quote.quote_number:
                try:
                    last_number = int(last_quote.quote_number.split('-')[-1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    new_number = 1
            else:
                new_number = 1
            self.quote_number = f"COT-{year}-{new_number:05d}"
        return self.quote_number
    
    def calculate_totals_with_tax(self):
        """Calcular subtotal, IVA y total"""
        subtotal = sum(item.quantity * (item.unit_price or 0) for item in self.items)
        tax_rate = 0.16  # 16% IVA en México
        tax_amount = round(subtotal * tax_rate, 2)
        total_with_tax = round(subtotal + tax_amount, 2)
        
        return {
            'subtotal': subtotal,
            'tax_rate': tax_rate,
            'tax_amount': tax_amount,
            'total_with_tax': total_with_tax
        }
    
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
            'items': [item.to_dict() for item in self.items],
            'user': self.user.to_dict() if self.user else None
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
            'notes': self.notes,
            'product': self.product.to_dict() if self.product else None
        }


class QuoteHistory(db.Model):
    __tablename__ = 'quote_history'
    
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'description': self.description,
            'user_name': self.user_name,
            'created_at': self.created_at.isoformat()
        }