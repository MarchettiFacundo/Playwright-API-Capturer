import sys
import os

# Asegurar que el directorio raíz esté en sys.path para resolución de módulos en PyInstaller
if getattr(sys, 'frozen', False):
    root_dir = sys._MEIPASS
else:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import json
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb

_splash_disponible = False
try:
    import pyi_splash
    _splash_disponible = True
except ImportError:
    pass

from src.utils.helpers import (
    is_dir_writable,
    get_documents_folder,
    obtener_ruta_recurso,
    habilitar_hi_dpi,
    aplicar_barra_titulo_oscura
)
from src.gui.splash import SplashWindow, cargar_modulos_y_dependencias
from src.gui.main_app import CapturaApp

def obtener_tema_guardado():
    """Recupera el tema guardado en config_gui.json o devuelve 'superhero' por defecto."""
    try:
        if getattr(sys, 'frozen', False):
            dir_ejecutable = os.path.dirname(sys.executable)
            raiz = os.path.dirname(dir_ejecutable) if os.path.basename(dir_ejecutable).lower() == "dist" else dir_ejecutable
        else:
            raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        base_dir = raiz if is_dir_writable(raiz) else os.path.join(get_documents_folder(), "Playwright API Capturer")
        cfg_file = os.path.join(base_dir, "config_gui.json")
        if os.path.exists(cfg_file):
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("tema", "superhero")
    except Exception:
        pass
    return "superhero"

def main():
    habilitar_hi_dpi()
    tema_inicial = obtener_tema_guardado()
    
    root = tb.Window(themename=tema_inicial)
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
            app = CapturaApp(root, tema_inicial=tema_inicial)
            root.deiconify()
            es_oscuro = tema_inicial.lower() in {"superhero", "darkly", "cyborg", "solar", "vapor"}
            aplicar_barra_titulo_oscura(root, oscuro=es_oscuro)
        except Exception as err:
            messagebox.showerror("Error de Inicialización", f"Error al cargar la aplicación:\n{err}")
            root.destroy()
            
    root.after(100, ejecutar_carga)
    root.mainloop()

if __name__ == "__main__":
    main()
