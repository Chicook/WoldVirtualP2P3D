"""Rutas de artefactos runtime -> STM_CH.

Las raices y las rutas concretas las define `STM_HRTS.rutas`; este modulo solo
mantiene el ciclo de vida de lo que el sistema crea en ejecucion (pycache,
pesos PSNRL, ledger, cache IAFREE), que se borra al cerrar.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from STM_HRTS.rutas import (  # noqa: E402  (necesita el sys.path de arriba)
    CACHE_IAFREE,
    CONTRRF_DIR,
    LEDGER_PATH,
    PSNRL_DIR,
    PYCACHE_DIR,
    RUFF_CACHE_CANON,
    SRC_DIR,
    STM_CH_DIR,
    TLLDCD_DIR,
)

__all__ = [
    "STM_CH_DIR", "SRC_DIR", "TLLDCD_DIR", "CONTRRF_DIR", "PYCACHE_DIR",
    "PSNRL_DIR", "LEDGER_PATH", "CACHE_IAFREE", "RUFF_CACHE_CANON",
    "inicializar", "limpiar",
]


def inicializar() -> None:
    """Crea STM_CH/PSNRL, redirige __pycache__ y fija RUFF_CACHE_DIR."""
    PSNRL_DIR.mkdir(parents=True, exist_ok=True)
    PYCACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        sys.pycache_prefix = str(PYCACHE_DIR)
    except Exception:
        pass
    try:
        os.environ.setdefault("RUFF_CACHE_DIR", str(RUFF_CACHE_CANON))
    except Exception:
        pass


def _objetivos_limpieza() -> list[Path]:
    """Carpetas generadas que se pueden borrar sin tocar codigo ni datos.

    Los `__pycache__` se descubren en el arbol en vez de listarlos a mano: un
    paquete nuevo no deja basura por olvido.
    """
    objetivos: list[Path] = [STM_CH_DIR / "__pycache__", SRC_DIR / "__pycache__"]
    try:
        objetivos.extend(sorted(p for p in SRC_DIR.rglob("__pycache__") if p.is_dir()))
    except Exception:
        pass
    for rc in (CONTRRF_DIR / ".ruff_cache", TLLDCD_DIR / ".ruff_cache", SRC_DIR / ".ruff_cache"):
        try:
            if rc.exists() and rc.resolve() != RUFF_CACHE_CANON.resolve():
                objetivos.append(rc)
        except Exception:
            pass
    vistos: set[Path] = set()
    unicos: list[Path] = []
    for objetivo in objetivos:
        if objetivo not in vistos:
            vistos.add(objetivo)
            unicos.append(objetivo)
    return unicos


def limpiar() -> dict:
    """Borra todo el contenido generado en STM_CH/. Devuelve resumen."""
    resumen: dict = {"borrados": 0, "errores": []}
    for objetivo in _objetivos_limpieza():
        if not objetivo.exists():
            continue
        if objetivo in (PSNRL_DIR, PYCACHE_DIR):
            for hijo in list(objetivo.iterdir()):
                try:
                    if hijo.is_dir() and not hijo.is_symlink():
                        shutil.rmtree(hijo, ignore_errors=True)
                    else:
                        hijo.unlink(missing_ok=True)
                    resumen["borrados"] += 1
                except Exception as e:
                    resumen["errores"].append(f"{hijo}: {e}")
        else:
            try:
                shutil.rmtree(objetivo, ignore_errors=True)
                resumen["borrados"] += 1
            except Exception as e:
                resumen["errores"].append(f"{objetivo}: {e}")
    for fich in (LEDGER_PATH, CACHE_IAFREE):
        try:
            if fich.exists():
                fich.unlink()
                resumen["borrados"] += 1
        except Exception as e:
            resumen["errores"].append(f"{fich}: {e}")
    return resumen
