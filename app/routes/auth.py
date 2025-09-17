from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models.user import User
from functools import wraps

auth_bp = Blueprint('auth', __name__)

# Decorador para requerir autenticación
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión para acceder a esta página', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para requerir roles específicos
def role_required(role_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor inicia sesión para acceder a esta página', 'warning')
                return redirect(url_for('auth.login'))
            
            user = User.query.get(session['user_id'])
            if not user or not user.has_role(role_name):
                flash('No tienes permisos para acceder a esta página', 'danger')
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if user.is_active:
                session['user_id'] = user.id
                session['user_email'] = user.email
                session['user_role'] = 'admin' if user.is_admin else user.account_type
                
                flash(f'¡Bienvenido de vuelta, {user.email}!', 'success')
                
                # Redirigir según el rol
                if user.is_admin:
                    return redirect(url_for('admin.dashboard'))
                else:
                    return redirect(url_for('products.catalogo_completo_cards'))
            else:
                flash('Tu cuenta está pendiente de activación', 'warning')
        else:
            flash('Email o contraseña incorrectos', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        account_type = request.form.get('account_type', 'public')
        full_name = request.form.get('full_name')
        
        # Verificar si el usuario ya existe
        if User.query.filter_by(email=email).first():
            flash('Este email ya está registrado', 'danger')
            return render_template('auth/register.html')
        
        # Crear nuevo usuario
        new_user = User(
            email=email,
            account_type=account_type,
            full_name=full_name
        )
        new_user.set_password(password)
        
        # Los usuarios admin solo se crean manualmente
        new_user.is_admin = False
        
        # Activar automáticamente usuarios públicos, clientes requieren validación
        new_user.is_active = (account_type == 'public')
        
        db.session.add(new_user)
        db.session.commit()
        
        if account_type == 'public':
            flash('¡Cuenta creada exitosamente! Ya puedes iniciar sesión', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('¡Solicitud de cuenta enviada! Requerirá validación administrativa', 'warning')
            return redirect(url_for('main.index'))
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada exitosamente', 'info')
    return redirect(url_for('main.index'))