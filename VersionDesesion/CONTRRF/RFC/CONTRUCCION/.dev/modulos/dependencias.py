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
    GODOT_PROJECT_FILE,
    PYTHON_EXE,
    REPO_ROOT,
    VENV_PYTHON,
    VISOR_CSPROJ,
    VISOR_HERRAMIENTAS_DIR,
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
        "modulos": estado_modulos,
    }


def verificar_recursos_visor() -> Dict[str, Any]:
    """Comprueba recursos requeridos para compilar y empaquetar el Visor 3D."""
    csproj_ok = VISOR_CSPROJ.is_file()
    godot_ok = GODOT_PROJECT_FILE.is_file()

    copia_dir = VISOR_HERRAMIENTAS_DIR / "CopiaDeSeguridad"
    zip_godot = (copia_dir / "constructor_godot.zip").is_file()
    zip_mundo = (copia_dir / "actualizacion_v2.8.4.zip").is_file()

    return {
        "csproj_existe": csproj_ok,
        "godot_proy_existe": godot_ok,
        "zip_godot_existe": zip_godot,
        "zip_mundo_existe": zip_mundo,
    }


def comprobar_todas_dependencias() -> Dict[str, Any]:
    """Genera un informe integral del estado de todas las dependencias del ecosistema."""
    return {
        "dotnet": verificar_dotnet_sdk(),
        "dlls_nativas": verificar_dlls_nativas(),
        "python": verificar_paquetes_python(),
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

    # 3. Python
    py = datos["python"]
    lineas.append(f"\n--- [3] ENTORNO PYTHON ---")
    lineas.append(f"  Intérprete actual: {py['interprete_actual']}")
    lineas.append(f"  Aislado en .dev  : {'Sí' if py['es_local_dev'] else 'No (sistema host)'}")
    for mod, ok in py["modulos"].items():
        st = "[OK]" if ok else "[FALTA]"
        lineas.append(f"  {st:<8} Módulo: {mod}")

    # 4. Recursos del Visor
    rc = datos["recursos_visor"]
    lineas.append(f"\n--- [4] RECURSOS DE CONSTRUCCIÓN VISOR 3D ---")
    lineas.append(f"  {'[OK]' if rc['csproj_existe'] else '[FALTA]':<8} Proyecto C# Visor3D.csproj")
    lineas.append(f"  {'[OK]' if rc['godot_proy_existe'] else '[FALTA]':<8} Proyecto Godot 3D project.godot")
    lineas.append(f"  {'[OK]' if rc['zip_godot_existe'] else '[AVISO]':<8} Paquete constructor_godot.zip")
    lineas.append(f"  {'[OK]' if rc['zip_mundo_existe'] else '[AVISO]':<8} Paquete actualizacion_v2.8.4.zip")

    lineas.append("\n" + "=" * 76)
    return "\n".join(lineas)
