from flask import Blueprint, render_template, request, jsonify, session, redirect, flash
from datetime import datetime
import json
from app import db 
from app.Services.stripe_service import StripePaymentService
from app.Services.mercadopago_service import MercadoPagoService
from app.models.product import Product
from app.models.favorite import Favorite
from app.models.cart import Cart, CartItem
from app.models.user import User
from app.models.product_utils import ProductUtils
from app.models.api_client import APIClient
from app.models.image_handler import ImageHandler

# Crear Blueprint para rutas de público general
public_bp = Blueprint('public', __name__, url_prefix='')

def get_current_user_id():
    """Obtener ID del usuario actual de la sesión"""
    return session.get('user_id', 'anonymous_user')

def get_product_image(product_data):
    """Obtener imagen del producto de forma segura"""
    images = product_data.get('productImages', [])
    if images and isinstance(images, list) and len(images) > 0:
        return images[0]
    
    return "https://via.placeholder.com/300x300/cccccc/969696?text=Imagen+No+Disponible"

# ==================== FUNCIONES DE CARRITO MEJORADAS ====================
def get_user_cart(user_id):
    """Obtener carrito del usuario - VERSIÓN MEJORADA Y CORREGIDA"""
    try:
        cart = Cart.query.filter_by(user_id=user_id, status='active').first()
        if not cart:
            return []
        
        items_with_details = []
        for item in cart.items:
            product = item.product
            
            product_images = []
            if product.metadata_json:
                try:
                    metadata = json.loads(product.metadata_json)
                    product_images = metadata.get('productImages', [])
                except:
                    product_images = []
            
            product_data = {
                'ingramPartNumber': product.ingram_part_number,
                'description': product.description,
                'vendorName': product.vendor_name,
                'upc': product.upc or '',
                'category': product.category or '',
                'pricing': {
                    'customerPrice': product.base_price if product.base_price else 0
                },
                'productImages': product_images
            }
            
            base_price = product.base_price or 0
            unit_price = round(base_price * 1.15, 2)
            total_price = round(unit_price * item.quantity, 2)
            
            items_with_details.append({
                'product': product_data,
                'quantity': item.quantity,
                'unit_price': unit_price,
                'total_price': total_price,
                'formatted_unit_price': f"${unit_price:,.2f} MXN",
                'formatted_total_price': f"${total_price:,.2f} MXN",
                'added_date': item.created_at.isoformat() if item.created_at else 'Desconocida'
            })
        
        return items_with_details
        
    except Exception as e:
        return []

def add_to_cart(user_id, product_data, quantity=1):
    """Agregar producto al carrito - VERSIÓN MEJORADA"""
    try:
        if quantity < 1:
            quantity = 1
        if quantity > 999:
            quantity = 999
            
        cart = Cart.query.filter_by(user_id=user_id, status='active').first()
        if not cart:
            cart = Cart(user_id=user_id, status='active')
            db.session.add(cart)
            db.session.flush()
        
        product = Product.query.filter_by(ingram_part_number=product_data['ingramPartNumber']).first()
        if not product:
            base_price = product_data.get('pricing', {}).get('customerPrice', 0)
            
            product = Product(
                ingram_part_number=product_data['ingramPartNumber'],
                description=product_data.get('description', ''),
                vendor_name=product_data.get('vendorName', 'N/A'),
                upc=product_data.get('upc', ''),
                category=product_data.get('category', ''),
                base_price=base_price,
                metadata_json=json.dumps({
                    'productImages': product_data.get('productImages', []),
                    'availability': product_data.get('availability', {})
                })
            )
            db.session.add(product)
            db.session.flush()
        
        existing_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.calculate_total()
        else:
            unit_price = round(product.base_price * 1.15, 2) if product.base_price else 0
            new_item = CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=unit_price
            )
            new_item.calculate_total()
            db.session.add(new_item)
        
        cart.calculate_total()
        db.session.commit()
        return True
        
    except Exception as e:
        db.session.rollback()
        raise

