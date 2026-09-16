import os
import sys
import json
import threading
import socket
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import webview
import tkinter as tk
from tkinter import filedialog

from adb_manager import ADBManager
from package_installer import PackageInstaller
from device_optimizer import DeviceOptimizer

class DLuzApi:
    def __init__(self, adb_mgr: ADBManager, installer: PackageInstaller, optimizer: DeviceOptimizer):
        self.adb = adb_mgr
        self.installer = installer
        self.optimizer = optimizer
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

    def scan_packages(self):
        search_dirs = [
            os.path.join(os.path.expanduser('~'), 'Desktop'),
            os.path.join(os.path.expanduser('~'), 'Downloads'),
            r"C:\Users\dluzgg\Desktop\free fire v7a\FF V7A",
            r"C:\Users\dluzgg\Desktop\free fire att",
            os.path.dirname(os.path.abspath(__file__)),
        ]
        seen_paths = set()
        packages = []

        for sdir in search_dirs:
            if not os.path.exists(sdir):
                continue
            for root, dirs, files in os.walk(sdir):
                depth = root[len(sdir):].count(os.sep)
                if depth > 2:
                    continue
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in ('.apks', '.xapk', '.apk'):
                        fpath = os.path.join(root, f)
                        if fpath in seen_paths:
                            continue
                        seen_paths.add(fpath)
                        try:
                            sz = os.path.getsize(fpath)
                            if ext == '.apk' and sz < 5 * 1024 * 1024 and 'free' not in f.lower():
                                continue
                            sz_str = self._format_size(sz)
                            clean_name = f.replace('+', ' ')
                            is_ff = 'free' in f.lower() or 'ff' in f.lower()
                            is_v7a = 'v7a' in f.lower()
                            tag = ext.replace('.', '').upper()
                            if is_v7a:
                                tag += ' • ARMv7a'
                            elif is_ff:
                                tag += ' • Free Fire'

                            packages.append({
                                'path': fpath,
                                'name': clean_name,
                                'size': sz_str,
                                'ext': ext.replace('.', '').upper(),
                                'is_ff': is_ff,
                                'is_v7a': is_v7a,
                                'tag': tag
                            })
                        except Exception:
                            pass

        packages.sort(key=lambda p: (
            0 if (p['is_ff'] and p['is_v7a']) else (1 if p['is_ff'] else 2),
            p['name']
        ))
        return packages

    def get_initial_data(self):
        devices = self.adb.list_devices()
        packages = self.scan_packages()

        return {
            "devices": devices,
            "adb_path": self.adb.adb_path,
            "packages": packages,
            "creator": {
                "name": "DLuz",
                "channel": "DLuz Games",
                "youtube": "https://www.youtube.com/@dluzgames",
                "member": "https://www.youtube.com/@dluzgames/join",
                "instagram": "https://www.instagram.com/dluzgames/",
                "store": "https://loja.dluz.com.br",
                "news": "https://dluz.com.br"
            },
            "device_profile": {
                "manufacturer": "INFINIX",
                "brand": "INFINIX",
                "model": "Infinix X6891"
            }
        }

    def rescan_packages(self):
        return self.scan_packages()

    def refresh_devices(self):
        return self.adb.list_devices()

    def apply_device_profile(self, serial: str = None):
        return self.optimizer.apply_profile(serial)

    def open_url(self, url: str):
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False

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
    optimizer = DeviceOptimizer(adb_mgr)
    api = DLuzApi(adb_mgr, installer, optimizer)

    port = find_free_port()
    start_server(ui_dir, port)
    app_url = f"http://127.0.0.1:{port}/index.html"

    window = webview.create_window(
        title="DLuz ZArchiver — por DLuz Games",
        url=app_url,
        js_api=api,
        width=960,
        height=780,
        min_size=(860, 660),
        resizable=True,
        background_color='#090d16'
    )
    api.set_window(window)
    webview.start(debug=False)

if __name__ == "__main__":
    main()
