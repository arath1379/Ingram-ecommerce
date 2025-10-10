# app/routes/admin.py - VERSIÓN COMPLETA CON CATÁLOGO
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from datetime import datetime
from sqlalchemy import or_
from app import db
from app.models import User, Quote, Product, QuoteHistory
from app.models.product_utils import ProductUtils
from app.models.image_handler import ImageHandler
from app.models.api_client import APIClient
from app.models.purchase import Purchase, PurchaseHistory, PurchaseItem

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión', 'danger')
            return redirect(url_for('auth.login', next=request.url))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash('Acceso restringido a administradores', 'danger')
            return redirect(url_for('main.index'))
        
        print(f"✅ Acceso admin concedido a: {user.email}")
        return f(*args, **kwargs)
    return decorated_function

# ==================== RUTAS PRINCIPALES ====================
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Dashboard principal de administración."""
    try:
        from sqlalchemy import func
        from datetime import date
        
        total_users = User.query.count()
        client_users = User.query.filter_by(account_type='client').count()
        total_quotes = Quote.query.count()
        quotes_today = Quote.query.filter(
            func.date(Quote.created_at) == date.today()
        ).count()
        
        new_users_month = User.query.filter(
            func.extract('month', User.created_at) == datetime.now().month,
            func.extract('year', User.created_at) == datetime.now().year
        ).count()
        
        admin_data = {
            'user_name': session.get('user_email', 'Administrador'),
            'total_users': total_users,
            'client_users': client_users,
            'total_quotes': total_quotes,
            'total_sales': 0,
            'quotes_today': quotes_today,
            'new_users_month': new_users_month,
            'sales_month': 0,
            'last_login': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'system_info': {'version': '1.0.0', 'database': 'SQLite'}
        }
        
        return render_template('admin/admin_dashboard.html', admin_data=admin_data)
        
    except Exception as e:
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Dashboard Admin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        </head>
        <body>
            <div class="container mt-4">
                <div class="alert alert-warning">
                    <h4>Dashboard de Administración</h4>
                    <p>Error: {str(e)}</p>
                </div>
                <a href="/admin/users" class="btn btn-primary">Gestionar Usuarios</a>
                <a href="/logout" class="btn btn-secondary">Cerrar Sesión</a>
            </div>
        </body>
        </html>
        """

@admin_bp.route('/test')
@admin_required
def test():
    user = User.query.get(session['user_id'])
    return jsonify({'status': 'success', 'user': user.email, 'is_admin': user.is_admin})

# ==================== RUTAS DE GESTIÓN ====================
@admin_bp.route('/users')
@admin_required
def users():
    """Gestión de usuarios."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        query = User.query
        
        search = request.args.get('search', '').strip()
        if search:
            query = query.filter(
                (User.full_name.contains(search)) |
                (User.email.contains(search)) |
                (User.business_name.contains(search))
            )
        
        user_type = request.args.get('type', '')
        if user_type:
            query = query.filter_by(account_type=user_type)
        
        status = request.args.get('status', '')
        if status == 'verified':
            query = query.filter_by(is_verified=True)
        elif status == 'unverified':
            query = query.filter_by(is_verified=False)
        elif status == 'active':
            query = query.filter_by(is_active=True)
        elif status == 'inactive':
            query = query.filter_by(is_active=False)
        
        pagination = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('admin/users.html', 
                             users=pagination.items, 
                             pagination=pagination,
                             current_user=User.query.get(session['user_id']))
        
    except Exception as e:
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Error</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body>
            <div class="container mt-4">
                <div class="alert alert-danger">
                    <h4>Error cargando usuarios</h4>
                    <p>{str(e)}</p>
                </div>
                <a href="/admin/dashboard" class="btn btn-primary">Volver al Dashboard</a>
            </div>
        </body>
        </html>
        """

