import json
from playwright.sync_api import sync_playwright
from src.utils.helpers import parsear_seleccion
from src.generators.api_generator import generar_script_python, generar_script_unificado

def interceptor_manual(url_objetivo):
    """
    Modo interactivo en consola para capturar peticiones Fetch/XHR navegando manualmente.
    """
    archivo_log = "capturas_api.jsonl"
    peticiones_capturadas = []

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
            peticiones_a_unificar = []
            for s_idx, idx in enumerate(indices_seleccionados):
                peticion_copia = peticiones_capturadas[idx].copy()
                peticion_copia["original_index"] = idx
                peticiones_a_unificar.append(peticion_copia)
                
            nombre_script = "flujo_unificado.py"
            generar_script_unificado(peticiones_a_unificar, nombre_archivo=nombre_script)
