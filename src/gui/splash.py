import os
import sys
import time
import tkinter as tk

class SplashWindow(tk.Toplevel):
    """Ventana Splash personalizada con barra de progreso para la carga inicial de la aplicación."""
    def __init__(self, parent, image_path):
        super().__init__(parent)
        self.overrideredirect(True)
        
        width = 550
        height = 350
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        self.configure(bg="#0f172a")
        
        try:
            from PIL import Image as PILImage, ImageTk as PILImageTk
            self.bg_image = PILImage.open(image_path)
            self.bg_photo = PILImageTk.PhotoImage(self.bg_image)
            self.label_bg = tk.Label(self, image=self.bg_photo, borderwidth=0, highlightthickness=0)
            self.label_bg.pack(fill="both", expand=True)
        except Exception:
            self.label_bg = tk.Label(self, text="Playwright API Capturer", fg="#f8fafc", bg="#0f172a", font=("Segoe UI", 16, "bold"))
            self.label_bg.pack(pady=40)
            
        self.progress_bar = tk.Frame(self.label_bg, bg="#06b6d4", height=6)
        self.progress_bar.place(x=50, y=270, width=0)
        
        self.status_label = tk.Label(self.label_bg, 
                                     text="Inicializando...", 
                                     fg="#94a3b8", 
                                     bg="#0f172a", 
                                     font=("Segoe UI", 10))
        self.status_label.place(x=50, y=295, width=450, anchor="w")
        
        self.update()

    def update_status(self, value, text):
        new_width = int(450 * (value / 100.0))
        self.progress_bar.place(width=new_width)
        self.status_label.config(text=text)
        self.update()

def cargar_modulos_y_dependencias(progress_callback=None):
    """Carga de forma secuencial y diferida los módulos principales y el motor Playwright."""
    if progress_callback:
        progress_callback(10, "Cargando dependencias del sistema...")
        time.sleep(0.15)
        
    if getattr(sys, 'frozen', False):
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(local_appdata, "ms-playwright")
            
    if progress_callback:
        progress_callback(35, "Cargando motor Playwright...")
        time.sleep(0.15)
        
    from playwright.async_api import async_playwright
    
    if progress_callback:
        progress_callback(70, "Cargando módulos de captura...")
        time.sleep(0.15)
        
    try:
        from src.captura_api import (
            generar_script_unificado,
            generar_script_python,
            limpiar_headers,
            generar_script_automatizacion_dom,
            generar_lista_selectores_json,
            generar_reporte_selectores_txt,
            generar_nombre_campo_auto,
            generar_script_scraping,
            generar_script_scraping_bs4
        )
    except ImportError:
        pass
        
    if progress_callback:
        progress_callback(95, "Finalizando preparación de GUI...")
        time.sleep(0.2)