@admin_bp.route('/quotes')
@admin_required
def quotes():
    """Gestión de cotizaciones."""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Gestión de cotizaciones por: {user.email}")
        
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        status_filter = request.args.get('status', '')
        search = request.args.get('search', '').strip()
        
        query = Quote.query
        
        if status_filter:
            query = query.filter(Quote.status == status_filter)
            
        if search:
            query = query.filter(Quote.quote_number.contains(search))
        
        quotes_pagination = query.order_by(Quote.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Estadísticas
        stats = {
            'total': Quote.query.count(),
            'draft': Quote.query.filter_by(status='draft').count(),
            'sent': Quote.query.filter_by(status='sent').count(),
            'pending': Quote.query.filter_by(status='pending').count(),
            'approved': Quote.query.filter_by(status='approved').count(),
            'rejected': Quote.query.filter_by(status='rejected').count(),
            'in_progress': Quote.query.filter_by(status='in_progress').count(),
            'completed': Quote.query.filter_by(status='completed').count(),
            'invoiced': Quote.query.filter_by(status='invoiced').count(),
            'paid': Quote.query.filter_by(status='paid').count(),
            'cancelled': Quote.query.filter_by(status='cancelled').count()
        }
        
        return render_template('admin/quotes.html',
                             quotes=quotes_pagination.items,
                             pagination=quotes_pagination,
                             status_filter=status_filter,
                             current_status=status_filter,
                             search=search,
                             stats=stats)
        
    except Exception as e:
        flash(f'Error al cargar cotizaciones: {str(e)}', 'danger')
        return render_template('admin/quotes.html', 
                             quotes=[], 
                             pagination=None,
                             stats={'total': 0, 'draft': 0, 'sent': 0, 'pending': 0, 'approved': 0, 'rejected': 0, 'in_progress': 0, 'completed': 0, 'invoiced': 0, 'paid': 0, 'cancelled': 0})
    
# ==================== GESTIÓN DE PRODUCTOS (SOLO CATÁLOGO INGRAM) ====================
@admin_bp.route('/products')
@admin_required
def products():
    """Gestión de productos - Solo catálogo Ingram para admin"""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Catálogo Admin por: {user.email}")
        
        # Parámetros de búsqueda del catálogo
        page_number = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 25))
        query = request.args.get("q", "").strip()
        vendor = request.args.get("vendor", "").strip()
        
        print(f"DEBUG - Catálogo Admin - Page: {page_number}, Query: '{query}', Vendor: '{vendor}'")
        
        # Buscar productos en Ingram
        productos, total_records, pagina_vacia = ProductUtils.buscar_productos_hibrido(
            query=query, 
            vendor=vendor, 
            page_number=page_number, 
            page_size=page_size, 
            use_keywords=bool(query)
        )
        
        print(f"DEBUG - Productos recibidos: {len(productos)}")
        
        # DEBUG DETALLADO DE LA ESTRUCTURA DE DATOS
        if productos:
            print(f"DEBUG - Tipo de productos: {type(productos)}")
            print(f"DEBUG - Primer producto completo: {productos[0]}")
            print(f"DEBUG - Claves del primer producto: {list(productos[0].keys()) if isinstance(productos[0], dict) else 'No es dict'}")
            
            # Buscar la clave correcta para el SKU
            primer_producto = productos[0]
            if isinstance(primer_producto, dict):
                for key, value in primer_producto.items():
                    if 'sku' in key.lower() or 'part' in key.lower() or 'number' in key.lower():
                        print(f"DEBUG - Posible clave SKU: '{key}' = '{value}'")
        
        # Aplicar lógica específica para admin (precios originales)
        productos_admin = []
        for i, producto in enumerate(productos):
            print(f"DEBUG - Procesando producto {i}: {type(producto)}")
            
            if not isinstance(producto, dict):
                print(f"DEBUG - Producto {i} no es diccionario: {producto}")
                continue
                
            producto_admin = producto.copy()
            
            # BUSCAR LA CLAVE CORRECTA DEL SKU - MÚLTIPLES POSIBILIDADES
            sku = None
            posibles_claves = ['ingramPartNumber', 'ingram_part_number', 'sku', 'partNumber', 'vendorPartNumber']
            
            for clave in posibles_claves:
                if clave in producto_admin:
                    sku = producto_admin[clave]
                    print(f"DEBUG - Encontrado SKU en clave '{clave}': {sku}")
                    break
            
            # Si no encontramos con las claves conocidas, buscar cualquier clave que contenga 'sku' o 'part'
            if not sku:
                for clave, valor in producto_admin.items():
                    if 'sku' in clave.lower() or 'part' in clave.lower():
                        sku = valor
                        print(f"DEBUG - Encontrado SKU en clave alternativa '{clave}': {sku}")
                        break
            
            # VERIFICAR QUE TENGA SKU VÁLIDO
            if not sku:
                print(f"DEBUG - Producto {i} sin SKU válido. Claves disponibles: {list(producto_admin.keys())}")
                producto_admin['precio_original'] = "SKU No Encontrado"
                producto_admin['precio_publico'] = "SKU No Encontrado"
                producto_admin['ingram_part_number'] = "NO SKU"
                productos_admin.append(producto_admin)
                continue
            
            print(f"DEBUG - Procesando producto con SKU: {sku}")
            
            # Para admin, mostrar información completa y precios originales
            try:
                # Obtener precio original de la API
                price_url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
                body = {"products": [{"ingramPartNumber": sku}]}
                params = {
                    "includeAvailability": "true",
                    "includePricing": "true"
                }
                
                print(f"DEBUG - Consultando precio para: {sku}")
                precio_res = APIClient.make_request("POST", price_url, params=params, json=body)
                
                if precio_res and precio_res.status_code == 200:
                    precio_data = precio_res.json()
                    if precio_data and isinstance(precio_data, list) and len(precio_data) > 0:
                        first_product = precio_data[0]
                        if first_product.get('productStatusCode') != 'E':
                            pricing = first_product.get('pricing', {})
                            if pricing:
                                customer_price = pricing.get('customerPrice')
                                if customer_price is not None:
                                    # PRECIO ORIGINAL PARA ADMIN
                                    precio_original = float(customer_price)
                                    producto_admin['precio_original'] = f"${precio_original:,.2f}"
                                    
                                    # Calcular precio público con markup (solo para referencia)
                                    precio_publico = round(precio_original * 1.15, 2)
                                    producto_admin['precio_publico'] = f"${precio_publico:,.2f}"
                                    
                                    # Información adicional para admin
                                    producto_admin['disponibilidad_real'] = first_product.get('totalAvailability', 0)
                                    producto_admin['disponible'] = first_product.get('available', False)
                                else:
                                    producto_admin['precio_original'] = "Consultar"
                                    producto_admin['precio_publico'] = "Consultar"
                            else:
                                producto_admin['precio_original'] = "Consultar"
                                producto_admin['precio_publico'] = "Consultar"
                        else:
                            producto_admin['precio_original'] = "No disponible"
                            producto_admin['precio_publico'] = "No disponible"
                    else:
                        producto_admin['precio_original'] = "Consultar"
                        producto_admin['precio_publico'] = "Consultar"
                else:
                    producto_admin['precio_original'] = "Error API"
                    producto_admin['precio_publico'] = "Error API"
                    
            except Exception as price_error:
                print(f"Error obteniendo precio para {sku}: {price_error}")
                producto_admin['precio_original'] = "Error"
                producto_admin['precio_publico'] = "Error"
            
            # Asegurar que siempre tengamos la clave ingram_part_number para el template
            producto_admin['ingram_part_number'] = sku
            productos_admin.append(producto_admin)
        
        print(f"DEBUG - Productos después de procesar: {len(productos_admin)}")
        
        # Cálculos de paginación
        total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
        page_number = max(1, min(page_number, total_pages))
        start_record = (page_number - 1) * page_size + 1 if total_records > 0 else 0
        end_record = min(page_number * page_size, total_records)
        
        return render_template('admin/products_management.html',
                             productos_ingram=productos_admin,
                             page_number=page_number,
                             total_records=total_records,
                             total_pages=total_pages,
                             start_record=start_record,
                             end_record=end_record,
                             query=query,
                             vendor=vendor,
                             selected_vendor=vendor,
                             pagina_vacia=pagina_vacia,
                             local_vendors=ProductUtils.get_local_vendors(),
                             get_image_url_enhanced=ImageHandler.get_image_url_enhanced,
                             get_availability_text=ProductUtils.get_availability_text)
        
    except Exception as e:
        print(f"ERROR en catálogo admin: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error al cargar productos: {str(e)}', 'danger')
        return render_template('admin/products_management.html', 
                             productos_ingram=[])
    
# ==================== DETALLE DE PRODUCTO INGRAM ====================
@admin_bp.route('/products/catalog/<part_number>')
@admin_required
def product_catalog_detail(part_number):
    """Detalle de producto del catálogo Ingram"""
    try:
        # Validar que part_number no esté vacío
        if not part_number or part_number == 'None':
            flash('Número de parte inválido', 'danger')
            return redirect(url_for('admin.products', view='catalog'))
        
        user = User.query.get(session['user_id'])
        print(f"✅ Detalle producto catálogo por: {user.email} - SKU: {part_number}")
        
        # Detalle del producto
        detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
        detalle_res = APIClient.make_request("GET", detail_url)
        
        if detalle_res.status_code != 200:
            flash(f'Producto {part_number} no encontrado en Ingram Micro', 'warning')
            return redirect(url_for('admin.products', view='catalog'))
        
        detalle = detalle_res.json()
        
        # Verificar que el producto tenga datos válidos
        if not detalle or 'ingramPartNumber' not in detalle:
            flash(f'Datos del producto {part_number} incompletos', 'warning')
            return redirect(url_for('admin.products', view='catalog'))

        # Precio y disponibilidad - PARA ADMIN MOSTRAR PRECIO ORIGINAL
        price_url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
        body = {"products": [{"ingramPartNumber": part_number}]}
        params = {
            "includeAvailability": "true",
            "includePricing": "true",
            "includeProductAttributes": "true"
        }
        
        precio_res = APIClient.make_request("POST", price_url, params=params, json=body)
        
        precio_info = {}
        if precio_res and precio_res.status_code == 200:
            precio_data = precio_res.json()
            if precio_data and isinstance(precio_data, list) and len(precio_data) > 0:
                precio_info = precio_data[0]

        # PARA ADMIN: Mostrar precio original sin markup
        pricing = precio_info.get("pricing") or {}
        precio_original = pricing.get("customerPrice")
        currency = pricing.get("currencyCode") or pricing.get("currency") or "USD"
        
        # Formatear precio original para admin
        if precio_original is not None:
            try:
                precio_original_val = float(precio_original)
                precio_original_formatted = ProductUtils.format_currency(precio_original_val, currency)
                precio_publico_val = round(precio_original_val * 1.15, 2)
                precio_publico_formatted = ProductUtils.format_currency(precio_publico_val, currency)
            except Exception as e:
                print(f"Error formateando precios: {e}")
                precio_original_formatted = "Consultar"
                precio_publico_formatted = "Consultar"
        else:
            precio_original_formatted = "No disponible"
            precio_publico_formatted = "No disponible"

        # Disponibilidad
        disponibilidad = ProductUtils.get_availability_text(precio_info, detalle)

        # Información de inventario
        inventory_info = {
            'available': precio_info.get("available", False),
            'total_availability': precio_info.get("totalAvailability", 0),
            'backOrderable': precio_info.get("backOrderable", False),
            'ingram_part_number': precio_info.get("ingramPartNumber", part_number)
        }

        # Extraer atributos
        atributos = []
        raw_attrs = detalle.get("productAttributes") or detalle.get("attributes") or []
        for a in raw_attrs:
            name = a.get("name") or a.get("attributeName") or a.get("key") or None
            value = a.get("value") or a.get("attributeValue") or a.get("val") or ""
            if name and value:
                atributos.append({"name": name, "value": value})

        # Imagen mejorada
        imagen_url = ImageHandler.get_image_url_enhanced(detalle)
        
        return render_template(
            "admin/product_catalog_detail.html",
            detalle=detalle,
            precio_original=precio_original_formatted,
            precio_publico=precio_publico_formatted,
            disponibilidad=disponibilidad,
            inventory_info=inventory_info,
            atributos=atributos,
            imagen_url=imagen_url,
            part_number=part_number
        )
    
    except Exception as e:
        print(f"Error obteniendo detalle del producto {part_number}: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error al cargar el detalle del producto: {str(e)}', 'danger')
        return redirect(url_for('admin.products', view='catalog'))
# ==================== RUTAS ADICIONALES ====================
@admin_bp.route('/reports')
@admin_required
def reports():
    """Reportes y analytics."""
    user = User.query.get(session['user_id'])
    print(f"✅ Reportes accedido por: {user.email}")
    
    report_data = {
        'period_days': 30,
        'sales_data': [],
        'top_products': [],
        'active_users': [],
        'total_sales': 0,
        'total_quotes': 0
    }
    return render_template('admin/reports.html', **report_data)

@admin_bp.route('/verifications')
@admin_required
def verifications():
    """Gestión de verificaciones de usuarios."""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Verificaciones accedido por: {user.email}")
        
        unverified_users = User.query.filter_by(is_verified=False).order_by(User.created_at.desc()).all()
        return render_template('admin/verifications.html', users=unverified_users)
    except Exception as e:
        flash(f'Error al cargar verificaciones: {str(e)}', 'danger')
        return render_template('admin/verifications.html', users=[])

@admin_bp.route('/orders')
@admin_required
def orders():
    """Gestión de órdenes."""
    return redirect(url_for('admin.quotes'))

# ==================== ACCIONES ADMINISTRATIVAS ====================
@admin_bp.route('/approve_quote/<int:quote_id>')
@admin_required
def approve_quote(quote_id):
    """Aprobar una cotización."""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Aprobando cotización {quote_id} por: {user.email}")
        
        quote = Quote.query.get(quote_id)
        if quote:
            quote.status = 'approved'
            quote.updated_at = datetime.now()
            db.session.commit()
            flash(f'Cotización {quote.quote_number} aprobada exitosamente', 'success')
        else:
            flash('Cotización no encontrada', 'danger')
        
    except Exception as e:
        flash(f'Error al aprobar cotización: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.quotes'))

@admin_bp.route('/reject_quote/<int:quote_id>')
@admin_required
def reject_quote(quote_id):
    """Rechazar una cotización."""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Rechazando cotización {quote_id} por: {user.email}")
        
        quote = Quote.query.get(quote_id)
        if quote:
            quote.status = 'rejected'
            quote.updated_at = datetime.now()
            db.session.commit()
            flash(f'Cotización {quote.quote_number} rechazada', 'warning')
        else:
            flash('Cotización no encontrada', 'danger')
        
    except Exception as e:
        flash(f'Error al rechazar cotización: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.quotes'))

