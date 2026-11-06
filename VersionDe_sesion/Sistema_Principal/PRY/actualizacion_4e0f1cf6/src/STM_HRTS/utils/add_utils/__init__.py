"""add_utils: rutas canonicas, herramientas y manifiesto del sistema.

Paquete anidado en ``STM_HRTS/utils/add_utils``. Se importa por su ruta real:

    from STM_HRTS.utils.add_utils import rutas, herramientas
    rutas.GODOT_DIR          # ruta real del proyecto Godot
    herramientas.catalogo()  # scripts de STM_HRTS/utils con su comando

La consola se expone en la raiz del taller: ``python -m STM_HRTS``.
"""
from __future__ import annotations

__all__ = ["rutas", "herramientas"]
