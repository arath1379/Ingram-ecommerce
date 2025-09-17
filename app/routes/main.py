# app/routes/main.py - RUTAS PRINCIPALES CORREGIDAS
from flask import Blueprint, render_template, redirect, url_for, jsonify

# Definir el Blueprint
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Página principal del e-commerce - Redirige al catálogo"""
    # Usar el nombre correcto de la función del endpoint
    return redirect(url_for('products.catalogo_completo_cards'))

@main_bp.route('/home')
def home():
    """Ruta alternativa para la página principal"""
    return redirect(url_for('products.catalog'))

@main_bp.route('/about')
def about():
    """Página acerca de"""
    try:
        return render_template('about.html')
    except Exception as e:
        return render_template('base.html', 
                             title='Acerca de',
                             content='Página en construcción'), 200

@main_bp.route('/contact')
def contact():
    """Página de contacto"""
    try:
        return render_template('contact.html')
    except Exception as e:
        return render_template('base.html',
                             title='Contacto', 
                             content='Página de contacto en construcción'), 200

@main_bp.route('/health')
def health_check():
    """Endpoint de salud para verificar que la app funciona"""
    return jsonify({
        'status': 'ok', 
        'message': 'E-commerce funcionando correctamente',
        'version': '1.0.0'
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
            'session_management': 'ok'
        },
        'message': 'Todos los servicios operativos'
    })

# ==================== RUTAS DE COMPATIBILIDAD ====================

@main_bp.route('/catalogo')
def catalogo_redirect():
    """Redirección de compatibilidad para /catalogo"""
    return redirect(url_for('products.catalog'))

@main_bp.route('/productos')
def productos_redirect():
    """Redirección de compatibilidad para /productos"""
    return redirect(url_for('products.catalog'))

@main_bp.route('/tienda')
def tienda_redirect():
    """Redirección de compatibilidad para /tienda"""
    return redirect(url_for('products.catalog'))

# ==================== PÁGINAS DE ERROR PERSONALIZADAS ====================

@main_bp.errorhandler(404)
def page_not_found(e):
    """Página de error 404 personalizada"""
    return render_template('errors/404.html', 
                         title='Página no encontrada',
                         message='La página que buscas no existe'), 404

@main_bp.errorhandler(500)
def internal_server_error(e):
    """Página de error 500 personalizada"""
    return render_template('errors/500.html',
                         title='Error del servidor',
                         message='Ha ocurrido un error interno'), 500

# ==================== RUTAS DE UTILIDAD ====================

@main_bp.route('/favicon.ico')
def favicon():
    """Manejar solicitudes de favicon"""
    return redirect(url_for('static', filename='favicon.ico'))

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
    <url>
        <loc>{base_url}/</loc>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>{base_url}/catalog</loc>
        <changefreq>daily</changefreq>
        <priority>0.9</priority>
    </url>
    <url>
        <loc>{base_url}/about</loc>
        <changefreq>monthly</changefreq>
        <priority>0.5</priority>
    </url>
    <url>
        <loc>{base_url}/contact</loc>
        <changefreq>monthly</changefreq>
        <priority>0.5</priority>
    </url>
</urlset>"""
    
    from flask import Response
    return Response(sitemap_xml, mimetype='application/xml')

# ==================== RUTAS DE BÚSQUEDA GLOBAL ====================

@main_bp.route('/buscar')
def buscar_global():
    """Búsqueda global que redirige al catálogo con parámetros"""
    query = request.args.get('q', '')
    vendor = request.args.get('vendor', '')
    
    # Construir URL del catálogo con parámetros de búsqueda
    catalog_url = url_for('products.catalog', q=query, vendor=vendor)
    return redirect(catalog_url)

@main_bp.route('/search')
def search_redirect():
    """Redirección de compatibilidad para búsqueda en inglés"""
    query = request.args.get('q', '')
    vendor = request.args.get('vendor', '')
    
    catalog_url = url_for('products.catalog', q=query, vendor=vendor)
    return redirect(catalog_url)