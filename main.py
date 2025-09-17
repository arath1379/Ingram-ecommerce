from app import create_app, db  # ← IMPORTAR db DESDE app
import secrets

# Crear la aplicación primero
app = create_app()

# Configurar secret key si no está configurada
if not app.config.get('SECRET_KEY') or app.config['SECRET_KEY'] == 'dev-key-change-in-production':
    app.config['SECRET_KEY'] = secrets.token_hex(16)

# Comando CLI para inicializar la base de datos
@app.cli.command("init-db")
def init_db():
    """Initialize the database"""
    with app.app_context():
        db.create_all()
        print("✅ Database initialized successfully!")

if __name__ == "__main__":
    print("🚀 Iniciando servidor de E-commerce Ingram...")
    print(f"📊 Modo debug: {app.config.get('DEBUG', False)}")
    print(f"🔑 Secret key: {app.config.get('SECRET_KEY', 'No configurada')[:15]}...")
    print(f"🌐 Servidor ejecutándose en: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)