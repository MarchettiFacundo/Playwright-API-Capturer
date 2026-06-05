import os
import sys
import subprocess

# Asegurar que el directorio de trabajo sea el de este script para resolver correctamente las rutas relativas
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

def instalar_dependencias():
    print("[1/4] Verificando e instalando dependencias (Pillow, pyinstaller, pywin32)...")
    try:
        # Intentamos instalar silenciosamente usando pip
        subprocess.run([sys.executable, "-m", "pip", "install", "Pillow", "pyinstaller", "pywin32"], check=True)
        print("[OK] Dependencias instaladas con éxito.")
    except Exception as e:
        print(f"[ERROR] No se pudieron instalar las dependencias: {e}")
        sys.exit(1)

def generar_icono_personalizado(ruta_salida=os.path.join("assets", "app_icon.ico")):
    print("[2/4] Generando icono de Red API personalizado para la aplicación...")
    try:
        # Aseguramos que el directorio de salida (assets) exista
        dir_salida = os.path.dirname(ruta_salida)
        if dir_salida:
            os.makedirs(dir_salida, exist_ok=True)

        from PIL import Image, ImageDraw
        
        # Crear un lienzo cuadrado RGBA de 256x256
        size = (256, 256)
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Dibujar fondo circular Indigo oscuro
        draw.ellipse([10, 10, 246, 246], fill=(30, 27, 75, 255)) # Indigo oscuro (#1e1b4b)
        
        # Borde circular cian brillante
        draw.ellipse([8, 8, 248, 248], outline=(6, 182, 212, 255), width=5) # Cyan (#06b6d4)
        
        # Coordenadas de los 3 nodos de la red
        nodo_sup = (128, 70)
        nodo_izq = (75, 175)
        nodo_der = (181, 175)
        
        # Dibujar líneas de conexión en blanco
        draw.line([nodo_sup, nodo_izq], fill=(248, 250, 252, 255), width=6)
        draw.line([nodo_sup, nodo_der], fill=(248, 250, 252, 255), width=6)
        draw.line([nodo_izq, nodo_der], fill=(248, 250, 252, 255), width=6)
        
        # Dibujar los nodos circulares con relleno cian y borde blanco
        r = 20 # radio de los nodos
        for cx, cy in [nodo_sup, nodo_izq, nodo_der]:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(6, 182, 212, 255), outline=(248, 250, 252, 255), width=3)
            
        # Guardar en formato ICO con todos los tamaños estándar para Windows
        image.save(ruta_salida, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        print(f"[OK] Nuevo icono de Red API generado con éxito en: {ruta_salida}")
    except Exception as e:
        print(f"[ERROR] Error al generar el icono: {e}")
        sys.exit(1)

def generar_splash_personalizado(ruta_salida=os.path.join("assets", "splash.png")):
    print("[2.5/4] Generando pantalla de carga (Splash) personalizada...")
    try:
        dir_salida = os.path.dirname(ruta_salida)
        if dir_salida:
            os.makedirs(dir_salida, exist_ok=True)

        from PIL import Image, ImageDraw, ImageFont
        
        # Canvas de 550x350, fondo color azul oscuro
        image = Image.new("RGBA", (550, 350), (15, 23, 42, 255)) # #0f172a
        draw = ImageDraw.Draw(image)
        
        # Borde cian brillante
        draw.rectangle([0, 0, 549, 349], outline=(6, 182, 212, 255), width=4)
        
        # Cargar fuentes estándar de Windows de forma segura
        try:
            font_title = ImageFont.truetype("arial.ttf", 26)
            font_subtitle = ImageFont.truetype("arial.ttf", 14)
            font_loading = ImageFont.truetype("arial.ttf", 11)
        except Exception:
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()
            font_loading = ImageFont.load_default()

        # Logotipo de red cian en la parte superior central
        cx, cy = 275, 95
        n_sup = (cx, cy - 45)
        n_izq = (cx - 45, cy + 30)
        n_der = (cx + 45, cy + 30)
        
        # Líneas de conexión
        draw.line([n_sup, n_izq], fill=(248, 250, 252, 255), width=4)
        draw.line([n_sup, n_der], fill=(248, 250, 252, 255), width=4)
        draw.line([n_izq, n_der], fill=(248, 250, 252, 255), width=4)
        
        # Círculos
        r = 15
        for x, y in [n_sup, n_izq, n_der]:
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(6, 182, 212, 255), outline=(248, 250, 252, 255), width=2)
            
        # Textos informativos
        draw.text((275, 195), "PLAYWRIGHT API CAPTURER", fill=(248, 250, 252, 255), font=font_title, anchor="ms")
        draw.text((275, 225), "RPA Automation & API Interceptor", fill=(99, 102, 241, 255), font=font_subtitle, anchor="ms")
        
        # Barra de carga de simulación
        draw.rectangle([50, 270, 500, 276], fill=(30, 41, 59, 255)) # Fondo
        draw.rectangle([50, 270, 380, 276], fill=(6, 182, 212, 255)) # Relleno (65%)
        
        # Mensaje de inicialización
        draw.text((275, 305), "Inicializando entorno y módulos Python...", fill=(148, 163, 184, 255), font=font_loading, anchor="ms")
        
        image.save(ruta_salida, format="PNG")
        print(f"[OK] Pantalla de carga (Splash) generada con éxito en: {ruta_salida}")
    except Exception as e:
        print(f"[ERROR] Error al generar la pantalla de carga (Splash): {e}")
        sys.exit(1)

