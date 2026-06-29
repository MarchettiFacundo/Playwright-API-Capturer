import sys
import os

# Asegurar que el directorio raíz esté en sys.path para resolución de módulos en PyInstaller
if getattr(sys, 'frozen', False):
    root_dir = sys._MEIPASS
else:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import tkinter as tk
from tkinter import messagebox

_splash_disponible = False
try:
    import pyi_splash
    _splash_disponible = True
except ImportError:
    pass

from src.utils.helpers import (
    is_dir_writable,
    get_documents_folder,
    find_chrome_path,
    find_edge_path,
    is_port_in_use,
    obtener_ruta_recurso,
    limpiar_headers,
    parsear_seleccion
)
from src.utils.updater import (
    VERSION_LOCAL,
    verificar_actualizaciones,
    descargar_y_ejecutar_instalador
)
from src.capture.js_templates import JS_SCRIPT
from src.capture.playwright_thread import PlaywrightCaptureThread
from src.generators.api_generator import (
    generar_script_unificado,
    generar_script_python
)
from src.generators.dom_generator import (
    generar_script_automatizacion_dom,
    generar_lista_selectores_json,
    generar_reporte_selectores_txt
)
from src.generators.scraper_generator import (
    generar_nombre_campo_auto,
    generar_script_scraping,
    generar_script_scraping_bs4
)
from src.gui.splash import SplashWindow, cargar_modulos_y_dependencias
from src.gui.main_app import CapturaApp

def main():
    root = tk.Tk()
    root.withdraw()
    
    ruta_splash = obtener_ruta_recurso(os.path.join("assets", "splash.png"))
    splash = SplashWindow(root, ruta_splash)
    
    if _splash_disponible:
        try:
            pyi_splash.close()
        except Exception:
            pass
            
    def ejecutar_carga():
        try:
            cargar_modulos_y_dependencias(progress_callback=splash.update_status)
            splash.destroy()
            app = CapturaApp(root)
            root.deiconify()
        except Exception as err:
            messagebox.showerror("Error de Inicialización", f"Error al cargar la aplicación:\n{err}")
            root.destroy()
            
    root.after(100, ejecutar_carga)
    root.mainloop()

if __name__ == "__main__":
    main()
