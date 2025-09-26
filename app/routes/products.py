from flask import Blueprint, render_template, request, jsonify, session, redirect, flash
from datetime import datetime
import json
from app import db 
from app.models.product import Product
from app.models.favorite import Favorite
from app.models.quote import Quote, QuoteItem
from app.models.user import User
from app.models.product_utils import ProductUtils
from app.models.api_client import APIClient
from app.models.image_handler import ImageHandler

# Crear Blueprint para las rutas de productos
products_bp = Blueprint('products', __name__, url_prefix='/products')

def get_current_user_id():
    """Obtener ID del usuario actual de la sesión"""
    return session.get('user_id', 'anonymous_user')

# ==================== FUNCIONES DE BASE DE DATOS ACTUALIZADAS ====================
def get_user_quotes(user_id):
    """Obtener cotización del usuario usando los nuevos modelos"""
    from app.models.quote import Quote, QuoteItem
    
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
    from app.models.quote import Quote, QuoteItem
    from app.models.product import Product
    
    try:
        print(f"DEBUG - add_to_quote iniciado para: {product_data['ingramPartNumber']}")
        
        # Obtener o crear quote
        quote = Quote.query.filter_by(user_id=user_id, status='draft').first()
        if not quote:
            quote_number = f"QT{datetime.now().strftime('%Y%m%d%H%M%S')}"
            quote = Quote(user_id=user_id, quote_number=quote_number, status='draft')
            db.session.add(quote)
            db.session.flush()
            print(f"DEBUG - Nueva quote creada: {quote_number}")
        
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
        
        # Buscar item existente
        existing_item = QuoteItem.query.filter_by(quote_id=quote.id, product_id=product.id).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.calculate_total()
            print(f"DEBUG - Item existente actualizado, cantidad: {existing_item.quantity}")
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
            print(f"DEBUG - Nuevo item creado, precio: {unit_price}, cantidad: {quantity}")
        
        # Recalcular total
        quote.calculate_total()
        db.session.commit()
        print(f"DEBUG - Quote guardada exitosamente, total: {quote.total_amount}")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding to quote: {e}")
        import traceback
        traceback.print_exc()
        raise
# ==================== RUTAS PRINCIPALES DEL CATÁLOGO ====================
# (Mantener el mismo código que ya tienes para catalogo_completo_cards)
@products_bp.route("/catalogo-completo-cards", methods=["GET"])
@products_bp.route("/catalog", methods=["GET"])
def catalogo_completo_cards():
    """Catálogo principal con búsqueda híbrida mejorada"""
    # Parámetros de búsqueda
    page_number = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 25))  # Permitir configurar tamaño de página
    query = request.args.get("q", "").strip()
    vendor = request.args.get("vendor", "").strip()
    
    # DEBUG: Log de parámetros
    print(f"DEBUG - Page: {page_number}, Size: {page_size}, Query: '{query}', Vendor: '{vendor}'")
    
    try:
        # Realizar la búsqueda
        productos, total_records, pagina_vacia = ProductUtils.buscar_productos_hibrido(
            query=query, 
            vendor=vendor, 
            page_number=page_number, 
            page_size=page_size, 
            use_keywords=bool(query)  # Solo usar keywords cuando hay query
        )
        
        print(f"DEBUG - Resultados: {len(productos)}/{total_records}, Página vacía: {pagina_vacia}")
        
        # Si la página está vacía pero debería tener datos, corregir
        if pagina_vacia and page_number > 1 and total_records > 0:
            # Intentar con la página anterior
            page_number = max(1, page_number - 1)
            productos, total_records, pagina_vacia = ProductUtils.buscar_productos_hibrido(
                query=query, vendor=vendor, page_number=page_number, page_size=page_size, use_keywords=bool(query)
            )
        
        # Cálculos de paginación corregidos
        total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
        
        # Asegurar que page_number esté dentro del rango válido
        page_number = max(1, min(page_number, total_pages))
        
        start_record = (page_number - 1) * page_size + 1 if total_records > 0 else 0
        end_record = min(page_number * page_size, total_records)
        
        # DEBUG: Información de paginación
        print(f"DEBUG - Páginas: {total_pages}, Rango: {start_record}-{end_record}/{total_records}")
        
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
        import traceback
        traceback.print_exc()
        
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
    
