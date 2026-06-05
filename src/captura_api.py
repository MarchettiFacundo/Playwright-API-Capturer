import json
import urllib.parse
from playwright.sync_api import sync_playwright

def limpiar_headers(headers):
    """
    Filtra headers del navegador que no son necesarios o pueden interferir 
    al replicar la petición con la librería requests en Python.
    """
    headers_filtrados = {}
    excluir = {
        'host', 'content-length', 'connection', 'accept-encoding',
        'sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform',
        'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-site',
        'sec-fetch-user', 'upgrade-insecure-requests'
    }
    for k, v in headers.items():
        if k.lower() not in excluir:
            headers_filtrados[k] = v
    return headers_filtrados

def parsear_seleccion(opcion, max_length):
    """
    Parsea cadenas de entrada complejas como '0', '0,2,3' o '0-3, 5'
    y devuelve una lista de enteros ordenados y validados.
    """
    indices = []
    partes = opcion.split(',')
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        if '-' in parte:
            subpartes = parte.split('-')
            if len(subpartes) == 2:
                try:
                    start = int(subpartes[0].strip())
                    end = int(subpartes[1].strip())
                    if start <= end:
                        indices.extend(range(start, end + 1))
                    else:
                        indices.extend(range(end, start + 1))
                except ValueError:
                    return None
            else:
                return None
        else:
            try:
                indices.append(int(parte))
            except ValueError:
                return None
                
    # Filtrar índices válidos y evitar duplicados
    indices_validos = []
    for idx in indices:
        if 0 <= idx < max_length:
            if idx not in indices_validos:
                indices_validos.append(idx)
        else:
            print(f"[WARN] Indice {idx} fuera de rango. Ignorado.")
            
    indices_validos.sort()
    return indices_validos

def extraer_token_de_valor(valor):
    """
    Limpia y extrae el string del token real quitando el prefijo Bearer si existe.
    """
    if not isinstance(valor, str):
        return valor
    if valor.lower().startswith("bearer "):
        return valor[7:].strip()
    return valor.strip()

def buscar_clave_de_valor(objeto_json, valor_buscado):
    """
    Busca de forma recursiva en un objeto JSON un string (token) de al menos 8 caracteres 
    y retorna la ruta (path) de claves de acceso (ej. ['data', 'token']).
    """
    if not isinstance(valor_buscado, str) or len(valor_buscado) < 8:
        return None
        
    if isinstance(objeto_json, dict):
        for k, v in objeto_json.items():
            if isinstance(v, str) and valor_buscado in v:
                return [k]
            if isinstance(v, (dict, list)):
                path = buscar_clave_de_valor(v, valor_buscado)
                if path:
                    return [k] + path
    elif isinstance(objeto_json, list):
        for idx, item in enumerate(objeto_json):
            if isinstance(item, str) and valor_buscado in item:
                return [idx]
            if isinstance(item, (dict, list)):
                path = buscar_clave_de_valor(item, valor_buscado)
                if path:
                    return [idx] + path
    return None

def formatear_path_seguro(path):
    """
    Convierte una lista de claves a formato de acceso seguro en Python: .get('clave', {})
    """
    partes = []
    for p in path:
        if isinstance(p, str):
            partes.append(f".get({repr(p)}, {{}})")
        else:
            partes.append(f"[{p}]")
            
    if partes:
        # Reemplazar el valor por defecto de la última clave para no retornar {} si falla
        ultimo = path[-1]
        if isinstance(ultimo, str):
            partes[-1] = f".get({repr(ultimo)})"
    return "".join(partes)

def resolver_locator_playwright(selector):
    """
    Mapea selectores semánticos especiales a llamadas de Locators nativos de Playwright Python.
    """
    if not selector:
        return "page"
    if selector.startswith("role:"):
        try:
            # Formato: role:nombre_rol[name="valor_name"]
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

