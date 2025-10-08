from flask import Blueprint, render_template, request, session, flash, redirect, jsonify
from datetime import datetime
import json
from app import db
from app.models.user import User
from app.models.quote import Quote, QuoteItem
from app.models.favorite import Favorite
from app.models.product import Product
from app.models.product_utils import ProductUtils
from app.models.api_client import APIClient
from app.models.image_handler import ImageHandler
from functools import wraps

# Crear Blueprint para rutas de clientes SIN prefijo
client_routes_bp = Blueprint('client_routes', __name__)

def login_required_sessions(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión para acceder a esta página', 'warning')
            return redirect('/auth/login')
        return f(*args, **kwargs)
    return decorated_function

def get_current_user_id():
    """Obtener ID del usuario actual de la sesión"""
    return session.get('user_id', 'anonymous_user')

# ==================== FUNCIONES AUXILIARES OPTIMIZADAS ====================

def get_user_quotes(user_id):
    """Obtener cotización del usuario usando los nuevos modelos"""
    try:
        quote = Quote.query.filter_by(user_id=user_id, status='draft').first()
        if not quote:
            return []
        
        items_with_details = []
        for item in quote.items:
            product = item.product
            items_with_details.append({
                'product': {
                    'ingramPartNumber': product.ingram_part_number,
                    'description': product.description,
                    'vendorName': product.vendor_name,
                    'upc': product.upc,
                    'category': product.category,
                    'pricing': {'customerPrice': product.base_price},
                    'productImages': json.loads(product.metadata_json).get('productImages', []) if product.metadata_json else []
                },
                'quantity': item.quantity,
                'added_date': item.created_at.isoformat()
            })
        
        return items_with_details
    except Exception as e:
        print(f"Error en get_user_quotes: {str(e)}")
        return []

def add_to_quote(user_id, product_data, quantity=1):
    """Agregar producto a cotización usando nuevos modelos"""
    try:
        # Obtener o crear quote
        quote = Quote.query.filter_by(user_id=user_id, status='draft').first()
        if not quote:
            quote_number = f"QT{datetime.now().strftime('%Y%m%d%H%M%S')}"
            quote = Quote(user_id=user_id, quote_number=quote_number, status='draft')
            db.session.add(quote)
            db.session.flush()
        
        # Buscar o crear producto
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
        
        # Buscar item existente
        existing_item = QuoteItem.query.filter_by(quote_id=quote.id, product_id=product.id).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.calculate_total()
        else:
            unit_price = product.base_price * 1.10  # 10% markup
            new_item = QuoteItem(
                quote_id=quote.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=unit_price
            )
            new_item.calculate_total()
            db.session.add(new_item)
        
        # Recalcular total
        quote.calculate_total()
        db.session.commit()
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding to quote: {e}")
        raise

def toggle_favorite(user_id, product_data):
    """Agregar/eliminar producto de favoritos usando nuevos modelos"""
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

def is_product_favorite(user_id, part_number):
    """Verificar si un producto está en favoritos usando nuevos modelos"""
    if user_id == 'anonymous_user':
        return False
    
    try:
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            return False
        
        return Favorite.query.filter_by(user_id=user_id, product_id=product.id).first() is not None
    except Exception as e:
        print(f"Error en is_product_favorite: {str(e)}")
        return False

def remove_product_from_quote(user_id, part_number):
    """Eliminar producto de cotización usando nuevos modelos"""
    try:
        # Obtener la cotización del usuario
        quote = Quote.query.filter_by(user_id=user_id, status='draft').first()
        if not quote:
            return False
        
        # Buscar el producto en la base de datos local
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            return False
        
        # Buscar el item en la cotización
        item = QuoteItem.query.filter_by(quote_id=quote.id, product_id=product.id).first()
        if not item:
            return False
        
        # Eliminar el item
        db.session.delete(item)
        
        # Recalcular el total de la cotización
        quote.calculate_total()
        
        # Guardar cambios
        db.session.commit()
        return True
        
    except Exception as e:
        print(f"ERROR in remove_from_quote: {str(e)}")
        db.session.rollback()
        return False

def update_quote_quantity(user_id, part_number, quantity):
    """Actualizar cantidad en cotización usando nuevos modelos"""
    quote = Quote.query.filter_by(user_id=user_id, status='draft').first()
    if not quote:
        return
    
    product = Product.query.filter_by(ingram_part_number=part_number).first()
    if not product:
        return
    
    item = QuoteItem.query.filter_by(quote_id=quote.id, product_id=product.id).first()
    if item:
        item.quantity = max(1, quantity)
        item.calculate_total()
        quote.calculate_total()
        db.session.commit()

def clear_user_quote(user_id):
    """Limpiar toda la cotización del usuario usando nuevos modelos"""
    quote = Quote.query.filter_by(user_id=user_id, status='draft').first()
    if quote:
        # Eliminar todos los items de la cotización
        for item in quote.items:
            db.session.delete(item)
        quote.total_amount = 0
        db.session.commit()

def get_user_favorites(user_id):
    """Obtener favoritos del usuario usando los nuevos modelos"""
    favorites = Favorite.query.filter_by(user_id=user_id).all()
    
    favorite_list = []
    for fav in favorites:
        product = fav.product
        favorite_list.append({
            'ingramPartNumber': product.ingram_part_number,
            'description': product.description,
            'vendorName': product.vendor_name,
            'favorited_date': fav.created_at.isoformat()
        })
    
    return favorite_list

def remove_from_favorites(user_id, part_number):
    """Eliminar producto de favoritos"""
    product = Product.query.filter_by(ingram_part_number=part_number).first()
    if not product:
        return
    
    favorite = Favorite.query.filter_by(user_id=user_id, product_id=product.id).first()
    if favorite:
        db.session.delete(favorite)
        db.session.commit()

# ==================== DASHBOARD CLIENTE ====================

@client_routes_bp.route('/dashboard/client')
@login_required_sessions
def client_dashboard():
    """Dashboard para clientes empresariales"""
    try:
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        
        # Verificar que sea cliente
        if user.account_type != 'client':
            flash('Acceso no autorizado', 'error')
            return redirect('/dashboard')
        
        # Obtener estadísticas de cotizaciones
        total_quotes = Quote.query.filter_by(user_id=user_id).count()
        pending_quotes = Quote.query.filter_by(user_id=user_id).filter(
            Quote.status.in_(['draft', 'sent', 'pending'])
        ).count()
        approved_quotes = Quote.query.filter_by(user_id=user_id, status='approved').count()
        
        # Obtener favoritos
        favorites_count = Favorite.query.filter_by(user_id=user_id).count()
        
        # Datos para el template
        dashboard_data = {
            'user_name': user.full_name or user.email.split('@')[0],
            'user_email': user.email,
            'business_name': user.business_name or 'Tu Empresa',
            'rfc': user.rfc or 'No especificado',
            'total_quotes': total_quotes,
            'pending_quotes': pending_quotes,
            'approved_quotes': approved_quotes,
            'favorites_count': favorites_count,
            'discount': 15,
            'credit_limit': 50000,
            'now': datetime.now(),
            'user_type': 'client'
        }
        
        return render_template('client/dashboard.html', **dashboard_data)
        
    except Exception as e:
        print(f"Error cargando dashboard cliente: {str(e)}")
        flash('Error al cargar el dashboard', 'error')
        return redirect('/')

# ==================== RUTAS DE CATÁLOGO ====================

@client_routes_bp.route("/catalogo-completo-cards", methods=["GET"])
@client_routes_bp.route("/catalog", methods=["GET"])
def catalogo_completo_cards():
    """Catálogo principal con búsqueda híbrida mejorada"""
    # Parámetros de búsqueda
    page_number = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 25))
    query = request.args.get("q", "").strip()
    vendor = request.args.get("vendor", "").strip()
    
    try:
        # Realizar la búsqueda
        productos, total_records, pagina_vacia = ProductUtils.buscar_productos_hibrido(
            query=query, 
            vendor=vendor, 
            page_number=page_number, 
            page_size=page_size, 
            use_keywords=bool(query)
        )
        
        # Si la página está vacía pero debería tener datos, corregir
        if pagina_vacia and page_number > 1 and total_records > 0:
            page_number = max(1, page_number - 1)
            productos, total_records, pagina_vacia = ProductUtils.buscar_productos_hibrido(
                query=query, vendor=vendor, page_number=page_number, page_size=page_size, use_keywords=bool(query)
            )
        
        # Cálculos de paginación
        total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
        page_number = max(1, min(page_number, total_pages))
        
        start_record = (page_number - 1) * page_size + 1 if total_records > 0 else 0
        end_record = min(page_number * page_size, total_records)
        
        return render_template(
            "client/catalog/catalog.html",
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
            format_currency=ProductUtils.format_currency,
            use_keywords=bool(query),
            suggested_keywords=ProductUtils.sugerir_palabras_clave(query) if query else []
        )
    
    except Exception as e:
        print(f"ERROR en catálogo: {str(e)}")
        return render_template("client/catalog/catalog.html", 
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
                             error_message=f"Error al cargar productos: {str(e)}")

