import requests
from urllib.parse import quote_plus
from flask import current_app
from app.models.api_client import APIClient  # ✅ Import corregido

class ImageHandler:
    # Cache para imágenes (evitar llamadas repetidas)
    image_cache = {}

    @staticmethod
    def get_image_url_enhanced(item):
        """
        Función optimizada que usa información específica del producto para buscar imágenes.
        Prioridad: Ingram -> Cache -> Categoría -> Unsplash -> Placeholder personalizado
        """
        if not item:
            return ImageHandler.generate_custom_placeholder("", "", "", "")
        
        # 1. Intentar imagen de Ingram primero
        try:
            imgs = item.get("productImages") or item.get("productImageList") or []
            if imgs and isinstance(imgs, list) and len(imgs) > 0:
                first = imgs[0]
                ingram_url = first.get("url") or first.get("imageUrl") or first.get("imageURL")
                if ingram_url and "placeholder" not in ingram_url.lower():
                    return ingram_url
        except Exception:
            pass
        
        # 2. Verificar cache para evitar llamadas repetidas
        sku = item.get("ingramPartNumber", "")
        vendor_part = item.get("vendorPartNumber", "")
        
        # Usar vendorPartNumber si está disponible (más específico)
        cache_key = vendor_part if vendor_part else sku
        if cache_key in ImageHandler.image_cache:
            return ImageHandler.image_cache[cache_key]
        
        # 3. Buscar por categoría y subcategoría de producto
        category_image = ImageHandler.get_category_based_image(item)
        if category_image:
            if cache_key:
                ImageHandler.image_cache[cache_key] = category_image
            return category_image
        
        # 4. Buscar con Unsplash API usando información específica del producto
        producto_nombre = item.get("description", "")
        marca = item.get("vendorName", "")
        categoria = item.get("category", "")
        subcategoria = item.get("subCategory", "")
        
        # Construir query usando información específica
        search_query = ImageHandler.build_unsplash_query(marca, producto_nombre, sku, vendor_part, categoria, subcategoria)
        unsplash_image = ImageHandler.get_unsplash_image(search_query)
        
        if unsplash_image:
            if cache_key:
                ImageHandler.image_cache[cache_key] = unsplash_image
            return unsplash_image
        
        # 5. Fallback con placeholder personalizado
        placeholder = ImageHandler.generate_custom_placeholder(marca, producto_nombre, sku, vendor_part)
        if cache_key:
            ImageHandler.image_cache[cache_key] = placeholder
        return placeholder

    @staticmethod
    def build_unsplash_query(marca, producto_nombre, sku, vendor_part, categoria, subcategoria):
        """Construye query optimizada para Unsplash usando información específica del producto"""
        
        # Prioridad 1: Vendor Part Number (más específico)
        if vendor_part and len(vendor_part) > 3:
            return f"{marca} {vendor_part} {producto_nombre.split()[0] if producto_nombre else ''}"
        
        # Prioridad 2: SKU + Marca
        if sku and marca:
            return f"{marca} {sku}"
        
        # Prioridad 3: Categoría y subcategoría específicas
        if categoria and subcategoria:
            return f"{marca} {categoria} {subcategoria} {producto_nombre.split()[0] if producto_nombre else ''}"
        
        # Prioridad 4: Nombre del producto con marca
        if marca and producto_nombre:
            # Limpiar y optimizar nombre (solo 2-3 palabras clave)
            nombre_limpio = " ".join(producto_nombre.replace(",", "").replace("-", " ").split()[:3])
            return f"{marca} {nombre_limpio}"
        
        # Prioridad 5: Solo SKU
        if sku:
            return f"{sku}"
        
        # Fallback: categoría general
        return f"{categoria} {subcategoria}"

    @staticmethod
    def get_unsplash_image(search_query):
        """
        Busca imágenes en Unsplash API con queries optimizadas para productos tecnológicos
        """
        api_key = current_app.config['UNSPLASH_ACCESS_KEY']
        if not api_key:
            return None
        
        try:
            url = "https://api.unsplash.com/search/photos"
            
            # Queries progresivas de más específica a más genérica
            queries_to_try = [
                f"{search_query} technology product",
                f"{search_query} tech device",
                f"{search_query} computer",
                search_query,
                "technology product"  # fallback final
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
                        # Preferir 'regular' (1080px) para buen balance calidad/velocidad
                        image_url = urls.get("regular") or urls.get("small") or urls.get("thumb")
                        if image_url:
                            return image_url
                    
                    # Si encontramos resultados pero ninguno válido, intentar siguiente query
                    continue
                
                # Manejar rate limits
                elif response.status_code == 403:
                    print("Unsplash API rate limit alcanzado")
                    break
            
        except Exception as e:
            print(f"Error con Unsplash API: {e}")
        
        return None

    @staticmethod
    def get_category_based_image(item):
        """
        Mapea productos a imágenes de alta calidad por categoría
        Usa información específica de category y subCategory
        """
        # Manejar casos donde item es None o no tiene los campos esperados
        if not item:
            return None
            
        descripcion = item.get("description", "").lower() if item.get("description") else ""
        marca = item.get("vendorName", "").lower() if item.get("vendorName") else ""
        categoria = item.get("category", "").lower() if item.get("category") else ""
        subcategoria = item.get("subCategory", "").lower() if item.get("subCategory") else ""
        
        # Mapeo optimizado con imágenes Unsplash de alta calidad
        category_mapping = {
            # Laptops y notebooks
            ("laptop", "notebook", "elitebook", "thinkpad", "macbook", "ultrabook"): 
                "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Computadoras de escritorio
            ("desktop", "workstation", "pc", "tower", "all-in-one"): 
                "https://images.unsplash.com/photo-1587831990711-23ca6441447b?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Monitores y pantallas
            ("monitor", "display", "screen", "lcd", "led", "oled", "curved"): 
                "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Impresoras
            ("printer", "impresora", "laserjet", "inkjet", "multifunc"): 
                "https://images.unsplash.com/photo-1612815154858-60aa4c59eaa6?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Networking y conectividad
            ("router", "switch", "firewall", "access point", "wifi", "ethernet"): 
                "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Servidores y datacenter
            ("server", "servidor", "rack", "blade", "datacenter"): 
                "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Almacenamiento
            ("storage", "disk", "ssd", "hdd", "nas", "san", "drive"): 
                "https://images.unsplash.com/photo-1597852074816-d933c7d2b988?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Tablets
            ("tablet", "ipad", "surface", "android tablet"): 
                "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Smartphones
            ("smartphone", "phone", "iphone", "android", "mobile"): 
                "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Cámaras
            ("camera", "webcam", "camara", "video"): 
                "https://images.unsplash.com/photo-1606983340126-99ab4feaa64a?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Audio (incluye headsets como el ejemplo Jabra)
            ("audio", "headset", "headphone", "auricular", "microphone", "speaker", "música"): 
                "https://images.unsplash.com/photo-1545454675-3531b543be5d?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Accesorios y cables
            ("cable", "adapter", "adaptador", "charger", "cargador", "hub"): 
                "https://images.unsplash.com/photo-1625842268584-8f3296236761?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Periféricos
            ("keyboard", "mouse", "teclado", "raton", "trackpad"): 
                "https://images.unsplash.com/photo-1541140532154-b024d705b90a?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Software y licencias
            ("software", "license", "licencia", "windows", "office", "antivirus"): 
                "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Componentes internos
            ("memory", "ram", "processor", "cpu", "gpu", "motherboard"): 
                "https://images.unsplash.com/photo-1591799264318-7e6ef8ddb7ea?w=400&h=400&fit=crop&auto=format&q=80",
            
            # Gaming
            ("gaming", "gamer", "game", "xbox", "playstation"): 
                "https://images.unsplash.com/photo-1552820728-8b83bb6b773f?w=400&h=400&fit=crop&auto=format&q=80",
        }
        
        # Buscar coincidencias en descripción, marca, categoría y subcategoría
        text_to_search = f"{descripcion} {marca} {categoria} {subcategoria}".lower()
        
        for keywords, image_url in category_mapping.items():
            if any(keyword in text_to_search for keyword in keywords):
                return image_url
        
        return None

    @staticmethod
    def generate_custom_placeholder(marca, producto_nombre, sku, vendor_part):
        """
        Genera placeholders personalizados y atractivos usando información específica
        """
        try:
            from urllib.parse import quote_plus
            
            # Determinar texto y color basado en la información disponible
            if vendor_part and len(vendor_part) <= 20:
                text = f"P/N: {vendor_part}"
                color = "F15A29"  # Naranja corporativo
            elif marca and len(marca) <= 20:
                text = marca.upper()
                # Colores por marca conocida usando la paleta corporativa
                brand_colors = {
                    "HP": "1C2A2F",
                    "DELL": "1C2A2F", 
                    "CISCO": "1C2A2F",
                    "APPLE": "1C2A2F",
                    "LENOVO": "F15A29",
                    "MICROSOFT": "1C2A2F",
                    "INTEL": "1C2A2F",
                    "AMD": "F15A29",
                    "JABRA": "1C2A2F"
                }
                color = brand_colors.get(marca.upper(), "6C757D")  # Gris medio como fallback
            elif sku and len(sku) <= 20:
                text = f"SKU: {sku}"
                color = "F15A29"  # Naranja corporativo
            elif producto_nombre:
                # Crear texto descriptivo corto
                words = producto_nombre.replace(",", "").split()[:3]
                text = " ".join(words).upper()
                if len(text) > 25:
                    text = text[:25] + "..."
                color = "6C757D"  # Gris medio
            else:
                text = "IT DATA GLOBAL"
                color = "1C2A2F"  # Negro azulado oscuro
            
            encoded_text = quote_plus(text)
            return f"https://via.placeholder.com/400x400/{color}/FFFFFF?text={encoded_text}&font_size=16"
            
        except Exception:
            return "https://via.placeholder.com/400x400/1C2A2F/FFFFFF?text=IT+DATA+GLOBAL"

    @staticmethod
    def _is_valid_image(url):
        """Valida que la URL sea una imagen válida."""
        if not url or not url.startswith(('http://', 'https://')):
            return False
        
        # Filtrar dominios problemáticos
        blocked = ['facebook.com', 'instagram.com', 'pinterest.com', 'twitter.com']
        if any(domain in url.lower() for domain in blocked):
            return False
        
        # Verificar indicadores de imagen
        indicators = ['.jpg', '.jpeg', '.png', '.gif', '.webp', 'image', 'img']
        return any(indicator in url.lower() for indicator in indicators)