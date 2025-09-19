# app/routes/admin.py - VERSIÓN CORRECTA
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user

# Definir el Blueprint
admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
def require_admin():
    """Verifica que el usuario sea administrador antes de acceder a rutas de admin."""
    if not current_user.is_admin:
        flash('Acceso restringido a administradores', 'danger')
        return redirect(url_for('main.index'))

@admin_bp.route('/dashboard')
def dashboard():
    """Panel de administración principal."""
    admin_data = {
        'user_name': current_user.name or 'Administrador',
        'total_users': 143,  # Esto deberías obtenerlo de la BD
        'pending_quotes': 24,  # Esto deberías obtenerlo de la BD
        'monthly_revenue': 125000.75,  # Esto deberías obtenerlo de la BD
        'low_stock': 18,  # Esto deberías obtenerlo de la BD
        'user_type': 'admin'
    }
    return render_template('admin_dashboard.html', **admin_data)

# Mantén tus otras rutas de admin...
@admin_bp.route('/users')
def manage_users():
    """Gestión de usuarios."""
    return render_template('admin/users.html')

@admin_bp.route('/products')
def manage_products():
    """Gestión de productos."""
    return render_template('admin/products.html')

@admin_bp.route('/verifications')
def manage_verifications():
    """Gestión de verificaciones de usuarios."""
    return render_template('admin/verifications.html')

@admin_bp.route('/orders')
def manage_orders():
    """Gestión de órdenes."""
    return render_template('admin/orders.html')