# ==================== DETALLE DE PRODUCTO ====================
@products_bp.route("/producto/<part_number>", methods=["GET"])
def producto_detalle(part_number=None, sku=None):
    """Detalle de producto unificado"""
    # Usar el parámetro que esté disponible
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

        # Precio y disponibilidad
        price_url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
        body = {"products": [{"ingramPartNumber": product_id}]}
        params = {
            "includeAvailability": "true",
            "includePricing": "true",
            "includeProductAttributes": "true"
        }
        precio_res = APIClient.make_request("POST", price_url, params=params, json=body)
        precio = precio_res.json() if precio_res.status_code == 200 else []
        precio_info = precio[0] if isinstance(precio, list) and precio else (precio if isinstance(precio, dict) else {})

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
            producto=detalle,  # Compatibilidad
            p=detalle,         # Alias adicional
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

# ==================== GESTIÓN DE COTIZACIONES (ACTUALIZADO PARA BD) ====================

@products_bp.route("/agregar-cotizacion", methods=["GET", "POST"])
def agregar_cotizacion():
    """Añadir producto a cotización - CON BASE DE DATOS"""
    try:
        if request.method == 'GET':
            part_number = request.args.get('part_number')
            if not part_number:
                return render_template("error.html", error="Número de parte requerido")
            
            # Obtener detalles del producto
            detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
            detalle_res = APIClient.make_request("GET", detail_url)
            
            if detalle_res.status_code != 200:
                return render_template("error.html", error="Producto no encontrado")
            
            detalle = detalle_res.json()
            
            # Obtener precio real de la API
            price_url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
            body = {"products": [{"ingramPartNumber": part_number}]}
            params = {
                "includeAvailability": "true",
                "includePricing": "true",
                "includeProductAttributes": "true"
            }
            precio_res = APIClient.make_request("POST", price_url, params=params, json=body)
            
            real_price = 0
            availability_data = {}
            
            if precio_res.status_code == 200:
                precio_data = precio_res.json()
                if precio_data and isinstance(precio_data, list) and len(precio_data) > 0:
                    first_product = precio_data[0]
                    pricing = first_product.get('pricing', {})
                    customer_price = pricing.get('customerPrice')
                    
                    if customer_price is not None:
                        try:
                            real_price = float(customer_price)
                        except (ValueError, TypeError):
                            real_price = 0
                    
                    availability_data = first_product.get('availability', {})
            
            # Construir datos del producto
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
            quantity = 1
            
        else:
            # POST method
            product_data = {
                'ingramPartNumber': request.form.get('part_number'),
                'description': request.form.get('description'),
                'pricing': {'customerPrice': float(request.form.get('price', 0))},
                'vendorName': request.form.get('vendor', 'N/A'),
                'upc': request.form.get('upc', ''),
                'category': request.form.get('category', ''),
                'availability': {}
            }
            quantity = int(request.form.get('quantity', 1))
        
        user_id = get_current_user_id()
        
        # Usar base de datos en lugar de diccionario en memoria
        add_to_quote(user_id, product_data, quantity)
        
        session['flash_message'] = "Producto agregado a cotización"
        return redirect('/products/mi-cotizacion')
        
    except Exception as e:
        print(f"Error al agregar a cotización: {str(e)}")
        return render_template("error.html", error=f"Error al agregar producto: {str(e)}")

@products_bp.route('/mi-cotizacion', methods=["GET"])
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
            "products/quote.html",
            items=items_with_totals,
            total=round(total, 2),
            formatted_total=f"${total:,.2f} MXN",
            count=len(quote_items),
            flash_message=flash_message
        )
        
    except Exception as e:
        print(f"Error al cargar cotización: {str(e)}")
        return render_template("error.html", error=f"Error al cargar cotización: {str(e)}")

# ==================== GESTIÓN DE FAVORITOS (ACTUALIZADO PARA BD) ====================