@client_routes_bp.route("/producto/<part_number>", methods=["GET"])
def producto_detalle(part_number=None, sku=None):
    """Detalle de producto unificado"""
    product_id = part_number or sku
    
    if not product_id:
        return render_template("errors/404.html", message="Producto no encontrado"), 404
    
    try:
        # Detalle del producto
        detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{product_id}"
        detalle_res = APIClient.make_request("GET", detail_url)
        
        if detalle_res.status_code != 200:
            return render_template("errors/404.html", message=f"Producto {product_id} no encontrado"), 404
        
        detalle = detalle_res.json()

        # Obtener extraDescription del endpoint de catálogo
        catalog_url = "https://api.ingrammicro.com/resellers/v6/catalog"
        params = {
            "pageSize": 1,
            "pageNumber": 1,
            "partNumber": product_id
        }
        catalog_res = APIClient.make_request("GET", catalog_url, params=params)
        catalog_data = catalog_res.json() if catalog_res.status_code == 200 else {}

        # Extraer extraDescription
        extra_description = None
        if isinstance(catalog_data, dict) and catalog_data.get("catalog"):
            productos = catalog_data["catalog"]
            if isinstance(productos, list) and len(productos) > 0:
                producto = productos[0]
                extra_description = producto.get("extraDescription")

        # Precio y disponibilidad - USANDO MÉTODO CORREGIDO
        price_data = APIClient.get_product_price_and_availability(product_id)
        precio_info = price_data if price_data else {}

        # Calcular precio final con markup del 10%
        pricing = precio_info.get("pricing") or {}
        base_price = pricing.get("customerPrice")
        currency = pricing.get("currencyCode") or pricing.get("currency") or ""
        precio_final_val = None
        if base_price is not None:
            try:
                precio_final_val = round(float(base_price) * 1.10, 2)
            except Exception:
                precio_final_val = None
        precio_final = ProductUtils.format_currency(precio_final_val, currency) if precio_final_val is not None else "No disponible"

        # Disponibilidad interpretada
        disponibilidad = ProductUtils.get_availability_text(precio_info, detalle)

        # Extraer atributos
        atributos = []
        raw_attrs = detalle.get("productAttributes") or detalle.get("attributes") or []
        if isinstance(raw_attrs, list):
            for a in raw_attrs:
                name = a.get("name") or a.get("attributeName") or a.get("key") or None
                value = a.get("value") or a.get("attributeValue") or a.get("val") or ""
                if name:
                    atributos.append({"name": name, "value": value})

        # Imagen mejorada
        imagen_url = ImageHandler.get_image_url_enhanced(detalle)
        
        # Descripción completa
        descripcion_completa = detalle.get("description") or detalle.get("productDescription") or ""
        
        return render_template(
            "client/catalog/product_detail.html",
            detalle=detalle,
            producto=detalle,
            p=detalle,
            precio_final=precio_final,
            disponibilidad=disponibilidad,
            atributos=atributos,
            imagen_url=imagen_url,
            part_number=product_id,
            extra_description=extra_description,
            descripcion_completa=descripcion_completa
        )
    
    except Exception as e:
        print(f"Error obteniendo detalle del producto {product_id}: {str(e)}")
        return render_template("errors/500.html", message="Error al cargar el detalle del producto"), 500

