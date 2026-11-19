"""Módulo de Gestión y Verificación de Dependencias (.dev)
WoldVirtualP2P3D · Versión canónica modular

Verifica el estado de dependencias del entorno de desarrollo:
- .NET 8 SDK y paquetes NuGet requeridos
- Python local (.dev/.python y .dev/venv) y paquetes pip
- DLLs nativas de seguridad de Windows (DPAPI, NCrypt, BCrypt, TBS, Kernel32)
- Recursos de construcción y paquetes volátiles de Godot
"""
from __future__ import annotations

import ctypes
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .rutas import (
    DEV_DIR,
    DEV_GITHUB_DIR,
    DEV_GITHUB_WORKFLOWS_DIR,
    DEV_PYTEST_INI,
    ESCENA_CANONICA_VISOR,
    GODOT_PROJECT_FILE,
    PYTHON_EXE,
    REPO_ROOT,
    VENV_PYTHON,
    VISOR_CSPROJ,
    VISOR_HERRAMIENTAS_DIR,
    VSCODE_DIR,
    localizar_dotnet,
)

DEPENDENCIAS_JSON = DEV_DIR / "dependencias.json"


def verificar_dlls_nativas() -> List[Dict[str, Any]]:
    """Comprueba la disponibilidad de DLLs del sistema operativo requeridas para Zero Trust."""
    dlls_esperadas = [
        ("Crypt32.dll", "DPAPI Data Protection API"),
        ("ncrypt.dll", "CNG Key Storage Provider / TPM 2.0"),
        ("bcrypt.dll", "BCrypt Cryptographic Primitives"),
        ("tbs.dll", "TPM Base Services (Hardware NV)"),
        ("kernel32.dll", "Detección de Depurador y Memory Guards"),
    ]

    resultados = []
    for nombre, desc in dlls_esperadas:
        disponible = False
        try:
            handle = ctypes.windll.kernel32.LoadLibraryW(nombre)
            if handle:
                disponible = True
        except Exception:
            disponible = False

        resultados.append({
            "nombre": nombre,
            "descripcion": desc,
            "disponible": disponible,
        })
    return resultados