# ==================== RUTAS DEL CARRITO ====================
@public_bp.route("/cart/add", methods=["POST"])
def add_to_cart_route():
    """Añadir producto al carrito"""
    try:
        if request.is_json:
            data = request.get_json()
            part_number = data.get('part_number')
            quantity = int(data.get('quantity', 1))
        else:
            part_number = request.form.get('part_number')
            quantity = int(request.form.get('quantity', 1))
        
        if not part_number or part_number == 'None':
            return jsonify({'success': False, 'error': 'Número de parte inválido'}), 400
        
        detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
        detalle_res = APIClient.make_request("GET", detail_url)
        
        if detalle_res.status_code != 200:
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        detalle = detalle_res.json()
        
        real_price = 0
        try:
            price_url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
            body = {"products": [{"ingramPartNumber": part_number}]}
            params = {
                "includeAvailability": "true",
                "includePricing": "true",
                "includeProductAttributes": "true"
            }
            
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
                                real_price = float(customer_price)
        except Exception:
            pass
        
        product_data = {
            'ingramPartNumber': part_number,
            'description': detalle.get('description', f"Producto {part_number}"),
            'pricing': {'customerPrice': real_price},
            'vendorName': detalle.get('vendorName', 'N/A'),
            'upc': detalle.get('upc', ''),
            'category': detalle.get('category', ''),
            'productImages': detalle.get('productImages', [])
        }
        
        user_id = get_current_user_id()
        
        try:
            add_to_cart(user_id, product_data, quantity)
            
            cart_count = len(get_user_cart(user_id))
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': f'Producto agregado al carrito (Cantidad: {quantity})',
                    'cart_count': cart_count
                })
            else:
                session['flash_message'] = "Producto agregado al carrito"
                return redirect('/cart')
                
        except Exception as e:
            if request.is_json:
                return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500
            else:
                session['flash_message'] = f"Error al agregar producto: {str(e)}"
                return redirect(request.referrer or '/catalog')
        
    except Exception as e:
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        else:
            session['flash_message'] = f"Error al agregar producto: {str(e)}"
            return redirect(request.referrer or '/catalog')

@public_bp.route('/cart', methods=["GET"])
def view_cart():
    """Ver carrito de compras"""
    try:
        user_id = get_current_user_id()
        cart_items = get_user_cart(user_id)
        
        total = 0
        items_with_totals = []
        
        for item in cart_items:
            total += item['total_price']
            items_with_totals.append(item)
        
        tax_rate = 0.16
        tax_amount = round(total * tax_rate, 2)
        total_with_tax = round(total + tax_amount, 2)
        
        flash_message = session.pop('flash_message', None)
        
        return render_template(
            "public/catalog/cart.html",
            items=items_with_totals,
            total=round(total, 2),
            tax_amount=tax_amount,
            total_with_tax=total_with_tax,
            formatted_total=f"${total:,.2f} MXN",
            formatted_tax_amount=f"${tax_amount:,.2f} MXN", 
            formatted_total_with_tax=f"${total_with_tax:,.2f} MXN",
            count=len(cart_items),
            flash_message=flash_message,
            get_image_url_enhanced=ImageHandler.get_image_url_enhanced,
            user_type='public'
        )
        
    except Exception as e:
        return render_template("errors/500.html", error=f"Error al cargar carrito: {str(e)}")

@public_bp.route('/cart/update', methods=['POST'])
def update_cart_item():
    """Actualizar cantidad de un producto en el carrito"""
    try:
        data = request.get_json()
        part_number = data.get('part_number')
        quantity = int(data.get('quantity', 1))
        
        if not part_number:
            return jsonify({'success': False, 'error': 'Part number requerido'}), 400
        
        if quantity < 1:
            quantity = 1
        if quantity > 999:
            quantity = 999
        
        user_id = get_current_user_id()
        
        cart = Cart.query.filter_by(user_id=user_id, status='active').first()
        if not cart:
            return jsonify({'success': False, 'error': 'Carrito no encontrado'}), 404
        
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        if not cart_item:
            return jsonify({'success': False, 'error': 'Producto no encontrado en el carrito'}), 404
        
        cart_item.quantity = quantity
        cart_item.calculate_total()
        
        cart.calculate_total()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Cantidad actualizada correctamente',
            'new_quantity': quantity,
            'item_total': float(cart_item.total_price)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@public_bp.route('/cart/remove', methods=['POST'])
def remove_cart_item():
    """Eliminar producto del carrito"""
    try:
        data = request.get_json()
        part_number = data.get('part_number')
        
        if not part_number:
            return jsonify({'success': False, 'error': 'Part number requerido'}), 400
        
        user_id = get_current_user_id()
        
        cart = Cart.query.filter_by(user_id=user_id, status='active').first()
        if not cart:
            return jsonify({'success': False, 'error': 'Carrito no encontrado'}), 404
        
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        if cart_item:
            db.session.delete(cart_item)
            
            cart.calculate_total()
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Producto eliminado del carrito'
            })
        else:
            return jsonify({'success': False, 'error': 'Producto no encontrado en el carrito'}), 404
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS ADICIONALES DEL CARRITO ====================
@public_bp.route("/cart/count", methods=["GET"])
def api_get_cart_count():
    """API para obtener cantidad de items en carrito"""
    try:
        user_id = get_current_user_id()
        cart_items = get_user_cart(user_id)
        
        return jsonify({
            'success': True,
            'count': len(cart_items)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'count': 0
        }), 500

