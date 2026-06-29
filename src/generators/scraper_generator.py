from src.generators.dom_generator import resolver_locator_playwright

def generar_nombre_campo_auto(accion):
    """
    Genera un nombre de campo descriptivo automáticamente para un elemento 
    capturado en modo scraper, basado en sus atributos HTML.
    Ejemplo: "h2_titulo", "span_precio", "a_enlace_1"
    """
    tag = (accion.get("tagName") or "").lower()
    id_el = accion.get("id", "")
    name_el = accion.get("name", "")
    placeholder = accion.get("placeholder", "")
    clase = accion.get("className", "")
    
    if id_el and len(id_el) <= 30 and id_el.isidentifier():
        return f"{tag}_{id_el}".lower().replace("-", "_")
    
    if name_el and len(name_el) <= 30 and name_el.replace("-", "_").replace(".", "_").isidentifier():
        return f"{tag}_{name_el}".lower().replace("-", "_").replace(".", "_")
    
    clases_genericas = {"active", "selected", "hover", "disabled", "hidden", "visible", "col", "row", "container", "wrapper", "flex", "grid"}
    if clase:
        for cls in clase.split():
            cls_limpia = cls.replace("-", "_").replace(".", "_")
            if cls_limpia.isidentifier() and cls_limpia.lower() not in clases_genericas:
                return f"{tag}_{cls_limpia[:25]}".lower()
    
    if placeholder:
        ph_limpio = placeholder[:20].lower().replace(" ", "_").replace("-", "_")
        ph_limpio = "".join(c for c in ph_limpio if c.isalnum() or c == "_")
        if ph_limpio:
            return f"{tag}_{ph_limpio}"
    
    tag_nombres = {
        "h1": "titulo_principal", "h2": "titulo", "h3": "subtitulo",
        "h4": "subtitulo_4", "h5": "subtitulo_5", "h6": "subtitulo_6",
        "p": "parrafo", "span": "texto", "div": "contenedor",
        "a": "enlace", "img": "imagen", "td": "celda_tabla",
        "th": "encabezado_tabla", "li": "item_lista", "input": "campo_input",
        "button": "boton", "select": "selector_lista", "textarea": "area_texto"
    }
    return tag_nombres.get(tag, f"campo_{tag}")

