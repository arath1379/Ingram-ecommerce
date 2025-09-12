from flask import current_app
from app.models.api_client import APIClient
from app.models.cache_manager import search_cache
import re
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Set, Optional, Tuple

class ProductUtils:
    # Diccionario de palabras clave y términos relacionados
    KEYWORD_MAPPING = {
        # Categorías generales
        'laptop': ['laptop', 'notebook', 'portatil', 'nb', 'ultrabook', 'chromebook'],
        'desktop': ['desktop', 'pc', 'computadora', 'torre', 'all-in-one', 'aio'],
        'monitor': ['monitor', 'pantalla', 'display', 'lcd', 'led', 'oled', 'gaming monitor'],
        'teclado': ['teclado', 'keyboard', 'mecanico', 'inalambrico', 'gaming keyboard'],
        'mouse': ['mouse', 'raton', 'gaming mouse', 'inalambrico', 'trackball'],
        'impresora': ['impresora', 'printer', 'multifuncional', 'laser', 'tinta', 'inkjet'],
        'servidor': ['servidor', 'server', 'rack', 'blade', 'poweredge', 'proliant'],
        'tablet': ['tablet', 'ipad', 'surface', 'android tablet', 'galaxy tab'],
        'smartphone': ['smartphone', 'telefono', 'celular', 'movil', 'iphone', 'galaxy'],
        'router': ['router', 'enrutador', 'wifi', 'wireless', 'red', 'switch'],
        'storage': ['ssd', 'hdd', 'disco duro', 'almacenamiento', 'usb', 'memory card'],
        'memoria': ['memoria', 'ram', 'ddr4', 'ddr5', 'sodimm', 'memory'],
        'ups': ['ups', 'respaldo', 'bateria', 'backup', 'power supply', 'fuente'],
        'proyector': ['proyector', 'projector', 'beamer', 'presentacion'],
        'audifonos': ['audifonos', 'headphones', 'earbuds', 'headset', 'auriculares'],
        'software': ['software', 'licencia', 'antivirus', 'office', 'windows', 'adobe'],
        'cable': ['cable', 'adaptador', 'conector', 'usb', 'hdmi', 'ethernet'],
        'camara': ['camara', 'webcam', 'security', 'ip camera', 'videoconferencia'],
        'telefono': ['telefono', 'teléfono', 'celular', 'smartphone', 'movil', 'móvil', 
                    'iphone', 'samsung galaxy', 'huawei', 'xiaomi', 'motorola', 'nokia',
                    'android', 'ios', 'smart phone', 'mobile phone'],
        'computadora': ['computadora', 'computador', 'pc', 'ordenador', 'equipo', 'cpu',
                       'workstation', 'estación de trabajo', 'all-in-one', 'aio'],
        'tablet': ['tablet', 'tableta', 'ipad', 'samsung tab', 'huawei tablet', 
                  'lenovo tablet', 'android tablet', 'windows tablet'],
        
        # Marcas específicas (algunos ejemplos)
        'apple': ['apple', 'iphone', 'ipad', 'macbook', 'imac', 'mac'],
        'hp': ['hp', 'hewlett packard', 'pavilion', 'elitebook', 'omen'],
        'dell': ['dell', 'inspiron', 'latitude', 'optiplex', 'precision', 'alienware'],
        'lenovo': ['lenovo', 'thinkpad', 'ideapad', 'legion', 'yoga'],
        'asus': ['asus', 'zenbook', 'vivobook', 'rog', 'tuf'],
        'samsung': ['samsung', 'galaxy', 'monitor samsung', 'ssd samsung'],
        'cisco': ['cisco', 'meraki', 'catalyst', 'firewall', 'switch cisco'],
        'microsoft': ['microsoft', 'surface', 'xbox', 'office', 'windows'],
        # Gaming
        'gaming': ['gaming', 'gamer', 'rog', 'msi gaming', 'alienware', 'predator', 'legion'],
        # Especificaciones técnicas
        'intel': ['intel', 'core i3', 'core i5', 'core i7', 'core i9', 'xeon'],
        'amd': ['amd', 'ryzen', 'radeon', 'threadripper', 'epyc'],
        'nvidia': ['nvidia', 'geforce', 'rtx', 'gtx', 'quadro'],
        'wifi6': ['wifi 6', 'ax', '802.11ax', 'wifi6'],
        '4k': ['4k', 'ultra hd', 'uhd', '3840x2160'],
        'ssd': ['ssd', 'solid state', 'nvme', 'm.2'],
    }

    SEARCH_CACHE_DURATION = 300  # 5 minutos en segundos
    POPULAR_SEARCHES = defaultdict(int)
    SEARCH_HISTORY = []
    MAX_SEARCH_HISTORY = 50
    
    # Cache para índice de palabras clave (simula BD)
    _keyword_index = defaultdict(set)
    _index_built = False

    @staticmethod
    def get_local_vendors():
        common_vendors = [
            "HP Cómputo", "Dell", "Lenovo", "Cisco", "Apple", "Microsoft", "Adata", "Getttech", "Acteck", "Hpe Accs", "Yeyian",
            "Samsung", "LG", "ASUS", "Acer", "Vorago", "Cnp T5 Enterprise", "NACEB", "Cecotec", "Barco", "Vorago Accs","Sansui",
            "Intel", "AMD", "Meraki", "Logitech", "Kingston", "Seagate", "Manhattan", "Kensington", "Toshiba (Pp)", "CyberPower",
            "Elo Touch", "TP-Link", "Zebra Tech.", "Jabra", "Poly", "LG Digital Signage", "Compulocks", "APC", "Balam Rush", "InFocus",
            "Canon", "Epson", "Brother", "StarTech.com", "HP POLY", "Honeywell", "Qian", "Intellinet", "BRobotix", "Eaton Consig Cables",
            "Xerox", "Perfect Choice", "Buffalo", "Hisense", "Dell NPOS", "HP Impresión", "Xzeal Gaming", "CDP", "Zebra Printers",
            "Targus", "Avision", "HPE ARUBA NETWORKING", "Cnp Meraki", "Zebra", "Vica", "Eaton", "Smartbitt", "BenQ", "Lenovo Idea Nb",
            "Hewlett Packard Enterprise", "Lenovo DCG", "Eaton Proyectos", "Eaton Consig Kvm", "Epson Hw", "Lexmark", "Axis", "TechZone",
            "Bixolon", "IBM", "Screenbeam", "Tecnosinergia", "TechZone DC POS", "Uniarch By Unv", "Lenovo Global", "Impresoras Zebra",
            "Surface", "Vertiv", "TMCELL", "Zebra Lectores", "Star Micronics", "Peerless", "Infinix Mobility", "Pdp", "Zebra Adc A5, A6", 
            "Corsair (Arroba)", "QNAP", "Chicago Digital", "Viewsonic", "KINGSTON PP FLASH", "Hp Componentes", "Silimex", "XPG", "Dell Memory",
            "Kvr Ar", "3M", "Dataproducts", "Hid Global", "Msi Componentes", "Cooler Master (A)", "Msi Componentes (A)", "Corsair", "Lacie",
            "Unitech America", "Ezviz", "Ingressio", "Sharp", "Epson Supp", "Cooler Master", "EC Line", "Lenovo Idea Aio", "Nexxt Home", "Zkteco",
            "Corel", "AOC", "GO TO", "Gigabyte", "Nokia", "PNY", "Forza", "Samsung Tab Mxp", "Koblenz", "KINGSTON PP SSD", "Amd (Arroba)",
            "Enson",  "Tripp Lite by Eaton", "Prolicom", "Accvent", "Honor Technologies", "Cnp Enterprise", "Mercusys", "Complet", "Konica Minolta",
            "Iris", "Xbox Accs", "Lenovo Notebook Usd", "Dell Gaming Accesori", "Vector Engineering", "Dell Gaming Desktop", "Mcafee Llc", "KINGSTON AP SSD",
            "Honor Tablet", "KINGSTON AP FLASH", "Premiercom Retail", "Dell Enterprise", "XP PEN", "Wacom", "Hyundai", "Tonivisa", "TJD",
        ]
        return sorted(common_vendors)

    @staticmethod
    def format_currency(amount, currency_code='MXP'):
        """Formatear moneda correctamente para pesos mexicanos"""
        if amount is None or amount == 0:
            return "No disponible"
        
        try:
            amount = float(amount)
            
            # Formatear según la moneda
            if currency_code in ['MXP', 'MXN']:  # Pesos mexicanos
                return f"${amount:,.2f} MXN"
            elif currency_code == 'USD':
                return f"USD ${amount:,.2f}"
            else:
                return f"${amount:,.2f} {currency_code}"
                
        except (ValueError, TypeError):
            return "No disponible"

    @staticmethod
    def get_availability_text(precio_info, detalle=None):
        """
        Genera un string amigable de disponibilidad.
        Usa: precio_info['availability'] preferente, luego detalle['availability'], luego productStatusCode/message.
        """
        av = None
        if isinstance(precio_info, dict):
            av = precio_info.get("availability")
        if not av and detalle and isinstance(detalle, dict):
            av = detalle.get("availability")

        # Si existe objeto availability -> interpretar
        if av and isinstance(av, dict):
            # intentar obtener totalAvailability
            total = None
            try:
                t = av.get("totalAvailability")
                if t is None:
                    # si no viene, sumar availabilityByWarehouse
                    byws = av.get("availabilityByWarehouse") or []
                    total = sum(int(w.get("quantityAvailable", 0) or 0) for w in byws) if byws else None
                else:
                    total = int(t) if isinstance(t, (int, float, str)) and str(t).strip() != "" else None
            except Exception:
                return None

            available_flag = av.get("available")
            # si hay al menos unidades o flag true -> disponible
            if (isinstance(total, int) and total > 0) or available_flag:
                # construir lista de almacenes con stock
                byws = av.get("availabilityByWarehouse") or []
                warehouses = []
                for w in byws:
                    q = int(w.get("quantityAvailable", 0) or 0)
                    if q > 0:
                        loc = w.get("location") or w.get("warehouseName") or f"Almacén {w.get('warehouseId','?')}"
                        warehouses.append(f"{loc}: {q}")
                if total is None and warehouses:
                    total = sum(int(x.split(":")[-1].strip()) for x in warehouses)
                if warehouses:
                    # mostrar hasta 3 almacenes como ejemplo
                    return f"Disponible — {total if total is not None else ''} unidades (ej. {', '.join(warehouses[:3])})"
                return f"Disponible — {total} unidades" if total is not None else "Disponible"
            else:
                return "Agotado"

        # fallback: usar productStatusCode / productStatusMessage
        if isinstance(precio_info, dict):
            code = precio_info.get("productStatusCode")
            msg = precio_info.get("productStatusMessage")
            if code:
                if code == "E":
                    return msg or "No encontrado"
                # 'W' y otros códigos: mostrar mensaje si existe, sino una nota genérica.
                return msg or f"Estado: {code}"
        return "No disponible"

    @staticmethod
    def normalize_text(text):
        """Normaliza texto para búsqueda: minúsculas, sin acentos, sin caracteres especiales."""
        if not text:
            return ""
        # Convertir a minúsculas
        text = text.lower()
        # Remover acentos básicos
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ü': 'u', 'ñ': 'n'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        # Mantener solo letras, números y espacios
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        # Normalizar espacios
        text = ' '.join(text.split())
        return text

    @staticmethod
    def extract_keywords_from_text(text):
        """Extrae palabras clave de un texto (descripción, nombre, etc.)."""
        normalized = ProductUtils.normalize_text(text)
        words = normalized.split()
        
        # Filtrar palabras muy cortas o comunes
        stop_words = {'de', 'la', 'el', 'en', 'con', 'para', 'por', 'una', 'un', 'y', 'o', 'a', 'que', 'del', 'los', 'las'}
        keywords = [word for word in words if len(word) >= 2 and word not in stop_words]
        
        return keywords
    
    @staticmethod
    def get_popular_searches(limit: int = 10) -> List[Tuple[str, int]]:
        """Obtiene las búsquedas más populares"""
        return sorted(ProductUtils.POPULAR_SEARCHES.items(), 
                     key=lambda x: x[1], reverse=True)[:limit]

    @staticmethod
    def get_search_suggestions(query: str, limit: int = 8) -> List[str]:
        """Sugiere búsquedas basadas en el historial y popularidad"""
        suggestions = set()
        
        # Sugerencias del historial
        for search_term in ProductUtils.SEARCH_HISTORY:
            if query.lower() in search_term.lower():
                suggestions.add(search_term)
        
        # Sugerencias de términos populares
        for popular_term, _ in ProductUtils.get_popular_searches(20):
            if query.lower() in popular_term.lower():
                suggestions.add(popular_term)
        
        # Sugerencias de palabras clave
        suggestions.update(ProductUtils.sugerir_palabras_clave(query))
        
        return sorted(list(suggestions))[:limit]
    @staticmethod
    def track_search(query: str):
        """Registra una búsqueda en el historial y contador de popularidad"""
        if not query.strip():
            return
            
        clean_query = query.strip().lower()
        
        # Actualizar contador de popularidad
        ProductUtils.POPULAR_SEARCHES[clean_query] += 1
        
        # Actualizar historial
        if clean_query not in ProductUtils.SEARCH_HISTORY:
            ProductUtils.SEARCH_HISTORY.insert(0, clean_query)
            # Mantener tamaño máximo
            if len(ProductUtils.SEARCH_HISTORY) > ProductUtils.MAX_SEARCH_HISTORY:
                ProductUtils.SEARCH_HISTORY.pop()

    @staticmethod
    def optimize_search_query(query: str) -> str:
        """Optimiza la query para mejores resultados"""
        if not query:
            return ""
        additional_stop_words = {'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'de', 'en', 'con'}
        words = query.split()
        filtered_words = [word for word in words if word.lower() not in additional_stop_words]

        corrected_query = ProductUtils.spell_check_query(' '.join(filtered_words))
        
        return corrected_query.strip()

    @staticmethod
    def spell_check_query(query: str) -> str:
        """Corrige errores ortográficos comunes en las búsquedas"""
        common_mistakes = {
            'telefno': 'telefono', 'telefon': 'telefono',
            'celular': 'celular', 'celula': 'celular',
            'computdora': 'computadora', 'computador': 'computadora',
            'lapto': 'laptop', 'notebok': 'notebook', 'noteboo': 'notebook',
            'impresora': 'impresora', 'impresor': 'impresora',
            'monito': 'monitor', 'teclado': 'teclado', 'teclao': 'teclado',
            'mouse': 'mouse', 'mous': 'mouse', 'route': 'router', 'route': 'router'
        }
        
        corrected = query.lower()
        for mistake, correction in common_mistakes.items():
            corrected = corrected.replace(mistake, correction)
        
        return corrected

    @staticmethod
    def log_search_metrics(query: str, results_count: int, response_time: float):
        """Registra métricas de performance de búsqueda"""
        print(f"🔍 Search Metrics - Query: '{query}', Results: {results_count}, Time: {response_time:.3f}s")

    @staticmethod
    def analyze_search_patterns(query: str, results_count: int):
        """Analiza patrones de búsqueda para mejorar futuras búsquedas"""
        if results_count == 0:
            print(f"⚠️  Búsqueda sin resultados: '{query}' - Considerar agregar al KEYWORD_MAPPING")

    @staticmethod
    def advanced_search_filters(products: List[Dict], filters: Dict) -> List[Dict]:
        """Aplica filtros avanzados a los resultados de búsqueda"""
        filtered_products = products.copy()
        
        # Filtro por precio
        if 'min_price' in filters:
            filtered_products = [p for p in filtered_products 
                               if p.get('pricing', {}).get('customerPrice', 0) >= filters['min_price']]
        
        if 'max_price' in filters:
            filtered_products = [p for p in filtered_products 
                               if p.get('pricing', {}).get('customerPrice', float('inf')) <= filters['max_price']]
        
        # Filtro por disponibilidad
        if 'in_stock_only' in filters and filters['in_stock_only']:
            filtered_products = [p for p in filtered_products 
                               if p.get('availability', {}).get('available', False)]
        
        # Filtro por marca
        if 'vendors' in filters and filters['vendors']:
            filtered_products = [p for p in filtered_products 
                               if p.get('vendorName') in filters['vendors']]
        
        # Filtro por categoría
        if 'categories' in filters and filters['categories']:
            filtered_products = [p for p in filtered_products 
                               if p.get('category') in filters['categories']]
        
        return filtered_products
        
    @staticmethod
    def get_search_analytics() -> Dict:
        """Obtiene analytics de búsquedas"""
        total_searches = sum(ProductUtils.POPULAR_SEARCHES.values())
        unique_searches = len(ProductUtils.POPULAR_SEARCHES)
        
        return {
            'total_searches': total_searches,
            'unique_searches': unique_searches,
            'avg_searches_per_term': total_searches / unique_searches if unique_searches > 0 else 0,
            'top_searches': ProductUtils.get_popular_searches(10)
        }

    @staticmethod
    def boost_popular_products(products: List[Dict]) -> List[Dict]:
        """Aumenta la relevancia de productos populares basado en criterios específicos"""
        if not products:
            return products
        
        boosted_products = []
        
        for product in products:
            boosted_product = product.copy()
            current_score = boosted_product.get('_relevance_score', 0)
            
            # Boost por disponibilidad (productos disponibles tienen prioridad)
            availability = boosted_product.get('availability', {})
            if isinstance(availability, dict) and availability.get('available'):
                current_score += 15
            elif isinstance(availability, bool) and availability:
                current_score += 15
            
            # Boost por marca popular
            popular_brands = ['apple', 'samsung', 'dell', 'hp', 'lenovo', 'cisco', 'microsoft', 'asus']
            vendor_name = str(boosted_product.get('vendorName', '')).lower()
            if any(brand in vendor_name for brand in popular_brands):
                current_score += 10
            
            # Boost por categorías populares
            popular_categories = ['laptop', 'smartphone', 'tablet', 'monitor', 'notebook', 'computadora']
            category = str(boosted_product.get('category', '')).lower()
            if any(pop_cat in category for pop_cat in popular_categories):
                current_score += 8
            
            # Boost por productos con imágenes
            product_images = boosted_product.get('productImages', [])
            if product_images and len(product_images) > 0:
                current_score += 5
            
            # Boost por productos con descripción detallada
            description = str(boosted_product.get('description', ''))
            if len(description) > 50:  # Descripciones largas suelen ser más completas
                current_score += 3
            
            boosted_product['_relevance_score'] = current_score
            boosted_products.append(boosted_product)
        
        return boosted_products

    @staticmethod
    def get_search_performance_metrics() -> Dict:
        """Métricas de performance de búsqueda"""
        # Implementar tracking de tiempo de respuesta, tasa de acierto, etc.
        return {
            'avg_response_time': 0,
            'success_rate': 0,
            'cache_hit_rate': 0
        }

    @staticmethod
    def export_search_data(format: str = 'json') -> Optional[str]:
        """Exporta datos de búsqueda para análisis"""
        data = {
            'popular_searches': dict(ProductUtils.POPULAR_SEARCHES),
            'search_history': ProductUtils.SEARCH_HISTORY,
            'timestamp': datetime.now().isoformat()
        }
        
        if format == 'json':
            import json
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        return None

    @staticmethod
    def auto_complete_query(query: str) -> List[str]:
        """Autocompletado de búsquedas en tiempo real"""
        if len(query) < 2:
            return []
            
        suggestions = []
        
        # Buscar en términos populares
        for term in ProductUtils.POPULAR_SEARCHES.keys():
            if term.startswith(query.lower()):
                suggestions.append(term)
        
        # Buscar en palabras clave
        for category_terms in ProductUtils.KEYWORD_MAPPING.values():
            for term in category_terms:
                if term.startswith(query.lower()) and term not in suggestions:
                    suggestions.append(term)
        
        return sorted(suggestions)[:8]

    @staticmethod
    def get_search_tips() -> List[str]:
        """Proporciona tips de búsqueda para usuarios"""
        return [
            "Usa comillas para búsquedas exactas: \"Samsung Galaxy S23\"",
            "Filtra por marca usando el menú desplegable",
            "Busca por número de parte para resultados precisos",
            "Usa palabras clave específicas como 'gaming', 'inalámbrico', '4k'",
            "Revisa las sugerencias debajo de la barra de búsqueda"
        ]

    @staticmethod
    def log_search_metrics(query: str, results_count: int, response_time: float):
        """Registra métricas de performance de búsqueda"""
        # Implementar logging para monitoreo
        print(f"Search: {query}, Results: {results_count}, Time: {response_time:.2f}s")

    @staticmethod
    def optimize_search_query(query: str) -> str:
        """Optimiza la query para mejores resultados"""
        # Remover stop words adicionales
        additional_stop_words = {'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas'}
        words = query.split()
        filtered_words = [word for word in words if word.lower() not in additional_stop_words]
        
        # Corregir ortografía
        corrected_query = ProductUtils.spell_check_query(' '.join(filtered_words))
        
        return corrected_query

    @staticmethod
    def find_matching_search_terms(query):
        """
        Encuentra términos de búsqueda mejorados basados en palabras clave.
        Devuelve una lista de términos para usar en la búsqueda.
        """
        normalized_query = ProductUtils.normalize_text(query)
        search_terms = set([query.strip()])  # Siempre incluir la búsqueda original
        
        # Buscar coincidencias en el mapeo de palabras clave
        for category, keywords in ProductUtils.KEYWORD_MAPPING.items():
            for keyword in keywords:
                if keyword.lower() in normalized_query:
                    # Agregar términos relacionados - aumentar a 5 términos
                    search_terms.update(keywords[:5])  # Aumentado a 5 términos relacionados
                    break
        
        # Extraer palabras individuales de la consulta
        query_words = normalized_query.split()
        for word in query_words:
            if len(word) >= 2:  # Reducido a 2 caracteres mínimo para capturar más términos
                search_terms.add(word)
        
        return list(search_terms)[:8]  # Aumentado a 8 términos máximo

    @staticmethod
    def score_product_relevance(producto, search_terms):
        """
        Calcula un score de relevancia para un producto basado en los términos de búsqueda.
        MEJORADO: Mayor puntuación para coincidencias exactas en campos importantes.
        """
        if not isinstance(producto, dict):
            return 0
            
        # Textos donde buscar - priorizar algunos campos
        campos_prioritarios = {
            "description": 20,  # Mayor peso a descripción
            "vendorName": 15,   # Alto peso a marca
            "ingramPartNumber": 10,
            "vendorPartNumber": 10,
            "category": 8,
            "subCategory": 8,
            "extraDescription": 5  # Si existe este campo
        }
        score = 0
        
        for campo, peso in campos_prioritarios.items():
            texto = producto.get(campo, "")
            if texto:
                texto_lower = str(texto).lower()
                for term in search_terms:
                    term_lower = term.lower()
                    
                    # Coincidencia exacta (máxima puntuación)
                    if term_lower == texto_lower:
                        score += peso * 3
                    # Coincidencia como palabra completa
                    elif f" {term_lower} " in f" {texto_lower} ":
                        score += peso * 2
                    # Coincidencia parcial
                    elif term_lower in texto_lower:
                        score += peso
        
        # Bonus por disponibilidad
        if producto.get('availability', {}).get('available'):
            score += 5
        return score

    @staticmethod
    def buscar_productos_hibrido(query="", vendor="", page_number=1, page_size=25, use_keywords=False):
        """
        Búsqueda híbrida mejorada con tracking y analytics
        """
        # Optimizar query
        optimized_query = ProductUtils.optimize_search_query(query)
        
        # Trackear búsqueda
        ProductUtils.track_search(optimized_query)
        
        start_time = time.time()
        
        # Generar clave única para esta búsqueda
        cache_key = f"{optimized_query}_{vendor}_{page_number}_{page_size}_{use_keywords}"
        
        # Intentar obtener del caché primero
        cached_result = search_cache.get(cache_key)
        if cached_result:
            end_time = time.time()
            ProductUtils.log_search_metrics(optimized_query, cached_result['total_records'], end_time - start_time)
            return (cached_result['productos'], cached_result['total_records'], 
                    cached_result['pagina_vacia'])

        productos = []
        total_records = 0
        pagina_vacia = False

        # Si la consulta parece un SKU (sin espacios y alfanumérico), intentar búsqueda directa primero
        if optimized_query and not vendor and not optimized_query.strip().isspace() and len(optimized_query) >= 3:
            # Verificar si la consulta parece un SKU (sin espacios, principalmente alfanumérico)
            sku_like = optimized_query.replace(" ", "").replace("-", "").replace("_", "")
            if sku_like.isalnum() and len(sku_like) >= 3:
                productos_sku = ProductUtils.buscar_por_sku_directo(optimized_query)
                if productos_sku:
                    productos = productos_sku
                    total_records = len(productos)
                    # Guardar en caché
                    search_cache.save(cache_key, {
                        'productos': productos,
                        'total_records': total_records,
                        'pagina_vacia': pagina_vacia
                    })
                    end_time = time.time()
                    ProductUtils.log_search_metrics(optimized_query, total_records, end_time - start_time)
                    ProductUtils.analyze_search_patterns(optimized_query, total_records)
                    return productos, total_records, pagina_vacia

        # Si no es un SKU o no se encontraron resultados, usar búsqueda en catálogo general
        if use_keywords and optimized_query:
            productos, total_records, pagina_vacia = ProductUtils.buscar_por_palabras_clave(optimized_query, vendor, page_number, page_size)
        else:
            productos, total_records, pagina_vacia = ProductUtils.buscar_en_catalogo_general(optimized_query, vendor, page_number, page_size)

        # Guardar en caché para futuras consultas
        search_cache.save(cache_key, {
            'productos': productos,
            'total_records': total_records,
            'pagina_vacia': pagina_vacia
        })

        end_time = time.time()
        
        # Log metrics
        ProductUtils.log_search_metrics(optimized_query, total_records, end_time - start_time)
        
        # Analizar patrones
        ProductUtils.analyze_search_patterns(optimized_query, total_records)
        
        return productos, total_records, pagina_vacia

    @staticmethod
    def buscar_por_palabras_clave(query="", vendor="", page_number=1, page_size=25):
        """
        Búsqueda por palabras clave mejorada con boost de productos populares
        """
        if not query.strip():
            return ProductUtils.buscar_en_catalogo_general(query, vendor, page_number, page_size)
        
        # Obtener términos de búsqueda mejorados
        search_terms = ProductUtils.find_matching_search_terms(query)
        
        # Realizar búsquedas individuales para cada término
        productos_combinados = {}
        
        for term in search_terms:
            try:
                # Buscar más resultados por término
                productos_term, _, _ = ProductUtils.buscar_en_catalogo_general(
                    term, vendor, 1, 100  # Aumentado a 100 resultados por término
                )
                
                for producto in productos_term:
                    part_number = producto.get("ingramPartNumber")
                    if part_number:
                        # Calcular score de relevancia
                        score = ProductUtils.score_product_relevance(producto, search_terms)
                        
                        if part_number not in productos_combinados or score > productos_combinados[part_number].get('_relevance_score', 0):
                            producto['_relevance_score'] = score
                            productos_combinados[part_number] = producto
                            
            except Exception as e:
                print(f"Error en búsqueda por término '{term}': {e}")
                continue
        
        # Filtrar productos irrelevantes
        productos_filtrados = {}
        for part_number, producto in productos_combinados.items():
            if ProductUtils._is_relevant_product(producto, query):
                productos_filtrados[part_number] = producto
        
        # Convertir a lista y ordenar por relevancia
        productos_list = list(productos_filtrados.values())
        productos_list.sort(key=lambda x: x.get('_relevance_score', 0), reverse=True)
        
        # Aplicar boost de productos populares
        productos_list = ProductUtils.boost_popular_products(productos_list)
        
        # Re-ordenar después del boost
        productos_list.sort(key=lambda x: x.get('_relevance_score', 0), reverse=True)
        
        # Aplicar paginación
        total_records = len(productos_list)
        start_index = (page_number - 1) * page_size
        end_index = start_index + page_size
        productos_paginated = productos_list[start_index:end_index]
        
        # Limpiar scores de los resultados finales
        for producto in productos_paginated:
            producto.pop('_relevance_score', None)
        
        pagina_vacia = len(productos_paginated) == 0
        
        return productos_paginated, total_records, pagina_vacia

    @staticmethod
    def _is_relevant_product(producto, original_query):
        """
        Determina si un producto es relevante para la consulta original.
        MEJORADO: Filtrado más inteligente basado en categorías.
        """
        if not isinstance(producto, dict):
            return True
            
        original_normalized = ProductUtils.normalize_text(original_query)
        description = ProductUtils.normalize_text(producto.get("description", ""))
        category = ProductUtils.normalize_text(producto.get("category", ""))
        subcategory = ProductUtils.normalize_text(producto.get("subCategory", ""))
        
        # Reglas de exclusión mejoradas
        exclusion_rules = {
            # Búsquedas de teléfonos
            'telefono': ['monitor', 'pantalla', 'impresora', 'laptop', 'notebook', 
                        'teclado', 'mouse', 'router', 'switch', 'servidor'],
            'celular': ['monitor', 'pantalla', 'impresora', 'laptop', 'notebook',
                       'teclado', 'mouse', 'router', 'switch', 'servidor'],
            'smartphone': ['monitor', 'pantalla', 'impresora', 'laptop', 'notebook',
                          'teclado', 'mouse', 'router', 'switch', 'servidor'],
            
            # Búsquedas de computadoras
            'computadora': ['audifonos', 'headset', 'telefono', 'celular', 'tablet',
                           'cable', 'adaptador', 'cargador'],
            'laptop': ['audifonos', 'headset', 'telefono', 'celular', 'tablet',
                      'cable', 'adaptador', 'cargador', 'monitor'],
            'notebook': ['audifonos', 'headset', 'telefono', 'celular', 'tablet',
                        'cable', 'adaptador', 'cargador', 'monitor'],
            
            # Búsquedas de monitores
            'monitor': ['telefono', 'celular', 'laptop', 'notebook', 'teclado',
                       'mouse', 'impresora', 'router'],
            'pantalla': ['telefono', 'celular', 'laptop', 'notebook', 'teclado',
                        'mouse', 'impresora', 'router'],
        }
        
        # Verificar reglas de exclusión
        for search_category, exclude_terms in exclusion_rules.items():
            if search_category in original_normalized:
                producto_text = f"{description} {category} {subcategory}"
                for exclude_term in exclude_terms:
                    if exclude_term in producto_text:
                        return False
        
        # Inclusión forzada para términos específicos
        inclusion_rules = {
            'telefono': ['telefono', 'celular', 'smartphone', 'iphone', 'galaxy'],
            'celular': ['telefono', 'celular', 'smartphone', 'iphone', 'galaxy'],
            'smartphone': ['telefono', 'celular', 'smartphone', 'iphone', 'galaxy'],
        }
        
        for search_category, include_terms in inclusion_rules.items():
            if search_category in original_normalized:
                producto_text = f"{description} {category} {subcategory}"
                for include_term in include_terms:
                    if include_term in producto_text:
                        return True
        return True
    
    @staticmethod
    def buscar_por_sku_directo(sku_query):
        """
        Busca productos usando el endpoint de price & availability con SKUs potenciales.
        """
        productos = []
        
        # Limpiar y normalizar el SKU
        sku_clean = sku_query.strip().upper()
        
        # Generar variantes del SKU
        sku_variants = [
            sku_clean,
            sku_clean.replace(" ", "-"),
            sku_clean.replace("-", ""),
            sku_clean.replace(" ", ""),
            sku_clean.replace("_", "-"),
            sku_clean.replace("_", ""),
        ]
        
        # Remover duplicados manteniendo orden
        sku_variants = list(dict.fromkeys(sku_variants))
        
        # Intentar con cada variante
        for sku in sku_variants[:5]:
            try:
                url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
                body = {"products": [{"ingramPartNumber": sku}]}
                params = {
                    "includeAvailability": "true",
                    "includePricing": "true",
                    "includeProductAttributes": "true"
                }
                
                res = APIClient.make_request("POST", url, params=params, json=body)
                
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list) and data:
                        producto_info = data[0]
                        
                        # Verificar que el producto existe y no tiene error
                        if (producto_info.get("productStatusCode") != "E" and 
                            producto_info.get("ingramPartNumber")):
                            
                            # Obtener detalles adicionales del producto
                            detalle = ProductUtils.obtener_detalle_producto(producto_info.get("ingramPartNumber"))
                            
                            # Asegurarse de que detalle no sea None
                            if detalle is None:
                                detalle = {}
                            
                            # Combinar información
                            producto_combinado = {
                                "ingramPartNumber": producto_info.get("ingramPartNumber"),
                                "vendorPartNumber": detalle.get("vendorPartNumber"),
                                "description": (detalle.get("description") or 
                                              producto_info.get("description") or 
                                              "Descripción no disponible"),
                                "vendorName": (detalle.get("vendorName") or 
                                             producto_info.get("vendorName") or 
                                             "Marca no disponible"),
                                "category": detalle.get("category"),
                                "subCategory": detalle.get("subCategory"),
                                "productImages": detalle.get("productImages", []),
                                "pricing": producto_info.get("pricing", {}),
                                "availability": producto_info.get("availability", {}),
                                "productStatusCode": producto_info.get("productStatusCode"),
                                "productStatusMessage": producto_info.get("productStatusMessage")
                            }
                            productos.append(producto_combinado)
                            break  # Si encontramos un resultado válido, salir del loop
                            
            except Exception as e:
                print(f"Error buscando SKU {sku}: {e}")
                continue
        
        return productos

    @staticmethod
    def obtener_detalle_producto(part_number):
        """
        Obtiene los detalles de un producto específico.
        """
        try:
            detail_url = f"https://api.ingrammicro.com/resellers/v6/catalog/details/{part_number}"
            detalle_res = APIClient.make_request("GET", detail_url)
            return detalle_res.json() if detalle_res.status_code == 200 else {}
        except Exception:
            return {}

    @staticmethod
    def buscar_en_catalogo_general(query="", vendor="", page_number=1, page_size=25):
        """
        Búsqueda en el catálogo general usando el endpoint GET.
        """
        url = "https://api.ingrammicro.com/resellers/v6/catalog"
        
        params = {
            "pageSize": page_size,
            "pageNumber": page_number,
            "showGroupInfo": "false"
        }
        
        if query:
            params["searchString"] = query
            params["searchInDescription"] = "true"
        if vendor and vendor != "Todas las marcas":
            params["vendor"] = vendor
            
        try:
            res = APIClient.make_request("GET", url, params=params)
            data = res.json() if res.status_code == 200 else {}
            
            productos = data.get("catalog", []) if isinstance(data, dict) else []
            total_records = data.get("recordsFound", 0)
            
            # Detectar si la página está vacía (no hay productos reales)
            pagina_vacia = len(productos) == 0
            
            return productos, total_records, pagina_vacia
            
        except Exception as e:
            print(f"Error en búsqueda de catálogo: {e}")
            return [], 0, True

    @staticmethod
    def sugerir_palabras_clave(query):
        """
        Sugiere palabras clave relacionadas basadas en la consulta del usuario.
        MEJORADO: Mejores sugerencias para búsquedas comunes.
        """
        if not query:
            return []
            
        normalized_query = ProductUtils.normalize_text(query)
        sugerencias = set()
        
        # Buscar coincidencias en el mapeo
        for category, keywords in ProductUtils.KEYWORD_MAPPING.items():
            category_match = False
            for keyword in keywords:
                if keyword.lower() in normalized_query or normalized_query in keyword.lower():
                    category_match = True
                    break
            
            if category_match:
                # Agregar palabras clave relacionadas de la misma categoría
                sugerencias.update(keywords[:6])  # Aumentado a 6 por categoría
        
        # Remover la consulta original de las sugerencias
        query_words = set(normalized_query.split())
        sugerencias = [s for s in sugerencias if s not in query_words]
        
        # Ordenar por relevancia (términos más específicos primero)
        sugerencias_ordenadas = sorted(sugerencias, key=lambda x: len(x), reverse=True)
        
        return sugerencias_ordenadas[:10]  # Aumentado a 10 sugerencias
    
    @staticmethod
    def obtener_precio_disponibilidad(part_number):
        """
        Obtiene información de precio y disponibilidad para un producto específico.
        """
        try:
            if not part_number:
                return None
                
            url = "https://api.ingrammicro.com/resellers/v6/catalog/priceandavailability"
            body = {"products": [{"ingramPartNumber": part_number}]}
            params = {
                "includeAvailability": "true",
                "includePricing": "true",
                "includeProductAttributes": "true"
            }
            
            res = APIClient.make_request("POST", url, params=params, json=body)
            
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and data:
                    return data[0]  # Devolver el primer (y único) producto
                    
            return None
            
        except Exception as e:
            print(f"Error obteniendo precio/disponibilidad para {part_number}: {e}")
            return None