"""Rutas runtime de LucIA, adaptadas de STM_CH/rutas.py del proyecto principal."""
from __future__ import annotations

from pathlib import Path

STM_CH_DIR: Path = Path(__file__).resolve().parent
SRC_DIR: Path = STM_CH_DIR.parent
PSNRL_DIR: Path = STM_CH_DIR / "PSNRL"


def inicializar() -> None:
    PSNRL_DIR.mkdir(parents=True, exist_ok=True)
