"""Sincronizador automatico de rutas de WoldVirtualP2P3D.

Cuando el arbol se mueve, se reorganiza o se actualiza, este modulo
relee ``rutas.py``, detecta que rutas clave han dejado de existir y
busca sus candidatos reales dentro de ``SRC_DIR``.  Si encuentra una
coincidencia unica, parchea ``rutas.py`` en el sitio, hace una copia
de seguridad previa y registra el cambio en un log JSON.

Uso desde Python:
    from STM_HRTS.utils.add_utils.sincronizar_rutas import sincronizar
    resultado = sincronizar()

Uso desde la consola (via __main__):
    python -m STM_HRTS sincronizar
    python -m STM_HRTS sincronizar --dry-run
    python -m STM_HRTS sincronizar --json
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ancla: src/ se resuelve desde la posicion de este fichero
# ---------------------------------------------------------------------------

_ADD_UTILS_DIR: Path = Path(__file__).resolve().parent
_SRC_DIR: Path = _ADD_UTILS_DIR.parents[2]        # add_utils -> utils -> STM_HRTS -> src
_RUTAS_PY: Path = _ADD_UTILS_DIR / "rutas.py"
_LOG_PATH: Path = _ADD_UTILS_DIR / "sincronizar_rutas.log.json"

# ---------------------------------------------------------------------------
# Tabla de busqueda: variable -> (nombre legible, nombre del objetivo, es_dir)
#
# Para cada constante de rutas.py que apunta a algo buscable por nombre,
# indicamos:
#   - var_name   : nombre exacto de la constante en rutas.py
#   - label      : descripcion humana
#   - objetivo   : nombre del archivo o directorio que buscamos
#   - es_dir     : True si es carpeta, False si es fichero
#   - retornar_padre: si True, se devuelve el directorio padre del fichero
#                     encontrado (util para GODOT_DIR que se deduce de project.godot)
# ---------------------------------------------------------------------------

BUSCABLES: List[Dict[str, Any]] = [
    # --- Godot ---
    dict(var="GODOT_DIR",           label="directorio Godot",         objetivo="project.godot",              es_dir=False, retornar_padre=True),
    dict(var="GODOT_SCRIPTS",       label="scripts GDScript",          objetivo="gdscrip",                    es_dir=True),
    dict(var="GODOT_SHADERS",       label="shaders Godot",             objetivo="gdshader",                   es_dir=True),
    dict(var="GODOT_SCENES",        label="escenas Godot",             objetivo="ESCENAS",                    es_dir=True),
    dict(var="GODOT_EXPORT_PRESETS",label="preset exportacion",        objetivo="export_presets.cfg",         es_dir=False),
    dict(var="GODOT_AVATARES",      label="avatares",                  objetivo="avtrnCRS",                   es_dir=True),
    dict(var="GODOT_MODELOS",       label="modelos gltf",              objetivo="gltfimport",                 es_dir=True),
    # --- Visor C# ---
    dict(var="CSPROJ",              label="proyecto Visor3D C#",       objetivo="Visor3D.csproj",             es_dir=False),
    # --- Documentos ---
    dict(var="DOCS_DIR",            label="directorio documentacion",  objetivo="STM_DOC",                    es_dir=True),
    dict(var="DOCS_REGLAS",         label="reglas de actualizacion",   objetivo="REGLAS_DE_ACTUALIZACION.md", es_dir=False),
    # --- Tests ---
    dict(var="TESTS_DIR",           label="directorio de tests",       objetivo="tests",                      es_dir=True),
    # --- Paquetes Python ---
    dict(var="PAQUETE_IA",          label="paquete STM_IA",            objetivo="STM_IA",                     es_dir=True),
    dict(var="CONOCIMIENTO_DIR",    label="conocimiento IA",           objetivo="conocimiento",               es_dir=True),
    dict(var="PAQUETE_CH",          label="paquete STM_CH",            objetivo="STM_CH",                     es_dir=True),
    dict(var="PAQUETE_BKCH",        label="paquete STM_BKCH",         objetivo="STM_BKCH",                   es_dir=True),
    dict(var="PAQUETE_SGR",         label="paquete STM_SGR",           objetivo="STM_SGR",                    es_dir=True),
    dict(var="PAQUETE_SBSTM",       label="paquete SBSTM",             objetivo="SBSTM",                      es_dir=True),
    dict(var="PAQUETE_GENERAL",     label="paquete STMGNRL",           objetivo="STMGNRL",                    es_dir=True),
    dict(var="PAQUETE_JSON",        label="paquete STM_JSON",          objetivo="STM_JSON",                   es_dir=True),
]

# Profundidad maxima de busqueda en SRC_DIR (evita recorrer node_modules, etc.)
_MAX_DEPTH: int = 8

# Carpetas que nunca deben aparecer como resultado
_EXCLUIR_DIRS: frozenset = frozenset({
    "__pycache__", ".git", ".ruff_cache", ".pytest_cache",
    "node_modules", ".venv", "venv", "LC_STM",
})


# ---------------------------------------------------------------------------
# Lectura y escritura de rutas.py
# ---------------------------------------------------------------------------

def _leer_rutas_py() -> str:
    return _RUTAS_PY.read_text(encoding="utf-8")


def _ruta_actual_en_codigo(codigo: str, var: str) -> Optional[str]:
    """Extrae el valor literal de una asignacion 'VAR: Path = ...' en rutas.py."""
    patron = rf'^\s*{re.escape(var)}\s*:\s*Path\s*=\s*(.+)$'
    m = re.search(patron, codigo, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip()


def _sustituir_en_codigo(codigo: str, var: str, nueva_expr: str) -> str:
    """Reemplaza la expresion de la asignacion de `var` en rutas.py."""
    patron = rf'^(\s*{re.escape(var)}\s*:\s*Path\s*=\s*)(.+)$'
    nuevo = re.sub(patron, rf'\g<1>{nueva_expr}', codigo, flags=re.MULTILINE)
    return nuevo


# ---------------------------------------------------------------------------
# Busqueda de candidatos
# ---------------------------------------------------------------------------

def _ruta_relativa_a_src(ruta: Path) -> str:
    """Devuelve la ruta relativa a SRC_DIR como expresion Python para rutas.py."""
    try:
        partes = ruta.relative_to(_SRC_DIR).parts
    except ValueError:
        return f'Path(r"{ruta}")'
    # Construimos: SRC_DIR / "a" / "b" / ...
    if not partes:
        return "SRC_DIR"
    encadenado = " / ".join(f'"{p}"' for p in partes)
    return f"SRC_DIR / {encadenado}"


def _buscar_candidatos(objetivo: str, es_dir: bool) -> List[Path]:
    """Busca `objetivo` (nombre exacto) en SRC_DIR hasta _MAX_DEPTH niveles."""
    candidatos: List[Path] = []

    def _recorrer(carpeta: Path, profundidad: int) -> None:
        if profundidad > _MAX_DEPTH:
            return
        try:
            for hijo in carpeta.iterdir():
                if hijo.name in _EXCLUIR_DIRS:
                    continue
                if hijo.name == objetivo:
                    if es_dir and hijo.is_dir():
                        candidatos.append(hijo)
                    elif not es_dir and hijo.is_file():
                        candidatos.append(hijo)
                if hijo.is_dir() and not hijo.is_symlink():
                    _recorrer(hijo, profundidad + 1)
        except PermissionError:
            pass

    _recorrer(_SRC_DIR, 0)
    return candidatos


# ---------------------------------------------------------------------------
# Resolucion de conflictos entre candidatos
# ---------------------------------------------------------------------------

def _mejor_candidato(candidatos: List[Path], var: str) -> Optional[Path]:
    """Heuristica para elegir el mejor candidato cuando hay varios.

    Prioridad:
      1. El que esta directamente bajo SRC_DIR (profundidad 1).
      2. El de menor profundidad relativa.
      3. Si hay empate, el primero en orden lexicografico.
    """
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0]

    def _profundidad(p: Path) -> int:
        try:
            return len(p.relative_to(_SRC_DIR).parts)
        except ValueError:
            return 999

    return sorted(candidatos, key=lambda p: (_profundidad(p), str(p)))[0]


# ---------------------------------------------------------------------------
# Nucleo: detectar y corregir
# ---------------------------------------------------------------------------

def _evaluar_ruta_actual(var: str) -> Optional[Path]:
    """Importa rutas y devuelve el valor actual de `var` como Path."""
    # Refresca el modulo para leer el estado real del fichero
    if "STM_HRTS.utils.add_utils.rutas" in sys.modules:
        import importlib
        mod = importlib.reload(sys.modules["STM_HRTS.utils.add_utils.rutas"])
    else:
        import importlib
        if str(_SRC_DIR) not in sys.path:
            sys.path.insert(0, str(_SRC_DIR))
        mod = importlib.import_module("STM_HRTS.utils.add_utils.rutas")
    return getattr(mod, var, None)


class ResultadoSincronizacion:
    """Resultado detallado de una operacion de sincronizacion."""

    def __init__(self) -> None:
        self.timestamp: str = datetime.now(timezone.utc).isoformat()
        self.dry_run: bool = False
        self.ok_sin_cambios: List[str] = []
        self.corregidas: List[Dict[str, str]] = []
        self.sin_candidato: List[Dict[str, str]] = []
        self.ambiguas: List[Dict[str, Any]] = []
        self.errores: List[Dict[str, str]] = []
        self.backup: Optional[str] = None

    # --- consultas ---

    @property
    def hubo_cambios(self) -> bool:
        return bool(self.corregidas)

    @property
    def hay_problemas(self) -> bool:
        return bool(self.sin_candidato or self.ambiguas or self.errores)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "dry_run": self.dry_run,
            "backup": self.backup,
            "ok_sin_cambios": self.ok_sin_cambios,
            "corregidas": self.corregidas,
            "sin_candidato": self.sin_candidato,
            "ambiguas": self.ambiguas,
            "errores": self.errores,
        }


def sincronizar(dry_run: bool = False) -> ResultadoSincronizacion:
    """Detecta y corrige rutas desactualizadas en ``rutas.py``.

    Args:
        dry_run: si es True, calcula los cambios pero no escribe nada.

    Returns:
        ResultadoSincronizacion con el detalle completo.
    """
    resultado = ResultadoSincronizacion()
    resultado.dry_run = dry_run

    codigo_original = _leer_rutas_py()
    codigo = codigo_original

    for entrada in BUSCABLES:
        var: str = entrada["var"]
        label: str = entrada["label"]
        objetivo: str = entrada["objetivo"]
        es_dir: bool = entrada["es_dir"]
        retornar_padre: bool = entrada.get("retornar_padre", False)

        # 1. Evaluar ruta actual
        try:
            ruta_actual: Optional[Path] = _evaluar_ruta_actual(var)
        except Exception as exc:
            resultado.errores.append({"var": var, "label": label, "error": str(exc)})
            continue

        if ruta_actual is None:
            resultado.errores.append({"var": var, "label": label, "error": "variable no encontrada en modulo"})
            continue

        # 2. ¿Ya existe? -> sin cambios
        if ruta_actual.exists():
            resultado.ok_sin_cambios.append(var)
            continue

        # 3. Buscar candidatos
        candidatos = _buscar_candidatos(objetivo, es_dir=not retornar_padre if retornar_padre else es_dir)
        if retornar_padre:
            # Queremos el directorio padre del fichero encontrado
            candidatos = [c.parent for c in candidatos]
            # Deduplicar
            vistos: set = set()
            unicos: List[Path] = []
            for c in candidatos:
                if c not in vistos:
                    vistos.add(c)
                    unicos.append(c)
            candidatos = unicos

        if not candidatos:
            resultado.sin_candidato.append({
                "var": var, "label": label,
                "ruta_actual": str(ruta_actual),
                "buscado": objetivo,
            })
            continue

        if len(candidatos) > 1:
            mejor = _mejor_candidato(candidatos, var)
            resultado.ambiguas.append({
                "var": var, "label": label,
                "ruta_actual": str(ruta_actual),
                "candidatos": [str(c) for c in candidatos],
                "elegido": str(mejor),
            })
            if mejor is None:
                continue
            candidato = mejor
        else:
            candidato = candidatos[0]

        # 4. Construir nueva expresion
        nueva_expr = _ruta_relativa_a_src(candidato)

        # 5. Parchar el codigo
        codigo_nuevo = _sustituir_en_codigo(codigo, var, nueva_expr)
        if codigo_nuevo == codigo:
            resultado.errores.append({
                "var": var, "label": label,
                "error": "no se pudo localizar la asignacion en rutas.py para parchear",
            })
            continue

        resultado.corregidas.append({
            "var": var, "label": label,
            "antes": str(ruta_actual),
            "despues": str(candidato),
            "nueva_expr": nueva_expr,
        })
        codigo = codigo_nuevo

    # 6. Escribir si hubo cambios y no es dry-run
    if resultado.hubo_cambios and not dry_run:
        # Backup
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = _RUTAS_PY.with_suffix(f".bak_{ts}.py")
        shutil.copy2(_RUTAS_PY, backup_path)
        resultado.backup = str(backup_path)
        # Escribir
        _RUTAS_PY.write_text(codigo, encoding="utf-8")
        # Log
        _guardar_log(resultado)

    return resultado


def _guardar_log(resultado: ResultadoSincronizacion) -> None:
    """Acumula entradas en el log JSON (ultimas 50 ejecuciones)."""
    entradas: List[Dict[str, Any]] = []
    if _LOG_PATH.exists():
        try:
            entradas = json.loads(_LOG_PATH.read_text(encoding="utf-8"))
            if not isinstance(entradas, list):
                entradas = []
        except Exception:
            entradas = []
    entradas.append(resultado.as_dict())
    entradas = entradas[-50:]  # mantener solo las ultimas 50
    _LOG_PATH.write_text(json.dumps(entradas, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# API de alto nivel para uso externo
# ---------------------------------------------------------------------------

def verificar_y_reportar() -> Tuple[bool, str]:
    """Version rapida: solo verifica sin modificar nada.

    Returns:
        (todo_ok: bool, resumen: str)
    """
    from . import rutas  # noqa: PLC0415
    informe = rutas.verificar()
    faltan = rutas.faltantes(informe)
    if not faltan:
        return True, f"OK: {len(informe)}/{len(informe)} rutas clave presentes."
    lineas = [f"FALTA ({len(faltan)}/{len(informe)}):"]
    for f in faltan:
        lineas.append(f"  - {f['nombre']}: {f['ruta']}")
    return False, "\n".join(lineas)
