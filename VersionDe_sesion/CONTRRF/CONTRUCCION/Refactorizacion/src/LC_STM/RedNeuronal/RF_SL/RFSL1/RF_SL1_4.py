"""
RF_SL1_4.py - Redes neuronales avanzadas (puente legado)
=========================================================

Este modulo ya no reimplementa la red neuronal. La implementacion unica vive
en el modulo especializado:

    RF_SL_SBRTM_RF_SL1_4/RF_SL_SBRTM_RF_SL1_4_1.py

Desde alli se importan ``NeuralNetworkOptimizer``, ``NeuronaMLP``, la base
compartida ``NeuronaMemoriaBase`` y las funciones nuevas (fabrica, metricas,
benchmark, persistencia y demo). El resto del archivo conserva las utilidades
historicas de compatibilidad (``ActivationEngine``, ``GradientClipper``,
``WeightInitializer``, ``DropoutLayer``, ``LossFunctions``,
``LearningRateScheduler`` y ``NeuralNetTrainer``), que no duplican ninguna de
las clases importadas.
"""

import logging
import math
from typing import Dict, List, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Red neuronal: fuente unica en el modulo especializado RF_SL_SBRTM_RF_SL1_4.
#
# Se importan sus clases (MLP con capas ocultas, Adam/AdamW, dropout,
# regularizacion, early stopping, serializacion...) y sus funciones nuevas.
# El antiguo bloque local de NeuralNetworkOptimizer (lineas 61-244) queda
# sustituido por este import, sin dejar una segunda definicion de la clase.
# ---------------------------------------------------------------------------
try:
    from ..RF_SL_SBRTM_RF_SL1_4.RF_SL_SBRTM_RF_SL1_4_1 import (
        LUCIA_NN_CONFIG,
        NeuralNetworkOptimizer,
        NeuronaMLP,
        NeuronaMemoriaBase,
        benchmark_modelo,
        cargar_modelo,
        crear_neurona,
        create_neural_network_optimizer,
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

    _CLAVE_MODULO = "_rf_sl1_4_nn_import"
    _modulo_nn = _sys.modules.get(_CLAVE_MODULO)
    if _modulo_nn is None:
        _ruta_modulo = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "RF_SL_SBRTM_RF_SL1_4",
            "RF_SL_SBRTM_RF_SL1_4_1.py",
        )
        _especificacion = _ilu.spec_from_file_location(_CLAVE_MODULO, _ruta_modulo)
        if _especificacion is None or _especificacion.loader is None:
            raise ImportError(f"No se pudo cargar {_ruta_modulo}")
        _modulo_nn = _ilu.module_from_spec(_especificacion)
        _sys.modules[_CLAVE_MODULO] = _modulo_nn
        _especificacion.loader.exec_module(_modulo_nn)
    LUCIA_NN_CONFIG = _modulo_nn.LUCIA_NN_CONFIG
    NeuralNetworkOptimizer = _modulo_nn.NeuralNetworkOptimizer
    NeuronaMLP = _modulo_nn.NeuronaMLP
    NeuronaMemoriaBase = _modulo_nn.NeuronaMemoriaBase
    benchmark_modelo = _modulo_nn.benchmark_modelo
    cargar_modelo = _modulo_nn.cargar_modelo
    crear_neurona = _modulo_nn.crear_neurona
    create_neural_network_optimizer = _modulo_nn.create_neural_network_optimizer
    demo = _modulo_nn.demo
    entrenar_y_evaluar = _modulo_nn.entrenar_y_evaluar
    guardar_modelo = _modulo_nn.guardar_modelo
    tipos_disponibles = _modulo_nn.tipos_disponibles

# Acceso directo a la clase anidada del nucleo matematico (activacion,
# perdidas, gradientes, optimizadores, horarios y metricas).
NucleoDiferenciable = NeuralNetworkOptimizer.NucleoDiferenciable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilidades historicas de compatibilidad (no sustituyen a la red importada)
# ---------------------------------------------------------------------------
class ActivationEngine:
    @staticmethod
    def relu(x: np.ndarray) -> np.ndarray:
        return np.maximum(0, x)

    @staticmethod
    def sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))

    @staticmethod
    def tanh(x: np.ndarray) -> np.ndarray:
        return np.tanh(x)

    @staticmethod
    def leaky_relu(x: np.ndarray, alpha: float = 0.01) -> np.ndarray:
        return np.where(x > 0, x, alpha * x)

    @staticmethod
    def softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return e / np.sum(e, axis=-1, keepdims=True)

    @staticmethod
    def relu_derivative(x: np.ndarray) -> np.ndarray:
        return (x > 0).astype(np.float32)

    @staticmethod
    def sigmoid_derivative(x: np.ndarray) -> np.ndarray:
        s = ActivationEngine.sigmoid(x)
        return s * (1 - s)

    @staticmethod
    def apply(x: np.ndarray, activation: str) -> np.ndarray:
        if activation == "relu":
            return ActivationEngine.relu(x)
        if activation == "sigmoid":
            return ActivationEngine.sigmoid(x)
        if activation == "tanh":
            return ActivationEngine.tanh(x)
        if activation == "leaky_relu":
            return ActivationEngine.leaky_relu(x)
        if activation == "softmax":
            return ActivationEngine.softmax(x)
        return x


