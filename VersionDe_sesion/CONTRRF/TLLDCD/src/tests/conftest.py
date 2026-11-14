"""Garantiza el import del taller desde la raiz de tests.

Pone ``src`` en ``sys.path`` para que la recoleccion funcione igual desde
pytest, un IDE o un script directo.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))