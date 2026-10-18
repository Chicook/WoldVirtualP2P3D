"""Submodulo stm_base de RFPRMN (refactor: tope 400/450 lineas).

Estilo de terminal, constantes, errores, mensajes y localización de la
raíz del proyecto. Sin dependencias internas: es la base del paquete.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

__version__ = "2.0.0"

# --- Estilo de terminal ------------------------------------------------------

_COLOR_ACTIVO = sys.stdout.isatty() and "NO_COLOR" not in os.environ


class Estilo:
    """Códigos ANSI usados para dar formato a la salida en terminal.

    Se desactivan automáticamente si la salida no es una terminal interactiva
    o si la variable de entorno ``NO_COLOR`` está definida.
    """

    _CODIGOS = {
        "reset": "0", "negrita": "1", "tenue": "2",
        "cian": "36", "verde": "32", "amarillo": "33",
        "rojo": "31", "magenta": "35", "azul": "34",
    }

    def __getattr__(self, nombre: str) -> str:
        if not _COLOR_ACTIVO:
            return ""
        return f"\033[{self._CODIGOS[nombre]}m"


E = Estilo()
ANCHO_TERMINAL = shutil.get_terminal_size(fallback=(80, 24)).columns


def _caja(titulo: str, filas: list[tuple[str, str]], color: str = "cian") -> str:
    """Dibuja una caja con bordes Unicode a partir de pares (etiqueta, texto)."""
    ancho_etiqueta = max((len(etiqueta) for etiqueta, _ in filas), default=0)
    ancho_interior = min(
        max(len(titulo), *(ancho_etiqueta + 3 + len(texto) for etiqueta, texto in filas)) + 2,
        ANCHO_TERMINAL - 2,
    )
    col = getattr(E, color)
    linea_top = f"{col}╭{'─' * ancho_interior}╮{E.reset}"
    linea_titulo = f"{col}│{E.reset} {E.negrita}{titulo.ljust(ancho_interior - 1)}{E.reset}{col}│{E.reset}"
    linea_sep = f"{col}├{'─' * ancho_interior}┤{E.reset}"
    linea_bottom = f"{col}╰{'─' * ancho_interior}╯{E.reset}"

    cuerpo = []
    for etiqueta, texto in filas:
        contenido = f" {E.negrita}{etiqueta.ljust(ancho_etiqueta)}{E.reset}  {texto}"
        relleno = ancho_interior - (ancho_etiqueta + len(texto) + 3)
        cuerpo.append(f"{col}│{E.reset}{contenido}{' ' * max(relleno, 0)}{col}│{E.reset}")

    return "\n".join([linea_top, linea_titulo, linea_sep, *cuerpo, linea_bottom])


def _panel(titulo: str, texto: str, color: str = "magenta") -> str:
    """Dibuja un panel de ancho fijo con ``texto`` envuelto en párrafos."""
    ancho = min(ANCHO_TERMINAL - 4, 78)
    col = getattr(E, color)
    encabezado = f"{col}┌─ {E.negrita}{titulo}{E.reset}{col} {'─' * max(ancho - len(titulo) - 3, 0)}{E.reset}"
    cuerpo = "\n".join(
        f"{col}│{E.reset} {linea}" for linea in textwrap.wrap(texto, width=ancho) or [""]
    )
    pie = f"{col}└{'─' * (ancho + 2)}{E.reset}"
    return f"{encabezado}\n{cuerpo}\n{pie}"


# --- Constantes y configuración --------------------------------------------

#: Respuestas que se interpretan como una confirmación afirmativa.
RESPUESTAS_AFIRMATIVAS = frozenset({"s", "si", "sí", "y", "yes"})

#: Tamaño máximo (en bytes) admitido para el análisis local de un archivo.
LIMITE_TAMANO_ANALISIS = 2_000_000

#: Extensiones de archivo admitidas por ``comando_crear_archivo``.
EXTENSIONES_POR_LENGUAJE: dict[str, str] = {
    "python": ".py", "py": ".py",
    "csharp": ".cs", "cs": ".cs",
    "html": ".html",
    "css": ".css",
    "javascript": ".js", "js": ".js",
    "java": ".java",
    "cpp": ".cpp", "c++": ".cpp", "c": ".c",
    "php": ".php",
    "ruby": ".rb",
    "go": ".go",
    "rust": ".rs",
    "typescript": ".ts", "ts": ".ts",
    "sh": ".sh",
    "bat": ".bat",
}

#: Patrón usado para detectar marcadores TODO/FIXME en comentarios.
PATRON_MARCADOR_PENDIENTE = re.compile(r"(?i)(?:#|//|/\*)\s*(?:todo|fixme)\b")


class ErrorProyecto(Exception):
    """Error base para fallos controlados de esta herramienta."""


class RaizProyectoNoEncontrada(ErrorProyecto):
    """Se lanza cuando no puede localizarse la raíz del proyecto."""


def _imprimir_seguro(mensaje: str) -> None:
    """Print tolerante a consolas cp1252 (sustituye símbolos no representables)."""
    try:
        print(mensaje)
    except UnicodeEncodeError:
        print(mensaje.encode("ascii", "replace").decode("ascii"))


def informar(mensaje: str) -> None:
    """Muestra un mensaje informativo estándar."""
    _imprimir_seguro(f"{E.cian}›{E.reset} {mensaje}")


def exito(mensaje: str) -> None:
    """Muestra un mensaje de operación completada correctamente."""
    _imprimir_seguro(f"{E.verde}✔{E.reset} {mensaje}")


def advertir(mensaje: str) -> None:
    """Muestra una advertencia no bloqueante."""
    _imprimir_seguro(f"{E.amarillo}⚠{E.reset} {mensaje}")


def reportar_error(mensaje: str) -> None:
    """Muestra un error de operación al usuario."""
    _imprimir_seguro(f"{E.rojo}✖{E.reset} {mensaje}")


def pedir_confirmacion(mensaje: str) -> bool:
    """Pide al usuario una confirmación s/n y devuelve ``True`` si aceptó."""
    aviso = f"{E.tenue}(s/n){E.reset}"
    respuesta = input(f"{E.negrita}?{E.reset} {mensaje} {aviso}: ").strip().lower()
    return respuesta in RESPUESTAS_AFIRMATIVAS


# --- Localización de la raíz del proyecto -----------------------------------

#: Archivo actual y árbol oficial VersionDe_sesion/CONTRRF/STM_RFC/STM_RFPRMN.
#: NOTA: este módulo vive un nivel más abajo que RFPRMN.py (dentro de
#: STM_RFPRMN_stmDL/), así que MODULO_DIR se ancla al directorio de
#: RFPRMN.py (padre del paquete). CONTRRF se resuelve por posición real.
MODULO_DIR = Path(__file__).resolve().parent.parent
CONTRRF_DIR = MODULO_DIR.parent.parent
TLLDCD_DIR = CONTRRF_DIR / "TLLDCD"
SRC_DIR = CONTRRF_DIR / "RFC" / "src"
if (TLLDCD_DIR / "src").is_dir():
    SRC_DIR = TLLDCD_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
#: El bytecode de esta herramienta se guarda en su propio directorio, NUNCA
#: dentro de los árboles sincronizados (RFC/PRY): antes se redirigía al
#: pycache de STM_CH dentro de RFC/src, lo que ensuciaba el contenido
#: sincronizado e impedía vaciar RFC (archivos .pyc bloqueados en Windows).
PYCACHE_PROPIO = MODULO_DIR / ".pycache_rfprmn"
try:
    PYCACHE_PROPIO.mkdir(parents=True, exist_ok=True)
    sys.pycache_prefix = str(PYCACHE_PROPIO)
except Exception:
    pass


def _ruta_larga(ruta: Path) -> str:
    """Devuelve ``ruta`` con prefijo \\\\?\\ en Windows (evita el tope MAX_PATH)."""
    texto = str(ruta)
    if os.name == "nt" and not texto.startswith("\\\\?\\"):
        return "\\\\?\\" + texto
    return texto


def limpiar_caches_arranque() -> None:
    """Borra las cachés de bytecode de la herramienta (silencioso).

    Se ejecuta al salir del proceso (atexit): cada ejecución deja el
    directorio limpio aunque después se lancen más comandos que
    recompilen e importen de nuevo.
    """
    import shutil as _shutil

    for objetivo in (MODULO_DIR / "__pycache__",
                     MODULO_DIR / "STM_RFPRMN_stmDL" / "__pycache__",
                     PYCACHE_PROPIO):
        try:
            if objetivo.is_dir() and not objetivo.is_symlink():
                _shutil.rmtree(_ruta_larga(objetivo), ignore_errors=True)
            elif objetivo.exists():
                objetivo.unlink()
        except OSError:
            pass


try:
    import atexit as _atexit
    _atexit.register(limpiar_caches_arranque)
except Exception:
    pass


def encontrar_raiz(ruta: str | Path) -> str:
    """Localiza la raíz del proyecto, soportando el layout actual
    (VersionDe_sesion/CONTRRF/TLLDCD/src), el moderno (RFC +
    Sistema_Principal/PRY) y el heredado (Construccion/CPRZ/PRY)."""
    actual = Path(ruta).resolve()
    if actual.is_file():
        actual = actual.parent
    for candidato in (actual, *actual.parents):
        if (candidato / "src" / "STMGNRL" / "mainLCSTM.py").is_file():
            return str(candidato)
        if (candidato / "RFC" / "src" / "STMGNRL" / "mainLCSTM.py").is_file():
            return str(candidato)
        if (candidato / "RFC").is_dir() and (candidato.parent / "Sistema_Principal" / "PRY").is_dir():
            return str(candidato.parent)
        if (candidato / "CONTRRF" / "RFC").is_dir() and (candidato / "Sistema_Principal" / "PRY").is_dir():
            return str(candidato)
        if (candidato / "RFC").is_dir() and (candidato / "Sistema_Principal" / "PRY").is_dir():
            return str(candidato)
        if (candidato / "VersionDe_sesion" / "CONTRRF" / "RFC").is_dir() and (candidato / "VersionDe_sesion" / "Sistema_Principal" / "PRY").is_dir():
            return str(candidato / "VersionDe_sesion")
        if (candidato / "Construccion" / "CPRZ" / "PRY").is_dir():
            return str(candidato)
    raise RaizProyectoNoEncontrada("No se encontró la raíz del proyecto.")


RAIZ = Path(encontrar_raiz(__file__))
if (RAIZ / "RFC" / "src" / "STMGNRL" / "mainLCSTM.py").is_file():
    ORIGEN = RAIZ / "RFC" / "src"
    DESTINO = RAIZ / "RFC"
elif (RAIZ / "src" / "STMGNRL" / "mainLCSTM.py").is_file():
    ORIGEN = RAIZ / "src"
    DESTINO = RAIZ / "STM_RFC" / "sync"
elif (RAIZ / "Sistema_Principal" / "PRY").is_dir():
    ORIGEN = RAIZ / "Sistema_Principal" / "PRY"
    DESTINO = RAIZ / "CONTRRF" / "RFC"
else:
    ORIGEN = RAIZ / "Construccion" / "CPRZ" / "PRY"
    DESTINO = RAIZ / "Construccion" / "CONTRRF" / "RFC"

try:
    from STM_JSON.registro_json import ruta_de as _ruta_json_stm  # pyrefly: ignore[missing-import]
    CONFIG_IA_LOCAL = _ruta_json_stm("ialocal")
except Exception:
    CONFIG_IA_LOCAL = SRC_DIR / "STM_JSON" / "IAlocal.json"

#: Rutas oficiales del sistema (fijas): refactorizar mueve PRY/<actualizacion>/src -> RFC/src.
RUTA_RFC_OFICIAL = Path(r"C:\Users\User\Desktop\WoldVirtualP2P3D_v0.0.01LCV1\VersionDe_sesion\CONTRRF\RFC")
RUTA_PRY_OFICIAL = Path(r"C:\Users\User\Desktop\WoldVirtualP2P3D_v0.0.01LCV1\VersionDe_sesion\Sistema_Principal\PRY")
#: Destino del comando ``enviar`` y origen principal del comando ``actualizar``.
RFC_DIR = RUTA_RFC_OFICIAL if RUTA_RFC_OFICIAL.is_dir() else CONTRRF_DIR / "RFC"
PRY_DIR = RUTA_PRY_OFICIAL if RUTA_PRY_OFICIAL.is_dir() else CONTRRF_DIR.parent / "Sistema_Principal" / "PRY"

#: Rutas de carpetas creadas durante la sesión, relativas a la raíz.
carpetas_creadas: list[str] = []