def formatear_payload_python(obj, indent=8, seq_idx=0, path="", parametrizar=False):
    """
    Formatea recursivamente un objeto (dict o list) a representación de código Python,
    inyectando variables de entorno os.environ.get para claves que parecen credenciales si parametrizar es True.
    """
    espacio = " " * indent
    if isinstance(obj, dict):
        lineas = ["{"]
        for k, v in obj.items():
            nuevo_path = f"{path}_{k}" if path else k
            es_sensible = any(p in k.lower() for p in ["pass", "clave", "token", "secret", "user", "usuario", "mail", "correo"])
            if parametrizar and es_sensible and isinstance(v, (str, int, float)):
                var_name = f"RPA_API_PAYLOAD_{seq_idx}_{nuevo_path.upper()}"
                val_str = f"os.environ.get({repr(var_name)}, {repr(v)})"
            else:
                val_str = formatear_payload_python(v, indent + 4, seq_idx, nuevo_path, parametrizar)
            lineas.append(f"{espacio}    {repr(k)}: {val_str},")
        lineas.append(f"{espacio}}}")
        return "\n".join(lineas)
    elif isinstance(obj, list):
        lineas = ["["]
        for idx, item in enumerate(obj):
            nuevo_path = f"{path}_{idx}"
            val_str = formatear_payload_python(item, indent + 4, seq_idx, nuevo_path, parametrizar)
            lineas.append(f"{espacio}    {val_str},")
        lineas.append(f"{espacio}]")
        return "\n".join(lineas)
    else:
        return repr(obj)

def generar_script_python(peticion, nombre_archivo="request_generado.py", parametrizar=False):
    """
    Genera un script ejecutable de Python utilizando la librería requests
    con los mismos headers, cookies y payloads capturados.
    """
    url = peticion["url"]
    metodo = peticion["metodo"].upper()
    headers = limpiar_headers(peticion["headers_peticion"])
    payload = peticion["payload_enviado"]
    
    codigo = []
    codigo.append("import requests")
    codigo.append("import urllib3")
    codigo.append("import json")
    if parametrizar:
        codigo.append("import os")
    codigo.append("")
    codigo.append("# Deshabilitar advertencias de SSL inseguro debido a certificados no validos")
    codigo.append("urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)")
    codigo.append("")
    codigo.append("def ejecutar_peticion():")
    codigo.append("    # Usamos una sesion para almacenar y administrar cookies automaticamente")
    codigo.append("    session = requests.Session()")
    codigo.append("")
    codigo.append("    url = " + repr(url))
    codigo.append("")
    
    # Escribir Headers
    codigo.append("    headers = {")
    for k, v in headers.items():
        es_sensible = any(p in k.lower() for p in ["authorization", "token", "password", "clave", "apikey"])
        if parametrizar and es_sensible:
            var_name = f"RPA_API_HEADER_{k.replace('-', '_').upper()}"
            codigo.append(f"        {repr(k)}: os.environ.get({repr(var_name)}, {repr(v)}),")
        else:
            codigo.append(f"        {repr(k)}: {repr(v)},")
    codigo.append("    }")
    codigo.append("")
    
    # Escribir Payload
    if payload:
        try:
            payload_json = json.loads(payload)
            codigo.append("    # Payload detectado y formateado como JSON")
            formatted_payload = formatear_payload_python(payload_json, indent=8, seq_idx=0, parametrizar=parametrizar)
            codigo.append("    payload = " + formatted_payload)
            codigo.append("    is_json = True")
        except Exception:
            codigo.append("    # Payload detectado como texto plano o formulario codificado")
            codigo.append("    payload = " + repr(payload))
            codigo.append("    is_json = False")
    else:
        codigo.append("    payload = None")
        codigo.append("    is_json = False")
        
    codigo.append("")
    
    # Escribir llamada HTTP segun el metodo
    codigo.append(f"    print(f'[ENVIANDO] Enviando peticion {metodo} a {{url}}...')")
    codigo.append("    try:")
    
    if metodo == "GET":
        codigo.append("        response = session.get(url, headers=headers, verify=False)")
    elif metodo in ["POST", "PUT", "PATCH"]:
        req_method = metodo.lower()
        codigo.append("        if is_json:")
        codigo.append(f"            response = session.{req_method}(url, headers=headers, json=payload, verify=False)")
        codigo.append("        else:")
        codigo.append(f"            response = session.{req_method}(url, headers=headers, data=payload, verify=False)")
    else:
        codigo.append("        if is_json:")
        codigo.append(f"            response = session.request('{metodo}', url, headers=headers, json=payload, verify=False)")
        codigo.append("        else:")
        codigo.append(f"            response = session.request('{metodo}', url, headers=headers, data=payload, verify=False)")
    
    codigo.append("")
    codigo.append("        print(f'[STATUS] Status Code: {response.status_code}')")
    codigo.append("        try:")
    codigo.append("            response_json = response.json()")
    codigo.append("            print('[RESPUESTA] Respuesta (JSON):')")
    codigo.append("            print(json.dumps(response_json, indent=4, ensure_ascii=False))")
    codigo.append("        except Exception:")
    codigo.append("            print('[RESPUESTA] Respuesta (Texto):')")
    codigo.append("            print(response.text[:1000] + ('... [Truncado]' if len(response.text) > 1000 else ''))")
    codigo.append("            ")
    codigo.append("    except Exception as e:")
    codigo.append("        print(f'[ERROR] Error al realizar la peticion: {e}')")
    codigo.append("")
    codigo.append("if __name__ == '__main__':")
    codigo.append("    ejecutar_peticion()")
    
    contenido_codigo = "\n".join(codigo)
    
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(contenido_codigo)
        
    print(f"\n[GENERADO] Script de Python generado con exito en: {nombre_archivo}")
    print("="*70)
    print(contenido_codigo)
    print("="*70)

