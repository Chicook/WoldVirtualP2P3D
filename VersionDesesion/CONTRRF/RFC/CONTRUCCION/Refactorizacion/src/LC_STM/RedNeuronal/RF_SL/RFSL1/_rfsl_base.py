"""
_rfsl_base.py - Base y estructuras auxiliares compartidas para RF_SL / RFSL1.
=============================================================================
Contiene las clases base y helpers comunes de optimización supervisada y boosting:
  - NeuronaMemoriaBase: clase base para almacenamiento y tracking de gradientes.
  - TreeBuilder: generador y divisor de árboles de decisión por varianza.
  - LossCalculator: cálculo y gradientes de funciones de pérdida (MSE, MAE, Huber, Log).
  - Sampler: submuestreo aleatorio de datasets e índices.
  - FeatureSelector: selección y proyección de atributos.
  - PredictionAggregator: acumulador y ponderador de predicciones iterativas.
"""
from __future__ import annotations
import numpy as np
from collections import deque
from typing import Dict, Any, List, Optional, Tuple, Deque


# ---------------------------------------------------------------------------
# NeuronaMemoriaBase y TreeBuilder: fuente unica en el modulo especializado
# RF_SL_SBRTM_RF/RF_SL_SNRTM__rfsl_base1.py.
#
# Se importan aqui (en lugar de redefinirlos) para no duplicar codigo y poder
# usar sus mejoras adicionales:
#   - NeuronaMemoriaBase: historial de perdidas, estadisticas ampliadas,
#     verificar_estabilidad() y registro unificado de gradientes.
#   - TreeBuilder: umbrales por cuantiles, min_samples_leaf/min_gain,
#     importancias de atributos normalizadas, profundidad_real() y
#     obtener_estadisticas().
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF.RF_SL_SNRTM__rfsl_base1 import (
        NeuronaMemoriaBase,
        TreeBuilder,
    )
except (ImportError, ValueError):
    # Fallback por ruta: permite cargar este modulo aislado (sin paquete),
    # por ejemplo desde el importador embebido de RF_SL_SBRTM_IMPORT.
    import importlib.util as _ilu
    import os as _os
    import sys as _sys

    _CLAVE_MODULO = "_rf_snrtm_base_import"
    _modulo = _sys.modules.get(_CLAVE_MODULO)
    if _modulo is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF",
            "RF_SL_SNRTM__rfsl_base1.py",
        )
        _especificacion = _ilu.spec_from_file_location(_CLAVE_MODULO, _ruta_modulo)
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo
        _especificacion.loader.exec_module(_modulo)
    NeuronaMemoriaBase = _modulo.NeuronaMemoriaBase  # type: ignore[no-redef]
    TreeBuilder = _modulo.TreeBuilder  # type: ignore[no-redef]


class LossCalculator:
    """Calculador de funciones de pérdida y sus gradientes analíticos."""

    def __init__(self, loss_type: str = "mse"):
        self.loss_type = loss_type

    def compute(self, pred: np.ndarray, target: np.ndarray) -> float:
        if self.loss_type == "mse":
            return float(np.mean((pred - target) ** 2))
        if self.loss_type == "mae":
            return float(np.mean(np.abs(pred - target)))
        if self.loss_type == "huber":
            delta = 1.0
            abs_err = np.abs(pred - target)
            quadratic = np.minimum(abs_err, delta)
            linear = abs_err - quadratic
            return float(np.mean(0.5 * quadratic ** 2 + delta * linear))
        if self.loss_type == "log":
            p = np.clip(pred, 1e-8, 1 - 1e-8)
            return float(-np.mean(target * np.log(p) + (1 - target) * np.log(1 - p)))
        if self.loss_type == "smoothed_l1":
            return self.huber_loss(pred, target)
        return float(np.mean((pred - target) ** 2))

    def gradient(self, pred: np.ndarray, target: np.ndarray) -> np.ndarray:
        diff = pred - target
        if self.loss_type == "mse":
            return diff
        if self.loss_type == "huber":
            delta = 1.0
            abs_diff = np.abs(diff)
            return np.where(abs_diff <= delta, diff, delta * np.sign(diff))
        if self.loss_type == "log":
            return (pred - target) / np.clip(pred * (1 - pred), 1e-8, None)
        return diff

    @staticmethod
    def huber_loss(pred: np.ndarray, target: np.ndarray, delta: float = 1.0) -> float:
        abs_err = np.abs(pred - target)
        quadratic = np.minimum(abs_err, delta)
        linear = abs_err - quadratic
        return float(np.mean(0.5 * quadratic ** 2 + delta * linear))

    @staticmethod
    def masked_loss(pred: np.ndarray, target: np.ndarray, mask: np.ndarray) -> float:
        if mask.sum() == 0:
            return 0.0
        return float(np.mean((pred[mask] - target[mask]) ** 2))


class Sampler:
    """Muestreador de instancias e índices con ratio configurable."""

    def __init__(self, subsample: float = 1.0, random_state: int = 42):
        self.subsample = subsample
        self.rng = np.random.default_rng(random_state)

    def sample(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self.subsample >= 1.0:
            return X, y
        n = len(X)
        size = max(1, int(n * self.subsample))
        idx = self.rng.choice(n, size=size, replace=False)
        return X[idx], y[idx]

    def sample_indices(self, n: int) -> np.ndarray:
        if self.subsample >= 1.0:
            return np.arange(n)
        size = max(1, int(n * self.subsample))
        return self.rng.choice(n, size=size, replace=False)


class FeatureSelector:
    """Selector de subconjuntos de atributos."""

    def __init__(self, n_features: Optional[int] = None, random_state: int = 42):
        self.n_features = n_features
        self.rng = np.random.default_rng(random_state)
        self._selected: Optional[np.ndarray] = None

    def select(self, X: np.ndarray, n_features: Optional[int] = None) -> np.ndarray:
        nf = n_features or self.n_features or X.shape[1]
        nf = min(nf, X.shape[1])
        self._selected = self.rng.choice(X.shape[1], size=nf, replace=False)
        return self._selected

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self._selected is None:
            raise RuntimeError("No hay features seleccionados")
        return X[:, self._selected]

    def get_mask(self, n_features: int) -> np.ndarray:
        mask = np.zeros(n_features, dtype=bool)
        if self._selected is not None:
            mask[self._selected] = True
        return mask


class PredictionAggregator:
    """Agregador ponderado de predicciones sucesivas."""

    def __init__(self, learning_rate: float = 0.1):
        self.learning_rate = learning_rate
        self._predictions: List[np.ndarray] = []
        self._weights: List[float] = []

    def add_prediction(self, prediction: np.ndarray, weight: float = 1.0) -> None:
        self._predictions.append(prediction)
        self._weights.append(weight)

    def aggregate(self) -> np.ndarray:
        if not self._predictions:
            return np.zeros(1)
        result = np.zeros_like(self._predictions[0], dtype=np.float64)
        for pred, w in zip(self._predictions, self._weights):
            result += self.learning_rate * w * pred.astype(np.float64)
        return result

    def weighted_aggregate(self, weights: List[float]) -> np.ndarray:
        if not self._predictions:
            return np.zeros(1)
        result = np.zeros_like(self._predictions[0], dtype=np.float64)
        for pred, w in zip(self._predictions, weights):
            result += self.learning_rate * w * pred.astype(np.float64)
        return result

    def reset(self) -> None:
        self._predictions.clear()
        self._weights.clear()

    @property
    def n_predictions(self) -> int:
        return len(self._predictions)
