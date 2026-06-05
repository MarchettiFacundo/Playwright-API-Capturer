# Guía de Distribución en Bitbucket: Playwright API Capturer Installer

Esta guía explica cómo distribuir el instalador profesional ejecutable (`Playwright_API_Capturer_Setup.exe`) utilizando la sección de descargas de **Bitbucket**, permitiendo que cualquier usuario final lo instale en su sistema sin necesidad de clonar el código fuente o tener instalado Python/Git.

---

## 1. Configuración Única en Bitbucket (Como Administrador del Repo)

Bitbucket posee una sección específica para alojar archivos binarios pesados (como instaladores ejecutable, imágenes de disco, etc.) denominada **Downloads**.

Si no ves la sección **Downloads** en el panel lateral izquierdo de tu repositorio, actívala siguiendo estos pasos:

1. Ve a tu repositorio en **Bitbucket Cloud**.
2. En el menú de la izquierda, haz clic en **Repository settings** (Configuración del repositorio).
3. En la sección **General**, busca **Features** (Características).
4. Asegúrate de activar la casilla de **Downloads** (Descargas).
5. Guarda los cambios. Ahora aparecerá la pestaña **Downloads** en el menú principal izquierdo.

---

## 2. Flujo del Desarrollador (Compilación y Publicación)

Cada vez que lances una nueva versión o actualización de la aplicación:

1. Ejecuta el script de compilación en tu máquina local:
   ```powershell
   python compilar_app.py
   ```
2. Este script realizará lo siguiente de forma totalmente automatizada:
   - Descargará e instalará **Inno Setup 6** silenciosamente si no lo tienes instalado.
   - Compilará la aplicación con **PyInstaller** en un único ejecutable.
   - Generará los recursos visuales e iconos correspondientes.
   - Creará el instalador nativo de Windows: `dist/Playwright_API_Capturer_Setup.exe`.
3. Ingresa a la sección **Downloads** de tu repositorio en Bitbucket.
4. Haz clic en **Upload files** (Subir archivos) y arrastra el archivo `dist/Playwright_API_Capturer_Setup.exe`.
5. *(Opcional)* Si deseas llevar un control de versiones, puedes renombrar el instalador antes de subirlo (ej. `Playwright_API_Capturer_Setup_v1.0.exe`) o subirlo con el mismo nombre reemplazando la versión anterior.

---

## 3. Flujo del Usuario Final (Instalación)

El usuario final no requiere instalar Python, Git, Playwright ni realizar configuraciones técnicas:

1. Ingresa a la página de tu repositorio en **Bitbucket**.
2. En el menú de la izquierda, haz clic en la sección **Downloads** (Descargas).
3. Verás una lista de archivos disponibles. Haz clic en `Playwright_API_Capturer_Setup.exe` para descargarlo.
4. Una vez descargado, haz doble clic en el instalador `.exe`.
5. Windows mostrará la advertencia de Control de Cuentas de Usuario (UAC) para solicitar permisos de Administrador, ya que la aplicación se instala en `C:\Program Files\Playwright API Capturer`. Haz clic en **Sí**.
6. Selecciona el idioma (Español o Inglés).
7. Sigue los pasos del asistente de instalación ("Siguiente > Siguiente > Instalar"). Opcionalmente, puedes marcar la casilla "Crear un acceso directo en el Escritorio".
8. ¡Listo! La aplicación se instalará correctamente. Al finalizar, puedes marcar la opción de ejecutarla inmediatamente o abrirla desde el acceso directo del Menú de Inicio o del Escritorio.

---

## 4. Desinstalación Limpia

Para desinstalar la aplicación de forma profesional, el usuario puede:
- Ir a **Configuración de Windows** -> **Aplicaciones** -> **Aplicaciones instaladas**.
- Buscar **Playwright API Capturer** y hacer clic en **Desinstalar**.
- Esto removerá de forma segura todos los ejecutables, iconos y carpetas del sistema, manteniendo el equipo limpio de residuos.
