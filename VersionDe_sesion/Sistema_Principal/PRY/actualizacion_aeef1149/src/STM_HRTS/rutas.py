"""Registro canonico de rutas del sistema WoldVirtualP2P3D.

Un unico modulo resuelve donde vive cada pieza del arbol: paquetes Python,
proyecto Godot, visor C#, documentacion, herramientas de STM_HRTS/utils y
artefactos runtime de STM_CH. Ningun otro modulo debe reconstruir estas rutas
con `Path(__file__).parent...`.

Las rutas se calculan desde este fichero, asi que el arbol se puede mover o
clonar sin editar codigo.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# ------------------------------------------------------------------ raices

STM_HRTS_DIR: Path = Path(__file__).resolve().parent
SRC_DIR: Path = STM_HRTS_DIR.parent
TLLDCD_DIR: Path = SRC_DIR.parent
CONTRRF_DIR: Path = TLLDCD_DIR.parent
VERSION_DIR: Path = CONTRRF_DIR.parent
REPO_DIR: Path = VERSION_DIR.parent

# --------------------------------------------------------------- paquetes

PAQUETE_IA: Path = SRC_DIR / "STM_IA"
CONOCIMIENTO_DIR: Path = PAQUETE_IA / "conocimiento"
IALOCAL_DIR: Path = PAQUETE_IA / "modelosIAlocal" / "IALOCAL"
PAQUETE_JSON: Path = SRC_DIR / "STM_JSON"
PAQUETE_CH: Path = SRC_DIR / "STM_CH"
PAQUETE_BKCH: Path = SRC_DIR / "STM_BKCH"
PAQUETE_SGR: Path = SRC_DIR / "STM_SGR"
PAQUETE_SBSTM: Path = SRC_DIR / "SBSTM"
PAQUETE_GENERAL: Path = SRC_DIR / "STMGNRL"

# ------------------------------------------------------------------ godot

GODOT_DIR: Path = SRC_DIR / "MTBGT" / "WoldVirtualP2P3D"
GODOT_PROJECT: Path = GODOT_DIR / "project.godot"
GODOT_SCRIPTS: Path = GODOT_DIR / "gdscrip"
GODOT_SHADERS: Path = GODOT_DIR / "gdshader"
GODOT_SCENES: Path = GODOT_DIR / "ESCENAS"
GODOT_EXPORT_PRESETS: Path = GODOT_DIR / "export_presets.cfg"
GODOT_AVATARES: Path = GODOT_DIR / "avtrnCRS"
GODOT_MODELOS: Path = GODOT_DIR / "gltfimport"

# -------------------------------------------------------------------- visor

VSC_DIR: Path = SRC_DIR / "VSC#"
CSPROJ: Path = VSC_DIR / "Visor3D.csproj"
PCK_EMBEBIDO: Path = VSC_DIR / "wvp3d.pck"
GODOT_EXE_ZIP: Path = VSC_DIR / "godot_exe.zip"

# ---------------------------------------------------------------- documentos

DOCS_DIR: Path = SRC_DIR / "STM_DOC"
DOCS_IMG: Path = DOCS_DIR / "docs" / "img"
DOCS_REGLAS: Path = DOCS_DIR / "REGLAS_DE_ACTUALIZACION.md"

# ------------------------------------------------------------ pruebas python

TESTS_DIR: Path = SRC_DIR / "tests"
# pytest.ini y su cache viven en STM_HRTS (no en la raiz de src)
PYTEST_INI: Path = STM_HRTS_DIR / "pytest.ini"
PYTEST_CACHE: Path = STM_HRTS_DIR / ".pytest_cache"

# ---------------------------------------------------- herramientas y runtime

HERRAMIENTAS_DIR: Path = STM_HRTS_DIR / "utils"
STM_CH_DIR: Path = PAQUETE_CH
PYCACHE_DIR: Path = STM_CH_DIR / "pycache"
PSNRL_DIR: Path = STM_CH_DIR / "PSNRL"
LEDGER_PATH: Path = STM_CH_DIR / "blockchain_ledger.json"
CACHE_IAFREE: Path = STM_CH_DIR / "openrouter_free_cache.json"
RUFF_CACHE_CANON: Path = STM_HRTS_DIR / ".ruff_cache"

# Raices compartidas con el resto de paquetes: se publican como ruta de verdad
# para que STM_CH/rutas.py no vuelva a calcularlas.
RAICES: Dict[str, Path] = {
    "repo": REPO_DIR,
    "version": VERSION_DIR,
    "contrrf": CONTRRF_DIR,
    "tlldcd": TLLDCD_DIR,
    "src": SRC_DIR,
}


def _candidatos_godot() -> Iterable[Path]:
    var = os.environ.get("GODOT_BIN", "").strip()
    if var:
        yield Path(var)
    en_path = shutil.which("godot") or shutil.which("godot4")
    if en_path:
        yield Path(en_path)
    escritorio = Path.home() / "Desktop"
    if escritorio.is_dir():
        for patron in ("Godot_v*-stable_win64_console.exe", "Godot_v*-stable_win64.exe"):
            yield from sorted(escritorio.glob(patron), reverse=True)
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        runtime_dir = Path(local_appdata) / "WoldVirtualP2P3D" / "runtime"
        if runtime_dir.is_dir():
            for g in sorted(runtime_dir.glob("*/Servidor3D/Godot_v*.exe"), reverse=True):
                yield g


def binario_godot() -> Optional[Path]:
    """Ejecutable de Godot 4. `GODOT_BIN` tiene prioridad sobre el resto."""
    for candidato in _candidatos_godot():
        if candidato.is_file():
            return candidato
    return None


def binario_dotnet() -> Optional[Path]:
    """SDK de .NET. `DOTNET_BIN` tiene prioridad sobre el resto."""
    var = os.environ.get("DOTNET_BIN", "").strip()
    if var and Path(var).is_file():
        return Path(var)
    en_path = shutil.which("dotnet")
    if en_path:
        return Path(en_path)
    for candidato in (Path("E:/Program Files/dotnet/dotnet.exe"),
                      Path("C:/Program Files/dotnet/dotnet.exe")):
        if candidato.is_file():
            return candidato
    return None


# Rutas que deben existir para que el arbol sea exportable y publicable.
RUTAS_CLAVE: tuple[tuple[str, Path], ...] = (
    ("src", SRC_DIR),
    ("proyecto Godot", GODOT_PROJECT),
    ("scripts Godot", GODOT_SCRIPTS),
    ("escenas Godot", GODOT_SCENES),
    ("shaders Godot", GODOT_SHADERS),
    ("preset de exportacion", GODOT_EXPORT_PRESETS),
    ("visor C#", CSPROJ),
    ("documentacion", DOCS_DIR),
    ("reglas de actualizacion", DOCS_REGLAS),
    ("herramientas", HERRAMIENTAS_DIR),
    ("pruebas Python", TESTS_DIR),
    ("config pytest", PYTEST_INI),
    ("conocimiento IA", CONOCIMIENTO_DIR),
)


def verificar(extra: Iterable[tuple[str, Path]] = ()) -> List[Dict[str, Any]]:
    """Comprueba las rutas clave y las `extra`. Devuelve un informe por ruta."""
    informe: List[Dict[str, Any]] = []
    for nombre, ruta in (*RUTAS_CLAVE, *extra):
        informe.append({"nombre": nombre, "ruta": str(ruta), "existe": ruta.exists()})
    return informe


def faltantes(informe: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [fila for fila in informe if not fila["existe"]]


def como_diccionario() -> Dict[str, str]:
    """Vista serializable de las rutas clave (para CLI y pruebas)."""
    return {nombre: str(ruta) for nombre, ruta in RUTAS_CLAVE}


def python_actual() -> Path:
    return Path(sys.executable)
