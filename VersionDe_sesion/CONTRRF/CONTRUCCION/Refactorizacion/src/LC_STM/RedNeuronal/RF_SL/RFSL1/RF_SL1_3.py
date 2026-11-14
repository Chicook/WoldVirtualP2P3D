"""
RF_SL1_3.py - Random Forest Avanzado
Optimizado con clases inline y estructura eficiente.
"""

import numpy as np
import logging
import time
import pickle
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RandomForestOptimizer y utilidades: fuente unica en el modulo especializado
# RF_SL_SBRTM_RF_SL1_3/RF_SL_SBRTM_RF_SL1_3_1.py.
#
# Se importan sus clases (arbol CART con hojas vectoriales, Random Forest con
# OOB real y TabM/BatchEnsemble) junto con sus funciones nuevas. El resto del
# archivo conserva sus metodos de compatibilidad (evaluate, estadisticas,
# save/load, summary...) sobre la implementacion importada.
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_SL1_3.RF_SL_SBRTM_RF_SL1_3_1 import (
        NeuronaArbolAleatorio,
        NeuronaBosqueAleatorio,
        NeuronaMemoriaBase,
        NeuronaTabM,
        RandomForestOptimizer as _RandomForestOptimizerBase,
        benchmark_modelo,
        cargar_modelo,
        crear_neurona,
        entrenar_y_evaluar,
        guardar_modelo,
    )
except (ImportError, ValueError):
    # Fallback por ruta para cargas por fichero o sin paquete padre.
    import importlib.util as _ilu
    import os as _os
    import sys as _sys

    _CLAVE_MODULO = "_rf_sl1_3_forest_import"
    _modulo_bosque = _sys.modules.get(_CLAVE_MODULO)
    if _modulo_bosque is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF_SL1_3",
            "RF_SL_SBRTM_RF_SL1_3_1.py",
        )
        _especificacion = _ilu.spec_from_file_location(_CLAVE_MODULO, _ruta_modulo)
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo_bosque = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo_bosque
        _especificacion.loader.exec_module(_modulo_bosque)
    NeuronaArbolAleatorio = _modulo_bosque.NeuronaArbolAleatorio
    NeuronaBosqueAleatorio = _modulo_bosque.NeuronaBosqueAleatorio
    NeuronaMemoriaBase = _modulo_bosque.NeuronaMemoriaBase
    NeuronaTabM = _modulo_bosque.NeuronaTabM
    _RandomForestOptimizerBase = _modulo_bosque.RandomForestOptimizer
    benchmark_modelo = _modulo_bosque.benchmark_modelo
    cargar_modelo = _modulo_bosque.cargar_modelo
    crear_neurona = _modulo_bosque.crear_neurona
    entrenar_y_evaluar = _modulo_bosque.entrenar_y_evaluar
    guardar_modelo = _modulo_bosque.guardar_modelo


