"""EN8_RN - Neurona de entrada ReLU (fachada extendida).

La implementacion base vive en ``SBTM_EN8_RN.sbrtm_EN8_RN1`` (clase
``NeuronaEntradaReLU`` con ``Activaciones`` y ``Optimizador`` anidados,
decoradores y estadisticas) y este modulo NO la duplica. Solo anade:

  - alias de optimizador heredados (``sgd_momentum`` -> ``sgd_momento``)
  - claves historicas en las estadisticas (``forwards``/``backwards``,
    ``paso``, ``optimizador`` como nombre, ``ultima_loss`` y tiempos medios)
  - ``verificar_estabilidad`` ampliado y ``resumen_rendimiento``
  - ``reiniciar_metricas`` (solo metricas, sin tocar pesos ni optimizador)

Se heredan del modulo base ``forward``, ``forward_batch``, ``backward``,
``grad_entrada``, ``paso_optimizador``, ``entrenar_paso``, ``penalizacion``,
``registrar_loss``, ``resetear`` y la persistencia ``a_dict``/``guardar``/
``cargar``.

Ejemplo:
    >>> n = NeuronaEntradaReLU(8, 4, tipo_relu="leaky_relu")
    >>> n.entrenar_paso(np.zeros((3, 8)), np.zeros((3, 4)))
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

try:
    from .SBTM_EN8_RN.sbrtm_EN8_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        NeuronaEntradaReLU as _NeuronaEntradaReLUBase,
        _RingBuffer,
        _dtype,
        _now,
        _sigmoid,
        actualizar_config,
    )
except ImportError:  # ejecucion directa sin paquete
    from SBTM_EN8_RN.sbrtm_EN8_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        NeuronaEntradaReLU as _NeuronaEntradaReLUBase,
        _RingBuffer,
        _dtype,
        _now,
        _sigmoid,
        actualizar_config,
    )

try:  # mantiene la precision configurada por el paquete ENRN
    from . import LUCIA_CONFIG as _CONFIG_ENRN

    if isinstance(_CONFIG_ENRN, dict):
        LUCIA_CONFIG.update(_CONFIG_ENRN)
except ImportError:
    pass

__all__ = [
    "NeuronaEntradaBase",
    "NeuronaEntradaReLU",
    "LUCIA_CONFIG",
    "actualizar_config",
    "_RingBuffer",
    "_dtype",
    "_now",
    "_sigmoid",
]


class NeuronaEntradaReLU(_NeuronaEntradaReLUBase):
    """EN8 con utilidades extra sobre la base ReLU importada."""

    _ALIAS_OPTIMIZADOR = {
        "sgd_momentum": "sgd_momento",
        "momentum": "sgd_momento",
        "sgd_l2": "sgd",
    }

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntradaReLU",
                 tipo_relu: str = "relu",
                 alpha: float = 0.01,
                 factor_escala: float = 1.0,
                 learning_rate: float = 0.001,
                 optimizador: str = "adam",
                 beta1: float = 0.9,
                 beta2: float = 0.999,
                 epsilon: float = 1e-8,
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
            tipo_relu=tipo_relu, alpha=alpha, factor_escala=factor_escala,
            learning_rate=learning_rate, optimizador=algoritmo,
            beta1=beta1, beta2=beta2, epsilon=epsilon,
            weight_decay=weight_decay, grad_clip=grad_clip,
            lr_decay=lr_decay, lr_min=lr_min,
            usar_cache_forward=usar_cache_forward,
            semilla=semilla, capacidad_historial=capacidad_historial,
        )

    # ------------------------------------------------------------------
    # Metricas (amplian las de la base, sin reimplementarlas)
    # ------------------------------------------------------------------
    def obtener_estadisticas(self, completas: bool = False) -> Dict[str, Any]:
        info = super().obtener_estadisticas(completas=completas)
        info["forwards"] = self.contador_forward
        info["backwards"] = self.contador_backward
        info["paso"] = self._paso
        info["optimizador"] = self.algoritmo
        return info

    def obtener_estadisticas_completas(self) -> Dict[str, Any]:
        stats = self.obtener_estadisticas(completas=True)
        stats.update({
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
        if self.pesos is not None:
            pmax = float(np.max(np.abs(self.pesos)))
            pmin = max(float(np.min(np.abs(self.pesos))), 1e-12)
            est["pesos_no_explosivos"] = pmax < 5.0
            est["pesos_no_desaparecen"] = pmin > 1e-6
            est["neuronas_muertas"] = self.tasa_activacion > 0.01
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
