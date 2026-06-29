# Checklist de Pruebas: Detección Antibot y Captura de Eventos

Este documento sirve para registrar los resultados de las pruebas de la aplicación **Playwright API Capturer & Generator** frente a diferentes sitios de prueba de bots, fingerprinting y automatización.

## Instrucciones de Prueba

1. **Modo Automático:** Deja desmarcada la opción *Conectar a navegador abierto (CDP)* en la GUI. Ingresa la URL y presiona **⚡ Iniciar Captura**.
2. **Modo Manual (CDP):**
   * Abre tu navegador habitual (Chrome o Edge) desde la consola/terminal usando los comandos de depuración remota:
     * **Chrome:** `chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\temp\perfil_cdp"`
     * **Edge:** `msedge.exe --remote-debugging-port=9222 --user-data-dir="C:\temp\perfil_cdp"`
   * Activa *Conectar a navegador abierto (CDP)* en la GUI, ingresa el puerto y presiona **⚡ Iniciar Captura**.
   * **Importante para el Grabador DOM en modo manual:** Si la página ya estaba abierta en la pestaña antes de iniciar la captura, presiona **F5 (recargar)** en la pestaña para que se inyecte el script de captura.

---

## Tabla de Control y Resultados

Marca con una `x` (ejemplo: `[x]`) las casillas de los controles que la aplicación supere exitosamente para cada sitio web.

| Sitio Web / URL | Propósito de la Prueba | APIs Red (Automático) | DOM (Automático) | APIs Red (Manual - CDP) | DOM (Manual - CDP) | Notas / Observaciones |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Sannysoft Bot Detector**<br>[bot.sannysoft.com](https://bot.sannysoft.com/) | Evaluar si se filtran firmas básicas de automatización (como `webdriver` o discrepancias de User Agent). | `[ ]` | `[ ]` | `[X]` | `[X]` | En modo manual (CDP) debería dar todo verde. En automático puede fallar `webdriver`. |
| **CreepJS**<br>[abrahamjuliot.github.io/creepjs](https://abrahamjuliot.github.io/creepjs/) | Analizar fingerprinting avanzado y confianza del navegador (Trust Score). | `[ ]` | `[ ]` | `[ ]` | `[ ]` | Evalúa la evasión y protección del navegador frente a fingerprints complejos. |
| **Scrapfly Bot Detection**<br>[tools.scrapfly.io/api/detect/bot](https://tools.scrapfly.io/api/detect/bot) | Verificar si detecta scripts de Playwright/Selenium directamente. | `[ ]` | `[ ]` | `[ ]` | `[ ]` | Detecta firmas y cabeceras específicas de automatización. |
| **Fingerprint Bot Detection**<br>[fingerprint.com/products/bot-detection](https://fingerprint.com/products/bot-detection/) | Prueba en vivo de detección de bots comercial. | `[ ]` | `[ ]` | `[ ]` | `[ ]` | Evalúa si el motor clasifica el acceso como "Humano" o "Bot". |
| **Nowsecure**<br>[nowsecure.nl](https://nowsecure.nl) | Superar el desafío / reto de acceso de Cloudflare. | `[ ]` | `[ ]` | `[ ]` | `[ ]` | En modo automático suele quedar atrapado en el reto. En modo manual (CDP) debería pasar al instante. |
| **Cloudflare Turnstile Demo**<br>[challenges.cloudflare.com](https://challenges.cloudflare.com/) | Interacción y resolución con el widget Turnstile oficial. | `[ ]` | `[ ]` | `[ ]` | `[ ]` | Probar si se puede interactuar con el botón o capturar peticiones detrás de él. |
| **Oxylabs Scraping Sandbox**<br>[sandbox.oxylabs.io](https://sandbox.oxylabs.io/) | Pruebas de extracción en entornos dinámicos estructurados. | `[ ]` | `[ ]` | `[ ]` | `[ ]` | Ideal para probar el **Grabador DOM** y exportar scripts limpios. |
| **ScrapeMe Shop**<br>[scrapeme.live/shop](https://scrapeme.live/shop/) | Captura de datos en eCommerce ficticio. | `[ ]` | `[ ]` | `[ ]` | `[ ]` | Excelente para mapear APIs de catálogo o probar clics en paginación. |

---

## Leyenda de Resultados
* **[ ]** No probado / Pendiente.
* **[x]** Funciona correctamente (captura APIs o clics del DOM según corresponda).
* **[-]** No aplica / Bloqueado por el sitio web de forma inevitable.
