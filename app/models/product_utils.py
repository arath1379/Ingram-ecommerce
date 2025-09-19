from flask import current_app, json
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
        Encuentra términos de búsqueda mejorados pero más conservadores
        """
        normalized_query = ProductUtils.normalize_text(query)
        search_terms = set([query.strip()])  # Siempre incluir la búsqueda original
        
        # Buscar coincidencias en el mapeo de palabras clave (más conservador)
        for category, keywords in ProductUtils.KEYWORD_MAPPING.items():
            # Solo agregar términos si la categoría está relacionada con la consulta
            if any(keyword in normalized_query for keyword in keywords[:3]):
                # Agregar solo los 2-3 términos principales de la categoría
                search_terms.update(keywords[:3])
        
        # Extraer palabras individuales significativas de la consulta
        query_words = normalized_query.split()
        for word in query_words:
            if len(word) >= 3:  # Solo palabras de 3+ caracteres
                search_terms.add(word)
        
        return list(search_terms)[:5] 

    @staticmethod
    def score_product_relevance_specific(producto, search_term, original_query):
        """
        Calcula score de relevancia específico para un término de búsqueda
        """
        if not isinstance(producto, dict):
            return 0
            
        score = 0
        original_terms = original_query.lower().split()
        
        # Campos y sus pesos
        campos = {
            "description": 20,
            "vendorName": 15,
            "ingramPartNumber": 10,
            "vendorPartNumber": 10,
            "category": 8,
            "subCategory": 8
        }
        
        for campo, peso in campos.items():
            texto = producto.get(campo, "")
            if texto:
                texto_lower = str(texto).lower()
                
                # Coincidencia exacta con el término de búsqueda
                if search_term.lower() == texto_lower:
                    score += peso * 3
                
                # Coincidencia como palabra completa
                elif f" {search_term.lower()} " in f" {texto_lower} ":
                    score += peso * 2
                
                # Coincidencia parcial
                elif search_term.lower() in texto_lower:
                    score += peso
        
        # Bonus adicional si coincide con términos de la consulta original
        for original_term in original_terms:
            for campo in ["description", "vendorName", "category"]:
                texto = producto.get(campo, "")
                if texto and original_term.lower() in str(texto).lower():
                    score += 5
                    break
        
        return score

    @staticmethod
    def buscar_productos_hibrido(query="", vendor="", page_number=1, page_size=25, use_keywords=False):
        """
        Búsqueda híbrida mejorada con tracking y analytics
        PRIORIDAD 1: Búsqueda local en base de datos
        PRIORIDAD 2: Búsqueda en API de Ingram Micro
        """
        # Optimizar query
        optimized_query = ProductUtils.optimize_search_query(query)
        
        # Trackear búsqueda
        ProductUtils.track_search(optimized_query)
        
        start_time = time.time()
        
        # INICIALIZAR variables locales para evitar errores
        productos_locales = []
        total_local = 0
        error_local = False
        
        # PRIORIDAD 1: Búsqueda local si hay query significativa
        if optimized_query and len(optimized_query.strip()) > 2:
            try:
                productos_locales, total_local, error_local = ProductUtils.buscar_local_avanzado(
                    query=optimized_query,
                    vendor=vendor,
                    category=None,
                    page=page_number,
                    page_size=page_size
                )
                
                # Si encontramos resultados locales, usarlos (son más rápidos y precisos)
                if productos_locales and total_local > 0:
                    end_time = time.time()
                    ProductUtils.log_search_metrics(optimized_query, total_local, end_time - start_time)
                    print(f"✅ Búsqueda LOCAL exitosa: {len(productos_locales)} resultados")
                    return (productos_locales, total_local, False)
                    
            except Exception as e:
                print(f"⚠️  Error en búsqueda local: {str(e)}")
                # Continuar con búsqueda API si falla la local
                error_local = True
        
        # PRIORIDAD 2: Búsqueda en API con sistema de caché
        
        # Generar clave única para esta búsqueda
        cache_key = f"{optimized_query}_{vendor}_{page_number}_{page_size}_{use_keywords}"
        
        # Intentar obtener del caché primero
        cached_result = search_cache.get(cache_key)
        if cached_result:
            end_time = time.time()
            ProductUtils.log_search_metrics(optimized_query, cached_result['total_records'], end_time - start_time)
            print(f"✅ Resultados desde CACHÉ: {cached_result['total_records']} resultados")
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
                try:
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
                        print(f"✅ Búsqueda por SKU exitosa: {total_records} resultados")
                        return productos, total_records, pagina_vacia
                        
                except Exception as e:
                    print(f"⚠️  Error en búsqueda por SKU: {str(e)}")
                    # Continuar con búsqueda normal
        try:
            if use_keywords and optimized_query:
                # CORRECCIÓN: Usar el método correcto buscar_por_palabras_clave
                productos, total_records, pagina_vacia = ProductUtils.buscar_por_palabras_clave(
                    optimized_query, vendor, page_number, page_size
                )
            else:
                productos, total_records, pagina_vacia = ProductUtils.buscar_en_catalogo_general(
                    optimized_query, vendor, page_number, page_size
                )
                
        except Exception as e:
            print(f"❌ Error en búsqueda API: {str(e)}")
            # Si falla la API, intentar devolver resultados locales aunque sean pocos
            if productos_locales and total_local > 0:
                print("🔄 Fallback a resultados locales por error en API")
                return productos_locales, total_local, False
            # Si no hay resultados locales, devolver error
            return [], 0, True

        # Guardar en caché para futuras consultas
        try:
            search_cache.save(cache_key, {
                'productos': productos,
                'total_records': total_records,
                'pagina_vacia': pagina_vacia
            })
        except Exception as e:
            print(f"⚠️  Error guardando en caché: {str(e)}")

        end_time = time.time()
        
        # Log metrics
        ProductUtils.log_search_metrics(optimized_query, total_records, end_time - start_time)
        
        # Analizar patrones
        ProductUtils.analyze_search_patterns(optimized_query, total_records)
        
        print(f"✅ Búsqueda API exitosa: {total_records} resultados")
        return productos, total_records, pagina_vacia
    
    @staticmethod
    def _is_highly_relevant_product(producto, original_query, relevance_score):
        """
        Filtrado más estricto para determinar relevancia
        """
        if relevance_score < 15:  # Score mínimo más alto
            return False
            
        if not isinstance(producto, dict):
            return False
            
        original_normalized = ProductUtils.normalize_text(original_query)
        description = ProductUtils.normalize_text(producto.get("description", ""))
        category = ProductUtils.normalize_text(producto.get("category", ""))
        
        # Verificar que al menos un término de la consulta original esté presente
        original_terms = original_normalized.split()
        has_original_term = any(term in description or term in category for term in original_terms if len(term) > 2)
        
        if not has_original_term:
            return False
        
        # Reglas de exclusión mejoradas
        exclusion_patterns = {
            'telefono': ['monitor', 'pantalla', 'impresora', 'laptop', 'computadora'],
            'laptop': ['telefono', 'celular', 'audifonos', 'cable', 'cargador'],
            'audifonos': ['computadora', 'laptop', 'monitor', 'teclado', 'mouse'],
            'bocina': ['computadora', 'laptop', 'telefono', 'tablet', 'monitor']
        }
        
        for search_category, exclude_terms in exclusion_patterns.items():
            if search_category in original_normalized:
                producto_text = f"{description} {category}"
                for exclude_term in exclude_terms:
                    if exclude_term in producto_text:
                        return False
        
        return True

    @staticmethod
    def buscar_por_palabras_clave(query="", vendor="", page_number=1, page_size=25):
        """
        Búsqueda por palabras clave mejorada con filtrado más estricto
        """
        if not query.strip():
            return ProductUtils.buscar_en_catalogo_general(query, vendor, page_number, page_size)
        
        # Obtener términos de búsqueda mejorados pero más específicos
        search_terms = ProductUtils.find_matching_search_terms(query)
        
        # Priorizar la consulta original
        original_query_terms = query.lower().split()
        search_terms = list(set(original_query_terms + search_terms))[:6]  # Limitar a 6 términos máximo
        
        productos_combinados = {}
        relevancia_por_producto = {}
        
        for term in search_terms:
            try:
                # Buscar resultados por término
                productos_term, _, _ = ProductUtils.buscar_en_catalogo_general(
                    term, vendor, 1, 50  # Reducido a 50 resultados por término
                )
                
                for producto in productos_term:
                    part_number = producto.get("ingramPartNumber")
                    if part_number:
                        # Calcular score de relevancia específico para este término
                        score = ProductUtils.score_product_relevance_specific(producto, term, query)
                        
                        # Solo considerar productos con score mínimo
                        if score >= 10:  # Umbral mínimo de relevancia
                            if part_number not in productos_combinados:
                                productos_combinados[part_number] = producto
                                relevancia_por_producto[part_number] = score
                            elif score > relevancia_por_producto[part_number]:
                                productos_combinados[part_number] = producto
                                relevancia_por_producto[part_number] = score
                                
            except Exception as e:
                print(f"Error en búsqueda por término '{term}': {e}")
                continue
        
        # Filtrar productos irrelevantes de manera más estricta
        productos_filtrados = {}
        for part_number, producto in productos_combinados.items():
            if ProductUtils._is_highly_relevant_product(producto, query, relevancia_por_producto[part_number]):
                producto['_relevance_score'] = relevancia_por_producto[part_number]
                productos_filtrados[part_number] = producto
        
        # Convertir a lista y ordenar por relevancia
        productos_list = list(productos_filtrados.values())
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
        from app.models.product import Product
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
            print(f"DEBUG - Llamando a API con params: {params}")
            res = APIClient.make_request("GET", url, params=params)
            
            if res.status_code != 200:
                print(f"ERROR - API returned status: {res.status_code}")
                return [], 0, True
                
            data = res.json()
            print(f"DEBUG - API response keys: {list(data.keys()) if isinstance(data, dict) else 'Not dict'}")
            
            productos = data.get("catalog", []) if isinstance(data, dict) else []
            total_records = data.get("recordsFound", 0)
            
            print(f"DEBUG - Productos encontrados: {len(productos)}, Total: {total_records}")
            
            # Detectar si la página está vacía
            pagina_vacia = len(productos) == 0
            
            return productos, total_records, pagina_vacia
            
        except Exception as e:
            print(f"ERROR en búsqueda de catálogo: {str(e)}")
            import traceback
            traceback.print_exc()
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
        
    @staticmethod
    def buscar_local_avanzado(query, vendor=None, category=None, page=1, page_size=25):
        from app.models.product import Product
        """
        Búsqueda local avanzada con múltiples criterios
        """
        try:
            offset = (page - 1) * page_size
            
            # Buscar en base de datos local
            productos, total = Product.buscar_avanzado(
                query=query,
                vendor=vendor,
                category=category,
                limit=page_size,
                offset=offset
            )
            
            # Convertir a formato similar al de la API
            resultados = []
            for producto in productos:
                metadata = json.loads(producto.metadata_json) if producto.metadata_json else {}
                
                resultados.append({
                    'ingramPartNumber': producto.ingram_part_number,
                    'description': producto.description,
                    'vendorName': producto.vendor_name,
                    'vendorPartNumber': producto.vendor_part_number,
                    'category': producto.category,
                    'subCategory': producto.subcategory,
                    'upc': producto.upc,
                    'pricing': {
                        'customerPrice': producto.base_price,
                        'currencyCode': producto.currency
                    },
                    'productImages': metadata.get('productImages', []),
                    'availability': metadata.get('availability', {}),
                    'es_local': True  # Flag para identificar que es de BD local
                })
            
            return resultados, total, False
            
        except Exception as e:
            print(f"Error en búsqueda local: {str(e)}")
            return [], 0, True
    
    @staticmethod
    def sugerir_palabras_clave_mejorado(query):
        from app.models.product import Product
        """
        Sugerir palabras clave basado en búsquedas anteriores y productos populares
        """
        sugerencias = set()
        
        # 1. Buscar en descripciones de productos
        productos = Product.query.filter(
            Product.description.ilike(f'%{query}%'),
            Product.is_active == True
        ).limit(5).all()
        
        for producto in productos:
            palabras = producto.description.split()
            for palabra in palabras:
                if palabra.lower().startswith(query.lower()) and len(palabra) > 3:
                    sugerencias.add(palabra.capitalize())
        
        # 2. Buscar en categorías
        categorias = Product.query.with_entities(Product.category).filter(
            Product.category.ilike(f'%{query}%'),
            Product.is_active == True
        ).distinct().limit(5).all()
        
        for categoria in categorias:
            if categoria[0]:
                sugerencias.add(categoria[0])
        
        # 3. Buscar en vendors
        vendors = Product.query.with_entities(Product.vendor_name).filter(
            Product.vendor_name.ilike(f'%{query}%'),
            Product.is_active == True
        ).distinct().limit(5).all()
        
        for vendor in vendors:
            if vendor[0]:
                sugerencias.add(vendor[0])
        
        return list(sugerencias)[:10]  # Máximo 10 sugerencias
    
    @staticmethod
    def buscar_con_ranking_local(query, limit=25):
        from app.models.product import Product
        """
        Búsqueda local con ranking de relevancia
        """
        try:
            resultados = Product.buscar_con_ranking(query, limit)
            
            productos_formateados = []
            for producto, relevancia in resultados:
                metadata = json.loads(producto.metadata_json) if producto.metadata_json else {}
                
                productos_formateados.append({
                    'ingramPartNumber': producto.ingram_part_number,
                    'description': producto.description,
                    'vendorName': producto.vendor_name,
                    'vendorPartNumber': producto.vendor_part_number,
                    'category': producto.category,
                    'subCategory': producto.subcategory,
                    'upc': producto.upc,
                    'pricing': {
                        'customerPrice': producto.base_price,
                        'currencyCode': producto.currency
                    },
                    'productImages': metadata.get('productImages', []),
                    'availability': metadata.get('availability', {}),
                    'es_local': True,
                    '_relevance_score': relevancia
                })
            
            return productos_formateados
            
        except Exception as e:
            print(f"Error en búsqueda con ranking: {str(e)}")
            return []