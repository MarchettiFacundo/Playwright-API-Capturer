import sys
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import threading
import queue
import json
import glob
import subprocess
import base64
import io
from PIL import Image, ImageTk

from src.utils.helpers import (
    is_dir_writable,
    get_documents_folder,
    find_chrome_path,
    find_edge_path,
    is_port_in_use,
    obtener_ruta_recurso,
    aplicar_barra_titulo_oscura
)
from src.utils.updater import verificar_actualizaciones, VERSION_LOCAL
from src.utils.codegen_manager import (
    lanzar_playwright_codegen,
    parsear_script_codegen,
    DISPOSITIVOS_CODEGEN,
    LENGUAJES_CODEGEN
)
from src.utils.dom_enricher import enriquecer_pasos_dom
from src.capture.playwright_thread import PlaywrightCaptureThread
from src.generators.api_generator import generar_script_python, generar_script_unificado
from src.generators.dom_generator import (
    resolver_locator_playwright,
    generar_script_automatizacion_dom,
    generar_lista_selectores_json,
    generar_reporte_selectores_txt
)
from src.utils.html_parser_utils import parsear_elemento_devtools, enriquecer_accion_con_datos_html

class CapturaApp:
    def __init__(self, root, tema_inicial="superhero"):
        self.root = root
        self.tema_actual = tema_inicial
        self.root.title("Playwright API Capturer & Generator")
        self.root.geometry("1200x750")
        self.root.minsize(1000, 600)
        self.elementos_involucrados = []
        
        self.queue = queue.Queue()
        self.capture_thread = None
        self.peticiones_capturadas = []
        
        if getattr(sys, 'frozen', False):
            dir_ejecutable = os.path.dirname(sys.executable)
            if os.path.basename(dir_ejecutable).lower() == "dist":
                self.raiz_proyecto = os.path.dirname(dir_ejecutable)
            else:
                self.raiz_proyecto = dir_ejecutable
        else:
            self.raiz_proyecto = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
        if is_dir_writable(self.raiz_proyecto):
            self.output_base_dir = self.raiz_proyecto
        else:
            self.output_base_dir = os.path.join(get_documents_folder(), "Playwright API Capturer")
            os.makedirs(self.output_base_dir, exist_ok=True)
            
        self.video_dir = os.path.join(self.output_base_dir, "output_videos")
        self.trace_file = os.path.join(self.output_base_dir, "trace.zip")
        self.log_file = os.path.join(self.output_base_dir, "debug_playwright.log")
        self.archivo_config_gui = os.path.join(self.output_base_dir, "config_gui.json")
        
        self.config_width = tk.IntVar(value=1280)
        self.config_height = tk.IntVar(value=720)
        self.config_ignore_ssl = tk.BooleanVar(value=True)
        self.config_headless = tk.BooleanVar(value=False)
        self.config_record_video = tk.BooleanVar(value=True)
        self.config_record_trace = tk.BooleanVar(value=True)
        self.config_timeout = tk.IntVar(value=30)
        self.config_user_agent = tk.StringVar(value="")
        self.config_output_dir = tk.StringVar(value=self.output_base_dir)
        self.config_usar_cdp = tk.BooleanVar(value=False)
        self.config_puerto_cdp = tk.StringVar(value="9222")
        self.config_storage_state = tk.StringVar(value="")
        self.config_http_user = tk.StringVar(value="")
        self.config_http_pass = tk.StringVar(value="")
        self.config_trace_en_codigo = tk.BooleanVar(value=False)
        self.codegen_process = None
        self.grabar_teclas_activo = False
        
        # Cargar configuración persistida si existe
        self.cargar_configuracion_gui()
        
        self.configurar_estilos()
        self.crear_widgets()
        
        self.root.after(100, self.procesar_cola)
        self.root.after(2000, lambda: verificar_actualizaciones(self))

    def es_tema_oscuro(self):
        """Verifica si el tema actual pertenece a la familia de temas oscuros."""
        temas_oscuros = {"superhero", "darkly", "cyborg", "solar", "vapor"}
        return self.tema_actual.lower() in temas_oscuros

    def actualizar_colores_paleta(self):
        """Sincroniza los colores internos con los del tema activo de ttkbootstrap asegurando alto contraste."""
        try:
            c = self.root.style.colors
            self.color_bg = c.bg
            self.color_panel = c.dark if self.es_tema_oscuro() else c.light
            self.color_accent = c.primary
            self.color_accent_active = c.info
            self.color_fg = c.fg if c.fg else ("#f8fafc" if self.es_tema_oscuro() else "#0f172a")
            # Forzamos un color secundario de alto contraste legible en modo oscuro
            self.color_fg_sec = "#cbd5e1" if self.es_tema_oscuro() else "#475569"
            self.color_border = c.border
            self.color_success = c.success
            self.color_stop = c.danger
            self.color_stop_active = "#dc2626"
        except Exception:
            self.color_bg = "#0f172a"
            self.color_panel = "#1e293b"
            self.color_accent = "#6366f1"
            self.color_accent_active = "#4f46e5"
            self.color_fg = "#f8fafc"
            self.color_fg_sec = "#cbd5e1"
            self.color_border = "#334155"
            self.color_success = "#10b981"
            self.color_stop = "#ef4444"
            self.color_stop_active = "#dc2626"

    def configurar_estilos(self):
        self.actualizar_colores_paleta()
        self.style = self.root.style if hasattr(self.root, "style") else ttk.Style()
        
        # Configuración de estilos retrocompatibles con alto contraste
        self.style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"), padding=[12, 5])
        self.style.configure("Stop.TButton", font=("Segoe UI", 9, "bold"), padding=[12, 5])
        self.style.configure("Header.TLabel", foreground=self.color_fg, font=("Segoe UI", 11, "bold"))
        self.style.configure("Status.TLabel", foreground=self.color_fg_sec, font=("Segoe UI", 9, "italic"))
        
        # Altura de filas de tabla generosa para evitar sensación de filas pegadas
        self.style.configure("Treeview", 
                              rowheight=34,
                              font=("Segoe UI", 9))
        self.style.configure("Treeview.Heading", 
                              font=("Segoe UI", 9, "bold"),
                              padding=[0, 8])
                              
        self.style.configure("TNotebook.Tab", 
                              font=("Segoe UI", 9, "bold"), 
                              padding=[14, 6])

    def aplicar_tema(self, nuevo_tema):
        """Aplica un nuevo tema visual en caliente a toda la aplicación."""
        self.tema_actual = nuevo_tema
        try:
            self.root.style.theme_use(nuevo_tema)
        except Exception as ex:
            print(f"[WARN] No se pudo cambiar el tema a {nuevo_tema}: {ex}")
            return
            
        self.actualizar_colores_paleta()
        aplicar_barra_titulo_oscura(self.root, oscuro=self.es_tema_oscuro())
        
        # Mantener dimensiones de fila y encabezados tras el cambio de tema
        self.style.configure("Treeview", rowheight=34, font=("Segoe UI", 9))
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), padding=[0, 8])
        self.style.configure("Status.TLabel", foreground=self.color_fg_sec, font=("Segoe UI", 9, "italic"))
        self.style.configure("Header.TLabel", foreground=self.color_fg, font=("Segoe UI", 11, "bold"))
        
        # Actualizar tags de las tablas
        try:
            if hasattr(self, "tabla"):
                self.tabla.tag_configure("par", background=self.color_panel)
                self.tabla.tag_configure("impar", background=self.color_bg)
            if hasattr(self, "tabla_elementos"):
                self.tabla_elementos.tag_configure("par", background=self.color_panel)
                self.tabla_elementos.tag_configure("impar", background=self.color_bg)
                self.tabla_elementos.tag_configure("elem_estandar", foreground=self.color_fg)
            if hasattr(self, "tabla_ancestros"):
                self.tabla_ancestros.tag_configure("par", background=self.color_panel)
                self.tabla_ancestros.tag_configure("impar", background=self.color_bg)
        except Exception:
            pass
            
        # Actualizar cajas de texto
        for attr in ["txt_headers", "txt_payload", "txt_response"]:
            txt = getattr(self, attr, None)
            if txt:
                try:
                    txt.configure(bg=self.color_bg, fg=self.color_fg, insertbackground=self.color_accent)
                except Exception:
                    pass
                    
        self.guardar_configuracion_gui()

    def cargar_configuracion_gui(self):
        """Carga la configuración persistida desde disco si existe."""
        if not hasattr(self, "archivo_config_gui") or not os.path.exists(self.archivo_config_gui):
            return
        try:
            with open(self.archivo_config_gui, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "tema" in cfg:
                self.tema_actual = cfg["tema"]
            if "width" in cfg:
                self.config_width.set(int(cfg["width"]))
            if "height" in cfg:
                self.config_height.set(int(cfg["height"]))
            if "ignore_ssl" in cfg:
                self.config_ignore_ssl.set(bool(cfg["ignore_ssl"]))
            if "headless" in cfg:
                self.config_headless.set(bool(cfg["headless"]))
            if "record_video" in cfg:
                self.config_record_video.set(bool(cfg["record_video"]))
            if "record_trace" in cfg:
                self.config_record_trace.set(bool(cfg["record_trace"]))
            if "timeout" in cfg:
                self.config_timeout.set(int(cfg["timeout"]))
            if "output_dir" in cfg and os.path.exists(cfg["output_dir"]):
                self.config_output_dir.set(cfg["output_dir"])
            if "storage_state" in cfg:
                self.config_storage_state.set(cfg["storage_state"])
            if "user_agent" in cfg:
                self.config_user_agent.set(cfg["user_agent"])
            if "usar_cdp" in cfg:
                self.config_usar_cdp.set(bool(cfg["usar_cdp"]))
            if "puerto_cdp" in cfg:
                self.config_puerto_cdp.set(str(cfg["puerto_cdp"]))
            if "http_user" in cfg:
                self.config_http_user.set(str(cfg["http_user"]))
            if "http_pass" in cfg:
                self.config_http_pass.set(str(cfg["http_pass"]))
        except Exception as ex:
            print(f"[WARN] Error al cargar config_gui.json: {ex}")

    def guardar_configuracion_gui(self):
        """Guarda la configuración actual en disco."""
        try:
            datos = {
                "tema": getattr(self, "tema_actual", "superhero"),
                "width": self.config_width.get(),
                "height": self.config_height.get(),
                "ignore_ssl": self.config_ignore_ssl.get(),
                "headless": self.config_headless.get(),
                "record_video": self.config_record_video.get(),
                "record_trace": self.config_record_trace.get(),
                "timeout": self.config_timeout.get(),
                "output_dir": self.config_output_dir.get(),
                "storage_state": self.config_storage_state.get(),
                "user_agent": self.config_user_agent.get(),
                "usar_cdp": self.config_usar_cdp.get(),
                "puerto_cdp": self.config_puerto_cdp.get(),
                "http_user": self.config_http_user.get(),
                "http_pass": self.config_http_pass.get()
            }
            os.makedirs(os.path.dirname(self.archivo_config_gui), exist_ok=True)
            with open(self.archivo_config_gui, "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=4, ensure_ascii=False)
        except Exception as ex:
            print(f"[WARN] Error al guardar config_gui.json: {ex}")

    def crear_widgets(self):
        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(1, weight=2)
        self.root.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(self.root, style="TFrame", padding=10)
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)
        
        control_frame = ttk.Frame(left_panel, style="TFrame")
        control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        control_frame.columnconfigure(5, weight=1)
        
        lbl_modo = ttk.Label(control_frame, text="Modo:", style="TLabel")
        lbl_modo.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")
        
        self.combo_modo = ttk.Combobox(control_frame, values=["APIs de Red (HTTP)", "Grabador DOM (Acciones)"], state="readonly", width=24, font=("Segoe UI", 9))
        self.combo_modo.set("APIs de Red (HTTP)")
        self.combo_modo.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.combo_modo.bind("<<ComboboxSelected>>", self.on_cambio_modo)
        
        self.lbl_browser = ttk.Label(control_frame, text="Navegador:", style="TLabel")
        self.lbl_browser.grid(row=0, column=2, padx=(10, 5), pady=2, sticky="w")
        
        self.combo_navegador = ttk.Combobox(control_frame, values=["Chromium", "Firefox", "WebKit", "Edge"], state="readonly", width=10, font=("Segoe UI", 9))
        self.combo_navegador.set("Chromium")
        self.combo_navegador.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        
        lbl_url = ttk.Label(control_frame, text="URL Objetivo:", style="TLabel")
        lbl_url.grid(row=0, column=4, padx=(10, 5), pady=2, sticky="w")
        
        self.entry_url = ttk.Entry(control_frame, font=("Segoe UI", 10))
        self.entry_url.grid(row=0, column=5, padx=5, pady=2, sticky="ew")
        
        self.chk_cdp = tb.Checkbutton(
            control_frame, 
            text="Conectar a navegador abierto (CDP)", 
            variable=self.config_usar_cdp,
            command=self.on_toggle_cdp,
            bootstyle="success-round-toggle"
        )
        self.chk_cdp.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        
        self.lbl_puerto_cdp = ttk.Label(control_frame, text="Puerto CDP:", style="TLabel")
        self.lbl_puerto_cdp.grid(row=1, column=2, padx=(10, 5), pady=5, sticky="w")
        
        self.entry_puerto_cdp = ttk.Entry(control_frame, textvariable=self.config_puerto_cdp, width=8, font=("Segoe UI", 9))
        self.entry_puerto_cdp.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        self.entry_puerto_cdp.state(["disabled"])
        
        self.btn_ayuda_cdp = tb.Button(
            control_frame, 
            text="❓ Ayuda", 
            width=8,
            command=self.mostrar_ayuda_cdp,
            bootstyle="secondary"
        )
        self.btn_ayuda_cdp.grid(row=1, column=4, padx=5, pady=5, sticky="w")
        
        self.btn_lanzar_cdp = tb.Button(
            control_frame, 
            text="🚀 Auto-Lanzar", 
            command=self.lanzar_navegador_cdp_gui,
            bootstyle="info-outline"
        )
        self.btn_lanzar_cdp.grid(row=1, column=5, padx=5, pady=5, sticky="w")
        self.btn_lanzar_cdp.state(["disabled"])
        
        buttons_subframe = ttk.Frame(control_frame, style="TFrame")
        buttons_subframe.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        
        self.btn_start = tb.Button(buttons_subframe, text="⚡ Iniciar Captura", bootstyle="success", command=self.iniciar_captura)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 5))
        
        self.btn_pause = tb.Button(buttons_subframe, text="⏸️ Pausar", bootstyle="secondary-outline", command=self.toggle_pause)
        self.btn_pause.pack(side=tk.LEFT, padx=5)
        self.btn_pause.state(["disabled"])
        
        self.btn_stop = tb.Button(buttons_subframe, text="🛑 Detener Captura", bootstyle="danger", command=self.detener_captura)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        self.btn_stop.state(["disabled"])
        
        self.btn_toggle_teclas = tb.Button(
            buttons_subframe, 
            text="⌨️ Atajos: OFF", 
            bootstyle="secondary-outline", 
            command=self.toggle_grabar_teclas
        )
        self.btn_toggle_teclas.pack(side=tk.LEFT, padx=5)
        self.btn_toggle_teclas.state(["disabled"])

        self.btn_inspector = tb.Button(buttons_subframe, text="🔍 Inspector", bootstyle="info-outline", command=self.abrir_inspector_playwright)
        self.btn_inspector.pack(side=tk.LEFT, padx=5)
        self.btn_inspector.state(["disabled"])
        
        self.btn_config = tb.Button(buttons_subframe, text="⚙️ Configuración", bootstyle="secondary", command=self.abrir_configuracion)
        self.btn_config.pack(side=tk.RIGHT, padx=(5, 0))

        table_frame = ttk.Frame(left_panel, style="TFrame")
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.notebook_izq = ttk.Notebook(table_frame)
        self.notebook_izq.grid(row=0, column=0, sticky="nsew")

        # ----------------------------------------------------
        # PESTAÑA 1: SECUENCIA DE ACCIONES
        # ----------------------------------------------------
        self.frame_tab_acciones = ttk.Frame(self.notebook_izq, style="TFrame")
        self.notebook_izq.add(self.frame_tab_acciones, text="📋 Acciones")
        self.frame_tab_acciones.columnconfigure(0, weight=1)
        self.frame_tab_acciones.rowconfigure(1, weight=1)

        sel_control_frame = ttk.Frame(self.frame_tab_acciones, style="TFrame")
        sel_control_frame.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        
        btn_sel_all = tb.Button(sel_control_frame, text="☑ Marcar Todos", width=16, command=self.seleccionar_todos, bootstyle="secondary")
        btn_sel_all.grid(row=0, column=0, padx=(0, 5))
        
        btn_desel_all = tb.Button(sel_control_frame, text="☐ Desmarcar Todos", width=18, command=self.deseleccionar_todos, bootstyle="secondary")
        btn_desel_all.grid(row=0, column=1, padx=5)

        self.btn_importar_codegen = tb.Button(sel_control_frame, text="📥 Importar Codegen", width=18, command=self.importar_script_codegen, bootstyle="secondary")
        self.btn_importar_codegen.grid(row=0, column=2, padx=5)
        self.btn_importar_codegen.grid_remove()

        self.btn_enriquecer_dom = tb.Button(sel_control_frame, text="⚡ Auto-Enriquecer DOM", width=20, command=self.iniciar_enriquecimiento_dom, bootstyle="info")
        self.btn_enriquecer_dom.grid(row=0, column=3, padx=5)
        self.btn_enriquecer_dom.grid_remove()

        self.btn_guia_generadores = tb.Button(sel_control_frame, text="💡 ¿Qué generador usar?", command=self.mostrar_guia_comparativa, bootstyle="secondary")
        self.btn_guia_generadores.grid(row=0, column=4, padx=5)

        scrollbar_y = tb.Scrollbar(self.frame_tab_acciones, orient="vertical", bootstyle="round")
        scrollbar_y.grid(row=1, column=1, sticky="ns")
        
        scrollbar_x = tb.Scrollbar(self.frame_tab_acciones, orient="horizontal", bootstyle="round")
        scrollbar_x.grid(row=2, column=0, sticky="ew")

        self.tabla = ttk.Treeview(
            self.frame_tab_acciones, 
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
        
        self.tabla.column("sel", width=50, anchor="center", stretch=False)
        self.tabla.column("idx", width=45, anchor="center", stretch=False)
        self.tabla.column("metodo", width=85, anchor="center", stretch=False)
        self.tabla.column("status", width=65, anchor="center", stretch=False)
        self.tabla.column("url", width=400, anchor="w")
        
        self.tabla.bind("<<TreeviewSelect>>", self.on_peticion_seleccionada)
        self.tabla.bind("<Double-1>", self.on_tabla_double_click)
        self.tabla.bind("<space>", self.on_tabla_space)
        self.tabla.bind("<Button-3>", self.mostrar_menu_contextual)

        self.tabla.tag_configure("par", background=self.color_panel)
        self.tabla.tag_configure("impar", background=self.color_bg)

        # ----------------------------------------------------
        # PESTAÑA 2: ELEMENTOS INVOLUCRADOS (CATÁLOGO DOM)
        # ----------------------------------------------------
        self.frame_tab_elementos = ttk.Frame(self.notebook_izq, style="TFrame")
        self.notebook_izq.add(self.frame_tab_elementos, text="🧩 Elementos Involucrados")
        self.frame_tab_elementos.columnconfigure(0, weight=1)
        self.frame_tab_elementos.rowconfigure(1, weight=1)

        elem_control_frame = ttk.Frame(self.frame_tab_elementos, style="TFrame")
        elem_control_frame.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        self.btn_cargar_html_elem = tb.Button(
            elem_control_frame, 
            text="📥 Cargar HTML DevTools", 
            command=self.cargar_html_elemento_seleccionado,
            bootstyle="secondary"
        )
        self.btn_cargar_html_elem.grid(row=0, column=0, padx=(0, 5))

        self.btn_cambiar_selector_elem = tb.Button(
            elem_control_frame, 
            text="🎯 Elegir Selector", 
            command=self.elegir_selector_elemento_seleccionado,
            bootstyle="primary"
        )
        self.btn_cambiar_selector_elem.grid(row=0, column=1, padx=5)

        self.btn_copiar_selector_elem = tb.Button(
            elem_control_frame, 
            text="📋 Copiar Selector", 
            command=self.copiar_selector_elemento_seleccionado,
            bootstyle="secondary"
        )
        self.btn_copiar_selector_elem.grid(row=0, column=2, padx=5)

        self.btn_sincronizar_elem = tb.Button(
            elem_control_frame, 
            text="🔄 Sincronizar", 
            command=self.sincronizar_y_actualizar_elementos,
            bootstyle="info"
        )
        self.btn_sincronizar_elem.grid(row=0, column=3, padx=5)

        scr_elem_y = tb.Scrollbar(self.frame_tab_elementos, orient="vertical", bootstyle="round")
        scr_elem_y.grid(row=1, column=1, sticky="ns")
        
        scr_elem_x = tb.Scrollbar(self.frame_tab_elementos, orient="horizontal", bootstyle="round")
        scr_elem_x.grid(row=2, column=0, sticky="ew")

        self.tabla_elementos = ttk.Treeview(
            self.frame_tab_elementos,
            columns=("idx", "nombre", "tag_rol", "selector", "pasos", "estado"),
            show="headings",
            yscrollcommand=scr_elem_y.set,
            xscrollcommand=scr_elem_x.set,
            selectmode="browse"
        )
        self.tabla_elementos.grid(row=1, column=0, sticky="nsew")
        scr_elem_y.config(command=self.tabla_elementos.yview)
        scr_elem_x.config(command=self.tabla_elementos.xview)

        self.tabla_elementos.heading("idx", text="#")
        self.tabla_elementos.heading("nombre", text="Elemento")
        self.tabla_elementos.heading("tag_rol", text="Tag / Rol")
        self.tabla_elementos.heading("selector", text="Selector Sugerido")
        self.tabla_elementos.heading("pasos", text="Pasos")
        self.tabla_elementos.heading("estado", text="Estado HTML")

        self.tabla_elementos.column("idx", width=35, anchor="center", stretch=False)
        self.tabla_elementos.column("nombre", width=180, anchor="w")
        self.tabla_elementos.column("tag_rol", width=120, anchor="center", stretch=False)
        self.tabla_elementos.column("selector", width=250, anchor="w")
        self.tabla_elementos.column("pasos", width=90, anchor="center", stretch=False)
        self.tabla_elementos.column("estado", width=100, anchor="center", stretch=False)

        self.tabla_elementos.bind("<<TreeviewSelect>>", self.on_elemento_seleccionado)
        self.tabla_elementos.bind("<Double-1>", lambda e: self.cargar_html_elemento_seleccionado())
        self.tabla_elementos.bind("<Button-3>", self.mostrar_menu_elementos)

        self.tabla_elementos.tag_configure("par", background=self.color_panel)
        self.tabla_elementos.tag_configure("impar", background=self.color_bg)
        self.tabla_elementos.tag_configure("elem_devtools", foreground="#34d399", font=("Segoe UI", 9, "bold"))
        self.tabla_elementos.tag_configure("elem_estandar", foreground=self.color_fg)

        # Ocultar inicialmente pestaña de elementos (modo inicial es APIs)
        try:
            self.notebook_izq.hide(self.frame_tab_elementos)
        except Exception:
            pass

        bottom_frame = ttk.Frame(left_panel, style="TFrame")
        bottom_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        bottom_frame.columnconfigure(2, weight=1)
        
        self.btn_generar = tb.Button(
            bottom_frame, 
            text="⚙️ Generar Flujo Unificado", 
            bootstyle="primary", 
            command=self.generar_codigo_flujo
        )
        self.btn_generar.grid(row=0, column=0, padx=(0, 10), sticky="w")
        
        self.var_parametrizar = tk.BooleanVar(value=True)
        self.chk_parametrizar = tb.Checkbutton(
            bottom_frame,
            text="🔒 Parametrizar Secretos",
            variable=self.var_parametrizar,
            bootstyle="info-round-toggle"
        )
        self.chk_parametrizar.grid(row=0, column=1, padx=5, sticky="w")
        
        self.lbl_status = ttk.Label(
            bottom_frame, 
            text="Listo. Ingrese la URL y pulse 'Iniciar Captura'.", 
            style="Status.TLabel"
        )
        self.lbl_status.grid(row=0, column=2, padx=(10, 0), sticky="w")

        right_panel = ttk.Frame(self.root, style="Panel.TFrame", padding=10)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        media_frame = ttk.Frame(right_panel, style="Panel.TFrame")
        media_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        media_frame.columnconfigure(0, weight=1)
        media_frame.columnconfigure(1, weight=1)
        media_frame.columnconfigure(2, weight=1)
        self.btn_video = tb.Button(media_frame, text="🎬 Reproducir Video", command=self.reproducir_video, bootstyle="info")
        self.btn_video.grid(row=0, column=0, padx=(0, 3), sticky="ew")
        
        self.btn_trace = tb.Button(media_frame, text="🔍 Ver Trace", command=self.abrir_trace, bootstyle="primary")
        self.btn_trace.grid(row=0, column=1, padx=3, sticky="ew")

        self.btn_codegen = tb.Button(media_frame, text="⚡ Codegen", command=self.abrir_dialogo_codegen, bootstyle="secondary")
        self.btn_codegen.grid(row=0, column=2, padx=(3, 0), sticky="ew")

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

        self.frame_arbol_json = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.frame_arbol_json, text="🌳 Árbol JSON")
        self.frame_arbol_json.columnconfigure(0, weight=1)
        self.frame_arbol_json.rowconfigure(0, weight=1)
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

        self.notebook.hide(self.frame_arbol_json)

        # Pestaña de Ancestros (elementos superiores)
        self.frame_ancestros = ttk.Frame(self.notebook, style="Panel.TFrame", padding=6)
        self.notebook.add(self.frame_ancestros, text="🌳 Ancestros")
        self.frame_ancestros.columnconfigure(0, weight=1)
        self.frame_ancestros.rowconfigure(0, weight=1)

        ancestros_cols = ("relacion", "tag_desc", "selector", "xpath")
        self.tabla_ancestros = ttk.Treeview(
            self.frame_ancestros, 
            columns=ancestros_cols,
            show="headings", 
            height=8
        )
        self.tabla_ancestros.heading("relacion", text="Relación")
        self.tabla_ancestros.heading("tag_desc", text="Elemento")
        self.tabla_ancestros.heading("selector", text="Selector Sugerido")
        self.tabla_ancestros.heading("xpath", text="XPath")
        
        self.tabla_ancestros.column("relacion", width=120, anchor="center", stretch=False)
        self.tabla_ancestros.column("tag_desc", width=180, anchor="w", stretch=True)
        self.tabla_ancestros.column("selector", width=220, anchor="w", stretch=True)
        self.tabla_ancestros.column("xpath", width=200, anchor="w", stretch=True)

        # Configurar tags de estilos visuales
        self.tabla_ancestros.tag_configure("objetivo", foreground="#818cf8", font=("Segoe UI", 9, "bold"))
        self.tabla_ancestros.tag_configure("padre", foreground="#e2e8f0")
        self.tabla_ancestros.tag_configure("par", background=self.color_panel)
        self.tabla_ancestros.tag_configure("impar", background=self.color_bg)

        scr_anc_y = ttk.Scrollbar(self.frame_ancestros, orient="vertical", command=self.tabla_ancestros.yview)
        scr_anc_x = ttk.Scrollbar(self.frame_ancestros, orient="horizontal", command=self.tabla_ancestros.xview)
        self.tabla_ancestros.configure(yscrollcommand=scr_anc_y.set, xscrollcommand=scr_anc_x.set)
        
        self.tabla_ancestros.grid(row=0, column=0, sticky="nsew")
        scr_anc_y.grid(row=0, column=1, sticky="ns")
        scr_anc_x.grid(row=1, column=0, sticky="ew")

        self.tabla_ancestros.bind("<Double-1>", self.on_ancestro_double_click)
        self.tabla_ancestros.bind("<Button-3>", self.mostrar_menu_ancestros)

        self.notebook.hide(self.frame_ancestros)

    def on_toggle_cdp(self):
        if self.config_usar_cdp.get():
            self.entry_puerto_cdp.state(["!disabled"])
            self.combo_navegador.state(["disabled"])
            if hasattr(self, "btn_lanzar_cdp"):
                self.btn_lanzar_cdp.state(["!disabled"])
        else:
            self.entry_puerto_cdp.state(["disabled"])
            self.combo_navegador.state(["!disabled"])
            if hasattr(self, "btn_lanzar_cdp"):
                self.btn_lanzar_cdp.state(["disabled"])

    def lanzar_navegador_cdp_gui(self):
        puerto_str = self.config_puerto_cdp.get().strip()
        try:
            puerto = int(puerto_str)
        except ValueError:
            messagebox.showerror("Error de Puerto", "El puerto configurado debe ser un número válido.")
            return

        if is_port_in_use(puerto):
            res_con = messagebox.askyesno(
                "Puerto en Uso",
                f"El puerto {puerto} ya está en uso por otra aplicación o navegador.\n\n"
                "¿Desea omitir el lanzamiento e intentar conectar directamente al navegador ya abierto?"
            )
            if res_con:
                self.config_usar_cdp.set(True)
                self.on_toggle_cdp()
                self.lbl_status.config(text=f"Conectado a puerto {puerto}. Listo para iniciar captura.")
            return

        select_win = tk.Toplevel(self.root)
        select_win.title("Seleccionar Navegador")
        select_win.geometry("400x180")
        select_win.resizable(False, False)
        select_win.configure(bg=self.color_bg)
        select_win.transient(self.root)
        select_win.grab_set()

        select_win.update_idletasks()
        w = select_win.winfo_width()
        h = select_win.winfo_height()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        select_win.geometry(f"+{x}+{y}")

        lbl_info = tk.Label(
            select_win,
            text="Elija el navegador que desea abrir en modo depuración (CDP):",
            fg=self.color_fg,
            bg=self.color_bg,
            font=("Segoe UI", 10),
            wraplength=360,
            justify="left"
        )
        lbl_info.pack(pady=(20, 10), padx=20, anchor="w")

        combo_val = tk.StringVar(value="Google Chrome")
        combo_browser = ttk.Combobox(
            select_win,
            textvariable=combo_val,
            values=["Google Chrome", "Microsoft Edge"],
            state="readonly",
            font=("Segoe UI", 10)
        )
        combo_browser.pack(pady=10, padx=20, fill="x")

        def confirmar_lanzamiento():
            nav_elegido = combo_val.get()
            select_win.destroy()
            self.ejecutar_lanzamiento_cdp(nav_elegido, puerto)

        btn_confirmar = ttk.Button(
            select_win,
            text="🚀 Lanzar Navegador",
            style="Accent.TButton",
            command=confirmar_lanzamiento
        )
        btn_confirmar.pack(pady=(10, 20), padx=20, anchor="e")

    def ejecutar_lanzamiento_cdp(self, navegador, puerto):
        if navegador == "Google Chrome":
            path = find_chrome_path()
            nombre_corto = "Google Chrome"
            key_name = "chrome"
        else:
            path = find_edge_path()
            nombre_corto = "Microsoft Edge"
            key_name = "edge"

        if not path:
            messagebox.showerror(
                "Navegador no encontrado",
                f"No se pudo localizar el ejecutable de {nombre_corto} en el equipo.\n\n"
                "Por favor, instale el navegador o levántelo de forma manual con los parámetros indicados en el botón de ayuda."
            )
            return

        user_data_dir = os.path.join(self.output_base_dir, f"perfil_cdp_{key_name}")
        try:
            os.makedirs(user_data_dir, exist_ok=True)
        except Exception:
            import tempfile
            user_data_dir = os.path.join(tempfile.gettempdir(), f"playwright_cdp_profile_{key_name}")
            os.makedirs(user_data_dir, exist_ok=True)

        cmd = [
            path,
            f"--remote-debugging-port={puerto}",
            f"--user-data-dir={user_data_dir}"
        ]

        try:
            self.lbl_status.config(text=f"Lanzando {nombre_corto} en puerto {puerto}...")
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            def verificar_escucha(reintentos=10):
                if is_port_in_use(puerto):
                    self.config_usar_cdp.set(True)
                    self.on_toggle_cdp()
                    self.lbl_status.config(text=f"{nombre_corto} lanzado y conectado con éxito en el puerto {puerto}.")
                    messagebox.showinfo(
                        "Navegador Iniciado",
                        f"¡{nombre_corto} se inició correctamente en el puerto {puerto}!\n\n"
                        "Puedes realizar tus acciones en el navegador y luego pulsar '⚡ Iniciar Captura' en la aplicación."
                    )
                elif reintentos > 0:
                    self.root.after(500, lambda: verificar_escucha(reintentos - 1))
                else:
                    self.lbl_status.config(text=f"No se pudo confirmar la escucha en el puerto {puerto}.")
                    messagebox.showwarning(
                        "Advertencia",
                        f"{nombre_corto} fue ejecutado, pero no pudimos confirmar la conexión en el puerto {puerto}.\n\n"
                        "Comprueba si había instancias anteriores del navegador abiertas y ciérralas antes de reintentar."
                    )

            self.root.after(500, lambda: verificar_escucha())

        except Exception as e:
            messagebox.showerror(
                "Error al Iniciar",
                f"No se pudo ejecutar el navegador automáticamente:\n{e}"
            )
            self.lbl_status.config(text="Error al auto-lanzar navegador.")

    def mostrar_ayuda_cdp(self):
        instrucciones = (
            "Para capturar tráfico desde un navegador abierto manualmente:\n\n"
            "1. Cierra todas las ventanas del navegador que vayas a usar (Edge o Chrome).\n"
            "2. Abre la consola de comandos de Windows (cmd) o presiona la combinación Win + R y ejecuta uno de los siguientes comandos:\n\n"
            "   • Para Microsoft Edge:\n"
            "     msedge.exe --remote-debugging-port=9222 --user-data-dir=\"C:\\temp\\perfil_cdp\"\n\n"
            "   • Para Google Chrome:\n"
            "     chrome.exe --remote-debugging-port=9222 --user-data-dir=\"C:\\temp\\perfil_cdp\"\n\n"
            "3. En la ventana del navegador que se abra, navega al sitio que desees e inicia sesión si es necesario.\n"
            "4. Asegúrate de que el puerto CDP configurado aquí coincida (por defecto 9222).\n"
            "5. Activa la casilla 'Conectar a navegador abierto (CDP)' en esta aplicación y presiona '⚡ Iniciar Captura'."
        )
        messagebox.showinfo("¿Cómo usar la conexión CDP?", instrucciones)

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
            try:
                self.notebook.add(self.frame_arbol_json)
                self.notebook.tab(self.frame_arbol_json, text="🌳 Árbol JSON")
            except Exception:
                pass
            try:
                self.notebook.hide(self.frame_ancestros)
            except Exception:
                pass
            if hasattr(self, "notebook_izq") and hasattr(self, "frame_tab_elementos"):
                try:
                    self.notebook_izq.hide(self.frame_tab_elementos)
                except Exception:
                    pass

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
            try:
                self.notebook.hide(self.frame_arbol_json)
            except Exception:
                pass
            try:
                self.notebook.add(self.frame_ancestros)
                self.notebook.tab(self.frame_ancestros, text="🌳 Ancestros")
            except Exception:
                pass
            if hasattr(self, "notebook_izq") and hasattr(self, "frame_tab_elementos"):
                try:
                    self.notebook_izq.add(self.frame_tab_elementos, text="🧩 Elementos Involucrados")
                    self.sincronizar_y_actualizar_elementos()
                except Exception:
                    pass

            self.btn_generar.config(text="⚙️ Generar Automatización (Playwright)")

        if hasattr(self, "btn_importar_codegen"):
            if "Grabador" in modo:
                self.btn_importar_codegen.grid()
                if hasattr(self, "btn_enriquecer_dom"):
                    self.btn_enriquecer_dom.grid()
            else:
                self.btn_importar_codegen.grid_remove()
                if hasattr(self, "btn_enriquecer_dom"):
                    self.btn_enriquecer_dom.grid_remove()

        self.peticiones_capturadas.clear()
        self.elementos_involucrados.clear()
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        if hasattr(self, "tabla_elementos"):
            for item in self.tabla_elementos.get_children():
                self.tabla_elementos.delete(item)
        self.limpiar_detalles()

    def iniciar_captura(self):
        url = self.entry_url.get().strip()
        if not url and not self.config_usar_cdp.get():
            messagebox.showerror("Error", "Debe ingresar una URL válida.")
            return

        self.peticiones_capturadas.clear()
        for item in self.tabla.get_children():
            self.tabla.delete(item)

        self.btn_start.state(["disabled"])
        self.entry_url.state(["disabled"])
        self.combo_modo.state(["disabled"])
        self.combo_navegador.state(["disabled"])
        self.chk_cdp.state(["disabled"])
        self.entry_puerto_cdp.state(["disabled"])
        if hasattr(self, "btn_lanzar_cdp"):
            self.btn_lanzar_cdp.state(["disabled"])
        self.btn_pause.state(["!disabled"])
        self.btn_pause.config(text="⏸️ Pausar")
        self.btn_stop.state(["!disabled"])
        self.btn_inspector.state(["!disabled"])
        if hasattr(self, "btn_toggle_teclas"):
            self.btn_toggle_teclas.state(["!disabled"])
        self.grabar_teclas_activo = False
        self.actualizar_ui_toggle_teclas(False)

        base_dir = self.config_output_dir.get().strip()
        if not base_dir:
            base_dir = self.output_base_dir
        self.video_dir = os.path.join(base_dir, "output_videos")
        self.trace_file = os.path.join(base_dir, "trace.zip")
        self.log_file = os.path.join(base_dir, "debug_playwright.log")

        puerto_cdp_val = 9222
        try:
            puerto_cdp_val = int(self.config_puerto_cdp.get().strip())
        except Exception:
            pass

        st_state = self.config_storage_state.get().strip()
        if not st_state or not os.path.exists(st_state):
            st_state = None

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
            user_agent=self.config_user_agent.get(),
            usar_cdp=self.config_usar_cdp.get(),
            puerto_cdp=puerto_cdp_val,
            storage_state=st_state,
            http_user=self.config_http_user.get().strip(),
            http_password=self.config_http_pass.get().strip()
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
            self.btn_inspector.state(["disabled"])
            if hasattr(self, "btn_toggle_teclas"):
                self.btn_toggle_teclas.state(["disabled"])

    def toggle_grabar_teclas(self):
        self.grabar_teclas_activo = not getattr(self, "grabar_teclas_activo", False)
        self.actualizar_ui_toggle_teclas(self.grabar_teclas_activo)
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.input_queue.put(("toggle_teclas", self.grabar_teclas_activo))

    def actualizar_ui_toggle_teclas(self, activo):
        self.grabar_teclas_activo = bool(activo)
        if hasattr(self, "btn_toggle_teclas"):
            if self.grabar_teclas_activo:
                self.btn_toggle_teclas.config(
                    text="⌨️ Atajos: ON",
                    bootstyle="success"
                )
                self.lbl_status.config(text="Grabación de atajos ACTIVADA (Shift+F4, F8, etc.).")
            else:
                self.btn_toggle_teclas.config(
                    text="⌨️ Atajos: OFF",
                    bootstyle="secondary-outline"
                )
                self.lbl_status.config(text="Grabación de atajos en PAUSA.")

    def descargar_e_instalar_navegadores(self, navegador="Chromium"):
        mapa_navegador = {
            "Chromium": "chromium",
            "Firefox": "firefox",
            "WebKit": "webkit",
            "Edge": "chromium",
        }
        nav_id = mapa_navegador.get(navegador, "chromium")

        install_win = tk.Toplevel(self.root)
        install_win.title("Instalando Navegador...")
        install_win.geometry("500x230")
        install_win.resizable(False, False)
        install_win.configure(bg=self.color_bg)
        install_win.transient(self.root)
        install_win.grab_set()
        install_win.protocol("WM_DELETE_WINDOW", lambda: None)

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

    def procesar_cola(self):
        try:
            while not self.queue.empty():
                try:
                    tipo, dato = self.queue.get_nowait()
                except queue.Empty:
                    break
                except Exception as get_err:
                    break
                
                try:
                    if tipo == "status":
                        self.lbl_status.config(text=dato)
                    elif tipo == "error":
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
                    elif tipo == "accion_dom":
                        idx = len(self.peticiones_capturadas) - 1
                        if (idx >= 0 and dato["tipo_accion"] == "fill" and
                                self.peticiones_capturadas[idx].get("tipo_accion") == "fill" and
                                self.peticiones_capturadas[idx].get("selector_sugerido") == dato["selector_sugerido"]):

                            self.peticiones_capturadas[idx]["valor"] = dato["valor"]
                            self.peticiones_capturadas[idx]["outerHTML"] = dato["outerHTML"]
                            if "ancestros" in dato:
                                self.peticiones_capturadas[idx]["ancestros"] = dato["ancestros"]

                            item_id = str(idx)
                            if self.tabla.exists(item_id):
                                tipo_map = {
                                    "click": "Click 🖱️",
                                    "fill": "Escribir ⌨️",
                                    "select": "Seleccionar 📋",
                                    "navigation": "Ir a URL 🌐",
                                    "extract": "Extraer Texto 🔍",
                                    "upload": "Subir Archivo 📤",
                                    "file_upload": "Subir Archivo 📤",
                                    "download": "Descargar Archivo 📥"
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
                                "change": "Seleccionar 📋",
                                "navigation": "Ir a URL 🌐",
                                "extract": "Extraer Texto 🔍",
                                "assert_visible": "Validar Visible 👁️",
                                "assert_text": "Validar Texto 🔤",
                                "key": "Presionar Tecla ⌨️",
                                "upload": "Subir Archivo 📤",
                                "file_upload": "Subir Archivo 📤",
                                "download": "Descargar Archivo 📥"
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
                    elif tipo == "toggle_teclas_estado":
                        self.actualizar_ui_toggle_teclas(dato)
                    elif tipo == "finalizado":
                        self.btn_start.state(["!disabled"])
                        self.entry_url.state(["!disabled"])
                        self.combo_modo.state(["!disabled"])
                        self.chk_cdp.state(["!disabled"])
                        self.on_toggle_cdp()
                        self.btn_stop.state(["disabled"])
                        self.btn_pause.state(["disabled"])
                        self.btn_inspector.state(["disabled"])
                        if hasattr(self, "btn_toggle_teclas"):
                            self.btn_toggle_teclas.state(["disabled"])
                        self.capture_thread = None
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self.root.after(100, self.procesar_cola)

    def actualizar_tabla_completa(self):
        seleccionada = self.tabla.selection()
        selected_idx = seleccionada[0] if seleccionada else None

        for item in self.tabla.get_children():
            self.tabla.delete(item)

        modo = self.combo_modo.get()
        is_api = "APIs" in modo

        for idx, pet in enumerate(self.peticiones_capturadas):
            val_check = "☑" if pet.get("seleccionado", True) else "☐"
            if is_api:
                url_corta = pet.get("url", "")
                if len(url_corta) > 120:
                    url_corta = url_corta[:117] + "..."
                self.tabla.insert("", "end", iid=str(idx),
                    values=(val_check, idx, pet.get("metodo", "GET"), pet.get("status", ""), url_corta),
                    tags=("par" if idx % 2 == 0 else "impar",))
            else:
                tipo_map = {
                    "click": "Click 🖱️",
                    "fill": "Escribir ⌨️",
                    "select": "Seleccionar 📋",
                    "change": "Seleccionar 📋",
                    "navigation": "Ir a URL 🌐",
                    "extract": "Extraer Texto 🔍",
                    "assert_visible": "Validar Visible 👁️",
                    "assert_text": "Validar Texto 🔤",
                    "key": "Presionar Tecla ⌨️",
                    "upload": "Subir Archivo 📤",
                    "file_upload": "Subir Archivo 📤",
                    "download": "Descargar Archivo 📥"
                }
                accion_legible = tipo_map.get(pet.get("tipo_accion"), str(pet.get("tipo_accion", "")).capitalize())
                self.tabla.insert(
                    "",
                    "end",
                    iid=str(idx),
                    values=(val_check, idx, accion_legible, pet.get("descriptor_legible", ""), pet.get("valor", "")),
                    tags=("par" if idx % 2 == 0 else "impar",)
                )
                
        if selected_idx and self.tabla.exists(selected_idx):
            self.tabla.selection_set(selected_idx)

        if "Grabador" in modo:
            self.sincronizar_y_actualizar_elementos()

    def on_peticion_seleccionada(self, event):
        seleccion = self.tabla.selection()
        if not seleccion:
            self.limpiar_detalles()
            return

        idx = int(seleccion[0])
        pet = self.peticiones_capturadas[idx]
        modo = self.combo_modo.get()

        if self.capture_thread and self.capture_thread.is_alive() and ("Grabador" in modo):
            sug = pet.get("selector_sugerido")
            if sug:
                self.capture_thread.input_queue.put(("highlight", sug))

        if "APIs" in modo:
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

            respuesta = pet.get("respuesta")
            if respuesta is not None:
                if isinstance(respuesta, (dict, list)):
                    respuesta_str = json.dumps(respuesta, indent=4, ensure_ascii=False)
                else:
                    respuesta_str = str(respuesta)
            else:
                respuesta_str = "<Sin Respuesta capturada o respuesta vacía>"
            self.actualizar_caja_texto_json(self.txt_response, respuesta_str)

            self.poblar_arbol_json(pet.get("respuesta"))
            self.limpiar_ancestros()

        else:
            atributos_info = []
            atributos_info.append("=== ATRIBUTOS DEL ELEMENTO ===")
            atributos_info.append(f"Tag Name: {pet.get('tagName', '')}")
            atributos_info.append(f"ID: {pet.get('id') or '<Ninguno>'}")
            atributos_info.append(f"Name: {pet.get('name') or '<Ninguno>'}")
            atributos_info.append(f"Class Name: {pet.get('className') or '<Ninguno>'}")
            atributos_info.append(f"Type: {pet.get('type') or '<Ninguno>'}")
            atributos_info.append(f"Placeholder: {pet.get('placeholder') or '<Ninguno>'}")
            self.actualizar_caja_texto_headers(self.txt_headers, "\n".join(atributos_info))

            selectores_info = []
            selectores_info.append("=== SELECTOR SUGERIDO (PLAYWRIGHT) ===")
            sug = pet.get("selector_sugerido", "")
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

            html_raw = pet.get("outerHTML", "<No disponible (por ejemplo, en navegación)>")
            self.actualizar_caja_texto(self.txt_response, html_raw)
            self.actualizar_ancestros(pet)

    def limpiar_ancestros(self):
        if hasattr(self, "tabla_ancestros"):
            for item in self.tabla_ancestros.get_children():
                self.tabla_ancestros.delete(item)

    def actualizar_ancestros(self, pet):
        if hasattr(self, "tabla_ancestros"):
            for item in self.tabla_ancestros.get_children():
                self.tabla_ancestros.delete(item)

            ancestros = pet.get("ancestros", [])
            for idx, anc in enumerate(ancestros):
                tag_desc = anc.get("descriptor", "")
                xpath = anc.get("xpath", "")
                sug = anc.get("selector_sugerido", "")
                es_obj = anc.get("esObjetivo", False)

                if es_obj:
                    relacion = "🎯 Objetivo"
                    tag = "objetivo"
                elif idx == 1:
                    relacion = "Padre"
                    tag = "padre"
                else:
                    relacion = f"Ancestro (N-{idx})"
                    tag = "par" if idx % 2 == 0 else "impar"

                self.tabla_ancestros.insert(
                    "",
                    "end",
                    iid=str(idx),
                    values=(relacion, tag_desc, sug, xpath),
                    tags=(tag,)
                )

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
        idx = int(item_id)
        pet = self.peticiones_capturadas[idx]
        
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="✏️ Editar Paso", command=self.abrir_editor_paso)
        if "tipo_accion" in pet:
            menu.add_command(label="📥 Cargar HTML DevTools a este Elemento...", command=lambda: self.abrir_dialogo_cargar_html_devtools(idx))
        menu.add_command(label="❌ Eliminar Paso", command=self.eliminar_paso)
        menu.add_separator()
        
        # Submenú rápido para cambiar tipo de acción si el elemento tiene tipo_accion
        if "tipo_accion" in pet:
            menu_cambiar = tk.Menu(menu, tearoff=0)
            acciones_rapidas = [
                ("🔍 Extraer Texto (extract)", "extract"),
                ("🔤 Validar Texto (assert_text)", "assert_text"),
                ("👁️ Validar Visible (assert_visible)", "assert_visible"),
                ("🖱️ Click (click)", "click"),
                ("⌨️ Escribir (fill)", "fill"),
                ("📋 Seleccionar (select)", "select"),
                ("⌨️ Presionar Tecla (key)", "key"),
                ("📤 Subir Archivo (upload)", "upload"),
                ("📥 Descargar Archivo (download)", "download")
            ]
            for etiqueta, cod_tipo in acciones_rapidas:
                def _crear_cambio(t=cod_tipo):
                    def _accion():
                        pet["tipo_accion"] = t
                        self.actualizar_tabla_completa()
                        self.on_peticion_seleccionada(None)
                    return _accion
                menu_cambiar.add_command(label=etiqueta, command=_crear_cambio(cod_tipo))
            menu.add_cascade(label="🔄 Cambiar Acción a...", menu=menu_cambiar)
            menu.add_separator()

        menu.add_command(label="⬆️ Subir Paso", command=self.subir_paso)
        menu.add_command(label="⬇️ Bajar Paso", command=self.bajar_paso)
        
        menu.post(event.x_root, event.y_root)

    def on_ancestro_double_click(self, event):
        seleccion = self.tabla_ancestros.selection()
        if not seleccion:
            return
        item_id = seleccion[0]
        valores = self.tabla_ancestros.item(item_id, "values")
        if not valores or len(valores) < 4:
            return
        
        tag_desc = valores[1]
        selector = valores[2]
        xpath = valores[3]
        
        copiado = selector if selector and selector != "<No aplicable>" else xpath
        if copiado:
            self.root.clipboard_clear()
            self.root.clipboard_append(copiado)
            self.root.update()
            self.lbl_status.config(text=f"Copiado al portapapeles: {copiado}")

    def mostrar_menu_ancestros(self, event):
        item_id = self.tabla_ancestros.identify_row(event.y)
        if not item_id:
            return
        self.tabla_ancestros.selection_set(item_id)
        valores = self.tabla_ancestros.item(item_id, "values")
        if not valores or len(valores) < 4:
            return
        
        menu = tk.Menu(self.root, tearoff=0)
        
        def copiar_val(val, desc):
            self.root.clipboard_clear()
            self.root.clipboard_append(val)
            self.root.update()
            self.lbl_status.config(text=f"Copiado {desc}: {val}")
            
        menu.add_command(label="Copiar Selector Sugerido", command=lambda: copiar_val(valores[2], "Selector"))
        menu.add_command(label="Copiar XPath", command=lambda: copiar_val(valores[3], "XPath"))
        menu.add_command(label="Copiar Elemento", command=lambda: copiar_val(valores[1], "Elemento"))
        
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