# ==================== GESTIÓN DE USUARIOS - ACCIONES ====================
@admin_bp.route('/users/verify/<int:user_id>')
@admin_required
def verify_user(user_id):
    """Verificar un usuario."""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.is_verified:
            flash(f'El usuario {user.email} ya está verificado', 'warning')
        else:
            user.is_verified = True
            user.updated_at = datetime.now()
            db.session.commit()
            flash(f'Usuario {user.email} verificado exitosamente', 'success')
        
    except Exception as e:
        flash(f'Error al verificar usuario: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/unverify/<int:user_id>')
@admin_required
def unverify_user(user_id):
    """Quitar verificación a un usuario."""
    try:
        user = User.query.get_or_404(user_id)
        
        if not user.is_verified:
            flash(f'El usuario {user.email} no está verificado', 'warning')
        else:
            user.is_verified = False
            user.updated_at = datetime.now()
            db.session.commit()
            flash(f'Verificación removida del usuario {user.email}', 'warning')
        
    except Exception as e:
        flash(f'Error al remover verificación: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/activate/<int:user_id>')
@admin_required
def activate_user(user_id):
    """Activar un usuario."""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.is_active:
            flash(f'El usuario {user.email} ya está activo', 'warning')
        else:
            user.is_active = True
            user.updated_at = datetime.now()
            db.session.commit()
            flash(f'Usuario {user.email} activado exitosamente', 'success')
        
    except Exception as e:
        flash(f'Error al activar usuario: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/deactivate/<int:user_id>')
