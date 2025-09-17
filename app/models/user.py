from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    account_type = db.Column(db.String(20), default='public')  # 'public', 'client', 'admin'
    
    # Campos para validación
    rfc = db.Column(db.String(13), nullable=True)
    business_name = db.Column(db.String(200), nullable=True)
    full_name = db.Column(db.String(150), nullable=True)
    curp = db.Column(db.String(18), nullable=True)
    document_path = db.Column(db.String(500), nullable=True)

    # Nuevos campos comerciales
    credit_limit = db.Column(db.Float, default=0.0)
    payment_terms = db.Column(db.String(50), default='CONTADO')  # CONTADO, 30 DÍAS, etc.
    tax_id = db.Column(db.String(20), nullable=True)
    commercial_reference = db.Column(db.Text, nullable=True)
    discount_percentage = db.Column(db.Float, default=0.0)  # Descuento especial
    
    # Relaciones
    favorites = db.relationship('Favorite', backref='user', lazy=True, cascade='all, delete-orphan')
    quotes = db.relationship('Quote', backref='user', lazy=True, cascade='all, delete-orphan')

    # Método para verificar roles
    def has_role(self, role_name):
        if role_name == 'admin':
            return self.is_admin
        elif role_name == 'client':
            return self.account_type == 'client' and self.is_active
        elif role_name == 'public':
            return self.account_type == 'public'
        return False
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'account_type': self.account_type,
            'full_name': self.full_name,
            'business_name': self.business_name,
            'created_at': self.created_at.isoformat()
        }
