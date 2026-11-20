"""EN7_RN - Neurona de entrada con BatchNorm (fachada extendida).

La implementacion base vive en ``SBTM_EN7_RN.sbrtm_EN7_RN1`` (clase
``NeuronaEntradaBatchNorm`` con ``BatchNorm`` y ``Optimizador`` anidados,
decoradores y estadisticas) y este modulo NO la duplica. Solo anade:

  - ``forward_batch``
  - claves historicas en las estadisticas (``forwards``/``backwards``,
    normas de running_mean, media de gamma, tiempos medios)
  - ``verificar_estabilidad`` ampliado y ``resumen_rendimiento``
  - ``reiniciar_metricas`` (solo metricas, sin tocar pesos ni optimizador)

Persistencia (``a_dict``/``guardar``/``cargar``), ``grad_entrada``,
``entrenar_paso`` y ``paso_optimizador`` se heredan del modulo base.

Ejemplo:
    >>> n = NeuronaEntradaBatchNorm(8, 4)
    >>> n.entrenar_paso(np.zeros((3, 8)), np.zeros((3, 4)))
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

try:
    from .SBTM_EN7_RN.sbrtm_EN7_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        NeuronaEntradaBatchNorm as _NeuronaEntradaBatchNormBase,
        _dtype,
        _now,
    )
except ImportError:  # ejecucion directa sin paquete
    from SBTM_EN7_RN.sbrtm_EN7_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        NeuronaEntradaBatchNorm as _NeuronaEntradaBatchNormBase,
        _dtype,
        _now,
    )

try:  # mantiene la precision configurada por el paquete ENRN
    from . import LUCIA_CONFIG as _CONFIG_ENRN

    if isinstance(_CONFIG_ENRN, dict):
        LUCIA_CONFIG.update(_CONFIG_ENRN)
except ImportError:
    pass

__all__ = [
    "NeuronaEntradaBase",
    "NeuronaEntradaBatchNorm",
    "LUCIA_CONFIG",
    "_dtype",
    "_now",
]


class NeuronaEntradaBatchNorm(_NeuronaEntradaBatchNormBase):
    """EN7 con utilidades extra sobre la base BatchNorm importada."""

    _ALIAS_OPTIMIZADOR = {
        "sgd_momentum": "sgd_momento",
        "momentum": "sgd_momento",
    }

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntradaBatchNorm",
                 momentum: float = 0.9,
                 epsilon: float = 1e-5,
                 factor_escala: float = 1.0,
                 modo_entrenamiento: bool = True,
                 learning_rate: float = 0.001,
                 optimizador: str = "adam",
                 beta1: float = 0.9,
                 beta2: float = 0.999,
                 eps_adam: float = 1e-8,
                 weight_decay: float = 0.0,
                 grad_clip: float = 5.0,
                 lr_decay: float = 0.0,
                 lr_min: float = 1e-6,
                 usar_cache_forward: bool = True,
                 semilla: Optional[int] = None,
                 capacidad_historial: int = 256):
        algoritmo = self._ALIAS_OPTIMIZADOR.get(str(optimizador).lower(),
                                                str(optimizador).lower())
        super().__init__(
            input_size, output_size, nombre,
            momentum=momentum, epsilon=epsilon, factor_escala=factor_escala,
            modo_entrenamiento=modo_entrenamiento, learning_rate=learning_rate,
            optimizador=algoritmo, beta1=beta1, beta2=beta2, eps_adam=eps_adam,
            weight_decay=weight_decay, grad_clip=grad_clip,
            lr_decay=lr_decay, lr_min=lr_min,
            usar_cache_forward=usar_cache_forward,
            semilla=semilla, capacidad_historial=capacidad_historial,
        )

    # ------------------------------------------------------------------
    def forward_batch(self, lote: List[np.ndarray]) -> List[np.ndarray]:
        return [self.forward(x) for x in lote]

    # ------------------------------------------------------------------
    # Metricas (amplian las de la base, sin reimplementarlas)
    # ------------------------------------------------------------------
    def obtener_estadisticas(self, completas: bool = False) -> Dict[str, Any]:
        info = super().obtener_estadisticas(completas=completas)
        info["forwards"] = self.contador_forward
        info["backwards"] = self.contador_backward
        return info

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        stats = self.obtener_estadisticas(completas=True)
        stats.update({
            "running_mean_norm": (float(np.linalg.norm(self.running_mean))
                                  if self.running_mean is not None else 0.0),
            "running_var_media": (float(np.mean(self.running_var))
                                  if self.running_var is not None else 0.0),
            "gamma_media": float(np.mean(self.gamma)) if self.gamma is not None else 0.0,
            "ultima_loss": self.historial_loss[-1] if self.historial_loss else None,
            "t_medio_forward_ms": (self.tiempo_forward_acum
                                   / max(1, self.contador_forward)) * 1000.0,
            "t_medio_backward_ms": (self.tiempo_backward_acum
                                    / max(1, self.contador_backward)) * 1000.0,
        })
        return stats

    def verificar_estabilidad(self) -> Dict[str, Any]:
        est = super().verificar_estabilidad()
        est["sesgo_inicializado"] = self.sesgo is not None
        est["bn_inicializado"] = self.gamma is not None
        if self.pesos is not None:
            pmax = float(np.max(np.abs(self.pesos)))
            pmin = max(float(np.min(np.abs(self.pesos))), 1e-12)
            est["pesos_no_explosivos"] = pmax < 5.0
            est["pesos_no_desaparecen"] = pmin > 1e-6
            est["sin_nan"] = bool(not np.isnan(self.pesos).any())
            est["sin_inf"] = bool(not np.isinf(self.pesos).any())
        return est

    def resumen_rendimiento(self) -> Dict[str, Any]:
        return {
            "forwards": self.contador_forward,
            "backwards": self.contador_backward,
            "t_forward_total_s": self.tiempo_forward_acum,
            "t_backward_total_s": self.tiempo_backward_acum,
        }

    def reiniciar_metricas(self) -> None:
        self.historial_activaciones.clear()
        self.historial_gradientes.clear()
        self.historial_loss.clear()
        self.contador_forward = 0
        self.contador_backward = 0
        self.tiempo_forward_acum = 0.0
        self.tiempo_backward_acum = 0.0