def compilar_ejecutable():
    print("[3/4] Compilando la aplicación con PyInstaller (esto puede tardar de 1 a 2 minutos)...")
    try:
        cmd = [
            "pyinstaller",
            "--clean",
            "--onefile",
            "--noconsole",
            "--collect-all", "playwright",
            f"--icon={os.path.join('assets', 'app_icon.ico')}",
            f"--splash={os.path.join('assets', 'splash.png')}",
            "--name=Playwright API Capturer",
            os.path.join("src", "captura_gui.py")
        ]
        # Ejecutar pyinstaller
        subprocess.run(cmd, check=True)
        print("[OK] Compilación finalizada con éxito. Ejecutable generado en la carpeta 'dist/'.")
    except Exception as e:
        print(f"[ERROR] Error al compilar con PyInstaller: {e}")
        sys.exit(1)

def crear_acceso_directo(nombre_exe="Playwright API Capturer.exe"):
    print("[4/4] Creando acceso directo en el Escritorio...")
    try:
        from win32com.client import Dispatch
        
        # Obtener ruta absoluta del ejecutable
        ruta_exe = os.path.abspath(os.path.join("dist", nombre_exe))
        if not os.path.exists(ruta_exe):
            print(f"[ERROR] No se encontró el ejecutable en: {ruta_exe}")
            return
            
        ruta_icono = os.path.abspath(os.path.join("assets", "app_icon.ico"))
        
        # Obtener ruta del Escritorio de Windows
        escritorio = os.path.join(os.environ["USERPROFILE"], "Desktop")
        ruta_lnk = os.path.join(escritorio, "Playwright API Capturer.lnk")
        
        # Crear acceso directo
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(ruta_lnk)
        shortcut.Targetpath = ruta_exe
        # Forzamos a que el directorio de trabajo sea la raíz del proyecto
        shortcut.WorkingDirectory = os.path.abspath(".")
        shortcut.Description = "Herramienta de Captura de APIs de Playwright"
        if os.path.exists(ruta_icono):
            shortcut.IconLocation = f"{ruta_icono},0"
        shortcut.save()
        
        print(f"[OK] Acceso directo creado en el Escritorio:")
        print(f"     => {ruta_lnk}")
    except Exception as e:
        print(f"[ERROR] Error al crear el acceso directo en el Escritorio: {e}")

def instalar_inno_setup_automaticamente():
    print("\nInno Setup 6 no fue detectado en el sistema.")
    print("El instalador profesional requiere Inno Setup para compilar el archivo .iss.")
    
    # Comprobar si estamos ejecutando en un entorno interactivo
    es_interactivo = sys.stdin.isatty()
    if es_interactivo:
        respuesta = input("¿Desea descargar e instalar Inno Setup 6 de forma silenciosa ahora mismo? (s/n): ").strip().lower()
        if respuesta != 's':
            print("[AVISO] Instalación automática omitida. Deberá instalar Inno Setup manualmente desde https://jrsoftware.org/isdl.php")
            return None
    else:
        # En entornos de CI/CD o no interactivos, intentamos la instalación directa si es posible
        print("[INFO] Entorno no interactivo detectado. Procediendo con la instalación automática de Inno Setup 6...")

    import urllib.request
    import tempfile
    
    url = "https://files.jrsoftware.org/is/6/innosetup-6.3.3.exe"
    temp_dir = tempfile.gettempdir()
    exe_path = os.path.join(temp_dir, "innosetup-installer.exe")
    
    try:
        print("Descargando Inno Setup 6 desde jrsoftware.org...")
        urllib.request.urlretrieve(url, exe_path)
        print("Descarga completada. Iniciando instalación silenciosa...")
        
        # Ejecutar instalador con flags silenciosos
        # /SP- deshabilita el aviso de inicio
        # /VERYSILENT hace la instalación silenciosa sin interfaz gráfica
        # /SUPPRESSMSGBOXES suprime ventanas de diálogo
        # /NORESTART evita el reinicio del sistema
        subprocess.run([exe_path, "/SP-", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], check=True)
        print("[OK] Inno Setup 6 se ha instalado correctamente.")
        
        # Intentamos borrar el temporal de forma segura
        try:
            os.remove(exe_path)
        except Exception:
            pass
            
        # Retornamos la ruta donde debería estar instalado
        ruta_pf_x86 = os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Inno Setup 6", "ISCC.exe")
        if os.path.exists(ruta_pf_x86):
            return ruta_pf_x86
            
        ruta_pf = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Inno Setup 6", "ISCC.exe")
        if os.path.exists(ruta_pf):
            return ruta_pf
            
    except Exception as e:
        print(f"[ERROR] No se pudo instalar Inno Setup automáticamente: {e}")
        print("Por favor, instálelo manualmente desde: https://jrsoftware.org/isdl.php")
        
    return None

