import sys
import os

# Módulos y funciones globales para importación diferida/dinámica
async_playwright = None
limpiar_headers = None
generar_script_unificado = None
generar_script_python = None
generar_script_automatizacion_dom = None
generar_lista_selectores_json = None
generar_reporte_selectores_txt = None
generar_nombre_campo_auto = None
generar_script_scraping = None
generar_script_scraping_bs4 = None

# 1. Intentar configurar una variable para saber si el splash nativo de PyInstaller estuvo activo
_splash_disponible = False
try:
    import pyi_splash
    _splash_disponible = True
except ImportError:
    pass

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import queue
import json
import glob
import subprocess

VERSION_LOCAL = "1.1.9"

def is_dir_writable(path):
    try:
        test_file = os.path.join(path, ".test_write")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception:
        return False

def get_documents_folder():
    try:
        import ctypes
        from ctypes import wintypes
        CSIDL_PERSONAL = 5
        SHGFP_TYPE_CURRENT = 0
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
        return buf.value
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Documents")

def verificar_actualizaciones(app_instance, manual=False):
    def check():
        import urllib.request
        import json
        url_version_remota = "https://raw.githubusercontent.com/MarchettiFacundo/Playwright-API-Capturer/main/version.json"
        try:
            req = urllib.request.Request(
                url_version_remota, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                version_remota = data.get("version")
                url_descarga = data.get("download_url")
                installer_url = data.get("installer_url")
                
                if version_remota:
                    try:
                        v_local_parts = [int(x) for x in VERSION_LOCAL.split('.')]
                        v_remota_parts = [int(x) for x in version_remota.split('.')]
                    except ValueError:
                        v_local_parts = [0]
                        v_remota_parts = [0]
                        
                    if v_remota_parts > v_local_parts:
                        app_instance.root.after(0, lambda: notificar_actualizacion(version_remota, url_descarga, installer_url))
                    else:
                        if manual:
                            app_instance.root.after(0, lambda: messagebox.showinfo(
                                "Sin actualizaciones", 
                                f"Tu aplicación está actualizada a la última versión (v{VERSION_LOCAL})."
                            ))
                else:
                    if manual:
                        app_instance.root.after(0, lambda: messagebox.showerror(
                            "Error", 
                            "No se pudo verificar el archivo de versión remota."
                        ))
        except Exception as e:
            if manual:
                app_instance.root.after(0, lambda: messagebox.showerror(
                    "Error de Conexión", 
                    f"No se pudo conectar al servidor de actualizaciones:\n{e}"
                ))

    def notificar_actualizacion(v_remota, url_web, url_installer):
        res = messagebox.askyesnocancel(
            "Actualización Disponible", 
            f"¡Una nueva versión (v{v_remota}) está disponible!\n"
            f"Tu versión actual es la v{VERSION_LOCAL}.\n\n"
            "¿Deseas descargar e instalar automáticamente la actualización ahora?\n"
            "Pulse 'Sí' para actualizar automáticamente, 'No' para descargar de forma manual en el navegador o 'Cancelar' para ignorarla."
        )
        if res is True:
            if url_installer:
                descargar_y_ejecutar_instalador(app_instance, url_installer, v_remota)
            else:
                messagebox.showwarning("Aviso", "No se detectó un enlace directo para el instalador. Se procederá con la descarga manual.")
                import webbrowser
                webbrowser.open(url_web)
        elif res is False:
            import webbrowser
            webbrowser.open(url_web)

    threading.Thread(target=check, daemon=True).start()

def descargar_y_ejecutar_instalador(app_instance, url_installer, version_nueva):
    # Crear ventana modal de descarga
    download_win = tk.Toplevel(app_instance.root)
    download_win.title("Actualizando Aplicación")
    download_win.geometry("380x150")
    download_win.resizable(False, False)
    download_win.configure(bg=app_instance.color_bg)
    download_win.transient(app_instance.root)
    download_win.grab_set()
    
    # Centrar ventana modal
    download_win.update_idletasks()
    w = download_win.winfo_width()
    h = download_win.winfo_height()
    x = app_instance.root.winfo_x() + (app_instance.root.winfo_width() - w) // 2
    y = app_instance.root.winfo_y() + (app_instance.root.winfo_height() - h) // 2
    download_win.geometry(f"+{x}+{y}")
    
    lbl_info = tk.Label(
        download_win, 
        text=f"Descargando actualización v{version_nueva}...\nPor favor, espere.", 
        fg=app_instance.color_fg, 
        bg=app_instance.color_bg, 
        font=("Segoe UI", 10),
        justify="left"
    )
    lbl_info.pack(pady=(20, 10), padx=20, anchor="w")
    
    # Barra de progreso cian
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Download.Horizontal.TProgressbar", 
                     troughcolor="#1e293b", 
                     background="#06b6d4", 
                     thickness=12, 
                     borderwidth=0)
    
    progress = ttk.Progressbar(
        download_win, 
        style="Download.Horizontal.TProgressbar", 
        orient="horizontal", 
        length=340, 
        mode="determinate"
    )
    progress.pack(pady=10, padx=20)
    
    cancelled = [False]
    
    def on_close():
        if messagebox.askyesno("Cancelar Descarga", "¿Estás seguro de que deseas cancelar la descarga de la actualización?"):
            cancelled[0] = True
            download_win.destroy()
            
    download_win.protocol("WM_DELETE_WINDOW", on_close)
    
    def download_thread():
        import urllib.request
        import tempfile
        
        try:
            req = urllib.request.Request(
                url_installer, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                total_size = int(response.info().get('Content-Length', 0))
                bytes_descargados = 0
                
                temp_dir = tempfile.gettempdir()
                temp_file_path = os.path.join(temp_dir, f"Playwright_API_Capturer_Setup_{version_nueva}.exe")
                
                with open(temp_file_path, "wb") as f_out:
                    chunk_size = 16384 # 16KB
                    while True:
                        if cancelled[0]:
                            return
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        bytes_descargados += len(chunk)
                        
                        if total_size > 0:
                            percent = int(100 * bytes_descargados / total_size)
                            download_win.after(0, lambda p=percent: actualizar_progreso(p))
                            
                if not cancelled[0]:
                    download_win.after(0, lambda: finalizar_y_ejecutar(temp_file_path))
                    
        except Exception as e:
            if not cancelled[0]:
                download_win.after(0, lambda err=e: manejar_error_descarga(err))
                
    def actualizar_progreso(percent):
        progress["value"] = percent
        lbl_info.config(text=f"Descargando actualización v{version_nueva}...\nProgreso: {percent}%")
        download_win.update()
        
    def finalizar_y_ejecutar(file_path):
        download_win.destroy()
        messagebox.showinfo("Instalación Lista", "Descarga completada con éxito.\nSe iniciará el instalador y la aplicación se cerrará para permitir la actualización.")
        try:
            os.startfile(file_path)
            app_instance.root.destroy()
            sys.exit(0)
        except Exception as e:
            messagebox.showerror("Error al Ejecutar", f"No se pudo ejecutar el instalador automáticamente:\n{e}\nPuedes ejecutarlo manualmente en:\n{file_path}")
            
    def manejar_error_descarga(err):
        download_win.destroy()
        if messagebox.askyesno(
            "Error de Descarga", 
            f"No se pudo completar la descarga automática debido al siguiente error:\n{err}\n\n"
            "¿Deseas intentar descargar la actualización manualmente desde tu navegador?"
        ):
            import webbrowser
            url_releases = "https://github.com/MarchettiFacundo/Playwright-API-Capturer/releases/latest"
            webbrowser.open(url_releases)
            
    threading.Thread(target=download_thread, daemon=True).start()

def obtener_ruta_recurso(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

class SplashWindow(tk.Toplevel):
    def __init__(self, parent, image_path):
        super().__init__(parent)
        self.overrideredirect(True)
        
        # Dimensiones de la ventana (550x350 para que coincida con la imagen generada)
        width = 550
        height = 350
        
        # Centrar la ventana en la pantalla
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Configurar colores y estilos
        self.configure(bg="#0f172a") # #0f172a
        
        # Cargar imagen usando PIL
        try:
            from PIL import Image as PILImage, ImageTk as PILImageTk
            self.bg_image = PILImage.open(image_path)
            self.bg_photo = PILImageTk.PhotoImage(self.bg_image)
            self.label_bg = tk.Label(self, image=self.bg_photo, borderwidth=0, highlightthickness=0)
            self.label_bg.pack(fill="both", expand=True)
        except Exception as e:
            # Fallback simple si falla la carga de la imagen
            self.label_bg = tk.Label(self, text="Playwright API Capturer", fg="#f8fafc", bg="#0f172a", font=("Segoe UI", 16, "bold"))
            self.label_bg.pack(pady=40)
            
        # Crear barra de progreso cian usando un tk.Frame para evitar fallos de estilos de temas
        self.progress_bar = tk.Frame(self.label_bg, bg="#06b6d4", height=6)
        self.progress_bar.place(x=50, y=270, width=0)
        
        # Label de estado
        self.status_label = tk.Label(self.label_bg, 
                                     text="Inicializando...", 
                                     fg="#94a3b8", 
                                     bg="#0f172a", 
                                     font=("Segoe UI", 10))
        self.status_label.place(x=50, y=295, width=450, anchor="w")
        
        # Forzar actualización inicial
        self.update()

    def update_status(self, value, text):
        new_width = int(450 * (value / 100.0))
        self.progress_bar.place(width=new_width)
        self.status_label.config(text=text)
        self.update()

def cargar_modulos_y_dependencias(progress_callback=None):
    global async_playwright, limpiar_headers, generar_script_unificado
    global generar_script_python, generar_script_automatizacion_dom
    global generar_lista_selectores_json, generar_reporte_selectores_txt
    global generar_nombre_campo_auto, generar_script_scraping, generar_script_scraping_bs4
    
    import time
    
    if progress_callback:
        progress_callback(10, "Cargando dependencias del sistema...")
        time.sleep(0.15)
        
    # Redirigir variables de entorno de Playwright si está compilado
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
        
    # Añadir el directorio actual al path para importar captura_api de forma robusta
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        from captura_api import (
            generar_script_unificado as g_unificado, 
            generar_script_python as g_python, 
            limpiar_headers as l_headers, 
            generar_script_automatizacion_dom as g_dom, 
            generar_lista_selectores_json as g_json, 
            generar_reporte_selectores_txt as g_txt,
            generar_nombre_campo_auto as g_nombre_auto,
            generar_script_scraping as g_scraping,
            generar_script_scraping_bs4 as g_scraping_bs4
        )
        limpiar_headers = l_headers
        generar_script_unificado = g_unificado
        generar_script_python = g_python
        generar_script_automatizacion_dom = g_dom
        generar_lista_selectores_json = g_json
        generar_reporte_selectores_txt = g_txt
        generar_nombre_campo_auto = g_nombre_auto
        generar_script_scraping = g_scraping
        generar_script_scraping_bs4 = g_scraping_bs4
    except ImportError:
        def l_headers(headers):
            return {k: v for k, v in headers.items() if k.lower() not in ['host', 'connection']}
        def g_unificado(peticiones, nombre_archivo, parametrizar=False):
            pass
        def g_python(peticion, nombre_archivo, parametrizar=False):
            pass
        def g_dom(acciones, nombre_archivo, parametrizar=False):
            pass
        def g_json(acciones, nombre_archivo):
            pass
        def g_txt(acciones, nombre_archivo):
            pass
        def g_nombre_auto(accion):
            return f"campo_{(accion.get('tagName') or 'el').lower()}"
        def g_scraping(campos, url, config, nombre_archivo="scraper.py", parametrizar=False):
            pass
        def g_scraping_bs4(campos, url, config, nombre_archivo="scraper_bs4.py"):
            pass
            
        limpiar_headers = l_headers
        generar_script_unificado = g_unificado
        generar_script_python = g_python
        generar_script_automatizacion_dom = g_dom
        generar_lista_selectores_json = g_json
        generar_reporte_selectores_txt = g_txt
        generar_nombre_campo_auto = g_nombre_auto
        generar_script_scraping = g_scraping
        generar_script_scraping_bs4 = g_scraping_bs4
        
    if progress_callback:
        progress_callback(95, "Finalizando preparación de GUI...")
        time.sleep(0.2)

# JS inyectado en el navegador para capturar selectores semánticos en caliente
JS_SCRIPT = r"""
(function() {
    if (window.__domCapturerInjected) return;
    window.__domCapturerInjected = true;
    
    function esIdValido(id) {
        if (!id) return false;
        if (id.includes("#")) return false; // IDs con '#' (como SAP WebGUI tree nodes) son altamente dinámicos e inestables en CSS
        if (id.includes("-") && /\d+/.test(id)) return false;
        if (id.includes("_") && /\d+/.test(id)) return false;
        if (id.startsWith("sap-ui-id")) return false;
        if (id.startsWith("sap-comp")) return false;
        if (id.includes("::")) return false;
        if (isNaN(id.charAt(0)) === false) return false;
        return true;
    }

    function obtenerXPath(el) {
        if (el.id && esIdValido(el.id)) return `//*[@id="${el.id}"]`;
        if (el === document.body) return '/html/body';
        let siblingCount = 0;
        let siblings = el.parentNode ? el.parentNode.childNodes : [];
        for (let i = 0; i < siblings.length; i++) {
            let sibling = siblings[i];
            if (sibling === el) {
                return obtenerXPath(el.parentNode) + '/' + el.tagName.toLowerCase() + '[' + (siblingCount + 1) + ']';
            }
            if (sibling.nodeType === 1 && sibling.tagName === el.tagName) {
                siblingCount++;
            }
        }
        return '';
    }

    function obtenerSelectorOptimo(el, tipoAccion) {
        let tag = el.tagName.toLowerCase();
        let esExtraccion = (tipoAccion === 'extract');
        
        // 1. Selector por etiqueta asociada (get_by_label)
        let labelText = "";
        if (el.id) {
            let labelEl = document.querySelector(`label[for="${el.id}"]`);
            if (labelEl) labelText = labelEl.textContent.trim();
        }
        if (!labelText) {
            let parentLabel = el.closest('label');
            if (parentLabel) {
                labelText = Array.from(parentLabel.childNodes)
                    .filter(node => node.nodeType === Node.TEXT_NODE)
                    .map(node => node.textContent.trim())
                    .join(" ").trim();
            }
        }
        if (labelText && labelText.length > 0 && labelText.length < 50) {
            return `label="${labelText.replace(/"/g, '\\"')}"`;
        }

        // 2. Selector por placeholder (get_by_placeholder)
        let placeholder = el.getAttribute("placeholder");
        if (placeholder && placeholder.trim().length > 0) {
            return `placeholder="${placeholder.trim().replace(/"/g, '\\"')}"`;
        }
        
        // 3. Selector por rol de accesibilidad (get_by_role)
        let role = el.getAttribute("role");
        if (!role) {
            if (tag === 'button' || (tag === 'input' && ['button', 'submit', 'reset'].includes(el.type))) {
                role = 'button';
            } else if (tag === 'a') {
                role = 'link';
            } else if (tag === 'input' && ['checkbox', 'radio'].includes(el.type)) {
                role = el.type;
            } else if (tag === 'select') {
                role = 'combobox';
            } else if (tag === 'textarea' || (tag === 'input' && ['text', 'email', 'password', 'tel', 'url', 'number', 'search'].includes(el.type))) {
                role = 'textbox';
            } else if (tag.match(/^h[1-6]$/)) {
                role = 'heading';
            }
        }

        if (role) {
            let roleName = "";
            if (role === 'button' || role === 'link' || role === 'heading') {
                // Si es extracción, NO usamos textContent/innerText porque es el dato dinámico a extraer
                if (!esExtraccion) {
                    roleName = el.textContent.trim() || el.value || el.getAttribute("aria-label") || "";
                } else {
                    // Usar sólo atributos estables si existen
                    roleName = el.getAttribute("aria-label") || el.title || "";
                }
            } else if (role === 'textbox') {
                roleName = el.getAttribute("aria-label") || el.title || "";
            }
            roleName = roleName.replace(/\s+/g, ' ').trim();
            if (roleName && roleName.length > 0 && roleName.length < 50) {
                return `role:${role}[name="${roleName.replace(/"/g, '\\"')}_"]`.replace(/_"]$/, '"]');
            }
        }

        // 4. Selector por texto visible corto (get_by_text) - Omitido por completo en extracciones
        if (!esExtraccion) {
            let textContent = el.textContent ? el.textContent.trim() : "";
            if ((tag === 'span' || tag === 'div' || tag === 'p' || tag === 'td' || tag === 'th') && textContent.length > 0 && textContent.length < 40) {
                return `text="${textContent.replace(/"/g, '\\"')}"`;
            }
        }

        // 5. IDs estáticos
        if (el.id && esIdValido(el.id)) {
            return `id=${el.id}`;
        }
        
        // 6. Name
        if (el.name) return `[name="${el.name}"]`;
        
        // 7. Clases CSS como último recurso antes de XPath
        if (el.className) {
            let clases = Array.from(el.classList).filter(c => !c.includes("hover") && !c.includes("active")).join(".");
            if (clases) return `${tag}.${clases}`;
        }
        return `xpath=${obtenerXPath(el)}`;
    }

    function obtenerDescriptorLegible(el) {
        let tag = el.tagName.toLowerCase();
        let text = el.textContent ? el.textContent.trim() : "";
        if (text.length > 30) text = text.substring(0, 27) + "...";
        
        if (tag === "button" || el.getAttribute("role") === "button") {
            return `Botón${text ? ` "${text}"` : ""}`;
        }
        if (tag === "a") {
            return `Enlace${text ? ` "${text}"` : ""}`;
        }
        if (tag === "input") {
            let type = el.getAttribute("type") || "text";
            let desc = el.id || el.name || el.getAttribute("placeholder") || "";
            return `Campo ${type}${desc ? ` "${desc}"` : ""}`;
        }
        if (tag === "select") {
            let desc = el.id || el.name || "";
            return `Selector${desc ? ` "${desc}"` : ""}`;
        }
        if (tag === "textarea") {
            let desc = el.id || el.name || "";
            return `Área de texto${desc ? ` "${desc}"` : ""}`;
        }
        if (tag === "td" || tag === "th") {
            return `Celda de tabla${text ? ` "${text}"` : ""}`;
        }
        if (tag === "tr") {
            return `Fila de tabla`;
        }
        if (tag.match(/^h[1-6]$/)) {
            return `Título "${text}"`;
        }
        if (tag === "p") {
            return `Párrafo "${text}"`;
        }
        if (tag === "div" || tag === "span") {
            return `Texto/Contenedor${text ? ` "${text}"` : ""}`;
        }
        return `Elemento <${tag}>${text ? ` "${text}"` : ""}`;
    }

    function enviarAccion(el, tipoAccion, valorOverride) {
        try {
            if (!window.registrarAccionDOM) return;
            
            let tag = el.tagName.toLowerCase();
            let valor = valorOverride !== undefined ? valorOverride : (el.value || "");
            
            if (tipoAccion === 'extract') {
                valor = el.innerText || el.textContent || "";
                valor = valor.trim();
            } else if (tag === "input" && (el.type === "checkbox" || el.type === "radio")) {
                valor = el.checked ? "checked" : "unchecked";
            }

            let datos = {
                tipo_accion: tipoAccion,
                tagName: el.tagName,
                descriptor_legible: obtenerDescriptorLegible(el),
                selector_sugerido: obtenerSelectorOptimo(el, tipoAccion),
                valor: valor,
                id: el.id || "",
                name: el.name || "",
                className: el.className || "",
                type: el.getAttribute("type") || "",
                placeholder: el.getAttribute("placeholder") || "",
                xpath: obtenerXPath(el),
                outerHTML: el.outerHTML || ""
            };
            
            window.registrarAccionDOM(JSON.stringify(datos));
        } catch (err) {
            console.error("Error al registrar acción DOM:", err);
        }
    }

    document.addEventListener('click', (e) => {
        let esExtraccion = e.shiftKey || e.ctrlKey || e.altKey;
        let el;
        
        if (esExtraccion) {
            el = e.target;
            e.preventDefault();
            e.stopPropagation();
        } else {
            el = e.target.closest('button, a, input, select, textarea, [role="button"]');
            
            if (!el) {
                let current = e.target;
                let depth = 0;
                while (current && current !== document.body && depth < 4) {
                    let style = window.getComputedStyle(current);
                    if (style && style.cursor === 'pointer') {
                        el = current;
                        break;
                    }
                    if (current.onclick || current.getAttribute('onclick')) {
                        el = current;
                        break;
                    }
                    current = current.parentElement;
                    depth++;
                }
            }
        }
        
        if (!el) return;
        
        let tag = el.tagName.toLowerCase();
        if (!esExtraccion) {
            if (tag === "input" && !["button", "submit", "reset", "checkbox", "radio", "image"].includes(el.type)) {
                return;
            }
            if (tag === "select" || tag === "textarea") {
                return;
            }
        }
        
        if (esExtraccion) {
            enviarAccion(el, 'extract');
        } else {
            enviarAccion(el, 'click');
        }
    }, true);

    document.addEventListener('input', (e) => {
        let el = e.target;
        let tag = el.tagName.toLowerCase();
        if (tag === "input" && !["button", "submit", "reset", "checkbox", "radio", "image"].includes(el.type)) {
            enviarAccion(el, 'fill');
        } else if (tag === "textarea") {
            enviarAccion(el, 'fill');
        }
    }, true);

    document.addEventListener('change', (e) => {
        let el = e.target;
        let tag = el.tagName.toLowerCase();
        if (tag === "select") {
            let seleccion = el.options[el.selectedIndex].text;
            enviarAccion(el, 'select', seleccion);
        }
    }, true);
})();
"""

# Definición del Hilo de Captura de Playwright
class PlaywrightCaptureThread(threading.Thread):
    def __init__(self, url, output_queue, video_dir="output_videos", trace_file="trace.zip", log_file="debug_playwright.log", 
                 modo="APIs de Red (HTTP)", navegador="Chromium", viewport_width=1280, viewport_height=720, ignore_ssl_errors=True,
                 headless=False, record_video=True, record_trace=True, timeout=30, user_agent=""):
        super().__init__()
        self.url = url
        self.output_queue = output_queue
        self.video_dir = video_dir
        self.trace_file = trace_file
        self.log_file = log_file
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.ignore_ssl_errors = ignore_ssl_errors
        self.modo = modo
        self.navegador = navegador
        self.headless = headless
        self.record_video = record_video
        self.record_trace = record_trace
        self.timeout = timeout
        self.user_agent = user_agent
        self.browser = None
        self.context = None
        self.playwright = None
        self.stop_event = threading.Event()
        self.paused = False
        
        # Cola de entrada para recibir comandos desde la GUI de forma segura entre hilos
        self.input_queue = queue.Queue()

    def run(self):
        import asyncio
        # Configurar la política de event loop para hilos secundarios en Windows
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
            
        asyncio.run(self.capturar_async())

    async def capturar_async(self):
        import asyncio
        try:
            os.makedirs(self.video_dir, exist_ok=True)
            
            self.output_queue.put(("status", "Iniciando Playwright..."))
            self.playwright = await async_playwright().start()
            
            # Lanzamos el motor de navegador seleccionado (headless configurable)
            if self.navegador == "Firefox":
                self.browser = await self.playwright.firefox.launch(headless=self.headless)
            elif self.navegador == "WebKit":
                self.browser = await self.playwright.webkit.launch(headless=self.headless)
            else:
                self.browser = await self.playwright.chromium.launch(headless=self.headless)
            
            # Creamos el contexto de manera dinámica según las opciones del usuario
            context_args = {
                "ignore_https_errors": self.ignore_ssl_errors,
                "viewport": {"width": self.viewport_width, "height": self.viewport_height}
            }
            if self.record_video:
                context_args["record_video_dir"] = self.video_dir
                context_args["record_video_size"] = {"width": self.viewport_width, "height": self.viewport_height}
            if self.user_agent and self.user_agent.strip():
                context_args["user_agent"] = self.user_agent.strip()
                
            self.context = await self.browser.new_context(**context_args)
            
            # Configurar el timeout global si se especificó
            if self.timeout > 0:
                self.context.set_default_timeout(self.timeout * 1000)
            
            # Iniciamos el tracing de Playwright condicionalmente
            if self.record_trace:
                await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)

            if self.modo == "APIs de Red (HTTP)":
                async def interceptar_respuesta(response):
                    if self.paused:
                        return
                    if response.request.resource_type in ["fetch", "xhr"]:
                        request = response.request
                        if request.method == "OPTIONS":
                            return
                        try:
                            # Capturamos post_data de forma asíncrona
                            post_data = request.post_data
                            
                            datos = {
                                "url": response.url,
                                "metodo": request.method,
                                "status": response.status,
                                "headers_peticion": dict(request.headers),
                                "headers_respuesta": dict(response.headers),
                                "payload_enviado": post_data,
                                "respuesta": None,
                                "seleccionado": True
                            }
                            
                            if response.ok:
                                try:
                                    content_type = (await response.header_value("content-type") or "").lower()
                                    if "event-stream" in content_type:
                                        datos["respuesta"] = "<Streaming Event Stream>"
                                    elif response.status == 204:
                                        datos["respuesta"] = "<Sin Contenido (204 No Content)>"
                                    else:
                                        try:
                                            datos["respuesta"] = await response.json()
                                        except Exception:
                                            try:
                                                datos["respuesta"] = await response.text()
                                            except Exception as text_e:
                                                datos["respuesta"] = f"<No se pudo leer cuerpo: {str(text_e)}>"
                                except Exception as body_e:
                                    datos["respuesta"] = f"<Error leyendo cuerpo: {str(body_e)}>"
                            else:
                                try:
                                    datos["respuesta"] = await response.text()
                                except Exception:
                                    datos["respuesta"] = f"<Respuesta con error status {response.status}>"

                            try:
                                with open(self.log_file, "a", encoding="utf-8") as f:
                                    f.write(f"Callback interceptar_respuesta: {datos.get('metodo')} {datos.get('url')[:60]}\n")
                            except Exception:
                                pass
                            self.output_queue.put(("peticion", datos))
                            
                        except Exception as e:
                            print(f"[WARN] Error en interceptar_respuesta: {e}")

                self.context.on("response", interceptar_respuesta)
            else:
                # Modo Grabador DOM (Acciones)
                async def registrar_accion(source, datos_json):
                    if self.paused:
                        return
                    try:
                        datos = json.loads(datos_json)
                        datos["seleccionado"] = True
                        
                        # Resolver jerarquía de iFrames en caliente
                        ruta_iframes = []
                        try:
                            # Acceder de forma segura a frame y page (soporta dict y objetos)
                            curr_frame = source.get("frame") if isinstance(source, dict) else getattr(source, "frame", None)
                            page_obj = source.get("page") if isinstance(source, dict) else getattr(source, "page", None)
                            main_frame = page_obj.main_frame if page_obj else None
                            
                            # Diagnóstico en debug log
                            with open(self.log_file, "a", encoding="utf-8") as debug_file:
                                debug_file.write(f"[DEBUG_FRAME] source.frame: name={curr_frame.name if curr_frame else None!r}, url={curr_frame.url[:120] if curr_frame else None!r}\n")
                                debug_file.write(f"[DEBUG_FRAME] main_frame: name={main_frame.name if main_frame else None!r}, url={main_frame.url[:120] if main_frame else None!r}\n")
                                debug_file.write(f"[DEBUG_FRAME] es_main_frame: {curr_frame == main_frame}\n")
                            
                            while curr_frame and curr_frame != main_frame:
                                iframe_handle = await curr_frame.frame_element()
                                if iframe_handle:
                                    iframe_id = await iframe_handle.get_attribute("id")
                                    iframe_name = await iframe_handle.get_attribute("name")
                                    iframe_src = await iframe_handle.get_attribute("src")
                                    
                                    with open(self.log_file, "a", encoding="utf-8") as debug_file:
                                        debug_file.write(f"[DEBUG_FRAME] Encontrado iframe: id={iframe_id!r}, name={iframe_name!r}, src={iframe_src[:120]!r}\n")
                                    
                                    # Generar un selector lo más estable posible para el iframe
                                    if iframe_id and not "-" in iframe_id and not iframe_id[0].isdigit() and not "itsframe" in iframe_id.lower():
                                        selector = f"#{iframe_id}"
                                    elif iframe_name:
                                        # Si el name contiene "itsframe" u otros patrones típicos de SAP, usamos selector parcial
                                        if "itsframe" in iframe_name.lower():
                                            selector = "iframe[name*='itsframe' i]"
                                        else:
                                            selector = f"[name='{iframe_name}']"
                                    elif iframe_src:
                                        base_src = iframe_src.split("?")[0]
                                        selector = f"iframe[src*='{base_src}']"
                                    else:
                                        selector = "iframe"
                                    ruta_iframes.insert(0, selector)
                                curr_frame = curr_frame.parent_frame
                        except Exception as frame_err:
                            import traceback
                            with open(self.log_file, "a", encoding="utf-8") as debug_file:
                                debug_file.write(f"[WARN] Error resolviendo ruta de iframes: {frame_err}\n")
                                debug_file.write(traceback.format_exc() + "\n")
                            
                        datos["ruta_iframes"] = ruta_iframes
                        
                        # Modificar el descriptor legible si está en un iframe para visibilidad en la GUI
                        if ruta_iframes:
                            ruta_visual = " -> ".join(ruta_iframes)
                            datos["descriptor_legible"] = f"[{ruta_visual}] {datos['descriptor_legible']}"
                            
                        try:
                            with open(self.log_file, "a", encoding="utf-8") as f:
                                f.write(f"Callback registrar_accion: {datos.get('tipo_accion')} {datos.get('descriptor_legible')}\n")
                        except Exception:
                            pass

                        # Marcar la fase (setup vs extract) para el modo Scraper
                        if "Scraper" in self.modo:
                            tipo_accion = datos.get("tipo_accion", "")
                            datos["fase_scraper"] = "extract" if tipo_accion == "extract" else "setup"

                        self.output_queue.put(("accion_dom", datos))
                    except Exception as err:
                        print(f"[WARN] Error parseando JSON de acción DOM: {err}")


                await self.context.expose_binding("registrarAccionDOM", registrar_accion)
                await self.context.add_init_script(JS_SCRIPT)

                # En modo Scraper: también interceptar requests POST/PUT para capturar login de red
                if "Scraper" in self.modo:
                    async def interceptar_posts_scraper(response):
                        try:
                            metodo = response.request.method.upper()
                            if metodo not in ("POST", "PUT", "PATCH"):
                                return
                            url_req = response.url
                            # Ignorar assets estáticos
                            ext_ignorar = (".css", ".js", ".png", ".jpg", ".jpeg",
                                           ".svg", ".woff", ".ico", ".gif", ".map")
                            if any(url_req.split("?")[0].lower().endswith(e) for e in ext_ignorar):
                                return

                            datos_post = {
                                "url": url_req,
                                "metodo": metodo,
                                "status": response.status,
                                "request_body": None,
                                "respuesta": None,
                            }

                            # Leer cuerpo del request
                            try:
                                post_data = response.request.post_data
                                if post_data:
                                    try:
                                        import json as _json
                                        datos_post["request_body"] = _json.loads(post_data)
                                    except Exception:
                                        datos_post["request_body"] = post_data[:1000]
                            except Exception:
                                pass

                            # Leer respuesta
                            if response.ok:
                                try:
                                    ct = (await response.header_value("content-type") or "").lower()
                                    if "json" in ct:
                                        datos_post["respuesta"] = await response.json()
                                    else:
                                        datos_post["respuesta"] = (await response.text())[:800]
                                except Exception:
                                    pass

                            self.output_queue.put(("post_red_scraper", datos_post))
                        except Exception:
                            pass

                    self.context.on("response", interceptar_posts_scraper)

            page = await self.context.new_page()
            
            def al_cerrar_pagina():
                self.output_queue.put(("status", "Página de navegación cerrada por el usuario."))
                self.stop()
                
            page.on("close", lambda p: al_cerrar_pagina())
            
            self.output_queue.put(("status", f"Navegando a {self.url}..."))
            
            # Emitir evento de navegación inicial
            if self.modo in ("Grabador DOM (Acciones)", "Scraper Visual (DOM)"):
                nav_data = {
                    "tipo_accion": "navigation",
                    "fase_scraper": "setup",
                    "tagName": "WINDOW",
                    "descriptor_legible": "Navegación Inicial",
                    "selector_sugerido": "",
                    "valor": self.url,
                    "id": "", "name": "", "className": "",
                    "type": "", "placeholder": "",
                    "xpath": "", "outerHTML": "",
                    "seleccionado": True, "ruta_iframes": []
                }
                self.output_queue.put(("accion_dom", nav_data))

            # En modo Scraper: rastrear cambios de URL (post-login, redirecciones)
            if "Scraper" in self.modo:
                self._last_scraper_url = self.url

                def on_frame_navigated(frame):
                    try:
                        if frame != page.main_frame:
                            return
                        new_url = frame.url or ""
                        if (new_url
                                and new_url != "about:blank"
                                and not new_url.startswith("data:")
                                and new_url != getattr(self, "_last_scraper_url", "")):
                            self._last_scraper_url = new_url
                            nav_ev = {
                                "tipo_accion": "navigation",
                                "fase_scraper": "setup",
                                "tagName": "WINDOW",
                                "descriptor_legible": f"Navegar a {new_url[:60]}",
                                "selector_sugerido": "",
                                "valor": new_url,
                                "id": "", "name": "", "className": "",
                                "type": "", "placeholder": "",
                                "xpath": "", "outerHTML": "",
                                "seleccionado": True, "ruta_iframes": []
                            }
                            self.output_queue.put(("accion_dom", nav_ev))
                    except Exception:
                        pass

                page.on("framenavigated", on_frame_navigated)

            try:
                await page.goto(self.url, wait_until="domcontentloaded", timeout=20000)
            except Exception as err:
                self.output_queue.put(("status", f"Advertencia navegación: {err}"))
                print(f"[WARN] Error al ir a la página inicial: {err}")

            self.output_queue.put(("status", "Captura activa. Interactúe en el navegador..."))
            
            # Bucle de espera interactivo asíncrono
            while not self.stop_event.is_set():
                if not self.browser.is_connected():
                    break
                
                # Procesar comandos entrantes desde la interfaz (ej. resaltado visual)
                try:
                    cmd_tipo, cmd_dato = self.input_queue.get_nowait()
                    if cmd_tipo == "highlight" and self.context:
                        for pg in self.context.pages:
                            try:
                                js_hl = """
                                (selector => {
                                    let el = document.querySelector(selector);
                                    if (!el) {
                                        if (selector.startsWith('xpath=')) {
                                            let xpath = selector.substring(6);
                                            let res = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                                            el = res.singleNodeValue;
                                        } else if (selector.startsWith('text=')) {
                                            let txt = selector.substring(5).replace(/^["']|["']$/g, '');
                                            el = Array.from(document.querySelectorAll('*')).find(e => e.textContent.trim() === txt);
                                        } else if (selector.startsWith('id=')) {
                                            el = document.getElementById(selector.substring(3));
                                        } else if (selector.startsWith('placeholder=')) {
                                            let plc = selector.substring(12).replace(/^["']|["']$/g, '');
                                            el = document.querySelector(`[placeholder="${plc}"]`);
                                        } else if (selector.startsWith('label=')) {
                                            let lbl = selector.substring(6).replace(/^["']|["']$/g, '');
                                            let labelEl = Array.from(document.querySelectorAll('label')).find(e => e.textContent.trim() === lbl);
                                            if (labelEl) {
                                                if (labelEl.htmlFor) el = document.getElementById(labelEl.htmlFor);
                                                else el = labelEl.querySelector('input, select, textarea');
                                            }
                                        }
                                    }
                                    if (el) {
                                        let origStyle = el.style.outline;
                                        let origTransition = el.style.transition;
                                        el.style.transition = "outline 0.15s ease-in-out";
                                        el.style.outline = "4px solid #ef4444";
                                        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                        setTimeout(() => {
                                            el.style.outline = origStyle;
                                            el.style.transition = origTransition;
                                        }, 2000);
                                    }
                                })
                                """
                                await pg.evaluate(js_hl, cmd_dato)
                            except Exception as err:
                                print(f"[WARN] Error resaltando: {err}")
                    elif cmd_tipo == "pause":
                        self.paused = cmd_dato
                except queue.Empty:
                    pass
                
                # Ceder control al event loop de asyncio nativo durmiendo 100ms
                await asyncio.sleep(0.1)

        except Exception as e:
            self.output_queue.put(("error", f"Error en captura: {e}"))
            print(f"[ERROR] Error en hilo Playwright: {e}")
        finally:
            await self.cerrar_todo_async()

    def stop(self):
        self.stop_event.set()

    async def cerrar_todo_async(self):
        self.output_queue.put(("status", "Guardando traza y cerrando navegador..."))
        try:
            if self.context and self.record_trace:
                await self.context.tracing.stop(path=self.trace_file)
        except Exception as e:
            print(f"[WARN] Error guardando traza: {e}")

        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            print(f"[WARN] Error cerrando Playwright: {e}")

        self.output_queue.put(("status", "Captura detenida. Recursos liberados."))
        self.output_queue.put(("finalizado", None))


# Aplicación GUI Principal
class CapturaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Playwright API Capturer & Generator")
        self.root.geometry("1200x750")
        self.root.minsize(1000, 600)
        
        self.queue = queue.Queue()
        self.capture_thread = None
        self.peticiones_capturadas = []
        
        import sys
        if getattr(sys, 'frozen', False):
            dir_ejecutable = os.path.dirname(sys.executable)
            if os.path.basename(dir_ejecutable).lower() == "dist":
                self.raiz_proyecto = os.path.dirname(dir_ejecutable)
            else:
                self.raiz_proyecto = dir_ejecutable
        else:
            self.raiz_proyecto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        # Determinar si la raíz del proyecto es escribible para guardar los outputs.
        # Si no es escribible (ej. instalado en Program Files), se usa la carpeta Documentos.
        if is_dir_writable(self.raiz_proyecto):
            self.output_base_dir = self.raiz_proyecto
        else:
            self.output_base_dir = os.path.join(get_documents_folder(), "Playwright API Capturer")
            os.makedirs(self.output_base_dir, exist_ok=True)
            
        self.video_dir = os.path.join(self.output_base_dir, "output_videos")
        self.trace_file = os.path.join(self.output_base_dir, "trace.zip")
        self.log_file = os.path.join(self.output_base_dir, "debug_playwright.log")
        
        # Variables de Configuración de Navegador (Playwright)
        self.config_width = tk.IntVar(value=1280)
        self.config_height = tk.IntVar(value=720)
        self.config_ignore_ssl = tk.BooleanVar(value=True)
        self.config_headless = tk.BooleanVar(value=False)
        self.config_record_video = tk.BooleanVar(value=True)
        self.config_record_trace = tk.BooleanVar(value=True)
        self.config_timeout = tk.IntVar(value=30)
        self.config_user_agent = tk.StringVar(value="")
        self.config_output_dir = tk.StringVar(value=self.output_base_dir)
        
        self.configurar_estilos()
        self.crear_widgets()
        
        self.root.after(100, self.procesar_cola)
        # Buscar actualizaciones después de 2 segundos en segundo plano
        self.root.after(2000, lambda: verificar_actualizaciones(self))

    def configurar_estilos(self):
        self.color_bg = "#0f172a"
        self.color_panel = "#1e293b"
        self.color_accent = "#6366f1"
        self.color_accent_active = "#4f46e5"
        self.color_fg = "#f8fafc"
        self.color_fg_sec = "#94a3b8"
        self.color_border = "#334155"
        self.color_success = "#10b981"
        self.color_stop = "#ef4444"
        self.color_stop_active = "#dc2626"
        
        self.root.configure(bg=self.color_bg)
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.style.configure(".", bg=self.color_bg, fg=self.color_fg, fieldbackground=self.color_panel, bordercolor=self.color_border)
        self.style.configure("TFrame", background=self.color_bg)
        self.style.configure("Panel.TFrame", background=self.color_panel, relief="flat")
        self.style.configure("TLabel", background=self.color_bg, foreground=self.color_fg, font=("Segoe UI", 10))
        self.style.configure("Panel.TLabel", background=self.color_panel, foreground=self.color_fg, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", background=self.color_bg, foreground=self.color_fg, font=("Segoe UI", 11, "bold"))
        self.style.configure("Status.TLabel", background=self.color_bg, foreground=self.color_fg_sec, font=("Segoe UI", 9, "italic"))
        
        self.style.configure("TButton", background=self.color_panel, foreground=self.color_fg, borderwidth=1, focuscolor=self.color_accent, font=("Segoe UI", 9, "bold"), padding=[12, 4])
        self.style.map("TButton", 
                       background=[("active", self.color_accent), ("pressed", self.color_accent_active)],
                       foreground=[("active", "#ffffff")])
        
        self.style.configure("Accent.TButton", background=self.color_accent, foreground=self.color_fg, borderwidth=1, font=("Segoe UI", 9, "bold"), padding=[12, 4])
        self.style.map("Accent.TButton", 
                       background=[("active", "#818cf8"), ("pressed", self.color_accent_active)],
                       foreground=[("active", "#ffffff")])
                       
        self.style.configure("Stop.TButton", background=self.color_stop, foreground=self.color_fg, borderwidth=1, font=("Segoe UI", 9, "bold"), padding=[12, 4])
        self.style.map("Stop.TButton", 
                       background=[("active", "#f87171"), ("pressed", self.color_stop_active)],
                       foreground=[("active", "#ffffff")])

        self.style.configure("TEntry", fieldbackground=self.color_panel, foreground=self.color_fg, bordercolor=self.color_border, insertcolor=self.color_fg, padding=5)
        
        self.style.configure("Treeview", 
                              background=self.color_panel, 
                              foreground=self.color_fg, 
                              fieldbackground=self.color_panel, 
                              rowheight=28,
                              font=("Segoe UI", 9),
                              borderwidth=0)
        self.style.map("Treeview", 
                       background=[("selected", self.color_accent)], 
                       foreground=[("selected", "#ffffff")])
                       
        self.style.configure("Treeview.Heading", 
                              background=self.color_border, 
                              foreground=self.color_fg, 
                              font=("Segoe UI", 9, "bold"),
                              borderwidth=0,
                              padding=[0, 6])
        self.style.map("Treeview.Heading", 
                       background=[("active", self.color_accent)])

        self.style.configure("TNotebook", background=self.color_bg, borderwidth=0)
        self.style.configure("TNotebook.Tab", 
                              background=self.color_panel, 
                              foreground=self.color_fg_sec, 
                              font=("Segoe UI", 9, "bold"), 
                              padding=[14, 6])
        self.style.map("TNotebook.Tab", 
                       background=[("selected", self.color_bg), ("active", self.color_border)],
                       foreground=[("selected", self.color_fg), ("active", self.color_fg)])

    def crear_widgets(self):
        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(1, weight=2)
        self.root.rowconfigure(0, weight=1)

        # -------------------------------------------------------------
        # PANEL IZQUIERDO
        # -------------------------------------------------------------
        left_panel = ttk.Frame(self.root, style="TFrame", padding=10)
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)
        
        # Subpanel de Control (Modo, Navegador, URL y Botones)
        control_frame = ttk.Frame(left_panel, style="TFrame")
        control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        control_frame.columnconfigure(5, weight=1)
        
        # Fila 0: Configuración
        lbl_modo = ttk.Label(control_frame, text="Modo:", style="TLabel")
        lbl_modo.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")
        
        self.combo_modo = ttk.Combobox(control_frame, values=["APIs de Red (HTTP)", "Grabador DOM (Acciones)", "Scraper Visual (DOM)"], state="readonly", width=22, font=("Segoe UI", 9))
        self.combo_modo.set("APIs de Red (HTTP)")
        self.combo_modo.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.combo_modo.bind("<<ComboboxSelected>>", self.on_cambio_modo)
        
        lbl_browser = ttk.Label(control_frame, text="Navegador:", style="TLabel")
        lbl_browser.grid(row=0, column=2, padx=(10, 5), pady=2, sticky="w")
        
        self.combo_navegador = ttk.Combobox(control_frame, values=["Chromium", "Firefox", "WebKit"], state="readonly", width=10, font=("Segoe UI", 9))
        self.combo_navegador.set("Chromium")
        self.combo_navegador.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        
        lbl_url = ttk.Label(control_frame, text="URL Objetivo:", style="TLabel")
        lbl_url.grid(row=0, column=4, padx=(10, 5), pady=2, sticky="w")
        
        self.entry_url = ttk.Entry(control_frame, font=("Segoe UI", 10))
        self.entry_url.grid(row=0, column=5, padx=5, pady=2, sticky="ew")
        
        # Fila 1: Botones de control
        buttons_subframe = ttk.Frame(control_frame, style="TFrame")
        buttons_subframe.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(5, 0))
        
        self.btn_start = ttk.Button(buttons_subframe, text="⚡ Iniciar Captura", style="Accent.TButton", command=self.iniciar_captura)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 5))
        
        self.btn_pause = ttk.Button(buttons_subframe, text="⏸️ Pausar", command=self.toggle_pause)
        self.btn_pause.pack(side=tk.LEFT, padx=5)
        self.btn_pause.state(["disabled"])
        
        self.btn_stop = ttk.Button(buttons_subframe, text="🛑 Detener Captura", style="Stop.TButton", command=self.detener_captura)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        self.btn_stop.state(["disabled"])
        
        self.btn_config = ttk.Button(buttons_subframe, text="⚙️ Configuración", command=self.abrir_configuracion)
        self.btn_config.pack(side=tk.RIGHT, padx=(5, 0))

        # Subpanel de la Tabla
        table_frame = ttk.Frame(left_panel, style="TFrame")
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(1, weight=1)

        sel_control_frame = ttk.Frame(table_frame, style="TFrame")
        sel_control_frame.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        
        btn_sel_all = ttk.Button(sel_control_frame, text="☑ Marcar Todos", width=16, command=self.seleccionar_todos)
        btn_sel_all.grid(row=0, column=0, padx=(0, 5))
        
        btn_desel_all = ttk.Button(sel_control_frame, text="☐ Desmarcar Todos", width=18, command=self.deseleccionar_todos)
        btn_desel_all.grid(row=0, column=1, padx=5)

        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical")
        scrollbar_y.grid(row=1, column=1, sticky="ns")
        
        scrollbar_x = ttk.Scrollbar(table_frame, orient="horizontal")
        scrollbar_x.grid(row=2, column=0, sticky="ew")

        self.tabla = ttk.Treeview(
            table_frame, 
            columns=("sel", "idx", "metodo", "status", "url"), 
            show="headings", 
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set,
            selectmode="browse"
        )
        self.tabla.grid(row=1, column=0, sticky="nsew")
        scrollbar_y.config(command=self.tabla.yview)
        scrollbar_x.config(command=self.tabla.xview)
        
        self.tabla.heading("sel", text="Sel")
        self.tabla.heading("idx", text="#")
        self.tabla.heading("metodo", text="Método")
        self.tabla.heading("status", text="Status")
        self.tabla.heading("url", text="URL")
        
        self.tabla.column("sel", width=45, anchor="center", stretch=False)
        self.tabla.column("idx", width=40, anchor="center", stretch=False)
        self.tabla.column("metodo", width=80, anchor="center", stretch=False)
        self.tabla.column("status", width=60, anchor="center", stretch=False)
        self.tabla.column("url", width=400, anchor="w")
        
        self.tabla.bind("<<TreeviewSelect>>", self.on_peticion_seleccionada)
        self.tabla.bind("<Double-1>", self.on_tabla_double_click)
        self.tabla.bind("<space>", self.on_tabla_space)
        self.tabla.bind("<Button-3>", self.mostrar_menu_contextual) # Clic derecho

        self.tabla.tag_configure("par", background=self.color_panel)
        self.tabla.tag_configure("impar", background=self.color_bg)

        # Subpanel de Acciones e Información Inferior
        bottom_frame = ttk.Frame(left_panel, style="TFrame")
        bottom_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        bottom_frame.columnconfigure(2, weight=1)
        
        self.btn_generar = ttk.Button(
            bottom_frame, 
            text="⚙️ Generar Flujo Unificado", 
            style="Accent.TButton", 
            command=self.generar_codigo_flujo
        )
        self.btn_generar.grid(row=0, column=0, padx=(0, 10), sticky="w")
        
        self.var_parametrizar = tk.BooleanVar(value=True)
        self.chk_parametrizar = ttk.Checkbutton(
            bottom_frame,
            text="🔒 Parametrizar Secretos",
            variable=self.var_parametrizar
        )
        self.chk_parametrizar.grid(row=0, column=1, padx=5, sticky="w")
        
        self.lbl_status = ttk.Label(
            bottom_frame, 
            text="Listo. Ingrese la URL y pulse 'Iniciar Captura'.", 
            style="Status.TLabel"
        )
        self.lbl_status.grid(row=0, column=2, padx=(10, 0), sticky="w")

        # -------------------------------------------------------------
        # PANEL DERECHO
        # -------------------------------------------------------------
        right_panel = ttk.Frame(self.root, style="Panel.TFrame", padding=10)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        media_frame = ttk.Frame(right_panel, style="Panel.TFrame")
        media_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        media_frame.columnconfigure(0, weight=1)
        media_frame.columnconfigure(1, weight=1)

        self.btn_video = ttk.Button(media_frame, text="🎬 Reproducir Video", command=self.reproducir_video)
        self.btn_video.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        
        self.btn_trace = ttk.Button(media_frame, text="🔍 Ver Trace de Playwright", command=self.abrir_trace)
        self.btn_trace.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.notebook = ttk.Notebook(right_panel)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        self.txt_headers = scrolledtext.ScrolledText(
            self.notebook, 
            bg=self.color_bg, 
            fg=self.color_fg, 
            insertbackground=self.color_accent, 
            font=("Consolas", 10),
            state=tk.DISABLED
        )
        self.notebook.add(self.txt_headers, text="Headers")

        self.txt_payload = scrolledtext.ScrolledText(
            self.notebook, 
            bg=self.color_bg, 
            fg=self.color_fg, 
            insertbackground=self.color_accent, 
            font=("Consolas", 10),
            state=tk.DISABLED
        )
        self.notebook.add(self.txt_payload, text="Payload (Request)")

        self.txt_response = scrolledtext.ScrolledText(
            self.notebook, 
            bg=self.color_bg, 
            fg=self.color_fg, 
            insertbackground=self.color_accent, 
            font=("Consolas", 10),
            state=tk.DISABLED
        )
        self.notebook.add(self.txt_response, text="Respuesta")

        # --- Pestaña: Árbol JSON (Opción B) --- visible en modo APIs ---
        self.frame_arbol_json = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.frame_arbol_json, text="🌳 Árbol JSON")
        self.frame_arbol_json.columnconfigure(0, weight=1)
        self.frame_arbol_json.rowconfigure(0, weight=1)

        # -------------------------------------------------------
        # Pestaña: Red POST (visible solo en modo Scraper)
        # -------------------------------------------------------
        self.frame_red_scraper = ttk.Frame(self.notebook, style="Panel.TFrame", padding=6)
        self.notebook.add(self.frame_red_scraper, text="🌐 Red POST")
        self.peticiones_red_post = []  # lista de requests POST capturados

        # Treeview de requests POST
        red_cols = ("metodo", "status", "url_corta")
        self.tabla_red_post = ttk.Treeview(self.frame_red_scraper, columns=red_cols,
                                           show="headings", height=6)
        self.tabla_red_post.heading("metodo", text="Método")
        self.tabla_red_post.heading("status", text="Status")
        self.tabla_red_post.heading("url_corta", text="URL")
        self.tabla_red_post.column("metodo", width=55, anchor="center", stretch=False)
        self.tabla_red_post.column("status", width=50, anchor="center", stretch=False)
        self.tabla_red_post.column("url_corta", width=280, anchor="w")
        scr_red = ttk.Scrollbar(self.frame_red_scraper, orient="vertical",
                                 command=self.tabla_red_post.yview)
        self.tabla_red_post.configure(yscrollcommand=scr_red.set)
        self.tabla_red_post.grid(row=0, column=0, sticky="nsew")
        scr_red.grid(row=0, column=1, sticky="ns")
        self.tabla_red_post.bind("<<TreeviewSelect>>", self.on_post_seleccionado)

        # Panel de detalle del request POST
        det_frame = ttk.LabelFrame(self.frame_red_scraper, text="Detalle del Request", padding=6)
        det_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 0))

        self.txt_red_detalle = scrolledtext.ScrolledText(
            det_frame, height=7, wrap=tk.WORD,
            font=("Consolas", 8), state=tk.DISABLED)
        self.txt_red_detalle.pack(fill="both", expand=True)

        btn_auto_login = ttk.Button(
            det_frame, text="🚀 Autocompletar Login BS4",
            style="Accent.TButton",
            command=self.autodetectar_login_bs4)
        btn_auto_login.pack(pady=(4, 0))

        self.frame_red_scraper.columnconfigure(0, weight=1)
        self.frame_red_scraper.rowconfigure(0, weight=1)
        self.frame_red_scraper.rowconfigure(1, weight=1)

        self.style.configure("ArbolJSON.Treeview",
                              background=self.color_panel,
                              foreground=self.color_fg,
                              fieldbackground=self.color_panel,
                              rowheight=22,
                              font=("Consolas", 9),
                              borderwidth=0)
        self.style.map("ArbolJSON.Treeview",
                       background=[("selected", self.color_accent)],
                       foreground=[("selected", "#ffffff")])

        arbol_scroll_y = ttk.Scrollbar(self.frame_arbol_json, orient="vertical")
        arbol_scroll_x = ttk.Scrollbar(self.frame_arbol_json, orient="horizontal")
        arbol_scroll_y.grid(row=0, column=1, sticky="ns")
        arbol_scroll_x.grid(row=1, column=0, sticky="ew")

        self.arbol_json = ttk.Treeview(
            self.frame_arbol_json,
            columns=("clave", "tipo", "valor"),
            show="tree headings",
            yscrollcommand=arbol_scroll_y.set,
            xscrollcommand=arbol_scroll_x.set,
            style="ArbolJSON.Treeview"
        )
        self.arbol_json.grid(row=0, column=0, sticky="nsew")
        arbol_scroll_y.config(command=self.arbol_json.yview)
        arbol_scroll_x.config(command=self.arbol_json.xview)

        self.arbol_json.heading("#0", text="Ruta")
        self.arbol_json.heading("clave", text="Clave")
        self.arbol_json.heading("tipo", text="Tipo")
        self.arbol_json.heading("valor", text="Valor")
        self.arbol_json.column("#0", width=160, stretch=True)
        self.arbol_json.column("clave", width=130, stretch=False)
        self.arbol_json.column("tipo", width=70, anchor="center", stretch=False)
        self.arbol_json.column("valor", width=280, stretch=True)

        # --- Pestaña: Config Scraper --- visible en modo Scraper ---
        self.frame_config_scraper = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.frame_config_scraper, text="⚙️ Config Scraper")
        self.frame_config_scraper.rowconfigure(0, weight=1)
        self.frame_config_scraper.columnconfigure(0, weight=1)

        # Canvas + Scrollbar para hacer el panel scrollable
        _cs_canvas = tk.Canvas(self.frame_config_scraper, highlightthickness=0,
                               bg=self.color_panel)
        _cs_scroll = ttk.Scrollbar(self.frame_config_scraper, orient="vertical",
                                   command=_cs_canvas.yview)
        _cs_canvas.configure(yscrollcommand=_cs_scroll.set)
        _cs_canvas.grid(row=0, column=0, sticky="nsew")
        _cs_scroll.grid(row=0, column=1, sticky="ns")

        # Frame interior que contiene todos los widgets
        _cs_inner = ttk.Frame(_cs_canvas, style="Panel.TFrame", padding=12)
        _cs_window = _cs_canvas.create_window((0, 0), window=_cs_inner, anchor="nw")

        def _on_cs_inner_configure(event):
            _cs_canvas.configure(scrollregion=_cs_canvas.bbox("all"))
        _cs_inner.bind("<Configure>", _on_cs_inner_configure)

        def _on_cs_canvas_configure(event):
            _cs_canvas.itemconfig(_cs_window, width=event.width)
        _cs_canvas.bind("<Configure>", _on_cs_canvas_configure)

        # Scroll con rueda del mouse cuando el cursor está sobre el panel
        def _on_cs_mousewheel(event):
            _cs_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        _cs_inner.bind_all_children = lambda: None  # no-op placeholder
        _cs_canvas.bind("<Enter>", lambda e: _cs_canvas.bind_all("<MouseWheel>", _on_cs_mousewheel))
        _cs_canvas.bind("<Leave>", lambda e: _cs_canvas.unbind_all("<MouseWheel>"))

        # Referencia al frame interior para usarlo en _on_motor_cambiado
        self._cs_inner = _cs_inner

        ttk.Label(_cs_inner, text="🕷️ CONFIGURACIÓN DEL SCRAPER",
                  style="Header.TLabel").pack(anchor="w", pady=(0, 8))

        # -- Paginación --
        pag_frame = ttk.LabelFrame(_cs_inner, text="Paginación", padding=8)
        pag_frame.pack(fill="x", pady=4)
        pag_frame.columnconfigure(1, weight=1)

        ttk.Label(pag_frame, text="Selector 'Siguiente Página':", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.scraper_selector_paginacion = tk.StringVar(value="")
        ttk.Entry(pag_frame, textvariable=self.scraper_selector_paginacion,
                  font=("Segoe UI", 9)).grid(row=0, column=1, sticky="ew", pady=3)

        ttk.Label(pag_frame, text="Máx. páginas (0=sin límite):", style="Panel.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        self.scraper_max_paginas = tk.IntVar(value=0)
        ttk.Entry(pag_frame, textvariable=self.scraper_max_paginas,
                  width=8, font=("Segoe UI", 9)).grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(pag_frame, text="Delay entre páginas (seg):", style="Panel.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        self.scraper_delay = tk.DoubleVar(value=1.5)
        ttk.Entry(pag_frame, textvariable=self.scraper_delay,
                  width=8, font=("Segoe UI", 9)).grid(row=2, column=1, sticky="w", pady=3)

        # -- Formato de salida --
        fmt_frame = ttk.LabelFrame(_cs_inner, text="Formatos de Exportación", padding=8)
        fmt_frame.pack(fill="x", pady=4)
        self.scraper_fmt_csv = tk.BooleanVar(value=True)
        self.scraper_fmt_json = tk.BooleanVar(value=True)
        self.scraper_headless = tk.BooleanVar(value=True)
        ttk.Checkbutton(fmt_frame, text="Exportar CSV",
                        variable=self.scraper_fmt_csv).pack(anchor="w", pady=2)
        ttk.Checkbutton(fmt_frame, text="Exportar JSON",
                        variable=self.scraper_fmt_json).pack(anchor="w", pady=2)
        ttk.Checkbutton(fmt_frame, text="Ejecutar en modo Headless (sin ventana)",
                        variable=self.scraper_headless).pack(anchor="w", pady=2)

        # -- Ayuda --
        ayuda_frame = ttk.LabelFrame(_cs_inner, text="Instrucciones de Uso", padding=8)
        ayuda_frame.pack(fill="x", pady=4)
        ayuda_texto = (
            "1. Ingresa la URL y presiona '⚡ Iniciar Captura'.\n"
            "2. En el navegador, los CLICKS, FILLS y NAVEGACIONES\n"
            "   se graban como pasos de '🔧 Setup' (login, menus).\n"
            "3. Usa Shift+Clic en elementos para marcarlos como\n"
            "   '📤 Extraer' (campos de datos).\n"
            "4. (Opcional) Configura paginación y motor abajo.\n"
            "5. Presiona '⬇️ Generar Script de Scraping'."
        )
        ttk.Label(ayuda_frame, text=ayuda_texto, style="Panel.TLabel",
                  justify="left", wraplength=260).pack(anchor="w")

        # -- Motor de Extracción --
        motor_frame = ttk.LabelFrame(_cs_inner, text="Motor de Extracción", padding=8)
        motor_frame.pack(fill="x", pady=(4, 2))

        self.scraper_motor = tk.StringVar(value="playwright")

        self.radio_playwright = ttk.Radiobutton(
            motor_frame, text="🎭 Playwright  (JS / Login / Dinámico)",
            variable=self.scraper_motor, value="playwright")
        self.radio_playwright.pack(anchor="w", pady=(3, 1))
        self.radio_playwright.config(command=lambda: self._on_motor_cambiado())

        self.radio_bs4 = ttk.Radiobutton(
            motor_frame, text="🌿 requests + BS4  (Estático / API)",
            variable=self.scraper_motor, value="bs4")
        self.radio_bs4.pack(anchor="w", pady=(1, 3))
        self.radio_bs4.config(command=lambda: self._on_motor_cambiado())

        self.lbl_motor_aviso = ttk.Label(
            motor_frame,
            text="⚠️ BS4 con pasos de Setup: asegurate de desmarcalos o configurar el login BS4.")
        # No hacemos pack aqui; se muestra/oculta desde _on_motor_cambiado

        # -- Login BS4 (opcional) --
        self.frame_bs4_login = ttk.LabelFrame(
            _cs_inner, text="Login BS4 (opcional)", padding=8)
        # Se muestra solo cuando el motor es BS4

        ttk.Label(self.frame_bs4_login,
                  text="URL de Login (POST):").grid(row=0, column=0, sticky="w", pady=2, padx=4)
        self.bs4_login_url = tk.StringVar()
        ttk.Entry(self.frame_bs4_login, textvariable=self.bs4_login_url,
                  width=28).grid(row=0, column=1, sticky="ew", pady=2, padx=4)

        ttk.Label(self.frame_bs4_login,
                  text="Usuario / clave campo:").grid(row=1, column=0, sticky="w", pady=2, padx=4)
        self.bs4_login_user_field = tk.StringVar(value="username")
        ttk.Entry(self.frame_bs4_login, textvariable=self.bs4_login_user_field,
                  width=28).grid(row=1, column=1, sticky="ew", pady=2, padx=4)

        ttk.Label(self.frame_bs4_login,
                  text="Pass campo:").grid(row=2, column=0, sticky="w", pady=2, padx=4)
        self.bs4_login_pass_field = tk.StringVar(value="password")
        ttk.Entry(self.frame_bs4_login, textvariable=self.bs4_login_pass_field,
                  width=28).grid(row=2, column=1, sticky="ew", pady=2, padx=4)

        ttk.Label(self.frame_bs4_login,
                  text="Tipo de Auth:").grid(row=3, column=0, sticky="w", pady=2, padx=4)
        self.bs4_auth_tipo = tk.StringVar(value="form_post")
        combo_auth = ttk.Combobox(
            self.frame_bs4_login, textvariable=self.bs4_auth_tipo,
            values=["form_post", "json_post", "bearer_token", "basic_auth"],
            state="readonly", width=26)
        combo_auth.grid(row=3, column=1, sticky="ew", pady=2, padx=4)

        ttk.Label(self.frame_bs4_login,
                  text="Campo token JSON:").grid(row=4, column=0, sticky="w", pady=2, padx=4)
        self.bs4_token_field = tk.StringVar(value="token")
        ttk.Entry(self.frame_bs4_login, textvariable=self.bs4_token_field,
                  width=28).grid(row=4, column=1, sticky="ew", pady=2, padx=4)

        self.frame_bs4_login.columnconfigure(1, weight=1)

        # Ocultar tabs de scraper y árbol al inicio (modo por defecto = APIs)
        self.notebook.hide(self.frame_arbol_json)
        self.notebook.hide(self.frame_config_scraper)
        self.notebook.hide(self.frame_red_scraper)



    def on_cambio_modo(self, event=None):
        modo = self.combo_modo.get()
        if "APIs" in modo:
            self.tabla["columns"] = ("sel", "idx", "metodo", "status", "url")
            self.tabla.heading("sel", text="Sel")
            self.tabla.heading("idx", text="#")
            self.tabla.heading("metodo", text="Método")
            self.tabla.heading("status", text="Status")
            self.tabla.heading("url", text="URL")

            self.tabla.column("sel", width=45, anchor="center", stretch=False)
            self.tabla.column("idx", width=40, anchor="center", stretch=False)
            self.tabla.column("metodo", width=80, anchor="center", stretch=False)
            self.tabla.column("status", width=60, anchor="center", stretch=False)
            self.tabla.column("url", width=400, anchor="w")

            self.notebook.tab(0, text="Headers")
            self.notebook.tab(1, text="Payload (Request)")
            self.notebook.tab(2, text="Respuesta")
            # Mostrar árbol JSON, ocultar config scraper
            try:
                self.notebook.add(self.frame_arbol_json)
                self.notebook.tab(self.frame_arbol_json, text="🌳 Árbol JSON")
            except Exception:
                pass
            try:
                self.notebook.hide(self.frame_config_scraper)
            except Exception:
                pass
            try:
                self.notebook.hide(self.frame_red_scraper)
            except Exception:
                pass

            self.btn_generar.config(text="⚙️ Generar Flujo Unificado")

        elif "Grabador" in modo:
            self.tabla["columns"] = ("sel", "idx", "accion", "elemento", "valor")
            self.tabla.heading("sel", text="Sel")
            self.tabla.heading("idx", text="#")
            self.tabla.heading("accion", text="Acción")
            self.tabla.heading("elemento", text="Elemento")
            self.tabla.heading("valor", text="Texto / Valor")

            self.tabla.column("sel", width=45, anchor="center", stretch=False)
            self.tabla.column("idx", width=40, anchor="center", stretch=False)
            self.tabla.column("accion", width=100, anchor="center", stretch=False)
            self.tabla.column("elemento", width=250, anchor="w")
            self.tabla.column("valor", width=350, anchor="w")

            self.notebook.tab(0, text="Atributos")
            self.notebook.tab(1, text="Selectores")
            self.notebook.tab(2, text="HTML Externo")
            # Ocultar árbol JSON y config scraper
            try:
                self.notebook.hide(self.frame_arbol_json)
            except Exception:
                pass
            try:
                self.notebook.hide(self.frame_config_scraper)
            except Exception:
                pass
            try:
                self.notebook.hide(self.frame_red_scraper)
            except Exception:
                pass

            self.btn_generar.config(text="⚙️ Generar Automatización (Playwright)")

        else:  # "Scraper Visual (DOM)"
            # 6 columnas: sel, idx, FASE, nombre_accion, selector, valor_preview
            self.tabla["columns"] = ("sel", "idx", "fase", "nombre_accion", "selector", "valor_preview")
            self.tabla.heading("sel", text="Sel")
            self.tabla.heading("idx", text="#")
            self.tabla.heading("fase", text="Fase")
            self.tabla.heading("nombre_accion", text="Campo / Acción")
            self.tabla.heading("selector", text="Selector")
            self.tabla.heading("valor_preview", text="Vista Previa")

            self.tabla.column("sel", width=40, anchor="center", stretch=False)
            self.tabla.column("idx", width=35, anchor="center", stretch=False)
            self.tabla.column("fase", width=85, anchor="center", stretch=False)
            self.tabla.column("nombre_accion", width=150, anchor="w")
            self.tabla.column("selector", width=180, anchor="w")
            self.tabla.column("valor_preview", width=270, anchor="w")

            self.notebook.tab(0, text="Atributos")
            self.notebook.tab(1, text="Selectores")
            self.notebook.tab(2, text="HTML Externo")
            # Mostrar config scraper, ocultar árbol JSON
            try:
                self.notebook.hide(self.frame_arbol_json)
            except Exception:
                pass
            try:
                self.notebook.add(self.frame_config_scraper)
                self.notebook.tab(self.frame_config_scraper, text="⚙️ Config Scraper")
                # Mostrar tab de Red POST para el scraper
                try:
                    self.notebook.add(self.frame_red_scraper)
                    self.notebook.tab(self.frame_red_scraper, text="🌐 Red POST")
                except Exception:
                    pass
                self.notebook.select(self.frame_config_scraper)
            except Exception:
                pass

            self.btn_generar.config(text="⬇️ Generar Script de Scraping")

        self.peticiones_capturadas.clear()
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        self.limpiar_detalles()

    # -------------------------------------------------------------
    # CONTROL DE CAPTURA
    # -------------------------------------------------------------
    def iniciar_captura(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showerror("Error", "Debe ingresar una URL válida.")
            return

        self.peticiones_capturadas.clear()
        for item in self.tabla.get_children():
            self.tabla.delete(item)

        self.btn_start.state(["disabled"])
        self.entry_url.state(["disabled"])
        self.combo_modo.state(["disabled"])
        self.combo_navegador.state(["disabled"])
        self.btn_pause.state(["!disabled"])
        self.btn_pause.config(text="⏸️ Pausar")
        self.btn_stop.state(["!disabled"])

        # Definir dinámicamente las rutas de guardado de los outputs
        base_dir = self.config_output_dir.get().strip()
        if not base_dir:
            base_dir = self.output_base_dir
        self.video_dir = os.path.join(base_dir, "output_videos")
        self.trace_file = os.path.join(base_dir, "trace.zip")
        self.log_file = os.path.join(base_dir, "debug_playwright.log")

        self.capture_thread = PlaywrightCaptureThread(
            url=url, 
            output_queue=self.queue,
            video_dir=self.video_dir,
            trace_file=self.trace_file,
            log_file=self.log_file,
            modo=self.combo_modo.get(),
            navegador=self.combo_navegador.get(),
            viewport_width=self.config_width.get(),
            viewport_height=self.config_height.get(),
            ignore_ssl_errors=self.config_ignore_ssl.get(),
            headless=self.config_headless.get(),
            record_video=self.config_record_video.get(),
            record_trace=self.config_record_trace.get(),
            timeout=self.config_timeout.get(),
            user_agent=self.config_user_agent.get()
        )
        self.capture_thread.start()

    def toggle_pause(self):
        if self.capture_thread and self.capture_thread.is_alive():
            nuevo_estado = not self.capture_thread.paused
            self.capture_thread.paused = nuevo_estado
            if nuevo_estado:
                self.btn_pause.config(text="▶️ Reanudar")
                self.lbl_status.config(text="Captura PAUSADA.")
                self.capture_thread.input_queue.put(("pause", True))
            else:
                self.btn_pause.config(text="⏸️ Pausar")
                self.lbl_status.config(text="Captura activa. Interactúe en el navegador...")
                self.capture_thread.input_queue.put(("pause", False))

    def detener_captura(self):
        if self.capture_thread and self.capture_thread.is_alive():
            self.lbl_status.config(text="Deteniendo captura...")
            self.capture_thread.stop()
            self.btn_stop.state(["disabled"])
            self.btn_pause.state(["disabled"])

    # -------------------------------------------------------------
    # INSTALACIÓN AUTOMÁTICA DE NAVEGADORES DE PLAYWRIGHT
    # -------------------------------------------------------------
    def descargar_e_instalar_navegadores(self, navegador="Chromium"):
        """Descarga e instala el navegador de Playwright faltante con una ventana de progreso interactiva."""
        # Mapa de nombre de la UI al identificador de Playwright CLI
        mapa_navegador = {
            "Chromium": "chromium",
            "Firefox": "firefox",
            "WebKit": "webkit",
        }
        nav_id = mapa_navegador.get(navegador, "chromium")

        # --- Ventana modal de progreso ---
        install_win = tk.Toplevel(self.root)
        install_win.title("Instalando Navegador...")
        install_win.geometry("500x230")
        install_win.resizable(False, False)
        install_win.configure(bg=self.color_bg)
        install_win.transient(self.root)
        install_win.grab_set()
        install_win.protocol("WM_DELETE_WINDOW", lambda: None)  # Bloquear cierre manual

        # Centrar ventana
        install_win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 230) // 2
        install_win.geometry(f"+{x}+{y}")

        lbl_titulo = tk.Label(
            install_win,
            text=f"Instalando {navegador} para Playwright...",
            fg=self.color_fg, bg=self.color_bg,
            font=("Segoe UI", 11, "bold")
        )
        lbl_titulo.pack(pady=(18, 6), padx=20, anchor="w")

        lbl_estado = tk.Label(
            install_win,
            text="Iniciando descarga, por favor espere...",
            fg=self.color_fg_sec, bg=self.color_bg,
            font=("Segoe UI", 9), wraplength=460, justify="left"
        )
        lbl_estado.pack(pady=(0, 10), padx=20, anchor="w")

        # Barra de progreso indeterminada (animada)
        style_local = ttk.Style()
        style_local.configure(
            "Install.Horizontal.TProgressbar",
            troughcolor="#1e293b", background="#06b6d4",
            thickness=12, borderwidth=0
        )
        progress_bar = ttk.Progressbar(
            install_win, style="Install.Horizontal.TProgressbar",
            orient="horizontal", length=460, mode="indeterminate"
        )
        progress_bar.pack(pady=6, padx=20)
        progress_bar.start(15)

        lbl_aviso = tk.Label(
            install_win,
            text="⚠️  No cierre la aplicación durante la instalación.",
            fg="#f59e0b", bg=self.color_bg,
            font=("Segoe UI", 8, "italic")
        )
        lbl_aviso.pack(pady=(10, 0))

        log_lines = []

        def actualizar_estado(texto):
            """Actualiza el label de estado desde el hilo secundario vía after."""
            install_win.after(0, lambda t=texto: lbl_estado.config(text=t))

        def hilo_instalacion():
            exito = False
            msg_final = ""
            try:
                from playwright._impl._driver import compute_driver_executable
                driver_exec = compute_driver_executable()

                if isinstance(driver_exec, (list, tuple)):
                    cmd = list(driver_exec) + ["install", nav_id, "ffmpeg"]
                else:
                    cmd = [driver_exec, "install", nav_id, "ffmpeg"]

                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NO_WINDOW

                proceso = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=creation_flags
                )

                for linea in iter(proceso.stdout.readline, ""):
                    linea = linea.strip()
                    if linea:
                        log_lines.append(linea)
                        # Mostrar solo líneas relevantes de progreso
                        if any(k in linea.lower() for k in ["downloading", "extracting", "installing", "descargando", "chromium", "firefox", "webkit", "ffmpeg", "done", "browser", "mb"]):
                            actualizar_estado(linea[:120])

                proceso.wait()
                if proceso.returncode == 0:
                    exito = True
                    msg_final = (
                        f"{navegador} y ffmpeg instalados correctamente.\n"
                        "Ya puede iniciar la captura nuevamente."
                    )
                else:
                    msg_final = (
                        f"La instalación terminó con código de error {proceso.returncode}.\n"
                        f"Detalle:\n" + "\n".join(log_lines[-8:])
                    )
            except Exception as e:
                msg_final = (
                    f"Error al ejecutar la instalación automática:\n{e}\n\n"
                    "Puedes instalarlo manualmente desde PowerShell ejecutando:\n"
                    f"  playwright install {nav_id} ffmpeg"
                )

            # Finalizar en el hilo de la UI
            install_win.after(0, lambda: finalizar(exito, msg_final))

        def finalizar(exito, mensaje):
            try:
                progress_bar.stop()
                install_win.grab_release()
                install_win.destroy()
            except Exception:
                pass

            if exito:
                messagebox.showinfo(
                    "✅ Instalación Completada",
                    mensaje
                )
                self.lbl_status.config(text=f"{navegador} instalado. Puede iniciar la captura nuevamente.")
            else:
                messagebox.showerror(
                    "Error en la Instalación",
                    mensaje
                )
                self.lbl_status.config(text="Instalación fallida. Revise el error.")

        threading.Thread(target=hilo_instalacion, daemon=True).start()

    # -------------------------------------------------------------
    # MANEJO DE COLA DE EVENTOS
    # -------------------------------------------------------------
    def procesar_cola(self):
        try:
            while not self.queue.empty():
                try:
                    tipo, dato = self.queue.get_nowait()
                except queue.Empty:
                    break
                except Exception as get_err:
                    try:
                        with open(self.log_file, "a", encoding="utf-8") as f:
                            f.write(f"GUI Error get_nowait: {get_err}\n")
                    except Exception:
                        pass
                    break
                
                try:
                    with open(self.log_file, "a", encoding="utf-8") as f:
                        f.write(f"GUI procesando cola: Tipo={tipo}\n")
                except Exception:
                    pass
                
                try:
                    if tipo == "status":
                        self.lbl_status.config(text=dato)
                    elif tipo == "error":
                        # Detectar si el error es por falta de navegador de Playwright
                        es_error_navegador = (
                            "Executable doesn't exist" in dato
                            or "playwright install" in dato.lower()
                            or "executable doesn't exist" in dato.lower()
                        )
                        if es_error_navegador:
                            navegador = self.combo_navegador.get() if hasattr(self, "combo_navegador") else "Chromium"
                            resp = messagebox.askyesno(
                                "Navegador de Playwright no instalado",
                                f"El navegador '{navegador}' de Playwright no está instalado en este equipo.\n\n"
                                f"Error: {dato[:300]}\n\n"
                                "¿Desea descargar e instalar automáticamente el navegador ahora?\n"
                                "(Puede requerir conexión a internet y algunos minutos.)"
                            )
                            if resp:
                                self.descargar_e_instalar_navegadores(navegador)
                        else:
                            messagebox.showerror("Error en Captura", dato)
                    elif tipo == "peticion":
                        self.peticiones_capturadas.append(dato)
                        idx = len(self.peticiones_capturadas) - 1
                        val_check = "☑" if dato.get("seleccionado", True) else "☐"
                        url_corta = dato["url"]
                        if len(url_corta) > 120:
                            url_corta = url_corta[:117] + "..."
                        self.tabla.insert(
                            "", 
                            "end", 
                            iid=str(idx), 
                            values=(val_check, idx, dato["metodo"], dato["status"], url_corta),
                            tags=("par" if idx % 2 == 0 else "impar",)
                        )
                    elif tipo == "post_red_scraper":
                        # Request POST/PUT capturado en modo Scraper — mostrar en tab Red POST
                        self.peticiones_red_post.append(dato)
                        idx_r = len(self.peticiones_red_post) - 1
                        url_corta = dato.get("url", "")
                        if len(url_corta) > 80:
                            url_corta = "..." + url_corta[-77:]
                        metodo  = dato.get("metodo", "POST")
                        status  = dato.get("status", "")
                        tag_red = "ok_red" if str(status).startswith("2") else "err_red"
                        self.tabla_red_post.insert(
                            "", "end", iid=str(idx_r),
                            values=(metodo, status, url_corta),
                            tags=(tag_red,)
                        )
                        # Auto-seleccionar la última entrada para mostrar el detalle
                        self.tabla_red_post.selection_set(str(idx_r))
                        self.tabla_red_post.see(str(idx_r))
                        self.on_post_seleccionado()
                    elif tipo == "accion_dom":

                        modo_actual = self.combo_modo.get()

                        if "Scraper" in modo_actual:
                            # MODO SCRAPER: capturar TODOS los eventos
                            # extract → campo de extracción (Shift+Clic)
                            # click/fill/navigation/select → paso de Setup
                            tipo_accion = dato.get("tipo_accion", "")
                            fase = dato.get("fase_scraper", "setup" if tipo_accion != "extract" else "extract")

                            if tipo_accion == "extract":
                                # ─── CAMPO DE EXTRACCIÓN ───
                                nombre_auto = generar_nombre_campo_auto(dato) if generar_nombre_campo_auto else "campo"
                                nombres_existentes = [p.get("nombre_campo", "") for p in self.peticiones_capturadas]
                                nombre_final = nombre_auto
                                sufijo = 2
                                while nombre_final in nombres_existentes:
                                    nombre_final = f"{nombre_auto}_{sufijo}"
                                    sufijo += 1
                                dato["nombre_campo"] = nombre_final
                                dato["fase_scraper"] = "extract"
                                self.peticiones_capturadas.append(dato)
                                idx = len(self.peticiones_capturadas) - 1
                                val_check = "☑" if dato.get("seleccionado", True) else "☐"
                                preview = (dato.get("valor") or "")[:50]
                                self.tabla.insert("", "end", iid=str(idx),
                                    values=(val_check, idx, "📤 Extraer", nombre_final,
                                            dato.get("selector_sugerido", ""), preview),
                                    tags=("extract",))

                            else:
                                # ─── PASO DE SETUP ───
                                # Dedup fills: si el mismo selector fue llenado antes, actualizar
                                idx_existente = len(self.peticiones_capturadas) - 1
                                if (tipo_accion == "fill" and
                                        idx_existente >= 0 and
                                        self.peticiones_capturadas[idx_existente].get("tipo_accion") == "fill" and
                                        self.peticiones_capturadas[idx_existente].get("selector_sugerido") == dato.get("selector_sugerido")):
                                    self.peticiones_capturadas[idx_existente]["valor"] = dato["valor"]
                                    self.peticiones_capturadas[idx_existente]["outerHTML"] = dato.get("outerHTML", "")
                                    item_id = str(idx_existente)
                                    if self.tabla.exists(item_id):
                                        vals = list(self.tabla.item(item_id, "values"))
                                        vals[5] = (dato["valor"] or "")[:50]
                                        self.tabla.item(item_id, values=vals)
                                else:
                                    dato["fase_scraper"] = "setup"
                                    self.peticiones_capturadas.append(dato)
                                    idx = len(self.peticiones_capturadas) - 1
                                    tipo_map = {
                                        "click": "Click 🖱️",
                                        "fill": "Escribir ⌨️",
                                        "select": "Seleccionar 📋",
                                        "navigation": "Ir a URL 🌐",
                                    }
                                    accion_legible = tipo_map.get(tipo_accion, tipo_accion.capitalize())
                                    desc = dato.get("descriptor_legible", "") or dato.get("valor", "")[:40]
                                    val_check = "☑" if dato.get("seleccionado", True) else "☐"
                                    self.tabla.insert("", "end", iid=str(idx),
                                        values=(val_check, idx, "🔧 Setup",
                                                f"{accion_legible}: {desc[:35]}",
                                                dato.get("selector_sugerido", ""),
                                                (dato.get("valor") or "")[:50]),
                                        tags=("setup",))

                        else:
                            # MODO GRABADOR DOM (comportamiento original)
                            idx = len(self.peticiones_capturadas) - 1
                            if (idx >= 0 and dato["tipo_accion"] == "fill" and
                                    self.peticiones_capturadas[idx].get("tipo_accion") == "fill" and
                                    self.peticiones_capturadas[idx].get("selector_sugerido") == dato["selector_sugerido"]):

                                self.peticiones_capturadas[idx]["valor"] = dato["valor"]
                                self.peticiones_capturadas[idx]["outerHTML"] = dato["outerHTML"]

                                item_id = str(idx)
                                if self.tabla.exists(item_id):
                                    tipo_map = {
                                        "click": "Click 🖱️",
                                        "fill": "Escribir ⌨️",
                                        "select": "Seleccionar 📋",
                                        "navigation": "Ir a URL 🌐",
                                        "extract": "Extraer Texto 🔍"
                                    }
                                    accion_legible = tipo_map.get(self.peticiones_capturadas[idx]["tipo_accion"], self.peticiones_capturadas[idx]["tipo_accion"].capitalize())
                                    val_check = "☑" if self.peticiones_capturadas[idx].get("seleccionado", True) else "☐"
                                    self.tabla.item(item_id, values=(val_check, idx, accion_legible, dato["descriptor_legible"], dato["valor"]))
                            else:
                                self.peticiones_capturadas.append(dato)
                                idx = len(self.peticiones_capturadas) - 1
                                tipo_map = {
                                    "click": "Click 🖱️",
                                    "fill": "Escribir ⌨️",
                                    "select": "Seleccionar 📋",
                                    "navigation": "Ir a URL 🌐",
                                    "extract": "Extraer Texto 🔍"
                                }
                                accion_legible = tipo_map.get(dato["tipo_accion"], dato["tipo_accion"].capitalize())
                                val_check = "☑" if dato.get("seleccionado", True) else "☐"
                                self.tabla.insert(
                                    "",
                                    "end",
                                    iid=str(idx),
                                    values=(val_check, idx, accion_legible, dato["descriptor_legible"], dato["valor"]),
                                    tags=("par" if idx % 2 == 0 else "impar",)
                                )
                    elif tipo == "finalizado":
                        self.btn_start.state(["!disabled"])
                        self.entry_url.state(["!disabled"])
                        self.combo_modo.state(["!disabled"])
                        self.combo_navegador.state(["!disabled"])
                        self.btn_stop.state(["disabled"])
                        self.btn_pause.state(["disabled"])
                        self.capture_thread = None
                except Exception as inner_err:
                    try:
                        with open(self.log_file, "a", encoding="utf-8") as f:
                            f.write(f"GUI Error interno procesando tipo {tipo}: {inner_err}\n")
                    except Exception:
                        pass
        except Exception as outer_err:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(f"GUI Error externo en procesar_cola: {outer_err}\n")
            except Exception:
                pass
        finally:
            self.root.after(100, self.procesar_cola)

    def actualizar_tabla_completa(self):
        # Guardamos la selección actual para restablecerla después
        seleccionada = self.tabla.selection()
        selected_idx = seleccionada[0] if seleccionada else None

        for item in self.tabla.get_children():
            self.tabla.delete(item)

        modo = self.combo_modo.get()
        is_api = "APIs" in modo
        is_scraper = "Scraper" in modo

        for idx, pet in enumerate(self.peticiones_capturadas):
            val_check = "☑" if pet.get("seleccionado", True) else "☐"
            if is_api:
                url_corta = pet["url"]
                if len(url_corta) > 120:
                    url_corta = url_corta[:117] + "..."
                self.tabla.insert("", "end", iid=str(idx),
                    values=(val_check, idx, pet["metodo"], pet["status"], url_corta),
                    tags=("par" if idx % 2 == 0 else "impar",))
            elif is_scraper:
                fase = pet.get("fase_scraper", "extract")
                if fase == "extract":
                    nombre = pet.get("nombre_campo", "")
                    preview = (pet.get("valor") or "")[:50]
                    self.tabla.insert("", "end", iid=str(idx),
                        values=(val_check, idx, "📤 Extraer", nombre,
                                pet.get("selector_sugerido", ""), preview),
                        tags=("extract",))
                else:
                    tipo_accion = pet.get("tipo_accion", "")
                    tipo_map = {"click": "Click 🖱️", "fill": "Escribir ⌨️",
                                "select": "Seleccionar 📋", "navigation": "Ir a URL 🌐"}
                    accion_legible = tipo_map.get(tipo_accion, tipo_accion.capitalize())
                    desc = pet.get("descriptor_legible", "") or pet.get("valor", "")[:40]
                    self.tabla.insert("", "end", iid=str(idx),
                        values=(val_check, idx, "🔧 Setup",
                                f"{accion_legible}: {desc[:35]}",
                                pet.get("selector_sugerido", ""),
                                (pet.get("valor") or "")[:50]),
                        tags=("setup",))
            else:
                tipo_map = {
                    "click": "Click 🖱️",
                    "fill": "Escribir ⌨️",
                    "select": "Seleccionar 📋",
                    "navigation": "Ir a URL 🌐",
                    "extract": "Extraer Texto 🔍"
                }
                accion_legible = tipo_map.get(pet["tipo_accion"], pet["tipo_accion"].capitalize())
                self.tabla.insert(
                    "",
                    "end",
                    iid=str(idx),
                    values=(val_check, idx, accion_legible, pet["descriptor_legible"], pet["valor"]),
                    tags=("par" if idx % 2 == 0 else "impar",)
                )
                
        # Restablecemos la selección si sigue existiendo
        if selected_idx and self.tabla.exists(selected_idx):
            self.tabla.selection_set(selected_idx)

    # -------------------------------------------------------------
    # INTERACCIONES Y MENÚ CONTEXTUAL
    # -------------------------------------------------------------
    def on_peticion_seleccionada(self, event):
        seleccion = self.tabla.selection()
        if not seleccion:
            self.limpiar_detalles()
            return

        idx = int(seleccion[0])
        pet = self.peticiones_capturadas[idx]
        modo = self.combo_modo.get()

        # Resaltar elemento en caliente en el navegador (si está activo en modo DOM o Scraper)
        if self.capture_thread and self.capture_thread.is_alive() and ("Grabador" in modo or "Scraper" in modo):
            sug = pet.get("selector_sugerido")
            if sug:
                self.capture_thread.input_queue.put(("highlight", sug))

        if "APIs" in modo:
            # 1. Mostrar Headers
            headers_info = []
            headers_info.append("=== GENERAL ===")
            headers_info.append(f"Request URL: {pet.get('url', '')}")
            headers_info.append(f"Request Method: {pet.get('metodo', '')}")
            headers_info.append(f"Status Code: {pet.get('status', '')}")
            headers_info.append("")
            headers_info.append("=== REQUEST HEADERS ===")
            for k, v in pet.get("headers_peticion", {}).items():
                headers_info.append(f"{k}: {v}")
            headers_info.append("")
            headers_info.append("=== RESPONSE HEADERS ===")
            for k, v in pet.get("headers_respuesta", {}).items():
                headers_info.append(f"{k}: {v}")

            self.actualizar_caja_texto_headers(self.txt_headers, "\n".join(headers_info))

            # 2. Mostrar Payload
            payload = pet.get("payload_enviado")
            if payload:
                try:
                    payload_json = json.loads(payload)
                    payload_str = json.dumps(payload_json, indent=4, ensure_ascii=False)
                except Exception:
                    payload_str = payload
            else:
                payload_str = "<Sin Payload / Sin datos enviados>"
            self.actualizar_caja_texto_json(self.txt_payload, payload_str)

            # 3. Mostrar Respuesta
            respuesta = pet.get("respuesta")
            if respuesta is not None:
                if isinstance(respuesta, (dict, list)):
                    respuesta_str = json.dumps(respuesta, indent=4, ensure_ascii=False)
                else:
                    respuesta_str = str(respuesta)
            else:
                respuesta_str = "<Sin Respuesta capturada o respuesta vacía>"
            self.actualizar_caja_texto_json(self.txt_response, respuesta_str)

            # 4. Poblar el Árbol JSON (Opción B)
            self.poblar_arbol_json(pet.get("respuesta"))

        elif "Scraper" in modo:
            # Modo Scraper: mostrar detalles del campo capturado
            atributos_info = []
            atributos_info.append("=== CAMPO DE SCRAPING ===")
            atributos_info.append(f"Nombre del Campo: {pet.get('nombre_campo', '')}")
            atributos_info.append(f"Tag HTML: {pet.get('tagName', '')}")
            atributos_info.append(f"ID: {pet.get('id') or '<Ninguno>'}")
            atributos_info.append(f"Name: {pet.get('name') or '<Ninguno>'}")
            atributos_info.append(f"Class Name: {pet.get('className') or '<Ninguno>'}")
            atributos_info.append(f"")
            atributos_info.append(f"=== VALOR CAPTURADO (PREVIEW) ===")
            atributos_info.append(pet.get("valor", "<vacío>"))
            self.actualizar_caja_texto_headers(self.txt_headers, "\n".join(atributos_info))

            selectores_info = []
            selectores_info.append("=== SELECTOR SUGERIDO (PLAYWRIGHT) ===")
            sug = pet.get("selector_sugerido", "")
            from captura_api import resolver_locator_playwright
            locator_traducido = resolver_locator_playwright(sug)
            selectores_info.append(locator_traducido if sug else "<No aplicable>")
            selectores_info.append("")
            selectores_info.append("=== SELECTORES ALTERNATIVOS ===")
            if pet.get("id"):
                selectores_info.append(f"Por ID: #{pet['id']}")
            if pet.get("name"):
                selectores_info.append(f"Por Name: [name='{pet['name']}']")
            if pet.get("xpath"):
                selectores_info.append(f"Por XPath: {pet['xpath']}")
            selectores_info.append("")
            selectores_info.append("=== TIPO DE DATO DETECTADO ===")
            tag = (pet.get("tagName") or "").lower()
            if tag == "a":
                selectores_info.append("Enlace → se extraerá atributo href")
            elif tag == "img":
                selectores_info.append("Imagen → se extraerá atributo src")
            else:
                selectores_info.append("Texto → se extraerá inner_text()")
            self.actualizar_caja_texto_headers(self.txt_payload, "\n".join(selectores_info))

            html_raw = pet.get("outerHTML", "<No disponible>")
            self.actualizar_caja_texto(self.txt_response, html_raw)

        else:
            # Modo Grabador DOM
            # 1. Mostrar Atributos
            atributos_info = []
            atributos_info.append("=== ATRIBUTOS DEL ELEMENTO ===")
            atributos_info.append(f"Tag Name: {pet.get('tagName', '')}")
            atributos_info.append(f"ID: {pet.get('id') or '<Ninguno>'}")
            atributos_info.append(f"Name: {pet.get('name') or '<Ninguno>'}")
            atributos_info.append(f"Class Name: {pet.get('className') or '<Ninguno>'}")
            atributos_info.append(f"Type: {pet.get('type') or '<Ninguno>'}")
            atributos_info.append(f"Placeholder: {pet.get('placeholder') or '<Ninguno>'}")
            self.actualizar_caja_texto_headers(self.txt_headers, "\n".join(atributos_info))

            # 2. Mostrar Selectores
            selectores_info = []
            selectores_info.append("=== SELECTOR SUGERIDO (PLAYWRIGHT) ===")
            sug = pet.get("selector_sugerido", "")

            from captura_api import resolver_locator_playwright
            locator_traducido = resolver_locator_playwright(sug)
            selectores_info.append(locator_traducido if sug else "<No aplicable>")
            selectores_info.append("")
            selectores_info.append("=== SELECTORES ALTERNATIVOS ===")
            if pet.get("id"):
                selectores_info.append(f"Por ID: #{pet['id']}")
            if pet.get("name"):
                selectores_info.append(f"Por Name: [name='{pet['name']}']")
            if pet.get("placeholder"):
                selectores_info.append(f"Por Placeholder: [placeholder='{pet['placeholder']}']")
            tag_name = pet.get('tagName', '').lower()
            if tag_name:
                selectores_info.append(f"Por CSS/Tag: {tag_name}")
            if pet.get("xpath"):
                selectores_info.append(f"Por XPath: {pet['xpath']}")
            self.actualizar_caja_texto_headers(self.txt_payload, "\n".join(selectores_info))

            # 3. Mostrar HTML Externo
            html_raw = pet.get("outerHTML", "<No disponible (por ejemplo, en navegación)>")
            self.actualizar_caja_texto(self.txt_response, html_raw)

    def on_tabla_double_click(self, event):
        item_id = self.tabla.identify_row(event.y)
        if item_id:
            self.toggle_seleccion_item(item_id)

    def on_tabla_space(self, event):
        seleccion = self.tabla.selection()
        if seleccion:
            for item_id in seleccion:
                self.toggle_seleccion_item(item_id)

    def toggle_seleccion_item(self, item_id):
        idx = int(item_id)
        pet = self.peticiones_capturadas[idx]
        nuevo_estado = not pet.get("seleccionado", True)
        pet["seleccionado"] = nuevo_estado
        self.actualizar_tabla_completa()

    def seleccionar_todos(self):
        for idx in range(len(self.peticiones_capturadas)):
            self.peticiones_capturadas[idx]["seleccionado"] = True
        self.actualizar_tabla_completa()

    def deseleccionar_todos(self):
        for idx in range(len(self.peticiones_capturadas)):
            self.peticiones_capturadas[idx]["seleccionado"] = False
        self.actualizar_tabla_completa()

    def mostrar_menu_contextual(self, event):
        item_id = self.tabla.identify_row(event.y)
        if not item_id:
            return
        
        self.tabla.selection_set(item_id)
        
        # Menú contextual de click derecho
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="✏️ Editar Paso", command=self.abrir_editor_paso)
        menu.add_command(label="❌ Eliminar Paso", command=self.eliminar_paso)
        menu.add_separator()
        menu.add_command(label="⬆️ Subir Paso", command=self.subir_paso)
        menu.add_command(label="⬇️ Bajar Paso", command=self.bajar_paso)
        
        menu.post(event.x_root, event.y_root)

    def eliminar_paso(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        idx = int(seleccion[0])
        if 0 <= idx < len(self.peticiones_capturadas):
            del self.peticiones_capturadas[idx]
            self.actualizar_tabla_completa()
            self.limpiar_detalles()

    def subir_paso(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        idx = int(seleccion[0])
        if idx > 0:
            self.peticiones_capturadas[idx], self.peticiones_capturadas[idx - 1] = \
                self.peticiones_capturadas[idx - 1], self.peticiones_capturadas[idx]
            self.actualizar_tabla_completa()
            self.tabla.selection_set(str(idx - 1))

    def bajar_paso(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        idx = int(seleccion[0])
        if idx < len(self.peticiones_capturadas) - 1:
            self.peticiones_capturadas[idx], self.peticiones_capturadas[idx + 1] = \
                self.peticiones_capturadas[idx + 1], self.peticiones_capturadas[idx]
            self.actualizar_tabla_completa()
            self.tabla.selection_set(str(idx + 1))

    def abrir_editor_paso(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        idx = int(seleccion[0])
        pet = self.peticiones_capturadas[idx]
        
        editor = tk.Toplevel(self.root)
        editor.title(f"Editar Paso {idx}")
        editor.geometry("600x380")
        editor.configure(bg=self.color_bg)
        editor.transient(self.root)
        editor.grab_set()
        
        modo = self.combo_modo.get()
        is_api = "APIs" in modo
        
        lbl_tit = ttk.Label(editor, text=f"Editar Datos del Paso #{idx}", style="Header.TLabel", padding=15)
        lbl_tit.pack(anchor="w")
        
        frame_form = ttk.Frame(editor, padding=10)
        frame_form.pack(fill=tk.BOTH, expand=True)
        frame_form.columnconfigure(1, weight=1)
        
        entries = {}
        
        if is_api:
            ttk.Label(frame_form, text="URL:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
            entry_url = ttk.Entry(frame_form, font=("Segoe UI", 10))
            entry_url.insert(0, pet.get("url", ""))
            entry_url.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
            entries["url"] = entry_url

            ttk.Label(frame_form, text="Método:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
            entry_method = ttk.Entry(frame_form, font=("Segoe UI", 10))
            entry_method.insert(0, pet.get("metodo", ""))
            entry_method.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
            entries["metodo"] = entry_method

            ttk.Label(frame_form, text="Payload:").grid(row=2, column=0, sticky="nw", pady=5, padx=5)
            txt_payload = scrolledtext.ScrolledText(frame_form, height=6, bg=self.color_panel, fg=self.color_fg, font=("Consolas", 10))
            txt_payload.insert(tk.END, pet.get("payload_enviado") or "")
            txt_payload.grid(row=2, column=1, sticky="nsew", pady=5, padx=5)
            frame_form.rowconfigure(2, weight=1)
            entries["payload_enviado"] = txt_payload
        elif "Scraper" in modo:
            ttk.Label(frame_form, text="Nombre del Campo:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
            entry_nombre = ttk.Entry(frame_form, font=("Segoe UI", 10))
            entry_nombre.insert(0, pet.get("nombre_campo", ""))
            entry_nombre.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
            entries["nombre_campo"] = entry_nombre

            ttk.Label(frame_form, text="Selector Sugerido:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
            entry_sel = ttk.Entry(frame_form, font=("Segoe UI", 10))
            entry_sel.insert(0, pet.get("selector_sugerido", ""))
            entry_sel.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
            entries["selector_sugerido"] = entry_sel

            ttk.Label(frame_form, text="XPath:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
            entry_xpath = ttk.Entry(frame_form, font=("Segoe UI", 10))
            entry_xpath.insert(0, pet.get("xpath", ""))
            entry_xpath.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
            entries["xpath"] = entry_xpath
        else:
            # Modo Grabador DOM
            ttk.Label(frame_form, text="Descriptor:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
            entry_desc = ttk.Entry(frame_form, font=("Segoe UI", 10))
            entry_desc.insert(0, pet.get("descriptor_legible", ""))
            entry_desc.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
            entries["descriptor_legible"] = entry_desc
            
            ttk.Label(frame_form, text="Selector Sugerido:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
            entry_sel = ttk.Entry(frame_form, font=("Segoe UI", 10))
            entry_sel.insert(0, pet.get("selector_sugerido", ""))
            entry_sel.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
            entries["selector_sugerido"] = entry_sel
            
            ttk.Label(frame_form, text="Valor / Texto:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
            entry_val = ttk.Entry(frame_form, font=("Segoe UI", 10))
            entry_val.insert(0, pet.get("valor", ""))
            entry_val.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
            entries["valor"] = entry_val

            
        def guardar():
            for k, widget in entries.items():
                if isinstance(widget, scrolledtext.ScrolledText):
                    pet[k] = widget.get("1.0", tk.END).strip()
                else:
                    pet[k] = widget.get().strip()
            editor.destroy()
            self.actualizar_tabla_completa()
            self.on_peticion_seleccionada(None)
            
        frame_btns = ttk.Frame(editor, padding=10)
        frame_btns.pack(side=tk.BOTTOM, fill=tk.X)
        
        btn_save = ttk.Button(frame_btns, text="💾 Guardar", style="Accent.TButton", command=guardar)
        btn_save.pack(side=tk.RIGHT, padx=5)
        
        btn_cancel = ttk.Button(frame_btns, text="Cancelar", command=editor.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=5)

    def limpiar_detalles(self):
        self.actualizar_caja_texto(self.txt_headers, "")
        self.actualizar_caja_texto(self.txt_payload, "")
        self.actualizar_caja_texto(self.txt_response, "")

    def actualizar_caja_texto(self, widget, contenido):
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, contenido)
        widget.config(state=tk.DISABLED)

    def actualizar_caja_texto_json(self, widget, contenido):
        import re
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, contenido)
        
        if contenido and not contenido.startswith("<") and (contenido.strip().startswith("{") or contenido.strip().startswith("[")):
            widget.tag_configure("key", foreground="#9cdcfe", font=("Consolas", 10, "bold"))
            widget.tag_configure("string", foreground="#ce9178", font=("Consolas", 10))
            widget.tag_configure("number", foreground="#b5cea8", font=("Consolas", 10))
            widget.tag_configure("boolean", foreground="#569cd6", font=("Consolas", 10, "bold"))
            widget.tag_configure("bracket", foreground="#ffd700", font=("Consolas", 10))
            
            for m in re.finditer(r'[{}[\]]', contenido):
                start = f"1.0 + {m.start()} chars"
                end = f"1.0 + {m.end()} chars"
                widget.tag_add("bracket", start, end)
                
            for m in re.finditer(r'"([^"\\]|\\.)*"\s*:', contenido):
                start = f"1.0 + {m.start()} chars"
                end = f"1.0 + {m.end() - 1} chars"
                widget.tag_add("key", start, end)
                
            for m in re.finditer(r'"([^"\\]|\\.)*"', contenido):
                resto = contenido[m.end():]
                match_dos_puntos = re.match(r'^\s*:', resto)
                start = f"1.0 + {m.start()} chars"
                end = f"1.0 + {m.end()} chars"
                if not match_dos_puntos:
                    widget.tag_add("string", start, end)
                    
            for m in re.finditer(r'\b-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b', contenido):
                start = f"1.0 + {m.start()} chars"
                end = f"1.0 + {m.end()} chars"
                widget.tag_add("number", start, end)
                
            for m in re.finditer(r'\b(?:true|false|null)\b', contenido):
                start = f"1.0 + {m.start()} chars"
                end = f"1.0 + {m.end()} chars"
                widget.tag_add("boolean", start, end)
                
        widget.config(state=tk.DISABLED)

    def actualizar_caja_texto_headers(self, widget, contenido):
        import re
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, contenido)
        
        widget.tag_configure("seccion", foreground="#818cf8", font=("Consolas", 10, "bold"))
        widget.tag_configure("clave", foreground="#9cdcfe", font=("Consolas", 9, "bold"))
        widget.tag_configure("valor", foreground="#f8fafc", font=("Consolas", 9))
        
        for m in re.finditer(r'^===.*===$', contenido, re.MULTILINE):
            start = f"1.0 + {m.start()} chars"
            end = f"1.0 + {m.end()} chars"
            widget.tag_add("seccion", start, end)
            
        lineas = contenido.split("\n")
        char_count = 0
        for linea in lineas:
            if not linea.startswith("===") and ": " in linea:
                idx_dos_puntos = linea.find(": ")
                start = f"1.0 + {char_count} chars"
                end = f"1.0 + {char_count + idx_dos_puntos} chars"
                widget.tag_add("clave", start, end)
            char_count += len(linea) + 1
            
        widget.config(state=tk.DISABLED)

    def _on_motor_cambiado(self):
        """Muestra/oculta el panel de login BS4 y el aviso según el motor elegido."""
        motor = self.scraper_motor.get() if hasattr(self, "scraper_motor") else "playwright"
        tiene_setup = any(p.get("fase_scraper") == "setup" for p in self.peticiones_capturadas)

        if motor == "bs4":
            # Mostrar panel de login BS4
            if hasattr(self, "frame_bs4_login"):
                self.frame_bs4_login.pack(fill="x", pady=4)
            # Mostrar aviso si hay pasos de setup capturados
            if tiene_setup and hasattr(self, "lbl_motor_aviso"):
                self.lbl_motor_aviso.pack(anchor="w", pady=(0, 2))
        else:
            # Ocultar panel de login BS4
            if hasattr(self, "frame_bs4_login"):
                self.frame_bs4_login.pack_forget()
            if hasattr(self, "lbl_motor_aviso"):
                self.lbl_motor_aviso.pack_forget()

    # -----------------------------------------------------------------
    # Red POST en modo Scraper
    # -----------------------------------------------------------------
    def on_post_seleccionado(self, event=None):
        """Muestra los detalles del request POST seleccionado en el panel de detalle."""
        sel = self.tabla_red_post.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx >= len(self.peticiones_red_post):
            return
        pet = self.peticiones_red_post[idx]

        lineas = []
        lineas.append(f"=== {pet.get('metodo', 'POST')}  {pet.get('status', '')} ===")
        lineas.append(f"URL: {pet.get('url', '')}")
        lineas.append("")
        lineas.append("--- REQUEST BODY ---")
        rb = pet.get("request_body")
        if rb is None:
            lineas.append("(sin cuerpo)")
        elif isinstance(rb, dict):
            lineas.append(json.dumps(rb, indent=2, ensure_ascii=False))
        else:
            lineas.append(str(rb))
        lineas.append("")
        lineas.append("--- RESPONSE ---")
        resp = pet.get("respuesta")
        if resp is None:
            lineas.append("(sin respuesta / error)")
        elif isinstance(resp, dict):
            lineas.append(json.dumps(resp, indent=2, ensure_ascii=False))
        else:
            lineas.append(str(resp))

        texto = "\n".join(lineas)
        self.txt_red_detalle.config(state=tk.NORMAL)
        self.txt_red_detalle.delete("1.0", tk.END)
        self.txt_red_detalle.insert(tk.END, texto)
        self.txt_red_detalle.config(state=tk.DISABLED)

    def autodetectar_login_bs4(self):
        """Analiza el request POST seleccionado y auto-rellena los campos de Login BS4."""
        sel = self.tabla_red_post.selection()
        if not sel:
            messagebox.showinfo("Sin selección",
                "Seleccioná un request POST de la lista antes de autocompletar.")
            return
        idx = int(sel[0])
        if idx >= len(self.peticiones_red_post):
            return
        pet = self.peticiones_red_post[idx]

        url      = pet.get("url", "")
        body     = pet.get("request_body") or {}
        response = pet.get("respuesta") or {}

        # --- Detectar tipo de auth y campos ---
        auth_tipo   = "form_post"
        user_field  = "username"
        pass_field  = "password"
        token_field = "token"

        if isinstance(body, dict):
            auth_tipo = "json_post"
            # Buscar campo de usuario
            for k in body:
                if any(p in k.lower() for p in ["user", "login", "email", "correo", "usuario"]):
                    user_field = k
                    break
            # Buscar campo de contraseña
            for k in body:
                if any(p in k.lower() for p in ["pass", "clave", "secret", "pwd", "contrasena", "contrase"]):
                    pass_field = k
                    break
        elif isinstance(body, str) and "=" in body:
            auth_tipo = "form_post"  # URL-encoded form

        # --- Detectar token en la respuesta ---
        if isinstance(response, dict):
            for k in response:
                if any(p in k.lower() for p in ["token", "access", "jwt", "auth", "bearer"]):
                    token_field = k
                    # Si la respuesta tiene un token, probablemente es bearer
                    auth_tipo = "bearer_token"
                    break

        # --- Rellenar el panel Login BS4 ---
        if hasattr(self, "bs4_login_url"):
            self.bs4_login_url.set(url)
        if hasattr(self, "bs4_login_user_field"):
            self.bs4_login_user_field.set(user_field)
        if hasattr(self, "bs4_login_pass_field"):
            self.bs4_login_pass_field.set(pass_field)
        if hasattr(self, "bs4_auth_tipo"):
            self.bs4_auth_tipo.set(auth_tipo)
        if hasattr(self, "bs4_token_field"):
            self.bs4_token_field.set(token_field)

        # Activar motor BS4 y mostrar su panel
        if hasattr(self, "scraper_motor"):
            self.scraper_motor.set("bs4")
            self._on_motor_cambiado()

        messagebox.showinfo(
            "✅ Login BS4 autocompletado",
            f"Se detectó:\n"
            f"  URL Login: {url[:60]}\n"
            f"  Campo usuario: {user_field}\n"
            f"  Campo contraseña: {pass_field}\n"
            f"  Tipo Auth: {auth_tipo}\n"
            f"  Campo token: {token_field}\n\n"
            "Revisá y ajustá los valores en el panel 'Login BS4' si es necesario."
        )


    # -------------------------------------------------------------
    # ÁRBOL JSON (Opción B)
    # -------------------------------------------------------------
    def poblar_arbol_json(self, dato):
        """Rellena el Treeview del árbol JSON con los datos de la respuesta seleccionada."""
        for item in self.arbol_json.get_children():
            self.arbol_json.delete(item)

        if dato is None:
            self.arbol_json.insert("", "end", text="<Sin datos>", values=("", "", ""))
            return

        self._insertar_nodo_arbol("", "", dato, ruta="raiz")

    def _insertar_nodo_arbol(self, parent, clave, valor, ruta=""):
        """Inserta recursivamente un nodo en el árbol JSON."""
        MAX_HIJOS = 200  # límite para evitar cuelgues con respuestas masivas

        if isinstance(valor, dict):
            tipo_str = f"dict ({len(valor)})"
            node_id = self.arbol_json.insert(
                parent, "end",
                text=f"📁 {clave}" if clave else "📁 [raíz]",
                values=(clave, tipo_str, ""),
                open=(parent == "")  # expandir el nodo raíz por defecto
            )
            for i, (k, v) in enumerate(valor.items()):
                if i >= MAX_HIJOS:
                    self.arbol_json.insert(node_id, "end", text="... [truncado]", values=("", "", f"{len(valor) - MAX_HIJOS} campos más"))
                    break
                self._insertar_nodo_arbol(node_id, k, v, ruta=f"{ruta}.{k}")

        elif isinstance(valor, list):
            tipo_str = f"list ({len(valor)})"
            node_id = self.arbol_json.insert(
                parent, "end",
                text=f"📋 {clave}" if clave else "📋 [raíz]",
                values=(clave, tipo_str, ""),
                open=(parent == "")
            )
            for i, item in enumerate(valor):
                if i >= MAX_HIJOS:
                    self.arbol_json.insert(node_id, "end", text="... [truncado]", values=("", "", f"{len(valor) - MAX_HIJOS} items más"))
                    break
                self._insertar_nodo_arbol(node_id, f"[{i}]", item, ruta=f"{ruta}[{i}]")

        else:
            # Valor escalar: string, número, bool, null
            if isinstance(valor, bool):
                tipo_str = "bool"
                val_str = str(valor).lower()
            elif isinstance(valor, int):
                tipo_str = "int"
                val_str = str(valor)
            elif isinstance(valor, float):
                tipo_str = "float"
                val_str = str(valor)
            elif valor is None:
                tipo_str = "null"
                val_str = "null"
            else:
                tipo_str = "str"
                val_str = str(valor)
                if len(val_str) > 120:
                    val_str = val_str[:117] + "..."

            self.arbol_json.insert(
                parent, "end",
                text=f"  {clave}",
                values=(clave, tipo_str, val_str)
            )

    # -------------------------------------------------------------
    # GENERACIÓN DE CÓDIGO
    # -------------------------------------------------------------
    def generar_codigo_flujo(self):
        peticiones_a_unificar = []
        for idx, pet in enumerate(self.peticiones_capturadas):
            if pet.get("seleccionado", True):
                pet_copia = pet.copy()
                pet_copia["original_index"] = idx
                peticiones_a_unificar.append(pet_copia)

        if not peticiones_a_unificar:
            messagebox.showwarning("Atención", "Debe seleccionar (marcar con ☑) al menos un elemento de la tabla.")
            return

        modo = self.combo_modo.get()
        is_api = "APIs" in modo
        is_scraper = "Scraper" in modo

        if is_scraper:
            url_obj = self.entry_url.get().strip()
            motor   = getattr(self, "scraper_motor", None)
            motor   = motor.get() if motor else "playwright"

            # Separar pasos de Setup y campos de Extracción
            pasos_setup   = [p for p in peticiones_a_unificar if p.get("fase_scraper", "extract") == "setup"]
            campos_extract = [p for p in peticiones_a_unificar if p.get("fase_scraper", "extract") == "extract"]

            if motor == "bs4" and pasos_setup:
                messagebox.showerror(
                    "Motor incompatible",
                    "El motor 'requests + BeautifulSoup' no soporta pasos de Setup/Login.\n"
                    "Desactivá los pasos de Setup (desmarcalos) o usá el motor Playwright."
                )
                return

            if not campos_extract:
                messagebox.showwarning(
                    "Sin campos de extracción",
                    "No hay campos marcados como '📤 Extraer'.\n"
                    "Usa Shift+Clic en el navegador para marcar elementos a extraer."
                )
                return

            config_scraping = {
                "selector_paginacion": self.scraper_selector_paginacion.get().strip(),
                "max_paginas":  self.scraper_max_paginas.get(),
                "delay_paginas": self.scraper_delay.get(),
                "formato_csv":  self.scraper_fmt_csv.get(),
                "formato_json": self.scraper_fmt_json.get(),
                "headless":     self.scraper_headless.get(),
            }

            from tkinter import filedialog
            if motor == "bs4":
                nombre_sugerido = "scraper_bs4.py"
                titulo_dialogo  = "Guardar Script BS4 Como"
            else:
                nombre_sugerido = "scraper_generado.py"
                titulo_dialogo  = "Guardar Script Playwright Como"

            nombre_archivo = filedialog.asksaveasfilename(
                initialdir=self.output_base_dir,
                initialfile=nombre_sugerido,
                defaultextension=".py",
                filetypes=[("Archivos Python", "*.py"), ("Todos los archivos", "*.*")],
                title=titulo_dialogo
            )
            if not nombre_archivo:
                return

            try:
                if motor == "bs4":
                    # Construir login_config desde los campos del panel BS4
                    login_url_val = getattr(self, "bs4_login_url", None)
                    login_url_val = login_url_val.get().strip() if login_url_val else ""
                    lc = None
                    if login_url_val:
                        lc = {
                            "login_url":   login_url_val,
                            "user_field":  getattr(self, "bs4_login_user_field", tk.StringVar(value="username")).get(),
                            "pass_field":  getattr(self, "bs4_login_pass_field", tk.StringVar(value="password")).get(),
                            "auth_tipo":   getattr(self, "bs4_auth_tipo", tk.StringVar(value="form_post")).get(),
                            "token_field": getattr(self, "bs4_token_field", tk.StringVar(value="token")).get(),
                        }
                    generar_script_scraping_bs4(
                        campos_extract=campos_extract,
                        url_objetivo=url_obj,
                        config_scraping=config_scraping,
                        nombre_archivo=nombre_archivo,
                        login_config=lc
                    )

                else:
                    # Playwright — pasamos TODOS (setup + extract)
                    generar_script_scraping(
                        campos_scraping=peticiones_a_unificar,
                        url_objetivo=url_obj,
                        config_scraping=config_scraping,
                        nombre_archivo=nombre_archivo
                    )

                if os.path.exists(nombre_archivo):
                    with open(nombre_archivo, "r", encoding="utf-8") as f:
                        codigo_generado = f.read()
                    self.mostrar_popup_codigo(nombre_archivo, codigo_generado)
                else:
                    messagebox.showerror("Error", f"No se pudo generar el archivo {nombre_archivo}.")
            except Exception as e:
                messagebox.showerror("Error", f"Error al generar el script de scraping:\n{e}")
            return

        if is_api:
            from tkinter import filedialog
            nombre_archivo = filedialog.asksaveasfilename(
                initialdir=self.output_base_dir,
                initialfile="flujo_unificado.py",
                defaultextension=".py",
                filetypes=[("Archivos Python", "*.py"), ("Todos los archivos", "*.*")],
                title="Guardar Flujo Unificado Como"
            )
            if not nombre_archivo:
                return

            try:
                generar_script_unificado(
                    peticiones_a_unificar, 
                    nombre_archivo=nombre_archivo, 
                    parametrizar=self.var_parametrizar.get()
                )
                if os.path.exists(nombre_archivo):
                    with open(nombre_archivo, "r", encoding="utf-8") as f:
                        codigo_generado = f.read()
                    self.mostrar_popup_codigo(nombre_archivo, codigo_generado)
                else:
                    messagebox.showerror("Error", f"No se pudo generar el archivo {nombre_archivo}.")
            except Exception as e:
                messagebox.showerror("Error", f"Error al generar el flujo unificado: {e}")
        else:
            self.abrir_opciones_exportacion_dom(peticiones_a_unificar)

    def abrir_opciones_exportacion_dom(self, acciones):
        export_win = tk.Toplevel(self.root)
        export_win.title("Exportar Elementos y Acciones DOM")
        export_win.geometry("500x320")
        export_win.resizable(False, False)
        export_win.configure(bg=self.color_bg)
        export_win.transient(self.root)
        export_win.grab_set()

        lbl_titulo = ttk.Label(
            export_win, 
            text="Selecciona el formato de exportación:", 
            style="Header.TLabel", 
            padding=15
        )
        lbl_titulo.pack(anchor="w")

        lbl_desc = ttk.Label(
            export_win,
            text="Puedes generar el código de automatización para Playwright\no extraer la lista de selectores y alternativas capturadas.",
            style="Status.TLabel",
            padding=(15, 0, 15, 20)
        )
        lbl_desc.pack(anchor="w")

        def procesar_exportacion(opcion):
            from tkinter import filedialog
            
            if opcion == "py":
                file_types = [("Archivos Python", "*.py")]
                init_file = "automatizacion_dom.py"
                title = "Guardar Script de Automatización Playwright"
                defaultext = ".py"
            elif opcion == "json":
                file_types = [("Archivos JSON", "*.json")]
                init_file = "selectores_capturados.json"
                title = "Guardar Lista de Selectores JSON"
                defaultext = ".json"
            else:
                file_types = [("Archivos de Texto", "*.txt")]
                init_file = "reporte_selectores.txt"
                title = "Guardar Reporte de Selectores"
                defaultext = ".txt"

            nombre_archivo = filedialog.asksaveasfilename(
                initialdir=self.output_base_dir,
                initialfile=init_file,
                defaultextension=defaultext,
                filetypes=file_types,
                title=title
            )
            if not nombre_archivo:
                return

            export_win.destroy()

            try:
                if opcion == "py":
                    generar_script_automatizacion_dom(
                        acciones, 
                        nombre_archivo=nombre_archivo, 
                        parametrizar=self.var_parametrizar.get()
                    )
                elif opcion == "json":
                    generar_lista_selectores_json(acciones, nombre_archivo=nombre_archivo)
                else:
                    generar_reporte_selectores_txt(acciones, nombre_archivo=nombre_archivo)

                if os.path.exists(nombre_archivo):
                    with open(nombre_archivo, "r", encoding="utf-8") as f:
                        contenido = f.read()
                    self.mostrar_popup_codigo(nombre_archivo, contenido)
                else:
                    messagebox.showerror("Error", f"No se pudo generar el archivo {nombre_archivo}.")
            except Exception as e:
                messagebox.showerror("Error", f"Error al exportar elementos: {e}")

        frame_btns = ttk.Frame(export_win, style="TFrame")
        frame_btns.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        btn_py = ttk.Button(
            frame_btns,
            text="⚙️ Generar Script de Automatización (.py)",
            style="Accent.TButton",
            command=lambda: procesar_exportacion("py")
        )
        btn_py.pack(fill=tk.X, pady=6)

        btn_json = ttk.Button(
            frame_btns,
            text="📋 Exportar Lista Estructurada (.json)",
            style="TButton",
            command=lambda: procesar_exportacion("json")
        )
        btn_json.pack(fill=tk.X, pady=6)

        btn_txt = ttk.Button(
            frame_btns,
            text="📝 Exportar Reporte de Selectores (.txt)",
            style="TButton",
            command=lambda: procesar_exportacion("txt")
        )
        btn_txt.pack(fill=tk.X, pady=6)

        btn_cancel = ttk.Button(export_win, text="Cancelar", command=export_win.destroy)
        btn_cancel.pack(pady=15)

    def mostrar_popup_codigo(self, archivo, codigo):
        popup = tk.Toplevel(self.root)
        popup.title(f"Código Generado - {archivo}")
        popup.geometry("800x600")
        popup.configure(bg=self.color_bg)
        
        lbl = ttk.Label(popup, text=f"Archivo guardado exitosamente en: {archivo}", style="Header.TLabel", padding=10)
        lbl.pack(side=tk.TOP, fill=tk.X)
        
        txt = scrolledtext.ScrolledText(popup, bg="#2d2d2d", fg="#e0e0e0", font=("Consolas", 10))
        txt.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        txt.insert(tk.END, codigo)
        txt.config(state=tk.DISABLED)
        
        btn_close = ttk.Button(popup, text="Aceptar", command=popup.destroy)
        btn_close.pack(side=tk.BOTTOM, pady=10)

    def reproducir_video(self):
        patron = os.path.join(self.video_dir, "*.webm")
        videos = glob.glob(patron)
        
        if not videos:
            messagebox.showinfo("Video", "No se encontraron grabaciones de video en la carpeta 'output_videos/'. Realice una captura primero.")
            return
            
        video_reciente = max(videos, key=os.path.getmtime)
        
        try:
            self.lbl_status.config(text=f"Abriendo video: {os.path.basename(video_reciente)}")
            os.startfile(video_reciente)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo de video: {e}")

    def abrir_trace(self):
        # Determinar el directorio donde se guardan las trazas
        dir_trazas = self.config_output_dir.get().strip()
        if not dir_trazas or not os.path.exists(dir_trazas):
            dir_trazas = self.output_base_dir

        try:
            self.lbl_status.config(text="Abriendo visor de trazas (Playwright)...")
            
            from playwright._impl._driver import compute_driver_executable
            driver_exec = compute_driver_executable()
            
            # Lanzamos el comando show-trace sin ruta para abrir el visor limpio y sin errores de red/firewall
            if isinstance(driver_exec, (list, tuple)):
                cmd = list(driver_exec) + ["show-trace"]
            else:
                cmd = [driver_exec, "show-trace"]
            
            subprocess.Popen(
                cmd, 
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Informar al usuario en la barra de estado
            self.lbl_status.config(text="Visor abierto. Arrastra el archivo trace.zip desde la carpeta al navegador.")
            
            # Abrir automáticamente la carpeta contenedora en el explorador para facilitar el drag-and-drop
            try:
                os.startfile(dir_trazas)
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el visor de trazas: {e}")

    def abrir_configuracion(self):
        config_win = tk.Toplevel(self.root)
        config_win.title("Configuración Avanzada")
        config_win.geometry("520x630")
        config_win.resizable(False, False)
        config_win.configure(bg=self.color_bg)
        config_win.transient(self.root)
        config_win.grab_set()
        
        # Centrar ventana
        config_win.update_idletasks()
        w = config_win.winfo_width()
        h = config_win.winfo_height()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        config_win.geometry(f"+{x}+{y}")
        
        lbl_titulo = ttk.Label(config_win, text="⚙️ CONFIGURACIÓN AVANZADA", style="Header.TLabel", padding=15)
        lbl_titulo.pack(anchor="w")

        # Contenedor con Scroll/Canvas si fuera necesario, pero cabe todo en 630px si ordenamos bien
        main_frame = ttk.Frame(config_win, style="TFrame")
        main_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        # 1. Grupo: Motor y Navegación
        nav_frame = ttk.LabelFrame(main_frame, text="Parámetros de Navegación", padding=10)
        nav_frame.pack(fill="x", pady=5)

        chk_ssl = ttk.Checkbutton(nav_frame, text="Ignorar errores de SSL / HTTPS", variable=self.config_ignore_ssl)
        chk_ssl.grid(row=0, column=0, columnspan=2, sticky="w", pady=2)

        chk_headless = ttk.Checkbutton(nav_frame, text="Ejecutar en segundo plano (Headless)", variable=self.config_headless)
        chk_headless.grid(row=0, column=2, columnspan=2, sticky="w", pady=2)

        lbl_w = ttk.Label(nav_frame, text="Viewport Ancho:")
        lbl_w.grid(row=1, column=0, sticky="w", pady=6, padx=(0, 5))
        entry_w = ttk.Entry(nav_frame, textvariable=self.config_width, width=8, font=("Segoe UI", 9))
        entry_w.grid(row=1, column=1, sticky="w", pady=6)

        lbl_h = ttk.Label(nav_frame, text="Viewport Alto:")
        lbl_h.grid(row=1, column=2, sticky="w", pady=6, padx=(10, 5))
        entry_h = ttk.Entry(nav_frame, textvariable=self.config_height, width=8, font=("Segoe UI", 9))
        entry_h.grid(row=1, column=3, sticky="w", pady=6)

        # 2. Grupo: Salidas y Archivos
        out_frame = ttk.LabelFrame(main_frame, text="Grabación y Diagnóstico", padding=10)
        out_frame.pack(fill="x", pady=5)

        chk_video = ttk.Checkbutton(out_frame, text="Grabar video de sesión", variable=self.config_record_video)
        chk_video.grid(row=0, column=0, sticky="w", pady=2)

        chk_trace = ttk.Checkbutton(out_frame, text="Generar traza de Playwright", variable=self.config_record_trace)
        chk_trace.grid(row=0, column=1, sticky="w", pady=2, padx=(10, 0))

        lbl_timeout = ttk.Label(out_frame, text="Timeout global (seg):")
        lbl_timeout.grid(row=1, column=0, sticky="w", pady=6, padx=(0, 5))
        entry_timeout = ttk.Entry(out_frame, textvariable=self.config_timeout, width=8, font=("Segoe UI", 9))
        entry_timeout.grid(row=1, column=1, sticky="w", pady=6)

        # 3. Grupo: Carpeta de Almacenamiento
        dir_frame = ttk.LabelFrame(main_frame, text="Carpeta de Almacenamiento", padding=10)
        dir_frame.pack(fill="x", pady=5)

        entry_dir = ttk.Entry(dir_frame, textvariable=self.config_output_dir, font=("Segoe UI", 9))
        entry_dir.grid(row=0, column=0, sticky="ew", pady=5, padx=(0, 5))
        dir_frame.columnconfigure(0, weight=1)

        def examinar_carpeta():
            from tkinter import filedialog
            inicial = self.config_output_dir.get().strip()
            if not inicial or not os.path.exists(inicial):
                inicial = self.output_base_dir
            carpeta = filedialog.askdirectory(initialdir=inicial, parent=config_win, title="Seleccionar Carpeta de Destino")
            if carpeta:
                self.config_output_dir.set(os.path.normpath(carpeta))

        btn_browse = ttk.Button(dir_frame, text="📂 Examinar...", command=examinar_carpeta)
        btn_browse.grid(row=0, column=1, sticky="w", pady=5)

        # 4. Grupo: User-Agent Personalizado
        ua_frame = ttk.LabelFrame(main_frame, text="User-Agent Personalizado (Opcional)", padding=10)
        ua_frame.pack(fill="x", pady=5)

        entry_ua = ttk.Entry(ua_frame, textvariable=self.config_user_agent, font=("Segoe UI", 9))
        entry_ua.pack(fill="x", pady=2)

        # 5. Grupo: Info de App e Instalación
        info_frame = ttk.LabelFrame(main_frame, text="Aplicación y Actualizaciones", padding=10)
        info_frame.pack(fill="x", pady=5)
        info_frame.columnconfigure(0, weight=1)

        lbl_ver = ttk.Label(info_frame, text=f"Versión Actual: v{VERSION_LOCAL}", font=("Segoe UI", 9, "bold"))
        lbl_ver.grid(row=0, column=0, sticky="w", pady=2)

        btn_chk_update = ttk.Button(info_frame, text="🔄 Buscar Actualizaciones", command=lambda: verificar_actualizaciones(self, manual=True))
        btn_chk_update.grid(row=0, column=1, sticky="e", pady=2)

        # Botón Guardar
        btn_save = ttk.Button(config_win, text="Guardar y Cerrar", style="Accent.TButton", command=config_win.destroy)
        btn_save.pack(anchor="e", padx=15, pady=(0, 15))


if __name__ == "__main__":
    # Iniciar root de Tkinter y ocultarlo temporalmente
    root = tk.Tk()
    root.withdraw()
    
    # Crear y mostrar la ventana de carga (Splash Tkinter)
    ruta_splash = obtener_ruta_recurso(os.path.join("assets", "splash.png"))
    splash = SplashWindow(root, ruta_splash)
    
    # Cerrar el splash screen nativo de PyInstaller ya que tenemos el de Tkinter visible
    if _splash_disponible:
        try:
            pyi_splash.close()
        except Exception:
            pass
            
    # Bucle de carga y actualización de la barra
    def ejecutar_carga():
        try:
            # Cargar módulos y dependencias de forma secuencial
            cargar_modulos_y_dependencias(progress_callback=splash.update_status)
            
            # Carga completa: destruir splash e iniciar la ventana principal de la app
            splash.destroy()
            app = CapturaApp(root)
            root.deiconify() # Mostrar ventana principal
        except Exception as err:
            messagebox.showerror("Error de Inicialización", f"Error al cargar la aplicación:\n{err}")
            root.destroy()
            
    # Lanzar la carga usando after para que la interfaz del splash tenga tiempo de dibujarse
    root.after(100, ejecutar_carga)
    root.mainloop()
