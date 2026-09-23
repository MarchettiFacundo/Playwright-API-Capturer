"""
Módulo de Enriquecimiento DOM mediante Auto-Replay.
Reproduce secuencialmente las acciones capturadas (por ejemplo desde Playwright Codegen)
en un navegador real en vivo para inspeccionar el DOM y extraer:
- outerHTML completo
- Jerarquía de ancestros (padres, abuelos, contenedores con ID/clases)
- XPath jerárquico absoluto y relativo
- Atributos completos (id, name, type, placeholder, etc.)
- Selectores alternativos de contingencia
"""

import time
import re
from typing import List, Dict, Any, Callable, Optional
from playwright.sync_api import sync_playwright

JS_EXTRACCION_DOM = r"""
(el) => {
    function esIdValido(id) {
        if (!id) return false;
        if (id.includes("#")) return false;
        if (/^u\d+$/.test(id)) return false; // IDs efímeros de sesión SAP (ej: u2186)
        if (/^\d+$/.test(id)) return false;
        // Reconocer IDs estructurales de SAP WebGUI
        if (id.includes("::") || /\[\d+,\d+\]/.test(id)) return true;
        if (id.includes("-") && /\d+/.test(id)) return false;
        if (id.includes("_") && /\d+/.test(id)) return false;
        if (id.startsWith("sap-ui-id")) return false;
        if (id.startsWith("sap-comp")) return false;
        if (isNaN(id.charAt(0)) === false) return false;
        return true;
    }

    function getXPath(node) {
        if (node.id && esIdValido(node.id)) return `//*[@id="${node.id}"]`;
        if (node === document.body) return '/html/body';
        let siblingCount = 0;
        let siblings = node.parentNode ? node.parentNode.childNodes : [];
        for (let i = 0; i < siblings.length; i++) {
            let sibling = siblings[i];
            if (sibling === node) {
                return getXPath(node.parentNode) + '/' + node.tagName.toLowerCase() + '[' + (siblingCount + 1) + ']';
            }
            if (sibling.nodeType === 1 && sibling.tagName === node.tagName) {
                siblingCount++;
            }
        }
        return '';
    }

    // Recorrido de ancestros
    let ancestros = [];
    let current = el;
    let maxNivel = 15;
    let nivel = 0;
    while (current && current !== document.documentElement && nivel < maxNivel) {
        let tag = current.tagName ? current.tagName.toLowerCase() : "";
        if (!tag) {
            current = current.parentElement;
            continue;
        }
        let idText = current.id ? `#${current.id}` : "";
        let clasesList = [];
        if (current.classList && typeof current.classList.forEach === 'function') {
            current.classList.forEach(c => {
                if (c && typeof c === 'string' && !c.includes("hover") && !c.includes("active")) {
                    clasesList.push(c);
                }
            });
        }
        let classText = clasesList.length > 0 ? "." + clasesList.join(".") : "";
        
        let sug = "";
        if (current.id && /\[\d+,\d+\]/.test(current.id)) {
            let mCoord = current.id.match(/\[\d+,\d+\]/);
            sug = mCoord ? `${tag}[id*="${mCoord[0]}_c"]` : `[id="${current.id}"]`;
        } else if (current.id && current.id.includes("::")) {
            sug = `[id="${current.id}"]`;
        } else if (current.id && esIdValido(current.id)) {
            sug = `#${current.id}`;
        } else if (clasesList.length > 0) {
            let clasesValidas = clasesList.filter(c => !c.toLowerCase().includes("lsfield") && !c.toLowerCase().includes("lscontrol") && !c.toLowerCase().includes("lsbutton"));
            if (clasesValidas.length > 0) {
                sug = `${tag}.${clasesValidas[0]}`;
            } else {
                sug = tag;
            }
        } else {
            sug = tag;
        }

        ancestros.push({
            tagName: current.tagName,
            id: current.id || "",
            className: (typeof current.className === "string" ? current.className : ""),
            descriptor: `${tag}${idText}${classText}`,
            xpath: getXPath(current),
            selector_sugerido: sug,
            esObjetivo: (nivel === 0)
        });
        current = current.parentElement;
        nivel++;
    }

    return {
        tagName: el.tagName || "",
        id: el.id || "",
        name: el.name || el.getAttribute("name") || "",
        className: (typeof el.className === "string" ? el.className : ""),
        type: el.getAttribute("type") || "",
        placeholder: el.getAttribute("placeholder") || "",
        outerHTML: el.outerHTML || "",
        xpath: getXPath(el),
        ancestros: ancestros
    };
}
"""

