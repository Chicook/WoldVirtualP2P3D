"""EN6_RN - Neurona de entrada con dropout (fachada extendida).

La implementacion base vive en ``SBTM_EN6_RN.sbrtm_EN6_RN1`` (clase
``NeuronaEntradaDropout`` con las clases anidadas ``Dropout`` y ``Optimizador``,
decoradores ``_instrumentar`` / ``_requiere_pesos`` y optimizador unificado
Adam/AdamW/SGD). Este modulo NO duplica esa logica: solo anade lo que la base
no expone:

  - ``forward(entrada, entrenamiento=None)`` con modo explicito por llamada
  - ``inferencia_mc`` (Monte Carlo dropout: media, std y muestras)
  - ``backward`` que devuelve (grad_pesos, grad_sesgo) sin aplicar el paso
  - ``forward_batch``, ``grad_entrada`` y ``entrenar_paso``
  - metricas extendidas y persistencia JSON (``a_dict``/``guardar``/``cargar``)

Ejemplo:
    >>> n = NeuronaEntradaDropout(8, 4, dropout_rate=0.2)
    >>> n.entrenar_paso(np.zeros((3, 8)), np.zeros((3, 4)))
    >>> n.inferencia_mc(np.zeros((3, 8)), pasadas=16)["media"]
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from .SBTM_EN6_RN.sbrtm_EN6_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        NeuronaEntradaDropout as _NeuronaEntradaDropoutBase,
        _dtype,
        _instrumentar,
        _now,
        _requiere_pesos,
    )
except ImportError:  # ejecucion directa sin paquete
    from SBTM_EN6_RN.sbrtm_EN6_RN1 import (
        LUCIA_CONFIG,
        NeuronaEntradaBase,
        NeuronaEntradaDropout as _NeuronaEntradaDropoutBase,
        _dtype,
        _instrumentar,
        _now,
        _requiere_pesos,
    )

try:  # mantiene la precision configurada por el paquete ENRN
    from . import LUCIA_CONFIG as _CONFIG_ENRN

    if isinstance(_CONFIG_ENRN, dict):
        LUCIA_CONFIG.update(_CONFIG_ENRN)
except ImportError:
    pass

__all__ = [
    "NeuronaEntradaBase",
    "NeuronaEntradaDropout",
    "LUCIA_CONFIG",
    "_dtype",
    "_now",
]


class NeuronaEntradaDropout(_NeuronaEntradaDropoutBase):
    """EN6 con utilidades extra sobre la base dropout importada."""

    _ALIAS_OPTIMIZADOR = {
        "sgd_momentum": "sgd_momento",
        "momentum": "sgd_momento",
    }

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaEntradaDropout",
                 dropout_rate: float = 0.1,
                 factor_escala: float = 1.0,
                 modo_entrenamiento: bool = True,
                 dropout_entrada: float = 0.0,
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
            dropout_rate=dropout_rate, factor_escala=factor_escala,
            modo_entrenamiento=modo_entrenamiento, dropout_entrada=dropout_entrada,
            learning_rate=learning_rate, optimizador=algoritmo,
            beta1=beta1, beta2=beta2, epsilon=epsilon,
            weight_decay=weight_decay, grad_clip=grad_clip,
            lr_decay=lr_decay, lr_min=lr_min,
            usar_cache_forward=usar_cache_forward,
            semilla=semilla, capacidad_historial=capacidad_historial,
        )

    # ------------------------------------------------------------------
    # Propagacion extra
    # ------------------------------------------------------------------
    def forward(self, entrada, entrenamiento: Optional[bool] = None) -> np.ndarray:
        """Forward con modo explicito opcional (sin cambiar el estado global)."""
        if entrenamiento is None:
            return super().forward(entrada)
        previo = self.modo_entrenamiento
        previo_dropout = self.dropout.activo
        self.modo_entrenamiento = bool(entrenamiento)
        self.dropout.activo = bool(entrenamiento)
        try:
            return super().forward(entrada)
        finally:
            self.modo_entrenamiento = previo
            self.dropout.activo = previo_dropout

    def forward_batch(self, lote: List[np.ndarray]) -> List[np.ndarray]:
        return [self.forward(x) for x in lote]

    def inferencia_mc(self, entrada: np.ndarray,
                      pasadas: int = 8) -> Dict[str, np.ndarray]:
        """Monte Carlo dropout: media/std de varias pasadas en entrenamiento."""
        n = max(1, int(pasadas))
        outs = [self.forward(entrada, entrenamiento=True) for _ in range(n)]
        arr = np.stack(outs, axis=0)
        return {"media": arr.mean(axis=0), "std": arr.std(axis=0), "muestras": arr}

    @_instrumentar("backward")
    @_requiere_pesos
    def backward(self, gradiente_salida: np.ndarray,
                 entrada: Optional[np.ndarray] = None
                 ) -> Tuple[np.ndarray, np.ndarray]:
        """Devuelve (grad_pesos, grad_sesgo) SIN aplicar el optimizador.

        Las mismas mascaras del forward se reaplican al gradiente; el weight
        decay y el clipping del paso viven en ``paso_optimizador``.
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
            mask_in = self._mask(xin.shape, self.dropout_entrada)
            mask_out = self._mask((xin.shape[0], self.output_size), self.dropout_rate)
            xin = self.dropout.aplicar(xin, mask_in)
        elif self._cache_xin is not None:
            xin = self._cache_xin
            mask_out = self._cache_mask_out
        else:
            raise ValueError("sin entrada ni cache forward")

        g = self.dropout.aplicar(g, mask_out)
        g = self._clip(g)
        b = max(1, xin.shape[0])
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

    def entrenar_paso(self, entrada: np.ndarray,
                      objetivo: np.ndarray) -> Dict[str, float]:
        pred = self.forward(entrada, entrenamiento=True)
        y = np.asarray(objetivo, dtype=self.dt)
        if y.ndim == 1:
            y = y.reshape(1, -1)
        err = (pred - y) / max(1, pred.shape[0])
        loss = float(np.mean((pred - y) ** 2))
        gp, gb = self.backward(err, entrada)
        opt = self.paso_optimizador(gp, gb)
        self.historial_loss.append(loss)
        if loss < self.mejor_loss:
            self.mejor_loss = loss
        return {"loss": loss, **opt}

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

    # ------------------------------------------------------------------
    # Persistencia JSON
    # ------------------------------------------------------------------
    def a_dict(self) -> Dict[str, Any]:
        return {
            "input_size": self.input_size,
            "output_size": self.output_size,
            "nombre": self.nombre,
            "dropout_rate": self.dropout_rate,
            "dropout_entrada": self.dropout_entrada,
            "factor_escala": self.factor_escala,
            "lr_base": self.lr_base,
            "optimizador": self.algoritmo,
            "weight_decay": self.weight_decay,
            "pesos": self.pesos.tolist() if self.pesos is not None else None,
            "sesgo": self.sesgo.tolist() if self.sesgo is not None else None,
        }

    def guardar(self, ruta: str) -> None:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(self.a_dict(), f)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaEntradaDropout":
        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)
        obj = cls(
            data["input_size"], data["output_size"],
            data.get("nombre", "NeuronaEntradaDropout"),
            dropout_rate=data.get("dropout_rate", 0.1),
            dropout_entrada=data.get("dropout_entrada", 0.0),
            factor_escala=data.get("factor_escala", 1.0),
            learning_rate=data.get("lr_base", 0.001),
            optimizador=data.get("optimizador", "adam"),
            weight_decay=data.get("weight_decay", 0.0),
        )
        if data.get("pesos") is not None:
            obj.pesos = np.asarray(data["pesos"], dtype=obj.dt)
            obj.sesgo = np.asarray(data["sesgo"], dtype=obj.dt).reshape(-1)
        return obj