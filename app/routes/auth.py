# app/routes/auth.py - VERSIÓN CORREGIDA (SIN FLASK-LOGIN)
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from app import db
from app.models.user import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Tu cuenta está pendiente de activación. Contacta al administrador.', 'warning')
                return render_template('auth/login.html')
            
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['user_role'] = 'admin' if user.is_admin else user.account_type
            
            print(f"✅ Login exitoso: {user.email}")
            print(f"✅ Tipo de cuenta: {user.account_type}")  # Ahora será 'public', 'client' o 'admin'
            print(f"✅ Activo: {user.is_active}")
            print(f"✅ Verificado: {user.is_verified}")
            
            flash(f'¡Bienvenido de vuelta, {user.full_name or user.email}!', 'success')
            return redirect(url_for('main.post_login'))
        else:
            flash('Email o contraseña incorrectos', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        account_type = request.form.get('account_type', 'public')
        full_name = request.form.get('full_name')
        business_name = request.form.get('business_name', '')
        rfc = request.form.get('rfc', '')
        
        if User.query.filter_by(email=email).first():
            flash('Este email ya está registrado', 'danger')
            return render_template('auth/register.html')
        
        # ✅ LÓGICA SIMPLIFICADA: Solo 'public' y 'client'
        is_admin = False
        is_active = is_admin  # Solo admins activos automáticamente
        is_verified = (account_type == 'public' and is_active)
        
        new_user = User(
            email=email,
            account_type=account_type,  # 'public' o 'client'
            full_name=full_name,
            business_name=business_name if account_type == 'client' else None,  # ✅ Cambiado a 'client'
            rfc=rfc if account_type == 'client' else None,  # ✅ Cambiado a 'client'
            is_admin=is_admin,
            is_active=is_active,
            is_verified=is_verified
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        print(f"✅ Usuario creado: {new_user.email}")
        print(f"✅ Tipo de cuenta: {new_user.account_type}")
        print(f"✅ Activo: {new_user.is_active}")
        print(f"✅ Admin: {new_user.is_admin}")
        print(f"✅ Verificado: {new_user.is_verified}")
        
        if is_admin:
            session['user_id'] = new_user.id
            session['user_email'] = new_user.email
            session['user_role'] = 'admin'
            flash('¡Cuenta de administrador creada exitosamente!', 'success')
            return redirect(url_for('main.post_login'))
        else:
            flash('¡Cuenta creada exitosamente! Requiere activación por parte del administrador.', 'warning')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada exitosamente', 'info')
    return redirect(url_for('auth.login'))