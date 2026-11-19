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


class NeuronaMemoriaBase:
    """Clase base de neurona con memoria acotada de activaciones y gradientes."""

    def __init__(self, input_size: int, output_size: int, nombre: str = "Neurona"):
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.pesos: Optional[np.ndarray] = None
        self.sesgo: Optional[np.ndarray] = None
        self.historial_activaciones: Deque[np.ndarray] = deque(maxlen=100)
        self.historial_gradientes: Deque[Dict[str, np.ndarray]] = deque(maxlen=100)
        self.pasos: int = 0

    def inicializar_pesos(self) -> None:
        raise NotImplementedError

    def forward(self, e: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'pasos': self.pasos,
            'historial_activaciones_len': len(self.historial_activaciones),
            'historial_gradientes_len': len(self.historial_gradientes),
        }
        if self.pesos is not None:
            stats['pesos_shape'] = self.pesos.shape
            stats['pesos_size'] = self.pesos.size
        if self.sesgo is not None:
            stats['sesgo_shape'] = self.sesgo.shape
        return stats

    def resetear_historial(self) -> None:
        self.historial_activaciones.clear()
        self.historial_gradientes.clear()

    def info(self) -> str:
        return f"{self.nombre}(in={self.input_size},out={self.output_size},pasos={self.pasos})"

    def params_count(self) -> int:
        total = 0
        if self.pesos is not None:
            total += self.pesos.size
        if self.sesgo is not None:
            total += self.sesgo.size
        return total


class TreeBuilder:
    """Constructor de árboles de decisión por reducción de varianza."""

    def __init__(self, max_depth: int = 3, min_samples_split: int = 2):
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self._tree: Optional[Dict] = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> Dict:
        self._tree = self._build_tree(X, y, depth=0)
        return self._tree

    def _build_tree(self, X: np.ndarray, y: np.ndarray, depth: int) -> Dict:
        n_samples = len(X)
        if depth >= self.max_depth or n_samples < self.min_samples_split:
            return {'leaf': True, 'value': float(np.mean(y))}
        best_feat, best_thresh, best_gain = self._find_best_split(X, y)
        if best_gain < 1e-8:
            return {'leaf': True, 'value': float(np.mean(y))}
        left_mask = X[:, best_feat] <= best_thresh
        right_mask = ~left_mask
        return {
            'leaf': False,
            'feature': best_feat,
            'threshold': best_thresh,
            'left': self._build_tree(X[left_mask], y[left_mask], depth + 1),
            'right': self._build_tree(X[right_mask], y[right_mask], depth + 1),
            'gain': float(best_gain),
            'n_samples': n_samples,
        }

    def _find_best_split(self, X: np.ndarray, y: np.ndarray) -> Tuple[int, float, float]:
        best_feat, best_thresh, best_gain = 0, 0.0, 0.0
        parent_var = float(np.var(y))
        n_features = X.shape[1]
        for feat in range(n_features):
            thresholds = np.unique(X[:, feat])
            for thresh in thresholds:
                left_mask = X[:, feat] <= thresh
                if left_mask.sum() == 0 or left_mask.sum() == len(y):
                    continue
                left_var = float(np.var(y[left_mask]))
                right_var = float(np.var(y[~left_mask]))
                n_l, n_r = left_mask.sum(), (~left_mask).sum()
                gain = parent_var - (n_l * left_var + n_r * right_var) / len(y)
                if gain > best_gain:
                    best_gain = gain
                    best_feat = feat
                    best_thresh = float(thresh)
        return best_feat, best_thresh, best_gain

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._tree is None:
            raise RuntimeError("Tree no ajustado")
        return np.array([self._predict_one(x, self._tree) for x in X])

    def _predict_one(self, x: np.ndarray, node: Dict) -> float:
        if node['leaf']:
            return node['value']
        if x[node['feature']] <= node['threshold']:
            return self._predict_one(x, node['left'])
        return self._predict_one(x, node['right'])


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
