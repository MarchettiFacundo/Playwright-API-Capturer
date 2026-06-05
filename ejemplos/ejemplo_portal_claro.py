import os
import time
from playwright.sync_api import sync_playwright

def automatizar_portal_claro():
    """
    Script de demostración de Playwright adaptado para el portal de Claro.
    Maneja de forma robusta la omisión de errores SSL y la captura de trazas visuales.
    """
    url_portal = "https://rpa-site.claro.amx/"
    output_dir = "output_videos"
    
    # Crear directorio para almacenar los videos si no existe
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("[INFO] Iniciando motor de automatización Playwright...")
    with sync_playwright() as p:
        # Lanzamos el navegador Chromium
        # slow_mo=300 ralentiza cada acción para facilitar el seguimiento visual
        browser = p.chromium.launch(headless=False, slow_mo=300)
        
        # Creamos un contexto configurado para:
        # 1. Omitir errores de certificados SSL inválidos (ignore_https_errors=True)
        # 2. Configurar una resolución de pantalla estándar (1280x800)
        # 3. Grabar un video de toda la sesión de automatización
        print("[INFO] Configurando el contexto del navegador (Ignorando errores SSL)...")
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            ignore_https_errors=True,
            record_video_dir=output_dir + "/"
        )
        
        # Iniciamos el registro de trazas de Playwright (Traces), ideal para auditoría y debug
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = context.new_page()

        try:
            print(f"[INFO] Navegando a la web de ejemplo: {url_portal}")
            # wait_until="networkidle" espera a que no haya peticiones de red activas por 500ms
            page.goto(url_portal, wait_until="load", timeout=30000)
            
            # Tomar una captura de pantalla inicial
            captura_inicial = "captura_inicio_claro.png"
            page.screenshot(path=captura_inicial, full_page=True)
            print(f"[OK] Captura inicial guardada como: {captura_inicial}")

            print("[INFO] Esperando 5 segundos para simular lectura/interacción...")
            time.sleep(5)

            # Ejemplos de buenas prácticas en selectores semánticos listos para cuando el portal los exponga:
            # -----------------------------------------------------------------------------------------
            # 1. Ingresar datos en el cuadro de Login (por placeholder o etiqueta)
            # if page.get_by_placeholder("Usuario").is_visible():
            #     page.get_by_placeholder("Usuario").fill("RPA_USER")
            #     page.get_by_placeholder("Contraseña").fill("CLAVE_EJEMPLO")
            #     page.get_by_role("button", name="Ingresar").click()
            
            # 2. Navegar a través de links o menús
            # page.get_by_role("link", name="Reportes").click()

            print("[OK] Flujo de navegación de prueba completado con éxito.")

        except Exception as e:
            print(f"[ERROR] Ocurrió un error inesperado durante el flujo: {e}")
            captura_error = "captura_error_claro.png"
            page.screenshot(path=captura_error, full_page=True)
            print(f"[OK] Captura del error guardada como: {captura_error}")
            
        finally:
            # Guardamos la traza para depuración detallada (se puede abrir en trace.playwright.dev)
            trace_path = "trace_claro.zip"
            context.tracing.stop(path=trace_path)
            print(f"[INFO] Registro de trazas detalladas guardado en: {trace_path}")
            
            # Cerramos limpiamente el contexto y el navegador
            print("[INFO] Finalizando procesos y cerrando navegador...")
            context.close()
            browser.close()
            print("[INFO] Proceso finalizado.")

if __name__ == "__main__":
    automatizar_portal_claro()