def generar_script_scraping(campos_scraping, url_objetivo, config_scraping, nombre_archivo="scraper_generado.py", parametrizar=False):
    """
    Genera un script Playwright ejecutable con DOS FASES claramente diferenciadas:
    FASE 1 - SETUP / LOGIN y FASE 2 - EXTRACCIÓN DE DATOS.
    """
    pasos_setup   = [c for c in campos_scraping if c.get("fase_scraper", "extract") == "setup"]
    campos_extract = [c for c in campos_scraping if c.get("fase_scraper", "extract") == "extract"]

    selector_paginacion = config_scraping.get("selector_paginacion", "")
    max_paginas         = config_scraping.get("max_paginas", 0)
    delay_paginas       = config_scraping.get("delay_paginas", 1.5)
    formato_csv         = config_scraping.get("formato_csv", True)
    formato_json        = config_scraping.get("formato_json", True)
    headless            = config_scraping.get("headless", True)

    codigo = []
    codigo.append("from playwright.sync_api import sync_playwright")
    codigo.append("import json")
    codigo.append("import time")
    if parametrizar:
        codigo.append("import os")
    if formato_csv:
        codigo.append("import csv")
    codigo.append("")
    codigo.append("")
    codigo.append("# =============================================================")
    codigo.append("# SCRIPT DE SCRAPING GENERADO POR PLAYWRIGHT API CAPTURER")
    codigo.append(f"# URL Objetivo: {url_objetivo}")
    codigo.append(f"# Pasos de Setup (login/navegacion): {len(pasos_setup)}")
    codigo.append(f"# Campos a extraer: {len(campos_extract)}")
    codigo.append("# =============================================================")
    codigo.append("")
    codigo.append("")

    codigo.append("def extraer_texto_elemento(pagina, selector, xpath):")
    codigo.append('    """Extrae el texto visible de un elemento usando el mejor selector disponible."""')
    codigo.append("    try:")
    codigo.append("        if xpath:")
    codigo.append("            el = pagina.locator(f'xpath={xpath}').first")
    codigo.append("        else:")
    codigo.append("            el = pagina.locator(selector).first")
    codigo.append("        if el.count() == 0:")
    codigo.append("            return None")
    codigo.append("        return el.inner_text().strip()")
    codigo.append("    except Exception:")
    codigo.append("        return None")
    codigo.append("")
    codigo.append("")
    codigo.append("def extraer_atributo_elemento(pagina, selector, xpath, atributo):")
    codigo.append('    """Extrae el valor de un atributo HTML de un elemento."""')
    codigo.append("    try:")
    codigo.append("        if xpath:")
    codigo.append("            el = pagina.locator(f'xpath={xpath}').first")
    codigo.append("        else:")
    codigo.append("            el = pagina.locator(selector).first")
    codigo.append("        if el.count() == 0:")
    codigo.append("            return None")
    codigo.append("        return el.get_attribute(atributo)")
    codigo.append("    except Exception:")
    codigo.append("        return None")
    codigo.append("")
    codigo.append("")

    codigo.append("def ejecutar_scraping():")
    codigo.append(f"    url_inicial = {repr(url_objetivo)}")
    if max_paginas > 0:
        codigo.append(f"    max_paginas = {max_paginas}")
    else:
        codigo.append("    max_paginas = 0  # 0 = sin limite de paginas")
    codigo.append(f"    delay_entre_paginas = {delay_paginas}")
    codigo.append("    resultados = []")
    codigo.append("")
    codigo.append(f"    with sync_playwright() as p:")
    codigo.append(f"        browser = p.chromium.launch(headless={str(headless)})")
    codigo.append("        context = browser.new_context(ignore_https_errors=True)")
    codigo.append("        page = context.new_page()")
    codigo.append("")

    if pasos_setup:
        codigo.append("        # ======================================================")
        codigo.append("        # FASE 1: SETUP / LOGIN")
        codigo.append("        # ======================================================")

        for i, paso in enumerate(pasos_setup):
            tipo       = paso.get("tipo_accion", "")
            selector   = paso.get("selector_sugerido", "")
            valor      = paso.get("valor", "")
            desc       = paso.get("descriptor_legible", f"Paso {i + 1}")

            locator_str = resolver_locator_playwright(selector)

            ruta_iframes = paso.get("ruta_iframes", [])
            if ruta_iframes:
                prefijo = "".join(f".frame_locator({repr(s)})" for s in ruta_iframes)
                if locator_str.startswith("page"):
                    locator_str = "page" + prefijo + locator_str[4:]

            codigo.append(f"        # -- Setup Paso {i + 1}: {desc} --")

            if tipo == "navigation":
                nav_url = valor or url_objetivo
                codigo.append(f"        print('[SETUP] Navegando a: {nav_url[:80]}')")
                codigo.append(f"        page.goto({repr(nav_url)}, wait_until='domcontentloaded')")
                codigo.append("        page.wait_for_timeout(1500)")

            elif tipo == "click":
                codigo.append(f"        print('[SETUP] Clic en: {desc}')")
                codigo.append(f"        {locator_str}.first.click()")
                codigo.append("        page.wait_for_load_state('domcontentloaded')")
                codigo.append("        page.wait_for_timeout(1000)")

            elif tipo == "fill":
                desc_lower   = desc.lower()
                sel_lower    = selector.lower()
                es_secreto   = (
                    paso.get("type") == "password" or
                    any(p in desc_lower + sel_lower for p in
                        ["pass", "clave", "contraseña", "secret", "password"])
                )
                if parametrizar and es_secreto:
                    var_name = f"RPA_SCRAPER_SECRET_{i + 1}"
                    codigo.append(f"        # CREDENCIAL: valor leido de variable de entorno {var_name}")
                    codigo.append(f"        {locator_str}.first.fill(os.environ.get({repr(var_name)}, {repr(valor)}))")
                else:
                    codigo.append(f"        print('[SETUP] Llenando: {desc}')")
                    codigo.append(f"        {locator_str}.first.fill({repr(valor)})")

            elif tipo == "select":
                codigo.append(f"        print('[SETUP] Seleccionando: {desc}')")
                codigo.append(f"        {locator_str}.first.select_option({repr(valor)})")

            codigo.append("        page.wait_for_timeout(500)")
            codigo.append("")

        codigo.append("        try:")
        codigo.append("            page.wait_for_load_state('networkidle', timeout=8000)")
        codigo.append("        except Exception:")
        codigo.append("            pass")
        codigo.append("        page.wait_for_timeout(2000)")
        codigo.append("")
    else:
        codigo.append("        # ======================================================")
        codigo.append("        # Navegación inicial")
        codigo.append("        # ======================================================")
        codigo.append(f"        print(f'[SCRAPER] Navegando a: {{url_inicial}}')")
        codigo.append("        page.goto(url_inicial, wait_until='domcontentloaded')")
        codigo.append("        page.wait_for_timeout(1500)")
        codigo.append("")

    if campos_extract:
        codigo.append("        # ======================================================")
        codigo.append("        # FASE 2: EXTRACCIÓN DE DATOS (loop de paginación)")
        codigo.append("        # ======================================================")
        codigo.append("        numero_pagina = 1")
        codigo.append("        while True:")
        codigo.append("            print(f'[SCRAPER] Extrayendo pagina {numero_pagina}...')")
        codigo.append("            registro = {}")
        codigo.append("")

        for campo in campos_extract:
            nombre   = campo.get("nombre_campo", "campo")
            selector = campo.get("selector_sugerido", "")
            xpath    = campo.get("xpath", "")
            tag      = campo.get("tagName", "").lower()

            codigo.append(f"            # Campo: {nombre}")
            if tag == "a":
                codigo.append(f"            registro[{repr(nombre)}] = extraer_atributo_elemento(page, {repr(selector)}, {repr(xpath)}, 'href')")
            elif tag == "img":
                codigo.append(f"            registro[{repr(nombre)}] = extraer_atributo_elemento(page, {repr(selector)}, {repr(xpath)}, 'src')")
            else:
                codigo.append(f"            registro[{repr(nombre)}] = extraer_texto_elemento(page, {repr(selector)}, {repr(xpath)})")

        codigo.append("")
        codigo.append("            resultados.append(registro)")
        codigo.append("            print(f'[OK] Pagina {numero_pagina}: {registro}')")
        codigo.append("")

        if selector_paginacion:
            codigo.append("            # -- Paginacion automatica --")
            codigo.append(f"            if max_paginas > 0 and numero_pagina >= max_paginas:")
            codigo.append("                print('[SCRAPER] Limite de paginas alcanzado.')")
            codigo.append("                break")
            codigo.append("")
            codigo.append(f"            btn_sig = page.locator({repr(selector_paginacion)})")
            codigo.append("            if btn_sig.count() == 0 or btn_sig.first.is_disabled():")
            codigo.append("                print('[SCRAPER] No hay mas paginas.')")
            codigo.append("                break")
            codigo.append("")
            codigo.append("            btn_sig.first.click()")
            codigo.append("            page.wait_for_load_state('domcontentloaded')")
            codigo.append(f"            time.sleep({delay_paginas})")
            codigo.append("            numero_pagina += 1")
        else:
            codigo.append("            break")
    else:
        codigo.append("        # Sin campos de extraccion configurados")

    codigo.append("")
    codigo.append("        browser.close()")
    codigo.append("")
    codigo.append("    total = len(resultados)")
    codigo.append("    print(f'\\n[SCRAPER] Completado. Total de registros: {total}')")
    codigo.append("")

    if formato_csv:
        codigo.append("    if resultados:")
        codigo.append("        nombre_csv = 'resultados_scraping.csv'")
        codigo.append("        with open(nombre_csv, 'w', newline='', encoding='utf-8-sig') as f_csv:")
        codigo.append("            writer = csv.DictWriter(f_csv, fieldnames=resultados[0].keys())")
        codigo.append("            writer.writeheader()")
        codigo.append("            writer.writerows(resultados)")
        codigo.append("        print(f'[EXPORTADO] CSV guardado en: {nombre_csv}')")
        codigo.append("")

    if formato_json:
        codigo.append("    nombre_json = 'resultados_scraping.json'")
        codigo.append("    with open(nombre_json, 'w', encoding='utf-8') as f_json:")
        codigo.append("        json.dump(resultados, f_json, indent=4, ensure_ascii=False)")
        codigo.append("    print(f'[EXPORTADO] JSON guardado en: {nombre_json}')")
        codigo.append("")

    codigo.append("    return resultados")
    codigo.append("")
    codigo.append("")
    codigo.append("if __name__ == '__main__':")
    codigo.append("    datos = ejecutar_scraping()")
    codigo.append("    print(f'\\n[FIN] Se extrajeron {len(datos)} registros.')")

    contenido_codigo = "\n".join(codigo)
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(contenido_codigo)

    print(f"\n[GENERADO] Script Playwright (dual-fase) generado: {nombre_archivo}")
    return contenido_codigo

