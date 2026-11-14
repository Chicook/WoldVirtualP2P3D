"""
RF_SL1_9.py - Regresion lineal avanzada (puente legado)
=======================================================

Este modulo ya no reimplementa la regresion lineal ni sus utilidades
matematicas. La implementacion unica vive en el modulo especializado:

    RF_SL_SBRTM_RF_SL1_9/RF_SL_SBRTM_RF_SL1_9_1.py

Desde alli se importan ``NeuronaRegresionLineal``, el adaptador historico
``LinearRegressionOptimizer``, la base compartida ``NeuronaMemoriaBase``,
las utilidades (``LossMSE``, ``GradientDescentLR``, ``NormalEquation``,
``FeatureStandardizer``, ``LinearPredictor``, ``ModelMetrics``) y las
funciones nuevas (fabrica, metricas, benchmark, persistencia normal y
comprimida, y demo). El resto del archivo conserva ``PolynomialFeatures`` y
``LearningRateScheduler``, que no tienen equivalente directo en el modulo
especializado.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Regresion lineal: fuente unica en RF_SL_SBRTM_RF_SL1_9.
#
# Se importan sus clases (solvers OLS/Ridge/Lasso/ElasticNet, SGD/momentum/
# Adam y gestor de RAM/VRAM/disco) y sus funciones nuevas. Los antiguos
# bloques locales de LinearRegressionOptimizer y de sus utilidades (lineas
# 60-356) quedan sustituidos por este import, sin definiciones duplicadas.
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_SL1_9.RF_SL_SBRTM_RF_SL1_9_1 import (
        LUCIA_LINEAR_CONFIG,
        FeatureStandardizer,
        GradientDescentLR,
        LinearPredictor,
        LinearRegressionOptimizer,
        LossMSE,
        ModelMetrics,
        NeuronaMemoriaBase,
        NeuronaRegresionLineal,
        NormalEquation,
        benchmark_modelo,
        cargar_modelo,
        cargar_modelo_comprimido,
        crear_neurona,
        create_linear_regression_optimizer,
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

    _CLAVE_MODULO = "_rf_sl1_9_linear_import"
    _modulo_linear = _sys.modules.get(_CLAVE_MODULO)
    if _modulo_linear is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF_SL1_9",
            "RF_SL_SBRTM_RF_SL1_9_1.py",
        )
        _especificacion = _ilu.spec_from_file_location(
            _CLAVE_MODULO, _ruta_modulo
        )
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo_linear = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo_linear
        _especificacion.loader.exec_module(_modulo_linear)
    LUCIA_LINEAR_CONFIG = _modulo_linear.LUCIA_LINEAR_CONFIG
    FeatureStandardizer = _modulo_linear.FeatureStandardizer
    GradientDescentLR = _modulo_linear.GradientDescentLR
    LinearPredictor = _modulo_linear.LinearPredictor
    LinearRegressionOptimizer = _modulo_linear.LinearRegressionOptimizer
    LossMSE = _modulo_linear.LossMSE
    ModelMetrics = _modulo_linear.ModelMetrics
    NeuronaMemoriaBase = _modulo_linear.NeuronaMemoriaBase
    NeuronaRegresionLineal = _modulo_linear.NeuronaRegresionLineal
    NormalEquation = _modulo_linear.NormalEquation
    benchmark_modelo = _modulo_linear.benchmark_modelo
    cargar_modelo = _modulo_linear.cargar_modelo
    cargar_modelo_comprimido = _modulo_linear.cargar_modelo_comprimido
    crear_neurona = _modulo_linear.crear_neurona
    create_linear_regression_optimizer = (
        _modulo_linear.create_linear_regression_optimizer
    )
    demo = _modulo_linear.demo
    entrenar_y_evaluar = _modulo_linear.entrenar_y_evaluar
    guardar_modelo = _modulo_linear.guardar_modelo
    tipos_disponibles = _modulo_linear.tipos_disponibles

# Acceso directo a las clases anidadas del nucleo y del gestor de recursos.
NucleoRegresionLineal = NeuronaRegresionLineal.NucleoRegresionLineal
GestorRecursos = NeuronaRegresionLineal.GestorRecursos

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilidades historicas sin equivalente directo en el modulo especializado
# ---------------------------------------------------------------------------
class PolynomialFeatures:
    def __init__(self, degree: int = 2, interaction_only: bool = False):
        self.degree = max(1, int(degree))
        self.interaction_only = bool(interaction_only)

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim != 2:
            raise ValueError("X debe ser 2D")
        n_features = matriz.shape[1]
        features = [matriz]
        for grado in range(2, self.degree + 1):
            if self.interaction_only:
                for i in range(n_features):
                    for j in range(i + 1, n_features):
                        features.append(
                            (matriz[:, i] * matriz[:, j]).reshape(-1, 1)
                        )
            else:
                for i in range(n_features):
                    features.append(
                        (matriz[:, i] ** grado).reshape(-1, 1)
                    )
        return np.hstack(features).astype(np.float32)

    def get_output_dim(self, input_dim: int) -> int:
        if self.interaction_only:
            return input_dim + (
                input_dim * (input_dim - 1) // 2 * self.degree
            )
        return input_dim * self.degree


class LearningRateScheduler:
    def __init__(self, initial_lr: float = 0.01,
                 strategy: str = "step"):
        self.initial_lr = float(initial_lr)
        self.strategy = (
            strategy if strategy in ("step", "exponential", "cosine")
            else "step"
        )
        self._current_lr: float = self.initial_lr
        self._step: int = 0

    def get_lr(self) -> float:
        if self.strategy == "step":
            return self.initial_lr * (0.5 ** (self._step // 100))
        if self.strategy == "exponential":
            return self.initial_lr * math.exp(-0.01 * self._step)
        if self.strategy == "cosine":
            return self.initial_lr * 0.5 * (
                1.0 + math.cos(math.pi * self._step / 1000)
            )
        return self.initial_lr

    def step(self) -> None:
        self._step += 1
        self._current_lr = self.get_lr()

    def reset(self) -> None:
        self._step = 0
        self._current_lr = self.initial_lr


# ``create_linear_regression_optimizer`` se importa del modulo especializado
# para no duplicar la fabrica. Se conserva el mismo nombre y firma historica.


if __name__ == "__main__":
    logger.info("RF_SL1_9.py cargado exitosamente")