# ==================== RUTAS DE PERFIL ====================
@public_bp.route('/profile', methods=['GET'])
def public_profile():
    """Página para EDITAR perfil del usuario público"""
    try:
        user_id = get_current_user_id()
        
        if user_id == 'anonymous_user':
            flash('Por favor inicia sesión para editar tu perfil', 'warning')
            return redirect('/login')
        
        user = User.query.get(user_id)
        if not user:
            flash('Usuario no encontrado', 'error')
            return redirect('/')
        
        favorites_count = get_favorites_count(user_id)
        cart_stats = get_cart_stats(user_id)
        
        profile_data = {
            'user_id': user_id,
            'user_name': user.full_name or user.email.split('@')[0],
            'user_email': user.email,
            'account_type': user.account_type,
            'business_name': user.business_name or 'No especificado',
            'rfc': user.rfc or 'No especificado',
            'favorites_count': favorites_count,
            'cart_count': cart_stats['total_items'],
            'member_since': user.created_at.strftime('%d/%m/%Y') if user.created_at else 'Reciente',
            'last_login': user.last_login.strftime('%d/%m/%Y %H:%M') if hasattr(user, 'last_login') and user.last_login else user.created_at.strftime('%d/%m/%Y %H:%M') if user.created_at else 'Nunca',
            'is_verified': user.is_verified
        }
        
        return render_template('public/catalog/profile.html', **profile_data)
        
    except Exception as e:
        flash('Error al cargar el perfil', 'error')
        return redirect('public/public_dashboard.html')
    
@public_bp.route('/profile/update', methods=['POST'])
def update_profile():
    """Actualizar información del perfil"""
    try:
        user_id = get_current_user_id()
        
        if user_id == 'anonymous_user':
            flash('Usuario no autenticado', 'error')
            return redirect('/auth/login')
        
        full_name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        
        if not full_name:
            flash('El nombre completo es requerido', 'error')
            return redirect('/profile')
        
        if not email:
            flash('El correo electrónico es requerido', 'error')
            return redirect('/profile')
        
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash('El formato del correo electrónico no es válido', 'error')
            return redirect('/profile')
        
        user = User.query.get(user_id)
        if not user:
            flash('Usuario no encontrado', 'error')
            return redirect('/profile')
        
        existing_user = User.query.filter(User.email == email, User.id != user_id).first()
        if existing_user:
            flash('Este correo electrónico ya está en uso', 'error')
            return redirect('/profile')
        
        user.full_name = full_name
        user.email = email
        
        db.session.commit()
        
        session['user_email'] = email
        session['username'] = full_name
        
        flash('Perfil actualizado correctamente', 'success')
        return redirect('/dashboard/public')
        
    except Exception as e:
        db.session.rollback()
        flash('Error al actualizar el perfil', 'error')
        return redirect('/profile')