def verificar_dotnet_sdk() -> Dict[str, Any]:
    """Comprueba la disponibilidad del SDK de .NET."""
    dotnet_exe = localizar_dotnet()
    if dotnet_exe is None:
        return {"disponible": False, "version": "No instalado", "ruta": None}

    try:
        # Fuera de .dev: su global.json fija SDK 8.0.400 y bloquea la consulta
        # de versión si esa revisión no está instalada.
        res = subprocess.run(
            [str(dotnet_exe), "--version"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        version = res.stdout.strip() if res.returncode == 0 else "Error al consultar"
        es_net8_plus = version.startswith("8.") or version.startswith("9.") or version.startswith("10.") or version.startswith("11.")
        return {
            "disponible": True,
            "version": version,
            "compatible": es_net8_plus,
            "ruta": str(dotnet_exe),
        }
    except Exception as ex:
        return {"disponible": False, "version": str(ex), "ruta": str(dotnet_exe)}


def obtener_version_python_dev() -> Dict[str, Any]:
    """Inspecciona y valida el intérprete Python canónico en .dev/.python (Python 3.15+)."""
    if not PYTHON_EXE.is_file():
        return {
            "disponible": False,
            "version": "No encontrado",
            "ruta": str(PYTHON_EXE),
            "es_python_315": False,
        }
    try:
        res = subprocess.run(
            [str(PYTHON_EXE), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        ver_str = (res.stdout or res.stderr).strip()
        es_315 = "3.15" in ver_str
        return {
            "disponible": True,
            "version": ver_str,
            "ruta": str(PYTHON_EXE),
            "es_python_315": es_315,
        }
    except Exception as ex:
        return {
            "disponible": False,
            "version": str(ex),
            "ruta": str(PYTHON_EXE),
            "es_python_315": False,
        }


def verificar_paquetes_python() -> Dict[str, Any]:
    """Comprueba módulos requeridos en el entorno Python activo."""
    modulos = ["websockets", "requests", "json", "hashlib", "ctypes"]
    estado_modulos = {}

    for mod in modulos:
        try:
            __import__(mod)
            estado_modulos[mod] = True
        except ImportError:
            estado_modulos[mod] = False

    return {
        "interprete_actual": sys.executable,
        "es_local_dev": str(DEV_DIR) in sys.executable,
        "python_dev": obtener_version_python_dev(),
        "modulos": estado_modulos,
    }


def verificar_recursos_visor() -> Dict[str, Any]:
    """Comprueba recursos requeridos para compilar y empaquetar el Visor 3D."""
    csproj_ok = VISOR_CSPROJ.is_file()
    godot_ok = GODOT_PROJECT_FILE.is_file()
    escena_ok = ESCENA_CANONICA_VISOR.is_file()

    copia_dir = VISOR_HERRAMIENTAS_DIR / "CopiaDeSeguridad"
    zip_godot = (copia_dir / "constructor_godot.zip").is_file()
    zip_mundo = (copia_dir / "actualizacion_v2.8.4.zip").is_file()

    return {
        "csproj_existe": csproj_ok,
        "godot_proy_existe": godot_ok,
        "escena_fijada_existe": escena_ok,
        "zip_godot_existe": zip_godot,
        "zip_mundo_existe": zip_mundo,
    }


def verificar_centralizacion_dev() -> Dict[str, Any]:
    """Comprueba que los artefactos de desarrollo (.github, pytest.ini, etc.) residan en .dev."""
    workflows = list(DEV_GITHUB_WORKFLOWS_DIR.glob("*.yml")) if DEV_GITHUB_WORKFLOWS_DIR.is_dir() else []
    return {
        "dev_dir_existe": DEV_DIR.is_dir(),
        "python_315_existe": PYTHON_EXE.is_file(),
        "github_workflows_existe": DEV_GITHUB_WORKFLOWS_DIR.is_dir() and len(workflows) > 0,
        "total_workflows_dev": len(workflows),
        "vscode_config_existe": (VSCODE_DIR / "settings.json").is_file(),
        "pytest_ini_existe": DEV_PYTEST_INI.is_file(),
    }


def comprobar_todas_dependencias() -> Dict[str, Any]:
    """Genera un informe integral del estado de todas las dependencias del ecosistema."""
    return {
        "dotnet": verificar_dotnet_sdk(),
        "dlls_nativas": verificar_dlls_nativas(),
        "python": verificar_paquetes_python(),
        "centralizacion_dev": verificar_centralizacion_dev(),
        "recursos_visor": verificar_recursos_visor(),
    }


def formatear_informe_dependencias() -> str:
    """Genera texto formateado para la consola con el estado de dependencias."""
    datos = comprobar_todas_dependencias()
    lineas = [
        "=" * 76,
        "  VERIFICACIÓN DE DEPENDENCIAS DEL ECOSISTEMA (.dev)",
        "=" * 76,
    ]

    # 1. .NET SDK
    dn = datos["dotnet"]
    st_dn = "[OK]" if dn.get("disponible") and dn.get("compatible") else "[FALTA]"
    lineas.append(f"\n--- [1] COMPILADOR .NET ---")
    lineas.append(f"  {st_dn:<8} .NET SDK Versión: {dn['version']} ({dn.get('ruta', 'N/A')})")

    # 2. DLLs Criptográficas Nativas
    lineas.append(f"\n--- [2] BIBLIOTECAS CRIPTOGRÁFICAS NATIVAS (Zero Trust) ---")
    for dll in datos["dlls_nativas"]:
        st = "[OK]" if dll["disponible"] else "[FALTA]"
        lineas.append(f"  {st:<8} {dll['nombre']:<16} -> {dll['descripcion']}")

    # 3. Python (.dev/.python Python 3.15+)
    py = datos["python"]
    py_dev = py["python_dev"]
    st_py_dev = "[OK]" if py_dev["disponible"] and py_dev["es_python_315"] else ("[AVISO]" if py_dev["disponible"] else "[FALTA]")
    lineas.append(f"\n--- [3] ENTORNO PYTHON CANÓNICO (.dev/.python) ---")
    lineas.append(f"  {st_py_dev:<8} Python canónico .dev : {py_dev['version']} ({py_dev['ruta']})")
    lineas.append(f"  Intérprete actual proceso : {py['interprete_actual']}")
    lineas.append(f"  Aislado en .dev           : {'Sí' if py['es_local_dev'] else 'No (sistema host)'}")
    for mod, ok in py["modulos"].items():
        st = "[OK]" if ok else "[FALTA]"
        lineas.append(f"  {st:<8} Módulo: {mod}")

    # 4. Centralización en .dev
    cd = datos["centralizacion_dev"]
    st_gh = "[OK]" if cd["github_workflows_existe"] else "[FALTA]"
    lineas.append(f"\n--- [4] ORGANIZACIÓN MODULAR Y CENTRALIZACIÓN (.dev) ---")
    lineas.append(f"  {st_gh:<8} Workflows GitHub (.dev/.github) : {cd['total_workflows_dev']} archivos .yml centralizados")
    lineas.append(f"  {'[OK]' if cd['pytest_ini_existe'] else '[FALTA]':<8} Config Pytest (.dev/pytest.ini)")
    lineas.append(f"  {'[OK]' if cd['vscode_config_existe'] else '[FALTA]':<8} Config VSCode (.dev/.vscode)")

    # 5. Recursos del Visor
    rc = datos["recursos_visor"]
    lineas.append(f"\n--- [5] RECURSOS DE CONSTRUCCIÓN VISOR 3D ---")
    lineas.append(f"  {'[OK]' if rc['csproj_existe'] else '[FALTA]':<8} Proyecto C# Visor3D.csproj")
    lineas.append(f"  {'[OK]' if rc['godot_proy_existe'] else '[FALTA]':<8} Proyecto Godot 3D project.godot")
    lineas.append(f"  {'[OK]' if rc['escena_fijada_existe'] else '[FALTA]':<8} Escena Principal res://WoldVirtual3DP2P.tscn")
    lineas.append(f"  {'[OK]' if rc['zip_godot_existe'] else '[AVISO]':<8} Paquete constructor_godot.zip")
    lineas.append(f"  {'[OK]' if rc['zip_mundo_existe'] else '[AVISO]':<8} Paquete actualizacion_v2.8.4.zip")

    lineas.append("\n" + "=" * 76)
    return "\n".join(lineas)