# ==================== RUTAS DE COTIZACIONES UNIFICADAS ====================

@client_routes_bp.route('/mi-cotizacion', methods=["GET"])
def mi_cotizacion():
    """Página de cotización con formato mexicano - CON BASE DE DATOS"""
    try:
        user_id = get_current_user_id()
        quote_items = get_user_quotes(user_id)
        
        total = 0
        items_with_totals = []
        
        for item in quote_items:
            pricing_info = item['product'].get('pricing', {})
            base_price = pricing_info.get('customerPrice', 0)
            quantity = item['quantity']
            
            try:
                if isinstance(base_price, str):
                    base_price_float = float(base_price.replace(',', '').replace('$', ''))
                elif isinstance(base_price, (int, float)):
                    base_price_float = float(base_price)
                else:
                    base_price_float = 0.0
                
                # Aplicar markup del 10%
                unit_price_with_markup = round(base_price_float * 1.10, 2)
                item_total = unit_price_with_markup * quantity
                total += item_total
                
                item_data = {
                    **item,
                    'unit_price': unit_price_with_markup,
                    'total_price': item_total,
                    'formatted_unit_price': f"${unit_price_with_markup:,.2f} MXN",
                    'formatted_total_price': f"${item_total:,.2f} MXN"
                }
                    
            except (ValueError, TypeError):
                item_data = {
                    **item,
                    'unit_price': 0,
                    'total_price': 0,
                    'formatted_unit_price': 'No disponible',
                    'formatted_total_price': 'No disponible'
                }
            
            items_with_totals.append(item_data)
        
        flash_message = session.pop('flash_message', None)
        
        return render_template(
            "client/catalog/quote.html",
            items=items_with_totals,
            total=round(total, 2),
            formatted_total=f"${total:,.2f} MXN",
            count=len(quote_items),
            flash_message=flash_message
        )
        
    except Exception as e:
        print(f"Error al cargar cotización: {str(e)}")
        return render_template("error.html", error=f"Error al cargar cotización: {str(e)}")

