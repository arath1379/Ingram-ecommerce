from flask import Flask
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
from app.models.cache_manager import search_cache

# Configuración para límites de búsqueda
app.config['MAX_RECORDS_LIMIT'] = 10000

# Configurar el cache si no existe
if not hasattr(app, 'search_cache'):
    app.search_cache = search_cache

# Opcional: Configurar logging para debug
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Agregar un contexto personalizado para templates
@app.context_processor
def utility_processor():
    return dict(
        debug_mode=app.debug,
        use_keywords_info=True  # Para mostrar información de debugging
    )

# Si necesitas probar manualmente la búsqueda por palabras clave
@app.cli.command()
def test_keyword_search():
    """Comando CLI para probar la búsqueda por palabras clave"""
    from app.models.product_utils import ProductUtils
    
    queries = ["laptop gaming", "monitor 4k", "impresora laser", "router cisco"]
    
    for query in queries:
        print(f"\n🔍 Testing query: '{query}'")
        print(f"Search terms: {ProductUtils.find_matching_search_terms(query)}")
        print(f"Suggestions: {ProductUtils.sugerir_palabras_clave(query)}")
        
        # Probar búsqueda
        productos, total, vacia = ProductUtils.buscar_productos_hibrido(query, "", 1, 5, True)
        print(f"Results: {len(productos)} products found (total: {total})")
        
        if productos:
            print("Sample products:")
            for p in productos[:3]:
                print(f"  - {p.get('description', 'No description')[:80]}...")
        
        print("-" * 80)
from app import routes