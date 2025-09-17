# app/routes/admin.py - VERSIÓN CORRECTA
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

# Definir el Blueprint - ¡ESTA LÍNEA ES ESENCIAL!
admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
def require_admin():
    """Verifica que el usuario sea administrador antes de acceder a rutas de admin."""
    if not current_user.is_admin:
        flash('Acceso restringido a administradores', 'danger')
        return redirect(url_for('main.index'))

@admin_bp.route('/')
def dashboard():
    """Panel de administración principal."""
    return render_template('admin/dashboard.html')

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