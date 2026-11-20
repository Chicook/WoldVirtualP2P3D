"""
RF_SL1_8.py - Regresion logistica avanzada (puente legado)
==========================================================

Este modulo ya no reimplementa la regresion logistica ni sus utilidades
matematicas. La implementacion unica vive en el modulo especializado:

    RF_SL_SBRTM_RF_SL1_8/RF_SL_SBRTM_RF_SL1_8_1.py

Desde alli se importan ``NeuronaRegresionLogistica``, el adaptador historico
``LogisticRegressionOptimizer``, la base compartida ``NeuronaMemoriaBase``,
las utilidades (``SigmoidEngine``, ``LossCalculator``, ``GradientDescent``,
``Regularizer``, ``DecisionBoundary``, ``FeatureScaler``) y las funciones
nuevas (fabrica, metricas, benchmark, persistencia y demo). El resto del
archivo conserva ``LRClassifier`` y ``ModelEvaluator``, que no tienen
equivalente directo en el modulo especializado.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Regresion logistica: fuente unica en RF_SL_SBRTM_RF_SL1_8.
#
# Se importan sus clases (sigmoide/softmax, regularizacion, optimizadores,
# escalado y metricas) y sus funciones nuevas. Los antiguos bloques locales
# de LogisticRegressionOptimizer y de sus utilidades (lineas 60-349) quedan
# sustituidos por este import, sin definiciones duplicadas.
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_SL1_8.RF_SL_SBRTM_RF_SL1_8_1 import (
        LUCIA_LR_CONFIG,
        DecisionBoundary,
        FeatureScaler,
        GradientDescent,
        LogisticRegressionOptimizer,
        LossCalculator,
        NeuronaMemoriaBase,
        NeuronaRegresionLogistica,
        Regularizer,
        SigmoidEngine,
        benchmark_modelo,
        cargar_modelo,
        crear_neurona,
        create_logistic_regression_optimizer,
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

    _CLAVE_MODULO = "_rf_sl1_8_lr_import"
    _modulo_lr = _sys.modules.get(_CLAVE_MODULO)
    if _modulo_lr is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF_SL1_8",
            "RF_SL_SBRTM_RF_SL1_8_1.py",
        )
        _especificacion = _ilu.spec_from_file_location(_CLAVE_MODULO, _ruta_modulo)
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo_lr = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo_lr
        _especificacion.loader.exec_module(_modulo_lr)
    LUCIA_LR_CONFIG = _modulo_lr.LUCIA_LR_CONFIG
    DecisionBoundary = _modulo_lr.DecisionBoundary
    FeatureScaler = _modulo_lr.FeatureScaler
    GradientDescent = _modulo_lr.GradientDescent
    LogisticRegressionOptimizer = _modulo_lr.LogisticRegressionOptimizer
    LossCalculator = _modulo_lr.LossCalculator
    NeuronaMemoriaBase = _modulo_lr.NeuronaMemoriaBase
    NeuronaRegresionLogistica = _modulo_lr.NeuronaRegresionLogistica
    Regularizer = _modulo_lr.Regularizer
    SigmoidEngine = _modulo_lr.SigmoidEngine
    benchmark_modelo = _modulo_lr.benchmark_modelo
    cargar_modelo = _modulo_lr.cargar_modelo
    crear_neurona = _modulo_lr.crear_neurona
    create_logistic_regression_optimizer = (
        _modulo_lr.create_logistic_regression_optimizer
    )
    demo = _modulo_lr.demo
    entrenar_y_evaluar = _modulo_lr.entrenar_y_evaluar
    guardar_modelo = _modulo_lr.guardar_modelo
    tipos_disponibles = _modulo_lr.tipos_disponibles

# Acceso directo a la clase anidada del nucleo matematico.
NucleoLogistico = NeuronaRegresionLogistica.NucleoLogistico

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilidades historicas sin equivalente directo en el modulo especializado
# ---------------------------------------------------------------------------
class LRClassifier:
    def __init__(self, input_size: int, output_size: int = 1,
                 threshold: float = 0.5):
        self.input_size = input_size
        self.output_size = output_size
        self.threshold = threshold
        self._model: Optional[LogisticRegressionOptimizer] = None

    def fit(self, X: np.ndarray, y: np.ndarray,
            **kwargs: Any) -> LogisticRegressionOptimizer:
        self._model = LogisticRegressionOptimizer(
            input_size=X.shape[1], output_size=self.output_size
        )
        self._model.train(X, y, **kwargs)
        return self._model

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Modelo no entrenado")
        return self._model.predict(X)

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        predicciones = self.predict(X)
        return float(np.mean(predicciones == y))


class ModelEvaluator:
    def __init__(self):
        self._results: Dict[str, Any] = {}

    def accuracy(self, y_true: np.ndarray,
                 y_pred: np.ndarray) -> float:
        return float(np.mean(y_true == y_pred))

    def precision(self, y_true: np.ndarray, y_pred: np.ndarray,
                  average: str = "binary") -> float:
        real = y_true.astype(int)
        pred = y_pred.astype(int)
        if average == "binary":
            tp = int(np.sum((pred == 1) & (real == 1)))
            fp = int(np.sum((pred == 1) & (real == 0)))
            return tp / max(1, tp + fp)
        return 0.0

    def recall(self, y_true: np.ndarray, y_pred: np.ndarray,
               average: str = "binary") -> float:
        real = y_true.astype(int)
        pred = y_pred.astype(int)
        if average == "binary":
            tp = int(np.sum((pred == 1) & (real == 1)))
            fn = int(np.sum((pred == 0) & (real == 1)))
            return tp / max(1, tp + fn)
        return 0.0

    def f1_score(self, y_true: np.ndarray,
                 y_pred: np.ndarray) -> float:
        p = self.precision(y_true, y_pred)
        r = self.recall(y_true, y_pred)
        return 2.0 * p * r / max(1e-8, p + r)

    def evaluate_all(self, y_true: np.ndarray,
                     y_pred: np.ndarray) -> Dict[str, float]:
        return {
            'accuracy': self.accuracy(y_true, y_pred),
            'precision': self.precision(y_true, y_pred),
            'recall': self.recall(y_true, y_pred),
            'f1': self.f1_score(y_true, y_pred),
        }


# ``create_logistic_regression_optimizer`` se importa del modulo especializado
# para no duplicar la fabrica. Se conserva el mismo nombre y firma historica.


if __name__ == "__main__":
    logger.info("RF_SL1_8.py cargado exitosamente")
