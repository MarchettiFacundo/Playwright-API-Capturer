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
    sap_coord = None
    lsdata_raw = attrs.get("lsdata", "")
    if lsdata_raw:
        try:
            lsdata_unescaped = html.unescape(lsdata_raw)
            lsdata_dict = json.loads(lsdata_unescaped)
            sap_field_id = str(lsdata_dict.get("3", "")).strip()
            data_21 = lsdata_dict.get("21", "")
            if isinstance(data_21, str) and "{" in data_21:
                data_21_dict = json.loads(data_21)
                sap_sid = data_21_dict.get("SID", "")
                sap_type = data_21_dict.get("Type", "")
            elif isinstance(data_21, dict):
                sap_sid = data_21.get("SID", "")
                sap_type = data_21.get("Type", "")
        except Exception:
            pass

    # 3. Detección de coordenadas de tabla SAP: [fila,columna]
    # Puede estar en el ID (ej: tbl112[1,2]_c) o en el SID de SAP
    match_coord = re.search(r'\[(\d+,\d+)\](_c)?', elem_id)
    if not match_coord and sap_sid:
        match_coord = re.search(r'\[(\d+,\d+)\]', sap_sid)

    # 4. Generación algorítmica de selectores candidatos resilientes
    selectores = []

    # A. Coordenadas de celdas SAP (Prioridad Máxima por resiliencia frente a cambios de prefijo de tabla)
    if match_coord:
        coord = match_coord.group(1)
        sufijo = match_coord.group(2) or ""
        sap_coord = coord
        
        # 1. Selector de celda/input con tag y sufijo: input[id*="[1,2]_c"]
        if tag in ("input", "textarea", "select"):
            selectores.append(f'{tag}[id*="[{coord}]{sufijo}"]')
        # 2. Selector genérico de celda/input: [id*="[1,2]_c"]
        selectores.append(f'[id*="[{coord}]{sufijo}"]')
        # 3. Selector sin sufijo: input[id*="[1,2]"]
        if tag in ("input", "textarea", "select"):
            selectores.append(f'{tag}[id*="[{coord}]"]')
        selectores.append(f'[id*="[{coord}]"]')
        # 4. Selector combinado con clase CSS principal: input.lsField__input[id*="[1,2]"]
        if classes and tag in ("input", "textarea", "select"):
            selectores.append(f'{tag}.{classes[0]}[id*="[{coord}]"]')

    # B. Selector exacto por ID
    if elem_id:
        selectores.append(f'[id="{elem_id}"]')
        if tag != "element":
            selectores.append(f'{tag}[id="{elem_id}"]')

    # C. Selector por Name
    if name:
        selectores.append(f'[name="{name}"]')
        if tag != "element":
            selectores.append(f'{tag}[name="{name}"]')

    # D. Selector semántico por Role Playwright
    if role:
        nombre_accesible = title or aria_label or placeholder or parser.texto_interno
        if nombre_accesible:
            nombre_esc = nombre_accesible.replace('"', '\\"')
            selectores.append(f'get_by_role("{role}", name="{nombre_esc}")')
        selectores.append(f'{tag}[role="{role}"]')

    # E. Selector por Placeholder
    if placeholder:
        pl_esc = placeholder.replace('"', '\\"')
        selectores.append(f'get_by_placeholder("{pl_esc}")')
        selectores.append(f'[placeholder="{placeholder}"]')

    # F. Selector por Título o Aria-Label
    if title:
        t_esc = title.replace('"', '\\"')
        selectores.append(f'get_by_title("{t_esc}")')
        selectores.append(f'[title="{title}"]')
    if aria_label:
        selectores.append(f'[aria-label="{aria_label}"]')

    # G. Selector por Clases CSS
    if classes:
        selectores.append(f'{tag}.{classes[0]}')
        if len(classes) > 1:
            clases_dos = ".".join(classes[:2])
            selectores.append(f'{tag}.{clases_dos}')

    # H. Selector por SID de SAP (para controles con identificador lógico en lsdata)
    if sap_sid:
        partes_sid = sap_sid.split("/")
        if partes_sid:
            clave_sid = partes_sid[-1]
            clave_sid_esc = clave_sid.replace('"', '\\"')
            selectores.append(f'[lsdata*="{clave_sid_esc}"]')

    # I. Selector por Campo de Menú SAP (M0:46:...::12:53)
    if sap_field_id:
        m_field = re.search(r'::(\d+:\d+)', sap_field_id)
        if m_field:
            selectores.append(f'[id$="::{m_field.group(1)}"]')

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
        if "tbl" in sel_actual.lower() or not sel_actual or sel_actual == "page":
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