def flexibilizar_selector_sap(s: str) -> List[str]:
    """Genera variantes de selectores tolerantes a cambios de sesión en SAP ITS."""
    candidatos = []
    if not s:
        return candidatos

    # Caso 1: Coordenadas de celdas de tabla SAP: [fila,columna]
    m_coord = re.search(r'\[(\d+,\d+)\]', s)
    if m_coord:
        coord = m_coord.group(1)
        tag = "input" if "input" in s.lower() else ""
        pref_tag = f"{tag}" if tag else ""
        
        # Variantes ordenadas por máxima resiliencia
        candidatos.append(f'{pref_tag}[id*="[{coord}]_c"]' if pref_tag else f'input[id*="[{coord}]_c"]')
        candidatos.append(f'[id*="[{coord}]_c"]')
        candidatos.append(f'[id^="M1:"] input[id*="[{coord}]"]')
        candidatos.append(f'[id^="M0:"] input[id*="[{coord}]"]')
        candidatos.append(f'td[id*="[{coord}]"] input')
        candidatos.append(f'[id*="[{coord}]"]')
        candidatos.append(f'[id*="[{coord}]"] input')

    # Caso 2: Campo de menú, botón o control con identificador SAP ::sufijo
    if "::" in s:
        partes_dos_puntos = s.split("::")
        if len(partes_dos_puntos) > 1:
            sufijo = partes_dos_puntos[-1].rstrip('"\'\\]').strip()
            if sufijo:
                candidatos.append(f'[id$="::{sufijo}"]')
                candidatos.append(f'[id*="::{sufijo}"]')
                candidatos.append(f'[id^="M1:"][id*="::{sufijo}"]')
                candidatos.append(f'[id^="M0:"][id*="::{sufijo}"]')

    # Mantener el selector original si no es hipergenérico
    es_generico = any(g in s.lower() for g in ["lsfield__input", "lscontrol", "lsbutton"])
    if s not in candidatos and not es_generico:
        candidatos.insert(0, s)
    elif s not in candidatos and es_generico:
        candidatos.append(s)

    # Eliminar duplicados preservando el orden
    resultado = []
    vistos = set()
    for c in candidatos:
        if c and c not in vistos:
            resultado.append(c)
            vistos.add(c)
    return resultado

def resolver_locators_candidatos(page, selector_str: str, ruta_iframes: Optional[List[str]] = None) -> List[Any]:
    """Resuelve un selector a una lista de Locators ordenados por preferencia (exacto -> flexibles)."""
    if not selector_str:
        return [page.locator("body")]
    s = selector_str.strip()

    # Descomponer selector si contiene .content_frame o .frame_locator
    if ".content_frame." in s or "frame_locator(" in s:
        from src.utils.codegen_manager import descomponer_locator_iframe
        sub_iframes, s = descomponer_locator_iframe(s)
        if sub_iframes:
            ruta_iframes = (ruta_iframes or []) + sub_iframes

    target = page
    if ruta_iframes:
        for if_sel in ruta_iframes:
            if "itsframe" in if_sel.lower():
                if_sel = "iframe[name*='itsframe' i]"
            target = target.frame_locator(if_sel)

    locators = []
    variantes = flexibilizar_selector_sap(s)

    for v in variantes:
        try:
            if v.startswith("page."):
                expr = "target." + v[5:]
                locators.append(eval(expr, {"target": target}))
            elif v.startswith("p."):
                expr = "target." + v[2:]
                locators.append(eval(expr, {"target": target}))
            elif v.startswith("xpath="):
                locators.append(target.locator(v))
            elif v.startswith("text="):
                locators.append(target.get_by_text(v[5:]))
            elif v.startswith("id="):
                locators.append(target.locator(f'[id="{v[3:]}"]'))
            elif v.startswith("role:"):
                from src.generators.dom_generator import resolver_locator_playwright as rlp
                loc_str = rlp(v)
                if loc_str.startswith("page."):
                    expr = "target." + loc_str[5:]
                    locators.append(eval(expr, {"target": target}))
                else:
                    locators.append(target.locator(loc_str))
            else:
                locators.append(target.locator(v))
        except Exception:
            pass

    if not locators:
        locators.append(target.locator(s))

    return locators

