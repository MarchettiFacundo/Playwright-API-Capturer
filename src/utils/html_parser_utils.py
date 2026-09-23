"""
Módulo de Utilidades para Parseo de HTML de DevTools y Generación de Selectores.
Permite inspeccionar snippets HTML crudos (copiados directamente desde las DevTools del navegador)
y extraer automáticamente metadatos, atributos y un abanico de selectores resilientes
para automatizaciones de Playwright, con soporte especializado para SAP ITS WebGUI (URST3).
"""

import re
import html
import json
from html.parser import HTMLParser
from typing import Dict, Any, List, Optional

class _DevToolsSnippetParser(HTMLParser):
    """Parser liviano y robusto para fragmentos HTML copiados de DevTools."""
    def __init__(self):
        super().__init__()
        self.tag = ""
        self.attrs = {}
        self.texto_interno = ""
        self._en_primer_tag = False

    def handle_starttag(self, tag, attrs):
        if not self.tag:
            self.tag = tag.lower()
            self.attrs = dict(attrs)
            self._en_primer_tag = True

    def handle_data(self, data):
        if self._en_primer_tag and not self.texto_interno:
            t = data.strip()
            if t:
                self.texto_interno = t


def parsear_elemento_devtools(html_crudo: str) -> Dict[str, Any]:
    """
    Parsea un fragmento HTML crudo pegado desde DevTools (por ejemplo de un clic derecho -> Copy -> Copy element).
    Extrae atributos, roles, clases, metadatos de SAP (lsdata, SID) y genera automáticamente
    una baraja ordenada de selectores candidatos para Playwright.
    """
    if not html_crudo or not html_crudo.strip():
        return {}

    html_limpio = html_crudo.strip()
    parser = _DevToolsSnippetParser()
    try:
        parser.feed(html_limpio)
    except Exception:
        pass

    tag = parser.tag or "element"
    attrs = parser.attrs

    # 1. Atributos estándar
    elem_id = attrs.get("id", "").strip()
    name = attrs.get("name", "").strip()
    raw_class = attrs.get("class", "").strip()
    classes = [c for c in raw_class.split() if c and not c.startswith("lsFocus") and not c.startswith("hover")]
    tipo = attrs.get("type", "").strip()
    role = attrs.get("role", "").strip()
    title = attrs.get("title", "").strip()
    placeholder = attrs.get("placeholder", "").strip()
    aria_label = attrs.get("aria-label", "").strip()
    aria_describedby = attrs.get("aria-describedby", "").strip()
    valor = attrs.get("value", "").strip()

    # 2. Metadatos específicos de SAP WebGUI / ITS
    sap_sid = ""
    sap_field_id = ""
    sap_type = ""
    sap_slow_id = ""
    sap_coord = None
    es_modal_wnd1 = False

    lsdata_raw = attrs.get("lsdata", "")
    lsdata_unescaped = ""
    if lsdata_raw:
        try:
            lsdata_unescaped = html.unescape(lsdata_raw)
            try:
                lsdata_dict = json.loads(lsdata_unescaped)
            except Exception:
                lsdata_dict = {}

            if isinstance(lsdata_dict, dict):
                sap_field_id = str(lsdata_dict.get("3", "")).strip()
                sap_sid = lsdata_dict.get("SID", "")
                data_21 = lsdata_dict.get("21", "")
                if isinstance(data_21, str) and "{" in data_21:
                    try:
                        d21 = json.loads(data_21)
                        if not sap_sid:
                            sap_sid = d21.get("SID", "")
                        sap_type = d21.get("Type", "")
                    except Exception:
                        pass
                elif isinstance(data_21, dict):
                    if not sap_sid:
                        sap_sid = data_21.get("SID", "")
                    sap_type = data_21.get("Type", "")
        except Exception:
            pass

        # Fallback con expresiones regulares sobre lsdata_unescaped
        if not sap_sid and lsdata_unescaped:
            m_sid = re.search(r'["\']?SID["\']?\s*:\s*["\']([^"\']+)["\']', lsdata_unescaped)
            if m_sid:
                sap_sid = m_sid.group(1)

        # Extraer identificador técnico de campo ABAP (ej: SLOW_I[1,0]) de SID o de lsdata
        if sap_sid:
            m_slow = re.search(r'(SLOW_[A-Z0-9_]+\[\d+,\d+\])', sap_sid)
            if m_slow:
                sap_slow_id = m_slow.group(1)
            else:
                partes_sid = sap_sid.split("/")
                if partes_sid:
                    ultima = partes_sid[-1]
                    if "-" in ultima:
                        sap_slow_id = ultima.split("-")[-1]
                    else:
                        sap_slow_id = ultima
        elif lsdata_unescaped:
            m_slow = re.search(r'(SLOW_[A-Z0-9_]+\[\d+,\d+\])', lsdata_unescaped)
            if m_slow:
                sap_slow_id = m_slow.group(1)

    # Detección de ventana modal wnd[1] vs ventana principal wnd[0]
    if "wnd[1]" in sap_sid or elem_id.startswith("M1:"):
        es_modal_wnd1 = True

    # 3. Detección de coordenadas de tabla SAP: [fila,columna]
    # Puede estar en el ID (ej: tbl112[1,2]_c), en sap_slow_id o en el SID de SAP
    match_coord = re.search(r'\[(\d+,\d+)\](_c)?', elem_id)
    if not match_coord and sap_slow_id:
        match_coord = re.search(r'\[(\d+,\d+)\]', sap_slow_id)
    if not match_coord and sap_sid:
        match_coord = re.search(r'\[(\d+,\d+)\]', sap_sid)

    CLASES_GENERICAS_SAP = {
        'lsfield__input', 'lsfield', 'lsfield__subinput', 'lsbutton', 
        'lsbutton--base', 'lsbutton--design-standard', 'lscontrol', 
        'lscontrol--explicitheight', 'lscontrol--valigntop', 'lscontrol--valignmiddle'
    }

    # 4. Generación algorítmica de selectores candidatos resilientes
    selectores = []

    # A. Coordenadas de celdas SAP (Prioridad Máxima por resiliencia frente a cambios de prefijo de tabla)
    if match_coord:
        coord = match_coord.group(1)
        sap_coord = coord
        
        # 1. Selector de input con coordenadas exactas de celda: input[id*="[1,2]_c"]
        if tag in ("input", "textarea", "select"):
            selectores.append(f'{tag}[id*="[{coord}]_c"]')
        selectores.append(f'[id*="[{coord}]_c"]')

        # 2. Selector por identificador técnico ABAP en lsdata (ej: input[lsdata*="SLOW_I[1,0]"])
        if sap_slow_id:
            slow_esc = sap_slow_id.replace('"', '\\"')
            if tag in ("input", "textarea", "select"):
                selectores.append(f'{tag}[lsdata*="{slow_esc}"]')
            selectores.append(f'[lsdata*="{slow_esc}"]')

        # 3. Selector anclado al contenedor de la ventana activa / modal (ej: [id^="M1:"] input[id*="[1,2]"])
        if es_modal_wnd1:
            if tag in ("input", "textarea", "select"):
                selectores.append(f'[id^="M1:"] {tag}[id*="[{coord}]"]')
            selectores.append(f'[id^="M1:"] [id*="[{coord}]"]')
        elif elem_id.startswith("M0:") or "wnd[0]" in sap_sid:
            if tag in ("input", "textarea", "select"):
                selectores.append(f'[id^="M0:"] {tag}[id*="[{coord}]"]')
            selectores.append(f'[id^="M0:"] [id*="[{coord}]"]')

        # 4. Selector por TD contenedor de la tabla (td[id*="[1,2]"] input)
        if tag in ("input", "textarea", "select"):
            selectores.append(f'td[id*="[{coord}]"] {tag}')
            selectores.append(f'td[id*="[{coord}]"] input')

        # 5. Selector con coordenada sin sufijo: [id*="[1,2]"]
        selectores.append(f'[id*="[{coord}]"]')

    # B. Selectores para botones o campos de menú SAP (ej: M0:46:1:1:2::12:53 o M1:37::btn[8])
    if elem_id and "::" in elem_id:
        selectores.append(f'[id="{elem_id}"]')
        partes_dos_puntos = elem_id.split("::")
        if len(partes_dos_puntos) > 1:
            sufijo = partes_dos_puntos[-1].strip()
            if sufijo:
                selectores.append(f'[id$="::{sufijo}"]')
                selectores.append(f'[id*="::{sufijo}"]')
                if es_modal_wnd1:
                    selectores.append(f'[id^="M1:"][id*="::{sufijo}"]')
                elif elem_id.startswith("M0:"):
                    selectores.append(f'[id^="M0:"][id*="::{sufijo}"]')

    # C. Selector exacto por ID (si no es celda tblXXX volátil o si no tiene :: ya agregado)
    if elem_id and f'[id="{elem_id}"]' not in selectores:
        selectores.append(f'[id="{elem_id}"]')
        if tag != "element":
            selectores.append(f'{tag}[id="{elem_id}"]')

    # D. Selector por Name
    if name:
        selectores.append(f'[name="{name}"]')
        if tag != "element":
            selectores.append(f'{tag}[name="{name}"]')

    # E. Selector semántico por Role Playwright
    if role:
        nombre_accesible = title or aria_label or placeholder or parser.texto_interno
        if nombre_accesible:
            nombre_esc = nombre_accesible.replace('"', '\\"')
            selectores.append(f'get_by_role("{role}", name="{nombre_esc}")')
        selectores.append(f'{tag}[role="{role}"]')

    # F. Selector por Placeholder
    if placeholder:
        pl_esc = placeholder.replace('"', '\\"')
        selectores.append(f'get_by_placeholder("{pl_esc}")')
        selectores.append(f'[placeholder="{placeholder}"]')

    # G. Selector por Título o Aria-Label
    if title:
        t_esc = title.replace('"', '\\"')
        selectores.append(f'get_by_title("{t_esc}")')
        selectores.append(f'[title="{title}"]')
    if aria_label:
        selectores.append(f'[aria-label="{aria_label}"]')

    # H. Selector por SID de SAP general (si no se agregó con SLOW_I)
    if sap_sid and not sap_slow_id:
        partes_sid = sap_sid.split("/")
        if partes_sid:
            clave_sid = partes_sid[-1]
            clave_sid_esc = clave_sid.replace('"', '\\"')
            selectores.append(f'[lsdata*="{clave_sid_esc}"]')

    # I. Clases CSS (FILTRANDO rigurosamente clases genéricas de SAP)
    clases_utiles = [c for c in classes if c.lower() not in CLASES_GENERICAS_SAP]
    if clases_utiles:
        selectores.append(f'{tag}.{clases_utiles[0]}')
        if len(clases_utiles) > 1:
            clases_dos = ".".join(clases_utiles[:2])
            selectores.append(f'{tag}.{clases_dos}')

    # Eliminar duplicados manteniendo el orden
    selectores_unicos = []
    vistos = set()
    for s in selectores:
        if s and s not in vistos:
            selectores_unicos.append(s)
            vistos.add(s)

    return {
        "tagName": tag.upper(),
        "id": elem_id,
        "name": name,
        "className": " ".join(classes),
        "classes": classes,
        "type": tipo,
        "role": role,
        "title": title,
        "placeholder": placeholder,
        "aria_label": aria_label,
        "value": valor,
        "texto_interno": parser.texto_interno,
        "sap_coord": sap_coord,
        "sap_sid": sap_sid,
        "sap_field_id": sap_field_id,
        "sap_type": sap_type,
        "outerHTML": html_limpio,
        "selectores_generados": selectores_unicos
    }


