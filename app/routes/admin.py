# app/routes/admin.py - VERSIÓN OPTIMIZADA SIN DUPLICADOS
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from datetime import datetime
from sqlalchemy import func
from app import db
from app.models import User, Quote, Product, QuoteHistory
from app.models.product_utils import ProductUtils
from app.models.image_handler import ImageHandler
from app.models.api_client import APIClient

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
        
        return f(*args, **kwargs)
    return decorated_function

# ==================== RUTAS PRINCIPALES ====================
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Dashboard principal de administración."""
    try:
        total_users = User.query.count()
        client_users = User.query.filter_by(account_type='client').count()
        total_quotes = Quote.query.count()
        quotes_today = Quote.query.filter(
            func.date(Quote.created_at) == datetime.now().date()
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
        flash(f'Error en dashboard: {str(e)}', 'danger')
        return render_template('admin/admin_dashboard.html', admin_data={})

# ==================== GESTIÓN DE USUARIOS (VERSIÓN UNIFICADA) ====================
@admin_bp.route('/users')
@admin_required
def users():
    """Gestión de usuarios."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        query = User.query
        
        # Filtros
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
                             pagination=pagination)
        
    except Exception as e:
        flash(f'Error cargando usuarios: {str(e)}', 'danger')
        return render_template('admin/users.html', users=[], pagination=None)

