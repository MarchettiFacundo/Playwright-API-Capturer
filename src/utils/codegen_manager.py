import os
import re
import subprocess
from typing import List, Dict, Any, Optional

DISPOSITIVOS_CODEGEN = [
    "Ninguno (Por Defecto)",
    "iPhone 14",
    "iPhone 14 Pro Max",
    "iPhone 13",
    "iPhone SE",
    "iPad Pro 11",
    "iPad (gen 7)",
    "Pixel 7",
    "Galaxy S9+",
]

LENGUAJES_CODEGEN = [
    ("Python (Sincrónico)", "python"),
    ("Python (Asincrónico)", "python-async"),
    ("Pytest", "python-pytest"),
    ("JavaScript", "javascript"),
]

def obtener_comando_driver():
    """
    Obtiene la ruta o tupla del ejecutable de Playwright Driver utilizando
    la implementación interna oficial de la librería playwright en Python.
    """
    try:
        from playwright._impl._driver import compute_driver_executable
        driver_exec = compute_driver_executable()
        if isinstance(driver_exec, (list, tuple)):
            return list(driver_exec)
        else:
            return [driver_exec]
    except Exception:
        import sys
        return [sys.executable, "-m", "playwright"]

def lanzar_playwright_codegen(
    url: str = "",
    browser: str = "Chromium",
    target: str = "python",
    output_file: Optional[str] = None,
    device: Optional[str] = None,
    save_storage: Optional[str] = None,
    load_storage: Optional[str] = None,
    viewport_width: Optional[int] = None,
    viewport_height: Optional[int] = None,
    ignore_https_errors: bool = True,
    timeout_sec: Optional[int] = None,
    canal_edge: bool = False
) -> subprocess.Popen:
    """
    Lanza el proceso de Playwright Codegen con los parámetros configurados.
    Retorna el objeto subprocess.Popen correspondiente.
    """
    cmd = obtener_comando_driver() + ["codegen"]

    # Target de lenguaje
    if target:
        cmd.extend(["--target", target])

    # Navegador / Canal
    browser_lower = (browser or "chromium").lower()
    if canal_edge or "edge" in browser_lower:
        cmd.extend(["--channel", "msedge"])
    elif "firefox" in browser_lower:
        cmd.extend(["-b", "firefox"])
    elif "webkit" in browser_lower or "safari" in browser_lower:
        cmd.extend(["-b", "webkit"])
    else:
        cmd.extend(["-b", "chromium"])

    # Archivo de salida de script
    if output_file and output_file.strip():
        cmd.extend(["-o", os.path.abspath(output_file.strip())])

    # Dispositivo a emular
    if device and device.strip() and device != "Ninguno (Por Defecto)":
        cmd.extend(["--device", device.strip()])
    elif viewport_width and viewport_height and viewport_width > 0 and viewport_height > 0:
        cmd.extend(["--viewport-size", f"{viewport_width},{viewport_height}"])

    # Guardar / Cargar sesión (storage state)
    if save_storage and save_storage.strip():
        cmd.extend(["--save-storage", os.path.abspath(save_storage.strip())])
    if load_storage and load_storage.strip() and os.path.exists(load_storage.strip()):
        cmd.extend(["--load-storage", os.path.abspath(load_storage.strip())])

    # Ignorar errores HTTPS
    if ignore_https_errors:
        cmd.append("--ignore-https-errors")

    # Timeout
    if timeout_sec and timeout_sec > 0:
        cmd.extend(["--timeout", str(timeout_sec * 1000)])

    # URL inicial
    if url and url.strip():
        cmd.append(url.strip())

    # Ejecutar en segundo plano de forma no bloqueante
    proceso = subprocess.Popen(
        cmd,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return proceso

def simplificar_locator(locator_str: str) -> str:
    """Extrae una descripción amigable a partir de una llamada locator de Playwright."""
    if not locator_str:
        return "Elemento"
    m_role = re.search(r'get_by_role\((["\'])(.*?)\1(?:,\s*name=(["\'])(.*?)\3)?', locator_str)
    if m_role:
        rol = m_role.group(2)
        nombre = m_role.group(4) or ""
        return f"{rol.capitalize()} '{nombre}'" if nombre else f"Rol {rol}"

    m_placeholder = re.search(r'get_by_placeholder\((["\'])(.*?)\1', locator_str)
    if m_placeholder:
        return f"Campo [{m_placeholder.group(2)}]"

    m_label = re.search(r'get_by_label\((["\'])(.*?)\1', locator_str)
    if m_label:
        return f"Etiqueta '{m_label.group(2)}'"

    m_text = re.search(r'get_by_text\((["\'])(.*?)\1', locator_str)
    if m_text:
        return f"Texto '{m_text.group(2)}'"

    m_loc = re.search(r'locator\((["\'])(.*?)\1', locator_str)
    if m_loc:
        return f"Selector '{m_loc.group(2)}'"

    return locator_str.replace("page.", "")

def descomponer_locator_iframe(loc_str: str):
    """
    Descompone un locator de Playwright que interactúa dentro de iframes mediante
    .content_frame o .frame_locator(...).
    Extrae la lista jerárquica de selectores de iframes y normaliza selectores efímeros
    (por ejemplo, SAP ITS itsframe con timestamps aleatorios).
    Retorna (ruta_iframes, selector_interior_limpio).
    """
    if not loc_str:
        return [], loc_str
    ruta_iframes = []
    resto = loc_str.strip()
    
    # 1. Normalización preventiva de selectores efímeros de SAP ITS WebGUI
    resto = re.sub(r'iframe\[name=["\']itsframe\d*_\d+.*?["\']\]', 'iframe[name*="itsframe" i]', resto, flags=re.IGNORECASE)
    resto = re.sub(r'iframe\[id=["\']itsframe\d*_\d+.*?["\']\]', 'iframe[id*="itsframe" i]', resto, flags=re.IGNORECASE)
    
    # 2. Descomponer iframes anidados (.content_frame o .frame_locator)
    patron = re.compile(r'^(?:page\.)?(?:locator\((["\'])(.*?)\1\)\.content_frame|frame_locator\((["\'])(.*?)\3\))\.(.+)$')
    
    while True:
        m = patron.match(resto)
        if not m:
            break
        sel_iframe = (m.group(2) or m.group(4) or "").strip()
        resto = m.group(5).strip()
        if "itsframe" in sel_iframe.lower():
            sel_iframe = 'iframe[name*="itsframe" i]'
        ruta_iframes.append(sel_iframe)
        if not resto.startswith("page."):
            resto = "page." + resto

    if not resto.startswith("page.") and not resto.startswith("p."):
        resto = "page." + resto

    return ruta_iframes, resto

def parsear_script_codegen(contenido_o_ruta: str) -> List[Dict[str, Any]]:
    """
    Analiza un script generado por Playwright Codegen (texto o ruta de archivo)
    y lo convierte en una lista de diccionarios compatibles con las acciones DOM de la aplicación.
    Soporta navegación profunda en iframes (SAP WebGUI, pasarelas de pago, etc.).
    """
    if os.path.exists(contenido_o_ruta):
        try:
            with open(contenido_o_ruta, "r", encoding="utf-8") as f:
                lineas = f.readlines()
        except Exception:
            with open(contenido_o_ruta, "r", encoding="latin-1") as f:
                lineas = f.readlines()
    else:
        lineas = contenido_o_ruta.splitlines()

    acciones = []

    for linea in lineas:
        l = linea.strip()
        if not l or l.startswith("#") or l.startswith("import ") or l.startswith("from "):
            continue

        # 1. Navegación: page.goto("url")
        m_goto = re.search(r'page\.goto\((["\'])(.*?)\1', l)
        if m_goto:
            url = m_goto.group(2)
            acciones.append({
                "tipo_accion": "navigation",
                "fase_scraper": "setup",
                "tagName": "WINDOW",
                "descriptor_legible": f"Navegar a {url}",
                "selector_sugerido": "",
                "valor": url,
                "id": "", "name": "", "className": "",
                "type": "", "placeholder": "",
                "xpath": "", "outerHTML": "",
                "seleccionado": True,
                "ruta_iframes": []
            })
            continue

        # 2. Clic: page....click()
        m_click = re.search(r'(page\..+?)\.click\(', l)
        if m_click:
            loc_raw = m_click.group(1).strip()
            r_iframes, loc = descomponer_locator_iframe(loc_raw)
            desc = simplificar_locator(loc)
            if r_iframes:
                desc = f"[{' -> '.join(r_iframes)}] {desc}"
            acciones.append({
                "tipo_accion": "click",
                "fase_scraper": "setup",
                "tagName": "ELEMENT",
                "descriptor_legible": f"Clic en {desc}",
                "selector_sugerido": loc,
                "valor": "",
                "id": "", "name": "", "className": "",
                "type": "", "placeholder": "",
                "xpath": "", "outerHTML": "",
                "seleccionado": True,
                "ruta_iframes": r_iframes
            })
            continue

        # 3. Llenar campo: page....fill("valor")
        m_fill = re.search(r'(page\..+?)\.fill\((["\'])(.*?)\2', l)
        if m_fill:
            loc_raw = m_fill.group(1).strip()
            val = m_fill.group(3)
            r_iframes, loc = descomponer_locator_iframe(loc_raw)
            desc = simplificar_locator(loc)
            if r_iframes:
                desc = f"[{' -> '.join(r_iframes)}] {desc}"
            acciones.append({
                "tipo_accion": "fill",
                "fase_scraper": "setup",
                "tagName": "INPUT",
                "descriptor_legible": f"Escribir '{val}' en {desc}",
                "selector_sugerido": loc,
                "valor": val,
                "id": "", "name": "", "className": "",
                "type": "text", "placeholder": "",
                "xpath": "", "outerHTML": "",
                "seleccionado": True,
                "ruta_iframes": r_iframes
            })
            continue

        # 4. Seleccionar opción: page....select_option("...")
        m_sel = re.search(r'(page\..+?)\.select_option\((["\'])(.*?)\2', l)
        if m_sel:
            loc_raw = m_sel.group(1).strip()
            val = m_sel.group(3)
            r_iframes, loc = descomponer_locator_iframe(loc_raw)
            desc = simplificar_locator(loc)
            if r_iframes:
                desc = f"[{' -> '.join(r_iframes)}] {desc}"
            acciones.append({
                "tipo_accion": "change",
                "fase_scraper": "setup",
                "tagName": "SELECT",
                "descriptor_legible": f"Seleccionar '{val}' en {desc}",
                "selector_sugerido": loc,
                "valor": val,
                "id": "", "name": "", "className": "",
                "type": "select-one", "placeholder": "",
                "xpath": "", "outerHTML": "",
                "seleccionado": True,
                "ruta_iframes": r_iframes
            })
            continue

        # 5. Check / Uncheck
        m_chk = re.search(r'(page\..+?)\.(check|uncheck)\(', l)
        if m_chk:
            loc_raw = m_chk.group(1).strip()
            accion_chk = m_chk.group(2)
            r_iframes, loc = descomponer_locator_iframe(loc_raw)
            desc = simplificar_locator(loc)
            if r_iframes:
                desc = f"[{' -> '.join(r_iframes)}] {desc}"
            acciones.append({
                "tipo_accion": "click",
                "fase_scraper": "setup",
                "tagName": "INPUT",
                "descriptor_legible": f"{'Marcar' if accion_chk == 'check' else 'Desmarcar'} {desc}",
                "selector_sugerido": loc,
                "valor": accion_chk,
                "id": "", "name": "", "className": "",
                "type": "checkbox", "placeholder": "",
                "xpath": "", "outerHTML": "",
                "seleccionado": True,
                "ruta_iframes": r_iframes
            })
            continue

        # 6. Presionar tecla: page....press("Enter")
        m_press = re.search(r'(page\..+?)\.press\((["\'])(.*?)\2', l)
        if m_press:
            loc_raw = m_press.group(1).strip()
            tecla = m_press.group(3)
            r_iframes, loc = descomponer_locator_iframe(loc_raw)
            desc = simplificar_locator(loc)
            if r_iframes:
                desc = f"[{' -> '.join(r_iframes)}] {desc}"
            acciones.append({
                "tipo_accion": "key",
                "fase_scraper": "setup",
                "tagName": "INPUT",
                "descriptor_legible": f"Presionar [{tecla}] en {desc}",
                "selector_sugerido": loc,
                "valor": tecla,
                "id": "", "name": "", "className": "",
                "type": "", "placeholder": "",
                "xpath": "", "outerHTML": "",
                "seleccionado": True,
                "ruta_iframes": r_iframes
            })
            continue

        # 7. Aserción de visibilidad: expect(page....).to_be_visible()
        m_vis = re.search(r'expect\((page\..+?)\)\.to_be_visible\(', l)
        if m_vis:
            loc_raw = m_vis.group(1).strip()
            r_iframes, loc = descomponer_locator_iframe(loc_raw)
            desc = simplificar_locator(loc)
            if r_iframes:
                desc = f"[{' -> '.join(r_iframes)}] {desc}"
            acciones.append({
                "tipo_accion": "assert_visible",
                "fase_scraper": "setup",
                "tagName": "ASSERTION",
                "descriptor_legible": f"Validar visibilidad: {desc}",
                "selector_sugerido": loc,
                "valor": "visible",
                "id": "", "name": "", "className": "",
                "type": "", "placeholder": "",
                "xpath": "", "outerHTML": "",
                "seleccionado": True,
                "ruta_iframes": r_iframes
            })
            continue

        # 8. Aserción de texto: expect(page....).to_have_text(...) o to_contain_text(...)
        m_txt = re.search(r'expect\((page\..+?)\)\.(?:to_have_text|to_contain_text)\((["\'])(.*?)\2', l)
        if m_txt:
            loc_raw = m_txt.group(1).strip()
            txt_esperado = m_txt.group(3)
            r_iframes, loc = descomponer_locator_iframe(loc_raw)
            desc = simplificar_locator(loc)
            if r_iframes:
                desc = f"[{' -> '.join(r_iframes)}] {desc}"
            acciones.append({
                "tipo_accion": "assert_text",
                "fase_scraper": "setup",
                "tagName": "ASSERTION",
                "descriptor_legible": f"Validar texto '{txt_esperado}' en {desc}",
                "selector_sugerido": loc,
                "valor": txt_esperado,
                "id": "", "name": "", "className": "",
                "type": "", "placeholder": "",
                "xpath": "", "outerHTML": "",
                "seleccionado": True,
                "ruta_iframes": r_iframes
            })
            continue

    return acciones

