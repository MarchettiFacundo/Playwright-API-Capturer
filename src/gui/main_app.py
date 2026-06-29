import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import queue
import json
import glob
import subprocess

from src.utils.helpers import (
    is_dir_writable,
    get_documents_folder,
    find_chrome_path,
    find_edge_path,
    is_port_in_use,
    obtener_ruta_recurso
)
from src.utils.updater import verificar_actualizaciones, VERSION_LOCAL
from src.capture.playwright_thread import PlaywrightCaptureThread
from src.generators.api_generator import generar_script_python, generar_script_unificado
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

class CapturaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Playwright API Capturer & Generator")
        self.root.geometry("1200x750")
        self.root.minsize(1000, 600)
        
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
        
        self.configurar_estilos()
        self.crear_widgets()
        
        self.root.after(100, self.procesar_cola)
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

        left_panel = ttk.Frame(self.root, style="TFrame", padding=10)
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)
        
        control_frame = ttk.Frame(left_panel, style="TFrame")
        control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        control_frame.columnconfigure(5, weight=1)
        
        lbl_modo = ttk.Label(control_frame, text="Modo:", style="TLabel")
        lbl_modo.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")
        
        self.combo_modo = ttk.Combobox(control_frame, values=["APIs de Red (HTTP)", "Grabador DOM (Acciones)", "Scraper Visual (DOM)"], state="readonly", width=22, font=("Segoe UI", 9))
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
        
        self.chk_cdp = ttk.Checkbutton(
            control_frame, 
            text="Conectar a navegador abierto (CDP)", 
            variable=self.config_usar_cdp,
            command=self.on_toggle_cdp,
            style="TCheckbutton"
        )
        self.chk_cdp.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        
        self.lbl_puerto_cdp = ttk.Label(control_frame, text="Puerto CDP:", style="TLabel")
        self.lbl_puerto_cdp.grid(row=1, column=2, padx=(10, 5), pady=5, sticky="w")
        
        self.entry_puerto_cdp = ttk.Entry(control_frame, textvariable=self.config_puerto_cdp, width=8, font=("Segoe UI", 9))
        self.entry_puerto_cdp.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        self.entry_puerto_cdp.state(["disabled"])
        
        self.btn_ayuda_cdp = ttk.Button(
            control_frame, 
            text="❓ Ayuda", 
            width=8,
            command=self.mostrar_ayuda_cdp
        )
        self.btn_ayuda_cdp.grid(row=1, column=4, padx=5, pady=5, sticky="w")
        
        self.btn_lanzar_cdp = ttk.Button(
            control_frame, 
            text="🚀 Auto-Lanzar", 
            command=self.lanzar_navegador_cdp_gui
        )
        self.btn_lanzar_cdp.grid(row=1, column=5, padx=5, pady=5, sticky="w")
        self.btn_lanzar_cdp.state(["disabled"])
        
        buttons_subframe = ttk.Frame(control_frame, style="TFrame")
        buttons_subframe.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        
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
        self.tabla.bind("<Button-3>", self.mostrar_menu_contextual)

        self.tabla.tag_configure("par", background=self.color_panel)
        self.tabla.tag_configure("impar", background=self.color_bg)

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

        self.frame_arbol_json = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.frame_arbol_json, text="🌳 Árbol JSON")
        self.frame_arbol_json.columnconfigure(0, weight=1)
        self.frame_arbol_json.rowconfigure(0, weight=1)

        self.frame_red_scraper = ttk.Frame(self.notebook, style="Panel.TFrame", padding=6)
        self.notebook.add(self.frame_red_scraper, text="🌐 Red POST")
        self.peticiones_red_post = []

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

        self.frame_config_scraper = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(self.frame_config_scraper, text="⚙️ Config Scraper")
        self.frame_config_scraper.rowconfigure(0, weight=1)
        self.frame_config_scraper.columnconfigure(0, weight=1)

        _cs_canvas = tk.Canvas(self.frame_config_scraper, highlightthickness=0,
                               bg=self.color_panel)
        _cs_scroll = ttk.Scrollbar(self.frame_config_scraper, orient="vertical",
                                   command=_cs_canvas.yview)
        _cs_canvas.configure(yscrollcommand=_cs_scroll.set)
        _cs_canvas.grid(row=0, column=0, sticky="nsew")
        _cs_scroll.grid(row=0, column=1, sticky="ns")

        _cs_inner = ttk.Frame(_cs_canvas, style="Panel.TFrame", padding=12)
        _cs_window = _cs_canvas.create_window((0, 0), window=_cs_inner, anchor="nw")

        def _on_cs_inner_configure(event):
            _cs_canvas.configure(scrollregion=_cs_canvas.bbox("all"))
        _cs_inner.bind("<Configure>", _on_cs_inner_configure)

        def _on_cs_canvas_configure(event):
            _cs_canvas.itemconfig(_cs_window, width=event.width)
        _cs_canvas.bind("<Configure>", _on_cs_canvas_configure)

        def _on_cs_mousewheel(event):
            _cs_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        _cs_canvas.bind("<Enter>", lambda e: _cs_canvas.bind_all("<MouseWheel>", _on_cs_mousewheel))
        _cs_canvas.bind("<Leave>", lambda e: _cs_canvas.unbind_all("<MouseWheel>"))

        self._cs_inner = _cs_inner

        ttk.Label(_cs_inner, text="🕷️ CONFIGURACIÓN DEL SCRAPER",
                  style="Header.TLabel").pack(anchor="w", pady=(0, 8))

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

        self.frame_bs4_login = ttk.LabelFrame(
            _cs_inner, text="Login BS4 (opcional)", padding=8)

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

        self.notebook.hide(self.frame_arbol_json)
        self.notebook.hide(self.frame_config_scraper)
        self.notebook.hide(self.frame_red_scraper)

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

        else:
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
            try:
                self.notebook.hide(self.frame_arbol_json)
            except Exception:
                pass
            try:
                self.notebook.add(self.frame_config_scraper)
                self.notebook.tab(self.frame_config_scraper, text="⚙️ Config Scraper")
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
            puerto_cdp=puerto_cdp_val
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
                    elif tipo == "post_red_scraper":
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
                        self.tabla_red_post.selection_set(str(idx_r))
                        self.tabla_red_post.see(str(idx_r))
                        self.on_post_seleccionado()
                    elif tipo == "accion_dom":
                        modo_actual = self.combo_modo.get()

                        if "Scraper" in modo_actual:
                            tipo_accion = dato.get("tipo_accion", "")
                            fase = dato.get("fase_scraper", "setup" if tipo_accion != "extract" else "extract")

                            if tipo_accion == "extract":
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
                        self.chk_cdp.state(["!disabled"])
                        self.on_toggle_cdp()
                        self.btn_stop.state(["disabled"])
                        self.btn_pause.state(["disabled"])
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
                
        if selected_idx and self.tabla.exists(selected_idx):
            self.tabla.selection_set(selected_idx)

    def on_peticion_seleccionada(self, event):
        seleccion = self.tabla.selection()
        if not seleccion:
            self.limpiar_detalles()
            return

        idx = int(seleccion[0])
        pet = self.peticiones_capturadas[idx]
        modo = self.combo_modo.get()

        if self.capture_thread and self.capture_thread.is_alive() and ("Grabador" in modo or "Scraper" in modo):
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

        elif "Scraper" in modo:
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
        motor = self.scraper_motor.get() if hasattr(self, "scraper_motor") else "playwright"
        tiene_setup = any(p.get("fase_scraper") == "setup" for p in self.peticiones_capturadas)

        if motor == "bs4":
            if hasattr(self, "frame_bs4_login"):
                self.frame_bs4_login.pack(fill="x", pady=4)
            if tiene_setup and hasattr(self, "lbl_motor_aviso"):
                self.lbl_motor_aviso.pack(anchor="w", pady=(0, 2))
        else:
            if hasattr(self, "frame_bs4_login"):
                self.frame_bs4_login.pack_forget()
            if hasattr(self, "lbl_motor_aviso"):
                self.lbl_motor_aviso.pack_forget()

    def on_post_seleccionado(self, event=None):
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

        auth_tipo   = "form_post"
        user_field  = "username"
        pass_field  = "password"
        token_field = "token"

        if isinstance(body, dict):
            auth_tipo = "json_post"
            for k in body:
                if any(p in k.lower() for p in ["user", "login", "email", "correo", "usuario"]):
                    user_field = k
                    break
            for k in body:
                if any(p in k.lower() for p in ["pass", "clave", "secret", "pwd", "contrasena", "contrase"]):
                    pass_field = k
                    break
        elif isinstance(body, str) and "=" in body:
            auth_tipo = "form_post"

        if isinstance(response, dict):
            for k in response:
                if any(p in k.lower() for p in ["token", "access", "jwt", "auth", "bearer"]):
                    token_field = k
                    auth_tipo = "bearer_token"
                    break

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
        is_api = "APIs" in modo
        is_scraper = "Scraper" in modo

        if is_scraper:
            url_obj = self.entry_url.get().strip()
            motor   = getattr(self, "scraper_motor", None)
            motor   = motor.get() if motor else "playwright"

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

    def abrir_configuracion(self):
        config_win = tk.Toplevel(self.root)
        config_win.title("Configuración Avanzada")
        config_win.geometry("520x630")
        config_win.resizable(False, False)
        config_win.configure(bg=self.color_bg)
        config_win.transient(self.root)
        config_win.grab_set()
        
        config_win.update_idletasks()
        w = config_win.winfo_width()
        h = config_win.winfo_height()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        config_win.geometry(f"+{x}+{y}")
        
        lbl_titulo = ttk.Label(config_win, text="⚙️ CONFIGURACIÓN AVANZADA", style="Header.TLabel", padding=15)
        lbl_titulo.pack(anchor="w")

        main_frame = ttk.Frame(config_win, style="TFrame")
        main_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

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

        ua_frame = ttk.LabelFrame(main_frame, text="User-Agent Personalizado (Opcional)", padding=10)
        ua_frame.pack(fill="x", pady=5)

        entry_ua = ttk.Entry(ua_frame, textvariable=self.config_user_agent, font=("Segoe UI", 9))
        entry_ua.pack(fill="x", pady=2)

        info_frame = ttk.LabelFrame(main_frame, text="Aplicación y Actualizaciones", padding=10)
        info_frame.pack(fill="x", pady=5)
        info_frame.columnconfigure(0, weight=1)

        lbl_ver = ttk.Label(info_frame, text=f"Versión Actual: v{VERSION_LOCAL}", font=("Segoe UI", 9, "bold"))
        lbl_ver.grid(row=0, column=0, sticky="w", pady=2)

        btn_chk_update = ttk.Button(info_frame, text="🔄 Buscar Actualizaciones", command=lambda: verificar_actualizaciones(self, manual=True))
        btn_chk_update.grid(row=0, column=1, sticky="e", pady=2)

        btn_save = ttk.Button(config_win, text="Guardar y Cerrar", style="Accent.TButton", command=config_win.destroy)
        btn_save.pack(anchor="e", padx=15, pady=(0, 15))
