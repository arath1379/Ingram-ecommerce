# create_admin_correct.py
import sys
import os
sys.path.append('.')

from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash
from datetime import datetime

def create_admin():
    app = create_app()
    
    with app.app_context():
        try:
            print("🔍 Iniciando creación de administrador...")
            
            # Verificar si ya existe un admin
            existing_admin = User.query.filter_by(email='admin@itdataglobal.com').first()
            if existing_admin:
                print("✅ El usuario admin ya existe")
                print(f"📧 Email: {existing_admin.email}")
                return
            
            # Crear nuevo usuario admin con la estructura correcta
            admin = User(
                email='administracion@itdata.com.mx',
                password_hash=generate_password_hash('ItdataGlobal25'),
                full_name='Administrador Principal',
                business_name='IT DATA GLOBAL',
                is_admin=True,
                is_active=True,  # IMPORTANTE: activar la cuenta
                account_type='admin',
                created_at=datetime.utcnow()
            )
            
            db.session.add(admin)
            db.session.commit()
            
            print("✅ Usuario administrador creado exitosamente!")
            print("📧 Email: administracion@itdata.com.mx")
            print("🔑 Contraseña: ItdataGlobal25")
            print("🏢 Empresa: IT DATA GLOBAL")
            print("👤 Nombre: Administrador Principal")
            print("⚠️ Cambia la contraseña después del primer login!")
            
            # Verificar que se creó correctamente
            verify_admin = User.query.filter_by(email='administracion@itdata.com.mx').first()
            if verify_admin:
                print(f"✅ Verificación: Admin encontrado en BD - ID: {verify_admin.id}")
            else:
                print("❌ Error: No se pudo verificar la creación")
            
        except Exception as e:
            print(f"❌ Error al crear administrador: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    create_admin()