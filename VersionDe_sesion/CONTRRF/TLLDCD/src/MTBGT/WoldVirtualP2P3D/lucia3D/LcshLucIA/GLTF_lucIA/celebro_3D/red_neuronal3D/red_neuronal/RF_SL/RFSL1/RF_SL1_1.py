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
from ._rfsl_base import (
    NeuronaMemoriaBase,
    TreeBuilder,
    LossCalculator,
    Sampler,
    FeatureSelector,
    PredictionAggregator,
)

logger = logging.getLogger(__name__)


class GradientBoostingOptimizer(NeuronaMemoriaBase):
    def __init__(self, input_size: int = 4, output_size: int = 8, nombre: str = "GradientBoostingOptimizer"):
        super().__init__(input_size, output_size, nombre)
        self.inicializar_pesos()
        self._learning_rate: float = 0.1
        self._n_estimators: int = 100
        self._max_depth: int = 3
        self._subsample: float = 1.0
        self._loss_type: str = "mse"
        self._convergence_history: List[float] = []
        self._timer_train: float = 0.0

    def inicializar_pesos(self) -> None:
        std = 0.1
        self.pesos = np.random.randn(self.input_size, self.output_size).astype(np.float32) * std
        self.sesgo = np.zeros((1, self.output_size), dtype=np.float32)

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        if self.pesos is None: self.inicializar_pesos()
        salida = np.dot(entrada, self.pesos) + self.sesgo
        self.historial_activaciones.append(salida.copy())
        self.pasos += 1
        return salida

    def predict(self, entrada: np.ndarray) -> np.ndarray:
        return self.forward(entrada)

    def compute_loss(self, prediccion: np.ndarray, objetivo: np.ndarray) -> float:
        if self._loss_type == "mse": return float(np.mean((prediccion - objetivo) ** 2))
        diff = prediccion - objetivo
        return float(np.mean(diff * np.log(1 + np.exp(np.abs(diff))) - objetivo * diff))

    def squared_error_loss(self, pred: np.ndarray, target: np.ndarray) -> float:
        return float(np.mean((pred - target) ** 2))

    def log_loss(self, pred: np.ndarray, target: np.ndarray) -> float:
        pred = np.clip(pred, 1e-8, 1 - 1e-8)
        return float(-np.mean(target * np.log(pred) + (1 - target) * np.log(1 - pred)))

    def compute_gradient(self, prediccion: np.ndarray, objetivo: np.ndarray) -> np.ndarray:
        diff = prediccion - objetivo
        if self._loss_type == "mse": return diff
        if self._loss_type == "huber":
            delta = 1.0
            abs_diff = np.abs(diff)
            return np.where(abs_diff <= delta, diff, delta * np.sign(diff))
        return diff

    def backward(self, gradiente_salida: np.ndarray, entrada: np.ndarray):
        grad_pesos = np.dot(entrada.T, gradiente_salida)
        grad_sesgo = np.sum(gradiente_salida, axis=0, keepdims=True)
        self.historial_gradientes.append({'pesos': grad_pesos.copy(), 'norma': float(np.linalg.norm(grad_pesos))})
        return grad_pesos, grad_sesgo

    def update_weights(self, grad_pesos: np.ndarray, grad_sesgo: np.ndarray) -> None:
        self.pesos -= self._learning_rate * grad_pesos
        self.sesgo -= self._learning_rate * grad_sesgo

    def apply_gradient(self, entrada: np.ndarray, objetivo: np.ndarray) -> float:
        pred = self.forward(entrada)
        grad = self.compute_gradient(pred, objetivo)
        gp, gs = self.backward(grad, entrada)
        self.update_weights(gp, gs)
        return self.compute_loss(pred, objetivo)

    def train_step(self, entrada: np.ndarray, objetivo: np.ndarray) -> Dict[str, float]:
        loss_before = self.compute_loss(self.forward(entrada), objetivo)
        loss = self.apply_gradient(entrada, objetivo)
        return {'loss_before': loss_before, 'loss_after': loss, 'improvement': loss_before - loss}

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 50, verbose: bool = False) -> List[float]:
        t0 = time.perf_counter()
        losses = []
        for epoch in range(epochs):
            loss = self.apply_gradient(X, y)
            losses.append(loss)
            self._convergence_history.append(loss)
            if verbose and (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}/{epochs}, loss={loss:.6f}")
        self._timer_train = time.perf_counter() - t0
        return losses

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
        state = {
            'pesos': self.pesos, 'sesgo': self.sesgo, 'nombre': self.nombre,
            'input_size': self.input_size, 'output_size': self.output_size,
            'learning_rate': self._learning_rate, 'n_estimators': self._n_estimators,
            'max_depth': self._max_depth, 'subsample': self._subsample,
            'loss_type': self._loss_type, 'pasos': self.pasos,
            'convergence_history': self._convergence_history,
        }
        with open(filepath, 'wb') as f: pickle.dump(state, f)

    def load(self, filepath: str) -> None:
        with open(filepath, 'rb') as f: state = pickle.load(f)
        self.__dict__.update({k: v for k, v in state.items() if k != 'convergence_history'})
        self._convergence_history = state.get('convergence_history', [])

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