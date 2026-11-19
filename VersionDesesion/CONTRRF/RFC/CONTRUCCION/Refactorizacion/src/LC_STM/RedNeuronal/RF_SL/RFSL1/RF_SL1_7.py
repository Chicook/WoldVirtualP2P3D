"""
RF_SL1_7.py - K-Nearest Neighbors avanzado (puente legado)
==========================================================

Este modulo ya no reimplementa KNN. La implementacion unica vive en el modulo
especializado:

    RF_SL_SBRTM_RF_SL1_7/RF_SL_SBRTM_RF_SL1_7_1.py

Desde alli se importan ``NeuronaKNN``, el adaptador historico
``KNearestNeighborsOptimizer``, la base compartida ``NeuronaMemoriaBase``, las
utilidades de distancia/normalizacion y las funciones nuevas (fabrica,
metricas, benchmark, persistencia y demo). El resto del archivo conserva
``KNNClassifier`` y ``ModelEvaluator``, que no tienen equivalente directo en el
modulo especializado.
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# KNN: fuente unica en el modulo especializado RF_SL_SBRTM_RF_SL1_7.
#
# Se importan sus clases (KNN con metricas vectorizadas, votos ponderados,
# regresion y normalizacion) y sus funciones nuevas. El antiguo bloque local
# de KNearestNeighborsOptimizer (lineas 61-243) queda sustituido por este
# import, sin dejar una segunda definicion del modelo.
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_SL1_7.RF_SL_SBRTM_RF_SL1_7_1 import (
        LUCIA_KNN_CONFIG,
        ConfusionMatrix,
        DistanceMetric,
        FeatureNormalizer,
        KNearestNeighborsOptimizer,
        KNNSearcher,
        NeuronaKNN,
        NeuronaMemoriaBase,
        RadiusNeighborSearcher,
        VoteAggregator,
        benchmark_modelo,
        cargar_modelo,
        crear_neurona,
        create_k_nearest_neighbors_optimizer,
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

    _CLAVE_MODULO = "_rf_sl1_7_knn_import"
    _modulo_knn = _sys.modules.get(_CLAVE_MODULO)
    if _modulo_knn is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF_SL1_7",
            "RF_SL_SBRTM_RF_SL1_7_1.py",
        )
        _especificacion = _ilu.spec_from_file_location(_CLAVE_MODULO, _ruta_modulo)
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo_knn = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo_knn
        _especificacion.loader.exec_module(_modulo_knn)
    LUCIA_KNN_CONFIG = _modulo_knn.LUCIA_KNN_CONFIG
    ConfusionMatrix = _modulo_knn.ConfusionMatrix
    DistanceMetric = _modulo_knn.DistanceMetric
    FeatureNormalizer = _modulo_knn.FeatureNormalizer
    KNearestNeighborsOptimizer = _modulo_knn.KNearestNeighborsOptimizer
    KNNSearcher = _modulo_knn.KNNSearcher
    NeuronaKNN = _modulo_knn.NeuronaKNN
    NeuronaMemoriaBase = _modulo_knn.NeuronaMemoriaBase
    RadiusNeighborSearcher = _modulo_knn.RadiusNeighborSearcher
    VoteAggregator = _modulo_knn.VoteAggregator
    benchmark_modelo = _modulo_knn.benchmark_modelo
    cargar_modelo = _modulo_knn.cargar_modelo
    crear_neurona = _modulo_knn.crear_neurona
    create_k_nearest_neighbors_optimizer = (
        _modulo_knn.create_k_nearest_neighbors_optimizer
    )
    demo = _modulo_knn.demo
    entrenar_y_evaluar = _modulo_knn.entrenar_y_evaluar
    guardar_modelo = _modulo_knn.guardar_modelo
    tipos_disponibles = _modulo_knn.tipos_disponibles

# Acceso directo a las clases anidadas de distancias y votacion.
NucleoDistancias = NeuronaKNN.NucleoDistancias
NucleoVotacion = NeuronaKNN.NucleoVotacion

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilidades historicas sin equivalente directo en el modulo especializado
# ---------------------------------------------------------------------------
class KNNClassifier:
    def __init__(self, k: int = 5, metric: str = "euclidean",
                 normalize: bool = False):
        self.k = k
        self.metric = metric
        self.normalize = normalize
        self.normalizer = FeatureNormalizer() if normalize else None
        self.searcher = KNNSearcher(k, metric)
        self.voter = VoteAggregator()
        self._data: Optional[np.ndarray] = None
        self._labels: Optional[np.ndarray] = None
        self._is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "KNNClassifier":
        if self.normalize:
            X = self.normalizer.fit_transform(X)
        self._data = X.copy()
        self._labels = y.astype(int) if y.dtype != int else y
        self._is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("No entrenado")
        if self.normalize:
            X = self.normalizer.transform(X)
        return np.array([
            self.voter.aggregate(
                self._labels[np.argpartition(
                    DistanceMetric.euclidean(
                        X[i:i + 1], self._data
                    )[0],
                    self.k,
                )[:self.k]]
            )
            for i in range(len(X))
        ])


class ModelEvaluator:
    def __init__(self, k_values: Optional[List[int]] = None):
        self.k_values = k_values or [1, 3, 5, 7, 9]
        self._scores: Dict[int, float] = {}

    def evaluate_k_range(self, X_train: np.ndarray, y_train: np.ndarray,
                         X_test: np.ndarray, y_test: np.ndarray
                         ) -> Dict[int, float]:
        for k in self.k_values:
            knn = KNearestNeighborsOptimizer(
                X_train.shape[1], len(np.unique(y_train))
            )
            knn._data = X_train.copy()
            knn._labels = (
                y_train.astype(int) if y_train.dtype != int else y_train
            )
            knn._k = k
            knn._is_fitted = True
            acc = knn.compute_accuracy(X_test, y_test)
            self._scores[k] = acc
        return self._scores

    def get_best_k(self) -> int:
        if not self._scores:
            return 5
        return max(self._scores, key=self._scores.get)

    def get_scores(self) -> Dict[int, float]:
        return self._scores.copy()


# ``create_k_nearest_neighbors_optimizer`` se importa del modulo especializado
# para no duplicar la fabrica. Se conserva el mismo nombre y firma historica.


if __name__ == "__main__":
    logger.info("RF_SL1_7.py cargado exitosamente")