def generar_script_unificado(peticiones_seleccionadas, nombre_archivo="flujo_unificado.py", parametrizar=False):
    """
    Genera un único script secuencial en requests que ejecuta múltiples peticiones en orden
    manteniendo la sesión de cookies y vinculando tokens de forma dinámica y automática.
    """
    codigo = []
    codigo.append("import requests")
    codigo.append("import urllib3")
    codigo.append("import json")
    if parametrizar:
        codigo.append("import os")
    codigo.append("")
    codigo.append("# Deshabilitar advertencias de SSL inseguro debido a certificados no validos")
    codigo.append("urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)")
    codigo.append("")
    codigo.append("def ejecutar_flujo_unificado():")
    codigo.append("    # Usamos una sesion compartida para mantener cookies automaticamente entre peticiones")
    codigo.append("    session = requests.Session()")
    codigo.append("")
    
    # Para almacenar la información de respuestas previas para la heurística de tokens
    respuestas_previas = [] # { "secuencia_index": idx, "variable_name": var, "respuesta_json": json_data }
    
    for secuencia_idx, pet in enumerate(peticiones_seleccionadas):
        original_idx = pet["original_index"]
        url = pet["url"]
        metodo = pet["metodo"].upper()
        headers = limpiar_headers(pet["headers_peticion"])
        payload = pet["payload_enviado"]
        
        var_url = f"url_{secuencia_idx}"
        var_headers = f"headers_{secuencia_idx}"
        var_payload = f"payload_{secuencia_idx}"
        var_response = f"response_{secuencia_idx}"
        
        codigo.append(f"    # ======================================================================")
        codigo.append(f"    # PETICION {secuencia_idx} (Original [{original_idx}]): {metodo} {url[:70]}...")
        codigo.append(f"    # ======================================================================")
        codigo.append(f"    {var_url} = {repr(url)}")
        
        # Procesar cabeceras y buscar tokens dinámicos
        headers_estaticos = {}
        headers_dinamicos_codigo = []
        
        for k, v in headers.items():
            token_en_header = extraer_token_de_valor(v)
            encontrado_en_anterior = False
            
            # Solo buscamos si el token parece un JWT o clave larga para evitar falsos positivos
            if isinstance(token_en_header, str) and len(token_en_header) >= 8:
                for resp_previa in respuestas_previas:
                    if resp_previa["respuesta_json"]:
                        path = buscar_clave_de_valor(resp_previa["respuesta_json"], token_en_header)
                        if path:
                            path_seguro = formatear_path_seguro(path)
                            var_resp_prev = resp_previa["variable_name"]
                            
                            headers_dinamicos_codigo.append(f"    # Enlace dinamico: token detectado en la respuesta de la Peticion {resp_previa['secuencia_index']}")
                            headers_dinamicos_codigo.append("    try:")
                            headers_dinamicos_codigo.append(f"        token_dinamico = {var_resp_prev}.json(){path_seguro}")
                            headers_dinamicos_codigo.append("        if token_dinamico:")
                            if v.lower().startswith("bearer "):
                                headers_dinamicos_codigo.append(f"            {var_headers}[{repr(k)}] = f'Bearer {{token_dinamico}}'")
                            else:
                                headers_dinamicos_codigo.append(f"            {var_headers}[{repr(k)}] = token_dinamico")
                            headers_dinamicos_codigo.append("        else:")
                            headers_dinamicos_codigo.append(f"            {var_headers}[{repr(k)}] = {repr(v)}")
                            headers_dinamicos_codigo.append("    except Exception:")
                            headers_dinamicos_codigo.append(f"        {var_headers}[{repr(k)}] = {repr(v)}")
                            
                            encontrado_en_anterior = True
                            break
            
            if not encontrado_en_anterior:
                headers_estaticos[k] = v
                
        # Escribir Headers estáticos
        codigo.append(f"    {var_headers} = {{")
        for k, v in headers_estaticos.items():
            es_sensible = any(p in k.lower() for p in ["authorization", "token", "password", "clave", "apikey"])
            if parametrizar and es_sensible:
                var_name = f"RPA_API_HEADER_{secuencia_idx}_{k.replace('-', '_').upper()}"
                codigo.append(f"        {repr(k)}: os.environ.get({repr(var_name)}, {repr(v)}),")
            else:
                codigo.append(f"        {repr(k)}: {repr(v)},")
        codigo.append("    }")
        
        # Escribir Headers dinámicos si existen
        if headers_dinamicos_codigo:
            codigo.extend(headers_dinamicos_codigo)
            
        # Escribir Payload
        if payload:
            try:
                payload_json = json.loads(payload)
                codigo.append(f"    # Payload detectado como JSON")
                formatted_payload = formatear_payload_python(payload_json, indent=8, seq_idx=secuencia_idx, parametrizar=parametrizar)
                codigo.append(f"    {var_payload} = {formatted_payload}")
                codigo.append(f"    is_json_{secuencia_idx} = True")
            except Exception:
                codigo.append(f"    # Payload detectado como texto")
                codigo.append(f"    {var_payload} = " + repr(payload))
                codigo.append(f"    is_json_{secuencia_idx} = False")
        else:
            codigo.append(f"    {var_payload} = None")
            codigo.append(f"    is_json_{secuencia_idx} = False")
            
        codigo.append("")
        
        # Ejecutar petición
        codigo.append(f"    print(f'[ENVIANDO] Peticion {secuencia_idx} ({metodo}) a {{{var_url}}}...')")
        codigo.append("    try:")
        
        if metodo == "GET":
            codigo.append(f"        {var_response} = session.get({var_url}, headers={var_headers}, verify=False)")
        elif metodo in ["POST", "PUT", "PATCH"]:
            req_method = metodo.lower()
            codigo.append(f"        if is_json_{secuencia_idx}:")
            codigo.append(f"            {var_response} = session.{req_method}({var_url}, headers={var_headers}, json={var_payload}, verify=False)")
            codigo.append(f"        else:")
            codigo.append(f"            {var_response} = session.{req_method}({var_url}, headers={var_headers}, data={var_payload}, verify=False)")
        else:
            codigo.append(f"        if is_json_{secuencia_idx}:")
            codigo.append(f"            {var_response} = session.request('{metodo}', {var_url}, headers={var_headers}, json={var_payload}, verify=False)")
            codigo.append(f"        else:")
            codigo.append(f"            {var_response} = session.request('{metodo}', {var_url}, headers={var_headers}, data={var_payload}, verify=False)")
            
        codigo.append("")
        codigo.append(f"        print(f'[STATUS] Peticion {secuencia_idx} - Status Code: {{{var_response}.status_code}}')")
        
        # Imprimir respuesta JSON con valores / formateada
        codigo.append("        try:")
        codigo.append(f"            resp_data = {var_response}.json()")
        codigo.append("            print('[RESPUESTA] Respuesta (JSON):')")
        codigo.append("            print(json.dumps(resp_data, indent=4, ensure_ascii=False))")
        codigo.append("        except Exception:")
        codigo.append(f"            print('[RESPUESTA] Texto (truncado):', {var_response}.text[:1000])")
            
        codigo.append("    except Exception as e:")
        codigo.append(f"        print(f'[ERROR] Error en Peticion {secuencia_idx}: {{e}}')")
        
        # Registrar respuesta para futuras heurísticas
        resp_json_data = pet["respuesta"]
        respuestas_previas.append({
            "secuencia_index": secuencia_idx,
            "variable_name": var_response,
            "respuesta_json": resp_json_data if isinstance(resp_json_data, (dict, list)) else None
        })
        
        codigo.append("")
        codigo.append("    # " + "-"*60)
        codigo.append("")
        
    codigo.append("if __name__ == '__main__':")
    codigo.append("    ejecutar_flujo_unificado()")
    
    contenido_codigo = "\n".join(codigo)
    
    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write(contenido_codigo)
        
    print(f"\n[GENERADO] Script de flujo unificado generado con exito en: {nombre_archivo}")
    print("="*75)
    # Mostramos los primeros 1800 caracteres para consola
    print(contenido_codigo[:1800] + ("\n... [Truncado, revisa el archivo físico completo] ..." if len(contenido_codigo) > 1800 else ""))
    print("="*75)