class GradientClipper:
    def __init__(self, max_norm: float = 5.0):
        self.max_norm = max_norm

    def clip(self, gradient: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(gradient)
        if norm > self.max_norm:
            return gradient * self.max_norm / (norm + 1e-8)
        return gradient

    def get_norm(self, gradient: np.ndarray) -> float:
        return float(np.linalg.norm(gradient))

    def is_clipped(self, gradient: np.ndarray) -> bool:
        return np.linalg.norm(gradient) > self.max_norm


class WeightInitializer:
    @staticmethod
    def he(shape: tuple, fan_in: int = 1) -> np.ndarray:
        return np.random.normal(
            0, math.sqrt(2.0 / max(1, fan_in)), shape
        ).astype(np.float32)

    @staticmethod
    def xavier(shape: tuple) -> np.ndarray:
        lim = math.sqrt(6.0 / max(1, shape[0] + shape[1]))
        return np.random.uniform(-lim, lim, shape).astype(np.float32)

    @staticmethod
    def lecun(shape: tuple, fan_in: int = 1) -> np.ndarray:
        return np.random.normal(
            0, math.sqrt(1.0 / max(1, fan_in)), shape
        ).astype(np.float32)

    @staticmethod
    def orthogonal(shape: tuple) -> np.ndarray:
        wf = np.random.randn(*shape).astype(np.float64)
        iters = 3
        v = np.random.default_rng(0).normal(0, 1, (wf.shape[1], 1))
        v /= max(1e-12, np.linalg.norm(v))
        for _ in range(iters):
            u = wf @ v
            u /= max(1e-12, np.linalg.norm(u))
            v = wf.T @ u
            v /= max(1e-12, np.linalg.norm(v))
        s = abs((u.T @ wf @ v)[0, 0])
        return np.random.randn(*shape).astype(np.float32) * abs(s)


class DropoutLayer:
    def __init__(self, rate: float = 0.5):
        self.rate = rate
        self._mask: Optional[np.ndarray] = None

    def forward(self, x: np.ndarray, training: bool = True) -> np.ndarray:
        if not training or self.rate == 0.0:
            return x
        self._mask = np.random.random(x.shape) > self.rate
        return x * self._mask / (1.0 - self.rate)

    def backward(self, grad: np.ndarray) -> np.ndarray:
        if self._mask is None:
            return grad
        return grad * self._mask / (1.0 - self.rate)

    def is_active(self) -> bool:
        return self.rate > 0 and self._mask is not None


class LossFunctions:
    @staticmethod
    def mse(pred: np.ndarray, target: np.ndarray) -> float:
        return float(np.mean((pred - target) ** 2))

    @staticmethod
    def mae(pred: np.ndarray, target: np.ndarray) -> float:
        return float(np.mean(np.abs(pred - target)))

    @staticmethod
    def cross_entropy(pred: np.ndarray, target: np.ndarray) -> float:
        p = np.clip(pred, 1e-8, 1 - 1e-8)
        return float(-np.mean(
            target * np.log(p) + (1 - target) * np.log(1 - p)
        ))

    @staticmethod
    def huber(pred: np.ndarray, target: np.ndarray,
              delta: float = 1.0) -> float:
        abs_err = np.abs(pred - target)
        q = np.minimum(abs_err, delta)
        l = abs_err - q
        return float(np.mean(0.5 * q ** 2 + delta * l))


class LearningRateScheduler:
    def __init__(self, initial_lr: float, strategy: str = "cosine",
                 total_steps: int = 100):
        self.lr = initial_lr
        self.strategy = strategy
        self.total_steps = total_steps
        self._step = 0

    def step(self) -> float:
        self._step += 1
        t = self._step / self.total_steps
        if self.strategy == "cosine":
            self.lr = 0.5 * self.lr * (1 + math.cos(math.pi * t))
        elif self.strategy == "linear":
            self.lr = self.lr * (1 - t)
        elif self.strategy == "step":
            self.lr = self.lr * (0.5 ** (self._step // 20))
        return self.lr

    def get_lr(self) -> float:
        return self.lr


class NeuralNetTrainer:
    def __init__(self, network: NeuralNetworkOptimizer,
                 max_norm: float = 5.0):
        self.network = network
        self.max_norm = max_norm
        self._train_losses: List[float] = []
        self._val_losses: List[float] = []

    def train_epoch(self, X: np.ndarray, y: np.ndarray) -> float:
        pred = self.network.forward(X)
        loss = self.network.compute_loss(pred, y)
        grad = self.network.compute_gradient(pred, y)
        grad = GradientClipper(self.max_norm).clip(grad)
        gp, gs = self.network.backward(grad, X)
        self.network.update_weights_momentum(gp, gs)
        self._train_losses.append(loss)
        return loss

    def validate(self, X: np.ndarray, y: np.ndarray) -> float:
        pred = self.network.predict(X)
        loss = LossFunctions.mse(pred, y)
        self._val_losses.append(loss)
        return loss

    def train_with_validation(self, X: np.ndarray, y: np.ndarray,
                              X_val: np.ndarray, y_val: np.ndarray,
                              epochs: int = 10) -> Dict[str, List[float]]:
        for epoch in range(epochs):
            train_loss = self.train_epoch(X, y)
            val_loss = self.validate(X_val, y_val)
            logger.info(
                f"Epoch {epoch + 1}: train={train_loss:.6f}, "
                f"val={val_loss:.6f}"
            )
        return {'train': self._train_losses, 'val': self._val_losses}

    def get_train_losses(self) -> List[float]:
        return self._train_losses.copy()

    def get_val_losses(self) -> List[float]:
        return self._val_losses.copy()


# ``create_neural_network_optimizer`` se importa del modulo especializado para
# no duplicar la fabrica. Se conserva el mismo nombre y firma historica.


if __name__ == "__main__":
    logger.info("RF_SL1_4.py cargado exitosamente")
