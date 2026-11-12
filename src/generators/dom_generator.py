import os
import json
import re

def resolver_locator_playwright(selector):
    """
    Mapea selectores semánticos especiales a llamadas de Locators nativos de Playwright Python.
    """
    if not selector:
        return "page"
    if selector.startswith("page."):
        return selector
    if selector.startswith("role:"):
        try:
            role_part, name_part = selector[5:].split("[name=", 1)
            role_name = role_part.strip()
            name_val = name_part.rstrip("]").strip('"\'')
            name_val_escaped = name_val.replace('"', '\\"')
            return f'page.get_by_role("{role_name}", name="{name_val_escaped}")'
        except Exception:
            pass
    elif selector.startswith("placeholder="):
        val = selector[12:].strip('"\'')
        val_escaped = val.replace('"', '\\"')
        return f'page.get_by_placeholder("{val_escaped}")'
    elif selector.startswith("label="):
        val = selector[6:].strip('"\'')
        val_escaped = val.replace('"', '\\"')
        return f'page.get_by_label("{val_escaped}")'
    elif selector.startswith("text="):
        val = selector[5:].strip('"\'')
        val_escaped = val.replace('"', '\\"')
        return f'page.get_by_text("{val_escaped}")'
    elif selector.startswith("id="):
        id_val = selector[3:]
        return f'page.locator(\'[id="{id_val}"]\')'
        
    return f'page.locator({repr(selector)})'

def selector_a_lambda_str(selector_str):
    """
    Convierte cualquier selector (Codegen, selector semántico o selector web estándar)
    a una expresión de función lambda nativa de Playwright: lambda p: p.<locator>
    """
    if not selector_str:
        return "lambda p: p"
    s = selector_str.strip()
    if s.startswith("page."):
        return f"lambda p: p.{s[5:]}"
    if s.startswith("p."):
        return f"lambda p: {s}"
    if s.startswith("role:"):
        loc = resolver_locator_playwright(s)
        return f"lambda p: p.{loc[5:]}" if loc.startswith("page.") else f"lambda p: p.locator({repr(s)})"
    if s.startswith("xpath="):
        return f"lambda p: p.locator({repr(s)})"
    if s.startswith("id="):
        return f"lambda p: p.locator('[id=\"{s[3:]}\"]')"
    if s.startswith("placeholder="):
        val = s[12:].strip('\"\'')
        return f"lambda p: p.get_by_placeholder({repr(val)})"
    if s.startswith("label="):
        val = s[6:].strip('\"\'')
        return f"lambda p: p.get_by_label({repr(val)})"
    if s.startswith("text="):
        val = s[5:].strip('\"\'')
        return f"lambda p: p.get_by_text({repr(val)})"
    return f"lambda p: p.locator({repr(s)})"

