# app/routes/api.py - VERSIÓN CORRECTA
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.product import Product

# Definir el Blueprint - ¡ESTA LÍNEA ES ESENCIAL!
api_bp = Blueprint('api', __name__)

@api_bp.route('/health')
def health_check():
    """Endpoint de salud para verificar que la API funciona."""
    return jsonify({
        'status': 'ok', 
        'message': 'API funcionando correctamente',
        'timestamp': '2025-09-12T18:30:00Z'
    })

@api_bp.route('/products')
def api_products():
    """Endpoint de productos (placeholder)."""
    return jsonify({
        'products': [],
        'count': 0,
        'message': 'Endpoint de productos - En desarrollo'
    })

@api_bp.route('/search')
def api_search():
    """Endpoint de búsqueda (placeholder)."""
    query = request.args.get('q', '')
    return jsonify({
        'query': query,
        'results': [],
        'count': 0,
        'message': 'Endpoint de búsqueda - En desarrollo'
    })

@api_bp.route('/user-info')
@login_required
def user_info():
    """Información del usuario actual."""
    return jsonify({
        'user_id': current_user.id,
        'email': current_user.email,
        'is_admin': current_user.is_admin,
        'is_active': current_user.is_active
    })

@api_bp.route('/stats')
@login_required
def stats():
    """Estadísticas básicas (solo para admins)."""
    if not current_user.is_admin:
        return jsonify({'error': 'Acceso no autorizado'}), 403
    
    user_count = User.query.count()
    product_count = Product.query.count()
    
    return jsonify({
        'users_count': user_count,
        'products_count': product_count,
        'active_users': User.query.filter_by(is_active=True).count()
    })