@admin_required
def deactivate_user(user_id):
    """Desactivar un usuario."""
    try:
        user = User.query.get_or_404(user_id)
        
        if not user.is_active:
            flash(f'El usuario {user.email} ya está inactivo', 'warning')
        else:
            user.is_active = False
            user.updated_at = datetime.now()
            db.session.commit()
            flash(f'Usuario {user.email} desactivado', 'warning')
        
    except Exception as e:
        flash(f'Error al desactivar usuario: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    """Eliminar un usuario."""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.id == session.get('user_id'):
            flash('No puedes eliminar tu propia cuenta', 'danger')
            return redirect(url_for('admin.users'))
        
        email = user.email
        db.session.delete(user)
        db.session.commit()
        flash(f'Usuario {email} eliminado exitosamente', 'success')
        
    except Exception as e:
        flash(f'Error al eliminar usuario: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.users'))

# ==================== APIs ====================
@admin_bp.route('/api/stats')
@admin_required
def api_stats():
    """API para obtener estadísticas actualizadas."""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ API stats accedido por: {user.email}")
        
        total_users = User.query.count()
        pending_quotes = Quote.query.filter_by(status='pending').count()
        monthly_revenue = 0
        low_stock = Product.query.filter(Product.stock < 10).count()
        
        return jsonify({
            'total_users': total_users,
            'pending_quotes': pending_quotes,
            'monthly_revenue': monthly_revenue,
            'low_stock': low_stock
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/new-quotes')
@admin_required
def api_new_quotes():
    """API para verificar nuevas cotizaciones."""
    return jsonify({'count': 0})

# ==================== RUTA DE DEBUG ====================
@admin_bp.route('/debug')
def debug_admin():
    """Ruta temporal para debug"""
    return jsonify({
        'session_user_id': session.get('user_id'),
        'session_user_email': session.get('user_email'),
        'session_keys': list(session.keys())
    })

# ==================== RUTAS AVANZADAS DE COTIZACIONES ====================
@admin_bp.route('/quotes/<int:quote_id>')
@admin_required
def quote_detail(quote_id):
    """Vista detallada de una cotización"""
    try:
        quotation = Quote.query.get_or_404(quote_id)
        history = QuoteHistory.query.filter_by(quote_id=quote_id).order_by(QuoteHistory.created_at.desc()).all()
        
        return render_template('admin/quotation_detail.html',
                             quotation=quotation,
                             history=history)
        
    except Exception as e:
        flash(f'Error al cargar la cotización: {str(e)}', 'danger')
        return redirect(url_for('admin.quotes'))

@admin_bp.route('/quotes/<int:quote_id>/update_status', methods=['POST'])
@admin_required
def update_quote_status(quote_id):
    """API para actualizar el estado de una cotización"""
    try:
        quotation = Quote.query.get_or_404(quote_id)
        data = request.json
        action = data.get('action')
        admin_notes = data.get('admin_notes', '')
        admin_user = User.query.get(session['user_id'])
        
        new_status = None
        action_description = ""
        
        if action == 'send':
            new_status = 'sent'
            action_description = "Cotización enviada al cliente"
        elif action == 'approve':
            new_status = 'approved'
            quotation.approved_at = datetime.utcnow()
            quotation.approved_by = admin_user.email
            action_description = "Cotización aprobada"
        elif action == 'reject':
            new_status = 'rejected'
            action_description = "Cotización rechazada"
        elif action == 'progress':
            new_status = 'in_progress'
            action_description = "Cotización en progreso"
        elif action == 'complete':
            new_status = 'completed'
            action_description = "Cotización completada"
        elif action == 'invoice':
            new_status = 'invoiced'
            quotation.invoice_number = data.get('invoice_number')
            quotation.invoice_date = datetime.utcnow()
            action_description = f"Factura {data.get('invoice_number')} generada"
        elif action == 'pay':
            new_status = 'paid'
            quotation.payment_date = datetime.utcnow()
            quotation.payment_method = data.get('payment_method', '')
            quotation.payment_reference = data.get('payment_reference', '')
            action_description = "Cotización pagada"
        elif action == 'cancel':
            new_status = 'cancelled'
            action_description = "Cotización cancelada"
        
        if new_status:
            quotation.status = new_status
            quotation.admin_notes = admin_notes
            quotation.updated_at = datetime.utcnow()
            
            # Agregar al historial
            history = QuoteHistory(
                quote_id=quotation.id,
                action=action_description,
                description=f"{action_description}. Notas: {admin_notes}",
                user_id=admin_user.id,
                user_name=admin_user.email
            )
            db.session.add(history)
            
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': f'Cotización {action_description.lower()}',
                'new_status': new_status
            })
        else:
            return jsonify({
                'success': False, 
                'error': 'Acción no válida'
            }), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/quotes/<int:quote_id>/add_note', methods=['POST'])
