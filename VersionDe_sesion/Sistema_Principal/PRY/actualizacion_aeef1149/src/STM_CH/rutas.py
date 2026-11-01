"""Rutas de artefactos runtime -> STM_CH.

Las raices y las rutas concretas las define `STM_HRTS.rutas`; este módulo solo
mantiene el ciclo de vida de lo que el sistema crea en ejecución (pycache,
pesos PSNRL, ledger, cache IAFREE).

H1 (contención P0) — separación de responsabilidades:
  - ``limpiar_solo_cache()``: borra únicamente pycache y ruff_cache.  SEGURA.
  - ``limpiar()``: alias de limpiar_solo_cache() para compatibilidad con código
    existente.  Ya no toca ledger ni PSNRL.
  - ``borrar_datos_sesion_confirmado(confirmado=False)``: borra ledger y PSNRL
    SOLO cuando ``confirmado=True`` se pasa explícitamente.  Debe llamarse
    únicamente tras verificar que existe un backup restaurable (CID real + pin
    confirmado + descarga de prueba con hash idéntico).
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
    "inicializar", "limpiar", "limpiar_solo_cache", "borrar_datos_sesion_confirmado",
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


def limpiar_solo_cache() -> dict:
    """Borra pycache y ruff_cache. NO toca ledger ni PSNRL (H1).

    Único modo seguro de limpieza automática al cerrar la sesión.
    Devuelve un resumen con el conteo de artefactos borrados.
    """
    resumen: dict = {"borrados": 0, "errores": []}
    for objetivo in _objetivos_limpieza():
        if not objetivo.exists():
            continue
        # H1: excluir explícitamente PSNRL_DIR y LEDGER_PATH de la limpieza normal
        if objetivo == PSNRL_DIR:
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
    # Cache de OpenRouter: se puede borrar, no contiene datos de sesión
    try:
        if CACHE_IAFREE.exists():
            CACHE_IAFREE.unlink()
            resumen["borrados"] += 1
    except Exception as e:
        resumen["errores"].append(f"{CACHE_IAFREE}: {e}")
    return resumen


def limpiar() -> dict:
    """Alias de ``limpiar_solo_cache()``.

    Compatibilidad con el código existente que llama a ``limpiar()``.
    Ya NO borra ledger ni PSNRL (H1, P0-1): esa responsabilidad pasó a
    ``borrar_datos_sesion_confirmado()``.
    """
    return limpiar_solo_cache()


def borrar_datos_sesion_confirmado(
    confirmado: bool = False,
    motivo: str = "",
) -> dict:
    """Borra ledger y PSNRL. OPERACIÓN DESTRUCTIVA (H1, P0-1).

    Solo se ejecuta cuando:
      1. ``confirmado=True`` se pasa explícitamente por el llamador.
      2. El llamador ha verificado beforehand la existencia de un backup
         restaurable (CID real, pin confirmado, descarga de prueba y bytes
         con hash idéntico).

    Sin backup verificado, esta función rechaza el borrado y devuelve un error.

    Args:
        confirmado: debe ser ``True`` para que el borrado proceda.
        motivo: texto libre del llamador describiendo por qué se borra.

    Returns:
        Diccionario ``{"ok", "borrados", "errores", "rechazado"}``.
    """
    if not confirmado:
        return {
            "ok": False,
            "rechazado": True,
            "borrados": 0,
            "errores": [],
            "error": (
                "Borrado rechazado: confirmado=False.  "
                "Llama con confirmado=True solo tras verificar backup restaurable."
            ),
        }
    resumen: dict = {"ok": True, "rechazado": False, "borrados": 0, "errores": [], "motivo": motivo}
    for fich in (LEDGER_PATH,):
        try:
            if fich.exists():
                fich.unlink()
                resumen["borrados"] += 1
        except Exception as e:
            resumen["errores"].append(f"{fich}: {e}")
            resumen["ok"] = False
    # PSNRL: borrar solo el contenido, no la carpeta
    if PSNRL_DIR.exists():
        for hijo in list(PSNRL_DIR.iterdir()):
            try:
                if hijo.is_dir() and not hijo.is_symlink():
                    shutil.rmtree(hijo, ignore_errors=True)
                else:
                    hijo.unlink(missing_ok=True)
                resumen["borrados"] += 1
            except Exception as e:
                resumen["errores"].append(f"{hijo}: {e}")
                resumen["ok"] = False
    return resumen
