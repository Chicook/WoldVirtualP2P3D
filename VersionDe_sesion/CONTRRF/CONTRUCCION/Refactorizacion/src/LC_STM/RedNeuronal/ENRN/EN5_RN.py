"""EN5_RN - Neurona de entrada regularizada (fachada extendida).

La implementacion base vive en ``SBTM_EN5_RN.sbrtm_EN5_RN1`` (clase principal
con la clase anidada ``Regularizador``, optimizador unificado y decoradores
``_instrumentar`` / ``_requiere_pesos``) y las utilidades extendidas en
``SBTM_EN5_RN.sbrtm_EN5_RN2`` (clase ``NeuronaEntradaRegularizadaExt`` con
``Metricas``/``Serializador`` anidadas: poda, normas, estadisticas,
estabilidad y persistencia JSON). Este modulo NO duplica esa logica: solo
anade lo que no esta en esos dos modulos:

  - inicializacion ``xavier`` / ``lecun`` ademas de ``he``
  - ``forward_batch`` y ``grad_entrada``
  - ``entrenar_paso`` (forward + backward + paso del optimizador)

Ejemplo:
    >>> n = NeuronaEntradaRegularizada(8, 4, lambda_l2=0.01)
    >>> n.entrenar_paso(np.zeros((3, 8)), np.zeros((3, 4)))
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from .SBTM_EN5_RN.sbrtm_EN5_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        _dtype,
        _instrumentar,
        _now,
        _requiere_pesos,
    )
    from .SBTM_EN5_RN.sbrtm_EN5_RN2 import (
        NeuronaEntradaRegularizadaExt as _NeuronaEntradaRegularizadaBase,
    )
except ImportError:  # ejecucion directa sin paquete
    from SBTM_EN5_RN.sbrtm_EN5_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        _dtype,
        _instrumentar,
        _now,
        _requiere_pesos,
    )
    from SBTM_EN5_RN.sbrtm_EN5_RN2 import (
        NeuronaEntradaRegularizadaExt as _NeuronaEntradaRegularizadaBase,
    )

try:  # mantiene la precision configurada por el paquete ENRN
    from . import LUCIA_CONFIG as _CONFIG_ENRN

    if isinstance(_CONFIG_ENRN, dict):
        LUCIA_CONFIG.update(_CONFIG_ENRN)
except ImportError:
    pass

__all__ = [
    "NeuronaEntradaBase",
    "NeuronaEntradaRegularizada",
    "LUCIA_CONFIG",
    "_dtype",
    "_now",
]


class NeuronaEntradaRegularizada(_NeuronaEntradaRegularizadaBase):
    """EN5 con utilidades extra sobre la base regularizada importada."""

    _ALIAS_OPTIMIZADOR = {
        "sgd_l2": "sgd",
        "sgd_momentum": "sgd_momento",
        "momentum": "sgd_momento",
    }

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntradaRegularizada",
                 lambda_l2: float = 0.01,
                 lambda_l1: float = 0.0,
                 factor_escala: float = 1.0,
                 learning_rate: float = 0.001,
                 optimizador: str = "adamw",
                 beta1: float = 0.9,
                 beta2: float = 0.999,
                 epsilon: float = 1e-8,
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
            lambda_l2=lambda_l2, lambda_l1=lambda_l1,
            factor_escala=factor_escala, learning_rate=learning_rate,
            optimizador=algoritmo, beta1=beta1, beta2=beta2,
            epsilon=epsilon, grad_clip=grad_clip, lr_decay=lr_decay,
            lr_min=lr_min, usar_cache_forward=usar_cache_forward,
            semilla=semilla, capacidad_historial=capacidad_historial,
        )

    # ------------------------------------------------------------------
    # Inicializacion: he (base) + xavier / lecun (extra)
    # ------------------------------------------------------------------
    def inicializar_pesos(self, modo: str = "he") -> None:
        modo = str(modo).lower()
        if modo == "he":
            super().inicializar_pesos()
            return
        if modo == "xavier":
            lim = math.sqrt(6.0 / (self.input_size + self.output_size)) * self.factor_escala
            pesos = self.rng.uniform(-lim, lim, (self.input_size, self.output_size))
        elif modo == "lecun":
            std = math.sqrt(1.0 / self.input_size) * self.factor_escala
            pesos = self.rng.normal(0.0, std, (self.input_size, self.output_size))
        else:
            raise ValueError(f"modo {modo} desconocido")
        self.pesos = pesos.astype(self.dt)
        self.sesgo = np.zeros(self.output_size, dtype=self.dt)
        self.varianza_real = float(np.var(self.pesos))
        self._estado.clear()
        self._paso = 0
        self._cache_entrada = None
        self._cache_norm = None
        self._registrar_norma()
        self._emit("init", {"modo": modo})

    # ------------------------------------------------------------------
    # Propagacion extra
    # ------------------------------------------------------------------
    def forward_batch(self, lote: List[np.ndarray]) -> List[np.ndarray]:
        return [self.forward(x) for x in lote]

    @_instrumentar("backward")
    @_requiere_pesos
    def backward(self, gradiente_salida: np.ndarray,
                 entrada: Optional[np.ndarray] = None
                 ) -> Tuple[np.ndarray, np.ndarray]:
        """Devuelve (grad_pesos, grad_sesgo) SIN aplicar el optimizador.

        La regularizacion L1/L2 y el clipping del paso se aplican en
        ``paso_optimizador`` (unica fuente, clase ``Regularizador``).
        """
        g = np.asarray(gradiente_salida, dtype=np.float64)
        if g.ndim == 1:
            g = g.reshape(1, -1)
        if g.ndim != 2 or g.shape[1] != self.output_size:
            raise ValueError(
                f"gradiente dim {g.shape[-1]} != output_size {self.output_size}"
            )
        if entrada is not None:
            xin = self._preparar(entrada) * self.factor_escala
        elif self._cache_norm is not None:
            xin = self._cache_norm
        else:
            raise ValueError("sin entrada ni cache forward")

        b = max(1, xin.shape[0])
        g = self._clip(g)
        gp = self._clip(np.dot(xin.T, g) / b)
        gb = self._clip(np.sum(g, axis=0) / b)

        self.historial_gradientes.append({
            "pesos": gp.astype(self.dt).copy(),
            "sesgo": gb.astype(self.dt).copy(),
            "norma_pesos": float(np.linalg.norm(gp)),
            "norma_sesgo": float(np.linalg.norm(gb)),
        })
        return gp.astype(self.dt), gb.astype(self.dt)

    @_requiere_pesos
    def grad_entrada(self, gradiente_salida: np.ndarray) -> np.ndarray:
        g = np.asarray(gradiente_salida, dtype=np.float64)
        if g.ndim == 1:
            g = g.reshape(1, -1)
        return (np.dot(g, self.pesos.T) * self.factor_escala).astype(self.dt)

    def paso_optimizador(self, grad_pesos: np.ndarray,
                         grad_sesgo: np.ndarray) -> Dict[str, float]:
        """Delega en el optimizador unificado y conserva la clave 'reg'."""
        info = super().paso_optimizador(grad_pesos, grad_sesgo)
        info["reg"] = info.get("penalizacion", self.penalizacion())
        return info

    def entrenar_paso(self, entrada: np.ndarray,
                      objetivo: np.ndarray) -> Dict[str, float]:
        pred = self.forward(entrada)
        y = np.asarray(objetivo, dtype=self.dt)
        if y.ndim == 1:
            y = y.reshape(1, -1)
        n = max(1, pred.shape[0])
        err = (pred - y) / n
        loss_data = float(np.mean((pred - y) ** 2))
        loss = loss_data + self.penalizacion() / n
        gp, gb = self.backward(err, entrada)
        opt = self.paso_optimizador(gp, gb)
        self.historial_loss.append(loss)
        if loss < self.mejor_loss:
            self.mejor_loss = loss
        return {"loss": loss, "loss_data": loss_data, **opt}

    # Podar/norma_actual, estadisticas, estabilidad, resumen de rendimiento,
    # reinicio de metricas y persistencia JSON (a_dict/guardar/cargar) se
    # heredan de NeuronaEntradaRegularizadaExt (SBTM_EN5_RN2).