# ==================== RUTAS DE FAVORITOS UNIFICADAS ====================

@client_routes_bp.route('/mis-favoritos', methods=["GET"])
@client_routes_bp.route('/favorites', methods=["GET"])
def mis_favoritos():
    """Página de favoritos del usuario - CON BASE DE DATOS"""
    try:
        user_id = get_current_user_id()
        favorites = get_user_favorites(user_id)
        
        flash_message = session.pop('flash_message', None)
        
        return render_template(
            "client/catalog/favorites.html",
            favorites=favorites,
            count=len(favorites),
            flash_message=flash_message,
            get_image_url_enhanced=ImageHandler.get_image_url_enhanced
        )
        
    except Exception as e:
        print(f"Error al cargar favoritos: {str(e)}")
        return render_template("error.html", error=f"Error al cargar favoritos: {str(e)}")

# ==================== RUTAS DE HISTORIAL DE COTIZACIONES ====================

@client_routes_bp.route('/quote/history')
@login_required_sessions
def quote_history():
    """Historial de cotizaciones del cliente"""
    try:
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        
        # Verificar que sea cliente
        if user.account_type != 'client':
            flash('Acceso no autorizado', 'error')
            return redirect('/dashboard')
        
        # Obtener parámetros de filtro
        status = request.args.get('status', 'all')
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        # Base query
        query = Quote.query.filter_by(user_id=user_id)
        
        # Aplicar filtro de estado
        if status == 'pending':
            query = query.filter(Quote.status.in_(['draft', 'sent', 'pending']))
        elif status == 'approved':
            query = query.filter(Quote.status == 'approved')
        elif status == 'rejected':
            query = query.filter(Quote.status == 'rejected')
        # 'all' muestra todas
        
        # Ordenar y paginar
        quotes = query.order_by(Quote.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Estadísticas
        stats = {
            'total': Quote.query.filter_by(user_id=user_id).count(),
            'pending': Quote.query.filter_by(user_id=user_id).filter(
                Quote.status.in_(['draft', 'sent', 'pending'])
            ).count(),
            'approved': Quote.query.filter_by(user_id=user_id, status='approved').count(),
            'rejected': Quote.query.filter_by(user_id=user_id, status='rejected').count()
        }
        
        return render_template('client/catalog/quote_history.html',
                            quotes=quotes,
                            stats=stats,
                            current_status=status,
                            user_type='client')
        
    except Exception as e:
        print(f"Error cargando historial de cotizaciones: {str(e)}")
        flash('Error al cargar el historial de cotizaciones', 'error')
        return redirect('/dashboard/client')

@client_routes_bp.route('/quote/<int:quote_id>')
@login_required_sessions
def quote_detail(quote_id):
    """Detalle de una cotización específica"""
    try:
        user_id = session.get('user_id')
        quote = Quote.query.filter_by(id=quote_id, user_id=user_id).first()
        
        if not quote:
            flash('Cotización no encontrada', 'error')
            return redirect('/quote/history')
        
        # Obtener items de la cotización
        quote_items = QuoteItem.query.filter_by(quote_id=quote_id).all()
        
        # Calcular totales
        total_amount = sum(item.quantity * (item.unit_price or 0) for item in quote_items)
        
        return render_template('client/catalog/quote_detail.html',
                            quote=quote,
                            quote_items=quote_items,
                            total_amount=total_amount,
                            user_type='client')
        
    except Exception as e:
        print(f"Error cargando detalle de cotización: {str(e)}")
        flash('Error al cargar la cotización', 'error')
        return redirect('/quote/history')

@client_routes_bp.route('/quote/request-approval/<int:quote_id>', methods=['POST'])
@login_required_sessions
def request_quote_approval(quote_id):
    """Solicitar aprobación de una cotización"""
    try:
        user_id = session.get('user_id')
        quote = Quote.query.filter_by(id=quote_id, user_id=user_id).first()
        
        if not quote:
            flash('Cotización no encontrada', 'error')
            return redirect('/quote/history')
        
        # Cambiar estado a pendiente de aprobación
        quote.status = 'pending'
        db.session.commit()
        
        flash('Solicitud de aprobación enviada correctamente', 'success')
        return redirect('/quote/history')
        
    except Exception as e:
        print(f"Error solicitando aprobación: {str(e)}")
        flash('Error al solicitar aprobación', 'error')
        return redirect('/quote/history')

@client_routes_bp.route('/quote/duplicate/<int:quote_id>', methods=['POST'])
@login_required_sessions
def duplicate_quote(quote_id):
    """Duplicar una cotización existente"""
    try:
        user_id = session.get('user_id')
        original_quote = Quote.query.filter_by(id=quote_id, user_id=user_id).first()
        
        if not original_quote:
            flash('Cotización no encontrada', 'error')
            return redirect('/quote/history')
        
        # Crear nueva cotización
        quote_number = f"QT{datetime.now().strftime('%Y%m%d%H%M%S')}"
        new_quote = Quote(
            user_id=user_id,
            quote_number=quote_number,
            status='draft',
            total_amount=original_quote.total_amount,
            business_name=original_quote.business_name,
            contact_name=original_quote.contact_name,
            contact_email=original_quote.contact_email
        )
        db.session.add(new_quote)
        db.session.flush()
        
        # Copiar items
        for original_item in original_quote.items:
            new_item = QuoteItem(
                quote_id=new_quote.id,
                product_id=original_item.product_id,
                quantity=original_item.quantity,
                unit_price=original_item.unit_price,
                total_price=original_item.total_price
            )
            db.session.add(new_item)
        
        db.session.commit()
        
        flash(f'Cotización #{quote_number} duplicada exitosamente', 'success')
        return redirect('/mi-cotizacion')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error duplicando cotización: {str(e)}")
        flash('Error al duplicar la cotización', 'error')
        return redirect('/quote/history')

# ==================== APIs JSON UNIFICADAS ====================

@client_routes_bp.route("/api/get-quote", methods=["GET"])
def api_get_quote():
    """API para obtener cotización actual - CON BASE DE DATOS"""
    try:
        user_id = get_current_user_id()
        quote_items = get_user_quotes(user_id)
        
        total = 0
        items_with_totals = []
        
        for item in quote_items:
            price_str = item['product'].get('pricing', {}).get('customerPrice', '0')
            quantity = item['quantity']
            
            try:
                if isinstance(price_str, str):
                    clean_price = ''.join(c for c in price_str if c.isdigit() or c == '.')
                    base_price = float(clean_price) if clean_price else 0.0
                else:
                    base_price = float(price_str)
                
                unit_price_with_markup = round(base_price * 1.10, 2)
                item_total = unit_price_with_markup * quantity
                total += item_total
                
                item_data = {
                    'product': {
                        'ingramPartNumber': item['product']['ingramPartNumber'],
                        'description': item['product']['description'],
                        'vendorName': item['product']['vendorName'],
                        'pricing': {
                            'customerPrice': unit_price_with_markup
                        },
                        'extraDescription': item['product'].get('extraDescription', ''),
                        'availability': item['product'].get('availability', {})
                    },
                    'quantity': quantity,
                    'unit_price': unit_price_with_markup,
                    'total_price': item_total
                }
                
            except (ValueError, TypeError):
                item_data = {
                    'product': {
                        **item['product'],
                        'pricing': {'customerPrice': 0}
                    },
                    'quantity': quantity,
                    'unit_price': 0,
                    'total_price': 0
                }
            
            items_with_totals.append(item_data)
        
        return jsonify({
            'success': True,
            'items': items_with_totals,
            'count': len(quote_items),
            'total': round(total, 2)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'items': [],
            'count': 0,
            'total': 0
        }), 500

@client_routes_bp.route("/api/get-favorites", methods=["GET"])
def api_get_favorites():
    """API para obtener favoritos - CON BASE DE DATOS"""
    try:
        user_id = get_current_user_id()
        favorites = get_user_favorites(user_id)
        
        return jsonify({
            'success': True,
            'favorites': favorites,
            'count': len(favorites)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'favorites': [],
            'count': 0
        }), 500

@client_routes_bp.route("/api/check-favorite/<product_id>", methods=["GET"])
def api_check_favorite(product_id):
    """Verificar si un producto está en favoritos - CON BASE DE DATOS"""
    try:
        user_id = get_current_user_id()
        
        # Para usuarios anónimos, siempre retornar false
        if user_id == 'anonymous_user':
            return jsonify({
                'success': True,
                'is_favorite': False,
                'favorites_count': 0
            })
        
        is_favorite = is_product_favorite(user_id, product_id)
        
        # Contar favoritos del usuario
        favorites_count = Favorite.query.filter_by(user_id=user_id).count()
        
        return jsonify({
            'success': True,
            'is_favorite': is_favorite,
            'favorites_count': favorites_count
        })
        
    except Exception as e:
        print(f"Error en api_check_favorite: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'is_favorite': False,
            'favorites_count': 0
        }), 500

