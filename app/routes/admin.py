# app/routes/admin.py - VERSIÓN CORREGIDA (SIN DUPLICADOS)
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from datetime import datetime
from sqlalchemy import or_
from app import db
from app.models import User, Quote, Product

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
        business_users = User.query.filter_by(account_type='business').count()
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
            'business_users': business_users,
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
        
        return render_template('admin/quotes.html',
                             quotes=quotes_pagination.items,
                             pagination=quotes_pagination,
                             status_filter=status_filter,
                             search=search)
        
    except Exception as e:
        flash(f'Error al cargar cotizaciones: {str(e)}', 'danger')
        return render_template('admin/quotes.html', quotes=[], pagination=None)

@admin_bp.route('/products')
@admin_required
def products():
    """Gestión de productos."""
    try:
        user = User.query.get(session['user_id'])
        print(f"✅ Gestión de productos por: {user.email}")
        
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        category = request.args.get('category', '')
        search = request.args.get('search', '').strip()
        stock_status = request.args.get('stock', '')
        
        query = Product.query
        
        if category:
            query = query.filter(Product.category == category)
            
        if search:
            query = query.filter(
                or_(
                    Product.name.contains(search),
                    Product.description.contains(search),
                    Product.sku.contains(search)
                )
            )
            
        if stock_status == 'low':
            query = query.filter(Product.stock < 10)
        elif stock_status == 'out':
            query = query.filter(Product.stock == 0)
        
        products_pagination = query.order_by(Product.name).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        categories = []
        try:
            categories_data = db.session.query(Product.category).distinct().all()
            categories = [cat[0] for cat in categories_data if cat[0]]
        except:
            pass
        
        return render_template('admin/products.html',
                             products=products_pagination.items,
                             pagination=products_pagination,
                             categories=categories,
                             category=category,
                             search=search,
                             stock_status=stock_status)
        
    except Exception as e:
        flash(f'Error al cargar productos: {str(e)}', 'danger')
        return render_template('admin/products.html', products=[], pagination=None)

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