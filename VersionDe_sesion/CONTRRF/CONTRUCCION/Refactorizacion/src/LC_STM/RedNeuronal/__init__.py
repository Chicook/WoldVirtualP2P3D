"""RedNeuronal - red neuronal modular de WoldVirtual P2P3D (2026).

Familias integradas
-------------------
- ``ENRN``    : red neuronal estandar / entrada sensorial.
- ``RF_EN``   : red neuronal por refuerzo.
- ``RF_SL``   : red neuronal supervisada (10 optimizadores + puentes).
- ``RNP``     : optimizacion de pesos (AdamW, SAM, Lion, SWAT, etc.).
- ``SLRN``    : aprendizaje supervisado con optimizadores neuronales.
- ``CELEBRO`` : BLOK1, orquestador e integrador con servidor neuronal.

La carga de cada familia es perezosa: ``import LC_STM.RedNeuronal`` no
inicializa ENRN/RF_EN/CELEBRO hasta que se accede a ellos.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List

__version__ = "2026.1.0"
__author__ = "WoldVirtualP2P3D Team"

FAMILIAS = ("ENRN", "RF_EN", "RF_SL", "RNP", "SLRN", "CELEBRO")
_SUBMODULOS = FAMILIAS


def __getattr__(nombre: str) -> Any:
    if nombre in _SUBMODULOS:
        return importlib.import_module(f"{__name__}.{nombre}")
    raise AttributeError(
        f"El paquete {__name__!r} no tiene el atributo {nombre!r}. "
        f"Familias disponibles: {', '.join(FAMILIAS)}"
    )


def salud_red() -> Dict[str, Dict[str, Any]]:
    """Comprueba la importacion y la salud basica de cada familia."""
    informe: Dict[str, Dict[str, Any]] = {}
    for familia in FAMILIAS:
        try:
            modulo = importlib.import_module(f"{__name__}.{familia}")
            detalle: Dict[str, Any] = {
                'importa': True,
                'version': getattr(modulo, '__version__', 'desconocida'),
            }
            if familia == 'RF_SL':
                modelos = modulo.get_available_models()
                detalle['modelos'] = list(modelos)
                detalle['ok'] = len(modelos) == 10
            elif familia == 'RNP':
                detalle['salud'] = modulo.health_check()
                detalle['ok'] = detalle['salud'].get('status') == 'ok'
            elif familia == 'SLRN':
                optimizadores = modulo.list_optimizers()
                detalle['optimizadores'] = list(optimizadores)
                detalle['ok'] = len(optimizadores) == 10
            elif familia == 'ENRN':
                tipos = modulo.listar_tipos()
                detalle['tipos'] = list(tipos) if tipos else []
                clases = [
                    nombre for nombre in dir(modulo)
                    if nombre.startswith('Neurona')
                ]
                detalle['clases'] = len(clases)
                detalle['ok'] = bool(clases or tipos)
            elif familia == 'RF_EN':
                detalle['clases'] = len(getattr(modulo, '__all__', ()))
                detalle['ok'] = detalle['clases'] >= 10
            elif familia == 'CELEBRO':
                bloque = modulo.BLOK1
                detalle['ok'] = bool(
                    hasattr(bloque, 'BaseNeuronal1')
                    and hasattr(bloque, 'ServidorNeuronal')
                )
            else:
                detalle['ok'] = True
            informe[familia] = detalle
        except Exception as exc:  # noqa: BLE001
            informe[familia] = {
                'importa': False,
                'ok': False,
                'error': f"{type(exc).__name__}: {exc}",
            }
    return informe


def info() -> Dict[str, Any]:
    """Metadatos de la red neuronal y familias disponibles."""
    return {
        'nombre': 'RedNeuronal',
        'version': __version__,
        'autor': __author__,
        'familias': list(FAMILIAS),
        'subpaquetes': {
            'ENRN': 'red neuronal estandar',
            'RF_EN': 'red neuronal por refuerzo',
            'RF_SL': 'red neuronal supervisada',
            'RNP': 'optimizacion de pesos',
            'SLRN': 'optimizadores supervisados',
            'CELEBRO': 'BLOK1 + servidor neuronal',
        },
    }


def __dir__() -> List[str]:
    return sorted(list(globals().keys()) + list(_SUBMODULOS))


__all__ = [
    'FAMILIAS',
    'salud_red',
    'info',
    'ENRN',
    'RF_EN',
    'RF_SL',
    'RNP',
    'SLRN',
    'CELEBRO',
    '__version__',
    '__author__',
]
