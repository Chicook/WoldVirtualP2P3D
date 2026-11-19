"""Garantiza el import del taller antes de recoger cualquier test.

`pythonpath = .` del pytest.ini de la raiz ya hace esto cuando la config se
encuentra, y 13 ficheros del taller llevan su propio
`sys.path.insert(0, str(Path(__file__).resolve().parents[2]))` por si acaso.
El conftest cubre el caso que quedaba descubierto: recoger desde un IDE o con
una config alternativa, donde el paquete `STM_HRTS` no esta instalado y el
import falla con un ModuleNotFoundError que no dice nada del taller.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2]

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