def resolver_locator_playwright(page, selector_str: str, ruta_iframes: Optional[List[str]] = None):
    """Resuelve un string de selector a un Locator de Playwright."""
    cands = resolver_locators_candidatos(page, selector_str, ruta_iframes)
    return cands[0] if cands else page.locator(selector_str or "body")


def cerrar_modales_emergentes(page, timeout_ms: int = 1000) -> bool:
    """Descarta banners de cookies, diálogos web o popups de sesión de SAP ITS de forma reactiva."""
    patrones_web = [
        "#onetrust-accept-btn-handler",
        "[id*='cookie' i] button", "[class*='cookie' i] button",
        "[id*='consent' i] button", "[class*='consent' i] button",
        "[role='dialog'] button[aria-label*='close' i]",
        "[role='dialog'] button[aria-label*='cerrar' i]",
        "[role='dialog'] button.close", "[role='dialog'] .modal-close",
        "button[data-dismiss='modal']", "button[data-bs-dismiss='modal']",
        "[aria-modal='true'] button[aria-label*='close' i]",
        "[aria-modal='true'] button[aria-label*='cerrar' i]",
        ".modal.show button.close",
        "button[aria-label='Cerrar']", "button[aria-label='Close']"
    ]
    cerrado = False
    for pat in patrones_web:
        try:
            loc = page.locator(pat).first
            if loc.is_visible(timeout=80):
                loc.click(timeout=timeout_ms)
                page.wait_for_timeout(300)
                cerrado = True
        except Exception:
            pass

    # Diálogos emergentes internos de SAP ITS (ej. sesión múltiple o avisos de sistema)
    try:
        sap_frame = page.frame_locator('iframe[name*="itsframe" i]')
        patrones_sap = [
            'button[title*="Entrada" i]',
            'button:has-text("Continuar")',
            'button:has-text("Entrada")',
            'button[id*="btn[0]" i]',
            '[role="dialog"] button:has-text("Aceptar")',
            '[role="dialog"] button:has-text("OK")',
            '[role="dialog"] button:has-text("Sí")',
            '[role="dialog"] button:has-text("Si")'
        ]
        for pat in patrones_sap:
            try:
                loc = sap_frame.locator(pat).first
                if loc.is_visible(timeout=80):
                    loc.click(timeout=timeout_ms)
                    page.wait_for_timeout(400)
                    cerrado = True
            except Exception:
                pass
    except Exception:
        pass

    return cerrado

