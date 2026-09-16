import os
import re
import shutil
import zipfile
import tempfile
import json
from typing import Callable, Optional, Tuple, List
from adb_manager import ADBManager

class PackageInstaller:
    def __init__(self, adb_manager: ADBManager):
        self.adb = adb_manager

    def extract_package_info(self, apk_path: str) -> str:
        """Tenta extrair o nome do pacote do AndroidManifest.xml de um APK."""
        candidates = []
        try:
            with zipfile.ZipFile(apk_path, "r") as z:
                if "AndroidManifest.xml" in z.namelist():
                    manifest_data = z.read("AndroidManifest.xml")
                    matches = re.findall(rb'(?:[\x20-\x7e]\x00){4,}', manifest_data)
                    for m in matches:
                        text = m.decode("utf-16le", errors="ignore")
                        clean = re.sub(r'[^a-zA-Z0-9_\.]', '', text)
                        parts = clean.split('.')
                        if len(parts) >= 2 and parts[0] in ("com", "net", "org", "br"):
                            # Ignorar bibliotecas conhecidas internas
                            if not any(clean.startswith(prefix) for prefix in [
                                "com.android.", "com.google.", "com.facebook.", 
                                "androidx.", "com.squareup.", "org.chromium."
                            ]):
                                candidates.append(clean)
        except Exception:
            pass

        # Se encontrou candidatos, prioriza os mais curtos ou mais comuns
        if candidates:
            # Ordena por profundidade de pacote (ex: com.dts.freefireth tem 3 partes)
            candidates.sort(key=lambda x: (len(x.split('.')), len(x)))
            return candidates[0]

        return ""

    def install(
        self,
        file_path: str,
        serial: str,
        replace: bool = True,
        downgrade: bool = True,
        grant_perms: bool = True,
        launch_after: bool = True,
        progress_cb: Optional[Callable[[int, str, str], None]] = None
    ) -> Tuple[bool, str, str]:
        """
        Instala um arquivo .apks, .xapk ou .apk no dispositivo especificado.
        """
        def report(pct: int, msg: str, stage: str = "info"):
            if progress_cb:
                progress_cb(pct, msg, stage)

        if not os.path.exists(file_path):
            return False, f"Arquivo não encontrado: {file_path}", ""

        ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)
        report(5, f"Iniciando análise de {file_name}...", "info")

        temp_dir = None
        package_name = ""

        try:
            # Caso 1: APK Individual Comum
            if ext == ".apk":
                report(20, "Detectado APK individual. Extraindo informações...", "info")
                package_name = self.extract_package_info(file_path)
                report(40, f"Enviando e instalando no emulador {serial} via ADB...", "adb")

                args = ["-s", serial, "install"]
                if replace:
                    args.append("-r")
                if downgrade:
                    args.append("-d")
                if grant_perms:
                    args.append("-g")
                args.append(file_path)

                code, out, err = self.adb.run_command(args, timeout=120)
                if "Success" in out or code == 0:
                    report(90, "Instalação concluída com sucesso no emulador!", "success")
                else:
                    return False, f"Erro no ADB: {err or out}", package_name

            # Caso 2: APKS, XAPK ou ZIP
            elif ext in (".apks", ".xapk", ".zip"):
                temp_dir = tempfile.mkdtemp(prefix="dluz_install_")
                report(15, f"Descompactando pacote ({ext.upper()}) em diretório temporário...", "extract")

                with zipfile.ZipFile(file_path, "r") as z:
                    file_list = z.namelist()
                    total_files = len(file_list)
                    for i, item in enumerate(file_list):
                        z.extract(item, temp_dir)
                        if (i + 1) % max(1, total_files // 5) == 0:
                            pct = 15 + int((i / total_files) * 25)
                            report(pct, f"Extraindo arquivos ({i+1}/{total_files})...", "extract")

                report(40, "Arquivos extraídos. Verificando estrutura do pacote...", "info")

                # Se for XAPK, verificar manifest.json
                manifest_json_path = os.path.join(temp_dir, "manifest.json")
                if os.path.exists(manifest_json_path):
                    try:
                        with open(manifest_json_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            package_name = data.get("package_name", "")
                    except Exception:
                        pass

                # Procurar por OBBs (XAPK)
                obb_files = []
                for root, _, files in os.walk(temp_dir):
                    for f in files:
                        if f.endswith(".obb"):
                            obb_files.append(os.path.join(root, f))

                if obb_files:
                    report(45, f"Detectados {len(obb_files)} arquivo(s) OBB. Enviando para o emulador...", "obb")
                    for obb in obb_files:
                        obb_name = os.path.basename(obb)
                        obb_pkg = package_name
                        if not obb_pkg:
                            parts = obb_name.split(".")
                            if len(parts) >= 4:
                                obb_pkg = ".".join(parts[2:-1])

                        if not obb_pkg and "freefire" in obb_name.lower():
                            obb_pkg = "com.dts.freefireth"

                        if obb_pkg:
                            target_dir = f"/sdcard/Android/obb/{obb_pkg}"
                            self.adb.run_command(["-s", serial, "shell", "mkdir", "-p", target_dir], timeout=10)
                            report(50, f"Enviando {obb_name} para {target_dir}...", "obb")
                            code, out, err = self.adb.run_command(["-s", serial, "push", obb, f"{target_dir}/"], timeout=180)
                            if code != 0:
                                report(55, f"Aviso: Falha ao enviar OBB ({err or out}), continuando...", "warning")

                # Coletar todos os arquivos APK descompactados
                apk_files = []
                for root, _, files in os.walk(temp_dir):
                    for f in files:
                        if f.endswith(".apk"):
                            apk_files.append(os.path.join(root, f))

                if not apk_files:
                    return False, "Nenhum arquivo APK foi encontrado dentro do pacote.", package_name

                # Ordenar para garantir base.apk primeiro
                apk_files.sort(key=lambda x: (0 if "base" in os.path.basename(x).lower() else 1, os.path.basename(x)))

                # Tentar extrair o package_name do base.apk se ainda não tiver
                if not package_name and apk_files:
                    package_name = self.extract_package_info(apk_files[0])
                    if not package_name and "freefire" in file_name.lower():
                        package_name = "com.dts.freefireth"

                report(60, f"Instalando {len(apk_files)} splits via ADB (install-multiple)...", "adb")

                if len(apk_files) == 1:
                    args = ["-s", serial, "install"]
                else:
                    args = ["-s", serial, "install-multiple"]

                if replace:
                    args.append("-r")
                if downgrade:
                    args.append("-d")
                if grant_perms:
                    args.append("-g")

                args.extend(apk_files)

                report(70, "Processando instalação no Android... Aguarde alguns instantes.", "adb")
                code, out, err = self.adb.run_command(args, timeout=240)

                if "Success" in out or code == 0:
                    report(90, "Todos os splits foram instalados com Sucesso!", "success")
                else:
                    return False, f"Falha na instalação ADB: {err or out}", package_name
            else:
                return False, f"Extensão não suportada: {ext}", ""

            # Abrir jogo se solicitado
            if launch_after and package_name:
                report(95, f"Iniciando aplicativo {package_name} no emulador...", "launch")
                ok, launch_msg = self.adb.launch_app(serial, package_name)
                if ok:
                    report(100, f"Jogo {package_name} instalado e aberto com sucesso!", "done")
                else:
                    report(100, f"Instalação finalizada com sucesso! (Não foi possível abrir automaticamente)", "done")
            else:
                report(100, "Instalação concluída com sucesso no emulador!", "done")

            return True, "Instalação realizada com sucesso!", package_name

        except Exception as e:
            report(0, f"Erro inesperado: {str(e)}", "error")
            return False, str(e), package_name
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
