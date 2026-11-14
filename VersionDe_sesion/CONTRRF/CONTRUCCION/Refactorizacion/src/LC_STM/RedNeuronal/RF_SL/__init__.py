"""RF_SL - red neuronal supervisada (2026).

Reune la base compartida, el motor de importacion/registro de modelos, los
puentes historicos ``RFSL1`` y las 10 implementaciones especializadas:
SL1_1 ... SL1_10.

La API principal recomendada es::

    from LC_STM.RedNeuronal.RF_SL import build_model, get_available_models
    modelo = build_model("neural_network", 4, 1)
"""

from __future__ import annotations

import importlib
from typing import Any, List

from .RF_SL_SBRTM_RF_rfsl_base import *  # noqa: F401,F403
from .RF_SL_SBRTM_RF_rfsl_base import __all__ as _base_all
from .RF_SL_SBRTM_IMPORT import (
    DataPipeline,
    MetricsCollector,
    ModelRegistry,
    NeuronaMemoriaBase,
    TrainingConfig,
    build_model,
    compare_models,
    get_available_models,
    quick_evaluate,
    quick_predict,
    quick_train,
    serialize_model,
    deserialize_model,
    train_all_models,
)

__version__ = "2026.1.0"
__author__ = "WoldVirtualP2P3D Team"

_PAQUETES_ESPECIALIZADOS = tuple(
    f"RF_SL_SBRTM_RF_SL1_{indice}" for indice in range(1, 11)
)
_SUBMODULOS = ("RFSL1",) + _PAQUETES_ESPECIALIZADOS


def __getattr__(nombre: str) -> Any:
    if nombre in _SUBMODULOS:
        return importlib.import_module(f"{__name__}.{nombre}")
    raise AttributeError(
        f"El paquete {__name__!r} no tiene el atributo {nombre!r}"
    )


def __dir__() -> List[str]:
    return sorted(list(globals().keys()) + list(_SUBMODULOS))


__all__ = list(dict.fromkeys([
    *_base_all,
    'NeuronaMemoriaBase',
    'ModelRegistry',
    'TrainingConfig',
    'MetricsCollector',
    'DataPipeline',
    'build_model',
    'train_all_models',
    'compare_models',
    'get_available_models',
    'serialize_model',
    'deserialize_model',
    'quick_train',
    'quick_predict',
    'quick_evaluate',
    'RFSL1',
    *_PAQUETES_ESPECIALIZADOS,
    '__version__',
    '__author__',
]))