@admin_required
def add_quote_note(quote_id):
    """API para agregar una nota al historial"""
    try:
        quotation = Quote.query.get_or_404(quote_id)
        data = request.json
        note = data.get('note', '').strip()
        admin_user = User.query.get(session['user_id'])
        
        if note:
            history = QuoteHistory(
                quote_id=quotation.id,
                action="Nota agregada",
                description=note,
                user_id=admin_user.id,
                user_name=admin_user.email
            )
            db.session.add(history)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Nota agregada correctamente'})
        else:
            return jsonify({'success': False, 'error': 'La nota no puede estar vacía'}), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS DEL CATÁLOGO PARA ADMINISTRADOR ====================
@admin_bp.route('/catalog/search')
@admin_required
def admin_catalog_search():
    """Búsqueda específica para administradores"""
    try:
        user = User.query.get(session['user_id'])
        search_type = request.args.get('type', 'sku')
        query = request.args.get('query', '').strip()
        page = request.args.get('page', 1, type=int)
        
        print(f"✅ Búsqueda en catálogo admin por: {user.email} - Tipo: {search_type}, Query: {query}")
        
        # Aquí puedes usar tu función existente de búsqueda
        productos = []
        total_results = 0
        
        if query:
            # Usar tu función de búsqueda existente
            productos, total_results, _ = ProductUtils.buscar_productos_hibrido(
                query=query, 
                vendor="", 
                page_number=page, 
                page_size=20, 
                use_keywords=bool(query)
            )
            
            # Aplicar transformaciones para admin
            for producto in productos:
                # Para admin, mostrar información de costo real
                if 'precio_final' in producto:
                    producto['precio_admin'] = producto.get('precio_base', 'Consultar')
                    producto['markup_aplicado'] = '15%'  # O calcular basado en la diferencia
        
        return render_template('admin/catalog/admin_search_results.html',
                             productos=productos,
                             search_type=search_type,
                             query=query,
                             total_results=total_results,
                             current_page=page)
        
    except Exception as e:
        flash(f'Error en la búsqueda: {str(e)}', 'danger')
        return render_template('admin/catalog/admin_search_results.html', 
                             productos=[], 
                             total_results=0,
                             query=request.args.get('query', ''))

