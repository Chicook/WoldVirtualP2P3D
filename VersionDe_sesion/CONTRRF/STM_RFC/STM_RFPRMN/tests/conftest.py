"""Configuración de las pruebas de STM_RFPRMN.

Dos ajustes necesarios para que la suite sea ejecutable en cualquier equipo:

1. Añade el directorio del módulo a ``sys.path`` (el paquete no se instala).
2. Sustituye ``tmp_path`` por una versión propia. La de pytest crea los
   directorios con ``mode=0o700`` y, en Windows con Python 3.14, eso produce
   carpetas que el propio proceso no puede abrir (``WinError 5``) cuando el
   equipo tiene políticas de integridad/sandbox. La nuestra usa el modo por
   defecto y limpia al terminar.

La raíz de temporales se puede fijar con ``RFPRMN_TEST_TMP``; si no, se usa
la del sistema.
"""
from __future__ import annotations

import itertools
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

RAIZ_MODULO = Path(__file__).resolve().parent.parent
if str(RAIZ_MODULO) not in sys.path:
    sys.path.insert(0, str(RAIZ_MODULO))

RAIZ_TEMPORALES = Path(os.environ.get("RFPRMN_TEST_TMP") or tempfile.gettempdir())
_CONTADOR = itertools.count()


@pytest.fixture
def tmp_path(request):
    """Directorio temporal propio, accesible y limpio al terminar la prueba."""
    RAIZ_TEMPORALES.mkdir(parents=True, exist_ok=True)
    nombre = "".join(c if c.isalnum() else "_" for c in request.node.name)[:40]
    carpeta = RAIZ_TEMPORALES / f"{nombre}-{next(_CONTADOR)}"
    shutil.rmtree(carpeta, ignore_errors=True)
    if carpeta.exists():
        # Una ejecución anterior dejó algo que no se pudo borrar (un binario en
        # uso, por ejemplo): se usa un nombre único en vez de fallar.
        carpeta = RAIZ_TEMPORALES / f"{nombre}-{uuid.uuid4().hex[:8]}"
        shutil.rmtree(carpeta, ignore_errors=True)
    carpeta.mkdir(parents=True)
    yield carpeta
    shutil.rmtree(carpeta, ignore_errors=True)
