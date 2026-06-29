import os
import sys
import json
import threading
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox

VERSION_LOCAL = "1.2.0"

def verificar_actualizaciones(app_instance, manual=False):
    """Verifica de forma asíncrona si existen actualizaciones en GitHub."""
    def check():
        import urllib.request
        url_version_remota = "https://raw.githubusercontent.com/MarchettiFacundo/Playwright-API-Capturer/main/version.json"
        try:
            req = urllib.request.Request(
                url_version_remota, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                version_remota = data.get("version")
                url_descarga = data.get("download_url")
                installer_url = data.get("installer_url")
                
                if version_remota:
                    try:
                        v_local_parts = [int(x) for x in VERSION_LOCAL.split('.')]
                        v_remota_parts = [int(x) for x in version_remota.split('.')]
                    except ValueError:
                        v_local_parts = [0]
                        v_remota_parts = [0]
                        
                    if v_remota_parts > v_local_parts:
                        app_instance.root.after(0, lambda: notificar_actualizacion(version_remota, url_descarga, installer_url))
                    else:
                        if manual:
                            app_instance.root.after(0, lambda: messagebox.showinfo(
                                "Sin actualizaciones", 
                                f"Tu aplicación está actualizada a la última versión (v{VERSION_LOCAL})."
                            ))
                else:
                    if manual:
                        app_instance.root.after(0, lambda: messagebox.showerror(
                            "Error", 
                            "No se pudo verificar el archivo de versión remota."
                        ))
        except Exception as e:
            if manual:
                app_instance.root.after(0, lambda: messagebox.showerror(
                    "Error de Conexión", 
                    f"No se pudo conectar al servidor de actualizaciones:\n{e}"
                ))

    def notificar_actualizacion(v_remota, url_web, url_installer):
        res = messagebox.askyesnocancel(
            "Actualización Disponible", 
            f"¡Una nueva versión (v{v_remota}) está disponible!\n"
            f"Tu versión actual es la v{VERSION_LOCAL}.\n\n"
            "¿Deseas descargar e instalar automáticamente la actualización ahora?\n"
            "Pulse 'Sí' para actualizar automáticamente, 'No' para descargar de forma manual en el navegador o 'Cancelar' para ignorarla."
        )
        if res is True:
            if url_installer:
                descargar_y_ejecutar_instalador(app_instance, url_installer, v_remota)
            else:
                messagebox.showwarning("Aviso", "No se detectó un enlace directo para el instalador. Se procederá con la descarga manual.")
                import webbrowser
                webbrowser.open(url_web)
        elif res is False:
            import webbrowser
            webbrowser.open(url_web)

    threading.Thread(target=check, daemon=True).start()

def descargar_y_ejecutar_instalador(app_instance, url_installer, version_nueva):
    """Descarga e instala la nueva versión mediante una ventana modal."""
    download_win = tk.Toplevel(app_instance.root)
    download_win.title("Actualizando Aplicación")
    download_win.geometry("380x150")
    download_win.resizable(False, False)
    download_win.configure(bg=app_instance.color_bg)
    download_win.transient(app_instance.root)
    download_win.grab_set()
    
    download_win.update_idletasks()
    w = download_win.winfo_width()
    h = download_win.winfo_height()
    x = app_instance.root.winfo_x() + (app_instance.root.winfo_width() - w) // 2
    y = app_instance.root.winfo_y() + (app_instance.root.winfo_height() - h) // 2
    download_win.geometry(f"+{x}+{y}")
    
    lbl_info = tk.Label(
        download_win, 
        text=f"Descargando actualización v{version_nueva}...\nPor favor, espere.", 
        fg=app_instance.color_fg, 
        bg=app_instance.color_bg, 
        font=("Segoe UI", 10),
        justify="left"
    )
    lbl_info.pack(pady=(20, 10), padx=20, anchor="w")
    
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Download.Horizontal.TProgressbar", 
                     troughcolor="#1e293b", 
                     background="#06b6d4", 
                     thickness=12, 
                     borderwidth=0)
    
    progress = ttk.Progressbar(
        download_win, 
        style="Download.Horizontal.TProgressbar", 
        orient="horizontal", 
        length=340, 
        mode="determinate"
    )
    progress.pack(pady=10, padx=20)
    
    cancelled = [False]
    
    def on_close():
        if messagebox.askyesno("Cancelar Descarga", "¿Estás seguro de que deseas cancelar la descarga de la actualización?"):
            cancelled[0] = True
            download_win.destroy()
            
    download_win.protocol("WM_DELETE_WINDOW", on_close)
    
    def download_thread():
        import urllib.request
        
        try:
            req = urllib.request.Request(
                url_installer, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                total_size = int(response.info().get('Content-Length', 0))
                bytes_descargados = 0
                
                temp_dir = tempfile.gettempdir()
                temp_file_path = os.path.join(temp_dir, f"Playwright_API_Capturer_Setup_{version_nueva}.exe")
                
                ultimo_porcentaje = -1
                with open(temp_file_path, "wb") as f_out:
                    chunk_size = 16384 # 16KB
                    while True:
                        if cancelled[0]:
                            return
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        bytes_descargados += len(chunk)
                        
                        if total_size > 0:
                            percent = int(100 * bytes_descargados / total_size)
                            if percent != ultimo_porcentaje:
                                ultimo_porcentaje = percent
                                download_win.after(0, lambda p=percent: actualizar_progreso(p))
                            
                if not cancelled[0]:
                    download_win.after(0, lambda: finalizar_y_ejecutar(temp_file_path))
                    
        except Exception as e:
            if not cancelled[0]:
                download_win.after(0, lambda err=e: manejar_error_descarga(err))
                
    def actualizar_progreso(percent):
        progress["value"] = percent
        lbl_info.config(text=f"Descargando actualización v{version_nueva}...\nProgreso: {percent}%")
        
    def finalizar_y_ejecutar(file_path):
        download_win.destroy()
        messagebox.showinfo("Instalación Lista", "Descarga completada con éxito.\nSe iniciará el instalador y la aplicación se cerrará para permitir la actualización.")
        try:
            os.startfile(file_path)
            app_instance.root.destroy()
            sys.exit(0)
        except Exception as e:
            messagebox.showerror("Error al Ejecutar", f"No se pudo ejecutar el instalador automáticamente:\n{e}\nPuedes ejecutarlo manualmente en:\n{file_path}")
            
    def manejar_error_descarga(err):
        download_win.destroy()
        if messagebox.askyesno(
            "Error de Descarga", 
            f"No se pudo completar la descarga automática debido al siguiente error:\n{err}\n\n"
            "¿Deseas intentar descargar la actualización manualmente desde tu navegador?"
        ):
            import webbrowser
            url_releases = "https://github.com/MarchettiFacundo/Playwright-API-Capturer/releases/latest"
            webbrowser.open(url_releases)
            
    threading.Thread(target=download_thread, daemon=True).start()
