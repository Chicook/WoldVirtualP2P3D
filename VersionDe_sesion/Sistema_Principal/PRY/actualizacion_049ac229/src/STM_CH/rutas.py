"""Rutas centralizadas de artefactos runtime -> STM_CH.

Todo lo que el sistema crea en ejecucion (pycache, pesos PSNRL,
ledger, cache IAFREE) vive bajo STM_CH/ y se borra al cerrar.
"""
from __future__ import annotations
import os
import shutil
import sys
from pathlib import Path

STM_CH_DIR: Path = Path(__file__).resolve().parent
SRC_DIR: Path = STM_CH_DIR.parent
TLLDCD_DIR: Path = SRC_DIR.parent
CONTRRF_DIR: Path = TLLDCD_DIR.parent
PYCACHE_DIR: Path = STM_CH_DIR / "pycache"
PSNRL_DIR: Path = STM_CH_DIR / "PSNRL"
LEDGER_PATH: Path = STM_CH_DIR / "blockchain_ledger.json"
CACHE_IAFREE: Path = STM_CH_DIR / "openrouter_free_cache.json"
RUFF_CACHE_CANON: Path = SRC_DIR / "STM_HRTS" / ".ruff_cache"


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


def limpiar() -> dict:
    """Borra todo el contenido generado en STM_CH/. Devuelve resumen."""
    resumen = {"borrados": 0, "errores": []}
    objetivos = [
        PYCACHE_DIR,
        PSNRL_DIR,
        STM_CH_DIR / "__pycache__",
        SRC_DIR / "__pycache__",
        SRC_DIR / "SBSTM" / "__pycache__",
        SRC_DIR / "STM_BKCH" / "__pycache__",
        SRC_DIR / "STM_IA" / "__pycache__",
        SRC_DIR / "STMGNRL" / "__pycache__",
        SRC_DIR / "STM_HRTS" / "__pycache__",
        SRC_DIR / "STM_SGR" / "__pycache__",
        SRC_DIR / "STM_JSON" / "__pycache__",
        SRC_DIR / "STMIPFS" / "__pycache__",
        SRC_DIR / "tests" / "__pycache__",
    ]
    for rc in (CONTRRF_DIR / ".ruff_cache", TLLDCD_DIR / ".ruff_cache", SRC_DIR / ".ruff_cache"):
        try:
            if rc.exists() and rc.resolve() != RUFF_CACHE_CANON.resolve():
                objetivos.append(rc)
        except Exception:
            pass
    vistos = set()
    unicos = []
    for o in objetivos:
        if o not in vistos:
            vistos.add(o)
            unicos.append(o)
    for objetivo in unicos:
        if objetivo.exists():
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
