"""Subpaquete RF_EN_SBRTM_RFEN1_RN_5: A3C Distribuido y Configuracion (RF_EN · SBRTM)."""
try:
    from .RF_EN_SBRTM_RFEN1_RN_5_1 import NeuronaDeComfiguracion, NeuronaRefuerzoA3C
except ImportError:
    import importlib.util as _ilu, os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_SBRTM_RFEN1_RN_5_1",
        _os.path.join(_base, "RF_EN_SBRTM_RFEN1_RN_5_1.py"),
    )
    if _spec and _spec.loader:
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        NeuronaDeComfiguracion = _mod.NeuronaDeComfiguracion
        NeuronaRefuerzoA3C = _mod.NeuronaRefuerzoA3C
    else:
        NeuronaDeComfiguracion = None
        NeuronaRefuerzoA3C = None

__all__ = ["NeuronaDeComfiguracion", "NeuronaRefuerzoA3C"]
