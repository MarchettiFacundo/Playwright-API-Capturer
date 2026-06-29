# Guía Completa de Automatización con Playwright (Python)

Esta guía explica en detalle cómo implementar, optimizar y depurar procesos de automatización robótica de procesos (RPA) utilizando **Playwright** en Python. También aborda la estrategia de **automatización híbrida (Playwright + Requests)**, diseñada para acelerar y robustecer los procesos de extracción y carga de datos en portales corporativos complejos como el de Claro (`https://rpa-site.claro.amx/`).

---

## 1. ¿Por Qué Playwright en Lugar de Selenium?

Playwright es una herramienta de automatización moderna que soluciona los problemas históricos de Selenium:

| Característica | Playwright | Selenium |
| :--- | :--- | :--- |
| **Protocolo de Comunicación** | Conexión WebSocket bidireccional directa (rápida y en tiempo real). | Protocolo HTTP WebDriver (lento y síncrono). |
| **Espera Automática (Auto-waiting)** | Espera a que los elementos estén listos (visibles, clickeables, estables) antes de actuar. | Requiere esperas manuales (`WebDriverWait`), propensas a fallar si hay lag en la red. |
| **Aislamiento de Navegación** | Concepto de **Contextos de Navegador** (múltiples sesiones aisladas en una sola instancia de navegador). | Requiere levantar una ventana de navegador completa por cada sesión de usuario. |
| **Interceptación de Red** | Soporte nativo para escuchar, bloquear y modificar peticiones/respuestas HTTP. | Requiere herramientas externas o proxies complejos como BrowserMob. |
| **Depuración (Debugging)** | Herramientas visuales incorporadas como **Playwright Inspector** y **Trace Viewer**. | Limitado a capturas de pantalla básicas y logs de consola. |

---

## 2. Instalación y Configuración en Entornos Corporativos

### 2.1 Instalación Básica
Para comenzar con Playwright en Python, instala la librería y sus binarios de navegación:

```bash
pip install playwright
playwright install chromium
```

### 2.2 Sorteando Certificados de Seguridad Inválidos (SSL)
En redes e intranets corporativas (como las de Claro), es común encontrarse con portales que utilizan certificados SSL autofirmados o inválidos. Esto provoca el error `net::ERR_CERT_AUTHORITY_INVALID`.

En Playwright, se soluciona configurando el **Contexto del Navegador** con la propiedad `ignore_https_errors=True`:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # 1. Lanzamos el navegador
    browser = p.chromium.launch(headless=False)
    
    # 2. Creamos un contexto configurando la evasión de errores SSL
    context = browser.new_context(ignore_https_errors=True)
    
    # 3. Abrimos la página desde este contexto seguro
    page = context.new_page()
    page.goto("https://rpa-site.claro.amx/")
```

---

## 3. Filosofía de Selectores Semánticos y Robustos

Uno de los principales motivos por los cuales los robots RPA fallan es el cambio en la estructura HTML de la página (cambios de IDs, clases CSS, etc.). Playwright introduce **Locators** que interactúan de forma semántica con el DOM:

### 3.1 Selectores Recomendados (Resistentes a Cambios Visuales)

*   **Por rol o elemento de UI (`get_by_role`)**: Busca elementos por su función de accesibilidad. Muy útil para botones, inputs y títulos.
    ```python
    page.get_by_role("button", name="Acceder").click()
    page.get_by_role("textbox", name="Usuario").fill("admin")
    ```
*   **Por marcador/placeholder (`get_by_placeholder`)**:
    ```python
    page.get_by_placeholder("Ingrese su contraseña").fill("Viernes.1219")
    ```
*   **Por etiqueta/label asociada (`get_by_label`)**:
    ```python
    page.get_by_label("Número de Teléfono").fill("1122334455")
    ```
*   **Por texto visible (`get_by_text`)**:
    ```python
    page.get_by_text("Error de autenticación").is_visible()
    ```

### 3.2 Selectores CSS/XPath (Último recurso)
Utiliza selectores CSS o XPath únicamente cuando los semánticos no sean viables. Playwright los resuelve de forma inteligente con el método `locator()`:

```python
# Selector CSS estándar
page.locator("div.login-container > button.btn-primary").click()

