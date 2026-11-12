import numpy as np
import math
import time
import json
from typing import Tuple, Optional, Dict, Any, List, Callable
try:
    from . import NeuronaEntradaBase, LUCIA_CONFIG
except ImportError:
    import numpy as _np_alias  # noqa: F401
    from typing import Tuple as _Tuple, Dict as _Dict, Any as _Any

    LUCIA_CONFIG = {
        "precision": "float32",
        "random_seed": 42,
        "default_learning_rate": 0.001,
    }

try:
    from .SBTM_EN3_RN.sbrtm_EN3_RN1 import (
        NeuronaEntradaBase,
        NeuronaEntradaLeCun as _NeuronaEntradaLeCunBase,
        LUCIA_CONFIG,
        _dtype,
        _now,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "sbrtm_EN3_RN1",
        _os.path.join(_base, "SBTM_EN3_RN", "sbrtm_EN3_RN1.py"))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    NeuronaEntradaBase = _mod.NeuronaEntradaBase
    _NeuronaEntradaLeCunBase = _mod.NeuronaEntradaLeCun
    LUCIA_CONFIG = _mod.LUCIA_CONFIG
    _dtype = _mod._dtype
    _now = _mod._now

try:
    from .SBTM_EN3_RN.sbrtm_EN3_RN2 import NeuronaCodigo as _NeuronaCodigo
except ImportError:
    import importlib.util as _ilu2
    import os as _os2
    _base2 = _os2.path.dirname(_os2.path.abspath(__file__))
    _spec2 = _ilu2.spec_from_file_location(
        "sbrtm_EN3_RN2",
        _os2.path.join(_base2, "SBTM_EN3_RN", "sbrtm_EN3_RN2.py"))
    _mod2 = _ilu2.module_from_spec(_spec2)
    _spec2.loader.exec_module(_mod2)
    _NeuronaCodigo = _mod2.NeuronaCodigo


class NeuronaEntradaLeCun(_NeuronaEntradaLeCunBase):
    """Neurona LeCun: API completa heredada de SBTM_EN3_RN.sbrtm_EN3_RN1."""

    # Creacion de archivos de codigo en la estructura de carpetas
    class NeuronaCodigo(_NeuronaCodigo):
        """Neurona de codigo: API completa heredada de SBTM_EN3_RN.sbrtm_EN3_RN2.

        Crea archivos de codigo vacio en cada seccion de LCtrabajando/src.
        Tras el analisis semantico del nombre de cada carpeta (via proyeccion
        LeCun + similitud coseno), determina el lenguaje mas afin y emite el
        comando 'crear archivo' para depositar un esqueleto vacio (.py, .cs,
        .gd, .json, .md ...) en cada subcarpeta de la estructura.

        Matematica expuesta (delega en Matematica de sbrtm_EN3_RN2):
          - similitud(a, b)     : coseno entre proyecciones LeCun.
          - similitud_batch()   : coseno vectorizado contra lista de textos.
          - impulso_codigo()    : temperatura [0.2, 0.9] desde ratio varianza LeCun.
          - entropia(texto)     : entropia de Shannon de la proyeccion LeCun.
          - divergencia_kl(a,b) : divergencia KL entre distribuciones softmax.
          - afinidad_lenguaje() : puntuacion coseno carpeta <-> descripcion lenguaje.
          - ranking()           : candidatos ordenados por afinidad descendente.
          - centroide() / dispersion(): metricas globales del espacio semantico.
        """

        def __init__(self, lecun: Any) -> None:
            super().__init__(lecun)
            self._lecun = self._neurona


__all__ = [
    "NeuronaEntradaBase",
    "NeuronaEntradaLeCun",
    "LUCIA_CONFIG",
]
