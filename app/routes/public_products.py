from flask import Blueprint, render_template, request, jsonify, session, redirect, flash
from datetime import datetime
import json
from app import db 
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
    
    # Usar un servicio de placeholder online
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
            
            # Manejar imágenes de forma segura
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
            
            # Calcular precios con markup del 15%
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
        
        print(f"DEBUG - Carrito obtenido: {len(items_with_details)} items")
        return items_with_details
        
    except Exception as e:
        print(f"Error en get_user_cart: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def add_to_cart(user_id, product_data, quantity=1):
    """Agregar producto al carrito - VERSIÓN MEJORADA"""
    try:
        print(f"DEBUG - add_to_cart iniciado para: {product_data['ingramPartNumber']}")
        
        # Validar cantidad
        if quantity < 1:
            quantity = 1
        if quantity > 999:
            quantity = 999
            
        # Obtener o crear carrito
        cart = Cart.query.filter_by(user_id=user_id, status='active').first()
        if not cart:
            cart = Cart(user_id=user_id, status='active')
            db.session.add(cart)
            db.session.flush()
            print(f"DEBUG - Nuevo carrito creado: {cart.id}")
        
        # Buscar o crear producto
        product = Product.query.filter_by(ingram_part_number=product_data['ingramPartNumber']).first()
        if not product:
            base_price = product_data.get('pricing', {}).get('customerPrice', 0)
            print(f"DEBUG - Creando nuevo producto, precio base: {base_price}")
            
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
            print(f"DEBUG - Nuevo producto creado: {product.ingram_part_number}")
        
        # Buscar item existente en el carrito
        existing_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.calculate_total()
            print(f"DEBUG - Item existente actualizado, cantidad: {existing_item.quantity}")
        else:
            # Calcular precio unitario con markup del 15%
            unit_price = round(product.base_price * 1.15, 2) if product.base_price else 0
            new_item = CartItem(
                cart_id=cart.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=unit_price
            )
            new_item.calculate_total()
            db.session.add(new_item)
            print(f"DEBUG - Nuevo item creado, precio: {unit_price}, cantidad: {quantity}")
        
        # Recalcular total del carrito
        cart.calculate_total()
        db.session.commit()
        print(f"DEBUG - Carrito guardado exitosamente, total: {cart.total_amount}")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"ERROR en add_to_cart: {e}")
        import traceback
        traceback.print_exc()
        raise

# ==================== RUTAS DEL CARRITO ====================
@public_bp.route("/cart/add", methods=["POST"])
def add_to_cart_route():
    """Añadir producto al carrito"""
    try:
        # Obtener datos de la solicitud
        if request.is_json:
            data = request.get_json()
            part_number = data.get('part_number')
            quantity = int(data.get('quantity', 1))
        else:
            part_number = request.form.get('part_number')
            quantity = int(request.form.get('quantity', 1))
        
        # Validar part_number
        if not part_number or part_number == 'None':
            print(f"ERROR - part_number inválido: {part_number}")
            return jsonify({'success': False, 'error': 'Número de parte inválido'}), 400
        
        print(f"DEBUG - Agregando al carrito: {part_number}, cantidad: {quantity}")
        
        # Obtener detalles del producto
        detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
        detalle_res = APIClient.make_request("GET", detail_url)
        
        if detalle_res.status_code != 200:
            print(f"ERROR - Producto no encontrado: {part_number}")
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        detalle = detalle_res.json()
        
        # Obtener precio
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
        except Exception as api_error:
            print(f"DEBUG - Excepción en API de precios: {api_error}")
        
        # Preparar datos del producto
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
        
        # Intentar agregar al carrito
        try:
            add_to_cart(user_id, product_data, quantity)
            
            cart_count = len(get_user_cart(user_id))
            print(f"DEBUG - Producto agregado exitosamente. Carrito tiene {cart_count} items")
            
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
            print(f"ERROR al agregar al carrito: {str(e)}")
            if request.is_json:
                return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500
            else:
                session['flash_message'] = f"Error al agregar producto: {str(e)}"
                return redirect(request.referrer or '/catalog')
        
    except Exception as e:
        print(f"ERROR en add_to_cart_route: {str(e)}")
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
        
        flash_message = session.pop('flash_message', None)
        
        return render_template(
            "public/catalog/cart.html",
            items=items_with_totals,
            total=round(total, 2),
            formatted_total=f"${total:,.2f} MXN",
            count=len(cart_items),
            flash_message=flash_message,
            get_product_image=get_product_image,
            user_type='public'
        )
        
    except Exception as e:
        print(f"Error al cargar carrito: {str(e)}")
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
        
        # Buscar el carrito activo del usuario
        cart = Cart.query.filter_by(user_id=user_id, status='active').first()
        if not cart:
            return jsonify({'success': False, 'error': 'Carrito no encontrado'}), 404
        
        # Buscar el producto
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        # Buscar el item en el carrito
        cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        if not cart_item:
            return jsonify({'success': False, 'error': 'Producto no encontrado en el carrito'}), 404
        
        # Actualizar cantidad
        cart_item.quantity = quantity
        cart_item.calculate_total()
        
        # Recalcular total del carrito
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
        print(f"ERROR en update_cart_item: {str(e)}")
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
        
        # Buscar el carrito activo del usuario
        cart = Cart.query.filter_by(user_id=user_id, status='active').first()
        if not cart:
            return jsonify({'success': False, 'error': 'Carrito no encontrado'}), 404
        
        # Buscar el producto
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        # Buscar y eliminar el item del carrito
        cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
        if cart_item:
            db.session.delete(cart_item)
            
            # Recalcular total del carrito
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
        print(f"ERROR en remove_cart_item: {str(e)}")
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

