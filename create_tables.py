# create_tables.py
from app import create_app, db

def create_database_tables():
    """Crear todas las tablas de la base de datos"""
    app = create_app()
    
    with app.app_context():
        try:
            db.create_all()
            print("✅ Tablas creadas exitosamente:")
            print("   - users")
            print("   - products")
            print("   - quotes")
            print("   - quote_items")
            print("   - favorites")
        except Exception as e:
            print(f"❌ Error al crear tablas: {e}")

if __name__ == "__main__":
    create_database_tables()