# ==================== APIS ESPECÍFICAS PARA ADMIN ====================
@admin_bp.route('/api/admin/catalog/search')
@admin_required
def api_admin_catalog_search():
    """API para búsqueda en tiempo real del catálogo (admin)"""
    try:
        search_type = request.args.get('type', 'sku')
        query = request.args.get('q', '').strip()
        limit = request.args.get('limit', 10, type=int)
        
        if not query or len(query) < 2:
            return jsonify({'results': []})
        
        # Usar tu función de búsqueda existente
        productos, total, _ = ProductUtils.buscar_productos_hibrido(
            query=query, 
            vendor="", 
            page_number=1, 
            page_size=limit, 
            use_keywords=bool(query)
        )
        
        # Formatear resultados para autocompletar
        results = []
        for producto in productos[:limit]:
            results.append({
                'id': producto.get('ingram_part_number', ''),
                'text': f"{producto.get('ingram_part_number', '')} - {producto.get('description', '')}",
                'vendor': producto.get('vendor_name', ''),
                'category': producto.get('category', '')
            })
        
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'results': []
        }), 500

@admin_bp.route('/api/admin/catalog/availability/<part_number>')
@admin_required
def api_admin_catalog_availability(part_number):
    """API para verificar disponibilidad y precios (admin - datos originales)"""
    try:
        # Obtener información actualizada de precio y disponibilidad
        price_url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
        body = {"products": [{"ingramPartNumber": part_number}]}
        params = {
            "includeAvailability": "true",
            "includePricing": "true"
        }
        precio_res = APIClient.make_request("POST", price_url, params=params, json=body)
        
        if precio_res.status_code != 200:
            return jsonify({
                'success': False,
                'error': 'No se pudo obtener información del producto'
            }), 404
        
        precio_info = precio_res.json()[0]
        pricing = precio_info.get("pricing") or {}
        
        availability_data = {
            'ingram_part_number': part_number,
            'available': precio_info.get("available", False),
            'total_availability': precio_info.get("totalAvailability", 0),
            'backorder_available': precio_info.get("backOrderable", False),
            'pricing': {
                'customer_price': pricing.get("customerPrice"),
                'currency': pricing.get("currencyCode", "USD"),
                'retail_price': pricing.get("retailPrice"),
                'special_pricing': pricing.get("specialPricing", False)
            },
            'warehouses': precio_info.get("warehouses", [])
        }
        
        return jsonify({
            'success': True,
            'availability': availability_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== FUNCIONES AUXILIARES PARA ADMIN ====================
def apply_admin_pricing(productos):
    """Aplica transformaciones de precios para la vista de administrador"""
    productos_admin = []
    
    for producto in productos:
        producto_admin = producto.copy()
        
        # Para admin, mostrar información de costo real
        if 'precio_final' in producto_admin:
            # Guardar precio público como referencia
            producto_admin['precio_publico'] = producto_admin['precio_final']
            
            # Calcular y mostrar precio original (costo)
            try:
                if producto_admin.get('precio_base'):
                    precio_base = float(str(producto_admin['precio_base']).replace('$', '').replace(',', ''))
                    producto_admin['precio_original'] = f"${precio_base:.2f}"
                    
                    # Calcular markup aplicado
                    precio_publico_val = float(str(producto_admin['precio_final']).replace('$', '').replace(',', ''))
                    markup = ((precio_publico_val - precio_base) / precio_base) * 100
                    producto_admin['markup'] = f"{markup:.1f}%"
                else:
                    producto_admin['precio_original'] = "Consultar"
                    producto_admin['markup'] = "N/A"
            except Exception as e:
                producto_admin['precio_original'] = "Consultar"
                producto_admin['markup'] = "Error"
        
        productos_admin.append(producto_admin)
    
    return productos_admin

# ==================== CONFIGURACIÓN DEL SISTEMA ====================
@admin_bp.route('/settings')
@admin_required
def settings():
    """Configuración del sistema"""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Configuración accedida por: {user.email}")
        
        # Configuración básica del sistema
        system_settings = {
            'app_name': 'Ingram eCommerce',
            'version': '1.0.0',
            'environment': 'Development',
            'maintenance_mode': False,
            'max_users': 100,
            'default_markup': 15.0,
            'currency': 'MXN',
            'api_timeout': 30,
            'results_per_page': 25
        }
        
        return render_template('admin/settings.html', 
                             settings=system_settings,
                             current_user=user)
        
    except Exception as e:
        flash(f'Error al cargar configuración: {str(e)}', 'danger')
        return render_template('admin/settings.html', 
                             settings={},
                             current_user=User.query.get(session['user_id']))

@admin_bp.route('/settings/update', methods=['POST'])
@admin_required
def update_settings():
    """Actualizar configuración del sistema"""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Actualizando configuración por: {user.email}")
        
        # Aquí procesarías los datos del formulario
        # Por ahora solo mostramos un mensaje de éxito
        flash('Configuración actualizada exitosamente', 'success')
        return redirect(url_for('admin.settings'))
        
    except Exception as e:
        flash(f'Error al actualizar configuración: {str(e)}', 'danger')
        return redirect(url_for('admin.settings'))
    
# ==================== RUTAS DE ELIMINACIÓN CORREGIDAS ====================

@admin_bp.route('/quotes/delete/<int:quote_id>', methods=['POST', 'GET'])
@admin_required
def delete_quote(quote_id):
    """Eliminar una cotización permanentemente."""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Eliminando cotización {quote_id} por: {user.email}")
        
        quote = Quote.query.get_or_404(quote_id)
        quote_number = quote.quote_number
        
        # Eliminar el historial primero
        QuoteHistory.query.filter_by(quote_id=quote_id).delete()
        
        # Eliminar la cotización
        db.session.delete(quote)
        db.session.commit()
        
        flash(f'Cotización #{quote_number} eliminada permanentemente', 'success')
        
    except Exception as e:
        flash(f'Error al eliminar cotización: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.quotes'))

@admin_bp.route('/quotes/cancel/<int:quote_id>', methods=['POST', 'GET'])
@admin_required
def cancel_quote(quote_id):
    """Cancelar una cotización (cambio de estado a cancelled)."""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Cancelando cotización {quote_id} por: {user.email}")
        
        quote = Quote.query.get_or_404(quote_id)
        
        if quote.status == 'cancelled':
            flash(f'La cotización #{quote.quote_number} ya está cancelada', 'warning')
            return redirect(url_for('admin.quotes'))
        
        # Cambiar estado a cancelled
        quote.status = 'cancelled'
        quote.updated_at = datetime.now()
        
        # Agregar al historial
        history = QuoteHistory(
            quote_id=quote.id,
            action="Cotización cancelada",
            description=f"La cotización fue cancelada por el administrador {user.email}",
            user_id=user.id,
            user_name=user.email
        )
        db.session.add(history)
        
        db.session.commit()
        
        flash(f'Cotización #{quote.quote_number} cancelada exitosamente', 'warning')
        
    except Exception as e:
        flash(f'Error al cancelar cotización: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.quotes'))

