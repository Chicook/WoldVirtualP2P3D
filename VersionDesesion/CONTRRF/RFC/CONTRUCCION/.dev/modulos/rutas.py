"""Módulo de Rutas Canónicas para WoldVirtualP2P3D (.dev)
Centraliza la resolución de rutas de todo el ecosistema:
- Raíz del repositorio, versión, CONTRRF, RFC, CONTRUCCION, .dev
- Intérpretes de Python (.dev/.python, .dev/venv)
- Módulos del taller (TLLDCD/src)
- Servidor Oficial Blockchain (STM_BKCH/stm_bkch1)
- Servidor de LucIA 3D (MTBGT/.../puente_3D)
- Visor 3D WPF C# (TLLDCD/src/VSC#/Visor3Ddesarrollo/HerraMientas)
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

# --- Directorios Principales de la Jerarquía ---
MODULOS_DIR: Path = Path(__file__).resolve().parent
DEV_DIR: Path = MODULOS_DIR.parent
CONTRUCCION_DIR: Path = DEV_DIR.parent
RFC_DIR: Path = CONTRUCCION_DIR.parent
CONTRRF_DIR: Path = RFC_DIR.parent
VERSION_DIR: Path = CONTRRF_DIR.parent
REPO_ROOT: Path = VERSION_DIR.parent

# --- Subdirectorios de .dev ---
PYTHON_DIR: Path = DEV_DIR / ".python"
PYTHON_EXE: Path = PYTHON_DIR / "python.exe"
PYTHONW_EXE: Path = PYTHON_DIR / "pythonw.exe"

VENV_DIR: Path = DEV_DIR / "venv"
VENV_PYTHON: Path = VENV_DIR / "Scripts" / "python.exe"
VENV_PYTHONW: Path = VENV_DIR / "Scripts" / "pythonw.exe"

PYTEST_CACHE_DIR: Path = DEV_DIR / ".pytest_cache"
RUFF_CACHE_DIR: Path = DEV_DIR / ".ruff_cache"
PYCACHE_DIR: Path = DEV_DIR / "pycache"
IPFS_DIR: Path = DEV_DIR / ".ipfs"
VSCODE_DIR: Path = DEV_DIR / ".vscode"
DEV_PYTEST_INI: Path = DEV_DIR / "pytest.ini"
DEV_GITHUB_DIR: Path = DEV_DIR / ".github"
DEV_GITHUB_WORKFLOWS_DIR: Path = DEV_GITHUB_DIR / "workflows"
REPO_GITHUB_DIR: Path = REPO_ROOT / ".github"
REPO_GITHUB_WORKFLOWS_DIR: Path = REPO_GITHUB_DIR / "workflows"

# --- Taller y Código Fuente (TLLDCD) ---
TLLDCD_DIR: Path = CONTRUCCION_DIR / "TLLDCD"
TLLDCD_SRC: Path = TLLDCD_DIR / "src"
STM_RFC_DIR: Path = CONTRUCCION_DIR / "STM_RFC" / "STM_RFPRMN"
REFACTOR_DIR: Path = CONTRUCCION_DIR / "Refactorizacion"
LC_TRABAJANDO_DIR: Path = CONTRUCCION_DIR / "LCtrabajando"

# --- Sistema Principal y Archivo Legado ---
PRY_DIR: Path = VERSION_DIR / "SistemaPrincipal" / "PRY"
PRY_ARCHIVOS_DIR: Path = PRY_DIR / "Archivo" / "VersionesDeRefuerzo"

# --- Servidor Blockchain Oficial (STM_BKCH) ---
BLOCKCHAIN_DIR: Path = TLLDCD_SRC / "STM_BKCH" / "stm_bkch1"
BLOCKCHAIN_SCRIPT: Path = BLOCKCHAIN_DIR / "servidor_oficial.py"
LEDGER_PATH: Path = TLLDCD_SRC / "STM_CH" / "blockchain_ledger.json"
PSNRL_DIR: Path = TLLDCD_SRC / "STM_CH" / "PSNRL"

# --- Servidor LucIA 3D ---
LUCIA_DIR: Path = TLLDCD_SRC / "MTBGT" / "WoldVirtualP2P3D" / "lucia3D" / "GLTF_lucIA" / "celebro_3D" / "puente_3D"
LUCIA_SCRIPT: Path = LUCIA_DIR / "servidor_lucia.py"

# --- Proyecto Visor 3D (C# WPF) ---
VISOR_BASE_DIR: Path = TLLDCD_SRC / "VSC#" / "Visor3Ddesarrollo"
VISOR_HERRAMIENTAS_DIR: Path = VISOR_BASE_DIR / "HerraMientas"
VISOR_CSPROJ: Path = VISOR_HERRAMIENTAS_DIR / "Visor3D.csproj"
VISOR_OUTPUT_DLL: Path = VISOR_HERRAMIENTAS_DIR / "bin" / "Debug" / "net8.0-windows" / "win-x64" / "LCDMWoldVirtualP2P3Dv2.8.4.dll"
VISOR_OUTPUT_EXE: Path = VISOR_HERRAMIENTAS_DIR / "bin" / "Debug" / "net8.0-windows" / "win-x64" / "LCDMWoldVirtualP2P3Dv2.8.4.exe"

# Módulos de Seguridad y Sesión Única del Visor
SEGURIDAD_DIR: Path = VISOR_BASE_DIR / "Seguridad"
SEGURIDAD_SESION_UNICA_DIR: Path = SEGURIDAD_DIR / "SeguridadSesionUnica"
SMTPLC_DIR: Path = SEGURIDAD_DIR / "SMTPLC"

# Archivos de SeguridadSesionUnica
ARRANQUE_CUENTA_CS: Path = SEGURIDAD_SESION_UNICA_DIR / "ArranqueCuenta.cs"
MAQUINA_HUELLA_CS: Path = SEGURIDAD_SESION_UNICA_DIR / "MaquinaHuellaDigital.cs"
REGISTRO_PC_UNICO_CS: Path = SEGURIDAD_SESION_UNICA_DIR / "RegistroPcUnico.cs"
REINICIO_CUENTA_CS: Path = SEGURIDAD_SESION_UNICA_DIR / "ReinicioCuenta.cs"
SESION_UNICA_GUARDA_CS: Path = SEGURIDAD_SESION_UNICA_DIR / "SesionUnicaGuarda.cs"

# Scripts del Visor
LUCIA_BAT_VISOR: Path = VISOR_HERRAMIENTAS_DIR / "Iniciar_Lucia_Visor.bat"
LUCIA_PS1_VISOR: Path = VISOR_HERRAMIENTAS_DIR / "Iniciar_Lucia_Visor.ps1"
LANZAR_BAT: Path = VISOR_HERRAMIENTAS_DIR / "Lanzar.bat"

# Motor y Proyecto Godot
GODOT_PROY_DIR: Path = TLLDCD_SRC / "MTBGT" / "WoldVirtualP2P3D"
GODOT_PROJECT_FILE: Path = GODOT_PROY_DIR / "project.godot"
ESCENA_CANONICA_VISOR: Path = GODOT_PROY_DIR / "WoldVirtual3DP2P.tscn"
ESCENA_CANONICA_RES: str = "res://WoldVirtual3DP2P.tscn"
ESCENA_CANONICA_UID: str = "uid://5bh8su08n101"


# --- Localización de Herramientas del Sistema ---
def localizar_dotnet() -> Path | None:
    """Devuelve la ruta al ejecutable de dotnet aunque no esté en PATH.

    Solo consulta ubicaciones de instalación ya existentes; no crea ni mueve nada.
    """
    en_path = shutil.which("dotnet")
    if en_path:
        return Path(en_path)

    candidatos: list[Path] = []
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if base:
            candidatos.append(Path(base) / "dotnet" / "dotnet.exe")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidatos.append(Path(local) / "Microsoft" / "dotnet" / "dotnet.exe")

    # dotnet puede estar instalado en una unidad distinta a la del sistema
    # (p. ej. E:\\Program Files\\dotnet en este equipo).
    for unidad in ("C", "D", "E", "F", "G", "H"):
        candidatos.append(Path(f"{unidad}:/Program Files/dotnet/dotnet.exe"))

    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    return None


# --- Control de Fronteras y Contención de Rutas ---
def asegurar_ruta_en_repositorio(ruta: Path | str) -> bool:
    """Verifica de forma estricta que una ruta resuelva dentro de REPO_ROOT (E:\\WoldVirtualP2P3D).
    Evita path traversal o escapes fuera de la jerarquía canónica."""
    try:
        p = Path(ruta).resolve()
        return p == REPO_ROOT or REPO_ROOT in p.parents
    except Exception:
        return False


def validar_frontera_carpetas() -> tuple[bool, list[str]]:
    """Comprueba que todos los directorios canónicos del ecosistema permanezcan estrictamente
    dentro de la jerarquía de REPO_ROOT, sin referencias que salgan a otras unidades o carpetas."""
    rutas_a_validar = [
        ("VERSION_DIR", VERSION_DIR),
        ("CONTRRF_DIR", CONTRRF_DIR),
        ("RFC_DIR", RFC_DIR),
        ("CONTRUCCION_DIR", CONTRUCCION_DIR),
        ("DEV_DIR", DEV_DIR),
        ("PYTHON_DIR", PYTHON_DIR),
        ("VENV_DIR", VENV_DIR),
        ("TLLDCD_DIR", TLLDCD_DIR),
        ("TLLDCD_SRC", TLLDCD_SRC),
        ("BLOCKCHAIN_DIR", BLOCKCHAIN_DIR),
        ("LUCIA_DIR", LUCIA_DIR),
        ("VISOR_BASE_DIR", VISOR_BASE_DIR),
        ("VISOR_HERRAMIENTAS_DIR", VISOR_HERRAMIENTAS_DIR),
        ("SEGURIDAD_DIR", SEGURIDAD_DIR),
        ("SEGURIDAD_SESION_UNICA_DIR", SEGURIDAD_SESION_UNICA_DIR),
        ("GODOT_PROY_DIR", GODOT_PROY_DIR),
    ]

    errores = []
    for nombre, ruta in rutas_a_validar:
        if not asegurar_ruta_en_repositorio(ruta):
            errores.append(f"VIOLACIÓN DE FRONTERA: {nombre} ({ruta}) se resuelve fuera de {REPO_ROOT}")

    return len(errores) == 0, errores