def generar_script_automatizacion_dom(acciones_seleccionadas, nombre_archivo="automatizacion_dom.py", parametrizar=False, storage_state="", incluir_trace=False, ruta_trace="trace_automatizacion.zip", incluir_video=False, dir_video="videos_automatizacion", modo_resiliente=True, http_user="", http_password=""):
    """
    Genera un script ejecutable de Playwright en Python que automatiza secuencialmente
    las acciones e interacciones grabadas sobre el DOM (clics, ingresos de texto, aserciones, etc.).
    Si modo_resiliente=True, inyecta funciones de auto-cierre de modales/cookies, sondeo rápido
    multi-selector (Fast-Scan sin bloqueos) y tolerancia a cambios en IDs dinámicos.
    """
    es_resiliente = modo_resiliente

    codigo = []
    codigo.append("from playwright.sync_api import sync_playwright, expect")
    codigo.append("import time")
    codigo.append("import re")
    tiene_archivos = any(a.get("tipo_accion") in ("upload", "file_upload", "download") for a in acciones_seleccionadas)
    if parametrizar or es_resiliente or (http_user and http_password) or tiene_archivos or incluir_video:
        codigo.append("import os")
    codigo.append("")

    es_sap = any(
        "sap" in str(a.get("valor", "")).lower()
        or "sap" in str(a.get("selector_sugerido", "")).lower()
        or "itsframe" in str(a.get("selector_sugerido", "")).lower()
        or any("itsframe" in str(ifr).lower() for ifr in a.get("ruta_iframes", []))
        for a in acciones_seleccionadas
    )
    timeout_val = 30000 if es_sap else 8000

    if es_resiliente:
        codigo.append("# =============================================================================")
        codigo.append("# HELPERS DE RESILIENCIA RPA (FAST-SCAN MULTI-SELECTOR Y AUTO-CIERRE DE MODALES)")
        codigo.append("# =============================================================================")
        codigo.append("SELECTOR_MODALES_COMBINADO = (")
        codigo.append("    '#onetrust-accept-btn-handler, '")
        codigo.append("    '[id*=\"cookie\" i] button, [class*=\"cookie\" i] button, '")
        codigo.append("    '[id*=\"consent\" i] button, [class*=\"consent\" i] button, '")
        codigo.append("    '[role=\"dialog\"] button[aria-label*=\"close\" i], '")
        codigo.append("    '[role=\"dialog\"] button[aria-label*=\"cerrar\" i], '")
        codigo.append("    '[role=\"dialog\"] button.close, [role=\"dialog\"] .modal-close, '")
        codigo.append("    'button[data-dismiss=\"modal\"], button[data-bs-dismiss=\"modal\"], '")
        codigo.append("    '[aria-modal=\"true\"] button[aria-label*=\"close\" i], '")
        codigo.append("    '[aria-modal=\"true\"] button[aria-label*=\"cerrar\" i], '")
        codigo.append("    '.modal.show button.close, '")
        codigo.append("    'button[aria-label=\"Cerrar\"], button[aria-label=\"Close\"]'")
        codigo.append(")")
        codigo.append("")
        codigo.append("def cerrar_modales_y_banners(page, timeout_ms=800):")
        codigo.append('    """Detecta y descarta banners de cookies o modales emergentes en una sola consulta rápida."""')
        codigo.append("    try:")
        codigo.append("        loc = page.locator(SELECTOR_MODALES_COMBINADO).locator('visible=true').first")
        codigo.append("        if loc.is_visible():")
        codigo.append("            print('      [RESILIENTE] Banner o modal obstructivo detectado. Cerrando...')")
        codigo.append("            loc.click(timeout=timeout_ms)")
        codigo.append("            page.wait_for_timeout(200)")
        codigo.append("            return True")
        codigo.append("    except Exception:")
        codigo.append("        pass")
        codigo.append("    return False")
        codigo.append("")
        codigo.append("def _construir_locator(target, sel):")
        codigo.append('    """Convierte un selector (string semántico, CSS, XPath o lambda) en un Locator de Playwright."""')
        codigo.append("    if callable(sel):")
        codigo.append("        return sel(target)")
        codigo.append("    if not isinstance(sel, str):")
        codigo.append("        return sel")
        codigo.append("    s = sel.strip()")
        codigo.append("    if s.startswith('role:'):")
        codigo.append("        try:")
        codigo.append("            role_part, name_part = s[5:].split('[name=', 1)")
        codigo.append("            role_name = role_part.strip()")
        codigo.append("            name_val = name_part.rstrip(']').strip('\"\\'')")
        codigo.append("            return target.get_by_role(role_name, name=name_val)")
        codigo.append("        except Exception:")
        codigo.append("            return target.locator(s)")
        codigo.append("    if s.startswith('page.') or s.startswith('p.') or s.startswith('target.'):")
        codigo.append("        expr_limpia = s.replace('page.', 'target.', 1).replace('p.', 'target.', 1)")
        codigo.append("        if 'itsframe' in expr_limpia.lower():")
        codigo.append("            expr_limpia = re.sub(r'iframe\\[name=[\"\\\']itsframe\\d*_\\d+.*?[\"\\\']\\]', 'iframe[name*=\"itsframe\" i]', expr_limpia, flags=re.IGNORECASE)")
        codigo.append("            expr_limpia = re.sub(r'iframe\\[id=[\"\\\']itsframe\\d*_\\d+.*?[\"\\\']\\]', 'iframe[id*=\"itsframe\" i]', expr_limpia, flags=re.IGNORECASE)")
        codigo.append("        return eval(expr_limpia, {'target': target})")
        codigo.append("    if s.startswith('get_by_') or s.startswith('locator('):")
        codigo.append("        return eval(f'target.{s}', {'target': target})")
        codigo.append("    if s.startswith('xpath='):")
        codigo.append("        return target.locator(s)")
        codigo.append("    if s.startswith('text='):")
        codigo.append("        return target.get_by_text(s[5:].strip('\"\\''))")
        codigo.append("    if s.startswith('id='):")
        codigo.append("        return target.locator(f'[id=\"{s[3:]}\"]')")
        codigo.append("    if s.startswith('placeholder='):")
        codigo.append("        return target.get_by_placeholder(s[12:].strip('\"\\''))")
        codigo.append("    if s.startswith('label='):")
        codigo.append("        return target.get_by_label(s[6:].strip('\"\\''))")
        codigo.append("    return target.locator(s)")
        codigo.append("")
        codigo.append("def _ejecutar_sobre_locator(page, target, loc, sel, tipo_accion, valor, desc, timeout_accion):")
        codigo.append('    """Ejecuta la interacción solicitada sobre un locator ya localizado."""')
        codigo.append("    if tipo_accion == 'click':")
        codigo.append("        loc.click(timeout=timeout_accion)")
        codigo.append("        if any(x in str(sel).lower() for x in ['tbl', '[id*=\"[\"', '_c']):")
        codigo.append("            time.sleep(0.2)")
        codigo.append("    elif tipo_accion == 'fill':")
        codigo.append("        try:")
        codigo.append("            loc.fill(valor or '', timeout=min(timeout_accion, 2500))")
        codigo.append("        except Exception:")
        codigo.append("            _exito = False")
        codigo.append("            try:")
        codigo.append("                _child = loc.locator(\"input, textarea, [contenteditable='true']\").first")
        codigo.append("                if _child.count() > 0:")
        codigo.append("                    _child.fill(valor or '', timeout=min(timeout_accion, 2500))")
        codigo.append("                    _exito = True")
        codigo.append("            except Exception:")
        codigo.append("                pass")
        codigo.append("            if not _exito:")
        codigo.append("                loc.click(timeout=min(timeout_accion, 2500))")
        codigo.append("                time.sleep(0.15)")
        codigo.append("                loc.press_sequentially(valor or '', delay=25)")
        codigo.append("    elif tipo_accion in ('select', 'change'):")
        codigo.append("        loc.select_option(valor or '', timeout=timeout_accion)")
        codigo.append("    elif tipo_accion == 'key':")
        codigo.append("        try:")
        codigo.append("            loc.press(valor or 'Enter', timeout=timeout_accion)")
        codigo.append("        except Exception:")
        codigo.append("            try:")
        codigo.append("                target.keyboard.press(valor or 'Enter')")
        codigo.append("            except Exception:")
        codigo.append("                page.keyboard.press(valor or 'Enter')")
        codigo.append("    elif tipo_accion == 'extract':")
        codigo.append("        raw_text = loc.inner_text(timeout=timeout_accion).strip()")
        codigo.append("        if not raw_text:")
        codigo.append("            try:")
        codigo.append("                raw_text = (loc.input_value(timeout=1000) or '').strip()")
        codigo.append("            except Exception:")
        codigo.append("                pass")
        codigo.append("        if valor and str(valor).strip():")
        codigo.append("            filtro = str(valor).strip()")
        codigo.append(r"            if re.match(r'^\d{2}:\d{2}(?::\d{2})?$', filtro):")
        codigo.append(r"                m_time = re.search(r'\b\d{2}:\d{2}(?::\d{2})?\b', raw_text)")
        codigo.append("                if m_time:")
        codigo.append("                    return m_time.group(0)")
        codigo.append(r"            if re.match(r'^\d{2}[./-]\d{2}[./-]\d{4}$', filtro):")
        codigo.append(r"                m_date = re.search(r'\b\d{2}[./-]\d{2}[./-]\d{4}\b', raw_text)")
        codigo.append("                if m_date:")
        codigo.append("                    return m_date.group(0)")
        codigo.append(r"            if any(tok in filtro for tok in ['(', ')', r'\d', r'\w', r'\s', '[', ']', '.*', '.+']):")
        codigo.append("                try:")
        codigo.append("                    m = re.search(filtro, raw_text)")
        codigo.append("                    if m:")
        codigo.append("                        return m.group(1) if m.groups() else m.group(0)")
        codigo.append("                except Exception:")
        codigo.append("                    pass")
        codigo.append(r"            pat_lbl = rf'(?:^|[\r\n])\s*{re.escape(filtro)}[\s:\n]+([^\r\n]+)'")
        codigo.append("            m_lbl = re.search(pat_lbl, raw_text, re.IGNORECASE)")
        codigo.append("            if m_lbl:")
        codigo.append("                return m_lbl.group(1).strip()")
        codigo.append("            if filtro in raw_text:")
        codigo.append("                return filtro")
        codigo.append("        return raw_text")
        codigo.append("    elif tipo_accion == 'assert_visible':")
        codigo.append("        expect(loc).to_be_visible(timeout=timeout_accion)")
        codigo.append("    elif tipo_accion == 'assert_text':")
        codigo.append("        expect(loc).to_contain_text(valor or '', timeout=timeout_accion)")
        codigo.append("    elif tipo_accion in ('upload', 'file_upload'):")
        codigo.append("        ruta_archivo = os.path.abspath(valor) if isinstance(valor, str) and valor.strip() else valor")
        codigo.append("        if isinstance(ruta_archivo, str) and not os.path.exists(ruta_archivo):")
        codigo.append("            print(f'      [ADVERTENCIA] El archivo no fue encontrado en el disco: {ruta_archivo}')")
        codigo.append("        try:")
        codigo.append("            with page.expect_file_chooser(timeout=min(timeout_accion, 10000)) as fc_info:")
        codigo.append("                loc.click(timeout=timeout_accion)")
        codigo.append("            file_chooser = fc_info.value")
        codigo.append("            file_chooser.set_files(ruta_archivo)")
        codigo.append("            print(f'      [SUBIDA] Archivo cargado exitosamente interceptando file_chooser: {ruta_archivo}')")
        codigo.append("        except Exception as exc_fc:")
        codigo.append("            try:")
        codigo.append("                loc.set_input_files(ruta_archivo, timeout=timeout_accion)")
        codigo.append("                print(f'      [SUBIDA] Archivo asignado directamente al input: {ruta_archivo}')")
        codigo.append("            except Exception:")
        codigo.append("                raise RuntimeError(f\"Error al cargar archivo en '{desc}': {exc_fc}\")")
        codigo.append("    elif tipo_accion == 'download':")
        codigo.append("        try:")
        codigo.append("            with page.expect_download(timeout=max(timeout_accion, 25000)) as dl_info:")
        codigo.append("                loc.click(timeout=timeout_accion)")
        codigo.append("            download = dl_info.value")
        codigo.append("            nombre_destino = valor if valor and str(valor).strip() else download.suggested_filename")
        codigo.append("            ruta_destino = os.path.abspath(nombre_destino)")
        codigo.append("            os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)")
        codigo.append("            download.save_as(ruta_destino)")
        codigo.append("            print(f'      [DESCARGA] Archivo descargado exitosamente en: {ruta_destino}')")
        codigo.append("        except Exception as exc_dl:")
        codigo.append("            raise RuntimeError(f\"Error al descargar archivo en '{desc}': {exc_dl}\")")
        codigo.append("    return True")
        codigo.append("")
        codigo.append(f"def ejecutar_accion_resiliente(page, selectores, tipo_accion, valor=None, desc='', timeout_ms={timeout_val}, ruta_iframes=None):")
        codigo.append('    """')
        codigo.append('    Ejecuta una acción mediante sondeo rápido multi-selector (Fast-Scan).')
        codigo.append('    En lugar de bloquear el timeout completo en cada selector fallido, verifica en milisegundos')
        codigo.append('    cuál de los selectores candidatos ya está visible en el DOM y actúa de inmediato.')
        codigo.append('    """')
        codigo.append("    target = page")
        codigo.append("    if ruta_iframes:")
        codigo.append("        for ifr in ruta_iframes:")
        codigo.append("            target = target.frame_locator(ifr)")
        codigo.append("")
        codigo.append("    # Pre-construir y deduplicar locators candidatos una sola vez")
        codigo.append("    candidatos_loc = []")
        codigo.append("    claves_vistas = set()")
        codigo.append("    for idx_s, sel in enumerate(selectores):")
        codigo.append("        if not sel:")
        codigo.append("            continue")
        codigo.append("        clave_norm = f'[id=\"{sel[3:]}\"]' if isinstance(sel, str) and sel.startswith('id=') else str(sel).strip()")
        codigo.append("        if clave_norm in claves_vistas:")
        codigo.append("            continue")
        codigo.append("        claves_vistas.add(clave_norm)")
        codigo.append("        try:")
        codigo.append("            candidatos_loc.append((idx_s, sel, _construir_locator(target, sel)))")
        codigo.append("        except Exception:")
        codigo.append("            pass")
        codigo.append("")
        codigo.append("    ultimo_error = None")
        codigo.append("    deadline = time.monotonic() + (timeout_ms / 1000.0)")
        codigo.append("    modal_verificado = False")
        codigo.append("    timeout_accion_rapida = min(timeout_ms, 3500)")
        codigo.append("")
        codigo.append("    # Bucle de sondeo rápido (Fast-Scan): revisa todos los selectores sin bloqueos largos")
        codigo.append("    while time.monotonic() < deadline:")
        codigo.append("        for idx_s, sel, base_loc in candidatos_loc:")
        codigo.append("            try:")
        codigo.append("                # Priorizar instancia visible real (evita elementos ocultos o en pantallas de fondo M0 vs M1)")
        codigo.append("                loc_vis = base_loc.locator('visible=true').first")
        codigo.append("                if loc_vis.is_visible():")
        codigo.append("                    res = _ejecutar_sobre_locator(page, target, loc_vis, sel, tipo_accion, valor, desc, timeout_accion_rapida)")
        codigo.append("                    if idx_s > 0:")
        codigo.append("                        print(f'      [FAST-SCAN] Coincidencia inmediata con selector #{idx_s + 1}: {sel}')")
        codigo.append("                    return res")
        codigo.append("            except Exception as ex:")
        codigo.append("                ultimo_error = ex")
        codigo.append("")
        codigo.append("            try:")
        codigo.append("                if base_loc.first.is_visible():")
        codigo.append("                    res = _ejecutar_sobre_locator(page, target, base_loc.first, sel, tipo_accion, valor, desc, timeout_accion_rapida)")
        codigo.append("                    if idx_s > 0:")
        codigo.append("                        print(f'      [FAST-SCAN] Coincidencia inmediata con selector #{idx_s + 1}: {sel}')")
        codigo.append("                    return res")
        codigo.append("            except Exception as ex:")
        codigo.append("                ultimo_error = ex")
        codigo.append("")
        codigo.append("        # Para cargas de archivo (<input type='file'> suele estar oculto), aceptar elemento attached")
        codigo.append("        if tipo_accion in ('upload', 'file_upload'):")
        codigo.append("            for idx_s, sel, base_loc in candidatos_loc:")
        codigo.append("                try:")
        codigo.append("                    if base_loc.count() > 0:")
        codigo.append("                        return _ejecutar_sobre_locator(page, target, base_loc.first, sel, tipo_accion, valor, desc, timeout_accion_rapida)")
        codigo.append("                except Exception as ex:")
        codigo.append("                    ultimo_error = ex")
        codigo.append("")
        codigo.append("        if not modal_verificado:")
        codigo.append("            modal_verificado = True")
        codigo.append("            cerrar_modales_y_banners(page)")
        codigo.append("")
        codigo.append("        time.sleep(0.12)")
        codigo.append("")
        codigo.append("    # Último recurso si expiró el tiempo de visibilidad: probar elementos attached en el DOM")
        codigo.append("    for idx_s, sel, base_loc in candidatos_loc:")
        codigo.append("        try:")
        codigo.append("            if base_loc.count() > 0:")
        codigo.append("                return _ejecutar_sobre_locator(page, target, base_loc.first, sel, tipo_accion, valor, desc, timeout_accion_rapida)")
        codigo.append("        except Exception as ex:")
        codigo.append("            ultimo_error = ex")
        codigo.append("")
        codigo.append("    raise RuntimeError(f\"No se pudo ejecutar '{tipo_accion}' en '{desc}' tras sondear {len(candidatos_loc)} selectores ({timeout_ms}ms). Error: {ultimo_error}\")")
        codigo.append("")

    codigo.append("def ejecutar_flujo_automatizado():")
    codigo.append("    print('[INFO] Iniciando automatización de Playwright...')")
    codigo.append("    variables = {}  # Almacén de variables dinámicas entre pantallas")
    codigo.append("    with sync_playwright() as p:")
    codigo.append("        # Lanzamos el navegador visible (headless=False) para observar las acciones")
    codigo.append("        browser = p.chromium.launch(headless=False)")
    ctx_args = ["ignore_https_errors=True"]
    if storage_state and storage_state.strip():
        ctx_args.append(f"storage_state={repr(storage_state.strip())}")
    if incluir_video:
        ctx_args.append(f"record_video_dir={repr(dir_video)}")
    
    if http_user and http_password:
        if parametrizar:
            codigo.append(f'        _http_u = os.environ.get("HTTP_USER", {repr(http_user.strip())})')
            codigo.append(f'        _http_p = os.environ.get("HTTP_PASS", {repr(http_password.strip())})')
            ctx_args.append('http_credentials={"username": _http_u, "password": _http_p}')
        else:
            ctx_args.append(f'http_credentials={{"username": {repr(http_user.strip())}, "password": {repr(http_password.strip())}}}')
            
    codigo.append(f"        context = browser.new_context({', '.join(ctx_args)})")
    if incluir_trace:
        codigo.append("        # Habilitamos el registro de trazas detalladas (Playwright Trace Viewer)")
        codigo.append("        context.tracing.start(screenshots=True, snapshots=True, sources=True)")
    codigo.append("        page = context.new_page()")
    
    codigo.append(f"        page.set_default_timeout({timeout_val})  # Timeout adaptativo por acción")
    codigo.append("")
    
    for idx, accion in enumerate(acciones_seleccionadas):
        tipo = accion.get("tipo_accion")
        selector = accion.get("selector_sugerido", "")
        ruta_iframes = list(accion.get("ruta_iframes", []))

        # Desacoplar y normalizar iframes si el selector contiene .content_frame o .frame_locator
        if selector and ("content_frame" in selector or "frame_locator" in selector):
            from src.utils.codegen_manager import descomponer_locator_iframe
            r_det, sel_limpio = descomponer_locator_iframe(selector)
            if r_det and not ruta_iframes:
                ruta_iframes = r_det
            selector = sel_limpio

        # Normalizar selectores dinámicos en la ruta de iframes (SAP ITS itsframe con timestamps)
        if ruta_iframes:
            ruta_normalizada = []
            for ifr in ruta_iframes:
                if "itsframe" in ifr.lower():
                    ruta_normalizada.append("iframe[name*='itsframe' i]")
                else:
                    ruta_normalizada.append(ifr)
            ruta_iframes = ruta_normalizada

        if tipo == "extract" and accion.get("xpath"):
            selector = "xpath=" + accion.get("xpath")
        valor = accion.get("valor", "")
        desc = accion.get("descriptor_legible", f"Paso {idx + 1}")
        
        locator_str = resolver_locator_playwright(selector)
        if ruta_iframes:
            prefijo_frames = ""
            for iframe_sel in ruta_iframes:
                prefijo_frames += f".frame_locator({repr(iframe_sel)})"
            if locator_str.startswith("page"):
                locator_str = "page" + prefijo_frames + locator_str[4:]

        # Recolectar lista ordenada y priorizada de selectores de respaldo para modo resiliente
        candidatos = []
        candidatos_vistos = set()
        candidatos_lambdas = []
        candidatos_lambdas_vistos = set()

        def _agregar_candidato_ambos(sel_raw):
            if not sel_raw or not str(sel_raw).strip():
                return
            s_limpio = str(sel_raw).strip()
            # Normalizar id=foo a [id="foo"] para evitar duplicados idénticos
            if s_limpio.startswith("id="):
                s_limpio = f'[id="{s_limpio[3:]}"]'
            if s_limpio not in candidatos_vistos:
                candidatos.append(s_limpio)
                candidatos_vistos.add(s_limpio)
            l_str = selector_a_lambda_str(s_limpio)
            if l_str not in candidatos_lambdas_vistos:
                candidatos_lambdas.append(l_str)
                candidatos_lambdas_vistos.add(l_str)

        # 1. Metadatos de SAP para priorizar de forma certera
        outer_html = accion.get("outerHTML", "")
        raw_id = accion.get("id", "")
        sugerido_orig = selector or ""
        
        # Detección de coordenadas de tabla SAP [fila,columna]
        m_coord = re.search(r'\[(\d+,\d+)\]', raw_id or sugerido_orig or outer_html)
        # Identificador técnico ABAP en lsdata (SLOW_I[1,0], etc.)
        m_slow = re.search(r'(SLOW_[A-Z0-9_]+\[\d+,\d+\])', outer_html)
        # Detección de ventana modal wnd[1] / M1: vs ventana principal
        es_modal_sap = "wnd[1]" in outer_html or (raw_id and raw_id.startswith("M1:")) or (sugerido_orig and "M1:" in sugerido_orig)
        es_main_sap = "wnd[0]" in outer_html or (raw_id and raw_id.startswith("M0:")) or (sugerido_orig and "M0:" in sugerido_orig)
        # Identificador con :: (botones, menús, etc.)
        cadena_busqueda_btn = raw_id or sugerido_orig
        partes_dos_puntos = cadena_busqueda_btn.split("::") if "::" in cadena_busqueda_btn else []
        sufijo_btn = ""
        if len(partes_dos_puntos) > 1:
            sufijo_btn = partes_dos_puntos[-1].strip()
            sufijo_btn = re.sub(r'["\']\]$', '', sufijo_btn).strip('"\'\\ ')

        # A. Si es celda de tabla SAP, priorizar el ID exacto y el selector universal [id*="[f,c]_c"]
        if m_coord:
            coord = m_coord.group(1)
            tag_real = (accion.get("tagName") or "").lower()

            # 1) ID exacto capturado (ej: [id="tbl2[2,2]_c"]) y comodín de celda _c (funciona tanto en span como en input)
            if raw_id:
                _agregar_candidato_ambos(f'[id="{raw_id}"]')
            _agregar_candidato_ambos(f'[id*="[{coord}]_c"]')

            # 2) Según tipo de acción o tag capturado, priorizar el tag real antes de alternativas
            if tipo == "fill":
                _agregar_candidato_ambos(f'input[id*="[{coord}]_c"]')
                _agregar_candidato_ambos(f'td[id*="[{coord}]"] input')
            elif tag_real in ("span", "div", "td"):
                _agregar_candidato_ambos(f'{tag_real}[id*="[{coord}]_c"]')
                _agregar_candidato_ambos(f'input[id*="[{coord}]_c"]')
            else:
                _agregar_candidato_ambos(f'input[id*="[{coord}]_c"]')
                _agregar_candidato_ambos(f'span[id*="[{coord}]_c"]')

            # 3) Respaldo por metadato técnico ABAP (lsdata)
            if m_slow:
                _agregar_candidato_ambos(f'[lsdata*="{m_slow.group(1)}"]')
                _agregar_candidato_ambos(f'input[lsdata*="{m_slow.group(1)}"]')

            # 4) Respaldo general de celda
            _agregar_candidato_ambos(f'[id*="[{coord}]"]')

        # B. Si es un botón o control SAP con :: (ej: M0:46:1:1:2::12:53 o M1:37::btn[8])
        if sufijo_btn:
            if raw_id:
                _agregar_candidato_ambos(f'[id="{raw_id}"]')
            _agregar_candidato_ambos(f'[id$="::{sufijo_btn}"]')
            _agregar_candidato_ambos(f'[id*="::{sufijo_btn}"]')
            if es_modal_sap:
                _agregar_candidato_ambos(f'[id^="M1:"][id*="::{sufijo_btn}"]')
            elif es_main_sap:
                _agregar_candidato_ambos(f'[id^="M0:"][id*="::{sufijo_btn}"]')

        # C. IDs limpios estáticos (ej: sap-user, ToolbarOkCode, LOGON_BUTTON) antes de selectores de texto/rol ambiguos
        if raw_id and not raw_id.startswith("u") and not raw_id.isdigit():
            id_sel = f'[id="{raw_id}"]'
            _agregar_candidato_ambos(id_sel)

        # D. Selector sugerido si NO es una clase genérica de SAP
        CLASES_GEN_SAP = ("lsfield__input", "lsfield", "lsbutton", "lscontrol", "lscontrol--explicitheight")
        es_sugerido_generico = any(g in sugerido_orig.lower() for g in CLASES_GEN_SAP)
        if sugerido_orig and not es_sugerido_generico:
            _agregar_candidato_ambos(sugerido_orig)
            try:
                from src.utils.dom_enricher import flexibilizar_selector_sap
                for s_flex in flexibilizar_selector_sap(sugerido_orig):
                    _agregar_candidato_ambos(s_flex)
            except Exception:
                pass

        # E. Selectores candidatos de DevTools
        for sc in accion.get("selectores_candidatos", []) + accion.get("selectores_alternativos", []):
            if sc and not any(g in str(sc).lower() for g in CLASES_GEN_SAP):
                _agregar_candidato_ambos(sc)

        # F. Name o Placeholder
        if accion.get("name"):
            _agregar_candidato_ambos(f'[name="{accion["name"]}"]')
        if accion.get("placeholder"):
            _agregar_candidato_ambos(f'placeholder={accion["placeholder"]}')

        # G. XPath
        if accion.get("xpath"):
            _agregar_candidato_ambos("xpath=" + accion["xpath"])

        # H. Como último recurso, si no teníamos nada más, el selector sugerido original
        if sugerido_orig and es_sugerido_generico and len(candidatos) == 0:
            _agregar_candidato_ambos(sugerido_orig)

        if not candidatos:
            candidatos.append(sugerido_orig or "page")
        if not candidatos_lambdas:
            candidatos_lambdas.append("lambda p: p")

        candidatos_repr = repr(candidatos)
        
        codigo.append(f"        # --------------------------------------------------")
        codigo.append(f"        # Paso {idx + 1}: {desc}")
        codigo.append(f"        # --------------------------------------------------")
        if tipo == "navigation":
            codigo.append(f"        print({repr(f'[PASO] Navegando a: {valor}')})")
            codigo.append(f"        page.goto({repr(valor)})")
            codigo.append("        page.wait_for_load_state('domcontentloaded')")
            if es_resiliente:
                codigo.append("        cerrar_modales_y_banners(page)")
        elif es_resiliente:
            # Flujo resiliente con Fast-Scan de selectores de respaldo y auto-cierre de modales
            es_secreto = (tipo == "fill" and (accion.get("type") == "password" or 
                          any(p in desc.lower() or p in (selector or "").lower() for p in ["pass", "clave", "contraseña", "secret"])))
            
            if parametrizar and es_secreto:
                var_name = f"RPA_SECRET_{idx + 1}"
                codigo.append(f"        # Credencial sensible parametrizada en variables de entorno")
                codigo.append(f"        valor_input = os.environ.get({repr(var_name)}, {repr(valor)})")
                codigo.append(f"        print({repr(f'[PASO] Escribir credencial protegida ({var_name}) en: {desc}')})")
            elif parametrizar and tipo in ("upload", "file_upload"):
                var_name = f"RPA_FILE_{idx + 1}"
                codigo.append(f"        # Ruta de archivo parametrizada en variables de entorno")
                codigo.append(f"        valor_input = os.environ.get({repr(var_name)}, {repr(valor)})")
                codigo.append(f"        print({repr(f'[PASO] Subir archivo ({var_name}) en: {desc}')})")
            elif parametrizar and tipo == "download":
                var_name = f"RPA_DOWNLOAD_{idx + 1}"
                codigo.append(f"        # Ruta o nombre de descarga parametrizado en variables de entorno")
                codigo.append(f"        valor_input = os.environ.get({repr(var_name)}, {repr(valor)})")
                codigo.append(f"        print({repr(f'[PASO] Descargar archivo ({var_name}) en: {desc}')})")
            elif tipo in ("upload", "file_upload"):
                codigo.append(f"        valor_input = {repr(valor)}")
                codigo.append(f"        print({repr(f'[PASO] Subir archivo \"{valor}\" en: {desc}')})")
            elif tipo == "download":
                codigo.append(f"        valor_input = {repr(valor)}")
                codigo.append(f"        print({repr(f'[PASO] Descargar archivo en: {desc}')})")
            else:
                codigo.append(f"        valor_input = {repr(valor)}")
                codigo.append(f"        print({repr(f'[PASO] Ejecutar {tipo} en: {desc}')})")

            candidatos_repr = repr(candidatos)
            ruta_repr = repr(ruta_iframes) if ruta_iframes else "None"

            if tipo == "extract":
                codigo.append(f"        texto_extraido = ejecutar_accion_resiliente(page, {candidatos_repr}, {repr(tipo)}, valor=valor_input, desc={repr(desc)}, ruta_iframes={ruta_repr})")
                codigo.append(f"        variables['var_{idx + 1}'] = texto_extraido")
                codigo.append(f"        print(f'[RESULTADO] Texto obtenido: {{texto_extraido}}')")
            else:
                codigo.append(f"        ejecutar_accion_resiliente(page, {candidatos_repr}, {repr(tipo)}, valor=valor_input, desc={repr(desc)}, ruta_iframes={ruta_repr})")

            if tipo == "fill" and ("okcode" in str(selector or "").lower() or "okcode" in locator_str.lower()):
                codigo.append(f"        print({repr(f'[PASO] Presionar Enter para enviar comando SAP en: {desc}')})")
                codigo.append(f"        ejecutar_accion_resiliente(page, {candidatos_repr}, 'key', valor='Enter', desc='Comando SAP', ruta_iframes={ruta_repr})")
                codigo.append("        print('[PASO] Esperando 3 segundos para que SAP procese la transacción...')")
                codigo.append("        time.sleep(3)")
        else:
            # Flujo estándar tradicional
            if tipo == "click":
                codigo.append(f"        print({repr(f'[PASO] Hacer clic en: {desc}')})")
                codigo.append(f"        {locator_str}.first.click()")
                if any(k in str(selector).lower() for k in ["[id*=\"[\"", "_c", "tbl"]):
                    codigo.append("        time.sleep(0.2)")
            elif tipo == "fill":
                es_secreto = (accion.get("type") == "password" or 
                              any(p in desc.lower() or p in (selector or "").lower() for p in ["pass", "clave", "contraseña", "secret"]))
                if parametrizar and es_secreto:
                    var_name = f"RPA_SECRET_{idx + 1}"
                    codigo.append(f"        valor_input = os.environ.get({repr(var_name)}, {repr(valor)})")
                    codigo.append(f"        print({repr(f'[PASO] Escribir credencial protegida ({var_name}) en: {desc}')})")
                else:
                    codigo.append(f"        valor_input = {repr(valor)}")
                    codigo.append(f"        print({repr(f'[PASO] Escribir \"{valor}\" en: {desc}')})")
                
                codigo.append("        try:")
                codigo.append(f"            {locator_str}.first.fill(valor_input)")
                codigo.append("        except Exception:")
                codigo.append("            _exito = False")
                codigo.append("            try:")
                codigo.append(f"                _child = {locator_str}.first.locator(\"input, textarea, [contenteditable='true']\").first")
                codigo.append("                if _child.count() > 0:")
                codigo.append("                    _child.fill(valor_input)")
                codigo.append("                    _exito = True")
                codigo.append("            except Exception:")
                codigo.append("                pass")
                codigo.append("            if not _exito:")
                codigo.append(f"                {locator_str}.first.click()")
                codigo.append("                time.sleep(0.15)")
                codigo.append(f"                {locator_str}.first.press_sequentially(valor_input, delay=25)")
                    
                if "okcode" in str(selector or "").lower() or "okcode" in locator_str.lower():
                    codigo.append(f"        print({repr(f'[PASO] Presionar Enter para enviar comando en: {desc}')})")
                    codigo.append(f"        {locator_str}.first.press('Enter')")
                    codigo.append("        print('[PASO] Esperando 3 segundos para que SAP procese la transacción...')")
                    codigo.append("        time.sleep(3)")
            elif tipo in ("select", "change"):
                codigo.append(f"        print({repr(f'[PASO] Seleccionar opción \"{valor}\" en: {desc}')})")
                codigo.append(f"        {locator_str}.first.select_option({repr(valor)})")
            elif tipo == "key":
                codigo.append(f"        print({repr(f'[PASO] Presionar tecla \"{valor}\" en: {desc}')})")
                codigo.append("        try:")
                codigo.append(f"            {locator_str}.first.press({repr(valor)})")
                codigo.append("        except Exception:")
                codigo.append(f"            page.keyboard.press({repr(valor)})")
            elif tipo == "assert_visible":
                codigo.append(f"        print({repr(f'[PASO] Validar visibilidad de: {desc}')})")
                codigo.append(f"        expect({locator_str}.first).to_be_visible()")
            elif tipo == "assert_text":
                codigo.append(f"        print({repr(f'[PASO] Validar texto \"{valor}\" en: {desc}')})")
                codigo.append(f"        expect({locator_str}.first).to_contain_text({repr(valor)})")
            elif tipo == "extract":
                codigo.append(f"        print({repr(f'[PASO] Extraer texto de: {desc}')})")
                codigo.append(f"        _raw_val = {locator_str}.first.inner_text().strip()")
                codigo.append("        if not _raw_val:")
                codigo.append("            try:")
                codigo.append(f"                _raw_val = ({locator_str}.first.input_value(timeout=1000) or '').strip()")
                codigo.append("            except Exception:")
                codigo.append("                pass")
                if valor and str(valor).strip():
                    codigo.append(f"        _filtro = {repr(str(valor).strip())}")
                    codigo.append("        if re.match(r'^\\d{2}:\\d{2}(?::\\d{2})?$', _filtro) and re.search(r'\\b\\d{2}:\\d{2}(?::\\d{2})?\\b', _raw_val):")
                    codigo.append("            texto_extraido = re.search(r'\\b\\d{2}:\\d{2}(?::\\d{2})?\\b', _raw_val).group(0)")
                    codigo.append("        elif re.match(r'^\\d{2}[./-]\\d{2}[./-]\\d{4}$', _filtro) and re.search(r'\\b\\d{2}[./-]\\d{2}[./-]\\d{4}\\b', _raw_val):")
                    codigo.append("            texto_extraido = re.search(r'\\b\\d{2}[./-]\\d{2}[./-]\\d{4}\\b', _raw_val).group(0)")
                    codigo.append("        elif any(tok in _filtro for tok in ['(', ')', r'\\d', r'\\w', r'\\s', '[', ']', '.*', '.+']):")
                    codigo.append("            _m = re.search(_filtro, _raw_val)")
                    codigo.append("            texto_extraido = (_m.group(1) if _m.groups() else _m.group(0)) if _m else _raw_val")
                    codigo.append("        elif re.search(rf'(?:^|[\\r\\n])\\s*{re.escape(_filtro)}[\\s:\\n]+([^\\r\\n]+)', _raw_val, re.IGNORECASE):")
                    codigo.append("            texto_extraido = re.search(rf'(?:^|[\\r\\n])\\s*{re.escape(_filtro)}[\\s:\\n]+([^\\r\\n]+)', _raw_val, re.IGNORECASE).group(1).strip()")
                    codigo.append("        elif _filtro in _raw_val:")
                    codigo.append("            texto_extraido = _filtro")
                    codigo.append("        else:")
                    codigo.append("            texto_extraido = _raw_val")
                else:
                    codigo.append("        texto_extraido = _raw_val")
                codigo.append(f"        variables['var_{idx + 1}'] = texto_extraido")
                codigo.append(f"        print(f'[RESULTADO] Texto obtenido: {{texto_extraido}}')")
            elif tipo in ("upload", "file_upload"):
                if parametrizar:
                    var_name = f"RPA_FILE_{idx + 1}"
                    codigo.append(f"        valor_input = os.environ.get({repr(var_name)}, {repr(valor)})")
                    codigo.append(f"        print({repr(f'[PASO] Subir archivo ({var_name}) en: {desc}')})")
                else:
                    codigo.append(f"        valor_input = {repr(valor)}")
                    codigo.append(f"        print({repr(f'[PASO] Subir archivo \"{valor}\" en: {desc}')})")
                codigo.append("        ruta_archivo = os.path.abspath(valor_input) if valor_input and str(valor_input).strip() else valor_input")
                codigo.append("        if isinstance(ruta_archivo, str) and not os.path.exists(ruta_archivo):")
                codigo.append("            print(f'      [ADVERTENCIA] El archivo no fue encontrado en el disco: {ruta_archivo}')")
                codigo.append("        try:")
                codigo.append(f"            with page.expect_file_chooser(timeout=min({timeout_val}, 15000)) as fc_info:")
                codigo.append(f"                {locator_str}.first.click()")
                codigo.append("            fc_info.value.set_files(ruta_archivo)")
                codigo.append("            print(f'      [SUBIDA] Archivo cargado exitosamente interceptando file_chooser: {ruta_archivo}')")
                codigo.append("        except Exception as exc_fc:")
                codigo.append("            try:")
                codigo.append(f"                {locator_str}.first.set_input_files(ruta_archivo)")
                codigo.append("                print(f'      [SUBIDA] Archivo asignado directamente al input: {ruta_archivo}')")
                codigo.append("            except Exception:")
                codigo.append(f"                raise RuntimeError(f\"Error al cargar archivo en '{desc}': {{exc_fc}}\")")
            elif tipo == "download":
                if parametrizar:
                    var_name = f"RPA_DOWNLOAD_{idx + 1}"
                    codigo.append(f"        valor_input = os.environ.get({repr(var_name)}, {repr(valor)})")
                    codigo.append(f"        print({repr(f'[PASO] Descargar archivo ({var_name}) en: {desc}')})")
                else:
                    codigo.append(f"        valor_input = {repr(valor)}")
                    codigo.append(f"        print({repr(f'[PASO] Descargar archivo en: {desc}')})")
                codigo.append("        try:")
                codigo.append(f"            with page.expect_download(timeout=min({timeout_val}, 30000)) as dl_info:")
                codigo.append(f"                {locator_str}.first.click()")
                codigo.append("            download = dl_info.value")
                codigo.append("            nombre_destino = valor_input if valor_input and str(valor_input).strip() else download.suggested_filename")
                codigo.append("            ruta_destino = os.path.abspath(nombre_destino)")
                codigo.append("            os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)")
                codigo.append("            download.save_as(ruta_destino)")
                codigo.append("            print(f'      [DESCARGA] Archivo descargado exitosamente en: {ruta_destino}')")
                codigo.append("        except Exception as exc_dl:")
                codigo.append(f"            raise RuntimeError(f\"Error al descargar archivo en '{desc}': {{exc_dl}}\")")
        
        codigo.append("        time.sleep(0.15)  # Pausa ágil entre pasos")
        codigo.append("")

    codigo.append("        print('[FIN] Flujo automatizado completado con éxito.')")
    tiene_extract = any(a.get("tipo_accion") == "extract" for a in acciones_seleccionadas)
    if tiene_extract:
        codigo.append("        if variables:")
        codigo.append("            print('\\n[VARIABLES EXTRAÍDAS]:')")
        codigo.append("            for k, v in variables.items():")
        codigo.append("                print(f'  - {k}: {v}')")
    if incluir_trace:
        codigo.append(f"        # Detener y exportar el archivo de traza")
        codigo.append(f"        context.tracing.stop(path={repr(ruta_trace)})")
        codigo.append(f"        print({repr(f'[TRACE] Traza guardada en: {ruta_trace}')})")
        codigo.append(f"        print({repr(f'[TRACE] Para inspeccionar la traza ejecuta: npx playwright show-trace {ruta_trace}')})")
    codigo.append("        print('Cerrando navegador en 3 segundos...')")
    codigo.append("        time.sleep(3)")
    if incluir_video:
        codigo.append("        ruta_video = page.video.path() if page.video else None")
        codigo.append("        context.close()")
    codigo.append("        browser.close()")
    if incluir_video:
        codigo.append("        if ruta_video:")
        codigo.append("            print(f'[VIDEO] Video de la ejecución guardado en: {ruta_video}')")
    codigo.append("        return variables")
    codigo.append("")
    codigo.append("if __name__ == '__main__':")
    codigo.append("    ejecutar_flujo_automatizado()")
    
    contenido_codigo = "\n".join(codigo)
    
    dir_padre = os.path.dirname(nombre_archivo)
    if dir_padre:
        os.makedirs(dir_padre, exist_ok=True)
        
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(contenido_codigo)
        
    print(f"[GENERADO] Script de automatización DOM generado en: {nombre_archivo}")
    return contenido_codigo

