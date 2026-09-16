import os
import sys
import json
import threading
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import webview
import tkinter as tk
from tkinter import filedialog

from adb_manager import ADBManager
from package_installer import PackageInstaller

class DLuzApi:
    def __init__(self, adb_mgr: ADBManager, installer: PackageInstaller):
        self.adb = adb_mgr
        self.installer = installer
        self._window = None

    def set_window(self, window):
        self._window = window

    def _format_size(self, bytes_size: int) -> str:
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.1f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"

    def find_ff_apks(self) -> str:
        candidates = [
            r"C:\Users\dluzgg\Desktop\free fire v7a\FF V7A\Free Fire V7A versao 1.132.1.apks",
            r"C:\Users\dluzgg\Desktop\free fire v7a\FF V7A\Free Fire V7A att via zarchiver.apks",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c

        # Checar na pasta Desktop ou diretório atual
        search_dirs = [
            r"C:\Users\dluzgg\Desktop\free fire v7a\FF V7A",
            os.path.join(os.path.expanduser("~"), "Desktop"),
            os.path.dirname(os.path.abspath(__file__))
        ]
        for d in search_dirs:
            if os.path.exists(d):
                for f in os.listdir(d):
                    if f.endswith(".apks") and ("free fire" in f.lower() or "1.132" in f):
                        return os.path.join(d, f)

        return candidates[0]

    def get_initial_data(self):
        devices = self.adb.list_devices()
        ff_path = self.find_ff_apks()
        ff_exists = os.path.exists(ff_path)
        ff_size = ""
        if ff_exists:
            try:
                ff_size = self._format_size(os.path.getsize(ff_path))
            except Exception:
                ff_size = "N/A"

        return {
            "devices": devices,
            "adb_path": self.adb.adb_path,
            "preset_ff": {
                "exists": ff_exists,
                "path": ff_path,
                "name": os.path.basename(ff_path),
                "size": ff_size,
                "version": "1.132.1"
            }
        }

    def refresh_devices(self):
        return self.adb.list_devices()

    def browse_file(self):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        file_path = filedialog.askopenfilename(
            title="Selecione o arquivo de jogo (APKS, XAPK ou APK)",
            filetypes=[
                ("Pacotes de Jogos Android", "*.apks;*.xapk;*.apk;*.zip"),
                ("APKS (Split APKs)", "*.apks"),
                ("XAPK (APKPure)", "*.xapk"),
                ("APK Individual", "*.apk"),
                ("Todos os Arquivos", "*.*")
            ]
        )
        root.destroy()

        if file_path and os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)
            return {
                "path": file_path,
                "name": os.path.basename(file_path),
                "size": self._format_size(size_bytes),
                "ext": os.path.splitext(file_path)[1].replace(".", "").lower()
            }
        return None

    def install(self, serial: str, file_path: str, options: dict):
        threading.Thread(
            target=self._install_worker,
            args=(serial, file_path, options),
            daemon=True
        ).start()
        return {"status": "started"}

    def _install_worker(self, serial: str, file_path: str, options: dict):
        def progress_cb(pct: int, msg: str, stage: str):
            if self._window:
                js_code = f"window.onInstallProgress({pct}, {json.dumps(msg)}, {json.dumps(stage)});"
                try:
                    self._window.evaluate_js(js_code)
                except Exception:
                    pass

        replace = options.get("replace", True)
        downgrade = options.get("downgrade", True)
        grant_perms = options.get("grant_perms", True)
        launch_after = options.get("launch_after", True)

        self.installer.install(
            file_path=file_path,
            serial=serial,
            replace=replace,
            downgrade=downgrade,
            grant_perms=grant_perms,
            launch_after=launch_after,
            progress_cb=progress_cb
        )

def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def start_server(ui_dir: str, port: int):
    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=ui_dir, **kwargs)
        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', port), QuietHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server

def main():
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    ui_dir = os.path.join(base_dir, "ui")

    adb_mgr = ADBManager()
    installer = PackageInstaller(adb_mgr)
    api = DLuzApi(adb_mgr, installer)

    port = find_free_port()
    start_server(ui_dir, port)
    app_url = f"http://127.0.0.1:{port}/index.html"

    window = webview.create_window(
        title="DLuz ZArchiver — Instalador Universal ADB",
        url=app_url,
        js_api=api,
        width=920,
        height=720,
        min_size=(800, 600),
        resizable=True,
        background_color='#090d16'
    )
    api.set_window(window)
    webview.start(debug=False)

if __name__ == "__main__":
    main()
