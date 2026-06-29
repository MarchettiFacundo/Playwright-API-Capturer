# 📘 Manual de Usuario - Playwright API Capturer & Generator

Bienvenido al manual oficial de **Playwright API Capturer & Generator**, una suite profesional para la inspección de red, grabación de interacciones DOM, scraping web dinámico y generación automática de código en Python.

---

## 1. Introducción y Pantalla Inicial

Al ejecutar la aplicación, se presenta la interfaz principal dividida en dos paneles principales: el **Panel Izquierdo de Control y Tabla de Eventos**, y el **Panel Derecho de Inspección y Configuración**.

![Pantalla Inicial](<imagenes_flujo/Captura de pantalla 2026-06-29 151601.png>)


---

## 2. Configuración de Navegación y Modos

### 2.1. Selector de Modos de Captura
La aplicación cuenta con tres modos de trabajo especializados según el objetivo de automatización RPA:

![Selector de Modos](<imagenes_flujo/Captura de pantalla 2026-06-29 151831.png>)

- **APIs de Red (HTTP)**: Captura peticiones asíncronas Fetch/XHR en segundo plano para replicar servicios REST/SOAP con la librería `requests`.
- **Grabador DOM (Acciones)**: Graba clics, escrituras, selecciones y navegaciones sobre el navegador para generar automatizaciones de interfaz con `Playwright`.
- **Scraper Visual (DOM)**: Permite definir flujos de extracción masiva de datos estructurados con soporte de paginación automática y dual-engine (`Playwright` o `BeautifulSoup4`).

### 2.2. Selección de Navegadores e Ingreso de URL
Permite elegir entre múltiples motores de renderizado (**Chromium**, **Firefox**, **WebKit** o **Microsoft Edge**). 

![Selección de Navegador y URL](<imagenes_flujo/Captura de pantalla 2026-06-29 151927.png>)

> [!TIP]
> Si el driver del navegador seleccionado no se encuentra en el equipo, la aplicación lo detectará automáticamente y ofrecerá instalarlo de forma guiada con un solo clic.

### 2.3. Panel de Configuración Avanzada
Accediendo desde el botón **⚙️ Configuración**, es posible ajustar parámetros globales de ejecución del navegador:

![Panel de Configuración Avanzada](<imagenes_flujo/Captura de pantalla 2026-06-29 151939.png>)

- **Viewport**: Dimensiones de resolución de pantalla (ancho y alto).
- **Modo Headless**: Ejecución en segundo plano sin ventana gráfica visible.
- **Opciones SSL y Timeout**: Ignorar certificados inválidos y definir tiempo máximo de espera por acción.
- **Rutas de Almacenamiento**: Personalización de la carpeta de destino para logs, videos y trazas.

### 2.4. Conexión a Navegador Abierto (CDP) / Evasión Antibot
Para sitios web complejos con sistemas de protección antibot (Cloudflare, Akamai, Imperva) que bloquean automatizaciones estándar, la aplicación permite conectarse a una instancia de Chrome o Edge ya iniciada mediante el protocolo CDP (Chrome DevTools Protocol).

![Conexión CDP](<imagenes_flujo/Captura de pantalla 2026-06-29 151950.png>)

> [!IMPORTANT]
> Al presionar **🚀 Auto-Lanzar**, la herramienta desplegará una ventana limpia del navegador en el puerto seleccionado (por defecto `9222`), permitiendo iniciar sesión manualmente y evadir cualquier verificación de captcha o bot.

---

## 3. Modo 1: APIs de Red (HTTP)

### 3.1. Captura de Tráfico Fetch / XHR
En este modo, al interactuar con el sitio web objetivo, el panel izquierdo listará en tiempo real todas las peticiones de red capturadas con su método HTTP (`GET`, `POST`, `PUT`, `DELETE`), código de status y URL.

![Lista de Peticiones HTTP](<imagenes_flujo/Captura de pantalla 2026-06-29 152030.png>)

### 3.2. Inspección Detallada de Red
Al seleccionar cualquier petición de la lista, el panel derecho permite auditar todos los componentes de la transacción:

| Pestaña | Descripción | Captura de Pantalla |
| :--- | :--- | :--- |
| **Headers** | Muestra los encabezados de la petición (General, Request y Response Headers). | ![Pestaña Headers](<imagenes_flujo/Captura de pantalla 2026-06-29 152040.png>) |
| **Payload** | Inspecciona los datos enviados en el cuerpo del request (JSON o Form Data). | ![Pestaña Payload](<imagenes_flujo/Captura de pantalla 2026-06-29 152054.png>) |
| **Respuesta** | Visualiza el cuerpo de la respuesta en formato texto o JSON formateado. | ![Pestaña Respuesta](<imagenes_flujo/Captura de pantalla 2026-06-29 152101.png>) |
| **Árbol JSON** | Representación gráfica interactiva y jerárquica para explorar objetos y arrays complejos. | ![Árbol JSON](<imagenes_flujo/Captura de pantalla 2026-06-29 152111.png>) |

---

## 4. Modo 2: Grabador DOM (Acciones UI)

### 4.1. Grabación de Interacciones y Extracción de Contenido
Al activar este modo, el motor inyecta controladores inteligentes en el navegador que registran automáticamente clics en botones, escrituras en campos de texto, selecciones en listas desplegables y navegaciones.

> [!TIP]
> **¿Cómo extraer el contenido o texto de un elemento en el Grabador DOM?**
> Para registrar una acción de **Extracción de Texto / Contenido** (obtención del texto visible `inner_text()` en lugar de un clic de navegación), utiliza cualquiera de las siguientes combinaciones de teclas mientras haces clic sobre el elemento en el navegador:
> - **Ctrl + Clic**
> - **Shift + Clic**
> - **Alt + Clic**
>
> Al realizar esta acción, el elemento se grabará con el tipo **Extraer Texto 🔍**, capturando su contenido e información de selectores sin activar la interacción por defecto del elemento web.

