import requests
from urllib.parse import quote_plus
from flask import current_app
import time
import random

class ImageHandler:
    # Cache para imágenes (evitar llamadas repetidas)
    image_cache = {}
    
    # Lista de User-Agents para rotación
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
    ]

    @staticmethod
    def get_image_url_enhanced(item):
        """
        Función optimizada que usa Vendor Part Number para buscar imágenes.
        Prioridad: SerpAPI (con VPN) -> Unsplash -> Categoría -> Placeholder
        """
        if not item:
            return ImageHandler.generate_custom_placeholder("", "", "", "")
        
        # Obtener Vendor Part Number (prioridad máxima)
        vendor_part = item.get("vendorPartNumber", "").strip()
        sku = item.get("ingramPartNumber", "").strip()
        producto_nombre = item.get("description", "")
        marca = item.get("vendorName", "")
        
        # Cache key usando Vendor Part Number (más específico)
        cache_key = vendor_part if vendor_part else sku
        if cache_key and cache_key in ImageHandler.image_cache:
            return ImageHandler.image_cache[cache_key]
        
        # 1. PRIORIDAD: SerpAPI con Vendor Part Number a través de VPN
        if vendor_part:
            serpapi_image = ImageHandler.get_serpapi_image_vpn(vendor_part, marca, producto_nombre)
            if serpapi_image:
                if cache_key:
                    ImageHandler.image_cache[cache_key] = serpapi_image
                return serpapi_image
        
        # 2. Fallback: SerpAPI con SKU si no hay Vendor Part Number
        if sku and not vendor_part:
            serpapi_image = ImageHandler.get_serpapi_image_vpn(sku, marca, producto_nombre)
            if serpapi_image:
                if cache_key:
                    ImageHandler.image_cache[cache_key] = serpapi_image
                return serpapi_image
        
        # 3. Buscar con Unsplash API como respaldo
        categoria = item.get("category", "")
        subcategoria = item.get("subCategory", "")
        
        search_query = ImageHandler.build_unsplash_query(marca, producto_nombre, sku, vendor_part, categoria, subcategoria)
        unsplash_image = ImageHandler.get_unsplash_image(search_query)
        
        if unsplash_image:
            if cache_key:
                ImageHandler.image_cache[cache_key] = unsplash_image
            return unsplash_image
        
        # 4. Buscar por categoría
        category_image = ImageHandler.get_category_based_image(item)
        if category_image:
            if cache_key:
                ImageHandler.image_cache[cache_key] = category_image
            return category_image
        
        # 5. Fallback con placeholder personalizado
        placeholder = ImageHandler.generate_custom_placeholder(marca, producto_nombre, sku, vendor_part)
        if cache_key:
            ImageHandler.image_cache[cache_key] = placeholder
        return placeholder

    @staticmethod
    def get_serpapi_image_vpn(vendor_part, marca="", producto_nombre=""):
        """
        Busca imágenes usando SerpAPI con Vendor Part Number a través de proxies/VPN
        """
        api_key = current_app.config.get('SERPAPI_KEY')
        if not api_key:
            print("SerpAPI key no configurada")
            return None
        
        try:
            # Construir query optimizada para Vendor Part Number
            search_query = ImageHandler.build_serpapi_query(vendor_part, marca, producto_nombre)
            
            # Configurar parámetros para SerpAPI
            params = {
                "engine": "google_images",
                "q": search_query,
                "api_key": api_key,
                "ijn": "0",  # Página de resultados
                "num": "10",  # Número de resultados
                "device": "desktop",
                "safe": "active"
            }
            
            # Añadir configuración de proxy/VPN si está disponible
            proxy_config = current_app.config.get('PROXY_CONFIG')
            if proxy_config:
                params["proxy"] = proxy_config
            
            url = "https://serpapi.com/search"
            
            # Headers con User-Agent rotatorio
            headers = {
                "User-Agent": random.choice(ImageHandler.USER_AGENTS),
                "Accept": "application/json",
            }
            
            # Realizar la petición con timeout
            response = requests.get(
                url, 
                params=params, 
                headers=headers, 
                timeout=15,
                verify=True  # SSL verification
            )
            
            if response.status_code == 200:
                data = response.json()
                images_results = data.get("images_results", [])
                
                # Priorizar imágenes de alta calidad
                for image in images_results:
                    # Filtrar por tamaño y calidad
                    if ImageHandler.is_high_quality_image(image):
                        image_url = image.get("original")
                        if image_url and ImageHandler._is_valid_image(image_url):
                            print(f"Imagen encontrada con SerpAPI para {vendor_part}: {image_url[:100]}...")
                            return image_url
                
                print(f"SerpAPI: No se encontraron imágenes de calidad para {vendor_part}")
                return None
            
            elif response.status_code == 404:
                print(f"SerpAPI: No se encontraron resultados para {vendor_part}")
                return None
            else:
                print(f"SerpAPI Error: {response.status_code} - {response.text[:200]}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"SerpAPI: Timeout para {vendor_part}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"SerpAPI Request Error para {vendor_part}: {e}")
            return None
        except Exception as e:
            print(f"SerpAPI Unexpected Error para {vendor_part}: {e}")
            return None

    @staticmethod
    def build_serpapi_query(vendor_part, marca="", producto_nombre=""):
        """
        Construye query optimizada para SerpAPI usando Vendor Part Number
        """
        # Limpiar el Vendor Part Number
        clean_vendor_part = vendor_part.strip().replace('"', '').replace("'", "")
        
        # Estrategias de query progresivas
        queries = []
        
        # 1. Query más específica: Vendor Part Number exacto con marca
        if marca:
            queries.append(f'"{clean_vendor_part}" {marca}')
        
        # 2. Vendor Part Number exacto entre comillas
        queries.append(f'"{clean_vendor_part}"')
        
        # 3. Vendor Part Number con términos de producto
        if producto_nombre:
            # Extraer palabras clave del nombre del producto
            product_keywords = " ".join(producto_nombre.split()[:3])
            queries.append(f"{clean_vendor_part} {product_keywords}")
        
        # 4. Vendor Part Number simple
        queries.append(clean_vendor_part)
        
        # Seleccionar la primera query que no sea demasiado larga
        for query in queries:
            if len(query) <= 100:  # Límite de longitud de query
                return query
        
        return clean_vendor_part[:100]  # Fallback truncado

    @staticmethod
    def is_high_quality_image(image_data):
        """
        Filtra imágenes por calidad, tamaño y procedencia
        """
        try:
            # Verificar dimensiones mínimas
            width = image_data.get("original_width", 0)
            height = image_data.get("original_height", 0)
            
            if width < 300 or height < 300:
                return False
            
            # Priorizar imágenes de fuentes confiables
            source = image_data.get("source", "").lower()
            trusted_sources = [
                "amazon", "bestbuy", "newegg", "walmart", "officedepot",
                "cdw", "ingeram", "techdata", "synnex", "dell", "hp",
                "lenovo", "cisco", "official", "manufacturer"
            ]
            
            if any(trusted in source for trusted in trusted_sources):
                return True
            
            # Verificar relación de aspecto (evitar imágenes muy alargadas)
            aspect_ratio = width / height if height > 0 else 0
            if aspect_ratio < 0.5 or aspect_ratio > 2.0:
                return False
            
            # Verificar extensión de archivo
            original_url = image_data.get("original", "").lower()
            valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            if not any(ext in original_url for ext in valid_extensions):
                return False
            
            return True
            
        except Exception:
            return False

    @staticmethod
    def build_unsplash_query(marca, producto_nombre, sku, vendor_part, categoria, subcategoria):
        """Construye query para Unsplash (ahora como respaldo)"""
        # Misma implementación que antes, pero ahora es respaldo
        if vendor_part and len(vendor_part) > 3:
            return f"{marca} {vendor_part} {producto_nombre.split()[0] if producto_nombre else ''}"
        
        if sku and marca:
            return f"{marca} {sku}"
        
        if categoria and subcategoria:
            return f"{marca} {categoria} {subcategoria} {producto_nombre.split()[0] if producto_nombre else ''}"
        
        if marca and producto_nombre:
            nombre_limpio = " ".join(producto_nombre.replace(",", "").replace("-", " ").split()[:3])
            return f"{marca} {nombre_limpio}"
        
        if sku:
            return f"{sku}"
        
        return f"{categoria} {subcategoria}"

    @staticmethod
    def get_unsplash_image(search_query):
        """Unsplash como respaldo (implementación existente)"""
        # Mantener la misma implementación que ya tenías
        api_key = current_app.config.get('UNSPLASH_ACCESS_KEY')
        if not api_key:
            return None
        
        try:
            url = "https://api.unsplash.com/search/photos"
            queries_to_try = [
                f"{search_query} technology product",
                f"{search_query} tech device", 
                f"{search_query} computer",
                search_query,
                "technology product"
            ]
            
            for query in queries_to_try:
                params = {
                    "query": query,
                    "per_page": 5,
                    "orientation": "squarish",
                    "content_filter": "high",
                    "order_by": "relevant"
                }
                headers = {
                    "Authorization": f"Client-ID {api_key}",
                    "Accept-Version": "v1"
                }
                
                response = requests.get(url, params=params, headers=headers, timeout=6)
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    
                    for result in results:
                        urls = result.get("urls", {})
                        image_url = urls.get("regular") or urls.get("small") or urls.get("thumb")
                        if image_url:
                            return image_url
                    
                    continue
                
                elif response.status_code == 403:
                    print("Unsplash API rate limit alcanzado")
                    break
            
        except Exception as e:
            print(f"Error con Unsplash API: {e}")
        
        return None

    @staticmethod
    def get_category_based_image(item):
        """Mapeo por categoría (implementación existente)"""
        # Mantener la misma implementación que ya tenías
        if not item:
            return None
            
        descripcion = item.get("description", "").lower() if item.get("description") else ""
        marca = item.get("vendorName", "").lower() if item.get("vendorName") else ""
        categoria = item.get("category", "").lower() if item.get("category") else ""
        subcategoria = item.get("subCategory", "").lower() if item.get("subCategory") else ""
        
        category_mapping = {
            # ... (mantener tu mapeo existente de categorías)
            ("laptop", "notebook", "elitebook", "thinkpad", "macbook", "ultrabook"): 
                "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400&h=400&fit=crop&auto=format&q=80",
            # ... resto del mapeo
        }
        
        text_to_search = f"{descripcion} {marca} {categoria} {subcategoria}".lower()
        
        for keywords, image_url in category_mapping.items():
            if any(keyword in text_to_search for keyword in keywords):
                return image_url
        
        return None

    @staticmethod
    def generate_custom_placeholder(marca, producto_nombre, sku, vendor_part):
        """Placeholder personalizado (implementación existente)"""
        # Mantener la misma implementación que ya tenías
        try:
            from urllib.parse import quote_plus
            
            if vendor_part and len(vendor_part) <= 20:
                text = f"P/N: {vendor_part}"
                color = "F15A29"
            elif marca and len(marca) <= 20:
                text = marca.upper()
                brand_colors = {
                    "HP": "1C2A2F", "DELL": "1C2A2F", "CISCO": "1C2A2F",
                    "APPLE": "1C2A2F", "LENOVO": "F15A29", "MICROSOFT": "1C2A2F",
                    "INTEL": "1C2A2F", "AMD": "F15A29", "JABRA": "1C2A2F"
                }
                color = brand_colors.get(marca.upper(), "6C757D")
            elif sku and len(sku) <= 20:
                text = f"SKU: {sku}"
                color = "F15A29"
            elif producto_nombre:
                words = producto_nombre.replace(",", "").split()[:3]
                text = " ".join(words).upper()
                if len(text) > 25:
                    text = text[:25] + "..."
                color = "6C757D"
            else:
                text = "IT DATA GLOBAL"
                color = "1C2A2F"
            
            encoded_text = quote_plus(text)
            return f"https://via.placeholder.com/400x400/{color}/FFFFFF?text={encoded_text}&font_size=16"
            
        except Exception:
            return "https://via.placeholder.com/400x400/1C2A2F/FFFFFF?text=IT+DATA+GLOBAL"

    @staticmethod
    def _is_valid_image(url):
        """Valida que la URL sea una imagen válida."""
        if not url or not url.startswith(('http://', 'https://')):
            return False
        
        blocked = ['facebook.com', 'instagram.com', 'pinterest.com', 'twitter.com']
        if any(domain in url.lower() for domain in blocked):
            return False
        
        indicators = ['.jpg', '.jpeg', '.png', '.gif', '.webp', 'image', 'img']
        return any(indicator in url.lower() for indicator in indicators)