# ==================== RUTAS DEL CATÁLOGO ====================
@public_bp.route("/catalog", methods=["GET"])
@public_bp.route("/tienda", methods=["GET"])
def public_catalog():
    """Catálogo para público general"""
    # Parámetros de búsqueda
    page_number = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 25))
    query = request.args.get("q", "").strip()
    vendor = request.args.get("vendor", "").strip()
    
    # DEBUG: Log de parámetros
    print(f"DEBUG - Catálogo Público - Page: {page_number}, Query: '{query}', Vendor: '{vendor}'")
    
    try:
        # Realizar la búsqueda (misma lógica que clientes)
        productos, total_records, pagina_vacia = ProductUtils.buscar_productos_hibrido(
            query=query, 
            vendor=vendor, 
            page_number=page_number, 
            page_size=page_size, 
            use_keywords=bool(query)
        )
        
        # Cálculos de paginación
        total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
        page_number = max(1, min(page_number, total_pages))
        start_record = (page_number - 1) * page_size + 1 if total_records > 0 else 0
        end_record = min(page_number * page_size, total_records)
        
        # Verificar si el usuario es cliente y redirigir si es necesario
        user_id = get_current_user_id()
        if user_id != 'anonymous_user':
            user = User.query.get(user_id)
            if user and user.account_type == 'client' and user.is_verified:
                # Redirigir al catálogo de clientes
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
        print(f"ERROR en catálogo público: {str(e)}")
        import traceback
        traceback.print_exc()
        
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
        # Detalle del producto (misma lógica que clientes)
        detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
        detalle_res = APIClient.make_request("GET", detail_url)
        
        if detalle_res.status_code != 200:
            return render_template("errors/404.html", message=f"Producto {part_number} no encontrado"), 404
        
        detalle = detalle_res.json()

        # Precio y disponibilidad
        price_url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
        body = {"products": [{"ingramPartNumber": part_number}]}
        params = {
            "includeAvailability": "true",
            "includePricing": "true",
            "includeProductAttributes": "true"
        }
        precio_res = APIClient.make_request("POST", price_url, params=params, json=body)
        precio_info = precio_res.json()[0] if precio_res.status_code == 200 else {}

        # Calcular precio final con markup del 15% (precio público)
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

        # Disponibilidad
        disponibilidad = ProductUtils.get_availability_text(precio_info, detalle)

        # Extraer atributos
        atributos = []
        raw_attrs = detalle.get("productAttributes") or detalle.get("attributes") or []
        for a in raw_attrs:
            name = a.get("name") or a.get("attributeName") or a.get("key") or None
            value = a.get("value") or a.get("attributeValue") or a.get("val") or ""
            if name:
                atributos.append({"name": name, "value": value})

        # Imagen mejorada
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
        print(f"Error obteniendo detalle del producto {part_number}: {str(e)}")
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
        print(f"Error al cargar favoritos: {str(e)}")
        return render_template("errors/500.html", error=f"Error al cargar favoritos: {str(e)}")

