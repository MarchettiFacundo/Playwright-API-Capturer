"""
Módulo Fachada (Facade) para captura y generación de scripts.
Re-exporta todas las funciones de utilidades, generadores y motor de captura
manteniendo compatibilidad retroactiva completa con el sistema.
"""

import sys
import os

if getattr(sys, 'frozen', False):
    root_dir = sys._MEIPASS
else:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.utils.helpers import (
    limpiar_headers,
    parsear_seleccion
)

from src.generators.api_generator import (
    extraer_token_de_valor,
    buscar_clave_de_valor,
    formatear_path_seguro,
    formatear_payload_python,
    generar_script_python,
    generar_script_unificado
)

from src.generators.dom_generator import (
    resolver_locator_playwright,
    generar_script_automatizacion_dom,
    generar_lista_selectores_json,
    generar_reporte_selectores_txt
)

from src.generators.scraper_generator import (
    generar_nombre_campo_auto,
    generar_script_scraping,
    generar_script_scraping_bs4
)

from src.capture.cli_interceptor import interceptor_manual

if __name__ == "__main__":
    interceptor_manual("https://rpa-site.claro.amx/")