def enriquecer_pasos_dom(
    acciones: List[Dict[str, Any]],
    callback_progreso: Optional[Callable[[int, int, str], None]] = None,
    headless: bool = False,
    timeout_ms: int = 6000,
    storage_state: str = ""
) -> List[Dict[str, Any]]:
    """
    Ejecuta el auto-replay de las acciones en un navegador vivo de Playwright,
    extrayendo outerHTML, ancestros y XPath para cada paso con soporte adaptativo para SAP.
    Retorna la lista de acciones enriquecidas.
    """
    if not acciones:
        return acciones

    total = len(acciones)

    # Detección inteligente de entorno SAP ITS
    es_sap = any(
        "sap" in str(a.get("valor", "")).lower()
        or "sap" in str(a.get("selector_sugerido", "")).lower()
        or "itsframe" in str(a.get("selector_sugerido", "")).lower()
        or any("itsframe" in str(ifr).lower() for ifr in a.get("ruta_iframes", []))
        for a in acciones
    )

    if es_sap and timeout_ms <= 10000:
        timeout_ms = 30000
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        if storage_state and storage_state.strip():
            context = browser.new_context(ignore_https_errors=True, storage_state=storage_state.strip())
        else:
            context = browser.new_context(ignore_https_errors=True)
            
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        for idx, accion in enumerate(acciones):
            tipo = accion.get("tipo_accion", "")
            desc = accion.get("descriptor_legible", f"Paso {idx + 1}")
            sug = accion.get("selector_sugerido", "")
            valor = accion.get("valor", "")

            if callback_progreso:
                callback_progreso(idx + 1, total, f"[{idx + 1}/{total}] {desc}")

            cerrar_modales_emergentes(page)

            # Caso 1: Navegación
            if tipo == "navigation":
                url = valor or sug
                if url:
                    try:
                        page.goto(url)
                        page.wait_for_load_state("domcontentloaded")
                        if es_sap:
                            page.wait_for_timeout(2500)
                        else:
                            page.wait_for_timeout(500)
                        cerrar_modales_emergentes(page)
                        accion["outerHTML"] = page.content()[:3000]
                    except Exception as ex:
                        print(f"[ENRICH] Error en navegación ({url}): {ex}")
                continue

            # Caso 2: Interacciones con elementos DOM
            if not sug:
                continue

            timeout_paso = 18000 if es_sap else timeout_ms
            locator_valido = None
            locators_candidatos = resolver_locators_candidatos(page, sug, accion.get("ruta_iframes"))

            for loc in locators_candidatos:
                try:
                    loc.first.wait_for(state="attached", timeout=timeout_paso)
                    locator_valido = loc.first
                    break
                except Exception:
                    continue

            if not locator_valido:
                # Reintento resiliente: cerrar posibles popups bloqueantes de SAP y reintentar
                cerrar_modales_emergentes(page)
                page.wait_for_timeout(1200)
                for loc in locators_candidatos:
                    try:
                        loc.first.wait_for(state="attached", timeout=5000)
                        locator_valido = loc.first
                        break
                    except Exception:
                        continue

            if not locator_valido:
                print(f"[ENRICH] Advertencia: No se pudo localizar elemento en paso {idx + 1} ({desc}). Continuando...")
                continue

            try:
                # Introspección profunda en el elemento vivo mediante JavaScript
                try:
                    info_dom = locator_valido.evaluate(JS_EXTRACCION_DOM)
                    if isinstance(info_dom, dict):
                        if info_dom.get("outerHTML"):
                            accion["outerHTML"] = info_dom["outerHTML"]
                        if info_dom.get("ancestros"):
                            accion["ancestros"] = info_dom["ancestros"]
                        if info_dom.get("xpath"):
                            accion["xpath"] = info_dom["xpath"]
                        if info_dom.get("id"):
                            accion["id"] = info_dom["id"]
                        if info_dom.get("name"):
                            accion["name"] = info_dom["name"]
                        if info_dom.get("className"):
                            accion["className"] = info_dom["className"]
                        if info_dom.get("type"):
                            accion["type"] = info_dom["type"]
                        if info_dom.get("placeholder"):
                            accion["placeholder"] = info_dom["placeholder"]
                        if info_dom.get("tagName"):
                            accion["tagName"] = info_dom["tagName"]
                except Exception as ex_eval:
                    print(f"[ENRICH] Introspección DOM omitida en paso {idx + 1}: {ex_eval}")

                # Ejecución real de la acción para avanzar la página al próximo estado
                if tipo == "click":
                    locator_valido.click(timeout=timeout_paso)
                    if any(k in sug for k in ["[id*=\"[", "_c", "tbl"]):
                        page.wait_for_timeout(350)
                elif tipo == "fill":
                    try:
                        locator_valido.fill(valor or "", timeout=timeout_paso)
                    except Exception as ex_fill:
                        # Fallback 1: Si el selector apunta al <td> contenedor, buscar input/textarea hijo
                        exito_fill = False
                        try:
                            input_hijo = locator_valido.locator("input, textarea, [contenteditable='true']").first
                            input_hijo.wait_for(state="attached", timeout=2500)
                            input_hijo.fill(valor or "", timeout=timeout_paso)
                            exito_fill = True
                        except Exception:
                            pass

                        if not exito_fill:
                            try:
                                # Fallback 2: Clic directo para enfocar y tipeo secuencial
                                locator_valido.click(timeout=1500)
                                page.wait_for_timeout(200)
                                locator_valido.press_sequentially(valor or "", delay=30)
                                exito_fill = True
                            except Exception:
                                raise ex_fill
                elif tipo in ("select", "change"):
                    locator_valido.select_option(valor or "", timeout=timeout_paso)
                elif tipo == "key":
                    locator_valido.press(valor or "Enter", timeout=timeout_paso)
                elif tipo == "extract":
                    try:
                        accion["valor"] = locator_valido.inner_text(timeout=timeout_paso).strip()
                    except Exception:
                        pass
                elif tipo in ("upload", "file_upload"):
                    ruta_archivo = valor
                    if isinstance(ruta_archivo, str) and ruta_archivo.strip():
                        import os
                        ruta_archivo = os.path.abspath(ruta_archivo.strip())
                    try:
                        with page.expect_file_chooser(timeout=min(timeout_paso, 5000)) as fc_info:
                            locator_valido.click(timeout=timeout_paso)
                        if ruta_archivo and isinstance(ruta_archivo, str) and os.path.exists(ruta_archivo):
                            fc_info.value.set_files(ruta_archivo)
                    except Exception:
                        if ruta_archivo and isinstance(ruta_archivo, str) and os.path.exists(ruta_archivo):
                            try:
                                locator_valido.set_input_files(ruta_archivo, timeout=timeout_paso)
                            except Exception:
                                pass
                elif tipo == "download":
                    try:
                        with page.expect_download(timeout=min(timeout_paso, 10000)) as dl_info:
                            locator_valido.click(timeout=timeout_paso)
                        if not valor:
                            accion["valor"] = dl_info.value.suggested_filename
                    except Exception:
                        pass

                # Pausas y sincronizaciones adaptativas para SAP ITS
                es_login_click = tipo == "click" and any(k in desc.lower() for k in ["acceder", "login", "logon", "ingresar"])
                es_transaccion = (tipo == "key" and (valor == "Enter" or "enter" in str(valor).lower())) or \
                                 ("okcode" in sug.lower() or "código de transacción" in desc.lower())
                es_ejecutar = tipo == "click" and any(k in desc.lower() for k in ["tomar", "ejecutar", "f8", "continuar", "entrada"])

                if es_login_click and es_sap:
                    # Esperar a que el entorno ITS termine de cargar el iframe principal
                    try:
                        page.locator('iframe[name*="itsframe" i]').first.wait_for(state="attached", timeout=20000)
                        page.wait_for_timeout(3500)
                    except Exception:
                        page.wait_for_timeout(5000)
                    cerrar_modales_emergentes(page)
                elif es_transaccion and es_sap:
                    page.wait_for_timeout(4500)
                    cerrar_modales_emergentes(page)
                elif es_ejecutar and es_sap:
                    page.wait_for_timeout(3000)
                    cerrar_modales_emergentes(page)
                else:
                    page.wait_for_timeout(500)

            except Exception as ex_accion:
                print(f"[ENRICH] Advertencia al ejecutar paso {idx + 1} ({desc}): {ex_accion}")
                cerrar_modales_emergentes(page)

        try:
            page.wait_for_timeout(1000)
            browser.close()
        except Exception:
            pass

    return acciones

