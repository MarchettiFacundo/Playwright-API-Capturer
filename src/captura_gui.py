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

VERSION_LOCAL = "1.1.2"

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
            generar_reporte_selectores_txt as g_txt
        )
        limpiar_headers = l_headers
        generar_script_unificado = g_unificado
        generar_script_python = g_python
        generar_script_automatizacion_dom = g_dom
        generar_lista_selectores_json = g_json
        generar_reporte_selectores_txt = g_txt
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
            
        limpiar_headers = l_headers
        generar_script_unificado = g_unificado
        generar_script_python = g_python
        generar_script_automatizacion_dom = g_dom
        generar_lista_selectores_json = g_json
        generar_reporte_selectores_txt = g_txt
        
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
                 modo="APIs de Red (HTTP)", navegador="Chromium", viewport_width=1280, viewport_height=720, ignore_ssl_errors=True):
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
            
            # Lanzamos el motor de navegador seleccionado
            if self.navegador == "Firefox":
                self.browser = await self.playwright.firefox.launch(headless=False)
            elif self.navegador == "WebKit":
                self.browser = await self.playwright.webkit.launch(headless=False)
            else:
                self.browser = await self.playwright.chromium.launch(headless=False)
            
            # Creamos el contexto con grabación de video y configuraciones personalizadas
            self.context = await self.browser.new_context(
                ignore_https_errors=self.ignore_ssl_errors,
                viewport={"width": self.viewport_width, "height": self.viewport_height},
                record_video_dir=self.video_dir,
                record_video_size={"width": self.viewport_width, "height": self.viewport_height}
            )
            
            # Iniciamos el tracing de Playwright
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
                        self.output_queue.put(("accion_dom", datos))
                    except Exception as err:
                        print(f"[WARN] Error parseando JSON de acción DOM: {err}")
                
                await self.context.expose_binding("registrarAccionDOM", registrar_accion)
                await self.context.add_init_script(JS_SCRIPT)

            page = await self.context.new_page()
            
            def al_cerrar_pagina():
                self.output_queue.put(("status", "Página de navegación cerrada por el usuario."))
                self.stop()
                
            page.on("close", lambda p: al_cerrar_pagina())
            
            self.output_queue.put(("status", f"Navegando a {self.url}..."))
            
            if self.modo == "Grabador DOM (Acciones)":
                nav_data = {
                    "tipo_accion": "navigation",
                    "tagName": "WINDOW",
                    "descriptor_legible": "Navegación Inicial",
                    "selector_sugerido": "",
                    "valor": self.url,
                    "id": "",
                    "name": "",
                    "className": "",
                    "type": "",
                    "placeholder": "",
                    "xpath": "",
                    "outerHTML": "",
                    "seleccionado": True
                }
                self.output_queue.put(("accion_dom", nav_data))

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
            if self.context:
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
        
        self.combo_modo = ttk.Combobox(control_frame, values=["APIs de Red (HTTP)", "Grabador DOM (Acciones)"], state="readonly", width=18, font=("Segoe UI", 9))
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
        self.entry_url.insert(0, "https://rpa-site.claro.amx/")
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
            
            self.btn_generar.config(text="⚙️ Generar Flujo Unificado")
        else:
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
            
            self.btn_generar.config(text="⚙️ Generar Automatización (Playwright)")
            
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
            ignore_ssl_errors=self.config_ignore_ssl.get()
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
                    elif tipo == "accion_dom":
                        # Agrupar entradas del mismo input (fill)
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
        
        for idx, pet in enumerate(self.peticiones_capturadas):
            val_check = "☑" if pet.get("seleccionado", True) else "☐"
            if is_api:
                url_corta = pet["url"]
                if len(url_corta) > 120:
                    url_corta = url_corta[:117] + "..."
                self.tabla.insert(
                    "", 
                    "end", 
                    iid=str(idx), 
                    values=(val_check, idx, pet["metodo"], pet["status"], url_corta),
                    tags=("par" if idx % 2 == 0 else "impar",)
                )
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

        # Resaltar elemento en caliente en el navegador (si está activo en modo DOM)
        if self.capture_thread and self.capture_thread.is_alive() and "Grabador" in modo:
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
        else:
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
        if not os.path.exists(self.trace_file):
            messagebox.showinfo("Trace Viewer", f"No se encontró el archivo de traza '{self.trace_file}'. Realice una captura primero.")
            return

        try:
            self.lbl_status.config(text="Abriendo visor de trazas (Playwright)...")
            
            from playwright._impl._driver import compute_driver_executable
            driver_exec = compute_driver_executable()
            
            # Convertir ruta absoluta a barras normales para evitar errores de URL-encoding en Windows
            trace_path = os.path.abspath(self.trace_file).replace('\\', '/')
            
            if isinstance(driver_exec, (list, tuple)):
                cmd = list(driver_exec) + ["show-trace", trace_path]
            else:
                cmd = [driver_exec, "show-trace", trace_path]
            
            subprocess.Popen(
                cmd, 
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el visor de trazas: {e}")

    def abrir_configuracion(self):
        config_win = tk.Toplevel(self.root)
        config_win.title("Configuración de Captura")
        config_win.geometry("400x380")
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
        
        lbl_titulo = ttk.Label(config_win, text="⚙️ CONFIGURACIÓN", style="Header.TLabel", padding=15)
        lbl_titulo.pack(anchor="w")
        
        # Opciones Frame
        opts_frame = ttk.LabelFrame(config_win, text="Parámetros de Captura", padding=15)
        opts_frame.pack(fill="x", padx=15, pady=5)
        
        chk_ssl = ttk.Checkbutton(opts_frame, text="Ignorar errores de SSL / HTTPS", variable=self.config_ignore_ssl)
        chk_ssl.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        lbl_w = ttk.Label(opts_frame, text="Ancho Viewport (px):")
        lbl_w.grid(row=1, column=0, sticky="w", pady=5)
        entry_w = ttk.Entry(opts_frame, textvariable=self.config_width, width=10)
        entry_w.grid(row=1, column=1, sticky="w", pady=5, padx=5)
        
        lbl_h = ttk.Label(opts_frame, text="Alto Viewport (px):")
        lbl_h.grid(row=2, column=0, sticky="w", pady=5)
        entry_h = ttk.Entry(opts_frame, textvariable=self.config_height, width=10)
        entry_h.grid(row=2, column=1, sticky="w", pady=5, padx=5)
        
        # Versión e Info Frame
        ver_frame = ttk.LabelFrame(config_win, text="Información de la Aplicación", padding=15)
        ver_frame.pack(fill="x", padx=15, pady=10)
        
        lbl_ver = ttk.Label(ver_frame, text=f"Versión Actual: v{VERSION_LOCAL}", font=("Segoe UI", 10, "bold"))
        lbl_ver.pack(anchor="w", pady=(0, 5))
        
        btn_chk_update = ttk.Button(ver_frame, text="🔄 Buscar Actualizaciones", command=lambda: verificar_actualizaciones(self, manual=True))
        btn_chk_update.pack(anchor="w", pady=5)
        
        # Botón Guardar
        btn_save = ttk.Button(config_win, text="Guardar y Cerrar", style="Accent.TButton", command=config_win.destroy)
        btn_save.pack(anchor="e", padx=15, pady=15)


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
