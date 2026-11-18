"""Módulo de Reconstrucción y Gestión del Visor 3D (.dev)
Gestiona la compilación con .NET 8 (dotnet build / run) de Visor3D.csproj,
verificación de artefactos de salida y comprobación de proyecto Godot.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .entorno import configurar_variables_entorno
from .rutas import (
    GODOT_PROJECT_FILE,
    GODOT_PROY_DIR,
    LANZAR_BAT,
    REPO_ROOT,
    VISOR_BASE_DIR,
    VISOR_CSPROJ,
    VISOR_HERRAMIENTAS_DIR,
    VISOR_OUTPUT_DLL,
    VISOR_OUTPUT_EXE,
    localizar_dotnet,
)


def comprobar_dotnet() -> Tuple[bool, str]:
    """Comprueba si dotnet está disponible (PATH o instalación habitual)."""
    exe = localizar_dotnet()
    if exe is None:
        return False, "dotnet no encontrado en PATH ni en ubicaciones habituales"
    try:
        # Se consulta fuera de .dev: su global.json fija SDK 8.0.400 y bloquea
        # cualquier lectura de versión si esa revisión no está instalada.
        res = subprocess.run(
            [str(exe), "--version"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, res.stdout.strip()
        return False, (res.stdout or res.stderr).strip() or f"dotnet devolvió código {res.returncode}"
    except Exception as e:
        return False, str(e)


def estado_visor() -> Dict[str, Any]:
    """Devuelve un informe del estado del proyecto Visor3D."""
    dotnet_ok, version_dotnet = comprobar_dotnet()

    dll_existe = VISOR_OUTPUT_DLL.is_file()
    dll_mod_time = None
    if dll_existe:
        try:
            dll_mod_time = time.ctime(VISOR_OUTPUT_DLL.stat().st_mtime)
        except Exception:
            pass

    return {
        "dotnet_disponible": dotnet_ok,
        "dotnet_version": version_dotnet,
        "csproj_existe": VISOR_CSPROJ.is_file(),
        "ruta_csproj": str(VISOR_CSPROJ),
        "dll_compilada": dll_existe,
        "ruta_dll": str(VISOR_OUTPUT_DLL),
        "dll_fecha_mod": dll_mod_time,
        "godot_proy_existe": GODOT_PROJECT_FILE.is_file(),
        "ruta_godot_proy": str(GODOT_PROY_DIR),
        "lanzar_bat_existe": LANZAR_BAT.is_file(),
    }


def reconstruir_visor(
    configuracion: str = "Debug",
    limpiar: bool = False,
    publicar_single_file: bool = False,
) -> Tuple[bool, str]:
    """Reconstruye el Visor3D ejecutando dotnet build con configuración canónica.

    Garantiza que DOTNET_CLI_TELEMETRY_OPTOUT=1 esté activo para evitar fallos de
    acceso al registro en Windows, y compila Visor3D.csproj sin abandonar el workspace.
    """
    configurar_variables_entorno()

    if not VISOR_CSPROJ.is_file():
        return False, f"No se encontró el archivo de proyecto: {VISOR_CSPROJ}"

    dotnet_ok, version = comprobar_dotnet()
    if not dotnet_ok:
        return False, f"El compilador dotnet no está disponible: {version}"

    dotnet_exe = str(localizar_dotnet())

    env = os.environ.copy()
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    env["DOTNET_SKIP_FIRST_TIME_EXPERIENCE"] = "1"

    t0 = time.time()

    if limpiar:
        print("[Visor3D] Limpiando compilación previa...")
        cmd_clean = [dotnet_exe, "clean", str(VISOR_CSPROJ), "-c", configuracion]
        subprocess.run(cmd_clean, cwd=str(VISOR_HERRAMIENTAS_DIR), env=env, capture_output=True)

    if publicar_single_file:
        print(f"[Visor3D] Publicando ejecutable único standalone (-c {configuracion})...")
        cmd = [
            dotnet_exe,
            "publish",
            str(VISOR_CSPROJ),
            "-c", configuracion,
            "-r", "win-x64",
            "--self-contained", "true",
            "/p:PublishSingleFile=true",
            "/p:SkipGodotAssets=true",
        ]
    else:
        print(f"[Visor3D] Compilando ensamblado del visor (-c {configuracion})...")
        cmd = [
            dotnet_exe,
            "build",
            str(VISOR_CSPROJ),
            "-c", configuracion,
        ]

    try:
        res = subprocess.run(
            cmd,
            cwd=str(VISOR_HERRAMIENTAS_DIR),
            env=env,
            capture_output=True,
            text=True,
        )
        elapsed = time.time() - t0

        if res.returncode == 0:
            msg = (
                f"Compilación exitosa en {elapsed:.2f}s.\n"
                f"Ensamblado generado: {VISOR_OUTPUT_DLL}\n"
            )
            return True, msg
        else:
            errores = [line for line in res.stdout.splitlines() if "error" in line.lower() or "fail" in line.lower()]
            err_msg = "\n".join(errores[:10]) if errores else res.stderr
            return False, f"Fallo en la compilación (código {res.returncode}):\n{err_msg}"
    except Exception as e:
        return False, f"Excepción al ejecutar dotnet build: {e}"


def lanzar_visor(args: Optional[List[str]] = None) -> int:
    """Lanza el Visor3D con dotnet run pasando los argumentos recibidos."""
    configurar_variables_entorno()

    env = os.environ.copy()
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"

    dotnet_exe = localizar_dotnet()
    if dotnet_exe is None:
        print("[Visor3D] dotnet no encontrado en PATH ni en ubicaciones habituales.")
        return 1

    cmd = [str(dotnet_exe), "run", "--project", str(VISOR_CSPROJ), "-c", "Debug", "--"]
    if args:
        cmd.extend(args)

    print(f"[Visor3D] Ejecutando: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(VISOR_HERRAMIENTAS_DIR), env=env)
    return res.returncode