@products_bp.route('/agregar-favorito', methods=["POST"])
def agregar_favorito():
    """Añadir/eliminar producto de favoritos - CON BASE DE DATOS"""
    try:
        part_number = request.form.get('part_number')
        
        if not part_number:
            return render_template("errors/error.html", error="Número de parte requerido")
        
        # Si no tenemos descripción, obtenerla de la API
        description = request.form.get('description')
        vendor = request.form.get('vendor')
        
        if not description:
            detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
            detalle_res = APIClient.make_request("GET", detail_url)
            if detalle_res.status_code == 200:
                detalle = detalle_res.json()
                description = detalle.get('description', f"Producto {part_number}")
                vendor = vendor or detalle.get('vendorName', 'N/A')
        
        product_data = {
            'ingramPartNumber': part_number,
            'description': description or f"Producto {part_number}",
            'vendorName': vendor or 'N/A'
        }
        
        user_id = get_current_user_id()
        
        # Usar base de datos en lugar de diccionario en memoria
        action = toggle_favorite(user_id, product_data)
        
        if action == 'added':
            message = "Producto agregado a favoritos"
        else:
            message = "Producto eliminado de favoritos"
        
        session['flash_message'] = message
        return redirect(request.referrer or '/')
        
    except Exception as e:
        print(f"Error con favoritos: {str(e)}")
        return render_template("error.html", error=f"Error con favoritos: {str(e)}")

@products_bp.route('/mis-favoritos', methods=["GET"])
@products_bp.route('/favorites', methods=["GET"])
def mis_favoritos():
    """Página de favoritos del usuario - CON BASE DE DATOS"""
    try:
        user_id = get_current_user_id()
        favorites = get_user_favorites(user_id)
        
        flash_message = session.pop('flash_message', None)
        
        return render_template(
            "products/favorites.html",
            favorites=favorites,
            count=len(favorites),
            flash_message=flash_message,
            get_image_url_enhanced=ImageHandler.get_image_url_enhanced
        )
        
    except Exception as e:
        print(f"Error al cargar favoritos: {str(e)}")
        return render_template("error.html", error=f"Error al cargar favoritos: {str(e)}")
    
@products_bp.route('/eliminar-favorito', methods=["POST"])
def eliminar_favorito():
    """Eliminar producto de favoritos (ruta HTML)"""
    try:
        part_number = request.form.get('part_number')
        
        user_id = get_current_user_id()
        remove_from_favorites(user_id, part_number)
        
        session['flash_message'] = "Producto eliminado de favoritos"
        return redirect('/products/mis-favoritos')
        
    except Exception as e:
        session['flash_message'] = f"Error al eliminar favorito: {str(e)}"
        return redirect('/products/mis-favoritos')

def remove_from_favorites(user_id, part_number):
    """Eliminar producto de favoritos"""
    from app.models.favorite import Favorite
    from app.models.product import Product
    
    product = Product.query.filter_by(ingram_part_number=part_number).first()
    if not product:
        return
    
    favorite = Favorite.query.filter_by(user_id=user_id, product_id=product.id).first()
    if favorite:
        db.session.delete(favorite)
        db.session.commit()

# ==================== APIs JSON (ACTUALIZADAS PARA BD) ====================

@products_bp.route("/api/get-quote", methods=["GET"])
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

@products_bp.route("/api/get-favorites", methods=["GET"])
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

@products_bp.route("/api/check-favorite/<product_id>", methods=["GET"])
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

# ==================== APIs DE GESTIÓN (ACTUALIZADAS PARA BD) ====================

