import os
import re
from typing import Dict, Any
from adb_manager import ADBManager

class DeviceOptimizer:
    BLUESTACKS_CONF_PATHS = [
        r"C:\ProgramData\BlueStacks_nxt_cn\bluestacks.conf",
        r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf",
        r"C:\ProgramData\BlueStacks_msi\bluestacks.conf",
        r"C:\ProgramData\BlueStacks_msi5\bluestacks.conf",
    ]

    PROFILE = {
        "manufacturer": "INFINIX",
        "brand": "INFINIX",
        "model": "Infinix X6891",
        "profile_code": "stou"
    }

    def __init__(self, adb_manager: ADBManager):
        self.adb = adb_manager

    def apply_infinix_to_bluestacks(self) -> int:
        updated_files = 0
        for conf_path in self.BLUESTACKS_CONF_PATHS:
            if not os.path.exists(conf_path):
                continue
            try:
                with open(conf_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Substitui ou atualiza para todas as instâncias encontradas
                instances = set(re.findall(r'bst\.instance\.([a-zA-Z0-9_]+)\.', content))
                if not instances:
                    instances = {"Pie64", "Nougat32", "Nougat64", "Tiramisu64"}

                new_content = content
                for inst in instances:
                    # Chaves a atualizar
                    keys = {
                        f'bst.instance.{inst}.device_custom_manufacturer': f'"{self.PROFILE["manufacturer"]}"',
                        f'bst.instance.{inst}.device_custom_brand': f'"{self.PROFILE["brand"]}"',
                        f'bst.instance.{inst}.device_custom_model': f'"{self.PROFILE["model"]}"',
                        f'bst.instance.{inst}.device_profile_code': f'"{self.PROFILE["profile_code"]}"',
                    }

                    for key, val in keys.items():
                        pattern = rf'^{re.escape(key)}=.*$'
                        if re.search(pattern, new_content, flags=re.MULTILINE):
                            new_content = re.sub(pattern, f'{key}={val}', new_content, flags=re.MULTILINE)
                        else:
                            # Adiciona no final se não existir
                            new_content += f'\n{key}={val}'

                with open(conf_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                updated_files += 1
            except Exception as e:
                print(f"Erro ao atualizar {conf_path}: {e}")

        return updated_files

    def apply_infinix_via_adb(self, serial: str) -> bool:
        if not serial:
            return False
        try:
            self.adb.run_command(["-s", serial, "shell", "setprop", "ro.product.manufacturer", self.PROFILE["manufacturer"]], timeout=5)
            self.adb.run_command(["-s", serial, "shell", "setprop", "ro.product.brand", self.PROFILE["brand"]], timeout=5)
            self.adb.run_command(["-s", serial, "shell", "setprop", "ro.product.model", self.PROFILE["model"]], timeout=5)
            return True
        except Exception:
            return False

    def apply_profile(self, serial: str = None) -> Dict[str, Any]:
        conf_count = self.apply_infinix_to_bluestacks()
        adb_ok = False
        if serial:
            adb_ok = self.apply_infinix_via_adb(serial)

        return {
            "success": True,
            "conf_updated": conf_count,
            "adb_updated": adb_ok,
            "profile": self.PROFILE,
            "message": "Perfil Infinix X6891 aplicado com sucesso!"
        }
