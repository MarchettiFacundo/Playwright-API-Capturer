from playwright.sync_api import sync_playwright

def probar_playwright():
    # Iniciamos la sesión de Playwright
    with sync_playwright() as p:
        
        # 1. LANZAMIENTO DEL NAVEGADOR
        # headless=False: Abre la interfaz gráfica para que veas lo que pasa.
        # slow_mo=500: Ralentiza cada acción 500ms para que el ojo humano pueda seguirla.
        # Nota: En tu contenedor de Podman, cambiarías a headless=True y quitarías slow_mo.
        print("🚀 Lanzando navegador...")
        browser = p.chromium.launch(headless=False, slow_mo=500)

        # 2. CONTEXTOS Y EMULACIÓN
        # Creamos un contexto aislado. Aquí configuramos el tamaño de pantalla 
        # y le indicamos que grabe un video de todo lo que suceda.
        print("📱 Configurando contexto y grabación de video...")
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            record_video_dir="output_videos/" 
        )

        # 3. TRACING (Modo Dios para debugging)
        # Esto guarda un registro exacto del DOM, red y capturas de cada microsegundo.
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = context.new_page()

        # 4. INTERCEPCIÓN DE RED (Network Route)
        # Optimizamos el bot bloqueando la descarga de imágenes para ahorrar ancho de banda.
        print("🛡️ Interceptando red: Bloqueando imágenes...")
        page.route("**/*.{png,jpg,jpeg,svg}", lambda route: route.abort())

        # 5. NAVEGACIÓN
        print("🌐 Navegando a la app de prueba (TodoMVC)...")
        page.goto("https://demo.playwright.dev/todomvc/#/")

        # 6. INTERACCIÓN CON EL DOM (Auto-waiting)
        print("✍️ Interactuando con elementos...")
        
        # Buscamos el input por su atributo placeholder de forma semántica
        input_tarea = page.get_by_placeholder("What needs to be done?")
        
        # Playwright automáticamente espera a que el input sea visible e interactuable
        input_tarea.fill("Armar arquitectura en Podman")
        input_tarea.press("Enter")
        
        input_tarea.fill("Aprender intercepción de red en Playwright")
        input_tarea.press("Enter")

        # Localizamos el primer botón circular y lo clickeamos para completar la tarea
        page.locator(".toggle").first.click()

        # 7. CAPTURAS Y EXTRACCIÓN DE DATOS
        print("📸 Tomando captura de pantalla completa...")
        page.screenshot(path="captura_final.png", full_page=True)

        # Extraemos texto de la página evaluando JavaScript directamente en el navegador
        items_restantes = page.locator(".todo-count").inner_text()
        print(f"📊 Estado actual: {items_restantes}")

        # 8. FINALIZACIÓN Y EXPORTACIÓN DE TRACE
        print("💾 Guardando el reporte de trazabilidad...")
        context.tracing.stop(path="trace.zip")
        # Cerramos los procesos limpiamente
        context.close()
        browser.close()
        
        print("✅ Prueba finalizada con éxito.")

if __name__ == "__main__":
    probar_playwright()
