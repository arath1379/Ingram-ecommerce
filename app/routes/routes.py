from app import app
from app.models.product_utils import ProductUtils
from app.models.api_client import APIClient
from app.models.image_handler import ImageHandler
import json
from datetime import datetime
from flask import render_template, request, jsonify, session, redirect
import time  # Import añadido

user_quotes = {}  # Diccionario para almacenar cotizaciones por usuario
user_favorites = {}

@app.route("/catalogo-completo-cards", methods=["GET"])
def catalogo_completo_cards():
    # Parámetros de búsqueda
    page_number = int(request.args.get("page", 1))
    page_size = 25
    query = request.args.get("q", "").strip()
    vendor = request.args.get("vendor", "").strip()
    
    # CORRECCIÓN PRINCIPAL: Activar búsqueda por palabras clave cuando hay consulta
    use_keywords = bool(query)  # Activar keywords solo cuando hay búsqueda de texto
    
    print(f"Búsqueda - Query: '{query}', Vendor: '{vendor}', Keywords: {use_keywords}")
    
    # Realizar la búsqueda híbrida CON palabras clave activadas
    productos, total_records, pagina_vacia = ProductUtils.buscar_productos_hibrido(
        query=query, 
        vendor=vendor, 
        page_number=page_number, 
        page_size=page_size, 
        use_keywords=use_keywords  # ← ESTO ES LO QUE FALTABA
    )
    
    print(f"Resultados: {len(productos)} productos de {total_records} total")
    
    # Determinar si mostrar mensaje de bienvenida solo cuando realmente no hay productos
    welcome_message = (page_number == 1 and len(productos) == 0 and not query and not vendor and not pagina_vacia)
    
    # Manejo inteligente de la paginación
    if pagina_vacia and page_number > 1:
        # Si la página está vacía, estimar el total real
        total_real_estimado = max(0, (page_number - 1) * page_size)
        total_records = total_real_estimado
    
    # Aplicar límite máximo conservador para evitar páginas infinitas
    MAX_RECORDS_LIMIT = app.config.get('MAX_RECORDS_LIMIT', 10000)
    if total_records > MAX_RECORDS_LIMIT:
        total_records = MAX_RECORDS_LIMIT
    
    # Cálculos para paginación ajustados
    total_pages = max(1, (total_records // page_size) + (1 if total_records % page_size else 0))
    
    # Ajustar página actual si excede el límite real
    if pagina_vacia and page_number > total_pages:
        page_number = total_pages
    
    start_record = (page_number - 1) * page_size + 1 if total_records > 0 else 0
    end_record = min(page_number * page_size, total_records)
    
    # Si no hay productos en esta página, ajustar la información mostrada
    if pagina_vacia and page_number > 1:
        end_record = start_record - 1
        start_record = 0

    return render_template(
        "catalog.html",
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
        welcome_message=welcome_message,
        local_vendors=ProductUtils.get_local_vendors(),
        get_image_url_enhanced=ImageHandler.get_image_url_enhanced,
        get_availability_text=ProductUtils.get_availability_text,
        format_currency=ProductUtils.format_currency,
        use_keywords=use_keywords,
        suggested_keywords=ProductUtils.sugerir_palabras_clave(query) if query else []
    )

# Ruta adicional para probar la búsqueda por palabras clave específicamente
@app.route("/test-keywords", methods=["GET"])
def test_keywords():
    """Ruta de prueba para verificar la búsqueda por palabras clave"""
    query = request.args.get("q", "laptop gaming").strip()
    
    # Probar ambos métodos
    productos_normal, total_normal, _ = ProductUtils.buscar_productos_hibrido(query, "", 1, 10, False)
    productos_keywords, total_keywords, _ = ProductUtils.buscar_productos_hibrido(query, "", 1, 10, True)
    
    return {
        "query": query,
        "search_terms": ProductUtils.find_matching_search_terms(query),
        "suggested_keywords": ProductUtils.sugerir_palabras_clave(query),
        "normal_search": {
            "count": len(productos_normal),
            "total": total_normal,
            "products": [p.get('description', '')[:100] for p in productos_normal[:5]]
        },
        "keyword_search": {
            "count": len(productos_keywords),
            "total": total_keywords,
            "products": [p.get('description', '')[:100] for p in productos_keywords[:5]]
        }
    }

@app.route("/producto/<part_number>", methods=["GET"])
def producto_detalle(part_number):
    # Detalle (catalog/details)
    detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
    detalle_res = APIClient.make_request("GET", detail_url)
    detalle = detalle_res.json() if detalle_res.status_code == 200 else {}

    # LLAMADA ADICIONAL: Obtener extraDescription del endpoint de catálogo
    catalog_url = "https://api.ingrammicro.com/resellers/v6/catalog"
    params = {
        "pageSize": 1,
        "pageNumber": 1,
        "partNumber": part_number   # <- CORRECCIÓN AQUÍ
    }
    catalog_res = APIClient.make_request("GET", catalog_url, params=params)
    catalog_data = catalog_res.json() if catalog_res.status_code == 200 else {}

    # Extraer extraDescription del catálogo
    extra_description = None
    if isinstance(catalog_data, dict) and catalog_data.get("catalog"):
        productos = catalog_data["catalog"]
        if isinstance(productos, list) and len(productos) > 0:
            producto = productos[0]
            extra_description = producto.get("extraDescription")

    # Precio y disponibilidad (priceandavailability)
    price_url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
    body = {"products": [{"ingramPartNumber": part_number}]}
    params = {
        "includeAvailability": "true",
        "includePricing": "true",
        "includeProductAttributes": "true"
    }
    precio_res = APIClient.make_request("POST", price_url, params=params, json=body)
    precio = precio_res.json() if precio_res.status_code == 200 else []
    precio_info = precio[0] if isinstance(precio, list) and precio else (precio if isinstance(precio, dict) else {})

    # Obtener pricing y aplicar 10%
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

    # Extraer atributos con formatos posibles
    atributos = []
    raw_attrs = detalle.get("productAttributes") or detalle.get("attributes") or []
    if isinstance(raw_attrs, list):
        for a in raw_attrs:
            # tratar distintos nombres de campo
            name = a.get("name") or a.get("attributeName") or a.get("key") or None
            value = a.get("value") or a.get("attributeValue") or a.get("val") or ""
            if name:
                atributos.append({"name": name, "value": value})

    # Usar la función mejorada para obtener imagen
    imagen_url = ImageHandler.get_image_url_enhanced(detalle)
    
    # Obtener la descripción completa del producto para la página de detalles
    descripcion_completa = detalle.get("description") or detalle.get("productDescription") or ""
    
    return render_template(
        "product_detail.html",
        detalle=detalle,
        precio_final=precio_final,
        disponibilidad=disponibilidad,
        atributos=atributos,
        imagen_url=imagen_url,
        part_number=part_number,
        extra_description=extra_description,  # Para usar en las cards
        descripcion_completa=descripcion_completa  # Para usar en la página de detalles
    )

#función helper para obtener user_id
def get_current_user_id():
    """Obtener ID del usuario actual de la sesión"""
    return session.get('user_id', 'anonymous_user')

@app.route("/agregar-cotizacion", methods=["GET", "POST"])
def agregar_cotizacion():
    """Añadir producto a cotización - CORRECCIÓN FINAL"""
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
            
            # Obtener precio REAL de la API
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
                print(f"DEBUG - Respuesta completa: {json.dumps(precio_data, indent=2)}")
                
                if precio_data and isinstance(precio_data, list) and len(precio_data) > 0:
                    first_product = precio_data[0]
                    
                    # ACCEDER CORRECTAMENTE AL PRICING
                    pricing = first_product.get('pricing', {})
                    customer_price = pricing.get('customerPrice')
                    
                    print(f"DEBUG - Pricing section: {pricing}")
                    print(f"DEBUG - Customer price raw: {customer_price} (type: {type(customer_price)})")
                    
                    # El customerPrice ya es un número, no string
                    if customer_price is not None:
                        try:
                            real_price = float(customer_price)
                            print(f"DEBUG - Precio convertido: {real_price}")
                        except (ValueError, TypeError):
                            real_price = 0
                    
                    availability_data = first_product.get('availability', {})
            
            print(f"DEBUG - Precio final que se guardará: {real_price}")
            
            # Construir datos del producto
            product_data = {
                'ingramPartNumber': part_number,
                'description': detalle.get('description', f"Producto {part_number}"),
                'pricing': {'customerPrice': real_price},  # Precio base SIN markup
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
        
        if user_id not in user_quotes:
            user_quotes[user_id] = []
        
        # Verificar si ya existe
        existing_item = None
        for item in user_quotes[user_id]:
            if item['product']['ingramPartNumber'] == product_data['ingramPartNumber']:
                existing_item = item
                break
        
        if existing_item:
            existing_item['quantity'] += quantity
            mensaje = f"Cantidad actualizada: {existing_item['quantity']} unidades"
        else:
            user_quotes[user_id].append({
                'product': product_data,
                'quantity': quantity,
                'added_date': datetime.now().isoformat()
            })
            mensaje = "Producto agregado a cotización"
        
        session['flash_message'] = mensaje
        return redirect('/mi-cotizacion')
        
    except Exception as e:
        print(f"ERROR - Error al agregar a cotización: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template("error.html", error=f"Error al agregar producto: {str(e)}")

@app.route('/agregar-favorito', methods=["POST"])
def agregar_favorito():
    """Añadir/eliminar producto de favoritos - Versión mejorada"""
    try:
        part_number = request.form.get('part_number')
        
        if not part_number:
            return render_template("error.html", error="Número de parte requerido")
        
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
        
        if user_id not in user_favorites:
            user_favorites[user_id] = []
        
        product_id = product_data['ingramPartNumber']
        existing_index = -1
        for i, fav in enumerate(user_favorites[user_id]):
            if fav['ingramPartNumber'] == product_id:
                existing_index = i
                break
        
        if existing_index >= 0:
            user_favorites[user_id].pop(existing_index)
            message = "Producto eliminado de favoritos"
        else:
            product_data['favorited_date'] = datetime.now().isoformat()
            user_favorites[user_id].append(product_data)
            message = "Producto agregado a favoritos"
        
        # Agregar mensaje flash
        session['flash_message'] = message
        
        # Redirigir de vuelta a donde venía el usuario
        return redirect(request.referrer or '/')
        
    except Exception as e:
        print(f"Error con favoritos: {str(e)}")
        return render_template("error.html", error=f"Error con favoritos: {str(e)}")

@app.route('/mi-cotizacion', methods=["GET"])
def mi_cotizacion():
    """Página HTML de la cotización - Con formato de peso mexicano"""
    try:
        user_id = get_current_user_id()
        quote_items = user_quotes.get(user_id, [])
        
        print(f"DEBUG - Cargando cotización para usuario: {user_id}")
        print(f"DEBUG - Número de items: {len(quote_items)}")
        
        total = 0
        items_with_totals = []
        
        for i, item in enumerate(quote_items):
            pricing_info = item['product'].get('pricing', {})
            base_price = pricing_info.get('customerPrice', 0)
            quantity = item['quantity']
            
            print(f"DEBUG Item {i}: {item['product'].get('ingramPartNumber')}")
            print(f"  - Precio base: {base_price} MXP")
            
            try:
                # Convertir precio a float
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
                
                print(f"  - Precio unitario con markup: ${unit_price_with_markup} MXN")
                print(f"  - Total del item: ${item_total} MXN")
                
                # FORMATO CORRECTO PARA PESOS MEXICANOS
                item_data = {
                    **item,
                    'unit_price': unit_price_with_markup,
                    'total_price': item_total,
                    'formatted_unit_price': f"${unit_price_with_markup:,.2f} MXN",
                    'formatted_total_price': f"${item_total:,.2f} MXN"
                }
                    
            except (ValueError, TypeError) as e:
                print(f"  - ERROR procesando precio: {e}")
                item_data = {
                    **item,
                    'unit_price': 0,
                    'total_price': 0,
                    'formatted_unit_price': 'No disponible',
                    'formatted_total_price': 'No disponible'
                }
            
            items_with_totals.append(item_data)
        
        print(f"DEBUG - Total final: ${total} MXN")
        
        flash_message = session.pop('flash_message', None)
        
        return render_template(
            "quote.html",
            items=items_with_totals,
            total=round(total, 2),
            formatted_total=f"${total:,.2f} MXN",  # FORMATO CORRECTO
            count=len(quote_items),
            flash_message=flash_message
        )
        
    except Exception as e:
        print(f"ERROR - Error al cargar cotización: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template("error.html", error=f"Error al cargar cotización: {str(e)}")

@app.route('/actualizar-cantidad-cotizacion', methods=["POST"])
def actualizar_cantidad_cotizacion():
    """Actualizar cantidad de un producto en la cotización"""
    try:
        part_number = request.form.get('part_number')
        new_quantity = int(request.form.get('quantity', 1))
        
        if new_quantity < 1:
            session['flash_message'] = "La cantidad debe ser mayor a 0"
            return redirect('/mi-cotizacion')
        
        user_id = get_current_user_id()
        
        if user_id in user_quotes:
            for item in user_quotes[user_id]:
                if item['product']['ingramPartNumber'] == part_number:
                    old_quantity = item['quantity']
                    item['quantity'] = new_quantity
                    session['flash_message'] = f"Cantidad actualizada de {old_quantity} a {new_quantity}"
                    break
        
        return redirect('/mi-cotizacion')
        
    except (ValueError, TypeError):
        session['flash_message'] = "Cantidad inválida"
        return redirect('/mi-cotizacion')
    except Exception as e:
        print(f"Error al actualizar cantidad: {str(e)}")
        return render_template("error.html", error=f"Error al actualizar cantidad: {str(e)}")

# 6. Mejorar manejo de errores globalmente
@app.errorhandler(404)
def page_not_found(e):
    """Manejador para páginas no encontradas"""
    return jsonify({
        'success': False,
        'error': 'Página no encontrada',
        'status_code': 404
    }), 404

@app.errorhandler(500)
def internal_error(e):
    """Manejador para errores internos del servidor"""
    return jsonify({
        'success': False,
        'error': 'Error interno del servidor',
        'status_code': 500
    }), 500

@app.route("/api/check-favorite/<product_id>", methods=["GET"])
def api_check_favorite(product_id):
    """Verificar si un producto está en favoritos - JSON response"""
    try:
        user_id = session.get('user_id', 'anonymous_user')
        favorites = user_favorites.get(user_id, [])
        
        # Buscar el producto en favoritos
        is_favorite = False
        for fav in favorites:
            if fav.get('ingramPartNumber') == product_id:
                is_favorite = True
                break
        
        return jsonify({
            'success': True,
            'is_favorite': is_favorite,
            'favorites_count': len(favorites)
        })
        
    except Exception as e:
        print(f"Error checking favorite: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'is_favorite': False
        }), 500
    
# 1. Ruta de favoritos (parece que la tienes como /mis-favoritos pero se llama /favoritos)
@app.route('/favoritos', methods=["GET"])
def favoritos():
    """Redirigir a la ruta correcta de favoritos"""
    return redirect('/mis-favoritos')

# O si prefieres que /favoritos sea la ruta principal:
@app.route('/favoritos', methods=["GET"])
def favoritos_main():
    """Página HTML de favoritos del usuario"""
    try:
        user_id = session.get('user_id', 'anonymous_user')
        favorites = user_favorites.get(user_id, [])
        
        return render_template(
            "favorites.html",
            favorites=favorites,
            count=len(favorites)
        )
        
    except Exception as e:
        print(f"Error al cargar favoritos: {str(e)}")
        return render_template("error.html", error=f"Error al cargar favoritos: {str(e)}")

@app.route("/api/get-quote", methods=["GET"])
def api_get_quote():
    """API para obtener cotización actual - JSON response"""
    try:
        user_id = session.get('user_id', 'anonymous_user')
        quote_items = user_quotes.get(user_id, [])
        
        # Calcular totales y preparar datos para el frontend
        total = 0
        items_with_totals = []
        
        for item in quote_items:
            price_str = item['product'].get('pricing', {}).get('customerPrice', '0')
            quantity = item['quantity']
            
            try:
                # Convertir el precio a float, manejando diferentes formatos
                if isinstance(price_str, str):
                    # Limpiar el string de caracteres no numéricos excepto punto decimal
                    clean_price = ''.join(c for c in price_str if c.isdigit() or c == '.')
                    base_price = float(clean_price) if clean_price else 0.0
                else:
                    base_price = float(price_str)
                
                # Aplicar markup del 10%
                unit_price_with_markup = round(base_price * 1.10, 2)
                item_total = unit_price_with_markup * quantity
                total += item_total
                
                # Crear item con la estructura que espera el frontend
                item_data = {
                    'product': {
                        'ingramPartNumber': item['product']['ingramPartNumber'],
                        'description': item['product']['description'],
                        'vendorName': item['product']['vendorName'],
                        'pricing': {
                            'customerPrice': unit_price_with_markup  # Precio CON markup
                        },
                        'extraDescription': item['product'].get('extraDescription', ''),
                        'availability': item['product'].get('availability', {})
                    },
                    'quantity': quantity,
                    'unit_price': unit_price_with_markup,
                    'total_price': item_total
                }
                
            except (ValueError, TypeError) as e:
                print(f"Error procesando precio: {price_str}, error: {e}")
                item_data = {
                    'product': {
                        **item['product'],
                        'pricing': {
                            'customerPrice': 0
                        }
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
        print(f"Error al obtener cotización: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'items': [],
            'count': 0,
            'total': 0
        }), 500

# 3. API para obtener favoritos (si la necesitas)
@app.route("/api/get-favorites", methods=["GET"])
def api_get_favorites():
    """API para obtener favoritos - JSON response"""
    try:
        user_id = session.get('user_id', 'anonymous_user')
        favorites = user_favorites.get(user_id, [])
        
        return jsonify({
            'success': True,
            'favorites': favorites,
            'count': len(favorites)
        })
        
    except Exception as e:
        print(f"Error al obtener favoritos: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'favorites': [],
            'count': 0
        }), 500

# 4. Ruta para limpiar cotización
@app.route('/limpiar-cotizacion', methods=["POST"])
def limpiar_cotizacion():
    """Limpiar toda la cotización"""
    try:
        user_id = session.get('user_id', 'anonymous_user')
        user_quotes[user_id] = []
        
        session['flash_message'] = "Cotización limpiada exitosamente"
        return redirect('/mi-cotizacion')
        
    except Exception as e:
        print(f"Error al limpiar cotización: {str(e)}")
        session['flash_message'] = f"Error al limpiar cotización: {str(e)}"
        return redirect('/mi-cotizacion')

# 5. Ruta para actualizar cantidad (si no la tienes)
@app.route('/actualizar-cantidad', methods=["POST"])
def actualizar_cantidad():
    """Actualizar cantidad de producto en cotización"""
    try:
        part_number = request.form.get('part_number')
        new_quantity = int(request.form.get('quantity', 1))
        
        if new_quantity < 1:
            session['flash_message'] = "La cantidad debe ser mayor a 0"
            return redirect('/mi-cotizacion')
        
        user_id = session.get('user_id', 'anonymous_user')
        
        if user_id in user_quotes:
            for item in user_quotes[user_id]:
                if item['product']['ingramPartNumber'] == part_number:
                    old_quantity = item['quantity']
                    item['quantity'] = new_quantity
                    session['flash_message'] = f"Cantidad actualizada de {old_quantity} a {new_quantity}"
                    break
            else:
                session['flash_message'] = "Producto no encontrado en cotización"
        
        return redirect('/mi-cotizacion')
        
    except (ValueError, TypeError):
        session['flash_message'] = "Cantidad inválida"
        return redirect('/mi-cotizacion')
    except Exception as e:
        print(f"Error al actualizar cantidad: {str(e)}")
        session['flash_message'] = f"Error al actualizar cantidad: {str(e)}"
        return redirect('/mi-cotizacion')

# 6. Mejorar el manejo de la ruta de compatibilidad existente
@app.route("/api/get-quote-compat", methods=["GET"])
def api_get_quote_compat_old():
    """Compatibilidad antigua - redirigir a página HTML"""
    return redirect('/mi-cotizacion')

@app.route("/api/get-favorites-compat", methods=["GET"])
def api_get_favorites_compat_old():
    """Compatibilidad antigua - redirigir a página HTML"""
    return redirect('/mis-favoritos')

@app.route('/api/submit-quote', methods=["POST"])
def api_submit_quote():
    """API para enviar cotización por email - JSON response"""
    try:
        data = request.get_json()
        user_info = data.get('user_info', {})
        user_id = session.get('user_id', 'anonymous_user')
        
        quote_items = user_quotes.get(user_id, [])
        
        if not quote_items:
            return jsonify({'success': False, 'error': 'La cotización está vacía'})
        
        # Aquí iría la lógica real para enviar el email
        print(f"Cotización enviada para: {user_info}")
        print(f"Productos: {len(quote_items)}")
        
        # Limpiar cotización después de enviar
        user_quotes[user_id] = []
        
        return jsonify({
            'success': True,
            'message': 'Cotización enviada exitosamente',
            'quote_id': f"QT{datetime.now().strftime('%Y%m%d%H%M%S')}"
        })
        
    except Exception as e:
        print(f"Error al enviar cotización: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/mis-favoritos', methods=["GET"])
def mis_favoritos():
    """Página HTML de favoritos del usuario"""
    try:
        user_id = session.get('user_id', 'anonymous_user')
        favorites = user_favorites.get(user_id, [])
        
        # Obtener y limpiar mensaje flash
        flash_message = session.pop('flash_message', None)
        
        return render_template(
            "favorites.html",
            favorites=favorites,
            count=len(favorites),
            flash_message=flash_message,
            get_image_url_enhanced=ImageHandler.get_image_url_enhanced
        )
        
    except Exception as e:
        print(f" Error al cargar favoritos: {str(e)}")
        return render_template("error.html", error=f"Error al cargar favoritos: {str(e)}")  
    
# NUEVAS RUTAS API CORREGIDAS (usando user_quotes en lugar de session['quote'])
@app.route('/api/update-quote-quantity', methods=['POST'])
def api_update_quote_quantity():
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        user_id = get_current_user_id()
        
        if user_id in user_quotes:
            for item in user_quotes[user_id]:
                if item['product']['ingramPartNumber'] == product_id:
                    item['quantity'] = max(1, quantity)
                    break
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/remove-from-quote', methods=['POST'])
def api_remove_from_quote():
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        
        user_id = get_current_user_id()
        
        if user_id in user_quotes:
            user_quotes[user_id] = [item for item in user_quotes[user_id] 
                                  if item['product']['ingramPartNumber'] != product_id]
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/clear-quote', methods=['POST'])
def api_clear_quote():
    try:
        user_id = get_current_user_id()
        user_quotes[user_id] = []
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500