def generar_lista_selectores_json(acciones_seleccionadas, nombre_archivo="selectores_capturados.json"):
    """
    Exporta la lista de acciones y elementos seleccionados en formato JSON estructurado
    con todos los metadatos y selectores alternativos.
    """
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        json.dump(acciones_seleccionadas, f, indent=4, ensure_ascii=False)
    return json.dumps(acciones_seleccionadas, indent=4, ensure_ascii=False)

def generar_reporte_selectores_txt(acciones_seleccionadas, nombre_archivo="reporte_selectores.txt"):
    """
    Genera un reporte legible en texto plano con el paso a paso de las acciones
    y todos los selectores alternativos disponibles para cada elemento.
    """
    lineas = []
    lineas.append("="*75)
    lineas.append("                 REPORTE DE ELEMENTOS Y SELECTORES CAPTURADOS")
    lineas.append("="*75)
    lineas.append("")
    
    for idx, accion in enumerate(acciones_seleccionadas):
        tipo = accion.get("tipo_accion", "")
        desc = accion.get("descriptor_legible", "")
        valor = accion.get("valor", "")
        sugerido = accion.get("selector_sugerido", "")
        
        tipo_map = {
            "click": "Hacer clic",
            "fill": "Escribir texto",
            "select": "Seleccionar opción",
            "navigation": "Navegar a URL",
            "upload": "Subir archivo",
            "file_upload": "Subir archivo",
            "download": "Descargar archivo"
        }
        accion_nombre = tipo_map.get(tipo, tipo.capitalize())
        
        lineas.append(f"Paso {idx + 1}: {desc}")
        lineas.append(f"  - Acción: {accion_nombre}")
        if tipo == "navigation":
            lineas.append(f"  - URL: {valor}")
        else:
            if valor:
                lineas.append(f"  - Valor / Texto: \"{valor}\"")
            lineas.append(f"  - Selector Sugerido (Playwright): page.locator({repr(sugerido)})")
            
            lineas.append("  - Selectores Alternativos:")
            if accion.get("id"):
                lineas.append(f"    * Por ID: #{accion['id']}")
            if accion.get("name"):
                lineas.append(f"    * Por Name: [name='{accion['name']}']")
            if accion.get("placeholder"):
                lineas.append(f"    * Por Placeholder: [placeholder='{accion['placeholder']}']")
            
            tag = accion.get("tagName", "").lower()
            if tag:
                lineas.append(f"    * Por CSS/Etiqueta: {tag}")
                if accion.get("className"):
                    clases = ".".join(accion["className"].split())
                    if clases:
                        lineas.append(f"    * Por Clase CSS: {tag}.{clases}")
            
            if accion.get("xpath"):
                lineas.append(f"    * Por XPath: {accion['xpath']}")
                
        lineas.append("-" * 75)
        lineas.append("")
        
    contenido = "\n".join(lineas)
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(contenido)
    return contenido