def generar_script_scraping_bs4(campos_extract, url_objetivo, config_scraping, nombre_archivo="scraper_bs4.py", login_config=None):
    """
    Genera un script de scraping usando requests + BeautifulSoup4 con soporte opcional de login.
    """
    selector_paginacion = config_scraping.get("selector_paginacion", "")
    max_paginas         = config_scraping.get("max_paginas", 0)
    delay_paginas       = config_scraping.get("delay_paginas", 1.0)
    formato_csv         = config_scraping.get("formato_csv", True)
    formato_json        = config_scraping.get("formato_json", True)

    def selector_a_css(selector):
        if not selector:
            return None
        s = selector.strip()
        if s.startswith("xpath=") or s.startswith("role:") or s.startswith("text=") or s.startswith("label="):
            return None
        if s.startswith("id="):
            return f"#{s[3:]}"
        if s.startswith("placeholder="):
            ph = s[12:].strip('"').strip("'")
            return f'[placeholder="{ph}"]'
        if s.startswith("name="):
            nm = s[5:].strip('"').strip("'")
            return f'[name="{nm}"]'
        return s

    lc              = login_config or {}
    login_url       = lc.get("login_url", "").strip()
    user_field      = lc.get("user_field", "username")
    pass_field      = lc.get("pass_field", "password")
    auth_tipo       = lc.get("auth_tipo", "form_post")
    token_field     = lc.get("token_field", "token")
    tiene_login     = bool(login_url)

    codigo = []
    codigo.append("import requests")
    codigo.append("from bs4 import BeautifulSoup")
    codigo.append("import json")
    codigo.append("import time")
    if tiene_login:
        codigo.append("import os")
    if formato_csv:
        codigo.append("import csv")
    codigo.append("from urllib.parse import urljoin")
    if auth_tipo == "basic_auth" and tiene_login:
        codigo.append("from requests.auth import HTTPBasicAuth")
    codigo.append("import urllib3")
    codigo.append("urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)")
    codigo.append("")
    codigo.append("")
    codigo.append("# =============================================================")
    codigo.append("# SCRIPT DE SCRAPING GENERADO POR PLAYWRIGHT API CAPTURER")
    codigo.append("# Motor: requests + BeautifulSoup (sitios estaticos / sin JS)")
    codigo.append(f"# URL Objetivo: {url_objetivo}")
    codigo.append(f"# Campos a extraer: {len(campos_extract)}")
    codigo.append("# =============================================================")
    codigo.append("# REQUISITO: pip install requests beautifulsoup4 lxml")
    codigo.append("")
    codigo.append("")

    codigo.append("HEADERS = {")
    codigo.append("    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'")
    codigo.append("                  ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',")
    codigo.append("    'Accept-Language': 'es-AR,es;q=0.9',")
    codigo.append("    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',")
    codigo.append("}")
    codigo.append("")
    codigo.append("")

    codigo.append("def extraer_campo_bs4(soup, selector_css, xpath, atributo=None):")
    codigo.append('    """Extrae un campo del HTML usando CSS selector (o XPath con lxml como fallback)."""')
    codigo.append("    try:")
    codigo.append("        if selector_css:")
    codigo.append("            el = soup.select_one(selector_css)")
    codigo.append("            if not el:")
    codigo.append("                return None")
    codigo.append("            return el.get(atributo) if atributo else el.get_text(strip=True)")
    codigo.append("        elif xpath:")
    codigo.append("            from lxml import etree")
    codigo.append("            tree = etree.fromstring(str(soup).encode(), etree.HTMLParser())")
    codigo.append("            result = tree.xpath(xpath)")
    codigo.append("            if not result:")
    codigo.append("                return None")
    codigo.append("            el = result[0]")
    codigo.append("            if atributo:")
    codigo.append("                return el.get(atributo)")
    codigo.append("            return etree.tostring(el, method='text', encoding='unicode').strip()")
    codigo.append("    except Exception:")
    codigo.append("        return None")
    codigo.append("    return None")
    codigo.append("")
    codigo.append("")

    codigo.append("def ejecutar_scraping():")
    codigo.append(f"    url = {repr(url_objetivo)}")
    if max_paginas > 0:
        codigo.append(f"    max_paginas = {max_paginas}")
    else:
        codigo.append("    max_paginas = 0  # 0 = sin limite")
    codigo.append(f"    delay_entre_paginas = {delay_paginas}")
    codigo.append("    session = requests.Session()")
    codigo.append("    session.headers.update(HEADERS)")

    if tiene_login:
        codigo.append("")
        codigo.append("    # ======================================================")
        codigo.append("    # FASE 1: AUTENTICACION (login via requests)")
        codigo.append("    # ======================================================")
        codigo.append(f"    LOGIN_URL = {repr(login_url)}")
        codigo.append(f"    USUARIO = os.environ.get('RPA_BS4_USER', 'tu_usuario_aqui')")
        codigo.append(f"    CONTRASENA = os.environ.get('RPA_BS4_PASS', 'tu_contrasena_aqui')")
        codigo.append("")

        if auth_tipo == "form_post":
            codigo.append("    print('[LOGIN] Autenticando via Form POST...')")
            codigo.append(f"    login_resp = session.post(LOGIN_URL, data={{")
            codigo.append(f"        {repr(user_field)}: USUARIO,")
            codigo.append(f"        {repr(pass_field)}: CONTRASENA,")
            codigo.append("    }, verify=False, timeout=20)")
            codigo.append("    login_resp.raise_for_status()")
            codigo.append("    print(f'[LOGIN] Respuesta: {{login_resp.status_code}}')")

        elif auth_tipo == "json_post":
            codigo.append("    print('[LOGIN] Autenticando via JSON POST...')")
            codigo.append(f"    login_resp = session.post(LOGIN_URL, json={{")
            codigo.append(f"        {repr(user_field)}: USUARIO,")
            codigo.append(f"        {repr(pass_field)}: CONTRASENA,")
            codigo.append("    }, verify=False, timeout=20)")
            codigo.append("    login_resp.raise_for_status()")
            codigo.append(f"    token = login_resp.json().get({repr(token_field)})")
            codigo.append("    if not token:")
            codigo.append(f"        print(f'[ERROR] No se encontro el campo \"{token_field}\" en la respuesta. Respuesta: {{login_resp.text[:200]}}')")
            codigo.append("        raise RuntimeError('Login fallido: token no encontrado')")
            codigo.append("    print(f'[LOGIN] Token obtenido: {{token[:20]}}...')")
            codigo.append("    session.headers.update({'Authorization': f'Bearer {token}'})")

        elif auth_tipo == "bearer_token":
            codigo.append("    print('[LOGIN] Obteniendo Bearer Token...')")
            codigo.append(f"    login_resp = session.post(LOGIN_URL, json={{")
            codigo.append(f"        {repr(user_field)}: USUARIO,")
            codigo.append(f"        {repr(pass_field)}: CONTRASENA,")
            codigo.append("    }, verify=False, timeout=20)")
            codigo.append("    login_resp.raise_for_status()")
            codigo.append(f"    token = login_resp.json().get({repr(token_field)})")
            codigo.append("    if not token:")
            codigo.append(f"        print(f'[ERROR] Token no encontrado en respuesta: {{login_resp.text[:200]}}')")
            codigo.append("        raise RuntimeError('Login fallido: token no encontrado')")
            codigo.append("    print(f'[LOGIN] Bearer token obtenido: {{token[:20]}}...')")
            codigo.append("    session.headers.update({'Authorization': f'Bearer {token}'})")

        elif auth_tipo == "basic_auth":
            codigo.append("    print('[LOGIN] Configurando Basic Auth...')")
            codigo.append("    session.auth = HTTPBasicAuth(USUARIO, CONTRASENA)")

        codigo.append("")
        codigo.append("    print('[LOGIN] Autenticacion completada.')")
        codigo.append("")

    codigo.append("    resultados = []")
    codigo.append("    pagina = 1")

    codigo.append("")
    codigo.append("    while True:")
    codigo.append("        print(f'[SCRAPER] Descargando pagina {pagina}: {url}')")
    codigo.append("        response = session.get(url, verify=False, timeout=30)")
    codigo.append("        response.raise_for_status()")
    codigo.append("        soup = BeautifulSoup(response.text, 'html.parser')")
    codigo.append("")
    codigo.append("        registro = {}")

    for campo in campos_extract:
        nombre   = campo.get("nombre_campo", "campo")
        selector = campo.get("selector_sugerido", "")
        xpath    = campo.get("xpath", "")
        tag      = campo.get("tagName", "").lower()

        css = selector_a_css(selector)
        xpath_val = xpath if not css else None

        codigo.append(f"        # Campo: {nombre}")
        if tag == "a":
            codigo.append(f"        registro[{repr(nombre)}] = extraer_campo_bs4(soup, {repr(css)}, {repr(xpath_val)}, 'href')")
        elif tag == "img":
            codigo.append(f"        registro[{repr(nombre)}] = extraer_campo_bs4(soup, {repr(css)}, {repr(xpath_val)}, 'src')")
        else:
            codigo.append(f"        registro[{repr(nombre)}] = extraer_campo_bs4(soup, {repr(css)}, {repr(xpath_val)})")

    codigo.append("")
    codigo.append("        resultados.append(registro)")
    codigo.append("        print(f'[OK] Pagina {pagina}: {registro}')")
    codigo.append("")

    if selector_paginacion:
        css_next = selector_a_css(selector_paginacion)
        codigo.append("        # -- Paginacion: buscar enlace 'Siguiente' --")
        codigo.append(f"        if max_paginas > 0 and pagina >= max_paginas:")
        codigo.append("            break")
        codigo.append("")
        if css_next:
            codigo.append(f"        btn_siguiente = soup.select_one({repr(css_next)})")
        else:
            codigo.append(f"        btn_siguiente = soup.select_one({repr(selector_paginacion)})")
        codigo.append("        if not btn_siguiente:")
        codigo.append("            print('[SCRAPER] No hay mas paginas.')")
        codigo.append("            break")
        codigo.append("")
        codigo.append("        href_siguiente = btn_siguiente.get('href')")
        codigo.append("        if not href_siguiente:")
        codigo.append("            print('[SCRAPER] Boton de paginacion sin href. Fin.')")
        codigo.append("            break")
        codigo.append("")
        codigo.append(f"        url = urljoin({repr(url_objetivo)}, href_siguiente)")
        codigo.append(f"        time.sleep({delay_paginas})")
        codigo.append("        pagina += 1")
    else:
        codigo.append("        break")

    codigo.append("")
    codigo.append("    total = len(resultados)")
    codigo.append("    print(f'\\n[SCRAPER] Completado. Total de registros: {total}')")
    codigo.append("")

    if formato_csv:
        codigo.append("    if resultados:")
        codigo.append("        nombre_csv = 'resultados_scraping.csv'")
        codigo.append("        with open(nombre_csv, 'w', newline='', encoding='utf-8-sig') as f_csv:")
        codigo.append("            writer = csv.DictWriter(f_csv, fieldnames=resultados[0].keys())")
        codigo.append("            writer.writeheader()")
        codigo.append("            writer.writerows(resultados)")
        codigo.append("        print(f'[EXPORTADO] CSV guardado en: {nombre_csv}')")
        codigo.append("")

    if formato_json:
        codigo.append("    nombre_json = 'resultados_scraping.json'")
        codigo.append("    with open(nombre_json, 'w', encoding='utf-8') as f_json:")
        codigo.append("        json.dump(resultados, f_json, indent=4, ensure_ascii=False)")
        codigo.append("    print(f'[EXPORTADO] JSON guardado en: {nombre_json}')")
        codigo.append("")

    codigo.append("    return resultados")
    codigo.append("")
    codigo.append("")
    codigo.append("if __name__ == '__main__':")
    codigo.append("    datos = ejecutar_scraping()")
    codigo.append("    print(f'\\n[FIN] {len(datos)} registros extraidos.')")

    contenido_codigo = "\n".join(codigo)
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(contenido_codigo)

    print(f"\n[GENERADO] Script BS4 generado: {nombre_archivo}")
    return contenido_codigo
