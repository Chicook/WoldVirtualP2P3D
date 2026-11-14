"""
RF_SL1_5.py - Arboles de decision avanzados (puente legado)
===========================================================

Este modulo ya no reimplementa el arbol CART. La implementacion unica vive
en el modulo especializado:

    RF_SL_SBRTM_RF_SL1_5/RF_SL_SBRTM_RF_SL1_5_1.py

Desde alli se importan ``NeuronaArbolDecision``, el adaptador historico
``DecisionTreeOptimizer``, la base compartida ``NeuronaMemoriaBase`` y las
funciones nuevas (fabrica, metricas, benchmark, persistencia y demo). El resto
del archivo conserva las utilidades historicas de compatibilidad
(``TreeSplitter``, ``TreePruner``, ``FeatureImportance``, ``TreeSerializer``,
``CriterionSelector`` y ``TreeEnsemble``), que no duplican ninguna de las
clases importadas.
"""

import logging
import pickle
from typing import Dict, List, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Arbol CART: fuente unica en el modulo especializado RF_SL_SBRTM_RF_SL1_5.
#
# Se importan sus clases (CART con criterios gini/entropy/mse/huber, poda,
# pesos, importancias y serializacion) y sus funciones nuevas. El antiguo
# bloque local de DecisionTreeOptimizer (lineas 61-299) queda sustituido por
# este import, sin dejar una segunda definicion del arbol.
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_SL1_5.RF_SL_SBRTM_RF_SL1_5_1 import (
        LUCIA_DT_CONFIG,
        DecisionTreeOptimizer,
        NeuronaArbolDecision,
        NeuronaMemoriaBase,
        benchmark_modelo,
        cargar_modelo,
        crear_neurona,
        create_decision_tree_optimizer,
        demo,
        entrenar_y_evaluar,
        guardar_modelo,
        tipos_disponibles,
    )
except (ImportError, ValueError):
    # Fallback por ruta para cargas por fichero o sin paquete padre.
    import importlib.util as _ilu
    import os as _os
    import sys as _sys

    _CLAVE_MODULO = "_rf_sl1_5_dt_import"
    _modulo_dt = _sys.modules.get(_CLAVE_MODULO)
    if _modulo_dt is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF_SL1_5",
            "RF_SL_SBRTM_RF_SL1_5_1.py",
        )
        _especificacion = _ilu.spec_from_file_location(_CLAVE_MODULO, _ruta_modulo)
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo_dt = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo_dt
        _especificacion.loader.exec_module(_modulo_dt)
    LUCIA_DT_CONFIG = _modulo_dt.LUCIA_DT_CONFIG
    DecisionTreeOptimizer = _modulo_dt.DecisionTreeOptimizer
    NeuronaArbolDecision = _modulo_dt.NeuronaArbolDecision
    NeuronaMemoriaBase = _modulo_dt.NeuronaMemoriaBase
    benchmark_modelo = _modulo_dt.benchmark_modelo
    cargar_modelo = _modulo_dt.cargar_modelo
    crear_neurona = _modulo_dt.crear_neurona
    create_decision_tree_optimizer = _modulo_dt.create_decision_tree_optimizer
    demo = _modulo_dt.demo
    entrenar_y_evaluar = _modulo_dt.entrenar_y_evaluar
    guardar_modelo = _modulo_dt.guardar_modelo
    tipos_disponibles = _modulo_dt.tipos_disponibles