class RandomForestOptimizer(_RandomForestOptimizerBase):
    """Bosque real (hojas vectoriales + OOB) con la API de RF_SL1_3."""

    def _aggregate_predictions(self, X: np.ndarray) -> np.ndarray:
        if not self._trees: return np.zeros(len(X))
        preds = np.zeros(len(X))
        for tree in self._trees:
            pred = tree.predict(X) if hasattr(tree, 'predict') else self.forward(X)
            preds += pred.flatten() if pred.ndim == 1 else pred[:, 0]
        return preds / len(self._trees)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        return super().evaluate(X, y)

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats['n_trees'] = self._n_trees
        stats['max_depth'] = self._max_depth
        stats['min_samples_split'] = self._min_samples_split
        stats['bootstrap'] = self._bootstrap
        stats['is_fitted'] = self._is_fitted
        stats['oob_score'] = self._oob_score
        stats['n_trees_built'] = len(self._trees)
        stats['training_time'] = self._training_time
        stats['n_features'] = self._n_features or self.input_size
        if self._feature_importances is not None:
            stats['top_feature'] = int(np.argmax(self._feature_importances))
        if self._convergence_history:
            stats['final_loss'] = float(self._convergence_history[-1])
        return stats

    def verificar_estabilidad(self) -> Dict[str, Any]:
        estado = dict(super().verificar_estabilidad())
        estado['pesos_inicializados'] = self.pesos is not None
        return estado

    def save(self, filepath: str) -> None:
        """Serializa el modelo completo (arboles incluidos)."""
        guardar_modelo(self, filepath)

    def load(self, filepath: str) -> None:
        """Carga un modelo completo serializado previamente con save()."""
        cargado = cargar_modelo(filepath)
        self.__dict__.update(cargado.__dict__)

    def get_config(self) -> Dict[str, Any]:
        return {
            'nombre': self.nombre, 'input_size': self.input_size, 'output_size': self.output_size,
            'n_trees': self._n_trees, 'max_depth': self._max_depth,
            'min_samples_split': self._min_samples_split, 'bootstrap': self._bootstrap,
        }

    def summary(self) -> str:
        cfg = self.get_config()
        stats = self.obtener_estadisticas()
        return "\n".join([
            f"=== {cfg['nombre']} ===",
            f"Trees: {cfg['n_trees']}, Depth: {cfg['max_depth']}",
            f"Input: {cfg['input_size']}, Output: {cfg['output_size']}",
            f"Fitted: {stats.get('is_fitted', False)}, OOB: {stats.get('oob_score', 0):.4f}",
            f"Trees built: {stats.get('n_trees_built', 0)}, Params: {self.params_count()}",
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(ent={self.input_size},sal={self.output_size})"


class DecisionTree:
    def __init__(self, max_depth: int = 10, min_samples_split: int = 2):
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self._tree: Optional[Dict] = None
        self.feature_importances_: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> 'DecisionTree':
        self._tree = self._build_tree(X, y, depth=0)
        self.feature_importances_ = np.zeros(X.shape[1])
        self._compute_importances(self._tree, X.shape[1])
        return self

    def _build_tree(self, X: np.ndarray, y: np.ndarray, depth: int) -> Dict:
        n = len(X)
        if depth >= self.max_depth or n < self.min_samples_split or len(np.unique(y)) == 1:
            return {'leaf': True, 'value': float(np.mean(y))}
        feat, thresh, gain = self._best_split(X, y)
        if gain < 1e-8: return {'leaf': True, 'value': float(np.mean(y))}
        left_mask = X[:, feat] <= thresh
        return {
            'leaf': False, 'feature': feat, 'threshold': thresh, 'gain': float(gain),
            'left': self._build_tree(X[left_mask], y[left_mask], depth + 1),
            'right': self._build_tree(X[~left_mask], y[~left_mask], depth + 1),
        }

    def _best_split(self, X: np.ndarray, y: np.ndarray) -> Tuple[int, float, float]:
        best_f, best_t, best_g = 0, 0.0, 0.0
        parent_var = float(np.var(y))
        for f in range(X.shape[1]):
            for t in np.unique(X[:, f]):
                lm = X[:, f] <= t
                if lm.sum() == 0 or lm.sum() == len(y): continue
                lv = float(np.var(y[lm])); rv = float(np.var(y[~lm]))
                n_l, n_r = lm.sum(), (~lm).sum()
                gain = parent_var - (n_l * lv + n_r * rv) / len(y)
                if gain > best_g: best_g = gain; best_f = f; best_t = float(t)
        return best_f, best_t, best_g

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.array([self._pred_one(x, self._tree) for x in X])

    def _pred_one(self, x: np.ndarray, node: Dict) -> float:
        if node['leaf']: return node['value']
        if x[node['feature']] <= node['threshold']: return self._pred_one(x, node['left'])
        return self._pred_one(x, node['right'])

    def _compute_importances(self, node: Dict, n_features: int) -> None:
        if node.get('leaf'): return
        if 'feature' in node:
            self.feature_importances_[node['feature']] += node.get('gain', 0)
            self._compute_importances(node.get('left', {}), n_features)
            self._compute_importances(node.get('right', {}), n_features)


class BootstrapSampler:
    def __init__(self, ratio: float = 0.8, random_state: int = 42):
        self.ratio = ratio
        self.rng = np.random.default_rng(random_state)

    def sample(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        n = len(X)
        size = max(1, int(n * self.ratio))
        idx = self.rng.choice(n, size=size, replace=True)
        oob = np.setdiff1d(np.arange(n), idx)
        return X[idx], y[idx], oob

    def sample_indices(self, n: int) -> Tuple[np.ndarray, np.ndarray]:
        size = max(1, int(n * self.ratio))
        idx = self.rng.choice(n, size=size, replace=True)
        oob = np.setdiff1d(np.arange(n), idx)
        return idx, oob


class FeatureBagger:
    def __init__(self, n_features: Optional[int] = None, random_state: int = 42):
        self.n_features = n_features
        self.rng = np.random.default_rng(random_state)
        self._selected: Optional[np.ndarray] = None

    def select(self, n_total: int) -> np.ndarray:
        nf = min(self.n_features or n_total, n_total)
        self._selected = self.rng.choice(n_total, size=nf, replace=False)
        return self._selected

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self._selected is None: raise RuntimeError("No hay features seleccionados")
        return X[:, self._selected]

    def get_mask(self, n_total: int) -> np.ndarray:
        mask = np.zeros(n_total, dtype=bool)
        if self._selected is not None: mask[self._selected] = True
        return mask


class PredictionVoter:
    def __init__(self):
        self._votes: List[np.ndarray] = []
        self._weights: List[float] = []

    def vote(self, prediction: np.ndarray, weight: float = 1.0) -> None:
        self._votes.append(prediction)
        self._weights.append(weight)

    def majority_vote(self) -> np.ndarray:
        if not self._votes: return np.zeros(1)
        stacked = np.array(self._votes)
        mean_pred = np.mean(stacked, axis=0)
        return mean_pred

    def weighted_vote(self) -> np.ndarray:
        if not self._votes: return np.zeros(1)
        w = np.array(self._weights) / max(1e-8, sum(self._weights))
        return np.average(np.array(self._votes), axis=0, weights=w)

    def reset(self) -> None:
        self._votes.clear()
        self._weights.clear()

    @property
    def n_votes(self) -> int: return len(self._votes)


class RandomForestTrainer:
    def __init__(self, n_trees: int = 100, max_depth: int = 10,
                 subsample_ratio: float = 0.8, n_features: Optional[int] = None):
        self.n_trees = n_trees
        self.max_depth = max_depth
        self.subsample_ratio = subsample_ratio
        self.n_features = n_features
        self.sampler = BootstrapSampler(self.subsample_ratio)
        self.bagger = FeatureBagger(self.n_features)
        self.voter = PredictionVoter()
        self._trees: List[DecisionTree] = []
        self._history: List[float] = []

    def fit(self, X: np.ndarray, y: np.ndarray) -> List[float]:
        self._trees.clear()
        self._history.clear()
        n = len(X)
        for i in range(self.n_trees):
            Xs, ys, oob = self.sampler.sample(X, y)
            tree = DecisionTree(max_depth=self.max_depth)
            tree.fit(Xs, ys)
            self._trees.append(tree)
            pred = tree.predict(X)
            self.voter.vote(pred.flatten() if pred.ndim == 1 else pred[:, 0])
            loss = float(np.mean((pred.flatten() - y.flatten()) ** 2))
            self._history.append(loss)
        return self._history

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.voter.majority_vote() if self.voter.n_votes > 0 else np.zeros(len(X))

    def get_trees(self) -> List[DecisionTree]: return self._trees.copy()

    @property
    def n_trees_built(self) -> int: return len(self._trees)

    @property
    def history(self) -> List[float]: return self._history.copy()


def create_random_forest_optimizer(input_size: int = 4, output_size: int = 8) -> RandomForestOptimizer:
    return RandomForestOptimizer(input_size=input_size, output_size=output_size)


if __name__ == "__main__":
    logger.info("RF_SL1_3.py cargado exitosamente")