# XPath (se detecta automáticamente por el prefijo '//')
page.locator("//input[@name='sap-user']").fill("RPA_4947")
```

---

## 4. Estrategia Híbrida: Playwright + Requests

La interacción visual con el navegador web es lenta y consume recursos de memoria y procesador. Si el robot RPA debe realizar tareas masivas (como consultar 10,000 registros, descargar cientos de PDF o subir datos repetitivos), realizarlo a través de la interfaz de usuario no es eficiente.

### 4.1 Concepto del Flujo Híbrido
1.  **Fase 1 (Playwright - Interfaz Visual)**:
    *   Inicia el navegador.
    *   Sortea procesos complejos como inicios de sesión (Logins), Captchas manuales o autenticaciones multi-factor (MFA).
    *   Una vez iniciada la sesión, captura las **Cookies** de autenticación y **Tokens** de cabecera (`Authorization`, `Bearer`, etc.) que el servidor asignó al navegador.
    *   Cierra el navegador para liberar recursos del sistema.
2.  **Fase 2 (Requests - Tráfico de Red Directo)**:
    *   Crea una sesión de Python con `requests.Session()`.
    *   Inyecta las cookies y cabeceras capturadas.
    *   Realiza peticiones HTTP directas (`GET`, `POST`) a las APIs del portal para consultar y cargar datos en milisegundos.

```
┌─────────────────────────────────┐
│     FASE 1: Navegador Web       │
│  (Login + Autenticación Web)   │
└────────────────┬────────────────┘
                 │
      [Capturar Headers & Cookies]
                 │
                 ▼
┌─────────────────────────────────┐
│      FASE 2: Peticiones HTTP    │
│  (Requests directos a la API)   │
└─────────────────────────────────┘
```

---

---

## 6. Ejemplo Práctico: Navegación e Interceptación en Claro RPA Site

A continuación, se detalla un script estructurado que demuestra cómo iniciar sesión, saltarse errores de SSL, esperar a que el DOM sea interactivo y tomar capturas de pantalla para auditoría.

```python
# Archivo de ejemplo: ejemplo_portal_claro.py
from playwright.sync_api import sync_playwright
import time

def ejecutar_automatizacion_claro():
    URL = "https://rpa-site.claro.amx/"

    with sync_playwright() as p:
        print("🚀 Levantando navegador Chromium...")
        browser = p.chromium.launch(headless=False, slow_mo=300)
        
        # ignore_https_errors=True es CLAVE para la intranet de Claro
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            ignore_https_errors=True
        )
        
        page = context.new_page()

        try:
            print(f"🌐 Navegando a: {URL}")
            page.goto(URL, wait_until="networkidle") # Espera a que no haya más tráfico de red activo
            
            # Ejemplo de toma de captura de pantalla para auditoría
            page.screenshot(path="captura_inicio.png")
            print("📸 Captura de inicio guardada.")

            # Suponiendo que el portal tiene un formulario de login genérico:
            # page.get_by_placeholder("Usuario").fill("mi_usuario")
            # page.get_by_placeholder("Contraseña").fill("mi_clave")
            # page.get_by_role("button", name="Ingresar").click()
            
            # Esperamos que cargue la interfaz principal
            # page.wait_for_load_state("domcontentloaded")
            
            print("⏳ Esperando que el usuario realice actividades o para fines de demostración...")
            time.sleep(5)

        except Exception as e:
            print(f"❌ Ocurrió un error en el flujo: {e}")
            page.screenshot(path="captura_error.png")
            
        finally:
            print("💾 Guardando estado y cerrando navegador...")
            context.close()
            browser.close()

if __name__ == "__main__":
    ejecutar_automatizacion_claro()
```

### 6.1 Cómo Replicar Cookies en Requests (Híbrido)
Si requieres pasar las cookies directamente de Playwright a Requests dentro del mismo flujo de código sin cerrar el navegador, puedes hacerlo de la siguiente forma:

```python
# Pasar cookies de Playwright a un objeto Session de requests
import requests

# 1. Obtener cookies del contexto de Playwright
cookies_playwright = context.cookies()

# 2. Inicializar la sesión de requests
session = requests.Session()

# 3. Inyectar cookies en la sesión de requests
for cookie in cookies_playwright:
    session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'], path=cookie['path'])

# 4. Ahora puedes hacer requests autorizados directamente
response = session.get("https://rpa-site.claro.amx/api/datos-privados", verify=False)
print(response.json())
```