# Acceso directo a la clase anidada del nucleo matematico del arbol.
NucleoArbol = NeuronaArbolDecision.NucleoArbol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilidades historicas de compatibilidad (no sustituyen al arbol importado)
# ---------------------------------------------------------------------------
class TreeSplitter:
    def __init__(self, criterion: str = "gini"):
        self.criterion = criterion

    def find_best_split(self, X: np.ndarray,
                        y: np.ndarray) -> Tuple[int, float, float]:
        if self.criterion == "gini":
            score_fn = self._gini_score
        elif self.criterion == "entropy":
            score_fn = self._entropy_score
        else:
            score_fn = self._mse_score
        best_f, best_t, best_g = 0, 0.0, 0.0
        parent = score_fn(y)
        for f in range(X.shape[1]):
            for t in np.unique(X[:, f]):
                lm = X[:, f] <= t
                if lm.sum() == 0 or lm.sum() == len(y):
                    continue
                g = parent - (
                    lm.sum() * score_fn(y[lm])
                    + (~lm).sum() * score_fn(y[~lm])
                ) / len(y)
                if g > best_g:
                    best_g = g
                    best_f = f
                    best_t = float(t)
        return best_f, best_t, best_g

    @staticmethod
    def _gini_score(y: np.ndarray) -> float:
        p = np.bincount(y.astype(int)) / max(1, len(y))
        return float(1.0 - np.sum(p ** 2))

    @staticmethod
    def _entropy_score(y: np.ndarray) -> float:
        p = np.bincount(y.astype(int)) / max(1, len(y))
        p = p[p > 0]
        return float(-np.sum(p * np.log2(p)))

    @staticmethod
    def _mse_score(y: np.ndarray) -> float:
        return float(np.var(y))


class TreePruner:
    def __init__(self, min_samples_split: int = 2):
        self.min_samples_split = min_samples_split

    def post_prune(self, tree: Dict, X: np.ndarray,
                   y: np.ndarray) -> Dict:
        if tree.get('leaf'):
            return tree
        left_mask = X[:, tree['feature']] <= tree['threshold']
        tree['left'] = self.post_prune(
            tree['left'], X[left_mask], y[left_mask]
        )
        tree['right'] = self.post_prune(
            tree['right'], X[~left_mask], y[~left_mask]
        )
        if len(X) < self.min_samples_split:
            return {
                'leaf': True,
                'value': float(np.bincount(y.astype(int)).argmax()),
            }
        return tree


class FeatureImportance:
    def __init__(self, n_features: int):
        self.n_features = n_features
        self._importances = np.zeros(n_features)

    def add(self, features: np.ndarray, gains: np.ndarray) -> None:
        for f, g in zip(features, gains):
            self._importances[int(f)] += float(g)

    def get(self) -> np.ndarray:
        return self._importances.copy()

    def top_k(self, k: int = 3) -> np.ndarray:
        return np.argsort(self._importances)[-k:][::-1]

    def normalized(self) -> np.ndarray:
        total = self._importances.sum()
        return self._importances / max(1e-8, total)


class TreeSerializer:
    @staticmethod
    def save(tree: Dict, filepath: str) -> None:
        with open(filepath, 'wb') as f:
            pickle.dump(tree, f)

    @staticmethod
    def load(filepath: str) -> Dict:
        with open(filepath, 'rb') as f:
            return pickle.load(f)


class CriterionSelector:
    @staticmethod
    def get_criterion(name: str) -> str:
        valid = ["gini", "entropy", "mse"]
        return name if name in valid else "gini"

    @staticmethod
    def list_criteria() -> List[str]:
        return ["gini", "entropy", "mse"]


class TreeEnsemble:
    def __init__(self, n_trees: int = 10):
        self.n_trees = n_trees
        self._trees: List[DecisionTreeOptimizer] = []

    def add_tree(self, tree: DecisionTreeOptimizer) -> None:
        self._trees.append(tree)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._trees:
            return np.zeros(len(X))
        preds = np.zeros(len(X))
        for tree in self._trees:
            preds += tree.predict(X).flatten()
        return preds / len(self._trees)

    def get_n_trees(self) -> int:
        return len(self._trees)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> float:
        pred = self.predict(X)
        return float(np.mean(np.abs(pred - y.flatten())))

    def feature_importances_global(self, n_features: int) -> np.ndarray:
        imp = np.zeros(n_features)
        for tree in self._trees:
            if tree._feature_importances is not None:
                imp += tree._feature_importances
        return imp / max(1, len(self._trees))


# ``create_decision_tree_optimizer`` se importa del modulo especializado para
# no duplicar la fabrica. Se conserva el mismo nombre y firma historica.


if __name__ == "__main__":
    logger.info("RF_SL1_5.py cargado exitosamente")