def interceptor_manual(url_objetivo):
    archivo_log = "capturas_api.jsonl"
    peticiones_capturadas = []

    # Limpiar el archivo de logs anterior
    with open(archivo_log, "w", encoding="utf-8") as f:
        pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)

        def guardar_respuesta(response):
            if response.request.resource_type in ["fetch", "xhr"]:
                request = response.request
                if request.method == "OPTIONS":
                    return

                try:
                    datos_capturados = {
                        "url": response.url,
                        "metodo": request.method,
                        "status": response.status,
                        "headers_peticion": request.headers,
                        "headers_respuesta": response.headers,
                        "payload_enviado": request.post_data,
                        "respuesta": None
                    }

                    if response.ok:
                        try:
                            datos_capturados["respuesta"] = response.json()
                        except Exception:
                            try:
                                datos_capturados["respuesta"] = response.text()
                            except Exception as text_e:
                                datos_capturados["respuesta"] = f"<No se pudo leer el cuerpo: {str(text_e)}>"

                    with open(archivo_log, "a", encoding="utf-8") as f:
                        f.write(json.dumps(datos_capturados, ensure_ascii=False) + "\n")
                    
                    peticiones_capturadas.append(datos_capturados)
                    print(f"[OK] [{request.method}] {response.url}")

                except Exception as e:
                    print(f"[WARN] Error capturando {response.url}: {e}")

        context.on("response", guardar_respuesta)

        page = context.new_page()
        print(f"[INFO] Abriendo objetivo: {url_objetivo}")
        
        try:
            page.goto(url_objetivo)
        except Exception as err:
            print(f"[WARN] Error navegando a la pagina inicial: {err}")

        print("\n" + "="*60)
        print("[INTERCEPTADOR] MODO INTERCEPTACION MANUAL CON HEADERS")
        print("Realiza las acciones que desees capturar en el navegador.")
        print("Cuando hayas terminado, vuelve aqui y PRESIONA ENTER para cerrar el navegador.")
        print("="*60 + "\n")

        input()
        
        print("[CERRANDO] Cerrando el navegador y cargando el menu interactivo...")
        browser.close()

    if not peticiones_capturadas:
        print("[ERROR] No se capturaron peticiones Fetch/XHR.")
        return

    print(f"\n[INFO] Interceptacion terminada. Se capturaron {len(peticiones_capturadas)} peticiones.")

    while True:
        print("\n[MENU] LISTA DE PETICIONES CAPTURADAS:")
        for index, pet in enumerate(peticiones_capturadas):
            url_corta = pet["url"][:90] + "..." if len(pet["url"]) > 90 else pet["url"]
            print(f"[{index}] [{pet['metodo']}] Status: {pet['status']} | {url_corta}")
        
        print("\nOpciones de exportacion:")
        print("1. Para exportar una sola peticion, ingresa su numero (ej: 3).")
        print("2. Para unificar multiples peticiones, ingresalas separadas por comas (ej: 0,3) o rangos (ej: 0-3).")
        print("Escribe 'salir' para finalizar el programa.")
        opcion = input("> Opcion: ").strip()
        
        if opcion.lower() == 'salir':
            print("[INFO] Saliendo del capturador de APIs.")
            break
            
        indices_seleccionados = parsear_seleccion(opcion, len(peticiones_capturadas))
        if not indices_seleccionados:
            print("[ERROR] Entrada no valida o ningun indice dentro de rango.")
            continue
            
        if len(indices_seleccionados) == 1:
            idx = indices_seleccionados[0]
            nombre_script = f"request_generado_{idx}.py"
            generar_script_python(peticiones_capturadas[idx], nombre_archivo=nombre_script)
        else:
            print(f"[INFO] Generando flujo unificado para peticiones: {indices_seleccionados}")
            # Estructurar la lista con su índice original para la visualización y auditoría
            peticiones_a_unificar = []
            for s_idx, idx in enumerate(indices_seleccionados):
                peticion_copia = peticiones_capturadas[idx].copy()
                peticion_copia["original_index"] = idx
                peticiones_a_unificar.append(peticion_copia)
                
            nombre_script = "flujo_unificado.py"
            generar_script_unificado(peticiones_a_unificar, nombre_archivo=nombre_script)

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
    
    # Timeout adaptativo: 30s si es SAP (ITS WebGUI), 10s por defecto
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
        
        # Traducir selector usando resolver_locator_playwright
        locator_str = resolver_locator_playwright(selector)
        
        # Soporte para iFrames: Inyectar frame_locator si la acción ocurrió dentro de un iframe
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
                
            # Regla de automatización para SAP: presionar Enter automáticamente tras escribir comandos en OkCode
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
    if __name__ == '__main__':
        pass # Evitar doble impresión en compilación
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
    import json
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
            
            # Selectores alternativos
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

if __name__ == "__main__":
    interceptor_manual("https://rpa-site.claro.amx/")
