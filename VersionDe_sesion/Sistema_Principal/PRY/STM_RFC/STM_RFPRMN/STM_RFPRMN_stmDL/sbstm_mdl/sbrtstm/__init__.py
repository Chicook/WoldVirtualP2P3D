"""Submódulos del agente autónomo de RFPRMN.

Cada archivo implementa una parte del agente; ``sbstm_agnt`` los importa para
componer la clase final. La carga es perezosa (PEP 562).
"""
from __future__ import annotations

import importlib

_MODULOS = {"AgenteRFPRMN": "snrtstm_sbstm_agnt"}

__all__ = list(_MODULOS)


def __getattr__(nombre: str):
    """Resuelve los símbolos públicos del paquete bajo demanda."""
    modulo = _MODULOS.get(nombre)
    if modulo is None:
        raise AttributeError(f"módulo {__name__!r} no tiene atributo {nombre!r}")
    return getattr(importlib.import_module(f"{__name__}.{modulo}"), nombre)
