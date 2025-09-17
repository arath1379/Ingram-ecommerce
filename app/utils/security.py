# app/utils/security.py - VERSIÓN CORRECTA
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

def hash_password(password):
    """Hash a password for storing."""
    return generate_password_hash(password, method='pbkdf2:sha256')

def check_password(hashed_password, password):
    """Check hashed password."""
    return check_password_hash(hashed_password, password)

def generate_verification_token(email):
    """Generate email verification token."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-verification')

def verify_verification_token(token, expiration=3600):
    """Verify email verification token."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='email-verification', max_age=expiration)
        return email
    except:
        return None

def generate_password_reset_token(email):
    """Generate password reset token."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset')

def verify_password_reset_token(token, expiration=3600):
    """Verify password reset token."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset', max_age=expiration)
        return email
    except:
        return None