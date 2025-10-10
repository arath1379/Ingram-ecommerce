# create_tables.py
from app import db, create_app

app = create_app()

with app.app_context():
    try:
        print("🔧 Creando tablas en la base de datos...")
        
        # Crear todas las tablas
        db.create_all()
        print("✅ Tablas creadas exitosamente")
        
        # Verificar que las tablas existen (compatible con SQLAlchemy 2.x)
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print("📊 Tablas en la base de datos:")
        for table in tables:
            print(f"   - {table}")
            
        # Verificar tablas específicas de compras
        required_tables = ['purchases', 'purchase_items', 'purchase_history']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            print(f"❌ Tablas faltantes: {missing_tables}")
        else:
            print("✅ Todas las tablas de compras creadas correctamente")
            
    except Exception as e:
        print(f"❌ Error creando tablas: {e}")
        import traceback
        traceback.print_exc()