@admin_bp.route('/quotes/bulk_action', methods=['POST'])
@admin_required
def quotes_bulk_action():
    """Acciones masivas sobre cotizaciones."""
    try:
        user = User.query.get(session['user_id'])
        action = request.form.get('bulk_action')
        quote_ids = request.form.getlist('quote_ids')
        
        if not quote_ids:
            flash('No se seleccionaron cotizaciones', 'warning')
            return redirect(url_for('admin.quotes'))
        
        quotes = Quote.query.filter(Quote.id.in_(quote_ids)).all()
        
        if action == 'delete':
            deleted_count = 0
            for quote in quotes:
                # Eliminar historial primero
                QuoteHistory.query.filter_by(quote_id=quote.id).delete()
                # Eliminar cotización
                db.session.delete(quote)
                deleted_count += 1
            
            db.session.commit()
            flash(f'{deleted_count} cotización(es) eliminada(s) permanentemente', 'success')
            
        elif action == 'cancel':
            cancelled_count = 0
            for quote in quotes:
                if quote.status != 'cancelled':
                    quote.status = 'cancelled'
                    quote.updated_at = datetime.now()
                    
                    # Agregar al historial
                    history = QuoteHistory(
                        quote_id=quote.id,
                        action="Cotización cancelada (acción masiva)",
                        description=f"Cancelada en acción masiva por {user.email}",
                        user_id=user.id,
                        user_name=user.email
                    )
                    db.session.add(history)
                    cancelled_count += 1
            
            db.session.commit()
            flash(f'{cancelled_count} cotización(es) cancelada(s)', 'warning')
            
        elif action == 'export':
            # Aquí podrías implementar exportación masiva
            flash(f'Exportando {len(quotes)} cotización(es) - Función en desarrollo', 'info')
            
        else:
            flash('Acción no válida', 'danger')
        
    except Exception as e:
        flash(f'Error en acción masiva: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.quotes'))