@products_bp.route('/api/update-quote-quantity', methods=['POST'])
def api_update_quote_quantity():
    """Actualizar cantidad en cotización - CON BASE DE DATOS"""
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        user_id = get_current_user_id()
        update_quote_quantity(user_id, product_id, quantity)
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@products_bp.route('/api/remove-from-quote', methods=['POST'])
def api_remove_from_quote():
    """Eliminar producto de cotización - CON BASE DE DATOS"""
    try:
        print("DEBUG: api_remove_from_quote called")
        
        # Manejar tanto JSON como form data
        if request.is_json:
            data = request.get_json()
            product_id = data.get('product_id')
            print(f"DEBUG: JSON request - product_id: {product_id}")
        else:
            # Para formularios tradicionales
            product_id = request.form.get('product_id')
            print(f"DEBUG: Form request - product_id: {product_id}")
        
        if not product_id:
            print("DEBUG: No product_id provided")
            return jsonify({'success': False, 'error': 'product_id requerido'}), 400
        
        user_id = get_current_user_id()
        print(f"DEBUG: User ID: {user_id}, Removing product: {product_id}")
        
        result = remove_from_quote(user_id, product_id)
        
        if result:
            return jsonify({'success': True, 'message': 'Producto eliminado de cotización'})
        else:
            return jsonify({'success': False, 'error': 'Producto no encontrado en cotización'})
        
    except Exception as e:
        print(f"ERROR en api_remove_from_quote: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@products_bp.route('/api/clear-quote', methods=['POST'])
def api_clear_quote():
    """Limpiar cotización completa - CON BASE DE DATOS"""
    try:
        user_id = get_current_user_id()
        clear_user_quote(user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS DE UTILIDAD (ACTUALIZADAS PARA BD) ====================

@products_bp.route('/limpiar-cotizacion', methods=["POST"])
def limpiar_cotizacion():
    """Limpiar cotización (ruta HTML) - CON BASE DE DATOS"""
    try:
        user_id = get_current_user_id()
        clear_user_quote(user_id)
        session['flash_message'] = "Cotización limpiada exitosamente"
        return redirect('/products/mi-cotizacion')
    except Exception as e:
        session['flash_message'] = f"Error al limpiar cotización: {str(e)}"
        return redirect('/products/mi-cotizacion')

@products_bp.route('/actualizar-cantidad-cotizacion', methods=["POST"])
def actualizar_cantidad_cotizacion():
    """Actualizar cantidad (ruta HTML) - CON BASE DE DATOS"""
    try:
        part_number = request.form.get('part_number')
        new_quantity = int(request.form.get('quantity', 1))
        
        if new_quantity < 1:
            session['flash_message'] = "La cantidad debe ser mayor a 0"
            return redirect('/products/mi-cotizacion')
        
        user_id = get_current_user_id()
        update_quote_quantity(user_id, part_number, new_quantity)
        
        session['flash_message'] = f"Cantidad actualizada a {new_quantity}"
        return redirect('/products/mi-cotizacion')
        
    except (ValueError, TypeError):
        session['flash_message'] = "Cantidad inválida"
        return redirect('/products/mi-cotizacion')
    except Exception as e:
        session['flash_message'] = f"Error al actualizar cantidad: {str(e)}"
        return redirect('/products/mi-cotizacion')

# ==================== RUTAS ADICIONALES QUE FALTABAN ====================

@products_bp.route("/limpiar-busqueda", methods=["GET"])
def limpiar_busqueda():
    """Limpiar parámetros de búsqueda y redirigir a página 1"""
    return redirect('/products/catalogo-completo-cards?page=1')

@products_bp.route("/it-data-global", methods=["GET"])
def it_data_global():
    """Redirigir a página 1 del catálogo (para botones)"""
    return redirect('/products/catalogo-completo-cards?page=1')

@products_bp.route("/pagina/<int:page_number>", methods=["GET"])
def ir_a_pagina(page_number):
    """Ir a una página específica manteniendo los filtros actuales"""
    # Mantener todos los parámetros de query excepto 'page'
    args = request.args.copy()
    args['page'] = page_number
    return redirect('/products/catalogo-completo-cards?' + '&'.join([f'{k}={v}' for k, v in args.items()]))

# ==================== RUTAS PARA BOTONES AJAX ====================
@products_bp.route('/api/add-to-quote', methods=['POST'])
def api_add_to_quote():
    """API para agregar producto a cotización"""
    try:
        data = request.get_json()
        part_number = data.get('part_number')
        
        # Obtener cantidad del frontend o usar valor por defecto
        quantity_input = data.get('quantity')
        
        if quantity_input is None:
            # Si no viene cantidad del frontend, usar 1
            quantity = 1
        else:
            try:
                quantity = int(quantity_input)
                # Validar que sea un número positivo
                if quantity < 1:
                    quantity = 1
                if quantity > 999:  # Límite máximo
                    quantity = 999
            except (ValueError, TypeError):
                quantity = 1
        
        print(f"DEBUG - Quantity recibida: {quantity}")
        
        # Obtener datos del producto
        detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
        detalle_res = APIClient.make_request("GET", detail_url)
        
        if detalle_res.status_code != 200:
            return jsonify({'success': False, 'error': 'Producto no encontrado'}), 404
        
        detalle = detalle_res.json()
        
        # Obtener precio y disponibilidad
        price_url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
        body = {"products": [{"ingramPartNumber": part_number}]}
        params = {
            "includeAvailability": "true",
            "includePricing": "true",
            "includeProductAttributes": "true"
        }
        precio_res = APIClient.make_request("POST", price_url, params=params, json=body)
        
        real_price = 0
        availability_data = {}
        
        if precio_res.status_code == 200:
            precio_data = precio_res.json()
            print(f"DEBUG - Precio API response: {precio_data}")  # DEBUG
            
            # La API devuelve un array de productos en la respuesta
            if isinstance(precio_data, list) and len(precio_data) > 0:
                first_product = precio_data[0]
                pricing = first_product.get('pricing', {})
                customer_price = pricing.get('customerPrice')
                
                # Debug del precio
                print(f"DEBUG - Customer price: {customer_price}, Type: {type(customer_price)}")
                
                if customer_price is not None:
                    try:
                        real_price = float(customer_price)
                        print(f"DEBUG - Precio convertido: {real_price}")  # DEBUG
                    except (ValueError, TypeError) as e:
                        print(f"DEBUG - Error convirtiendo precio: {e}")
                        real_price = 0
                else:
                    print("DEBUG - Customer price es None")
                    real_price = 0
                
                availability_data = first_product.get('availability', {})
                print(f"DEBUG - Availability: {availability_data}")  # DEBUG
            else:
                print(f"DEBUG - Formato inesperado de respuesta: {type(precio_data)}")
        else:
            print(f"DEBUG - Error en API precio: {precio_res.status_code}")
        
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
        
        print(f"DEBUG - Product data: {product_data}")  # DEBUG
        
        user_id = get_current_user_id()
        add_to_quote(user_id, product_data, quantity)
        
        return jsonify({
            'success': True,
            'message': f'Producto agregado a cotización (Cantidad: {quantity})',
            'quote_count': len(get_user_quotes(user_id))
        })
        
    except Exception as e:
        print(f"Error en api_add_to_quote: {str(e)}")
        import traceback
        traceback.print_exc()  # Esto mostrará el traceback completo
        return jsonify({'success': False, 'error': str(e)}), 500

@products_bp.route('/api/toggle-favorite', methods=['POST'])
def api_toggle_favorite():
    """API para agregar/eliminar favorito"""
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

# ==================== FUNCIONES FALTANTES ====================

def toggle_favorite(user_id, product_data):
    """Agregar/eliminar producto de favoritos usando nuevos modelos"""
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

def is_product_favorite(user_id, part_number):
    """Verificar si un producto está en favoritos usando nuevos modelos"""
    from app.models.favorite import Favorite
    from app.models.product import Product
    
    # Para usuarios anónimos, siempre retornar false
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
    
def remove_from_quote(user_id, part_number):
    """Eliminar producto de cotización usando nuevos modelos"""
    from app.models.quote import Quote, QuoteItem
    from app.models.product import Product
    
    try:
        print(f"DEBUG: remove_from_quote - User: {user_id}, Part: {part_number}")
        
        # Obtener la cotización del usuario
        quote = Quote.query.filter_by(user_id=user_id, status='draft').first()
        if not quote:
            print("DEBUG: No quote found for user")
            return False
        print(f"DEBUG: Quote found: {quote.id}")
        
        # Buscar el producto en la base de datos local
        product = Product.query.filter_by(ingram_part_number=part_number).first()
        if not product:
            print(f"DEBUG: Product {part_number} not found in database")
            return False
        print(f"DEBUG: Product found: {product.id}")
        
        # Buscar el item en la cotización
        item = QuoteItem.query.filter_by(quote_id=quote.id, product_id=product.id).first()
        if not item:
            print(f"DEBUG: Product {part_number} not found in quote")
            return False
        print(f"DEBUG: Quote item found: {item.id}")
        
        # Eliminar el item
        db.session.delete(item)
        print("DEBUG: Item deleted from session")
        
        # Recalcular el total de la cotización
        quote.calculate_total()
        print("DEBUG: Total recalculated")
        
        # Guardar cambios
        db.session.commit()
        print("DEBUG: Changes committed to database")
        
        print(f"DEBUG: Product {part_number} removed successfully")
        return True
        
    except Exception as e:
        print(f"ERROR in remove_from_quote: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return False    

def update_quote_quantity(user_id, part_number, quantity):
    """Actualizar cantidad en cotización usando nuevos modelos"""
    from app.models.quote import Quote, QuoteItem
    from app.models.product import Product
    
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
    from app.models.quote import Quote
    
    quote = Quote.query.filter_by(user_id=user_id, status='draft').first()
    if quote:
        # Eliminar todos los items de la cotización
        for item in quote.items:
            db.session.delete(item)
        quote.total_amount = 0
        db.session.commit()

def get_user_favorites(user_id):
    """Obtener favoritos del usuario usando los nuevos modelos"""
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
            'favorited_date': fav.created_at.isoformat()
        })
    
    return favorite_list