@public_bp.route('/favorites/toggle', methods=['POST'])
def toggle_favorite_route():
    """Agregar/eliminar favorito - VERSIÓN CORREGIDA para form data"""
    try:
        # Determinar si es JSON o form data
        if request.is_json:
            data = request.get_json()
            part_number = data.get('part_number')
        else:
            # Para form data tradicional
            part_number = request.form.get('part_number')
        
        if not part_number:
            return jsonify({'success': False, 'error': 'Part number requerido'}), 400
        
        print(f"DEBUG - Eliminando favorito: {part_number}")
        
        user_id = get_current_user_id()
        
        # Buscar producto en la base de datos local
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            # Si no existe en la BD, crear un producto básico
            product = Product(
                ingram_part_number=part_number,
                description=request.form.get('description', 'Producto sin descripción'),
                vendor_name=request.form.get('vendor', 'N/A')
            )
            db.session.add(product)
            db.session.flush()
        
        # Buscar el favorito
        favorite = Favorite.query.filter_by(user_id=user_id, product_id=product.id).first()
        
        if favorite:
            # Eliminar favorito
            db.session.delete(favorite)
            action = 'removed'
            message = 'Producto eliminado de favoritos'
        else:
            # Agregar favorito
            new_favorite = Favorite(user_id=user_id, product_id=product.id)
            db.session.add(new_favorite)
            action = 'added'
            message = 'Producto agregado a favoritos'
        
        db.session.commit()
        
        # Redirigir de vuelta a favoritos
        flash(message, 'success')
        return redirect('/favorites')
        
    except Exception as e:
        db.session.rollback()
        print(f"ERROR en toggle_favorite_route: {str(e)}")
        import traceback
        traceback.print_exc()
        
        flash('Error al actualizar favoritos', 'error')
        return redirect('/favorites')

@public_bp.route('/favorites/check/<part_number>', methods=['GET'])
def check_favorite_route(part_number):
    """API para verificar si un producto es favorito"""
    try:
        user_id = get_current_user_id()
        
        # Buscar producto
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            return jsonify({'success': True, 'is_favorite': False})
        
        # Verificar si es favorito
        favorite = Favorite.query.filter_by(user_id=user_id, product_id=product.id).first()
        
        return jsonify({
            'success': True,
            'is_favorite': favorite is not None
        })
        
    except Exception as e:
        print(f"Error checking favorite: {str(e)}")
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
    
    # Buscar o crear producto
    product = Product.query.filter_by(ingram_part_number=product_data['ingramPartNumber']).first()
    if not product:
        product = Product(
            ingram_part_number=product_data['ingramPartNumber'],
            description=product_data.get('description', ''),
            vendor_name=product_data.get('vendorName', 'N/A')
        )
        db.session.add(product)
        db.session.flush()
    
    # Verificar si ya es favorito
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
        
        # Calcular totales REALES
        total_items = sum(item['quantity'] for item in cart_items)
        total_value = 0.0
        
        for item in cart_items:
            total_value += item['total_price']
        
        # Obtener fecha de última actualización
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
        print(f"Error obteniendo estadísticas del carrito: {str(e)}")
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
        print(f"Error obteniendo contador de favoritos: {str(e)}")
        return 0

def get_recent_activity(user_id):
    """Obtener actividad reciente del usuario"""
    try:
        # Aquí puedes implementar lógica para obtener actividad reciente
        # Por ahora devolvemos datos de ejemplo
        return [
            {'action': 'Producto agregado al carrito', 'date': 'Hoy', 'icon': 'fas fa-cart-plus'},
            {'action': 'Producto visto', 'date': 'Hoy', 'icon': 'fas fa-eye'},
            {'action': 'Búsqueda realizada', 'date': 'Ayer', 'icon': 'fas fa-search'}
        ]
    except Exception as e:
        print(f"Error obteniendo actividad reciente: {str(e)}")
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
        print(f"ERROR en api_remove_from_cart: {str(e)}")
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
        print(f"Error removing from cart: {e}")
        return False