# =========================================================================
    # GESTIÓN DEL CATÁLOGO DE ELEMENTOS INVOLUCRADOS (OBJETOS DOM)
    # =========================================================================
    def sincronizar_elementos_involucrados(self):
        """
        Analiza las acciones capturadas en self.peticiones_capturadas y consolida
        la lista de Elementos Involucrados únicos (Catálogo de Objetos DOM).
        Agrupa acciones que interactúan sobre el mismo control físico o celda lógica.
        """
        elementos_dict = {}
        orden_claves = []

        for idx, pet in enumerate(self.peticiones_capturadas):
            tipo = pet.get("tipo_accion")
            if tipo == "navigation":
                continue

            sug = pet.get("selector_sugerido", "")
            elem_id = pet.get("id", "")
            elem_elem_id = pet.get("element_id")
            
            # Buscar coordenadas de celda SAP si existen en ID o selector
            match_sap = re.search(r'\[(\d+,\d+)\]', elem_id or sug)
            
            if elem_elem_id:
                clave = elem_elem_id
            elif match_sap:
                clave = f"sap_cell_{match_sap.group(1)}"
            elif elem_id and not re.search(r'\d{6,}', elem_id):
                clave = f"id_{elem_id}"
            elif sug:
                clave = f"sel_{sug}"
            else:
                clave = f"step_{idx}"

            pet["element_id"] = clave

            if clave not in elementos_dict:
                orden_claves.append(clave)
                nombre_defecto = pet.get("descriptor_legible", f"Elemento #{len(orden_claves)}")
                if match_sap:
                    nombre_defecto = f"Celda SAP [{match_sap.group(1)}]"
                
                cands = list(pet.get("selectores_candidatos", []))
                if sug and sug not in cands:
                    cands.insert(0, sug)

                elementos_dict[clave] = {
                    "id_elemento": clave,
                    "nombre": nombre_defecto,
                    "tagName": pet.get("tagName", "ELEMENT"),
                    "role": pet.get("role", ""),
                    "selector_actual": sug,
                    "selectores_candidatos": cands,
                    "pasos_asociados": [idx],
                    "html_origen": pet.get("html_origen", "auto"),
                    "outerHTML": pet.get("outerHTML", ""),
                    "id": elem_id,
                    "name": pet.get("name", ""),
                    "className": pet.get("className", ""),
                    "sap_coord": match_sap.group(1) if match_sap else None
                }
            else:
                elem = elementos_dict[clave]
                if idx not in elem["pasos_asociados"]:
                    elem["pasos_asociados"].append(idx)
                if pet.get("html_origen") == "devtools":
                    elem["html_origen"] = "devtools"
                    elem["outerHTML"] = pet.get("outerHTML", elem["outerHTML"])
                    elem["tagName"] = pet.get("tagName", elem["tagName"])
                    elem["role"] = pet.get("role", elem["role"])
                    elem["id"] = pet.get("id", elem["id"])
                    elem["className"] = pet.get("className", elem["className"])
                    for sc in pet.get("selectores_candidatos", []):
                        if sc not in elem["selectores_candidatos"]:
                            elem["selectores_candidatos"].append(sc)

        self.elementos_involucrados = [elementos_dict[k] for k in orden_claves]

    def actualizar_tabla_elementos(self):
        """Renderiza los elementos únicos involucrados en self.tabla_elementos."""
        if not hasattr(self, "tabla_elementos"):
            return

        seleccionada = self.tabla_elementos.selection()
        selected_iid = seleccionada[0] if seleccionada else None

        for item in self.tabla_elementos.get_children():
            self.tabla_elementos.delete(item)

        for idx, elem in enumerate(self.elementos_involucrados):
            pasos_str = ", ".join(f"#{p + 1}" for p in elem.get("pasos_asociados", []))
            tag = elem.get("tagName", "").upper()
            role = elem.get("role", "")
            tag_rol = f"{tag} ({role})" if role else tag
            
            estado = "✅ DevTools" if elem.get("html_origen") == "devtools" else "⚠️ Sin HTML"
            tag_style = "elem_devtools" if elem.get("html_origen") == "devtools" else ("par" if idx % 2 == 0 else "impar")

            self.tabla_elementos.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    idx + 1,
                    elem.get("nombre", ""),
                    tag_rol,
                    elem.get("selector_actual", ""),
                    pasos_str,
                    estado
                ),
                tags=(tag_style,)
            )

        if selected_iid and self.tabla_elementos.exists(selected_iid):
            self.tabla_elementos.selection_set(selected_iid)

    def sincronizar_y_actualizar_elementos(self):
        """Sincroniza y repuebla la tabla de elementos involucrados."""
        self.sincronizar_elementos_involucrados()
        self.actualizar_tabla_elementos()

    def on_elemento_seleccionado(self, event):
        """Muestra los datos completos del elemento seleccionado en los paneles de detalle de la derecha."""
        seleccion = self.tabla_elementos.selection()
        if not seleccion:
            return
        idx = int(seleccion[0])
        if idx >= len(self.elementos_involucrados):
            return
        elem = self.elementos_involucrados[idx]

        atributos_info = [
            "=== ELEMENTO INVOLUCRADO ===",
            f"Nombre: {elem.get('nombre', '')}",
            f"Tag Name: {elem.get('tagName', '')}",
            f"Role: {elem.get('role', '<Ninguno>')}",
            f"ID: {elem.get('id', '<Ninguno>')}",
            f"Name: {elem.get('name', '<Ninguno>')}",
            f"Class: {elem.get('className', '<Ninguno>')}",
            f"Coordenadas SAP: {elem.get('sap_coord') or '<No aplica>'}",
            f"Pasos Asociados: {', '.join(f'#{p+1}' for p in elem.get('pasos_asociados', []))}",
            f"Origen: {elem.get('html_origen', 'auto')}"
        ]
        self.actualizar_caja_texto_headers(self.txt_headers, "\n".join(atributos_info))

        sel_info = [
            "=== SELECTOR PRINCIPAL ACTUAL ===",
            elem.get("selector_actual", "<Ninguno>"),
            "",
            f"=== SELECTORES CANDIDATOS DISPONIBLES ({len(elem.get('selectores_candidatos', []))}) ==="
        ]
        for i, sc in enumerate(elem.get("selectores_candidatos", []), 1):
            sel_info.append(f"{i}. {sc}")
        self.actualizar_caja_texto_headers(self.txt_payload, "\n".join(sel_info))

        html_raw = elem.get("outerHTML") or "<No se ha cargado HTML de DevTools para este elemento. Pulsa 'Cargar HTML DevTools' para pegarlo.>"
        self.actualizar_caja_texto(self.txt_response, html_raw)

    def cargar_html_elemento_seleccionado(self):
        seleccion = self.tabla_elementos.selection()
        if not seleccion:
            messagebox.showwarning("Atención", "Seleccione primero un elemento de la lista.", parent=self.root)
            return
        idx = int(seleccion[0])
        if idx < len(self.elementos_involucrados):
            self.abrir_dialogo_cargar_html_devtools(self.elementos_involucrados[idx])

    def elegir_selector_elemento_seleccionado(self):
        seleccion = self.tabla_elementos.selection()
        if not seleccion:
            messagebox.showwarning("Atención", "Seleccione primero un elemento de la lista.", parent=self.root)
            return
        idx = int(seleccion[0])
        elem = self.elementos_involucrados[idx]
        candidatos = elem.get("selectores_candidatos", [])
        if not candidatos:
            messagebox.showinfo("Selectores", "Este elemento no posee selectores alternativos cargados aún. Usa 'Cargar HTML DevTools'.", parent=self.root)
            return

        sel_win = tk.Toplevel(self.root)
        sel_win.title("Elegir Selector Principal")
        sel_win.geometry("540x260")
        sel_win.configure(bg=self.color_bg)
        sel_win.transient(self.root)
        sel_win.grab_set()

        lbl_info = ttk.Label(sel_win, text=f"Selecciona el selector principal para:\n{elem.get('nombre')}", style="Header.TLabel", padding=12)
        lbl_info.pack(anchor="w")

        combo_sel = ttk.Combobox(sel_win, values=candidatos, state="readonly", font=("Segoe UI", 10))
        if elem.get("selector_actual") in candidatos:
            combo_sel.set(elem.get("selector_actual"))
        else:
            combo_sel.set(candidatos[0])
        combo_sel.pack(fill="x", padx=15, pady=10)

        def confirmar():
            nuevo_sel = combo_sel.get().strip()
            if nuevo_sel:
                elem["selector_actual"] = nuevo_sel
                for p_idx in elem.get("pasos_asociados", []):
                    if p_idx < len(self.peticiones_capturadas):
                        self.peticiones_capturadas[p_idx]["selector_sugerido"] = nuevo_sel
                self.actualizar_tabla_completa()
                self.actualizar_tabla_elementos()
                self.on_elemento_seleccionado(None)
                self.lbl_status.config(text=f"Selector principal actualizado a: {nuevo_sel}")
            sel_win.destroy()

        btn_conf = ttk.Button(sel_win, text="✔️ Aplicar a todas las acciones", style="Accent.TButton", command=confirmar)
        btn_conf.pack(pady=15)

    def copiar_selector_elemento_seleccionado(self):
        seleccion = self.tabla_elementos.selection()
        if not seleccion:
            return
        idx = int(seleccion[0])
        elem = self.elementos_involucrados[idx]
        sel = elem.get("selector_actual", "")
        if sel:
            self.root.clipboard_clear()
            self.root.clipboard_append(sel)
            self.root.update()
            self.lbl_status.config(text=f"Copiado selector: {sel}")

    def mostrar_menu_elementos(self, event):
        item_id = self.tabla_elementos.identify_row(event.y)
        if not item_id:
            return
        self.tabla_elementos.selection_set(item_id)
        idx = int(item_id)
        elem = self.elementos_involucrados[idx]

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="📥 Cargar / Pegar HTML de DevTools...", command=self.cargar_html_elemento_seleccionado)
        menu.add_command(label="🎯 Elegir Selector Principal...", command=self.elegir_selector_elemento_seleccionado)
        menu.add_command(label="📋 Copiar Selector Actual", command=self.copiar_selector_elemento_seleccionado)
        menu.post(event.x_root, event.y_root)

    def abrir_dialogo_cargar_html_devtools(self, target=None):
        """
        Abre una ventana interactiva para pegar el snippet HTML copiado desde DevTools (F12),
        parsear automáticamente sus atributos y generar una baraja de selectores resilientes.
        """
        elem_ref = None
        idx_paso_ref = None

        if isinstance(target, dict):
            elem_ref = target
        elif isinstance(target, int):
            idx_paso_ref = target
            if idx_paso_ref < len(self.peticiones_capturadas):
                pet = self.peticiones_capturadas[idx_paso_ref]
                elem_id = pet.get("element_id")
                for e in self.elementos_involucrados:
                    if e.get("id_elemento") == elem_id:
                        elem_ref = e
                        break
                if not elem_ref:
                    self.sincronizar_elementos_involucrados()
                    elem_ref = next((e for e in self.elementos_involucrados if e.get("id_elemento") == pet.get("element_id")), None)

        if not elem_ref and self.elementos_involucrados:
            elem_ref = self.elementos_involucrados[0]

        modal = tk.Toplevel(self.root)
        modal.title("📥 Cargar HTML desde DevTools (F12)")
        modal.geometry("720x640")
        modal.minsize(640, 520)
        modal.configure(bg=self.color_bg)
        modal.transient(self.root)
        modal.grab_set()

        nombre_elem = elem_ref.get("nombre", "Elemento") if elem_ref else "Elemento"

        # Cabecera
        lbl_tit = ttk.Label(modal, text="📥 ENRIQUECER ELEMENTO CON HTML DE DEVTOOLS", style="Header.TLabel", padding=(15, 12, 15, 4))
        lbl_tit.pack(anchor="w")

        lbl_desc = ttk.Label(
            modal, 
            text=f"Elemento objetivo: {nombre_elem}\n\n"
                 "Instrucciones:\n"
                 "1. En tu navegador (o Playwright Inspector), abre DevTools pulsando F12 o Inspeccionar elemento.\n"
                 "2. Haz clic derecho sobre el elemento/celda > Copiar > 'Copiar elemento' (Copy element).\n"
                 "3. Pega el código HTML a continuación y pulsa '⚡ Parsear HTML':",
            padding=(15, 0, 15, 8),
            font=("Segoe UI", 9),
            foreground=self.color_fg_sec
        )
        lbl_desc.pack(anchor="w")

        # Campo de texto para pegar HTML
        frame_input = ttk.Frame(modal, padding=(15, 0, 15, 10))
        frame_input.pack(fill="both", expand=True)

        txt_html = scrolledtext.ScrolledText(
            frame_input, 
            height=6, 
            bg=self.color_panel, 
            fg=self.color_fg, 
            insertbackground=self.color_accent, 
            font=("Consolas", 9)
        )
        txt_html.pack(fill="both", expand=True)

        # Si ya tenía outerHTML, pre-cargarlo
        html_existente = elem_ref.get("outerHTML", "") if elem_ref else ""
        if html_existente:
            txt_html.insert(tk.END, html_existente)

        # Área de resultados parseados
        frame_resultados = ttk.LabelFrame(modal, text="Selectores Descubiertos y Atributos", padding=10)
        frame_resultados.pack(fill="x", padx=15, pady=(0, 10))

        lbl_resumen = ttk.Label(frame_resultados, text="Pega el HTML y haz clic en '⚡ Parsear HTML' para extraer datos...", font=("Segoe UI", 9, "italic"), foreground=self.color_fg_sec)
        lbl_resumen.pack(anchor="w", pady=(0, 5))

        lbl_sel_combo = ttk.Label(frame_resultados, text="Selector Principal a Asignar:")
        lbl_sel_combo.pack(anchor="w")

        combo_selectores = ttk.Combobox(frame_resultados, state="readonly", font=("Segoe UI", 9))
        combo_selectores.pack(fill="x", pady=4)

        lbl_respaldo_info = ttk.Label(frame_resultados, text="", font=("Segoe UI", 8), foreground=self.color_fg_sec)
        lbl_respaldo_info.pack(anchor="w", pady=(2, 0))

        datos_parseados_holder = {"datos": None}

        def parsear_action():
            crudo = txt_html.get("1.0", tk.END).strip()
            if not crudo:
                messagebox.showwarning("HTML Vacío", "Pega primero el código HTML copiado de DevTools.", parent=modal)
                return

            res = parsear_elemento_devtools(crudo)
            if not res or not res.get("tagName"):
                messagebox.showerror("Error de Parseo", "No se reconoció una etiqueta HTML válida en el texto pegado.", parent=modal)
                return

            datos_parseados_holder["datos"] = res

            # Mostrar resumen
            detalles = [f"Tag: <{res['tagName'].lower()}>"]
            if res.get("id"):
                detalles.append(f"ID: {res['id']}")
            if res.get("role"):
                detalles.append(f"Rol: {res['role']}")
            if res.get("className"):
                detalles.append(f"Clase: {res['className'].split()[0]}")
            if res.get("sap_coord"):
                detalles.append(f"Celda SAP: [{res['sap_coord']}]")

            lbl_resumen.config(
                text="✅ Detectado: " + " | ".join(detalles), 
                foreground="#34d399",
                font=("Segoe UI", 9, "bold")
            )

            # Llenar combobox con los selectores generados
            selectores = res.get("selectores_generados", [])
            if selectores:
                combo_selectores.config(values=selectores)
                combo_selectores.set(selectores[0])
                lbl_respaldo_info.config(text=f"Se guardarán además {len(selectores) - 1} selectores alternativos como respaldo resiliente.")
            else:
                combo_selectores.config(values=[])
                lbl_respaldo_info.config(text="No se generaron selectores alternativos.")

        btn_parsear = ttk.Button(modal, text="⚡ Parsear HTML y Generar Selectores", style="Accent.TButton", command=parsear_action)
        btn_parsear.pack(fill="x", padx=15, pady=(0, 10))

        # Botones de acción inferiores
        frame_btns = ttk.Frame(modal, padding=(15, 0, 15, 12))
        frame_btns.pack(fill="x", side="bottom")

        def guardar_y_aplicar():
            datos = datos_parseados_holder["datos"]
            if not datos:
                crudo = txt_html.get("1.0", tk.END).strip()
                if crudo:
                    parsear_action()
                    datos = datos_parseados_holder["datos"]

            if not datos:
                messagebox.showwarning("Sin Datos", "Debes pegar y parsear el HTML antes de guardar.", parent=modal)
                return

            sel_elegido = combo_selectores.get().strip()

            if elem_ref:
                elem_ref["html_origen"] = "devtools"
                elem_ref["outerHTML"] = datos.get("outerHTML", "")
                elem_ref["tagName"] = datos.get("tagName", "")
                elem_ref["role"] = datos.get("role", "")
                elem_ref["id"] = datos.get("id", "")
                elem_ref["className"] = datos.get("className", "")
                elem_ref["sap_coord"] = datos.get("sap_coord")
                if sel_elegido:
                    elem_ref["selector_actual"] = sel_elegido
                elem_ref["selectores_candidatos"] = datos.get("selectores_generados", [])

                for p_idx in elem_ref.get("pasos_asociados", []):
                    if p_idx < len(self.peticiones_capturadas):
                        enriquecer_accion_con_datos_html(self.peticiones_capturadas[p_idx], datos, sel_elegido)
            elif idx_paso_ref is not None and idx_paso_ref < len(self.peticiones_capturadas):
                enriquecer_accion_con_datos_html(self.peticiones_capturadas[idx_paso_ref], datos, sel_elegido)

            self.actualizar_tabla_completa()
            self.sincronizar_y_actualizar_elementos()
            self.lbl_status.config(text=f"Elemento enriquecido exitosamente con {len(datos.get('selectores_generados', []))} selectores.")
            modal.destroy()

        btn_guardar = ttk.Button(frame_btns, text="💾 Guardar y Aplicar a este Elemento y Acciones", style="Accent.TButton", command=guardar_y_aplicar)
        btn_guardar.pack(side="right", padx=(5, 0))

        btn_cancelar = ttk.Button(frame_btns, text="Cancelar", command=modal.destroy)
        btn_cancelar.pack(side="right")

        if html_existente:
            modal.after(150, parsear_action)

    def abrir_editor_paso(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        idx = int(seleccion[0])
        pet = self.peticiones_capturadas[idx]
        
        editor = tk.Toplevel(self.root)
        editor.title(f"Editar Paso {idx}")
        editor.geometry("620x420")
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
            ttk.Label(frame_form, text="Tipo de Acción:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
            combo_tipo = ttk.Combobox(
                frame_form,
                state="readonly",
                values=[
                    "click",
                    "fill",
                    "upload",
                    "download",
                    "extract",
                    "assert_text",
                    "assert_visible",
                    "select",
                    "key",
                    "navigation"
                ],
                font=("Segoe UI", 10)
            )
            combo_tipo.set(pet.get("tipo_accion", "click"))
            combo_tipo.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
            entries["tipo_accion"] = combo_tipo

            ttk.Label(frame_form, text="Descriptor:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
            entry_desc = ttk.Entry(frame_form, font=("Segoe UI", 10))
            entry_desc.insert(0, pet.get("descriptor_legible", ""))
            entry_desc.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
            entries["descriptor_legible"] = entry_desc
            
            ttk.Label(frame_form, text="Selector Sugerido:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
            entry_sel = ttk.Entry(frame_form, font=("Segoe UI", 10))
            entry_sel.insert(0, pet.get("selector_sugerido", ""))
            entry_sel.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
            entries["selector_sugerido"] = entry_sel
            
            ttk.Label(frame_form, text="Valor / Archivo / Regex:").grid(row=3, column=0, sticky="w", pady=5, padx=5)
            frame_val_box = ttk.Frame(frame_form)
            frame_val_box.grid(row=3, column=1, sticky="ew", pady=5, padx=5)
            frame_val_box.columnconfigure(0, weight=1)

            entry_val = ttk.Entry(frame_val_box, font=("Segoe UI", 10))
            entry_val.insert(0, pet.get("valor", ""))
            entry_val.grid(row=0, column=0, sticky="ew")
            entries["valor"] = entry_val

            def examinar_archivo():
                t_actual = combo_tipo.get()
                if t_actual == "download":
                    ruta = filedialog.asksaveasfilename(
                        title="Seleccionar archivo destino para descarga",
                        initialfile=entry_val.get().strip()
                    )
                else:
                    ruta = filedialog.askopenfilename(
                        title="Seleccionar archivo para subir"
                    )
                if ruta:
                    entry_val.delete(0, tk.END)
                    entry_val.insert(0, ruta)

            btn_examinar = ttk.Button(frame_val_box, text="📁 Examinar...", command=examinar_archivo)
            btn_examinar.grid(row=0, column=1, padx=(5, 0))

            lbl_hint = ttk.Label(
                frame_form,
                text="💡 Upload: ruta del archivo a subir. Download: ruta o nombre de guardado (o vacío para el sugerido).\n"
                     "💡 Extracción: escribe etiqueta (ej. 'Hora'), regex (ej. r'\\d{2}:\\d{2}') o vacío para todo el texto.",
                font=("Segoe UI", 8),
                foreground="#94a3b8"
            )
            lbl_hint.grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 5), padx=5)

        def guardar():
            for k, widget in entries.items():
                if isinstance(widget, scrolledtext.ScrolledText):
                    pet[k] = widget.get("1.0", tk.END).strip()
                elif isinstance(widget, ttk.Combobox):
                    pet[k] = widget.get().strip()
                else:
                    pet[k] = widget.get().strip()
            editor.destroy()
            self.actualizar_tabla_completa()
            self.on_peticion_seleccionada(None)
            
        frame_btns = ttk.Frame(editor, padding=10)
        frame_btns.pack(side=tk.BOTTOM, fill=tk.X)
        
        if not is_api:
            btn_devtools = ttk.Button(frame_btns, text="📥 Cargar HTML DevTools", command=lambda: [editor.destroy(), self.abrir_dialogo_cargar_html_devtools(idx)])
            btn_devtools.pack(side=tk.LEFT, padx=5)

        btn_save = ttk.Button(frame_btns, text="💾 Guardar", style="Accent.TButton", command=guardar)
        btn_save.pack(side=tk.RIGHT, padx=5)
        
        btn_cancel = ttk.Button(frame_btns, text="Cancelar", command=editor.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=5)

    def limpiar_detalles(self):
        self.actualizar_caja_texto(self.txt_headers, "")
        self.actualizar_caja_texto(self.txt_payload, "")
        self.actualizar_caja_texto(self.txt_response, "")
        self.limpiar_ancestros()

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


    def poblar_arbol_json(self, dato):
        for item in self.arbol_json.get_children():
            self.arbol_json.delete(item)

        if dato is None:
            self.arbol_json.insert("", "end", text="<Sin datos>", values=("", "", ""))
            return

        self._insertar_nodo_arbol("", "", dato, ruta="raiz")

    def _insertar_nodo_arbol(self, parent, clave, valor, ruta=""):
        MAX_HIJOS = 200

        if isinstance(valor, dict):
            tipo_str = f"dict ({len(valor)})"
            node_id = self.arbol_json.insert(
                parent, "end",
                text=f"📁 {clave}" if clave else "📁 [raíz]",
                values=(clave, tipo_str, ""),
                open=(parent == "")
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
        if "APIs" in modo:
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
        export_win.geometry("540x420")
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
            text="Puedes generar el script de automatización resiliente para Playwright\no exportar la lista estructurada de selectores y alternativas capturadas.",
            style="Status.TLabel",
            padding=(15, 0, 15, 10)
        )
        lbl_desc.pack(anchor="w")

        var_modo_resiliente = tk.BooleanVar(value=True)

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
                        parametrizar=self.var_parametrizar.get(),
                        storage_state=self.config_storage_state.get().strip(),
                        incluir_trace=self.config_trace_en_codigo.get(),
                        modo_resiliente=var_modo_resiliente.get(),
                        http_user=self.config_http_user.get().strip(),
                        http_password=self.config_http_pass.get().strip()
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
        frame_btns.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        chk_resiliente = ttk.Checkbutton(
            frame_btns,
            text="🛡️ Modo Script Resiliente (Cierre de popups y selectores de respaldo)",
            variable=var_modo_resiliente
        )
        chk_resiliente.pack(anchor="w", pady=(0, 10))

        btn_py = ttk.Button(
            frame_btns,
            text="⚙️ Generar Script de Automatización Playwright (.py)",
            style="Accent.TButton",
            command=lambda: procesar_exportacion("py")
        )
        btn_py.pack(fill=tk.X, pady=4)

        btn_json = ttk.Button(
            frame_btns,
            text="📋 Exportar Lista Estructurada (.json)",
            style="TButton",
            command=lambda: procesar_exportacion("json")
        )
        btn_json.pack(fill=tk.X, pady=4)

        btn_txt = ttk.Button(
            frame_btns,
            text="📝 Exportar Reporte de Selectores (.txt)",
            style="TButton",
            command=lambda: procesar_exportacion("txt")
        )
        btn_txt.pack(fill=tk.X, pady=4)

        btn_guia = ttk.Button(
            frame_btns,
            text="💡 ¿Dudas? Comparar Generadores (Codegen vs App)",
            command=self.mostrar_guia_comparativa
        )
        btn_guia.pack(fill=tk.X, pady=(6, 0))

        btn_cancel = ttk.Button(export_win, text="Cancelar", command=export_win.destroy)
        btn_cancel.pack(pady=10)

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
        dir_trazas = self.config_output_dir.get().strip()
        if not dir_trazas or not os.path.exists(dir_trazas):
            dir_trazas = self.output_base_dir

        try:
            self.lbl_status.config(text="Abriendo visor de trazas (Playwright)...")
            
            from playwright._impl._driver import compute_driver_executable
            driver_exec = compute_driver_executable()
            
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
            
            self.lbl_status.config(text="Visor abierto. Arrastra el archivo trace.zip desde la carpeta al navegador.")
            
            try:
                os.startfile(dir_trazas)
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el visor de trazas: {e}")

    def abrir_inspector_playwright(self):
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.input_queue.put(("abrir_inspector", None))
            self.lbl_status.config(text="Inspector de Playwright invocado. Interactúe con la ventana del Inspector...")
        else:
            messagebox.showinfo("Inspector Playwright", "El Inspector solo puede abrirse durante una sesión de captura activa.")

    def importar_script_codegen(self, ruta_archivo=None):
        if not ruta_archivo:
            ruta_archivo = filedialog.askopenfilename(
                parent=self.root,
                title="Importar Script de Playwright Codegen",
                filetypes=[("Archivos Python", "*.py"), ("Todos los archivos", "*.*")]
            )
        if not ruta_archivo:
            return

        try:
            acciones = parsear_script_codegen(ruta_archivo)
            if not acciones:
                messagebox.showwarning(
                    "Sin acciones",
                    "No se detectaron acciones de Playwright reconocibles en el archivo seleccionado.",
                    parent=self.root
                )
                return

            modo_actual = self.combo_modo.get()
            if "Grabador" not in modo_actual:
                self.combo_modo.set("Grabador DOM (Acciones)")
                self.on_cambio_modo()

            if self.peticiones_capturadas:
                resp = messagebox.askyesnocancel(
                    "Importar Pasos de Codegen",
                    f"Se encontraron {len(acciones)} pasos.\n\n¿Deseas REEMPLAZAR los pasos actuales?\n• Sí: Reemplazar lista completa\n• No: Añadir al final de la lista\n• Cancelar: No hacer nada",
                    parent=self.root
                )
                if resp is None:
                    return
                elif resp:
                    self.peticiones_capturadas = acciones
                else:
                    self.peticiones_capturadas.extend(acciones)
            else:
                self.peticiones_capturadas = acciones

            self.actualizar_tabla_completa()
            self.lbl_status.config(text=f"Se importaron {len(acciones)} pasos desde Codegen.")
            
            desea_enriquecer = messagebox.askyesno(
                "Auto-Enriquecer Pasos DOM",
                f"¡Se han importado {len(acciones)} pasos de Playwright Codegen con éxito!\n\n"
                "¿Deseas ejecutar ahora el Auto-Replay para enriquecerlos automáticamente con:\n"
                "• outerHTML completo\n"
                "• Árbol interactivo de ancestros (padres, abuelos, contenedores)\n"
                "• Selectores de respaldo y XPath?\n\n"
                "(Podrás ver la ejecución en el navegador y los datos se completarán solos)",
                parent=self.root
            )
            if desea_enriquecer:
                self.iniciar_enriquecimiento_dom()
        except Exception as e:
            messagebox.showerror("Error al importar", f"Ocurrió un error al procesar el archivo: {e}", parent=self.root)

    def iniciar_enriquecimiento_dom(self):
        if not self.peticiones_capturadas:
            messagebox.showwarning(
                "Sin Pasos",
                "No hay pasos cargados en la tabla para enriquecer.\nImporta primero un script de Codegen o captura acciones con el Grabador DOM.",
                parent=self.root
            )
            return

        prog_win = tk.Toplevel(self.root)
        prog_win.title("Auto-Enriqueciendo Pasos DOM...")
        prog_win.geometry("480x230")
        prog_win.resizable(False, False)
        prog_win.configure(bg=self.color_bg)
        prog_win.transient(self.root)
        prog_win.grab_set()

        lbl_tit = ttk.Label(prog_win, text="⚡ Auto-Replay & Enriquecimiento DOM", style="Header.TLabel", padding=(15, 15, 15, 5))
        lbl_tit.pack(anchor="w")

        lbl_info = ttk.Label(
            prog_win,
            text="Reproduciendo pasos en el navegador e inspeccionando el DOM vivo...",
            style="Status.TLabel",
            padding=(15, 0, 15, 10)
        )
        lbl_info.pack(anchor="w")

        pbar = ttk.Progressbar(prog_win, mode="determinate", maximum=len(self.peticiones_capturadas))
        pbar.pack(fill=tk.X, padx=15, pady=5)

        lbl_step = ttk.Label(prog_win, text="Iniciando navegador Playwright...", font=("Segoe UI", 9))
        lbl_step.pack(anchor="w", padx=15, pady=5)

        def actualizar_progreso(paso_actual, total, texto):
            def _update():
                pbar["value"] = paso_actual
                lbl_step.config(text=texto)
            self.root.after(0, _update)

        import threading

        def hilo_trabajo():
            try:
                storage = self.config_storage_state.get().strip()
                pasos_actuales = [dict(p) for p in self.peticiones_capturadas]
                pasos_enriquecidos = enriquecer_pasos_dom(
                    pasos_actuales,
                    callback_progreso=actualizar_progreso,
                    headless=False,
                    storage_state=storage
                )

                def finalizado_ok():
                    prog_win.destroy()
                    self.peticiones_capturadas = pasos_enriquecidos
                    self.actualizar_tabla_completa()
                    if self.peticiones_capturadas:
                        self.tabla.selection_set("0")
                        self.on_peticion_seleccionada(None)
                    messagebox.showinfo(
                        "Enriquecimiento Completado",
                        f"¡Se han enriquecido exitosamente {len(pasos_enriquecidos)} pasos!\n\n"
                        "Ahora puedes ver el outerHTML completo, la jerarquía de ancestros en la pestaña '🌳 Ancestros' "
                        "y generar scripts con selectores de respaldo múltiples.",
                        parent=self.root
                    )

                self.root.after(0, finalizado_ok)
            except Exception as e:
                def finalizado_err(err=e):
                    prog_win.destroy()
                    messagebox.showerror("Error en Auto-Replay", f"Ocurrió un error al enriquecer los pasos: {err}", parent=self.root)
                self.root.after(0, finalizado_err)

        t = threading.Thread(target=hilo_trabajo, daemon=True)
        t.start()

    def abrir_dialogo_codegen(self):
        codegen_win = tk.Toplevel(self.root)
        codegen_win.title("Asistente de Playwright Codegen")
        codegen_win.geometry("640x680")
        codegen_win.minsize(580, 500)
        codegen_win.resizable(True, True)
        codegen_win.configure(bg=self.color_bg)
        codegen_win.transient(self.root)
        codegen_win.grab_set()

        codegen_win.update_idletasks()
        w = 640
        h = 680
        x = max(10, self.root.winfo_x() + (self.root.winfo_width() - w) // 2)
        y = max(10, self.root.winfo_y() + (self.root.winfo_height() - h) // 2)
        codegen_win.geometry(f"{w}x{h}+{x}+{y}")
        aplicar_barra_titulo_oscura(codegen_win, oscuro=self.es_tema_oscuro())

        lbl_titulo = ttk.Label(codegen_win, text="⚡ ASISTENTE DE PLAYWRIGHT CODEGEN", style="Header.TLabel", padding=12)
        lbl_titulo.pack(anchor="w")

        # Barra inferior fija con el botón de lanzamiento (siempre visible sin importar la altura de pantalla)
        bottom_bar = ttk.Frame(codegen_win, style="TFrame")
        bottom_bar.pack(side="bottom", fill="x", padx=15, pady=12)

        # Contenedor central con scrollbar vertical para adaptarse a cualquier resolución/escalado
        container = ttk.Frame(codegen_win, style="TFrame")
        container.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 5))

        canvas = tk.Canvas(container, bg=self.color_bg, highlightthickness=0)
        scrollbar = tb.Scrollbar(container, orient="vertical", command=canvas.yview, bootstyle="round")
        scrollable_frame = ttk.Frame(canvas, style="TFrame")

        def _on_frame_configure_cg(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        scrollable_frame.bind("<Configure>", _on_frame_configure_cg)

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_canvas_configure_cg(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure_cg)

        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_cg_mousewheel(event):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_cg_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        codegen_win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        main_f = scrollable_frame

        # Banner informativo de buenas prácticas y complementariedad con texto claro y legible
        info_banner = ttk.LabelFrame(main_f, text="💡 Recomendaciones de Uso y Límites de Codegen", padding=10)
        info_banner.pack(fill="x", pady=(0, 6))

        msg_info = (
            "• Ideal para: Prototipado veloz, mapear selectores y guardar login con MFA/Cookies (--save-storage).\n"
            "• Limitación: Genera scripts planos lineales sin control de flujo (sin if/else, bucles ni reintentos).\n"
            "• Sinergia RPA: Te recomendamos mantener activa la casilla 'Importar acciones al Grabador DOM' para\n"
            "  dotar a tu flujo de selectores de respaldo, auto-cierre de modales/cookies y parametrización segura."
        )
        lbl_info = ttk.Label(info_banner, text=msg_info, font=("Segoe UI", 9), foreground="#cbd5e1", justify="left")
        lbl_info.pack(anchor="w")

        # 1. URL y Navegador
        f_nav = ttk.LabelFrame(main_f, text="Destino y Navegador", padding=10)
        f_nav.pack(fill="x", pady=4)
        f_nav.columnconfigure(1, weight=1)

        url_var = tk.StringVar(value=self.entry_url.get().strip() or "https://")
        ttk.Label(f_nav, text="URL Objetivo:").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 5))
        e_url = ttk.Entry(f_nav, textvariable=url_var, font=("Segoe UI", 9))
        e_url.grid(row=0, column=1, sticky="ew", pady=4)

        nav_var = tk.StringVar(value=self.combo_navegador.get() or "Chromium")
        ttk.Label(f_nav, text="Navegador:").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 5))
        c_nav = ttk.Combobox(f_nav, textvariable=nav_var, values=["Chromium", "Edge", "Firefox", "WebKit"], state="readonly", width=18)
        c_nav.grid(row=1, column=1, sticky="w", pady=4)

        # 2. Configuración de Grabación
        f_code = ttk.LabelFrame(main_f, text="Configuración de Grabación", padding=10)
        f_code.pack(fill="x", pady=4)
        f_code.columnconfigure(1, weight=1)

        lang_var = tk.StringVar(value="Python (Sincrónico)")
        ttk.Label(f_code, text="Lenguaje Objetivo:").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 5))
        c_lang = ttk.Combobox(f_code, textvariable=lang_var, values=[l[0] for l in LENGUAJES_CODEGEN], state="readonly", width=22)
        c_lang.grid(row=0, column=1, sticky="w", pady=4)

        dev_var = tk.StringVar(value="Ninguno (Por Defecto)")
        ttk.Label(f_code, text="Emular Dispositivo:").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 5))
        c_dev = ttk.Combobox(f_code, textvariable=dev_var, values=DISPOSITIVOS_CODEGEN, state="readonly", width=22)
        c_dev.grid(row=1, column=1, sticky="w", pady=4)

        # 3. Archivo de Salida
        f_out = ttk.LabelFrame(main_f, text="Exportación de Script", padding=10)
        f_out.pack(fill="x", pady=4)
        f_out.columnconfigure(0, weight=1)

        out_script_var = tk.StringVar(value=os.path.join(self.output_base_dir, "script_codegen.py"))
        e_out = ttk.Entry(f_out, textvariable=out_script_var, font=("Segoe UI", 9))
        e_out.grid(row=0, column=0, sticky="ew", pady=2, padx=(0, 5))

        def examinar_salida():
            f = filedialog.asksaveasfilename(
                parent=codegen_win,
                title="Guardar script grabado",
                defaultextension=".py",
                initialfile="script_codegen.py",
                initialdir=self.output_base_dir,
                filetypes=[("Archivos Python", "*.py"), ("Todos los archivos", "*.*")]
            )
            if f:
                out_script_var.set(os.path.normpath(f))

        tb.Button(f_out, text="📂 Examinar...", command=examinar_salida, bootstyle="secondary").grid(row=0, column=1, sticky="w", pady=2)

        auto_import_var = tk.BooleanVar(value=True)
        chk_auto_import = tb.Checkbutton(
            f_out, 
            text="Al cerrar Codegen, importar acciones al Grabador DOM", 
            variable=auto_import_var,
            bootstyle="success-round-toggle"
        )
        chk_auto_import.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 4))

        # 4. Estado de Sesión (Storage State)
        f_auth = ttk.LabelFrame(main_f, text="Autenticación y Sesión (Opcional)", padding=10)
        f_auth.pack(fill="x", pady=4)
        f_auth.columnconfigure(0, weight=1)

        load_storage_var = tk.StringVar(value=self.config_storage_state.get().strip())
        save_storage_var = tk.StringVar(value="")

        ttk.Label(f_auth, text="Cargar sesión previa (--load-storage):").grid(row=0, column=0, sticky="w", columnspan=2)
        e_load = ttk.Entry(f_auth, textvariable=load_storage_var, font=("Segoe UI", 9))
        e_load.grid(row=1, column=0, sticky="ew", pady=2, padx=(0, 5))

        def examinar_load():
            f = filedialog.askopenfilename(
                parent=codegen_win,
                title="Cargar archivo auth.json",
                filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")]
            )
            if f:
                load_storage_var.set(os.path.normpath(f))

        tb.Button(f_auth, text="📂...", width=6, command=examinar_load, bootstyle="secondary").grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(f_auth, text="Guardar sesión al salir (--save-storage):").grid(row=2, column=0, sticky="w", columnspan=2, pady=(4, 0))
        e_save = ttk.Entry(f_auth, textvariable=save_storage_var, font=("Segoe UI", 9))
        e_save.grid(row=3, column=0, sticky="ew", pady=2, padx=(0, 5))

        def examinar_save():
            f = filedialog.asksaveasfilename(
                parent=codegen_win,
                title="Guardar sesión auth.json",
                defaultextension=".json",
                initialfile="storage_state.json",
                initialdir=self.output_base_dir,
                filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")]
            )
            if f:
                save_storage_var.set(os.path.normpath(f))

        tb.Button(f_auth, text="📂...", width=6, command=examinar_save, bootstyle="secondary").grid(row=3, column=1, sticky="w", pady=2)

        def ejecutar_codegen():
            target_code = "python"
            for nombre_l, target_id in LENGUAJES_CODEGEN:
                if nombre_l == lang_var.get():
                    target_code = target_id
                    break

            url_ejecutar = url_var.get().strip()
            script_dest = out_script_var.get().strip() if out_script_var.get().strip() else None
            save_st = save_storage_var.get().strip() if save_storage_var.get().strip() else None
            load_st = load_storage_var.get().strip() if load_storage_var.get().strip() else None

            codegen_win.destroy()
            self.lbl_status.config(text="Ejecutando Playwright Codegen... Interactúe en la ventana abierta.")

            def worker_espera():
                try:
                    p = lanzar_playwright_codegen(
                        url=url_ejecutar,
                        browser=nav_var.get(),
                        target=target_code,
                        output_file=script_dest,
                        device=dev_var.get(),
                        save_storage=save_st,
                        load_storage=load_st,
                        ignore_https_errors=self.config_ignore_ssl.get()
                    )
                    p.wait()

                    if save_st and os.path.exists(save_st):
                        self.config_storage_state.set(save_st)

                    if script_dest and os.path.exists(script_dest):
                        if auto_import_var.get():
                            self.root.after(200, lambda: self.importar_script_codegen(script_dest))
                        else:
                            self.root.after(200, lambda: messagebox.showinfo(
                                "Codegen Finalizado",
                                f"El script fue guardado con éxito en:\n{script_dest}",
                                parent=self.root
                            ))
                    self.lbl_status.config(text="Playwright Codegen finalizado.")
                except Exception as err:
                    self.root.after(200, lambda: messagebox.showerror("Error en Codegen", f"No se pudo ejecutar Playwright Codegen: {err}", parent=self.root))

            threading.Thread(target=worker_espera, daemon=True).start()

        btn_lanzar = tb.Button(
            bottom_bar, 
            text="🚀 Iniciar Grabación con Codegen", 
            bootstyle="success", 
            command=ejecutar_codegen,
            padding=(12, 8)
        )
        btn_lanzar.pack(fill="x")

    def abrir_configuracion(self):
        config_win = tk.Toplevel(self.root)
        config_win.title("Configuración Avanzada")
        config_win.geometry("560x700")
        config_win.minsize(520, 500)
        config_win.resizable(True, True)
        config_win.configure(bg=self.color_bg)
        config_win.transient(self.root)
        config_win.grab_set()
        
        config_win.update_idletasks()
        w = 560
        h = 700
        x = max(10, self.root.winfo_x() + (self.root.winfo_width() - w) // 2)
        y = max(10, self.root.winfo_y() + (self.root.winfo_height() - h) // 2)
        config_win.geometry(f"{w}x{h}+{x}+{y}")
        aplicar_barra_titulo_oscura(config_win, oscuro=self.es_tema_oscuro())
        
        # Título superior
        lbl_titulo = ttk.Label(config_win, text="⚙️ CONFIGURACIÓN AVANZADA", style="Header.TLabel", padding=(15, 12, 15, 8))
        lbl_titulo.pack(side="top", anchor="w", fill="x")

        # Barra inferior fija: botón 'Guardar y Cerrar' siempre visible
        bottom_bar = ttk.Frame(config_win, style="TFrame")
        bottom_bar.pack(side="bottom", fill="x", padx=15, pady=12)

        def guardar_y_cerrar():
            self.guardar_configuracion_gui()
            config_win.destroy()

        btn_save = tb.Button(bottom_bar, text="💾 Guardar y Cerrar", bootstyle="success", command=guardar_y_cerrar)
        btn_save.pack(side="right")

        # Contenedor central con scrollbar para asegurar visualización en cualquier resolución o escalado DPI
        container = ttk.Frame(config_win, style="TFrame")
        container.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 5))

        canvas = tk.Canvas(container, bg=self.color_bg, highlightthickness=0)
        scrollbar = tb.Scrollbar(container, orient="vertical", command=canvas.yview, bootstyle="round")
        scrollable_frame = ttk.Frame(canvas, style="TFrame")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        scrollable_frame.bind("<Configure>", _on_frame_configure)

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_cfg_mousewheel(event):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_cfg_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        config_win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        main_frame = scrollable_frame

        # ----------------------------------------------------
        # SECCIÓN 1: APARIENCIA Y TEMA VISUAL
        # ----------------------------------------------------
        theme_frame = ttk.LabelFrame(main_frame, text="🎨 Apariencia y Tema Visual", padding=10)
        theme_frame.pack(fill="x", pady=5)
        theme_frame.columnconfigure(1, weight=1)

        lbl_theme = ttk.Label(theme_frame, text="Tema de Interfaz:")
        lbl_theme.grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)

        combo_tema = ttk.Combobox(
            theme_frame,
            values=["superhero", "darkly", "cyborg", "solar", "vapor", "flatly", "cosmo"],
            state="readonly",
            width=18,
            font=("Segoe UI", 9)
        )
        combo_tema.set(self.tema_actual)
        combo_tema.grid(row=0, column=1, sticky="w", pady=4)

        def on_cambiar_tema_cfg(e=None):
            sel = combo_tema.get()
            if sel:
                self.aplicar_tema(sel)
                aplicar_barra_titulo_oscura(config_win, oscuro=self.es_tema_oscuro())

        combo_tema.bind("<<ComboboxSelected>>", on_cambiar_tema_cfg)

        lbl_theme_desc = ttk.Label(
            theme_frame,
            text="💡 El tema se actualiza en tiempo real y tu preferencia se guardará automáticamente.",
            style="Status.TLabel",
            font=("Segoe UI", 8, "italic")
        )
        lbl_theme_desc.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # ----------------------------------------------------
        # SECCIÓN 2: PARÁMETROS DE NAVEGACIÓN
        # ----------------------------------------------------
        nav_frame = ttk.LabelFrame(main_frame, text="Parámetros de Navegación", padding=10)
        nav_frame.pack(fill="x", pady=5)

        chk_ssl = tb.Checkbutton(nav_frame, text="Ignorar errores de SSL / HTTPS", variable=self.config_ignore_ssl, bootstyle="round-toggle")
        chk_ssl.grid(row=0, column=0, columnspan=2, sticky="w", pady=4)

        chk_headless = tb.Checkbutton(nav_frame, text="Ejecutar en segundo plano (Headless)", variable=self.config_headless, bootstyle="round-toggle")
        chk_headless.grid(row=0, column=2, columnspan=2, sticky="w", pady=4, padx=(10, 0))

        lbl_w = ttk.Label(nav_frame, text="Viewport Ancho:")
        lbl_w.grid(row=1, column=0, sticky="w", pady=6, padx=(0, 5))
        entry_w = ttk.Entry(nav_frame, textvariable=self.config_width, width=8, font=("Segoe UI", 9))
        entry_w.grid(row=1, column=1, sticky="w", pady=6)

        lbl_h = ttk.Label(nav_frame, text="Viewport Alto:")
        lbl_h.grid(row=1, column=2, sticky="w", pady=6, padx=(10, 5))
        entry_h = ttk.Entry(nav_frame, textvariable=self.config_height, width=8, font=("Segoe UI", 9))
        entry_h.grid(row=1, column=3, sticky="w", pady=6)

        out_frame = ttk.LabelFrame(main_frame, text="Grabación y Diagnóstico", padding=10)
        out_frame.pack(fill="x", pady=5)

        chk_video = tb.Checkbutton(out_frame, text="Grabar video de sesión", variable=self.config_record_video, bootstyle="round-toggle")
        chk_video.grid(row=0, column=0, sticky="w", pady=4)

        chk_trace = tb.Checkbutton(out_frame, text="Generar traza de captura Playwright", variable=self.config_record_trace, bootstyle="round-toggle")
        chk_trace.grid(row=0, column=1, sticky="w", pady=4, padx=(10, 0))

        chk_trace_gen = tb.Checkbutton(out_frame, text="Iniciar traza en código generado (Trace Viewer)", variable=self.config_trace_en_codigo, bootstyle="round-toggle")
        chk_trace_gen.grid(row=1, column=0, columnspan=2, sticky="w", pady=4)

        lbl_timeout = ttk.Label(out_frame, text="Timeout global (seg):")
        lbl_timeout.grid(row=2, column=0, sticky="w", pady=6, padx=(0, 5))
        entry_timeout = ttk.Entry(out_frame, textvariable=self.config_timeout, width=8, font=("Segoe UI", 9))
        entry_timeout.grid(row=2, column=1, sticky="w", pady=6)

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

        btn_browse = tb.Button(dir_frame, text="📂 Examinar...", command=examinar_carpeta, bootstyle="secondary-outline")
        btn_browse.grid(row=0, column=1, sticky="w", pady=5)

        auth_frame = ttk.LabelFrame(main_frame, text="Sesión de Autenticación / Cookies (Storage State)", padding=10)
        auth_frame.pack(fill="x", pady=5)
        auth_frame.columnconfigure(0, weight=1)

        entry_storage = ttk.Entry(auth_frame, textvariable=self.config_storage_state, font=("Segoe UI", 9))
        entry_storage.grid(row=0, column=0, sticky="ew", pady=2, padx=(0, 5))

        def examinar_storage():
            f = filedialog.askopenfilename(
                parent=config_win,
                title="Seleccionar archivo de sesión JSON",
                filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")]
            )
            if f:
                self.config_storage_state.set(os.path.normpath(f))

        btn_storage = tb.Button(auth_frame, text="📂 Examinar...", command=examinar_storage, bootstyle="secondary-outline")
        btn_storage.grid(row=0, column=1, sticky="w", pady=2)

        def grabar_login_rapido():
            url_login = self.entry_url.get().strip() or "https://"
            dest = os.path.join(self.output_base_dir, "storage_state.json")
            msg = f"Se iniciará Playwright Codegen en: {url_login}\n\nInicia sesión normalmente y resuelve cualquier verificación.\nAl cerrar el navegador, las cookies y tokens se guardarán en:\n{dest}"
            if messagebox.askyesno("Grabar Sesión de Login", msg, parent=config_win):
                try:
                    lanzar_playwright_codegen(
                        url=url_login,
                        browser=self.combo_navegador.get(),
                        save_storage=dest,
                        ignore_https_errors=self.config_ignore_ssl.get()
                    )
                    self.config_storage_state.set(dest)
                    messagebox.showinfo("Codegen Iniciado", "Inicia sesión en la ventana de Codegen y ciérrala al terminar para guardar la sesión.", parent=config_win)
                except Exception as ex:
                    messagebox.showerror("Error", f"No se pudo iniciar Codegen: {ex}", parent=config_win)

        btn_login = tb.Button(auth_frame, text="🔑 Grabar Login con Codegen", command=grabar_login_rapido, bootstyle="info-outline")
        btn_login.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))

        # ----------------------------------------------------
        # SECCIÓN: AUTENTICACIÓN HTTP / NTLM
        # ----------------------------------------------------
        http_frame = ttk.LabelFrame(main_frame, text="Credenciales HTTP / NTLM (Autenticación de Red / Basic)", padding=10)
        http_frame.pack(fill="x", pady=5)
        http_frame.columnconfigure(1, weight=1)

        lbl_u = ttk.Label(http_frame, text="Usuario:")
        lbl_u.grid(row=0, column=0, sticky="w", pady=4, padx=(0, 10))
        entry_u = ttk.Entry(http_frame, textvariable=self.config_http_user, font=("Segoe UI", 9))
        entry_u.grid(row=0, column=1, sticky="ew", pady=4)

        lbl_p = ttk.Label(http_frame, text="Contraseña:")
        lbl_p.grid(row=1, column=0, sticky="w", pady=4, padx=(0, 10))
        entry_p = ttk.Entry(http_frame, textvariable=self.config_http_pass, show="*", font=("Segoe UI", 9))
        entry_p.grid(row=1, column=1, sticky="ew", pady=4)

        lbl_http_hint = ttk.Label(
            http_frame,
            text="💡 Se usan para responder automáticamente al desafío 401 (ej. Claro SiteMinder/NTLM) e inyectar http_credentials en los scripts generados.",
            style="Status.TLabel",
            font=("Segoe UI", 8, "italic"),
            wraplength=480
        )
        lbl_http_hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ua_frame = ttk.LabelFrame(main_frame, text="User-Agent Personalizado (Opcional)", padding=10)
        ua_frame.pack(fill="x", pady=5)

        entry_ua = ttk.Entry(ua_frame, textvariable=self.config_user_agent, font=("Segoe UI", 9))
        entry_ua.pack(fill="x", pady=2)

        info_frame = ttk.LabelFrame(main_frame, text="Aplicación y Actualizaciones", padding=10)
        info_frame.pack(fill="x", pady=5)
        info_frame.columnconfigure(0, weight=1)

        lbl_ver = ttk.Label(info_frame, text=f"Versión Actual: v{VERSION_LOCAL}", font=("Segoe UI", 9, "bold"))
        lbl_ver.grid(row=0, column=0, sticky="w", pady=2)

        btn_chk_update = tb.Button(info_frame, text="🔄 Buscar Actualizaciones", command=lambda: verificar_actualizaciones(self, manual=True), bootstyle="secondary-outline")
        btn_chk_update.grid(row=0, column=1, sticky="e", pady=2)

    def mostrar_guia_comparativa(self):
        guia_win = tk.Toplevel(self.root)
        guia_win.title("Guía Comparativa: Playwright Codegen vs. Generador RPA")
        guia_win.geometry("740x650")
        guia_win.minsize(660, 520)
        guia_win.resizable(True, True)
        guia_win.configure(bg=self.color_bg)
        guia_win.transient(self.root)
        guia_win.grab_set()

        guia_win.update_idletasks()
        w = 740
        h = 650
        x = max(10, self.root.winfo_x() + (self.root.winfo_width() - w) // 2)
        y = max(10, self.root.winfo_y() + (self.root.winfo_height() - h) // 2)
        guia_win.geometry(f"{w}x{h}+{x}+{y}")
        aplicar_barra_titulo_oscura(guia_win, oscuro=self.es_tema_oscuro())

        lbl_titulo = ttk.Label(guia_win, text="💡 GUÍA COMPARATIVA: ¿QUÉ GENERADOR ELEGIR?", style="Header.TLabel", padding=(15, 12, 15, 5))
        lbl_titulo.pack(side="top", anchor="w", fill="x")

        bottom_bar = ttk.Frame(guia_win, style="TFrame")
        bottom_bar.pack(side="bottom", fill="x", padx=15, pady=10)
        btn_cerrar = tb.Button(bottom_bar, text="Entendido y Cerrar", bootstyle="primary", command=guia_win.destroy)
        btn_cerrar.pack(side="right")

        container = ttk.Frame(guia_win, style="TFrame")
        container.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 5))

        txt_info = scrolledtext.ScrolledText(
            container,
            bg="#1e293b",
            fg="#f8fafc",
            font=("Segoe UI", 9),
            wrap=tk.WORD,
            padx=12,
            pady=12,
            relief="flat"
        )
        txt_info.pack(fill="both", expand=True)

        contenido_guia = (
            "========================================================================================\n"
            "   PLAYWRIGHT CODEGEN vs. GENERADOR RPA NATIVO (DOM / APIS)\n"
            "========================================================================================\n\n"
            "Ambas herramientas tienen fortalezas distintas. Para una automatización profesional,\n"
            "lo ideal no es elegir una u otra, sino combinarlas en un mismo flujo de trabajo:\n\n"
            "----------------------------------------------------------------------------------------\n"
            "1. TABLA COMPARATIVA\n"
            "----------------------------------------------------------------------------------------\n"
            "Aspecto                 | Playwright Codegen               | Generador RPA Nativo (App)\n"
            "------------------------+----------------------------------+----------------------------\n"
            "Objetivo principal      | Descubrimiento / Prototipado     | Automatización RPA Industrial\n"
            "Manejo de Login y MFA   | Excelente (graba cookies auth)   | Permite cargar sesiones previas\n"
            "Selectores generados    | Planos (getByRole, texto)        | Multi-selector con Fallbacks\n"
            "Tolerancia a cambios    | Baja (IDs dinámicos rompen bot)  | Alta (Respaldo en XPath/Name/ID)\n"
            "Avisos de Cookies/Popup | No los maneja; causan fallos     | Auto-cierre de modales activo\n"
            "Extracción de datos     | No gestiona variables            | Variables dinámicas / CSV/JSON\n"
            "Seguridad credenciales  | Texto plano en el código         | Variables de entorno seguras\n"
            "Gestión de iframes      | A veces incompleto               | Soporte de iframes anidados\n"
            "Trazas de diagnóstico   | Opcional manual                  | Integrado con Trace Viewer\n\n"
            "----------------------------------------------------------------------------------------\n"
            "2. ¿CUÁNDO CONVIENE USAR CADA HERRAMIENTA?\n"
            "----------------------------------------------------------------------------------------\n"
            "• USA PLAYWRIGHT CODEGEN CUANDO:\n"
            "  - Necesites iniciar sesión manualmente en un sitio con CAPTCHA o 2FA para guardar cookies\n"
            "    en 'storage_state.json' (--save-storage) y luego reusarlas en tus bots.\n"
            "  - Quieras grabar de un tirón 15 o 20 pasos de navegación exploratoria sin inspeccionar HTML.\n"
            "  - Estés prototipando y quieras ver en vivo cómo Playwright detecta cada botón o campo.\n\n"
            "• USA EL GENERADOR RPA NATIVO (DE LA APP) CUANDO:\n"
            "  - Construyas un bot para producción que deba tolerar cambios de interfaz (React, Angular, SAP).\n"
            "  - Necesites que el bot detecte y cierre automáticamente avisos de cookies o popups emergentes.\n"
            "  - Requieras extraer datos (números de trámite, celdas de tabla) y encadenarlos en variables.\n"
            "  - Manejes credenciales que deban protegerse como variables de entorno (RPA_SECRET).\n\n"
            "----------------------------------------------------------------------------------------\n"
            "3. EL FLUJO HÍBRIDO RECOMENDADO (MÁXIMA EFICIENCIA Y RESILIENCIA)\n"
            "----------------------------------------------------------------------------------------\n"
            "  Paso 1: Lanza '🚀 Iniciar Grabación con Codegen' para navegar, autenticarte y generar tu sesión.\n"
            "  Paso 2: Al cerrar Codegen, se importan automáticamente las acciones a la tabla de la App.\n"
            "  Paso 3: En la tabla de la App, convierte pasos mecánicos en '📤 Extraer' o '👁️ Validar'.\n"
            "  Paso 4: Exporta como '⚙️ Script de Automatización' con la casilla '🛡️ Modo Resiliente' activa.\n\n"
            "¡Así obtienes la velocidad de grabación de Codegen con la resiliencia industrial de la App!\n"
        )
        txt_info.insert(tk.END, contenido_guia)
        txt_info.config(state=tk.DISABLED)
