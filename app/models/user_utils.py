# app/models/user_utils.py (ACTUALIZADO)
from flask import session
from app.models.user import User

def get_current_user():
    """Obtener el usuario actual basado en la sesión"""
    user_id = session.get('user_id')
    if not user_id or user_id == 'anonymous_user':
        return None
    
    try:
        return User.query.get(user_id)
    except:
        return None

def is_public_user():
    """Determinar si el usuario actual es público (sin markup)"""
    user = get_current_user()
    # Usuario anónimo o sin tipo definido es público (precio base)
    if not user or not hasattr(user, 'user_type'):
        return True
    # Si es cliente empresarial, no es público (aplica markup)
    return user.user_type != 'business'

def is_business_user():
    """Determinar si el usuario actual es cliente empresarial (con markup)"""
    user = get_current_user()
    return user and hasattr(user, 'user_type') and user.user_type == 'business'

def get_user_pricing_tier():
    """Obtener el nivel de precios del usuario"""
    if is_business_user():
        return 'business'  # Precios con markup
    else:
        return 'public'    # Precios base (sin markup)