# ==================== APIs DE GESTIÓN UNIFICADAS ====================

@client_routes_bp.route('/api/quote/add', methods=['POST'])
def api_add_to_quote():
    """API UNIFICADA para agregar producto a cotización"""
    try:
        data = request.get_json()
        part_number = data.get('part_number')
        
        # Obtener cantidad del frontend o usar valor por defecto
        quantity_input = data.get('quantity')
        
        if quantity_input is None:
            quantity = 1
        else:
            try:
                quantity = int(quantity_input)
                if quantity < 1:
                    quantity = 1
                if quantity > 999:
                    quantity = 999
            except (ValueError, TypeError):
                quantity = 1
        
        # Obtener datos del producto
        detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
        detalle_res = APIClient.make_request("GET", detail_url)
        
        if detalle_res.status_code != 200:
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        detalle = detalle_res.json()
        
        # Obtener precio usando método corregido
        price_data = APIClient.get_product_price_and_availability(part_number)
        
        real_price = 0
        availability_data = {}
        
        if price_data:
            pricing = price_data.get('pricing', {})
            customer_price = pricing.get('customerPrice')
            
            if customer_price is not None:
                try:
                    real_price = float(customer_price)
                except (ValueError, TypeError):
                    real_price = 0
            
            availability_data = price_data.get('availability', {})
        
        product_data = {
            'ingramPartNumber': part_number,
            'description': detalle.get('description', f"Producto {part_number}"),
            'pricing': {'customerPrice': real_price},
            'vendorName': detalle.get('vendorName', 'N/A'),
            'upc': detalle.get('upc', ''),
            'category': detalle.get('category', ''),
            'availability': availability_data,
            'productImages': detalle.get('productImages', [])
        }
        
        user_id = get_current_user_id()
        add_to_quote(user_id, product_data, quantity)
        
        return jsonify({
            'success': True,
            'message': f'Producto agregado a cotización (Cantidad: {quantity})',
            'quote_count': len(get_user_quotes(user_id))
        })
        
    except Exception as e:
        print(f"Error en api_add_to_quote: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@client_routes_bp.route('/api/quote/remove', methods=['POST'])
def api_remove_from_quote():
    """API UNIFICADA para eliminar producto de cotización"""
    try:
        # Manejar tanto JSON como form data
        if request.is_json:
            data = request.get_json()
            product_id = data.get('product_id')
        else:
            # Para formularios tradicionales
            product_id = request.form.get('product_id')
        
        if not product_id:
            return jsonify({'success': False, 'error': 'product_id requerido'}), 400
        
        user_id = get_current_user_id()
        result = remove_product_from_quote(user_id, product_id)
        
        if result:
            return jsonify({'success': True, 'message': 'Producto eliminado de cotización'})
        else:
            return jsonify({'success': False, 'error': 'Producto no encontrado en cotización'})
        
    except Exception as e:
        print(f"ERROR en api_remove_from_quote: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@client_routes_bp.route('/api/quote/update-quantity', methods=['POST'])
def api_update_quote_quantity():
    """API UNIFICADA para actualizar cantidad en cotización"""
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        user_id = get_current_user_id()
        update_quote_quantity(user_id, product_id, quantity)
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@client_routes_bp.route('/api/quote/clear', methods=['POST'])
def api_clear_quote():
    """API UNIFICADA para limpiar cotización completa"""
    try:
        user_id = get_current_user_id()
        clear_user_quote(user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@client_routes_bp.route('/api/favorite/toggle', methods=['POST'])
def api_toggle_favorite():
    """API UNIFICADA para agregar/eliminar favorito"""
    try:
        data = request.get_json()
        part_number = data.get('part_number')
        
        # Obtener datos básicos del producto
        detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
        detalle_res = APIClient.make_request("GET", detail_url)
        
        description = f"Producto {part_number}"
        vendor = "N/A"
        
        if detalle_res.status_code == 200:
            detalle = detalle_res.json()
            description = detalle.get('description', description)
            vendor = detalle.get('vendorName', vendor)
        
        product_data = {
            'ingramPartNumber': part_number,
            'description': description,
            'vendorName': vendor
        }
        
        user_id = get_current_user_id()
        action = toggle_favorite(user_id, product_data)
        
        return jsonify({
            'success': True,
            'action': action,
            'is_favorite': action == 'added',
            'message': 'Producto agregado a favoritos' if action == 'added' else 'Producto eliminado de favoritos'
        })
        
    except Exception as e:
        print(f"Error en api_toggle_favorite: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS DE ELIMINACIÓN DE COTIZACIONES ====================

@client_routes_bp.route('/quote/delete/<int:quote_id>', methods=['POST'])
@login_required_sessions
def delete_quote(quote_id):
    """Eliminar una cotización del historial (solo borradores y propias)"""
    try:
        user_id = session.get('user_id')
        quote = Quote.query.filter_by(id=quote_id, user_id=user_id).first()
        
        if not quote:
            flash('Cotización no encontrada', 'error')
            return redirect('/quote/history')
        
        # Solo permitir eliminar cotizaciones en estado 'draft' o 'sent'
        if quote.status not in ['draft', 'sent']:
            flash('Solo puedes eliminar cotizaciones en borrador o enviadas', 'warning')
            return redirect('/quote/history')
        
        quote_number = quote.quote_number
        
        # Eliminar items primero
        QuoteItem.query.filter_by(quote_id=quote_id).delete()
        
        # Eliminar la cotización
        db.session.delete(quote)
        db.session.commit()
        
        flash(f'Cotización #{quote_number} eliminada correctamente', 'success')
        return redirect('/quote/history')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error eliminando cotización: {str(e)}")
        flash('Error al eliminar la cotización', 'error')
        return redirect('/quote/history')

@client_routes_bp.route('/quote/cancel/<int:quote_id>', methods=['POST'])
@login_required_sessions
def cancel_quote(quote_id):
    """Cancelar una cotización (cambio de estado a cancelled)"""
    try:
        user_id = session.get('user_id')
        quote = Quote.query.filter_by(id=quote_id, user_id=user_id).first()
        
        if not quote:
            flash('Cotización no encontrada', 'error')
            return redirect('/quote/history')
        
        # Solo permitir cancelar cotizaciones que no estén ya canceladas o aprobadas
        if quote.status in ['cancelled', 'approved', 'completed']:
            flash(f'No puedes cancelar una cotización en estado: {quote.status}', 'warning')
            return redirect('/quote/history')
        
        quote.status = 'cancelled'
        quote.updated_at = datetime.now()
        db.session.commit()
        
        flash(f'Cotización #{quote.quote_number} cancelada correctamente', 'warning')
        return redirect('/quote/history')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error cancelando cotización: {str(e)}")
        flash('Error al cancelar la cotización', 'error')
        return redirect('/quote/history')

# ==================== RUTAS DE UTILIDAD ====================

@client_routes_bp.route('/limpiar-cotizacion', methods=["POST"])
def limpiar_cotizacion():
    """Limpiar cotización (ruta HTML) - CON BASE DE DATOS"""
    try:
        user_id = get_current_user_id()
        clear_user_quote(user_id)
        session['flash_message'] = "Cotización limpiada exitosamente"
        return redirect('/mi-cotizacion')
    except Exception as e:
        session['flash_message'] = f"Error al limpiar cotización: {str(e)}"
        return redirect('/mi-cotizacion')

@client_routes_bp.route('/actualizar-cantidad-cotizacion', methods=["POST"])
def actualizar_cantidad_cotizacion():
    """Actualizar cantidad (ruta HTML) - CON BASE DE DATOS"""
    try:
        part_number = request.form.get('part_number')
        new_quantity = int(request.form.get('quantity', 1))
        
        if new_quantity < 1:
            session['flash_message'] = "La cantidad debe ser mayor a 0"
            return redirect('/mi-cotizacion')
        
        user_id = get_current_user_id()
        update_quote_quantity(user_id, part_number, new_quantity)
        
        session['flash_message'] = f"Cantidad actualizada a {new_quantity}"
        return redirect('/mi-cotizacion')
        
    except (ValueError, TypeError):
        session['flash_message'] = "Cantidad inválida"
        return redirect('/mi-cotizacion')
    except Exception as e:
        session['flash_message'] = f"Error al actualizar cantidad: {str(e)}"
        return redirect('/mi-cotizacion')

@client_routes_bp.route("/limpiar-busqueda", methods=["GET"])
def limpiar_busqueda():
    """Limpiar parámetros de búsqueda y redirigir a página 1"""
    return redirect('/catalogo-completo-cards?page=1')

@client_routes_bp.route("/pagina/<int:page_number>", methods=["GET"])
def ir_a_pagina(page_number):
    """Ir a una página específica manteniendo los filtros actuales"""
    args = request.args.copy()
    args['page'] = page_number
    return redirect('/catalogo-completo-cards?' + '&'.join([f'{k}={v}' for k, v in args.items()]))

def send_quote_to_admin(quote, user):
    """Enviar cotización al administrador con el total que incluye IVA"""
    try:
        # Calcular totales con IVA
        totals = quote.calculate_totals_with_tax()
        
        # Guardar en la misma cotización
        quote.subtotal = totals['subtotal']
        quote.tax_amount = totals['tax_amount']
        quote.total_amount = totals['total_with_tax']
        quote.status = 'sent'  # Cambiar estado a enviado
        db.session.commit()
        
        print(f"COTIZACIÓN ENVIADA AL ADMINISTRADOR:")
        print(f"Quote ID: {quote.id}")
        print(f"Subtotal: ${totals['subtotal']:,.2f} MXN")
        print(f"IVA (16%): ${totals['tax_amount']:,.2f} MXN")
        print(f"TOTAL CON IVA: ${totals['total_with_tax']:,.2f} MXN")
        
        return True
        
    except Exception as e:
        print(f"Error enviando cotización al admin: {str(e)}")
        return False

@client_routes_bp.route('/enviar-cotizacion', methods=['POST'])
@login_required_sessions
def enviar_cotizacion():
    """Enviar cotización actual al administrador (desde la página de cotización)"""
    try:
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        
        # Obtener la cotización en borrador actual
        draft_quote = Quote.query.filter_by(user_id=user_id, status='draft').first()
        
        if not draft_quote or not draft_quote.items:
            flash('No hay productos en tu cotización actual', 'warning')
            return redirect('/mi-cotizacion')
        
        # Cambiar el estado a 'sent' y calcular con IVA
        draft_quote.status = 'sent'
        
        # Enviar al administrador con IVA
        send_quote_to_admin(draft_quote, user)
        
        flash(f'Cotización enviada al administrador. Total con IVA: ${draft_quote.total_amount:,.2f} MXN', 'success')
        return redirect('/mi-cotizacion')
        
    except Exception as e:
        db.session.rollback()
        print(f"Error enviando cotización: {str(e)}")
        flash('Error al enviar la cotización', 'error')
        return redirect('/mi-cotizacion')