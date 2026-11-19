"""
RF_SL1_1.py - Gradient Boosting Avanzado (XGBoost/LightGBM)
Optimizado con clases inline y estructura eficiente.
"""

import numpy as np
import logging
import time
import pickle
from collections import deque
from typing import Dict, Any, List, Optional, Tuple, Deque

# ---------------------------------------------------------------------------
# Compatibilidad de importacion suelta y del nombre antiguo de la carpeta base.
# Si el modulo se ejecuta como script o se importa por ruta, no existe el
# paquete padre y los imports relativos fallan. Se registra un paquete
# sintetico "RF_SL.RFSL1" equivalente al real. Ademas, "_rfsl_base.py" aun
# referencia la carpeta "RF_SL_SBRTM_RF"; si esa carpeta ya no existe se
# registra un alias hacia "RF_SL_SBRTM_RF_rfsl_base".
# ---------------------------------------------------------------------------
import os as _os
import sys as _sys
import types as _types

_DIR_RFSL1 = _os.path.dirname(_os.path.abspath(__file__))
_DIR_RF_SL = _os.path.dirname(_DIR_RFSL1)

if "." not in (__package__ or ""):
    if _DIR_RF_SL not in _sys.path:
        _sys.path.insert(0, _DIR_RF_SL)
    if "RF_SL" not in _sys.modules:
        _paquete_rf_sl = _types.ModuleType("RF_SL")
        _paquete_rf_sl.__path__ = [_DIR_RF_SL]
        _paquete_rf_sl.__package__ = "RF_SL"
        _sys.modules["RF_SL"] = _paquete_rf_sl
    __package__ = "RF_SL.RFSL1"
    __path__ = [_DIR_RFSL1]
    _sys.modules.setdefault("RF_SL.RFSL1", _sys.modules[__name__])

_PADRE_PAQUETE = (__package__ or "").rpartition(".")[0]
_RUTA_BASE_ANTIGUA = _os.path.join(_DIR_RF_SL, "RF_SL_SBRTM_RF")
_RUTA_BASE_ACTUAL = _os.path.join(_DIR_RF_SL, "RF_SL_SBRTM_RF_rfsl_base")

if (_PADRE_PAQUETE
        and not _os.path.isdir(_RUTA_BASE_ANTIGUA)
        and _os.path.isdir(_RUTA_BASE_ACTUAL)):
    _NOMBRE_ALIAS = f"{_PADRE_PAQUETE}.RF_SL_SBRTM_RF"
    _NOMBRE_ALIAS_MODULO = f"{_NOMBRE_ALIAS}.RF_SL_SNRTM__rfsl_base1"
    _NOMBRE_MODULO_ACTUAL = (
        f"{_PADRE_PAQUETE}.RF_SL_SBRTM_RF_rfsl_base.RF_SL_SNRTM__rfsl_base1"
    )
    if _NOMBRE_ALIAS not in _sys.modules:
        _paquete_alias = _types.ModuleType(_NOMBRE_ALIAS)
        _paquete_alias.__path__ = [_RUTA_BASE_ACTUAL]
        _paquete_alias.__package__ = _NOMBRE_ALIAS
        _sys.modules[_NOMBRE_ALIAS] = _paquete_alias
    if _NOMBRE_ALIAS_MODULO not in _sys.modules:
        try:
            import importlib as _importlib
            _sys.modules[_NOMBRE_ALIAS_MODULO] = _importlib.import_module(
                _NOMBRE_MODULO_ACTUAL
            )
        except Exception:
            # Si falla, _rfsl_base resolvera el alias por su propio __path__.
            pass

from ._rfsl_base import (
    NeuronaMemoriaBase,
    TreeBuilder,
    LossCalculator,
    Sampler,
    FeatureSelector,
    PredictionAggregator,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GradientBoostingOptimizer: implementacion unica en el modulo especializado
# RF_SL_SBRTM_RF_SL1_1/RF_SL_SBRTM_RF_SL1_1_1.py.
#
# Se importa su clase (boosting de segundo orden con histogramas, hojas Newton
# o lineales, regularizacion y early stopping) y se conservan debajo los
# metodos de compatibilidad que ya vivian en este archivo (evaluate,
# obtener_estadisticas, verificar_estabilidad, save/load, get_config, summary,
# __str__). Asi no se duplica la implementacion del algoritmo.
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_SL1_1.RF_SL_SBRTM_RF_SL1_1_1 import (
        GradientBoostingOptimizer as _GradientBoostingOptimizerBase,
        NeuronaArbolGradiente,
        NeuronaArbolLinealGradiente,
        NeuronaGradienteBoosting,
        cargar_modelo,
        crear_neurona as crear_neurona_boosting,
        guardar_modelo,
    )
except (ImportError, ValueError):
    # Fallback por ruta para cargas por fichero o sin paquete padre.
    import importlib.util as _ilu
    import os as _os
    import sys as _sys

    _CLAVE_MODULO = "_rf_sl1_1_gb_import"
    _modulo_gb = _sys.modules.get(_CLAVE_MODULO)
    if _modulo_gb is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF_SL1_1",
            "RF_SL_SBRTM_RF_SL1_1_1.py",
        )
        _especificacion = _ilu.spec_from_file_location(_CLAVE_MODULO, _ruta_modulo)
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo_gb = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo_gb
        _especificacion.loader.exec_module(_modulo_gb)
    _GradientBoostingOptimizerBase = _modulo_gb.GradientBoostingOptimizer
    NeuronaArbolGradiente = _modulo_gb.NeuronaArbolGradiente
    NeuronaArbolLinealGradiente = _modulo_gb.NeuronaArbolLinealGradiente
    NeuronaGradienteBoosting = _modulo_gb.NeuronaGradienteBoosting
    crear_neurona_boosting = _modulo_gb.crear_neurona
    guardar_modelo = _modulo_gb.guardar_modelo
    cargar_modelo = _modulo_gb.cargar_modelo


