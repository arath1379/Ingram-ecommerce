from app import db
from datetime import datetime
from sqlalchemy import or_, and_

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    ingram_part_number = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    vendor_name = db.Column(db.String(200), nullable=False)
    vendor_part_number = db.Column(db.String(100))
    category = db.Column(db.String(200))
    subcategory = db.Column(db.String(200))
    upc = db.Column(db.String(50))
    base_price = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(10), default='MXP')
    image_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime, default=db.func.current_timestamp())
    metadata_json = db.Column(db.Text)
    
    # Relaciones
    favorites = db.relationship('Favorite', backref='product', lazy=True, cascade='all, delete-orphan')
    # quote_items se define aquí con backref
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
    
    __table_args__ = (
        db.Index('idx_description', 'description'),
        db.Index('idx_vendor_name', 'vendor_name'),
        db.Index('idx_category', 'category'),
        db.Index('idx_ingram_part', 'ingram_part_number'),
    )
    @classmethod
    def buscar_avanzado(cls, query, vendor=None, category=None, limit=25, offset=0):
        """
        Búsqueda avanzada con palabras clave, vendor y category
        """
        # Construir consulta base
        base_query = cls.query.filter(cls.is_active == True)
        
        # Búsqueda por palabras clave
        if query:
            # Dividir la query en palabras individuales
            palabras = query.split()
            condiciones = []
            
            for palabra in palabras:
                if len(palabra) > 2:  # Ignorar palabras muy cortas
                    # Búsqueda en múltiples campos
                    cond = or_(
                        cls.description.ilike(f'%{palabra}%'),
                        cls.vendor_name.ilike(f'%{palabra}%'),
                        cls.category.ilike(f'%{palabra}%'),
                        cls.subcategory.ilike(f'%{palabra}%'),
                        cls.ingram_part_number.ilike(f'%{palabra}%'),
                        cls.vendor_part_number.ilike(f'%{palabra}%')
                    )
                    condiciones.append(cond)
            
            if condiciones:
                # Combinar todas las condiciones con AND (todas las palabras deben coincidir)
                base_query = base_query.filter(and_(*condiciones))
        
        # Filtros adicionales
        if vendor:
            base_query = base_query.filter(cls.vendor_name.ilike(f'%{vendor}%'))
        
        if category:
            base_query = base_query.filter(
                or_(
                    cls.category.ilike(f'%{category}%'),
                    cls.subcategory.ilike(f'%{category}%')
                )
            )
        
        # Conteo total y resultados
        total = base_query.count()
        resultados = base_query.order_by(cls.description).limit(limit).offset(offset).all()
        
        return resultados, total
    
    @classmethod
    def buscar_con_ranking(cls, query, limit=25):
        """
        Búsqueda con ranking de relevancia
        """
        from sqlalchemy import func, case
        
        palabras = [p.strip() for p in query.split() if len(p.strip()) > 2]
        
        if not palabras:
            return cls.query.filter(cls.is_active == True).limit(limit).all()
        
        # Crear condiciones de búsqueda
        condiciones = []
        for palabra in palabras:
            cond = or_(
                cls.description.ilike(f'%{palabra}%'),
                cls.vendor_name.ilike(f'%{palabra}%'),
                cls.category.ilike(f'%{palabra}%')
            )
            condiciones.append(cond)
        
        # Calcular puntaje de relevancia
        puntaje = func.coalesce(
            case([
                (cls.description.ilike(f'%{palabra}%'), 3) for palabra in palabras
            ], else_=0),
            0
        ) + func.coalesce(
            case([
                (cls.vendor_name.ilike(f'%{palabra}%'), 2) for palabra in palabras
            ], else_=0),
            0
        ) + func.coalesce(
            case([
                (cls.category.ilike(f'%{palabra}%'), 1) for palabra in palabras
            ], else_=0),
            0
        )
        
        return cls.query.filter(
            cls.is_active == True,
            and_(*condiciones)
        ).add_columns(
            puntaje.label('relevancia')
        ).order_by(
            db.desc('relevancia'),
            cls.description
        ).limit(limit).all()