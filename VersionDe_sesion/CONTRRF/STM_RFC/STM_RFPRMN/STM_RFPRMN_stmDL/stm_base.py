"""Estilo de terminal, constantes, errores y mensajes de RFPRMN.

Las rutas ya no se calculan aquí: viven en :mod:`stm_rutas` (única fuente de
verdad, R1/R2) y se re-exportan para no romper a los módulos ni a la fachada
que hacían ``from .stm_base import RFC_DIR``.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
from pathlib import Path

from .stm_rutas import (  # noqa: F401  (re-exportados por compatibilidad)
    CONFIG_IA_LOCAL, CONTRRF_DIR, DESTINO, DIR_CONFIG, DIR_DATOS,
    DIR_MODELOS_LOCAL, MODULO_DIR, ORIGEN, PRY_DIR, RAIZ, REGISTRO_REFACTOR_MD,
    RFC_DIR, RUTA_PRY_OFICIAL, RUTA_RFC_OFICIAL, SRC_DIR, TLLDCD_DIR,
    encontrar_raiz,
)

__version__ = "2.16.0"

#: El `src` del proyecto se añade al path para los imports del sistema.
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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


# --- Cachés de bytecode ------------------------------------------------------

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
    for objetivo in (MODULO_DIR / "__pycache__",
                     MODULO_DIR / "STM_RFPRMN_stmDL" / "__pycache__",
                     PYCACHE_PROPIO):
        try:
            if objetivo.is_dir() and not objetivo.is_symlink():
                shutil.rmtree(_ruta_larga(objetivo), ignore_errors=True)
            elif objetivo.exists():
                objetivo.unlink()
        except OSError:
            pass


try:
    import atexit as _atexit
    _atexit.register(limpiar_caches_arranque)
except Exception:
    pass

#: Rutas de carpetas creadas durante la sesión, relativas a la raíz.
carpetas_creadas: list[str] = []