def compilar_instalador_inno_setup():
    print("\n[5/5] Buscando e integrando Inno Setup para generar el instalador (.exe)...")
    
    import shutil
    ruta_iscc = None
    
    # 1. Intentar buscar en PATH
    if shutil.which("ISCC.exe"):
        ruta_iscc = shutil.which("ISCC.exe")
        print(f"[OK] Inno Setup detectado en el PATH: {ruta_iscc}")
    else:
        # 2. Buscar en rutas estándar de 32 y 64 bits en Program Files y en LocalAppData del usuario
        pf_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        pf = os.environ.get("ProgramFiles", "C:\\Program Files")
        local_app = os.environ.get("LocalAppData", "")
        
        rutas_comunes = [
            os.path.join(pf_x86, "Inno Setup 6", "ISCC.exe"),
            os.path.join(pf, "Inno Setup 6", "ISCC.exe"),
            os.path.join(local_app, "Programs", "Inno Setup 6", "ISCC.exe")
        ]
        
        for ruta in rutas_comunes:
            if os.path.exists(ruta):
                ruta_iscc = ruta
                print(f"[OK] Inno Setup detectado en la ruta estándar: {ruta_iscc}")
                break
                
    # 3. Si no se encuentra, ofrecer instalarlo
    if not ruta_iscc:
        ruta_iscc = instalar_inno_setup_automaticamente()
        
    if not ruta_iscc:
        print("[ERROR] No se pudo localizar el compilador de Inno Setup (ISCC.exe).")
        print("        El instalador final (.exe) no pudo ser compilado.")
        print("        Puedes compilarlo tú mismo abriendo 'instalador.iss' en Inno Setup.")
        return
        
    # 4. Ejecutar el compilador sobre instalador.iss
    script_iss = "instalador.iss"
    if not os.path.exists(script_iss):
        print(f"[ERROR] No se encontró el script de Inno Setup: {script_iss}")
        return
        
    try:
        print(f"Ejecutando Inno Setup para empaquetar la aplicación...")
        subprocess.run([ruta_iscc, script_iss], check=True)
        print("[OK] ¡Instalador ejecutable generado con éxito!")
        print(f"     => Ubicación: {os.path.abspath(os.path.join('dist', 'Playwright_API_Capturer_Setup.exe'))}")
    except Exception as e:
        print(f"[ERROR] Error al ejecutar Inno Setup: {e}")

if __name__ == "__main__":
    print("="*65)
    print("  COMPILADOR AUTOMÁTICO - PLAYWRIGHT API CAPTURER  ")
    print("="*65)
    
    # 1. Instalar dependencias
    instalar_dependencias()
    
    # 2. Generar icono
    generar_icono_personalizado()
    
    # 2.5. Generar pantalla de carga (Splash)
    generar_splash_personalizado()
    
    # 3. Compilar
    compilar_ejecutable()
    
    # 4. Crear acceso directo
    crear_acceso_directo()
    
    # 5. Compilar instalador nativo
    compilar_instalador_inno_setup()
    
    print("\n" + "="*65)
    print(" ¡PROCESO FINALIZADO CON ÉXITO! ")
    print(" Puedes hacer doble clic en el acceso directo de tu Escritorio")
    print(" o distribuir el instalador desde la carpeta dist/.")
    print("="*65)
