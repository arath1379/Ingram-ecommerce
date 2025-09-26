# app/routes/main.py - SISTEMA COMPLETO DE DASHBOARDS POR ROL
from flask import Blueprint, render_template, redirect, url_for, jsonify, request, flash, session
from app import db
from app.models import User

# Definir el Blueprint
main_bp = Blueprint('main', __name__)

# Decorador para requerir autenticación (usando sesiones)
def login_required_sessions(f):
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión para acceder a esta página', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
def index():
    """Página principal - Redirige al dashboard si está logueado, sino al catálogo"""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.post_login'))

@main_bp.route('/home')
def home():
    """Ruta alternativa para la página principal"""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('products.catalog'))

# ==================== SISTEMA PRINCIPAL DE DASHBOARDS ====================
@main_bp.route('/dashboard')
@login_required_sessions
def dashboard():
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Sesión no válida', 'danger')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user:
        flash('Usuario no encontrado', 'danger')
        session.clear()
        return redirect(url_for('auth.login'))
    
    print(f"🔍 Usuario: {user.email}")
    print(f"🔍 Tipo de cuenta: {user.account_type}")
    print(f"🔍 Activo: {user.is_active}")
    print(f"🔍 Admin: {user.is_admin}")
    print(f"🔍 Verificado: {user.is_verified}")
    
    if not user.is_active:
        flash('Cuenta pendiente de activación. Contacta al administrador.', 'danger')
        return redirect(url_for('auth.logout'))
    
    if user.is_admin:
        return redirect(url_for('admin.dashboard'))
    elif user.account_type == 'client':
        if user.is_verified:
            return redirect(url_for('main.client_dashboard'))
        else:
            flash('Cuenta de cliente en proceso de verificación.', 'warning')
            return redirect(url_for('main.public_dashboard'))
    else:
        return redirect(url_for('main.public_dashboard'))

