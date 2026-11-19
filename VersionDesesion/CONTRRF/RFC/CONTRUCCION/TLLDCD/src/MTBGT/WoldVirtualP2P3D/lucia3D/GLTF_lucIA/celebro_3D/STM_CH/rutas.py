"""Rutas runtime de LucIA.

Los datos de la red neuronal (PSNRL) no deben escribirse dentro del proyecto:
el visor puede estar instalado en una carpeta de solo lectura. Se usa, por
orden:

1. ``LUCIA_PSNRL_DIR`` si está definida.
2. ``%APPDATA%\\WoldVirtualP2P3D\\lucia\\PSNRL`` (Windows).
3. ``STM_CH/PSNRL`` del proyecto como último recurso.

Si la carpeta destino está vacía se copian los pesos iniciales del proyecto.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

STM_CH_DIR: Path = Path(__file__).resolve().parent
SRC_DIR: Path = STM_CH_DIR.parent
_SEED_DIR: Path = STM_CH_DIR / "PSNRL"


def _elegir_dir() -> Path:
    forzada = os.getenv("LUCIA_PSNRL_DIR", "").strip()
    if forzada:
        return Path(forzada)
    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / "Godot" / "app_userdata" / "WoldVirtualP2P3D" / "lucia" / "PSNRL"
    return _SEED_DIR


PSNRL_DIR: Path = _elegir_dir()


def inicializar() -> None:
    PSNRL_DIR.mkdir(parents=True, exist_ok=True)
    if PSNRL_DIR.resolve() == _SEED_DIR.resolve():
        return
    for nombre in ("psnrl_lucia.npz", "psnrl_lucia.json"):
        origen = _SEED_DIR / nombre
        destino = PSNRL_DIR / nombre
        if origen.exists() and not destino.exists():
            try:
                shutil.copy2(origen, destino)
            except OSError:
                pass