class GradientBoostingOptimizer(_GradientBoostingOptimizerBase):
    """Boosting real (2.º orden) con la API de compatibilidad de RF_SL1_1."""

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        pred = self.predict(X)
        mse = self.squared_error_loss(pred, y)
        mae = float(np.mean(np.abs(pred - y)))
        rmse = float(np.sqrt(mse))
        return {'mse': mse, 'mae': mae, 'rmse': rmse, 'n_samples': len(X)}

    def obtener_estadisticas(self) -> Dict[str, Any]:
        stats = super().obtener_estadisticas()
        stats['learning_rate'] = self._learning_rate
        stats['n_estimators'] = self._n_estimators
        stats['max_depth'] = self._max_depth
        stats['subsample'] = self._subsample
        stats['loss_type'] = self._loss_type
        stats['convergence_history_len'] = len(self._convergence_history)
        stats['timer_train'] = self._timer_train
        if self._convergence_history:
            stats['final_loss'] = float(self._convergence_history[-1])
            stats['initial_loss'] = float(self._convergence_history[0])
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        ok = {'pesos_inicializados': self.pesos is not None}
        if self.pesos is not None:
            ok['pesos_no_explosivos'] = float(np.max(np.abs(self.pesos))) < 10.0
            ok['pesos_no_nan'] = not bool(np.any(np.isnan(self.pesos)))
            ok['pesos_no_inf'] = not bool(np.any(np.isinf(self.pesos)))
            ok['sesgo_no_nan'] = not bool(np.any(np.isnan(self.sesgo)))
        return ok

    def save(self, filepath: str) -> None:
        """Serializa el modelo completo (base lineal + arboles del boosting)."""
        guardar_modelo(self, filepath)

    def load(self, filepath: str) -> None:
        """Carga un modelo completo serializado previamente con save()."""
        cargado = cargar_modelo(filepath)
        self.__dict__.update(cargado.__dict__)

    def get_config(self) -> Dict[str, Any]:
        return {
            'nombre': self.nombre, 'input_size': self.input_size,
            'output_size': self.output_size, 'learning_rate': self._learning_rate,
            'n_estimators': self._n_estimators, 'max_depth': self._max_depth,
            'subsample': self._subsample, 'loss_type': self._loss_type,
        }

    def summary(self) -> str:
        cfg = self.get_config()
        stats = self.obtener_estadisticas()
        return "\n".join([
            f"=== {cfg['nombre']} ===",
            f"Input: {cfg['input_size']}, Output: {cfg['output_size']}",
            f"LR: {cfg['learning_rate']}, Estimators: {cfg['n_estimators']}, Depth: {cfg['max_depth']}",
            f"Pesos: {stats.get('pesos_shape', 'N/A')}, Params: {self.params_count()}",
            f"Pasos: {self.pasos}, Final loss: {stats.get('final_loss', 'N/A')}",
        ])

    def __str__(self) -> str:
        return f"{self.nombre}(ent={self.input_size},sal={self.output_size})"

class GradientBooster:
    def __init__(self, input_size: int = 4, output_size: int = 8, n_estimators: int = 50,
                 learning_rate: float = 0.1, max_depth: int = 3, subsample: float = 1.0):
        self.input_size = input_size
        self.output_size = output_size
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.subsample = subsample
        self._trees: List[TreeBuilder] = []
        self._loss_fn = LossCalculator("mse")
        self._sampler = Sampler(subsample)
        self._aggregator = PredictionAggregator(learning_rate)
        self._residuals: Optional[np.ndarray] = None
        self._training_history: List[float] = []

    def fit(self, X: np.ndarray, y: np.ndarray) -> List[float]:
        self._residuals = y.copy().astype(np.float64)
        self._training_history.clear()
        for i in range(self.n_estimators):
            X_s, r_s = self._sampler.sample(X, self._residuals)
            tree = TreeBuilder(max_depth=self.max_depth)
            tree.fit(X_s, r_s)
            pred = tree.predict(X)
            self._trees.append(tree)
            self._aggregator.add_prediction(pred)
            self._residuals = self._residuals - self.learning_rate * pred
            loss = self._loss_fn.compute(self._aggregator.aggregate(), y)
            self._training_history.append(loss)
        return self._training_history

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._aggregator.aggregate() if self._aggregator.n_predictions > 0 else np.zeros(len(X))

    def get_n_estimators(self) -> int: return len(self._trees)

    def get_trees_info(self) -> List[Dict]:
        return [{'tree_idx': i, 'n_predictions': self._aggregator.n_predictions} for i in range(len(self._trees))]


def create_gradient_boosting_optimizer(input_size: int = 4, output_size: int = 8) -> GradientBoostingOptimizer:
    return GradientBoostingOptimizer(input_size=input_size, output_size=output_size)


def train_booster(X: np.ndarray, y: np.ndarray, n_estimators: int = 50, learning_rate: float = 0.1,
                  max_depth: int = 3) -> GradientBooster:
    booster = GradientBooster(input_size=X.shape[1], output_size=1, n_estimators=n_estimators,
                              learning_rate=learning_rate, max_depth=max_depth)
    booster.fit(X, y)
    return booster


def evaluate_booster(booster: GradientBooster, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    pred = booster.predict(X)
    return {
        'mse': float(np.mean((pred - y) ** 2)),
        'mae': float(np.mean(np.abs(pred - y))),
        'n_estimators': booster.get_n_estimators(),
        'final_loss': booster._training_history[-1] if booster._training_history else 0.0,
    }


if __name__ == "__main__":
    logger.info("RF_SL1_1.py cargado exitosamente")