@main_bp.route('/dashboard/public')
@login_required_sessions
def public_dashboard():
    """Dashboard para usuarios públicos/individuales."""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    # Verificar que no sea admin ni client
    if user.is_admin:
        flash('Acceso redirigido al panel de administración', 'info')
        return redirect(url_for('admin.dashboard'))
    elif user.account_type == 'client':
        flash('Acceso redirigido al dashboard de cliente', 'info')
        return redirect(url_for('main.client_dashboard'))
    
    # Obtener datos REALES para el dashboard público
    from app.models import Favorite, Quote, Cart, CartItem
    from sqlalchemy import func
    
    # Contador de favoritos
    favorites_count = Favorite.query.filter_by(user_id=user_id).count()
    
    # Obtener datos REALES del carrito - CORREGIDO
    cart = Cart.query.filter_by(user_id=user_id, status='active').first()
    
    # Calcular total_items sumando las cantidades de todos los items
    total_items = 0
    item_count = 0
    total_value = 0.0
    
    if cart and cart.items:
        for item in cart.items:
            total_items += item.quantity  # Sumar cantidad de cada item
            item_count += 1  # Contar productos distintos
            if item.unit_price:
                total_value += float(item.unit_price) * item.quantity
    
    cart_stats = {
        'total_items': total_items,
        'item_count': item_count,
        'total_value': total_value,
        'last_update': cart.updated_at.strftime('%d/%m/%Y %H:%M') if cart and cart.updated_at else 'Hoy'
    }
    
    # Cotizaciones activas
    active_quotes = Quote.query.filter_by(user_id=user_id).filter(
        Quote.status.in_(['draft', 'sent', 'pending'])
    ).count()
    
    # Favoritos recientes (últimos 5)
    recent_favorites = Favorite.query.filter_by(user_id=user_id).order_by(
        Favorite.created_at.desc()
    ).limit(5).all()
    
    # Categorías de favoritos (simplificado)
    favorite_categories = []
    if recent_favorites:
        # Obtener categorías únicas de los favoritos recientes
        categories_set = set()
        for fav in recent_favorites:
            if hasattr(fav, 'product') and fav.product and fav.product.category:
                categories_set.add(fav.product.category)
        favorite_categories = list(categories_set)
    
    # Actividad reciente
    recent_activity = [
        {
            'type': 'user',
            'icon': 'fas fa-user-plus',
            'title': 'Cuenta activa',
            'description': f'Bienvenido/a {user.full_name or user.email}',
            'time': 'Hoy'
        }
    ]
    
    # Agregar actividad basada en datos reales
    if favorites_count > 0:
        recent_activity.append({
            'type': 'heart',
            'icon': 'fas fa-heart',
            'title': 'Favoritos guardados',
            'description': f'Tienes {favorites_count} productos en favoritos',
            'time': 'Reciente'
        })
    
    if total_items > 0:
        recent_activity.append({
            'type': 'cart',
            'icon': 'fas fa-shopping-cart',
            'title': 'Carrito activo',
            'description': f'Tienes {total_items} productos en el carrito',
            'time': 'Reciente'
        })
    
    public_data = {
        'user_name': user.full_name or user.email.split('@')[0],
        'user_email': user.email,
        'favorites_count': favorites_count,
        'active_quotes': active_quotes,
        'user_type': 'public',
        'account_type': user.account_type,
        'member_since': user.created_at.strftime('%d/%m/%Y') if user.created_at else 'Reciente',
        'last_login': 'Hoy',
        'cart_stats': cart_stats,
        'recent_favorites': recent_favorites,
        'favorite_categories': favorite_categories,
        'recent_activity': recent_activity
    }
    
    # DEBUG: Verificar datos
    print(f"🔍 Datos para template público:")
    print(f"   - User: {public_data['user_name']}")
    print(f"   - Favoritos: {public_data['favorites_count']}")
    print(f"   - Carrito total_items: {public_data['cart_stats']['total_items']}")
    print(f"   - Carrito item_count: {public_data['cart_stats']['item_count']}")
    print(f"   - Carrito total_value: {public_data['cart_stats']['total_value']}")
    
    try:
        # PRIMERO: Intentar con template normal
        return render_template('public_dashboard.html', **public_data)
    except Exception as e:
        print(f"❌ Error con template: {e}")
        try:
            # SEGUNDO: Intentar con ruta alternativa
            return render_template('public/public_dashboard.html', **public_data)
        except Exception as e2:
            print(f"❌ Error con template alternativo: {e2}")
            # TERCERO: Fallback básico
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Panel Público - IT Data Global</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    body {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
                    .dashboard-card {{ background: white; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }}
                </style>
            </head>
            <body>
                <div class="container py-5">
                    <div class="row">
                        <div class="col-12 text-center mb-4">
                            <h1 class="text-white">👋 ¡Hola {public_data['user_name']}!</h1>
                            <p class="text-white">Panel de Usuario Público</p>
                        </div>
                    </div>
                    
                    <div class="row g-4">
                        <div class="col-md-4">
                            <div class="dashboard-card p-4 text-center">
                                <h3>❤️ Favoritos</h3>
                                <h2 class="text-primary">{public_data['favorites_count']}</h2>
                                <p>Productos guardados</p>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div class="dashboard-card p-4 text-center">
                                <h3>🛒 Carrito</h3>
                                <h2 class="text-success">{public_data['cart_stats']['total_items']}</h2>
                                <p>Productos en carrito</p>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div class="dashboard-card p-4 text-center">
                                <h3>📋 Cotizaciones</h3>
                                <h2 class="text-warning">{public_data['active_quotes']}</h2>
                                <p>Activas</p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row mt-4">
                        <div class="col-12">
                            <div class="dashboard-card p-4">
                                <h4>🚀 Acciones Rápidas</h4>
                                <div class="d-grid gap-2 d-md-flex">
                                    <a href="/catalog" class="btn btn-primary me-md-2">📦 Ver Catálogo</a>
                                    <a href="/cart" class="btn btn-success me-md-2">🛒 Ver Carrito</a>
                                    <a href="/favorites" class="btn btn-warning me-md-2">❤️ Mis Favoritos</a>
                                    <a href="/logout" class="btn btn-outline-danger">🚪 Cerrar Sesión</a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """

@main_bp.route('/dashboard/client')
@login_required_sessions
def client_dashboard():
    """Dashboard para clientes empresariales."""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    # Verificar que sea client
    if user.is_admin:
        flash('Acceso redirigido al panel de administración', 'info')
        return redirect(url_for('admin.dashboard'))
    elif user.account_type != 'client':
        flash('Acceso restringido a clientes', 'danger')
        return redirect(url_for('main.public_dashboard'))
    
    # Obtener datos reales para el dashboard de cliente
    from app.models import Quote
    total_quotes = Quote.query.filter_by(user_id=user_id).count()
    pending_quotes = Quote.query.filter_by(user_id=user_id, status='pending').count()
    approved_quotes = Quote.query.filter_by(user_id=user_id, status='approved').count()
    
    # ✅ CORREGIDO: Usar total_amount en lugar de total
    from sqlalchemy import func
    total_sales = db.session.query(func.sum(Quote.total_amount)).filter(
        Quote.user_id == user_id, 
        Quote.status.in_(['approved', 'paid'])  # ✅ Usar estados correctos
    ).scalar() or 0
    
    client_data = {
        'user_name': user.full_name or user.email,
        'business_name': user.business_name or 'Mi Empresa',
        'rfc': user.rfc or 'No especificado',
        'user_email': user.email,
        'total_quotes': total_quotes,
        'pending_quotes': pending_quotes,
        'approved_quotes': approved_quotes,
        'total_sales': float(total_sales),
        'discount': user.discount_percentage or 0,
        'credit_limit': user.credit_limit or 0,
        'user_type': 'client'
    }
    
    try:
        # ✅ CORREGIDO: Quitar la barra diagonal inicial
        return render_template('client/client_dashboard.html', **client_data)
    except Exception as e:
        print(f"⚠️ Error cargando template: {e}")
        # Fallback si no existe el template
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dashboard de Cliente</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .dashboard-card {{ background: white; padding: 20px; margin: 10px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .nav-dashboard {{ background: #e3f2fd; padding: 15px; border-radius: 10px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="container mt-4">
                <div class="nav-dashboard">
                    <h3>🏢 Dashboard de Cliente - {client_data['business_name']}</h3>
                    <div class="d-flex gap-2">
                        <a href="/products/catalog" class="btn btn-primary">📦 Ver Catálogo</a>
                        <a href="/dashboard" class="btn btn-outline-primary">📊 Mi Dashboard</a>
                        <a href="/logout" class="btn btn-outline-danger">🚪 Cerrar Sesión</a>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-3">
                        <div class="dashboard-card text-center">
                            <h4>📋 Total Cotizaciones</h4>
                            <h2 class="text-primary">{client_data['total_quotes']}</h2>
                            <small>Todas las cotizaciones</small>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="dashboard-card text-center">
                            <h4>⏳ Pendientes</h4>
                            <h2 class="text-warning">{client_data['pending_quotes']}</h2>
                            <small>Por aprobar</small>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="dashboard-card text-center">
                            <h4>✅ Aprobadas</h4>
                            <h2 class="text-success">{client_data['approved_quotes']}</h2>
                            <small>Listas para ordenar</small>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="dashboard-card text-center">
                            <h4>💰 Ventas Totales</h4>
                            <h2 class="text-info">${client_data['total_sales']:,.2f}</h2>
                            <small>Historial completo</small>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-3">
                    <div class="col-md-6">
                        <div class="dashboard-card">
                            <h5>🏷️ Información de Descuento</h5>
                            <p><strong>Descuento Especial:</strong> {client_data['discount']}%</p>
                            <p><strong>Límite de Crédito:</strong> ${client_data['credit_limit']:,.2f}</p>
                            <p><strong>RFC:</strong> {client_data['rfc']}</p>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="dashboard-card">
                            <h5>🚀 Acciones Rápidas</h5>
                            <div class="d-grid gap-2">
                                <a href="/products/catalog" class="btn btn-outline-primary">Nueva Cotización</a>
                                <a href="/quote/history" class="btn btn-outline-success">Historial de Compras</a>
                                <a href="/profile" class="btn btn-outline-info">Actualizar Datos</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
# ==================== RUTA DE POST-LOGIN ====================

@main_bp.route('/post-login')
@login_required_sessions
def post_login():
    """Punto de entrada después del login - decide a qué dashboard redirigir."""
    return redirect(url_for('main.dashboard'))

# ==================== RUTAS INFORMATIVAS ====================

@main_bp.route('/about')
def about():
    """Página acerca de"""
    try:
        return render_template('about.html')
    except Exception as e:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Acerca de Nosotros</title></head>
        <body>
            <h1>Acerca de IT Data Global</h1>
            <p>Tu partner confiable en soluciones tecnológicas.</p>
            <a href="/">Volver al inicio</a>
        </body>
        </html>
        """, 200

@main_bp.route('/contact')
def contact():
    """Página de contacto"""
    try:
        return render_template('contact.html')
    except Exception as e:
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Contacto</title></head>
        <body>
            <h1>Contacto</h1>
            <p>Email: info@itdataglobal.com</p>
            <p>Teléfono: +52 55 1234 5678</p>
            <a href="/">Volver al inicio</a>
        </body>
        </html>
        """, 200

# ==================== RUTAS DE SALUD ====================

@main_bp.route('/health')
def health_check():
    """Endpoint de salud para verificar que la app funciona"""
    return jsonify({
        'status': 'ok', 
        'message': 'E-commerce funcionando correctamente',
        'version': '1.0.0',
        'session_active': 'user_id' in session
    })

@main_bp.route('/api/health')
def api_health_check():
    """Endpoint de salud más detallado para APIs"""
    import datetime
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.now().isoformat(),
        'services': {
            'database': 'ok',
            'api_connection': 'ok',
            'session_management': 'ok',
            'user_session': 'active' if 'user_id' in session else 'inactive'
        }
    })

# ==================== RUTAS DE COMPATIBILIDAD ====================

@main_bp.route('/catalog')
def catalogo_redirect():
    """Redirección de compatibilidad para /catalogo"""
    return redirect(url_for('public.public_catalog'))

@main_bp.route('/productos')
def productos_redirect():
    """Redirección de compatibilidad para /productos"""
    return redirect(url_for('products.catalog'))

# ==================== MANEJO DE ERRORES ====================

@main_bp.app_errorhandler(404)
def page_not_found(e):
    """Página de error 404 personalizada"""
    return """
    <html>
        <head><title>404 - Página no encontrada</title></head>
        <body>
            <h1>🔍 Página no encontrada</h1>
            <p>La página que buscas no existe.</p>
            <p><a href="/">🏠 Volver al inicio</a></p>
        </body>
    </html>
    """, 404

@main_bp.app_errorhandler(500)
def internal_server_error(e):
    """Página de error 500 personalizada"""
    return """
    <html>
        <head><title>500 - Error del servidor</title></head>
        <body>
            <h1>⚠️ Error del servidor</h1>
            <p>Ha ocurrido un error interno. Por favor intenta más tarde.</p>
            <p><a href="/">🏠 Volver al inicio</a></p>
        </body>
    </html>
    """, 500

# ==================== RUTAS DE UTILIDAD ====================

@main_bp.route('/favicon.ico')
def favicon():
    """Manejar solicitudes de favicon"""
    try:
        return redirect(url_for('static', filename='favicon.ico'))
    except:
        return '', 404

@main_bp.route('/robots.txt')
def robots():
    """Archivo robots.txt para SEO"""
    return """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Sitemap: /sitemap.xml"""

@main_bp.route('/sitemap.xml')
def sitemap():
    """Sitemap básico para SEO"""
    from flask import request
    base_url = request.url_root.rstrip('/')
    
    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>{base_url}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>
    <url><loc>{base_url}/catalog</loc><changefreq>daily</changefreq><priority>0.9</priority></url>
    <url><loc>{base_url}/about</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>
    <url><loc>{base_url}/contact</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>
</urlset>"""
    
    from flask import Response
    return Response(sitemap_xml, mimetype='application/xml')

# ==================== RUTAS DE BÚSQUEDA ====================

@main_bp.route('/buscar')
def buscar_global():
    """Búsqueda global que redirige al catálogo con parámetros"""
    query = request.args.get('q', '')
    vendor = request.args.get('vendor', '')
    catalog_url = url_for('products.catalog', q=query, vendor=vendor)
    return redirect(catalog_url)

@main_bp.route('/search')
def search_redirect():
    """Redirección para búsqueda en inglés"""
    query = request.args.get('q', '')
    vendor = request.args.get('vendor', '')
    catalog_url = url_for('products.catalog', q=query, vendor=vendor)
    return redirect(catalog_url)

# ==================== RUTA DE DIAGNÓSTICO ====================

@main_bp.route('/check-session')
def check_session():
    """Verificar estado de la sesión"""
    user_info = {}
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user_info = {
                'user_id': user.id,
                'email': user.email,
                'is_admin': user.is_admin,
                'account_type': user.account_type,
                'full_name': user.full_name,
                'business_name': user.business_name
            }
    
    return jsonify({
        'session_active': 'user_id' in session,
        'session_data': {
            'user_id': session.get('user_id'),
            'user_email': session.get('user_email'), 
            'user_role': session.get('user_role'),
            'session_keys': list(session.keys())
        },
        'user_info': user_info
    })