![Lista de Acciones DOM](<imagenes_flujo/Captura de pantalla 2026-06-29 152203.png>)

### 4.2. Inspección de Elementos e Inteligencia de Selectores
Al hacer clic en cualquier acción grabada, el panel derecho revela información sobre el elemento HTML capturado:

- **Atributos**: ID, Name, Class Name, Tag Name y Placeholder.
- **Selectores**: Muestra el selector semántico óptimo generado para Playwright (`get_by_role`, `get_by_label`, `get_by_placeholder`) y alternativas CSS/XPath.
- **HTML Externo**: Fragmento de código fuente del elemento inspeccionado.

![Atributos del Elemento](<imagenes_flujo/Captura de pantalla 2026-06-29 152227.png>)
![Selectores y Locators](<imagenes_flujo/Captura de pantalla 2026-06-29 152231.png>)
![HTML Externo](<imagenes_flujo/Captura de pantalla 2026-06-29 152235.png>)

---

## 5. Modo 3: Scraper Visual (DOM & BS4) aun en DESARROLLO

### 5.1. Flujo Dual-Fase (Setup vs. Extracción)
El modo Scraper organiza las acciones en dos fases claramente diferenciadas:
1. **🔧 Setup (Login y Navegación)**: Clics y escrituras necesarios para llegar a la sección privada o catálogo deseado.
2. **📤 Extraer (Campos de Datos)**: Marcados mediante la combinación de teclado **Ctrl + Clic**, **Shift + Clic** o **Alt + Clic** en el navegador sobre los elementos cuyo contenido se desea extraer.

![Pasos del Scraper](<imagenes_flujo/Captura de pantalla 2026-06-29 152448.png>)

### 5.2. Inspección y Configuración del Scraper
En la sección derecha se pueden auditar los atributos y selectores de los campos a extraer, así como configurar los parámetros de extracción masiva:

![Atributos del Campo](<imagenes_flujo/Captura de pantalla 2026-06-29 152515.png>)
![Selectores del Campo](<imagenes_flujo/Captura de pantalla 2026-06-29 152519.png>)
![HTML del Campo](<imagenes_flujo/Captura de pantalla 2026-06-29 152522.png>)

En la pestaña **⚙️ Config Scraper**, es posible definir:
- **Paginación Automática**: Selector del botón "Siguiente página" y límite de páginas.
- **Motor de Extracción**: Elección entre `Playwright` (sitios dinámicos JS) o `requests + BeautifulSoup4` (sitios estáticos ultra-rápidos).
- **Formatos de Salida**: Exportación automática a CSV y JSON.

![Configuración del Scraper](<imagenes_flujo/Captura de pantalla 2026-06-29 152528.png>)

### 5.3. Pestaña Red POST y Autocompletado BS4
Para scrapers basados en `BeautifulSoup4` que requieren autenticación previa vía HTTP POST, la pestaña **🌐 Red POST** intercepta las peticiones de login de red y permite autocompletar automáticamente la configuración de inicio de sesión con un solo clic.

![Red POST y Autocompletado](<imagenes_flujo/Captura de pantalla 2026-06-29 152533.png>)

---

## 6. Gestión, Edición y Generación de Código

### 6.1. Menú Contextual y Editor de Pasos
En cualquiera de los tres modos, el usuario tiene control total sobre la lista de elementos:
- **Filtro mediante Casilla (☑/☐)**: Permite incluir o excluir elementos de la generación final.
- **Menú Contextual (Clic Derecho)**: Opciones para subir/bajar la secuencia de pasos, eliminar o editar datos.
- **Editor de Pasos**: Modal interactivo para modificar manualmente URLs, selectores, xpaths o credenciales.

![Selección de Pasos](<imagenes_flujo/Captura de pantalla 2026-06-29 152256.png>)
![Editor Modal de Pasos](<imagenes_flujo/Captura de pantalla 2026-06-29 152309.png>)

### 6.2. Generación y Exportación de Código
Al presionar el botón principal de generación en la parte inferior, la herramienta compila un script Python limpio, mantenible y listo para producción:

- **Modo APIs**: Genera un script secuencial con sesión persistente y vinculación dinámica automática de tokens de autenticación.
- **Modo DOM**: Despliega un menú emergente para exportar el script ejecutable `.py`, la lista estructurada `.json` o el reporte completo de selectores `.txt`.
- **Modo Scraper**: Exporta un script automatizado completo con soporte de exportación a CSV/JSON.

![Exportación DOM](<imagenes_flujo/Captura de pantalla 2026-06-29 152320.png>)

---

## 7. Diagnóstico y Herramientas Multimedia

### 7.1. Reproducción de Video y Visor de Trazas (Trace Viewer)
En la esquina superior derecha del panel de inspección, se incluyen herramientas avanzadas para auditoría de ejecuciones RPA:

![Herramientas Multimedia](<imagenes_flujo/Captura de pantalla 2026-06-29 152635.png>)

- **🎬 Reproducir Video**: Abre el reproductor del sistema con la grabación WebM de la sesión interactiva realizada.
- **🔍 Ver Trace de Playwright**: Ejecuta de forma nativa la herramienta **Playwright Trace Viewer** para inspeccionar paso a paso cada evento de red, renderizado de DOM y captura de pantalla en la línea de tiempo.

> [!TIP]
> Al presionar "Ver Trace de Playwright", se abrirá automáticamente la carpeta contenedora con el archivo `trace.zip` para arrastrarlo y soltarlo fácilmente sobre la ventana del visor.
