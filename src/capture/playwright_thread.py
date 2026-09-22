import os
import json
import threading
import queue
from playwright.async_api import async_playwright
from src.capture.js_templates import JS_SCRIPT

class PlaywrightCaptureThread(threading.Thread):
    def __init__(self, url, output_queue, video_dir="output_videos", trace_file="trace.zip", log_file="debug_playwright.log", 
                 modo="APIs de Red (HTTP)", navegador="Chromium", viewport_width=1280, viewport_height=720, ignore_ssl_errors=True,
                 headless=False, record_video=True, record_trace=True, timeout=30, user_agent="", usar_cdp=False, puerto_cdp=9222,
                 storage_state=None, http_user="", http_password=""):
        super().__init__()
        self.url = url
        self.output_queue = output_queue
        self.video_dir = video_dir
        self.trace_file = trace_file
        self.log_file = log_file
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.ignore_ssl_errors = ignore_ssl_errors
        self.modo = modo
        self.navegador = navegador
        self.headless = headless
        self.record_video = record_video
        self.record_trace = record_trace
        self.timeout = timeout
        self.user_agent = user_agent
        self.usar_cdp = usar_cdp
        self.puerto_cdp = puerto_cdp
        self.storage_state = storage_state
        self.http_user = http_user
        self.http_password = http_password
        self.browser = None
        self.context = None
        self.playwright = None
        self.stop_event = threading.Event()
        self.paused = False
        
        self.input_queue = queue.Queue()

    def run(self):
        import asyncio
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
            
        asyncio.run(self.capturar_async())

    async def capturar_async(self):
        import asyncio
        try:
            os.makedirs(self.video_dir, exist_ok=True)
            
            self.playwright = await async_playwright().start()
            
            if self.usar_cdp:
                self.output_queue.put(("status", f"Conectando a navegador en puerto {self.puerto_cdp}..."))
                self.browser = await self.playwright.chromium.connect_over_cdp(f"http://localhost:{self.puerto_cdp}")
                if self.browser.contexts:
                    self.context = self.browser.contexts[0]
                else:
                    context_args = {
                        "ignore_https_errors": self.ignore_ssl_errors,
                        "viewport": {"width": self.viewport_width, "height": self.viewport_height}
                    }
                    if self.record_video:
                        context_args["record_video_dir"] = self.video_dir
                        context_args["record_video_size"] = {"width": self.viewport_width, "height": self.viewport_height}
                    if self.user_agent and self.user_agent.strip():
                        context_args["user_agent"] = self.user_agent.strip()
                    if self.storage_state and os.path.exists(self.storage_state):
                        context_args["storage_state"] = self.storage_state
                    if self.http_user and self.http_password:
                        context_args["http_credentials"] = {
                            "username": self.http_user.strip(),
                            "password": self.http_password.strip()
                        }
                    self.context = await self.browser.new_context(**context_args)
            else:
                self.output_queue.put(("status", "Iniciando Playwright..."))
                if self.navegador == "Firefox":
                    self.browser = await self.playwright.firefox.launch(headless=self.headless)
                elif self.navegador == "WebKit":
                    self.browser = await self.playwright.webkit.launch(headless=self.headless)
                elif self.navegador == "Edge":
                    self.browser = await self.playwright.chromium.launch(channel="msedge", headless=self.headless)
                else:
                    self.browser = await self.playwright.chromium.launch(headless=self.headless)
                
                context_args = {
                    "ignore_https_errors": self.ignore_ssl_errors,
                    "viewport": {"width": self.viewport_width, "height": self.viewport_height}
                }
                if self.record_video:
                    context_args["record_video_dir"] = self.video_dir
                    context_args["record_video_size"] = {"width": self.viewport_width, "height": self.viewport_height}
                if self.user_agent and self.user_agent.strip():
                    context_args["user_agent"] = self.user_agent.strip()
                if self.storage_state and os.path.exists(self.storage_state):
                    context_args["storage_state"] = self.storage_state
                if self.http_user and self.http_password:
                    context_args["http_credentials"] = {
                        "username": self.http_user.strip(),
                        "password": self.http_password.strip()
                    }
                    
                self.context = await self.browser.new_context(**context_args)
            
            if self.timeout > 0:
                self.context.set_default_timeout(self.timeout * 1000)
            
            if self.record_trace:
                await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)

            if self.modo == "APIs de Red (HTTP)":
                async def interceptar_respuesta(response):
                    if self.paused:
                        return
                    es_api = response.request.resource_type in ["fetch", "xhr"]
                    es_doc_post = response.request.resource_type == "document" and response.request.method == "POST"
                    if es_api or es_doc_post:
                        request = response.request
                        if request.method == "OPTIONS":
                            return
                        try:
                            post_data = request.post_data
                            
                            datos = {
                                "url": response.url,
                                "metodo": request.method,
                                "status": response.status,
                                "headers_peticion": dict(request.headers),
                                "headers_respuesta": dict(response.headers),
                                "payload_enviado": post_data,
                                "respuesta": None,
                                "seleccionado": True
                            }
                            
                            if response.ok:
                                try:
                                    content_type = (await response.header_value("content-type") or "").lower()
                                    if "event-stream" in content_type:
                                        datos["respuesta"] = "<Streaming Event Stream>"
                                    elif response.status == 204:
                                        datos["respuesta"] = "<Sin Contenido (204 No Content)>"
                                    else:
                                        try:
                                            datos["respuesta"] = await response.json()
                                        except Exception:
                                            try:
                                                datos["respuesta"] = await response.text()
                                            except Exception as text_e:
                                                datos["respuesta"] = f"<No se pudo leer cuerpo: {str(text_e)}>"
                                except Exception as body_e:
                                    datos["respuesta"] = f"<Error leyendo cuerpo: {str(body_e)}>"
                            else:
                                try:
                                    datos["respuesta"] = await response.text()
                                except Exception:
                                    datos["respuesta"] = f"<Respuesta con error status {response.status}>"

                            try:
                                with open(self.log_file, "a", encoding="utf-8") as f:
                                    f.write(f"Callback interceptar_respuesta: {datos.get('metodo')} {datos.get('url')[:60]}\n")
                            except Exception:
                                pass
                            self.output_queue.put(("peticion", datos))
                            
                        except Exception as e:
                            print(f"[WARN] Error en interceptar_respuesta: {e}")

                self.context.on("response", interceptar_respuesta)
            else:
                async def registrar_accion(source, datos_json):
                    if self.paused:
                        return
                    try:
                        datos = json.loads(datos_json)
                        datos["seleccionado"] = True
                        
                        ruta_iframes = []
                        try:
                            curr_frame = source.get("frame") if isinstance(source, dict) else getattr(source, "frame", None)
                            page_obj = source.get("page") if isinstance(source, dict) else getattr(source, "page", None)
                            main_frame = page_obj.main_frame if page_obj else None
                            
                            with open(self.log_file, "a", encoding="utf-8") as debug_file:
                                debug_file.write(f"[DEBUG_FRAME] source.frame: name={curr_frame.name if curr_frame else None!r}, url={curr_frame.url[:120] if curr_frame else None!r}\n")
                                debug_file.write(f"[DEBUG_FRAME] main_frame: name={main_frame.name if main_frame else None!r}, url={main_frame.url[:120] if main_frame else None!r}\n")
                                debug_file.write(f"[DEBUG_FRAME] es_main_frame: {curr_frame == main_frame}\n")
                            
                            while curr_frame and curr_frame != main_frame:
                                iframe_handle = await curr_frame.frame_element()
                                if iframe_handle:
                                    iframe_id = await iframe_handle.get_attribute("id")
                                    iframe_name = await iframe_handle.get_attribute("name")
                                    iframe_src = await iframe_handle.get_attribute("src")
                                    
                                    with open(self.log_file, "a", encoding="utf-8") as debug_file:
                                        debug_file.write(f"[DEBUG_FRAME] Encontrado iframe: id={iframe_id!r}, name={iframe_name!r}, src={iframe_src[:120]!r}\n")
                                    
                                    if iframe_id and not "-" in iframe_id and not iframe_id[0].isdigit() and not "itsframe" in iframe_id.lower():
                                        selector = f"#{iframe_id}"
                                    elif iframe_name:
                                        if "itsframe" in iframe_name.lower():
                                            selector = "iframe[name*='itsframe' i]"
                                        else:
                                            selector = f"[name='{iframe_name}']"
                                    elif iframe_src:
                                        base_src = iframe_src.split("?")[0]
                                        selector = f"iframe[src*='{base_src}']"
                                    else:
                                        selector = "iframe"
                                    ruta_iframes.insert(0, selector)
                                curr_frame = curr_frame.parent_frame
                        except Exception as frame_err:
                            import traceback
                            with open(self.log_file, "a", encoding="utf-8") as debug_file:
                                debug_file.write(f"[WARN] Error resolviendo ruta de iframes: {frame_err}\n")
                                debug_file.write(traceback.format_exc() + "\n")
                            
                        datos["ruta_iframes"] = ruta_iframes
                        
                        if ruta_iframes:
                            ruta_visual = " -> ".join(ruta_iframes)
                            datos["descriptor_legible"] = f"[{ruta_visual}] {datos['descriptor_legible']}"
                            
                        try:
                            with open(self.log_file, "a", encoding="utf-8") as f:
                                f.write(f"Callback registrar_accion: {datos.get('tipo_accion')} {datos.get('descriptor_legible')}\n")
                        except Exception:
                            pass

                        self.output_queue.put(("accion_dom", datos))
                    except Exception as err:
                        print(f"[WARN] Error parseando JSON de acción DOM: {err}")

                await self.context.expose_binding("registrarAccionDOM", registrar_accion)
                await self.context.add_init_script(JS_SCRIPT)

            if self.usar_cdp:
                if not self.url or not self.url.strip():
                    if self.context.pages:
                        page = self.context.pages[0]
                    else:
                        page = await self.context.new_page()
                else:
                    page = await self.context.new_page()
            else:
                page = await self.context.new_page()
            
            def al_cerrar_pagina():
                if self.context and len(self.context.pages) <= 1:
                    self.output_queue.put(("status", "Página de navegación cerrada por el usuario."))
                    self.stop()
                
            page.on("close", lambda p: al_cerrar_pagina())

            if self.modo == "Grabador DOM (Acciones)":
                def al_detectar_descarga(download):
                    try:
                        nombre = download.suggested_filename
                        self.output_queue.put(("status", f"Descarga iniciada: {nombre}"))
                    except Exception:
                        pass

                page.on("download", al_detectar_descarga)

                async def inyectar_en_frame(frame):
                    try:
                        await frame.evaluate(JS_SCRIPT)
                    except Exception:
                        pass

                page.on("framenavigated", lambda f: asyncio.create_task(inyectar_en_frame(f)))

                async def al_abrir_pagina(nueva_p):
                    try:
                        nueva_p.on("close", lambda p: al_cerrar_pagina())
                        nueva_p.on("download", al_detectar_descarga)
                        nueva_p.on("framenavigated", lambda f: asyncio.create_task(inyectar_en_frame(f)))
                        try:
                            await nueva_p.evaluate(JS_SCRIPT)
                        except Exception:
                            pass
                    except Exception:
                        pass

                self.context.on("page", lambda p: asyncio.create_task(al_abrir_pagina(p)))

            
            if self.url and self.url.strip():
                self.output_queue.put(("status", f"Navegando a {self.url}..."))
                
                if self.modo == "Grabador DOM (Acciones)":
                    nav_data = {
                        "tipo_accion": "navigation",
                        "tagName": "WINDOW",
                        "descriptor_legible": "Navegación Inicial",
                        "selector_sugerido": "",
                        "valor": self.url,
                        "id": "", "name": "", "className": "",
                        "type": "", "placeholder": "",
                        "xpath": "", "outerHTML": "",
                        "seleccionado": True, "ruta_iframes": []
                    }
                    self.output_queue.put(("accion_dom", nav_data))

                try:
                    await page.goto(self.url, wait_until="domcontentloaded", timeout=20000)
                except Exception as err:
                    self.output_queue.put(("status", f"Advertencia navegación: {err}"))
                    print(f"[WARN] Error al ir a la página inicial: {err}")
            else:
                self.output_queue.put(("status", "Conectado al navegador. Listo para capturar peticiones..."))

            self.output_queue.put(("status", "Captura activa. Interactúe en el navegador..."))
            
            while not self.stop_event.is_set():
                if not self.browser.is_connected():
                    break
                
                try:
                    cmd_tipo, cmd_dato = self.input_queue.get_nowait()
                    if cmd_tipo == "highlight" and self.context:
                        for pg in self.context.pages:
                            try:
                                js_hl = """
                                (selector => {
                                    let el = document.querySelector(selector);
                                    if (!el) {
                                        if (selector.startsWith('xpath=')) {
                                            let xpath = selector.substring(6);
                                            let res = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                                            el = res.singleNodeValue;
                                        } else if (selector.startsWith('text=')) {
                                            let txt = selector.substring(5).replace(/^["']|["']$/g, '');
                                            el = Array.from(document.querySelectorAll('*')).find(e => e.textContent.trim() === txt);
                                        } else if (selector.startsWith('id=')) {
                                            el = document.getElementById(selector.substring(3));
                                        } else if (selector.startsWith('placeholder=')) {
                                            let plc = selector.substring(12).replace(/^["']|["']$/g, '');
                                            el = document.querySelector(`[placeholder="${plc}"]`);
                                        } else if (selector.startsWith('label=')) {
                                            let lbl = selector.substring(6).replace(/^["']|["']$/g, '');
                                            let labelEl = Array.from(document.querySelectorAll('label')).find(e => e.textContent.trim() === lbl);
                                            if (labelEl) {
                                                if (labelEl.htmlFor) el = document.getElementById(labelEl.htmlFor);
                                                else el = labelEl.querySelector('input, select, textarea');
                                            }
                                        }
                                    }
                                    if (el) {
                                        let origStyle = el.style.outline;
                                        let origTransition = el.style.transition;
                                        el.style.transition = "outline 0.15s ease-in-out";
                                        el.style.outline = "4px solid #ef4444";
                                        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                        setTimeout(() => {
                                            el.style.outline = origStyle;
                                            el.style.transition = origTransition;
                                        }, 2000);
                                    }
                                })
                                """
                                await pg.evaluate(js_hl, cmd_dato)
                            except Exception as err:
                                print(f"[WARN] Error resaltando: {err}")
                    elif cmd_tipo == "pause":
                        self.paused = cmd_dato
                    elif cmd_tipo == "abrir_inspector":
                        if self.context and self.context.pages:
                            for pg in self.context.pages:
                                try:
                                    self.output_queue.put(("status", "Inspector de Playwright abierto. Reanude en la barra del Inspector para continuar."))
                                    await pg.pause()
                                    self.output_queue.put(("status", "Inspector reanudado. Captura activa."))
                                    break
                                except Exception as insp_err:
                                    print(f"[WARN] Error al pausar para inspector: {insp_err}")
                except queue.Empty:
                    pass
                
                await asyncio.sleep(0.1)

        except Exception as e:
            self.output_queue.put(("error", f"Error en captura: {e}"))
            print(f"[ERROR] Error en hilo Playwright: {e}")
        finally:
            await self.cerrar_todo_async()

    def stop(self):
        self.stop_event.set()

    async def cerrar_todo_async(self):
        self.output_queue.put(("status", "Guardando traza y cerrando navegador..."))
        try:
            if self.context and self.record_trace:
                await self.context.tracing.stop(path=self.trace_file)
        except Exception as e:
            print(f"[WARN] Error guardando traza: {e}")

        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            print(f"[WARN] Error cerrando Playwright: {e}")

        self.output_queue.put(("status", "Captura detenida. Recursos liberados."))
        self.output_queue.put(("finalizado", None))
