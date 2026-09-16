import os
import sys
import subprocess
import re
from typing import List, Dict, Optional, Tuple

class ADBManager:
    KNOWN_ADB_PATHS = [
        r"C:\Program Files\BlueStacks_nxt_cn\HD-Adb.exe",
        r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
        r"C:\Program Files (x86)\BlueStacks_nxt\HD-Adb.exe",
        r"C:\Users\dluzgg\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        r"C:\Program Files\WSA PacMan\embedded-tools\adb.exe",
        r"C:\Program Files\e2eSoft\iVCam\adb\adb.exe",
    ]

    EMULATOR_PORTS = [5555, 5554, 5556, 5557, 5559, 62001, 16384, 21503, 28001]

    def __init__(self):
        self.adb_path = self._find_best_adb()

    def _find_best_adb(self) -> str:
        # 1. Se BlueStacks estiver instalado, prioriza HD-Adb.exe para evitar colisao de daemon
        for path in self.KNOWN_ADB_PATHS:
            if "HD-Adb.exe" in path and os.path.exists(path):
                return path

        # 2. ADB embutido no proprio aplicativo (pasta bin/)
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        bundled_adb = os.path.join(base_dir, "bin", "adb.exe")
        if os.path.exists(bundled_adb):
            return bundled_adb

        # 3. Outros caminhos conhecidos instalados no PC
        for path in self.KNOWN_ADB_PATHS:
            if os.path.exists(path):
                return path

        # Fallback para adb no PATH
        return "adb"

    def run_command(self, args: List[str], timeout: int = 40) -> Tuple[int, str, str]:
        cmd = [self.adb_path] + args
        startupinfo = None
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
            return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Comando atingiu o tempo limite (timeout)."
        except Exception as e:
            return -1, "", str(e)

    def auto_connect_emulators(self):
        for port in self.EMULATOR_PORTS:
            self.run_command(["connect", f"127.0.0.1:{port}"], timeout=3)

    def list_devices(self) -> List[Dict[str, str]]:
        code, stdout, _ = self.run_command(["devices", "-l"])
        devices = []

        if code == 0:
            lines = stdout.splitlines()
            for line in lines[1:]:
                line = line.strip()
                if not line or line.startswith("*"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    serial = parts[0]
                    status = parts[1]

                    if status == "device":
                        model = self.get_device_prop(serial, "ro.product.model") or serial
                        brand = self.get_device_prop(serial, "ro.product.brand") or ""
                        android = self.get_device_prop(serial, "ro.build.version.release") or ""
                        
                        friendly_name = f"{model}"
                        if brand and brand.lower() not in model.lower():
                            friendly_name = f"{brand} {model}"
                        if "emulator" in serial or "127.0.0.1" in serial:
                            friendly_name += " (Emulador)"

                        devices.append({
                            "id": serial,
                            "name": friendly_name.strip(),
                            "status": "online",
                            "model": model,
                            "brand": brand,
                            "android": android,
                            "adb_path": self.adb_path
                        })
                    else:
                        devices.append({
                            "id": serial,
                            "name": f"{serial} ({status})",
                            "status": status,
                            "model": serial,
                            "brand": "",
                            "android": "",
                            "adb_path": self.adb_path
                        })

        if not devices:
            self.auto_connect_emulators()
            code, stdout, _ = self.run_command(["devices", "-l"])
            if code == 0:
                for line in stdout.splitlines()[1:]:
                    line = line.strip()
                    if not line or line.startswith("*"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "device":
                        serial = parts[0]
                        model = self.get_device_prop(serial, "ro.product.model") or serial
                        devices.append({
                            "id": serial,
                            "name": f"{model} (Emulador)",
                            "status": "online",
                            "model": model,
                            "brand": "",
                            "android": "",
                            "adb_path": self.adb_path
                        })

        return devices

    def get_device_prop(self, serial: str, prop: str) -> str:
        code, stdout, _ = self.run_command(["-s", serial, "shell", "getprop", prop], timeout=5)
        if code == 0:
            return stdout.strip()
        return ""

    def launch_app(self, serial: str, package_name: str) -> Tuple[bool, str]:
        code, out, err = self.run_command(
            ["-s", serial, "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
            timeout=10
        )
        if code == 0:
            return True, f"Aplicativo {package_name} iniciado com sucesso!"
        return False, f"Falha ao iniciar {package_name}: {err or out}"
