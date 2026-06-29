import json
from src.utils.helpers import limpiar_headers

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
        ultimo = path[-1]
        if isinstance(ultimo, str):
            partes[-1] = f".get({repr(ultimo)})"
    return "".join(partes)

def formatear_payload_python(obj, indent=8, seq_idx=0, path="", parametrizar=False):
    """
    Formatea recursivamente un objeto (dict o list) a representación de código Python,
    inyectando variables de entorno os.environ.get para claves sensibles si parametrizar es True.
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
    return contenido_codigo

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
    
    respuestas_previas = []
    
    for secuencia_idx, pet in enumerate(peticiones_seleccionadas):
        original_idx = pet.get("original_index", secuencia_idx)
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
        
        headers_estaticos = {}
        headers_dinamicos_codigo = []
        
        for k, v in headers.items():
            token_en_header = extraer_token_de_valor(v)
            encontrado_en_anterior = False
            
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
                
        codigo.append(f"    {var_headers} = {{")
        for k, v in headers_estaticos.items():
            es_sensible = any(p in k.lower() for p in ["authorization", "token", "password", "clave", "apikey"])
            if parametrizar and es_sensible:
                var_name = f"RPA_API_HEADER_{secuencia_idx}_{k.replace('-', '_').upper()}"
                codigo.append(f"        {repr(k)}: os.environ.get({repr(var_name)}, {repr(v)}),")
            else:
                codigo.append(f"        {repr(k)}: {repr(v)},")
        codigo.append("    }")
        
        if headers_dinamicos_codigo:
            codigo.extend(headers_dinamicos_codigo)
            
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
        
        codigo.append("        try:")
        codigo.append(f"            resp_data = {var_response}.json()")
        codigo.append("            print('[RESPUESTA] Respuesta (JSON):')")
        codigo.append("            print(json.dumps(resp_data, indent=4, ensure_ascii=False))")
        codigo.append("        except Exception:")
        codigo.append(f"            print('[RESPUESTA] Texto (truncado):', {var_response}.text[:1000])")
            
        codigo.append("    except Exception as e:")
        codigo.append(f"        print(f'[ERROR] Error en Peticion {secuencia_idx}: {{e}}')")
        
        resp_json_data = pet.get("respuesta")
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
    return contenido_codigo
