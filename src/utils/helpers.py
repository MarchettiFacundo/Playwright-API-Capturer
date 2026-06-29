import os
import sys
import socket

def is_dir_writable(path):
    """Verifica si un directorio tiene permisos de escritura."""
    try:
        test_file = os.path.join(path, ".test_write")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception:
        return False

def get_documents_folder():
    """Obtiene la ruta a la carpeta Documentos del usuario en Windows o fallback."""
    try:
        import ctypes
        from ctypes import wintypes
        CSIDL_PERSONAL = 5
        SHGFP_TYPE_CURRENT = 0
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
        return buf.value
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Documents")

def find_chrome_path():
    """Busca la ruta del ejecutable de Google Chrome en el registro o ubicaciones estándar."""
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
        for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hkey, key_path) as key:
                    path, _ = winreg.QueryValue(key, None)
                    if os.path.exists(path):
                        return path
            except Exception:
                pass
    except Exception:
        pass

    rutas = [
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LocalAppData", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for r in rutas:
        if r and os.path.exists(r):
            return r
    return None

def find_edge_path():
    """Busca la ruta del ejecutable de Microsoft Edge en el registro o ubicaciones estándar."""
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
        for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hkey, key_path) as key:
                    path, _ = winreg.QueryValue(key, None)
                    if os.path.exists(path):
                        return path
            except Exception:
                pass
    except Exception:
        pass

    rutas = [
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("LocalAppData", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    for r in rutas:
        if r and os.path.exists(r):
            return r
    return None

def is_port_in_use(port):
    """Comprueba si un puerto localhost está en uso."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0

def obtener_ruta_recurso(relative_path):
    """Obtiene la ruta absoluta para un recurso, compatible con PyInstaller MEIPASS."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, relative_path)

def limpiar_headers(headers):
    """
    Filtra headers del navegador que no son necesarios o pueden interferir 
    al replicar la petición con la librería requests en Python.
    """
    headers_filtrados = {}
    excluir = {
        'host', 'content-length', 'connection', 'accept-encoding',
        'sec-ch-ua', 'sec-ch-ua-mobile', 'sec-ch-ua-platform',
        'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-site',
        'sec-fetch-user', 'upgrade-insecure-requests'
    }
    for k, v in headers.items():
        if k.lower() not in excluir:
            headers_filtrados[k] = v
    return headers_filtrados

def parsear_seleccion(opcion, max_length):
    """
    Parsea cadenas de entrada complejas como '0', '0,2,3' o '0-3, 5'
    y devuelve una lista de enteros ordenados y validados.
    """
    indices = []
    partes = opcion.split(',')
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        if '-' in parte:
            subpartes = parte.split('-')
            if len(subpartes) == 2:
                try:
                    start = int(subpartes[0].strip())
                    end = int(subpartes[1].strip())
                    if start <= end:
                        indices.extend(range(start, end + 1))
                    else:
                        indices.extend(range(end, start + 1))
                except ValueError:
                    return None
            else:
                return None
        else:
            try:
                indices.append(int(parte))
            except ValueError:
                return None
                
    indices_validos = []
    for idx in indices:
        if 0 <= idx < max_length:
            if idx not in indices_validos:
                indices_validos.append(idx)
        else:
            print(f"[WARN] Indice {idx} fuera de rango. Ignorado.")
            
    indices_validos.sort()
    return indices_validos
