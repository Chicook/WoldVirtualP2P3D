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
#
# Este fichero vive en STM_HRTS/utils/add_utils/rutas.py, dentro de su carpeta.
# Las raices se suben nivel a nivel desde aqui, de modo que el paquete puede
# permanecer anidado sin editar codigo ni duplicar rutas en otros modulos.
#
#   add_utils/rutas.py
#     add_utils/          <- ADD_UTILS_DIR (donde vive este paquete)
#       utils/            <- UTILS_DIR     (herramientas del taller)
#         STM_HRTS/       <- STM_HRTS_DIR
#           src/          <- SRC_DIR

ADD_UTILS_DIR: Path = Path(__file__).resolve().parent
UTILS_DIR: Path = ADD_UTILS_DIR.parent
STM_HRTS_DIR: Path = UTILS_DIR.parent
SRC_DIR: Path = STM_HRTS_DIR.parent
TLLDCD_DIR: Path = SRC_DIR.parent
CONTRRF_DIR: Path = TLLDCD_DIR.parent
VERSION_DIR: Path = CONTRRF_DIR.parent
REPO_DIR: Path = VERSION_DIR.parent

# --------------------------------------------------------------- paquetes

PAQUETE_IA: Path = SRC_DIR / "STM_IA"
CONOCIMIENTO_DIR: Path = PAQUETE_IA / "STM_Informacion" / "conocimiento"
IALOCAL_DIR: Path = PAQUETE_IA / "STM_Informacion" / "modelosIAlocal" / "IALOCAL"
PAQUETE_JSON: Path = SRC_DIR / "STM_JSON" / "STM_LC"
PAQUETE_CH: Path = SRC_DIR / "STM_CH" / "STM_herramientas"
PAQUETE_BKCH: Path = SRC_DIR / "STM_BKCH" / "stm_bkch1"
PAQUETE_SGR: Path = SRC_DIR / "STM_SGR" / "STM_CNX"
PAQUETE_SBSTM: Path = SRC_DIR / "SBSTM" / "SistemasLC"
PAQUETE_GENERAL: Path = SRC_DIR / "STMGNRL" / "SistemaGeneral"

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
DOCS_REGLAS: Path = SRC_DIR / "STM_DOC" / "Otros_documentos" / "REGLAS_DE_ACTUALIZACION.md"

# ------------------------------------------------------------ pruebas python

TESTS_DIR: Path = SRC_DIR / "tests"
# La config de pytest viaja con el paquete (utils/add_utils/pytest.ini) y su
# cache canonica vive dentro del propio paquete, en utils/add_utils/STM_HRTS/.
PYTEST_INI: Path = ADD_UTILS_DIR / "pytest.ini"
PYTEST_CACHE: Path = ADD_UTILS_DIR / "STM_HRTS" / ".pytest_cache"

# ---------------------------------------------------- herramientas y runtime

HERRAMIENTAS_DIR: Path = UTILS_DIR
STM_CH_DIR: Path = SRC_DIR / "STM_CH"
PYCACHE_DIR: Path = STM_CH_DIR / "pycache"
PSNRL_DIR: Path = STM_CH_DIR / "PSNRL"
LEDGER_PATH: Path = STM_CH_DIR / "blockchain_ledger.json"
CACHE_IAFREE: Path = STM_CH_DIR / "openrouter_free_cache.json"
RUFF_CACHE_CANON: Path = STM_HRTS_DIR / ".ruff_cache"

# ------------------------------------------------ fuente unica: Rutas.json
try:
    from STM_CH.STM_herramientas.rutas_json import (
        cargar as _cargar_rutas_json,
        resolver as _resolver_ruta_json,
    )
    _RUTAS_JSON = _cargar_rutas_json()
except Exception:  # noqa: BLE001 - el JSON es opcional, hay fallback calculado
    _RUTAS_JSON = {}


def _ruta_json(clave: str, por_defecto: Path) -> Path:
    """Lee una ruta de Rutas.json; si falta, conserva la calculada."""
    if not _RUTAS_JSON:
        return por_defecto
    try:
        return _resolver_ruta_json(clave, _RUTAS_JSON)
    except Exception:  # noqa: BLE001
        return por_defecto


PAQUETE_IA = _ruta_json("subsistemas.STM_IA.raiz", PAQUETE_IA)
CONOCIMIENTO_DIR = _ruta_json("subsistemas.STM_IA.secciones.conocimiento",
                              CONOCIMIENTO_DIR)
IALOCAL_DIR = _ruta_json("subsistemas.STM_IA.secciones.IALOCAL", IALOCAL_DIR)
PAQUETE_JSON = _ruta_json("subsistemas.STM_JSON.seccion", PAQUETE_JSON)
PAQUETE_CH = _ruta_json("subsistemas.STM_CH.seccion", PAQUETE_CH)
PAQUETE_BKCH = _ruta_json("subsistemas.STM_BKCH.seccion", PAQUETE_BKCH)
PAQUETE_SGR = _ruta_json("subsistemas.STM_SGR.seccion", PAQUETE_SGR)
PAQUETE_SBSTM = _ruta_json("subsistemas.SBSTM.seccion", PAQUETE_SBSTM)
PAQUETE_GENERAL = _ruta_json("subsistemas.STMGNRL.seccion", PAQUETE_GENERAL)
STM_CH_DIR = _ruta_json("subsistemas.STM_CH.raiz", STM_CH_DIR)
PYCACHE_DIR = _ruta_json("runtime.pycache", PYCACHE_DIR)
PSNRL_DIR = _ruta_json("runtime.psnrl", PSNRL_DIR)
LEDGER_PATH = _ruta_json("runtime.ledger", LEDGER_PATH)
CACHE_IAFREE = _ruta_json("runtime.cache_iafree", CACHE_IAFREE)

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
