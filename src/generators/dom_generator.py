import json

def resolver_locator_playwright(selector):
    """
    Mapea selectores semánticos especiales a llamadas de Locators nativos de Playwright Python.
    """
    if not selector:
        return "page"
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

def generar_script_automatizacion_dom(acciones_seleccionadas, nombre_archivo="automatizacion_dom.py", parametrizar=False):
    """
    Genera un script ejecutable de Playwright en Python que automatiza secuencialmente
    las acciones e interacciones grabadas sobre el DOM (clics, ingresos de texto, etc.).
    """
    codigo = []
    codigo.append("from playwright.sync_api import sync_playwright")
    codigo.append("import time")
    if parametrizar:
        codigo.append("import os")
    codigo.append("")
    codigo.append("def ejecutar_flujo_automatizado():")
    codigo.append("    print('[INFO] Iniciando automatización de Playwright...')")
    codigo.append("    with sync_playwright() as p:")
    codigo.append("        # Lanzamos el navegador visible (headless=False) para observar las acciones")
    codigo.append("        browser = p.chromium.launch(headless=False)")
    codigo.append("        context = browser.new_context(ignore_https_errors=True)")
    codigo.append("        page = context.new_page()")
    
    es_sap = any("sap" in str(a.get("valor", "")).lower() or "sap" in str(a.get("selector_sugerido", "")).lower() or "itsframe" in str(a.get("selector_sugerido", "")).lower() for a in acciones_seleccionadas)
    timeout_val = 30000 if es_sap else 10000
    codigo.append(f"        page.set_default_timeout({timeout_val})  # Timeout adaptativo por acción")
    codigo.append("")
    
    for idx, accion in enumerate(acciones_seleccionadas):
        tipo = accion.get("tipo_accion")
        selector = accion.get("selector_sugerido")
        if tipo == "extract" and accion.get("xpath"):
            selector = "xpath=" + accion.get("xpath")
        valor = accion.get("valor", "")
        desc = accion.get("descriptor_legible", f"Paso {idx}")
        
        locator_str = resolver_locator_playwright(selector)
        
        ruta_iframes = accion.get("ruta_iframes", [])
        if ruta_iframes:
            prefijo_frames = ""
            for iframe_sel in ruta_iframes:
                prefijo_frames += f".frame_locator({repr(iframe_sel)})"
            if locator_str.startswith("page"):
                locator_str = "page" + prefijo_frames + locator_str[4:]
        
        codigo.append(f"        # --------------------------------------------------")
        codigo.append(f"        # Paso {idx + 1}: {desc}")
        codigo.append(f"        # --------------------------------------------------")
        if tipo == "navigation":
            codigo.append(f"        print({repr(f'[PASO] Navegando a: {valor}')})")
            codigo.append(f"        page.goto({repr(valor)})")
            codigo.append("        page.wait_for_load_state('load')")
        elif tipo == "click":
            codigo.append(f"        print({repr(f'[PASO] Hacer clic en: {desc}')})")
            codigo.append(f"        {locator_str}.first.click()")
        elif tipo == "fill":
            es_secreto = (accion.get("type") == "password" or 
                          any(p in desc.lower() or p in (selector or "").lower() for p in ["pass", "clave", "contraseña", "secret"]))
            
            if parametrizar and es_secreto:
                var_name = f"RPA_SECRET_{idx + 1}"
                codigo.append(f"        # Valor parametrizado como variable de entorno por seguridad")
                codigo.append(f"        valor_secreto = os.environ.get({repr(var_name)}, {repr(valor)})")
                codigo.append(f"        print({repr(f'[PASO] Escribir credencial protegida ({var_name}) en: {desc}')})")
                codigo.append(f"        {locator_str}.first.fill(valor_secreto)")
            else:
                codigo.append(f"        print({repr(f'[PASO] Escribir \"{valor}\" en: {desc}')})")
                codigo.append(f"        {locator_str}.first.fill({repr(valor)})")
                
            if "okcode" in str(selector or "").lower() or "okcode" in locator_str.lower():
                codigo.append(f"        print({repr(f'[PASO] Presionar Enter para enviar comando en: {desc}')})")
                codigo.append(f"        {locator_str}.first.press('Enter')")
                codigo.append("        print('[PASO] Esperando 5 segundos para que SAP procese la transacción...')")
                codigo.append("        time.sleep(5)  # Pausa de espera transaccional")
        elif tipo == "select":
            codigo.append(f"        print({repr(f'[PASO] Seleccionar opción \"{valor}\" en: {desc}')})")
            codigo.append(f"        {locator_str}.first.select_option({repr(valor)})")
        elif tipo == "extract":
            codigo.append(f"        print({repr(f'[PASO] Extraer texto de: {desc}')})")
            codigo.append(f"        texto_extraido = {locator_str}.first.inner_text()")
            codigo.append(f"        print(f'[RESULTADO] Texto obtenido: {{texto_extraido}}')")
        
        codigo.append("        time.sleep(0.5)  # Breve pausa para estabilidad visual")
        codigo.append("")
        
    codigo.append("        print('[FIN] Flujo automatizado completado con éxito.')")
    codigo.append("        print('Cerrando navegador en 3 segundos...')")
    codigo.append("        time.sleep(3)")
    codigo.append("        browser.close()")
    codigo.append("")
    codigo.append("if __name__ == '__main__':")
    codigo.append("    ejecutar_flujo_automatizado()")
    
    contenido_codigo = "\n".join(codigo)
    
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
            "navigation": "Navegar a URL"
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
