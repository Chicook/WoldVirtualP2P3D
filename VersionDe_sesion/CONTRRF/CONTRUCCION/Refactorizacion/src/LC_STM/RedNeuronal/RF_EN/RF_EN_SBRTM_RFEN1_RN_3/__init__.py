"""Subpaquete RF_EN_SBRTM_RFEN1_RN_3: Actor-Critic, Inicialización y Gradientes (RF_EN · SBRTM)."""

try:
    from .RF_EN_SBRTM_RFEN1_RN_3_1 import (
        GestorGradientesAC,
        NeuronaGestionGradientesAC,
    )
    from .RF_EN_SBRTM_RFEN1_RN_3_2 import (
        requiere_pesos_inicializados,
        tiempo_ejecucion,
        NeuronaIniciacionDePesos,
        NeuronaActorCriticOptimizada,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.abspath(__file__))

    # Carga 3_1
    _spec1 = _ilu.spec_from_file_location(
        "RF_EN_SBRTM_RFEN1_RN_3_1",
        _os.path.join(_base, "RF_EN_SBRTM_RFEN1_RN_3_1.py"),
    )
    if _spec1 and _spec1.loader:
        _mod1 = _ilu.module_from_spec(_spec1)
        _spec1.loader.exec_module(_mod1)
        GestorGradientesAC = _mod1.GestorGradientesAC
        NeuronaGestionGradientesAC = _mod1.NeuronaGestionGradientesAC
    else:
        GestorGradientesAC = None  # type: ignore[assignment]
        NeuronaGestionGradientesAC = None  # type: ignore[assignment]

    # Carga 3_2
    _spec2 = _ilu.spec_from_file_location(
        "RF_EN_SBRTM_RFEN1_RN_3_2",
        _os.path.join(_base, "RF_EN_SBRTM_RFEN1_RN_3_2.py"),
    )
    if _spec2 and _spec2.loader:
        _mod2 = _ilu.module_from_spec(_spec2)
        _spec2.loader.exec_module(_mod2)
        requiere_pesos_inicializados = _mod2.requiere_pesos_inicializados
        tiempo_ejecucion = _mod2.tiempo_ejecucion
        NeuronaIniciacionDePesos = _mod2.NeuronaIniciacionDePesos
        NeuronaActorCriticOptimizada = _mod2.NeuronaActorCriticOptimizada
    else:
        requiere_pesos_inicializados = None  # type: ignore[assignment]
        tiempo_ejecucion = None  # type: ignore[assignment]
        NeuronaIniciacionDePesos = None  # type: ignore[assignment]
        NeuronaActorCriticOptimizada = None  # type: ignore[assignment]

__all__ = [
    "GestorGradientesAC",
    "NeuronaGestionGradientesAC",
    "requiere_pesos_inicializados",
    "tiempo_ejecucion",
    "NeuronaIniciacionDePesos",
    "NeuronaActorCriticOptimizada",
]