# ==================== GESTIÓN DE COMPRAS DIRECTAS ====================
@admin_bp.route('/purchases')
@admin_required
def purchases():
    """Gestión de compras directas y carritos de usuarios."""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Gestión de compras por: {user.email}")
        
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        status_filter = request.args.get('status', '')
        search = request.args.get('search', '').strip()
        tab = request.args.get('tab', 'purchases')  # 'purchases' o 'carts'
        
        # Query para Purchase
        from app.models import Purchase, Cart
        
        query = Purchase.query
        
        if status_filter:
            query = query.filter(Purchase.status == status_filter)
            
        if search:
            query = query.filter(
                (Purchase.order_number.contains(search)) |
                (Purchase.customer_email.contains(search)) |
                (Purchase.customer_name.contains(search))
            )
        
        purchases_pagination = query.order_by(Purchase.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Obtener carritos activos
        active_carts = Cart.query.filter(Cart.status == 'active').order_by(Cart.updated_at.desc()).all()
        
        # Estadísticas
        stats = {
            'total': Purchase.query.count(),
            'pending': Purchase.query.filter_by(status='pending').count(),
            'paid': Purchase.query.filter_by(status='paid').count(),
            'shipped': Purchase.query.filter_by(status='shipped').count(),
            'delivered': Purchase.query.filter_by(status='delivered').count(),
            'cancelled': Purchase.query.filter_by(status='cancelled').count(),
            'refunded': Purchase.query.filter_by(status='refunded').count(),
            'total_revenue': db.session.query(db.func.sum(Purchase.total_amount)).filter(Purchase.status.in_(['paid', 'shipped', 'delivered'])).scalar() or 0,
            'active_carts': len(active_carts),
            'total_cart_value': sum(cart.total_amount for cart in active_carts)
        }
        
        return render_template('admin/purchases.html',
                             purchases=purchases_pagination.items,
                             pagination=purchases_pagination,
                             status_filter=status_filter,
                             current_status=status_filter,
                             search=search,
                             tab=tab,
                             stats=stats,
                             active_carts=active_carts)
        
    except Exception as e:
        flash(f'Error al cargar compras: {str(e)}', 'danger')
        return render_template('admin/purchases.html', 
                             purchases=[], 
                             pagination=None,
                             stats={'total': 0, 'pending': 0, 'paid': 0, 'shipped': 0, 'delivered': 0, 'cancelled': 0, 'refunded': 0, 'total_revenue': 0, 'active_carts': 0, 'total_cart_value': 0},
                             active_carts=[])

@admin_bp.route('/purchases/<int:purchase_id>')
@admin_required
def purchase_detail(purchase_id):
    """Detalle de una compra específica."""
    try:
        from app.models import Purchase, PurchaseItem
        
        purchase = Purchase.query.get_or_404(purchase_id)
        items = PurchaseItem.query.filter_by(purchase_id=purchase_id).all()
        
        return render_template('admin/purchase_detail.html',
                             purchase=purchase,
                             items=items)
        
    except Exception as e:
        flash(f'Error al cargar la compra: {str(e)}', 'danger')
        return redirect(url_for('admin.purchases'))

@admin_bp.route('/purchases/<int:purchase_id>/update_status', methods=['POST'])
@admin_required
def update_purchase_status(purchase_id):
    """Actualizar el estado de una compra."""
    try:
        from app.models import Purchase, PurchaseHistory
        
        purchase = Purchase.query.get_or_404(purchase_id)
        data = request.json
        new_status = data.get('status')
        admin_notes = data.get('admin_notes', '')
        admin_user = User.query.get(session['user_id'])
        
        valid_statuses = ['pending', 'paid', 'shipped', 'delivered', 'cancelled', 'refunded']
        
        if new_status not in valid_statuses:
            return jsonify({
                'success': False, 
                'error': 'Estado no válido'
            }), 400
        
        # Actualizar estado
        old_status = purchase.status
        purchase.status = new_status
        purchase.updated_at = datetime.utcnow()
        
        # Agregar tracking number si se proporciona
        if new_status == 'shipped' and data.get('tracking_number'):
            purchase.tracking_number = data.get('tracking_number')
        
        # Agregar al historial
        history = PurchaseHistory(
            purchase_id=purchase.id,
            action=f"Estado actualizado: {old_status} → {new_status}",
            description=f"Estado cambiado por {admin_user.email}. Notas: {admin_notes}",
            user_id=admin_user.id,
            user_name=admin_user.email
        )
        db.session.add(history)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Estado actualizado a {new_status}',
            'new_status': new_status
        })
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/purchases/<int:purchase_id>/add_note', methods=['POST'])
@admin_required
def add_purchase_note(purchase_id):
    """Agregar nota a una compra."""
    try:
        from app.models import PurchaseHistory
        
        data = request.json
        note = data.get('note', '').strip()
        admin_user = User.query.get(session['user_id'])
        
        if note:
            history = PurchaseHistory(
                purchase_id=purchase_id,
                action="Nota agregada",
                description=note,
                user_id=admin_user.id,
                user_name=admin_user.email
            )
            db.session.add(history)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Nota agregada correctamente'})
        else:
            return jsonify({'success': False, 'error': 'La nota no puede estar vacía'}), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/purchases/stats')
@admin_required
def api_purchases_stats():
    """API para estadísticas de compras."""
    try:
        from app.models import Purchase
        from sqlalchemy import func, extract
        from datetime import datetime, timedelta
        
        # Estadísticas básicas
        total_purchases = Purchase.query.count()
        pending_purchases = Purchase.query.filter_by(status='pending').count()
        paid_purchases = Purchase.query.filter_by(status='paid').count()
        
        # Ingresos del mes actual
        current_month = datetime.now().month
        current_year = datetime.now().year
        monthly_revenue = db.session.query(func.sum(Purchase.total_amount)).filter(
            Purchase.status.in_(['paid', 'shipped', 'delivered']),
            extract('month', Purchase.created_at) == current_month,
            extract('year', Purchase.created_at) == current_year
        ).scalar() or 0
        
        # Compras de hoy
        today = datetime.now().date()
        today_purchases = Purchase.query.filter(
            func.date(Purchase.created_at) == today
        ).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_purchases': total_purchases,
                'pending_purchases': pending_purchases,
                'paid_purchases': paid_purchases,
                'monthly_revenue': float(monthly_revenue),
                'today_purchases': today_purchases
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500