def enriquecer_accion_con_datos_html(accion: Dict[str, Any], datos_html: Dict[str, Any], selector_elegido: Optional[str] = None) -> None:
    """
    Aplica y fusiona los datos extraídos del HTML de DevTools a un diccionario de acción.
    Actualiza atributos clave, selector sugerido y añade la lista de selectores alternativos.
    """
    if not datos_html:
        return

    # Preservar selectores candidatos existentes y sumar los nuevos
    existentes = list(accion.get("selectores_candidatos", []))
    nuevos = datos_html.get("selectores_generados", [])
    
    todos_candidatos = []
    vistos = set()
    for s in nuevos + existentes:
        if s and s not in vistos:
            todos_candidatos.append(s)
            vistos.add(s)
    accion["selectores_candidatos"] = todos_candidatos

    # Actualizar selector sugerido principal si se especificó o si hay un candidato preferido
    if selector_elegido:
        accion["selector_sugerido"] = selector_elegido
    elif nuevos:
        sel_actual = accion.get("selector_sugerido", "")
        clases_gen_check = ("lsfield", "lscontrol", "lsbutton", "tbl", "page")
        if not sel_actual or any(k in sel_actual.lower() for k in clases_gen_check):
            accion["selector_sugerido"] = nuevos[0]

    # Actualizar atributos DOM
    if datos_html.get("tagName"):
        accion["tagName"] = datos_html["tagName"]
    if datos_html.get("id"):
        accion["id"] = datos_html["id"]
    if datos_html.get("name"):
        accion["name"] = datos_html["name"]
    if datos_html.get("className"):
        accion["className"] = datos_html["className"]
    if datos_html.get("type"):
        accion["type"] = datos_html["type"]
    if datos_html.get("placeholder"):
        accion["placeholder"] = datos_html["placeholder"]
    if datos_html.get("role"):
        accion["role"] = datos_html["role"]
    if datos_html.get("outerHTML"):
        accion["outerHTML"] = datos_html["outerHTML"]
    if datos_html.get("sap_coord"):
        accion["sap_coord"] = datos_html["sap_coord"]

    accion["html_origen"] = "devtools"
