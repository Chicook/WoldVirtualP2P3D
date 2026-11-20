"""Escaneo del historial Git: el dropper vivio en un commit, no en el arbol.

``deteccion.escanear_arbol`` solo ve el arbol de trabajo; el codigo danino
(commit ``d510acd``) quedo en el historial. Este modulo invoca ``git`` para
localizar que commits introdujeron los indicadores o los nombres de camuflaje,
de modo que el subsistema delate introducciones pasadas y vigile las futuras.

No modifica nada: usa ``git log`` en modo lectura (``-S``/pickaxe y pathspec) y
degrada con elegancia si ``git`` no esta disponible o no hay repositorio.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from . import SRC_DIR, iocs
from .modelos import ALTA, MEDIA, Hallazgo

#: Literales del dropper que se buscan por contenido (pickaxe ``git log -S``).
TERMINOS_VIGILADOS: Tuple[str, ...] = (
    "ethplorer.io",
    "eth_getTransactionByHash",
    "getAddressTransactions",
    iocs.DIRECCIONES_C2[0],
    "apiKey=freekey",
)

#: Severidad por termino de contenido (el canal C2 es ALTA).
_SEVERIDAD_TERMINO = {
    "ethplorer.io": ALTA,
    "eth_getTransactionByHash": ALTA,
    "getAddressTransactions": ALTA,
    iocs.DIRECCIONES_C2[0]: ALTA,
    "apiKey=freekey": MEDIA,
}

#: Fragmentos de RUTA de camuflaje (busqueda por pathspec, no por contenido).
RUTAS_VIGILADAS: Tuple[str, ...] = (
    "fa-brand-400",
    "transport.py",
)

#: Comandos git con firma desactivada, para poder usarlos en entornos de prueba.
_GIT_BASE = ("git", "-c", "commit.gpgsign=false")


def git_disponible() -> bool:
    """True si el ejecutable ``git`` esta en el PATH."""
    return shutil.which("git") is not None


def raiz_git(inicio: Optional[Path] = None) -> Optional[Path]:
    """Sube directorios desde ``inicio`` (por defecto ``src/``) hasta el repo."""
    actual = (inicio or SRC_DIR).resolve()
    for candidato in (actual, *actual.parents):
        if (candidato / ".git").exists():
            return candidato
    return None


def _git(repo: Path, *args: str) -> str:
    """Ejecuta ``git`` en modo lectura; devuelve la salida o cadena vacia."""
    try:
        proceso = subprocess.run(
            [*_GIT_BASE, "-C", str(repo), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
    except OSError:
        return ""
    return proceso.stdout if proceso.returncode == 0 else ""


def _filas(salida: str) -> List[Tuple[str, str]]:
    """Descompone ``%h\\t%ad\\t%s`` en pares ``(sha, resumen)``."""
    filas: List[Tuple[str, str]] = []
    for linea in salida.splitlines():
        partes = linea.split("\t", 2)
        if len(partes) == 3:
            filas.append((partes[0], f"{partes[1]} {partes[2]}"))
    return filas


def _commits_por_contenido(repo: Path, termino: str, limite: int) -> List[Tuple[str, str]]:
    """Commits donde cambio el numero de apariciones de ``termino`` (pickaxe)."""
    salida = _git(repo, "log", "--all", f"--max-count={limite}", "--date=short",
                  "--format=%h\t%ad\t%s", f"-S{termino}")
    return _filas(salida)


def _commits_por_ruta(repo: Path, fragmento: str, limite: int) -> List[Tuple[str, str]]:
    """Commits que tocaron una ruta cuyo nombre contiene ``fragmento``."""
    salida = _git(repo, "log", "--all", f"--max-count={limite}", "--date=short",
                  "--format=%h\t%ad\t%s", "--", f"*{fragmento}*")
    return _filas(salida)


def escanear_historial(
    repo: Optional[Path] = None,
    limite: int = 200,
    terminos: Optional[Sequence[str]] = None,
    rutas: Optional[Sequence[str]] = None,
) -> List[Hallazgo]:
    """Busca introducciones del dropper en el historial de commits.

    Devuelve un :class:`~STM_HRTS.STM_DEF.modelos.Hallazgo` por (commit, termino)
    detectado. Si no hay repositorio o no hay ``git``, devuelve una lista vacia
    en lugar de fallar: el escaneo del historial complementa, no sustituye, al
    barrido del arbol.
    """
    raiz = raiz_git(repo)
    if raiz is None or not git_disponible():
        return []

    lista_terminos = tuple(terminos) if terminos is not None else TERMINOS_VIGILADOS
    lista_rutas = tuple(rutas) if rutas is not None else RUTAS_VIGILADAS

    hallazgos: List[Hallazgo] = []
    for termino in lista_terminos:
        severidad = _SEVERIDAD_TERMINO.get(termino, MEDIA)
        for sha, resumen in _commits_por_contenido(raiz, termino, limite):
            hallazgos.append(Hallazgo(
                id=f"git.contenido.{termino}",
                severidad=severidad,
                descripcion=f"commit introduce '{termino}'  ({resumen})",
                origen=f"git:{sha}",
            ))
    for fragmento in lista_rutas:
        for sha, resumen in _commits_por_ruta(raiz, fragmento, limite):
            hallazgos.append(Hallazgo(
                id=f"git.ruta.{fragmento}",
                severidad=MEDIA,
                descripcion=f"commit toca un fichero de camuflaje '{fragmento}'  ({resumen})",
                origen=f"git:{sha}",
            ))
    return hallazgos


def resumen(hallazgos: List[Hallazgo]) -> dict:
    """Vista minima y serializable del barrido del historial."""
    commits = {h.origen for h in hallazgos}
    return {
        "hallazgos": len(hallazgos),
        "commits": len(commits),
        "terminos": list(TERMINOS_VIGILADOS),
        "rutas": list(RUTAS_VIGILADAS),
    }


__all__ = [
    "escanear_historial", "raiz_git", "git_disponible", "resumen",
    "TERMINOS_VIGILADOS", "RUTAS_VIGILADAS",
]
