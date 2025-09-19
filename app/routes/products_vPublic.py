# app/routes/products.py (versión optimizada)
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

# ==================== RUTAS PRINCIPALES ====================

@products_bp.route("/catalogo-completo-cards", methods=["GET"])
@products_bp.route("/catalog", methods=["GET"])
def catalogo_completo_cards():
    """Catálogo principal - Determina automáticamente si es público o con descuento"""
    # Parámetros de búsqueda
    page_number = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 25))
    query = request.args.get("q", "").strip()
    vendor = request.args.get("vendor", "").strip()
    
    # Determinar si es usuario público o con descuento
    is_public = is_public_user()
    
    try:
        # Realizar la búsqueda
        productos, total_records, pagina_vacia = ProductUtils.buscar_productos_hibrido(
            query=query, 
            vendor=vendor, 
            page_number=page_number, 
            page_size=page_size, 
            use_keywords=bool(query)
        )
        
        # Aplicar precios según el tipo de usuario
        for producto in productos:
            apply_user_pricing(producto, is_public)
        
        # Cálculos de paginación
        total_pages = max(1, (total_records + page_size - 1) // page_size) if total_records > 0 else 1
        page_number = max(1, min(page_number, total_pages))
        
        start_record = (page_number - 1) * page_size + 1 if total_records > 0 else 0
        end_record = min(page_number * page_size, total_records)
        
        return render_template(
            "products/catalog.html",  # MISMO TEMPLATE
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
            suggested_keywords=ProductUtils.sugerir_palabras_clave(query) if query else [],
            is_public=is_public,  # Variable clave para el template
            add_to_quote_endpoint='products.agregar_cotizacion_publico' if is_public else 'products.agregar_cotizacion'
        )
    
    except Exception as e:
        print(f"ERROR en catálogo: {str(e)}")
        return render_template("products/catalog.html", 
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
                             is_public=is_public)

# ==================== DETALLE DE PRODUCTO ====================

@products_bp.route("/producto/<part_number>", methods=["GET"])
@products_bp.route("/product/<part_number>", methods=["GET"])
def producto_detalle(part_number):
    """Detalle de producto - Adapta precios según tipo de usuario"""
    if not part_number:
        return render_template("errors/404.html", message="Producto no encontrado"), 404
    
    is_public = is_public_user()
    
    try:
        # Detalle del producto
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
        precio = precio_res.json() if precio_res.status_code == 200 else []
        precio_info = precio[0] if isinstance(precio, list) and precio else (precio if isinstance(precio, dict) else {})

        # Aplicar precio según tipo de usuario
        pricing = precio_info.get("pricing") or {}
        base_price = pricing.get("customerPrice")
        currency = pricing.get("currencyCode") or pricing.get("currency") or ""
        
        if is_public:
            # Precio sin markup para público
            precio_final = ProductUtils.format_currency(base_price, currency) if base_price is not None else "No disponible"
        else:
            # Precio con markup para clientes
            precio_final_val = round(float(base_price) * 1.10, 2) if base_price is not None else None
            precio_final = ProductUtils.format_currency(precio_final_val, currency) if precio_final_val is not None else "No disponible"

        # Resto del código igual...
        disponibilidad = ProductUtils.get_availability_text(precio_info, detalle)

        atributos = []
        raw_attrs = detalle.get("productAttributes") or detalle.get("attributes") or []
        if isinstance(raw_attrs, list):
            for a in raw_attrs:
                name = a.get("name") or a.get("attributeName") or a.get("key") or None
                value = a.get("value") or a.get("attributeValue") or a.get("val") or ""
                if name:
                    atributos.append({"name": name, "value": value})

        imagen_url = ImageHandler.get_image_url_enhanced(detalle)
        descripcion_completa = detalle.get("description") or detalle.get("productDescription") or ""
        
        return render_template(
            "products/product_detail.html",  # MISMO TEMPLATE
            detalle=detalle,
            precio_final=precio_final,
            disponibilidad=disponibilidad,
            atributos=atributos,
            imagen_url=imagen_url,
            part_number=part_number,
            descripcion_completa=descripcion_completa,
            is_public=is_public,  # Variable para el template
            add_to_quote_endpoint='products.agregar_cotizacion_publico' if is_public else 'products.agregar_cotizacion'
        )
    
    except Exception as e:
        print(f"Error obteniendo detalle del producto {part_number}: {str(e)}")
        return render_template("errors/500.html", message="Error al cargar el detalle del producto"), 500

# ==================== FUNCIONES AUXILIARES ====================

def is_public_user():
    """Determina si el usuario actual es público"""
    user_id = get_current_user_id()
    
    # Si es usuario anónimo, es público
    if user_id == 'anonymous_user':
        return True
    
    # Si está logueado pero no es cliente empresarial, es público
    # (Aquí debes implementar tu lógica de verificación de usuario)
    try:
        user = User.query.get(user_id)
        if user and hasattr(user, 'user_type'):
            return user.user_type != 'business' and not user.is_admin
    except:
        pass
    
    return True

def apply_user_pricing(producto, is_public):
    """Aplica precios según el tipo de usuario"""
    if not is_public:
        # Aplicar markup del 10% para clientes
        pricing = producto.get('pricing', {})
        base_price = pricing.get('customerPrice')
        
        if base_price is not None:
            try:
                precio_con_markup = round(float(base_price) * 1.10, 2)
                pricing['customerPrice'] = precio_con_markup
                producto['pricing'] = pricing
            except (ValueError, TypeError):
                pass

# ==================== RUTAS DE COTIZACIÓN ====================

@products_bp.route("/agregar-cotizacion", methods=["POST"])
def agregar_cotizacion():
    """Añadir producto a cotización CON markup (para clientes)"""
    return add_to_quote_handler(with_markup=True)

@products_bp.route("/agregar-cotizacion-publico", methods=["POST"])
def agregar_cotizacion_publico():
    """Añadir producto a cotización SIN markup (para público)"""
    return add_to_quote_handler(with_markup=False)

def add_to_quote_handler(with_markup=True):
    """Manejador común para agregar a cotización"""
    try:
        part_number = request.form.get('part_number')
        if not part_number:
            return render_template("error.html", error="Número de parte requerido")
        
        # Obtener detalles del producto
        detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
        detalle_res = APIClient.make_request("GET", detail_url)
        
        if detalle_res.status_code != 200:
            return render_template("error.html", error="Producto no encontrado")
        
        detalle = detalle_res.json()
        
        # Obtener precio real
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
                        # Aplicar markup si corresponde
                        if with_markup:
                            real_price = round(real_price * 1.10, 2)
                    except (ValueError, TypeError):
                        real_price = 0
                
                availability_data = first_product.get('availability', {})
        
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
        
        quantity = int(request.form.get('quantity', 1))
        user_id = get_current_user_id()
        
        # Usar la función de cotización apropiada
        if with_markup:
            add_to_quote(user_id, product_data, quantity)
        else:
            add_to_quote_public(user_id, product_data, quantity)
        
        session['flash_message'] = "Producto agregado a cotización"
        return redirect('/products/mi-cotizacion')
        
    except Exception as e:
        print(f"Error al agregar a cotización: {str(e)}")
        return render_template("error.html", error=f"Error al agregar producto: {str(e)}")