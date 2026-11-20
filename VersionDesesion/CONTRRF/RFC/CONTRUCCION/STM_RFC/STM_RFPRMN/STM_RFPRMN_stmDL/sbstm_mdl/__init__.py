"""Submódulos extraídos de la fachada ``stm_flujo.py``.

Cada archivo de este paquete implementa una parte del pipeline; ``stm_flujo``,
``stm_particion`` y ``stm_agente`` los re-exportan para conservar la API
pública. La carga es perezosa (PEP 562) para no importar todo de golpe.
"""
from __future__ import annotations

import importlib

_MODULOS = {
    "FlujoRefactorLucIA": "sbstm_flj",
    "consumir_modelos_por_entorno": "sbstm_flj",
    "Particionador": "sbstm_ptcn",
    "AgenteRFPRMN": "sbstm_agnt",
}

__all__ = list(_MODULOS)


def __getattr__(nombre: str):
    """Resuelve los símbolos públicos del paquete bajo demanda."""
    modulo = _MODULOS.get(nombre)
    if modulo is None:
        raise AttributeError(f"módulo {__name__!r} no tiene atributo {nombre!r}")
    return getattr(importlib.import_module(f"{__name__}.{modulo}"), nombre)