@public_bp.route('/profile/password', methods=['POST'])
def update_password():
    """Actualizar contraseña del usuario"""
    try:
        user_id = get_current_user_id()
        
        if user_id == 'anonymous_user':
            return jsonify({'success': False, 'error': 'Usuario no autenticado'}), 401
        
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not current_password or not new_password or not confirm_password:
            return jsonify({'success': False, 'error': 'Todos los campos son requeridos'}), 400
        
        if new_password != confirm_password:
            return jsonify({'success': False, 'error': 'Las contraseñas nuevas no coinciden'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
        
        if not user.check_password(current_password):
            return jsonify({'success': False, 'error': 'La contraseña actual es incorrecta'}), 400
        
        user.set_password(new_password)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Contraseña actualizada correctamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Error al actualizar contraseña: {str(e)}'}), 500

@public_bp.route('/profile/stats', methods=['GET'])
def get_profile_stats():
    """API para obtener estadísticas del perfil (para actualizar en tiempo real)"""
    try:
        user_id = get_current_user_id()
        
        if user_id == 'anonymous_user':
            return jsonify({'success': False, 'error': 'Usuario no autenticado'}), 401
        
        favorites_count = get_favorites_count(user_id)
        cart_stats = get_cart_stats(user_id)
        
        return jsonify({
            'success': True,
            'favorites_count': favorites_count,
            'cart_count': cart_stats['total_items'],
            'cart_value': cart_stats['total_value']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS DEL CATÁLOGO ====================
@public_bp.route("/catalog", methods=["GET"])
@public_bp.route("/tienda", methods=["GET"])
def public_catalog():
    """Catálogo para público general"""
    page_number = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 25))
    query = request.args.get("q", "").strip()
    vendor = request.args.get("vendor", "").strip()
    
    try:
        productos, total_records, pagina_vacia = ProductUtils.buscar_productos_hibrido(
            query=query, 
            vendor=vendor, 
            page_number=page_number, 
            page_size=page_size, 
            use_keywords=bool(query)
        )
        
        total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
        page_number = max(1, min(page_number, total_pages))
        start_record = (page_number - 1) * page_size + 1 if total_records > 0 else 0
        end_record = min(page_number * page_size, total_records)
        
        user_id = get_current_user_id()
        if user_id != 'anonymous_user':
            user = User.query.get(user_id)
            if user and user.account_type == 'client' and user.is_verified:
                redirect_url = f'/client/catalog?page={page_number}'
                if query:
                    redirect_url += f'&q={query}'
                if vendor:
                    redirect_url += f'&vendor={vendor}'
                return redirect(redirect_url)
        
        return render_template(
            "public/catalog/catalog.html",
            productos=productos,
            page_number=page_number,
            total_records=total_records,
            total_pages=total_pages,
            start_record=start_record,
            end_record=end_record,
            query=query,
            vendor=vendor,
            selected_vendor=vendor,
            pagina_vacia=pagina_vacia,
            welcome_message=(page_number == 1 and not query and not vendor and not productos),
            local_vendors=ProductUtils.get_local_vendors(),
            get_image_url_enhanced=ImageHandler.get_image_url_enhanced,
            get_availability_text=ProductUtils.get_availability_text,
            user_type='public'
        )
    
    except Exception as e:
        return render_template("public/catalog/catalog.html", 
                             query=query,
                             vendor=vendor,
                             page_number=1,
                             total_pages=1,
                             total_records=0,
                             start_record=0,
                             end_record=0,
                             productos=[],
                             local_vendors=ProductUtils.get_local_vendors(),
                             pagina_vacia=True,
                             welcome_message=False,
                             error_message=f"Error al cargar productos: {str(e)}",
                             user_type='public')

@public_bp.route("/product/<part_number>", methods=["GET"])
def public_product_detail(part_number):
    """Detalle de producto para público general"""
    try:
        detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
        detalle_res = APIClient.make_request("GET", detail_url)
        
        if detalle_res.status_code != 200:
            return render_template("errors/404.html", message=f"Producto {part_number} no encontrado"), 404
        
        detalle = detalle_res.json()

        price_url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
        body = {"products": [{"ingramPartNumber": part_number}]}
        params = {
            "includeAvailability": "true",
            "includePricing": "true",
            "includeProductAttributes": "true"
        }
        precio_res = APIClient.make_request("POST", price_url, params=params, json=body)
        precio_info = precio_res.json()[0] if precio_res.status_code == 200 else {}

        pricing = precio_info.get("pricing") or {}
        base_price = pricing.get("customerPrice")
        currency = pricing.get("currencyCode") or pricing.get("currency") or ""
        precio_final_val = None
        if base_price is not None:
            try:
                precio_final_val = round(float(base_price) * 1.15, 2)
            except Exception:
                precio_final_val = None
        precio_final = ProductUtils.format_currency(precio_final_val, currency) if precio_final_val is not None else "No disponible"

        disponibilidad = ProductUtils.get_availability_text(precio_info, detalle)

        atributos = []
        raw_attrs = detalle.get("productAttributes") or detalle.get("attributes") or []
        for a in raw_attrs:
            name = a.get("name") or a.get("attributeName") or a.get("key") or None
            value = a.get("value") or a.get("attributeValue") or a.get("val") or ""
            if name:
                atributos.append({"name": name, "value": value})

        imagen_url = ImageHandler.get_image_url_enhanced(detalle)
        
        return render_template(
            "public/catalog/product_detail.html",
            detalle=detalle,
            precio_final=precio_final,
            disponibilidad=disponibilidad,
            atributos=atributos,
            imagen_url=imagen_url,
            part_number=part_number,
            user_type='public'
        )
    
    except Exception as e:
        return render_template("errors/500.html", message="Error al cargar el detalle del producto"), 500

# ==================== RUTAS DE FAVORITOS ====================
@public_bp.route('/favorites', methods=["GET"])
def public_favorites():
    """Favoritos para público general"""
    try:
        user_id = get_current_user_id()
        favorites = get_user_favorites(user_id)
        
        flash_message = session.pop('flash_message', None)
        
        return render_template(
            "public/catalog/favorites.html",
            favorites=favorites,
            count=len(favorites),
            flash_message=flash_message,
            get_image_url_enhanced=ImageHandler.get_image_url_enhanced,
            user_type='public'
        )
        
    except Exception as e:
        return render_template("errors/500.html", error=f"Error al cargar favoritos: {str(e)}")

@public_bp.route('/favorites/toggle', methods=['POST'])
def toggle_favorite_route():
    """Agregar/eliminar favorito - VERSIÓN CORREGIDA para form data"""
    try:
        if request.is_json:
            data = request.get_json()
            part_number = data.get('part_number')
        else:
            part_number = request.form.get('part_number')
        
        if not part_number:
            return jsonify({'success': False, 'error': 'Part number requerido'}), 400
        
        user_id = get_current_user_id()
        
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            product = Product(
                ingram_part_number=part_number,
                description=request.form.get('description', 'Producto sin descripción'),
                vendor_name=request.form.get('vendor', 'N/A')
            )
            db.session.add(product)
            db.session.flush()
        
        favorite = Favorite.query.filter_by(user_id=user_id, product_id=product.id).first()
        
        if favorite:
            db.session.delete(favorite)
            action = 'removed'
            message = 'Producto eliminado de favoritos'
        else:
            new_favorite = Favorite(user_id=user_id, product_id=product.id)
            db.session.add(new_favorite)
            action = 'added'
            message = 'Producto agregado a favoritos'
        
        db.session.commit()
        
        flash(message, 'success')
        return redirect('/favorites')
        
    except Exception as e:
        db.session.rollback()
        flash('Error al actualizar favoritos', 'error')
        return redirect('/favorites')

@public_bp.route('/favorites/check/<part_number>', methods=['GET'])
def check_favorite_route(part_number):
    """API para verificar si un producto es favorito"""
    try:
        user_id = get_current_user_id()
        
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            return jsonify({'success': True, 'is_favorite': False})
        
        favorite = Favorite.query.filter_by(user_id=user_id, product_id=product.id).first()
        
        return jsonify({
            'success': True,
            'is_favorite': favorite is not None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== FUNCIONES AUXILIARES ====================
def get_user_favorites(user_id):
    """Obtener favoritos del usuario"""
    from app.models.favorite import Favorite
    from app.models.product import Product
    
    favorites = Favorite.query.filter_by(user_id=user_id).all()
    
    favorite_list = []
    for fav in favorites:
        product = fav.product
        favorite_list.append({
            'ingramPartNumber': product.ingram_part_number,
            'description': product.description,
            'vendorName': product.vendor_name,
            'favorited_date': fav.created_at.isoformat() if fav.created_at else 'Desconocida'
        })
    
    return favorite_list

def toggle_favorite(user_id, product_data):
    """Agregar/eliminar favorito"""
    from app.models.favorite import Favorite
    from app.models.product import Product
    
    product = Product.query.filter_by(ingram_part_number=product_data['ingramPartNumber']).first()
    if not product:
        product = Product(
            ingram_part_number=product_data['ingramPartNumber'],
            description=product_data.get('description', ''),
            vendor_name=product_data.get('vendorName', 'N/A')
        )
        db.session.add(product)
        db.session.flush()
    
    existing_fav = Favorite.query.filter_by(user_id=user_id, product_id=product.id).first()
    
    if existing_fav:
        db.session.delete(existing_fav)
        action = 'removed'
    else:
        new_fav = Favorite(user_id=user_id, product_id=product.id)
        db.session.add(new_fav)
        action = 'added'
    
    db.session.commit()
    return action

def get_cart_stats(user_id):
    """Obtener estadísticas REALES del carrito desde la BD"""
    try:
        cart_items = get_user_cart(user_id)
        
        if not cart_items:
            return {
                'total_items': 0,
                'total_value': 0.0,
                'last_update': 'Nunca',
                'item_count': 0
            }
        
        total_items = sum(item['quantity'] for item in cart_items)
        total_value = 0.0
        
        for item in cart_items:
            total_value += item['total_price']
        
        last_update = "Reciente"
        cart = Cart.query.filter_by(user_id=user_id, status='active').first()
        if cart and cart.updated_at:
            last_update = cart.updated_at.strftime("%d/%m/%Y %H:%M")
        
        return {
            'total_items': total_items,
            'total_value': round(total_value, 2),
            'last_update': last_update,
            'item_count': len(cart_items)
        }
        
    except Exception as e:
        return {
            'total_items': 0,
            'total_value': 0.0,
            'last_update': 'Error',
            'item_count': 0
        }

def get_favorites_count(user_id):
    """Obtener cantidad REAL de favoritos desde la BD"""
    try:
        from app.models.favorite import Favorite
        count = Favorite.query.filter_by(user_id=user_id).count()
        return count
    except Exception as e:
        return 0

def get_recent_activity(user_id):
    """Obtener actividad reciente del usuario"""
    try:
        return [
            {'action': 'Producto agregado al carrito', 'date': 'Hoy', 'icon': 'fas fa-cart-plus'},
            {'action': 'Producto visto', 'date': 'Hoy', 'icon': 'fas fa-eye'},
            {'action': 'Búsqueda realizada', 'date': 'Ayer', 'icon': 'fas fa-search'}
        ]
    except Exception as e:
        return []

# ==================== RUTAS DE COMPATIBILIDAD ====================
@public_bp.route('/api/cart/remove', methods=['POST'])
def api_remove_from_cart():
    """API para eliminar producto del carrito (compatibilidad)"""
    try:
        data = request.get_json()
        part_number = data.get('part_number')
        
        if not part_number:
            return jsonify({'success': False, 'error': 'part_number requerido'}), 400
        
        user_id = get_current_user_id()
        result = remove_from_cart_legacy(user_id, part_number)
        
        if result:
            return jsonify({
                'success': True, 
                'message': 'Producto eliminado del carrito',
                'cart_count': len(get_user_cart(user_id))
            })
        else:
            return jsonify({'success': False, 'error': 'Producto no encontrado en carrito'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def remove_from_cart_legacy(user_id, part_number):
    """Eliminar producto del carrito (función legacy)"""
    try:
        cart = Cart.query.filter_by(user_id=user_id, status='active').first()
        if not cart:
            return False
        
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            return False
        
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        if not item:
            return False
        
        db.session.delete(item)
        cart.calculate_total()
        db.session.commit()
        return True
        
    except Exception as e:
        db.session.rollback()
        return False

# ==================== RUTAS DE PAGO CON STRIPE (SIMPLIFICADO) ====================
@public_bp.route('/payment/stripe-checkout', methods=['POST'])
def stripe_checkout():
    """Crear link de pago con Stripe - VERSIÓN SIMPLIFICADA"""
    try:
        user_id = get_current_user_id()
        
        if user_id == 'anonymous_user':
            return jsonify({'success': False, 'error': 'Debes iniciar sesión para realizar una compra'}), 401
        
        cart_items = get_user_cart(user_id)
        if not cart_items:
            return jsonify({'success': False, 'error': 'El carrito está vacío'}), 400
        
        subtotal = sum(item['total_price'] for item in cart_items)
        tax_amount = round(subtotal * 0.16, 2)
        total_amount = round(subtotal + tax_amount, 2)
        
        order_number = f"ITD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        cart_data = {
            'order_number': order_number,
            'items': cart_items,
            'subtotal': subtotal,
            'tax_amount': tax_amount,
            'total_amount': total_amount
        }
        
        base_url = request.url_root.rstrip('/')
        success_url = f"{base_url}/payment/success?order={order_number}"
        cancel_url = f"{base_url}/cart"
        
        stripe_service = StripePaymentService()
        result = stripe_service.create_payment_link(
            cart_data=cart_data,
            user_email=session.get('user_email', ''),
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        if result['success']:
            session['pending_order'] = {
                'order_number': order_number,
                'payment_id': result['payment_id'],
                'cart_data': cart_data,
                'user_id': user_id
            }
            
            return jsonify({
                'success': True,
                'payment_url': result['payment_url'],
                'order_number': order_number
            })
        else:
            return jsonify({'success': False, 'error': result['error']}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@public_bp.route('/payment/success')
def payment_success():
    """Página de éxito después del pago - VERSIÓN SIMPLIFICADA"""
    try:
        order_number = request.args.get('order')
        
        pending_order = session.get('pending_order')
        
        if not pending_order or pending_order['order_number'] != order_number:
            flash('Redirigiendo... procesando tu pago', 'info')
            return redirect('/dashboard/public')
        
        user_id = pending_order['user_id']
        cart_data = pending_order['cart_data']
        
        purchase = process_successful_purchase(
            user_id=user_id,
            cart_data=cart_data,
            payment_info={
                'payment_id': pending_order['payment_id'],
                'payment_method': 'stripe', 
                'status': 'paid'
            }
        )
        
        clear_user_cart(user_id)
        
        session.pop('pending_order', None)
        
        return render_template(
            'public/payment/success.html',
            purchase=purchase,
            payment_info={
                'payment_id': pending_order['payment_id'],
                'order_number': purchase.order_number,
                'amount': purchase.total_amount
            }
        )
            
    except Exception as e:
        flash('Pago procesado. Revisa tu dashboard.', 'success')
        return redirect('/dashboard/public')

def process_successful_purchase(user_id, cart_data, payment_info):
    """Procesar una compra exitosa - VERSIÓN SIMPLIFICADA"""
    try:
        from app.models.purchase import Purchase, PurchaseItem
        
        purchase = Purchase(
            user_id=user_id,
            order_number=cart_data['order_number'],
            status='paid',
            subtotal_amount=cart_data['subtotal'],
            tax_amount=cart_data['tax_amount'],
            shipping_amount=0.0,
            total_amount=cart_data['total_amount'],
            payment_method='stripe',
            payment_reference=payment_info['payment_id'],
            payer_email=session.get('user_email', ''),
            payer_name=session.get('user_name', 'Cliente')
        )
        db.session.add(purchase)
        db.session.flush()
        
        for item in cart_data['items']:
            product = Product.query.filter_by(ingram_part_number=item['product']['ingramPartNumber']).first()
            
            purchase_item = PurchaseItem(
                purchase_id=purchase.id,
                product_id=product.id if product else None,
                product_sku=item['product']['ingramPartNumber'],
                product_name=item['product']['description'][:100],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                total_price=item['total_price']
            )
            db.session.add(purchase_item)
        
        db.session.commit()
        
        return purchase
        
    except Exception as e:
        db.session.rollback()
        class SimplePurchase:
            def __init__(self, order_number, total_amount):
                self.order_number = order_number
                self.total_amount = total_amount
                
        return SimplePurchase(cart_data['order_number'], cart_data['total_amount'])

def clear_user_cart(user_id):
    """Limpiar carrito del usuario - VERSIÓN SIMPLIFICADA"""
    try:
        cart = Cart.query.filter_by(user_id=user_id, status='active').first()
        if cart:
            CartItem.query.filter_by(cart_id=cart.id).delete()
            cart.total_amount = 0.0
            db.session.commit()
    except Exception as e:
        db.session.rollback()

@public_bp.route('/payment/mercadopago-checkout', methods=['POST'])
def mercadopago_checkout():
    """Crear preferencia de pago con MercadoPago - VERSIÓN MEJORADA"""
    try:
        user_id = get_current_user_id()
        
        if user_id == 'anonymous_user':
            return jsonify({'success': False, 'error': 'Debes iniciar sesión'}), 401
        
        cart_items = get_user_cart(user_id)
        if not cart_items:
            return jsonify({'success': False, 'error': 'Carrito vacío'}), 400
        
        subtotal = sum(item['total_price'] for item in cart_items)
        tax_amount = round(subtotal * 0.16, 2)
        total_amount = round(subtotal + tax_amount, 2)
        
        order_number = f"ITD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        cart_data = {
            'order_number': order_number,
            'items': cart_items,
            'subtotal': subtotal,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            'tax_rate': 0.16
        }
        
        base_url = request.url_root.rstrip('/')
        success_url = f"{base_url}/payment/mercadopago/success"
        failure_url = f"{base_url}/payment/mercadopago/failure" 
        pending_url = f"{base_url}/payment/mercadopago/pending"
        
        user_email = session.get('user_email', 'cliente@itdataglobal.com')
        user_name = session.get('user_name', 'Cliente')
        
        mp_service = MercadoPagoService()
        result = mp_service.create_preference(
            cart_data=cart_data,
            user_email=user_email,
            user_name=user_name,
            success_url=success_url,
            failure_url=failure_url,
            pending_url=pending_url
        )
        
        if result['success']:
            session['pending_mp_order'] = {
                'order_number': order_number,
                'preference_id': result['preference_id'],
                'cart_data': cart_data,
                'user_id': user_id
            }
            
            return jsonify({
                'success': True,
                'init_point': result['init_point'],
                'preference_id': result['preference_id'],
                'order_number': order_number,
                'amounts': result.get('amounts', {
                    'subtotal': subtotal,
                    'tax_amount': tax_amount, 
                    'total_amount': total_amount
                })
            })
        else:
            return jsonify({'success': False, 'error': result['error']}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500
    
@public_bp.route('/payment/mercadopago/success')
def mercadopago_success():
    """Página de éxito después del pago con MercadoPago"""
    try:
        payment_id = request.args.get('payment_id')
        status = request.args.get('status')
        external_reference = request.args.get('external_reference')
        
        flash('¡Pago realizado exitosamente!', 'success')
        return redirect('/dashboard/public')
        
    except Exception as e:
        flash('Pago procesado correctamente', 'success')
        return redirect('/dashboard/public')

@public_bp.route('/payment/mercadopago/failure')
def mercadopago_failure():
    """Página de fallo en el pago con MercadoPago"""
    flash('El pago fue cancelado o falló. Puedes intentar nuevamente.', 'error')
    return redirect('/cart')

@public_bp.route('/payment/mercadopago/pending')
def mercadopago_pending():
    """Página de pago pendiente con MercadoPago"""
    flash('Tu pago está pendiente de confirmación. Te notificaremos cuando sea procesado.', 'warning')
    return redirect('/dashboard/public')

@public_bp.route('/payment/mercadopago/notifications', methods=['POST'])
def mercadopago_notifications():
    """Manejar notificaciones de MercadoPago"""
    try:
        data = request.json
        
        if data.get('type') == 'payment':
            payment_id = data.get('data', {}).get('id')
            
        return jsonify({'success': True}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTA DE ACTIVIDAD ====================
@public_bp.route('/activity', methods=['GET'])
def activity():
    """Página de actividad del usuario"""
    try:
        user_id = get_current_user_id()
        
        if user_id == 'anonymous_user':
            flash('Por favor inicia sesión para ver tu actividad', 'warning')
            return redirect('/login')
        
        from app.models.quote import Quote
        
        total_quotes = Quote.query.filter_by(user_id=user_id).count()
        pending_quotes = Quote.query.filter_by(user_id=user_id, status='pending').count()
        approved_quotes = Quote.query.filter_by(user_id=user_id, status='approved').count()
        
        from datetime import datetime
        current_month = datetime.now().month
        current_year = datetime.now().year
        month_quotes = Quote.query.filter(
            Quote.user_id == user_id,
            db.extract('month', Quote.created_at) == current_month,
            db.extract('year', Quote.created_at) == current_year
        ).count()
        
        recent_activities = Quote.query.filter_by(user_id=user_id)\
            .order_by(Quote.created_at.desc())\
            .limit(10)\
            .all()
        
        activities = []
        for quote in recent_activities:
            activity_data = {
                'type': 'quote',
                'title': f'Cotización #{quote.quote_number}',
                'description': f'Cotización creada para {quote.customer_name}' if hasattr(quote, 'customer_name') else 'Cotización creada',
                'created_at': quote.created_at,
                'quote_number': quote.quote_number,
                'status': quote.status,
                'amount': float(quote.total_amount) if quote.total_amount else 0.0,
                'quote_id': quote.id
            }
            activities.append(activity_data)
        
        if len(activities) < 5:
            cart_activities = get_recent_cart_activity(user_id)
            activities.extend(cart_activities)
        
        activities.sort(key=lambda x: x['created_at'], reverse=True)
        
        return render_template(
            "public/catalog/activity.html",
            total_quotes=total_quotes,
            pending_quotes=pending_quotes,
            approved_quotes=approved_quotes,
            month_quotes=month_quotes,
            activities=activities[:10],
            user=session
        )
        
    except Exception as e:
        flash('Error al cargar la actividad', 'error')
        return redirect('/dashboard/public')

def get_recent_cart_activity(user_id):
    """Obtener actividad reciente del carrito"""
    try:
        from app.models.cart import Cart, CartItem
        from app.models.product import Product
        from datetime import datetime, timedelta
        
        recent_carts = Cart.query.filter(
            Cart.user_id == user_id,
            Cart.created_at >= datetime.now() - timedelta(days=30)
        ).order_by(Cart.created_at.desc()).limit(5).all()
        
        cart_activities = []
        for cart in recent_carts:
            items = CartItem.query.filter_by(cart_id=cart.id).all()
            if items:
                product_count = len(items)
                total_value = sum(item.total_price for item in items if item.total_price)
                
                activity_data = {
                    'type': 'order',
                    'title': f'Carrito actualizado',
                    'description': f'{product_count} productos en carrito - Total: ${total_value:,.2f} MXN',
                    'created_at': cart.updated_at or cart.created_at,
                    'status': 'pending',
                    'amount': float(total_value) if total_value else 0.0
                }
                cart_activities.append(activity_data)
        
        return cart_activities
        
    except Exception as e:
        return []