@admin_bp.route('/users/view/<int:user_id>')
@admin_required
def view_user(user_id):
    """Vista detallada de un usuario."""
    try:
        user = User.query.get_or_404(user_id)
        user_quotes = Quote.query.filter_by(user_id=user_id).count()
        recent_quotes = Quote.query.filter_by(user_id=user_id).order_by(Quote.created_at.desc()).limit(5).all()
        
        return render_template('admin/user_detail.html',
                             user=user,
                             user_quotes=user_quotes,
                             recent_quotes=recent_quotes)
        
    except Exception as e:
        flash(f'Error al cargar usuario: {str(e)}', 'danger')
        return redirect(url_for('admin.users'))

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Editar usuario - REEMPLAZA todas las rutas individuales de verify/activate/etc."""
    try:
        user = User.query.get_or_404(user_id)
        current_admin = User.query.get(session['user_id'])
        
        if request.method == 'POST':
            # Campos básicos
            user.full_name = request.form.get('full_name', user.full_name)
            user.email = request.form.get('email', user.email)
            user.business_name = request.form.get('business_name', user.business_name)
            user.rfc = request.form.get('rfc', user.rfc)
            user.curp = request.form.get('curp', user.curp)
            
            # Campos comerciales
            try:
                user.credit_limit = float(request.form.get('credit_limit', 0))
                user.discount_percentage = float(request.form.get('discount_percentage', 0))
            except ValueError:
                pass
            
            user.payment_terms = request.form.get('payment_terms', user.payment_terms)
            user.tax_id = request.form.get('tax_id', user.tax_id)
            user.commercial_reference = request.form.get('commercial_reference', user.commercial_reference)
            
            # Campos de permisos (solo admin)
            if current_admin.is_admin:
                account_type = request.form.get('account_type')
                if account_type in ['public', 'client', 'admin']:
                    user.account_type = account_type
                
                user.is_active = 'is_active' in request.form
                user.is_verified = 'is_verified' in request.form
                user.is_admin = 'is_admin' in request.form
            
            # Cambio de contraseña
            new_password = request.form.get('new_password', '').strip()
            if new_password:
                confirm_password = request.form.get('confirm_password', '').strip()
                if new_password == confirm_password and len(new_password) >= 6:
                    user.set_password(new_password)
                    flash('Contraseña actualizada', 'success')
                else:
                    flash('Error en contraseña', 'warning')
            
            user.updated_at = datetime.now()
            db.session.commit()
            
            flash('Usuario actualizado exitosamente', 'success')
            return redirect(url_for('admin.view_user', user_id=user_id))
        
        return render_template('admin/user_edit.html', user=user)
        
    except Exception as e:
        flash(f'Error al editar usuario: {str(e)}', 'danger')
        db.session.rollback()
        return redirect(url_for('admin.users'))

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    """Crear nuevo usuario."""
    try:
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            full_name = request.form.get('full_name', '').strip()
            
            if not email or not full_name:
                flash('Email y nombre son obligatorios', 'danger')
                return redirect(url_for('admin.create_user'))
            
            if User.query.filter_by(email=email).first():
                flash('El email ya existe', 'danger')
                return redirect(url_for('admin.create_user'))
            
            new_user = User(
                email=email,
                full_name=full_name,
                business_name=request.form.get('business_name', ''),
                rfc=request.form.get('rfc', ''),
                curp=request.form.get('curp', ''),
                account_type=request.form.get('account_type', 'public'),
                is_active='is_active' in request.form,
                is_verified='is_verified' in request.form,
                is_admin='is_admin' in request.form,
                credit_limit=float(request.form.get('credit_limit', 0)),
                discount_percentage=float(request.form.get('discount_percentage', 0)),
                payment_terms=request.form.get('payment_terms', 'CONTADO')
            )
            
            temp_password = "Temp123!"
            new_user.set_password(temp_password)
            
            db.session.add(new_user)
            db.session.commit()
            
            flash(f'Usuario creado. Contraseña temporal: {temp_password}', 'success')
            return redirect(url_for('admin.view_user', user_id=new_user.id))
        
        return render_template('admin/user_create.html')
        
    except Exception as e:
        flash(f'Error al crear usuario: {str(e)}', 'danger')
        db.session.rollback()
        return redirect(url_for('admin.users'))

@admin_bp.route('/users/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    """Eliminar usuario."""
    try:
        user = User.query.get_or_404(user_id)
        
        if user.id == session.get('user_id'):
            flash('No puedes eliminar tu propia cuenta', 'danger')
            return redirect(url_for('admin.users'))
        
        email = user.email
        db.session.delete(user)
        db.session.commit()
        
        flash(f'Usuario {email} eliminado', 'success')
        
    except Exception as e:
        flash(f'Error al eliminar usuario: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.users'))

# ==================== GESTIÓN DE COTIZACIONES (VERSIÓN UNIFICADA) ====================
@admin_bp.route('/quotes')
@admin_required
def quotes():
    """Gestión de cotizaciones."""
    try:
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
            'cancelled': Quote.query.filter_by(status='cancelled').count()
        }
        
        return render_template('admin/quotes.html',
                             quotes=quotes_pagination.items,
                             pagination=quotes_pagination,
                             status_filter=status_filter,
                             search=search,
                             stats=stats)
        
    except Exception as e:
        flash(f'Error al cargar cotizaciones: {str(e)}', 'danger')
        return render_template('admin/quotes.html', quotes=[], pagination=None, stats={})

@admin_bp.route('/quotes/<int:quote_id>')
@admin_required
def quote_detail(quote_id):
    """Detalle de cotización."""
    try:
        quotation = Quote.query.get_or_404(quote_id)
        history = QuoteHistory.query.filter_by(quote_id=quote_id).order_by(QuoteHistory.created_at.desc()).all()
        
        return render_template('admin/quotation_detail.html',
                             quotation=quotation,
                             history=history)
        
    except Exception as e:
        flash(f'Error al cargar cotización: {str(e)}', 'danger')
        return redirect(url_for('admin.quotes'))

@admin_bp.route('/quotes/<int:quote_id>/update_status', methods=['POST'])
@admin_required
def update_quote_status(quote_id):
    """API UNIFICADA para cambiar estado de cotización - REEMPLAZA rutas individuales."""
    try:
        quotation = Quote.query.get_or_404(quote_id)
        data = request.json
        action = data.get('action')
        admin_notes = data.get('admin_notes', '')
        admin_user = User.query.get(session['user_id'])
        
        status_map = {
            'send': 'sent',
            'approve': 'approved', 
            'reject': 'rejected',
            'progress': 'in_progress',
            'complete': 'completed',
            'invoice': 'invoiced',
            'pay': 'paid',
            'cancel': 'cancelled'
        }
        
        if action in status_map:
            new_status = status_map[action]
            quotation.status = new_status
            quotation.updated_at = datetime.now()
            
            # Campos adicionales según acción
            if action == 'approve':
                quotation.approved_at = datetime.now()
                quotation.approved_by = admin_user.email
            elif action == 'invoice':
                quotation.invoice_number = data.get('invoice_number')
                quotation.invoice_date = datetime.now()
            elif action == 'pay':
                quotation.payment_date = datetime.now()
                quotation.payment_method = data.get('payment_method', '')
                quotation.payment_reference = data.get('payment_reference', '')
            
            # Historial
            action_description = f"Cambiado a {new_status}"
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
                'message': f'Estado actualizado a {new_status}',
                'new_status': new_status
            })
        else:
            return jsonify({'success': False, 'error': 'Acción no válida'}), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/quotes/<int:quote_id>/add_note', methods=['POST'])
@admin_required
def add_quote_note(quote_id):
    """Agregar nota al historial."""
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
            
            return jsonify({'success': True, 'message': 'Nota agregada'})
        else:
            return jsonify({'success': False, 'error': 'Nota vacía'}), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/quotes/delete/<int:quote_id>', methods=['POST'])
@admin_required
def delete_quote(quote_id):
    """Eliminar cotización."""
    try:
        quote = Quote.query.get_or_404(quote_id)
        quote_number = quote.quote_number
        
        QuoteHistory.query.filter_by(quote_id=quote_id).delete()
        db.session.delete(quote)
        db.session.commit()
        
        flash(f'Cotización #{quote_number} eliminada', 'success')
        
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.quotes'))

@admin_bp.route('/quotes/bulk_action', methods=['POST'])
@admin_required
def quotes_bulk_action():
    """Acciones masivas."""
    try:
        action = request.form.get('bulk_action')
        quote_ids = request.form.getlist('quote_ids')
        admin_user = User.query.get(session['user_id'])
        
        if not quote_ids:
            flash('No se seleccionaron cotizaciones', 'warning')
            return redirect(url_for('admin.quotes'))
        
        quotes = Quote.query.filter(Quote.id.in_(quote_ids)).all()
        
        if action == 'delete':
            for quote in quotes:
                QuoteHistory.query.filter_by(quote_id=quote.id).delete()
                db.session.delete(quote)
            flash(f'{len(quotes)} cotización(es) eliminadas', 'success')
            
        elif action == 'cancel':
            for quote in quotes:
                if quote.status != 'cancelled':
                    quote.status = 'cancelled'
                    quote.updated_at = datetime.now()
            flash(f'{len(quotes)} cotización(es) canceladas', 'warning')
            
        db.session.commit()
        
    except Exception as e:
        flash(f'Error en acción masiva: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('admin.quotes'))

# ==================== GESTIÓN DE PRODUCTOS (CATÁLOGO INGRAM) ====================
@admin_bp.route('/products')
@admin_required
def products():
    """Gestión de productos - Catálogo Ingram."""
    try:
        page_number = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 25))
        query = request.args.get("q", "").strip()
        vendor = request.args.get("vendor", "").strip()
        
        productos, total_records, pagina_vacia = ProductUtils.buscar_productos_hibrido(
            query=query, 
            vendor=vendor, 
            page_number=page_number, 
            page_size=page_size, 
            use_keywords=bool(query)
        )
        
        # Procesar para admin
        productos_admin = []
        for producto in productos:
            if not isinstance(producto, dict):
                continue
                
            producto_admin = producto.copy()
            sku = None
            
            # Buscar SKU
            posibles_claves = ['ingramPartNumber', 'ingram_part_number', 'sku', 'partNumber', 'vendorPartNumber']
            for clave in posibles_claves:
                if clave in producto_admin:
                    sku = producto_admin[clave]
                    break
            
            if sku:
                try:
                    price_data = APIClient.get_product_price_and_availability(sku)
                    if price_data:
                        valid_status_codes = ['S', 'W']
                        product_status = price_data.get('productStatusCode', '')
                        
                        if product_status in valid_status_codes:
                            pricing = price_data.get('pricing', {})
                            availability = price_data.get('totalAvailability', 0)
                            
                            if pricing and pricing.get('customerPrice') is not None:
                                precio_original = float(pricing['customerPrice'])
                                producto_admin['precio_original'] = f"${precio_original:,.2f}"
                                precio_publico = round(precio_original * 1.15, 2)
                                producto_admin['precio_publico'] = f"${precio_publico:,.2f}"
                                producto_admin['disponibilidad'] = availability
                                producto_admin['disponible'] = availability > 0
                            else:
                                producto_admin['precio_original'] = "Consultar"
                                producto_admin['precio_publico'] = "Consultar"
                        else:
                            producto_admin['precio_original'] = "No disponible"
                            producto_admin['precio_publico'] = "No disponible"
                    else:
                        producto_admin['precio_original'] = "Error API"
                        producto_admin['precio_publico'] = "Error API"
                except Exception:
                    producto_admin['precio_original'] = "Error"
                    producto_admin['precio_publico'] = "Error"
            else:
                producto_admin['precio_original'] = "Consultar"
                producto_admin['precio_publico'] = "Consultar"
                producto_admin['ingram_part_number'] = "NO SKU"
            
            producto_admin['ingram_part_number'] = sku or "NO SKU"
            productos_admin.append(producto_admin)
        
        # Paginación
        total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
        page_number = max(1, min(page_number, total_pages))
        start_record = (page_number - 1) * page_size + 1 if total_records > 0 else 0
        end_record = min(page_number * page_size, total_records)
        
        vendors = ProductUtils.get_local_vendors()
        
        return render_template('admin/products_management.html',
                             productos_ingram=productos_admin,
                             page_number=page_number,
                             total_records=total_records,
                             total_pages=total_pages,
                             start_record=start_record,
                             end_record=end_record,
                             query=query,
                             vendor=vendor,
                             pagina_vacia=pagina_vacia,
                             vendors=vendors, 
                             get_image_url_enhanced=ImageHandler.get_image_url_enhanced,
                             get_availability_text=ProductUtils.get_availability_text)
        
    except Exception as e:
        flash(f'Error al cargar productos: {str(e)}', 'danger')
        return render_template('admin/products_management.html', productos_ingram=[])

# ==================== RUTAS ADICIONALES ====================
@admin_bp.route('/reports')
@admin_required
def reports():
    """Reportes."""
    report_data = {
        'period_days': 30,
        'sales_data': [],
        'top_products': [],
        'active_users': [],
        'total_sales': 0,
        'total_quotes': 0
    }
    return render_template('admin/reports.html', **report_data)

@admin_bp.route('/settings')
@admin_required
def settings():
    """Configuración."""
    system_settings = {
        'app_name': 'Ingram eCommerce',
        'version': '1.0.0',
        'environment': 'Development',
        'default_markup': 15.0,
        'currency': 'MXN'
    }
    return render_template('admin/settings.html', settings=system_settings)

# ==================== APIS ====================
@admin_bp.route('/api/stats')
@admin_required
def api_stats():
    """API estadísticas."""
    try:
        total_users = User.query.count()
        pending_quotes = Quote.query.filter_by(status='pending').count()
        
        return jsonify({
            'total_users': total_users,
            'pending_quotes': pending_quotes,
            'monthly_revenue': 0,
            'low_stock': 0
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/admin/catalog/search')
@admin_required
def api_admin_catalog_search():
    """API búsqueda catálogo."""
    try:
        query = request.args.get('q', '').strip()
        limit = request.args.get('limit', 10, type=int)
        
        if not query or len(query) < 2:
            return jsonify({'results': []})
        
        productos, total, _ = ProductUtils.buscar_productos_hibrido(
            query=query, vendor="", page_number=1, page_size=limit, use_keywords=bool(query)
        )
        
        results = []
        for producto in productos[:limit]:
            results.append({
                'id': producto.get('ingram_part_number', ''),
                'text': f"{producto.get('ingram_part_number', '')} - {producto.get('description', '')}",
                'vendor': producto.get('vendor_name', ''),
                'category': producto.get('category', '')
            })
        
        return jsonify({'success': True, 'results': results, 'count': len(results)})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'results': []}), 500
