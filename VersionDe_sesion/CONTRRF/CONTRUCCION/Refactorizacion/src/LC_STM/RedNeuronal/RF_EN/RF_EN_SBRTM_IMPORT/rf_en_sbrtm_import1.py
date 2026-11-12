"""Utilidades de refuerzo para las neuronas RF (SBRTM).

Autocontenido: configuración, inicializadores de pesos, buffers de
experiencia, cálculo de recompensas/ventajas, entrenamiento y métricas.

Las funciones sueltas originales se conservan como fachada y delegan en
HerramientasRefuerzo (funciones unificadas). GestorEntrenamientoRefuerzo
reparte el trabajo entre varias neuronas y vigila su convergencia.
"""

from __future__ import annotations

import math
import random
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

LUCIA_RL_CONFIG: Dict[str, Any] = {
    "precision": "float32",
    "random_seed": 0,
    "gamma": 0.99,
    "lambda_gae": 0.95,
    "grad_clip": 0.5,
    "buffer_capacity": 10000,
    "per_alpha": 0.6,
    "per_beta": 0.4,
}

_DTYPE_MAP = {"float32": np.float32, "float64": np.float64, "float16": np.float16}


def actualizar_config(**kwargs) -> Dict[str, Any]:
    """Actualiza LUCIA_RL_CONFIG y devuelve la configuración resultante."""
    for clave, valor in kwargs.items():
        if valor is not None:
            LUCIA_RL_CONFIG[clave] = valor
    return dict(LUCIA_RL_CONFIG)


def _dt() -> np.dtype:
    return np.dtype(_DTYPE_MAP.get(str(LUCIA_RL_CONFIG.get("precision", "float32")).lower(), np.float32))


def _now() -> float:
    return time.perf_counter()


class HerramientasRefuerzo:
    """Unifica las funciones sueltas de refuerzo en clases anidadas.

    - Inicializacion: He, Xavier, LeCun, ortogonal, espectral y comparativas.
    - Recompensas: descuento, normalización, GAE, Huber, entropía y softmax.
    - Buffers: experiencia simple y priorizada (PER).
    - Entrenamiento: clipping, scheduler, parada temprana y epochs.
    - Metricas: evaluación, convergencia y recuento de parámetros.
    """

    class Inicializacion:
        """Inicializadores de pesos y comparativas de varianza."""

        @staticmethod
        def he(shape, fan_in: int = 1) -> np.ndarray:
            return np.random.normal(0, math.sqrt(2.0 / max(1, fan_in)), shape).astype(_dt())

        @staticmethod
        def xavier(shape, fan_in: int = 1, fan_out: int = 1) -> np.ndarray:
            lim = math.sqrt(6.0 / max(1, fan_in + fan_out))
            return np.random.uniform(-lim, lim, shape).astype(_dt())

        @staticmethod
        def lecun(shape, fan_in: int = 1) -> np.ndarray:
            return np.random.normal(0, math.sqrt(1.0 / max(1, fan_in)), shape).astype(_dt())

        @staticmethod
        def ortogonal(shape) -> np.ndarray:
            wf = np.random.randn(*shape).astype(np.float64)
            v = np.random.default_rng(0).normal(0, 1, (wf.shape[1], 1))
            v /= max(1e-12, np.linalg.norm(v))
            u = v
            for _ in range(3):
                u = wf @ v
                u /= max(1e-12, np.linalg.norm(u))
                v = wf.T @ u
                v /= max(1e-12, np.linalg.norm(v))
            r = (u.T @ wf @ v)[0, 0]
            return np.random.randn(*shape).astype(_dt()) * abs(r)

        @staticmethod
        def espectral(shape) -> np.ndarray:
            wf = np.random.randn(*shape).astype(np.float64)
            v = np.random.default_rng(0).normal(0, 1, (wf.shape[1], 1))
            v /= max(1e-12, np.linalg.norm(v))
            u = v
            for _ in range(3):
                u = wf @ v
                u /= max(1e-12, np.linalg.norm(u))
                v = wf.T @ u
                v /= max(1e-12, np.linalg.norm(v))
            s = abs((u.T @ wf @ v)[0, 0])
            return (np.random.randn(*shape) * s / max(1e-12, np.linalg.norm(wf))).astype(_dt())

        @staticmethod
        def por_metodo(metodo: str, shape, fan_in: int = 1, fan_out: int = 1) -> np.ndarray:
            metodos = {
                "he": HerramientasRefuerzo.Inicializacion.he,
                "xavier": HerramientasRefuerzo.Inicializacion.xavier,
                "lecun": HerramientasRefuerzo.Inicializacion.lecun,
                "ortogonal": HerramientasRefuerzo.Inicializacion.ortogonal,
                "espectral": HerramientasRefuerzo.Inicializacion.espectral,
            }
            fn = metodos.get(metodo, HerramientasRefuerzo.Inicializacion.he)
            if metodo == "xavier":
                return fn(shape, fan_in, fan_out)
            if metodo in ("ortogonal", "espectral"):
                return fn(shape)
            return fn(shape, fan_in)

        @staticmethod
        def layer_init(layer, method: str = "xavier", fan_in: int = 1) -> np.ndarray:
            fn = {
                "he": HerramientasRefuerzo.Inicializacion.he,
                "xavier": HerramientasRefuerzo.Inicializacion.xavier,
                "lecun": HerramientasRefuerzo.Inicializacion.lecun,
                "ortogonal": HerramientasRefuerzo.Inicializacion.ortogonal,
            }.get(method, HerramientasRefuerzo.Inicializacion.xavier)
            shape = layer.shape if hasattr(layer, "shape") else (fan_in, layer)
            return fn(shape, fan_in)

        @staticmethod
        def comparar(input_size: int, output_size: int, n_pruebas: int = 100) -> Dict[str, float]:
            resultados: Dict[str, Dict[str, float]] = {}
            for nombre in ("he", "xavier", "lecun", "ortogonal"):
                medias = [
                    float(np.mean(np.abs(HerramientasRefuerzo.Inicializacion.por_metodo(
                        nombre, (input_size, output_size)))))
                    for _ in range(n_pruebas)
                ]
                resultados[nombre] = {
                    "media": float(np.mean(medias)),
                    "std": float(np.std(medias)),
                    "max": float(np.max(medias)),
                }
            return resultados

    class Recompensas:
        """Retornos, ventajas, pérdidas y normalizaciones."""

        @staticmethod
        def descuento(recompensas: List[float], gamma: float) -> np.ndarray:
            n = len(recompensas)
            discounted = np.zeros(n, dtype=np.float64)
            acum = 0.0
            for t in range(n - 1, -1, -1):
                acum = recompensas[t] + gamma * acum
                discounted[t] = acum
            return discounted

        @staticmethod
        def normalizar(recompensas: np.ndarray) -> np.ndarray:
            media = np.mean(recompensas)
            std = np.std(recompensas)
            return (recompensas - media) / max(1e-8, std)

        @staticmethod
        def gae(recompensas: List[float], valores: List[float],
                gamma: float = 0.99, lambda_gae: float = 0.95) -> np.ndarray:
            rews = np.array(recompensas, dtype=np.float64)
            vals = np.array(valores, dtype=np.float64)
            n = len(rews)
            advantages = np.zeros(n, dtype=np.float64)
            adv = 0.0
            for t in range(n - 1, -1, -1):
                nv = 0.0 if t == n - 1 else vals[t + 1]
                delta = rews[t] + gamma * nv - vals[t]
                adv = delta + gamma * lambda_gae * adv
                advantages[t] = adv
            return advantages

        @staticmethod
        def huber(error: np.ndarray, delta: float = 1.0) -> float:
            abs_err = np.abs(error)
            quadratic = np.minimum(abs_err, delta)
            linear = abs_err - quadratic
            return float(np.mean(0.5 * quadratic ** 2 + delta * linear))

        @staticmethod
        def entropia(prob: np.ndarray) -> float:
            p = np.abs(prob)
            p = p / max(1e-12, p.sum())
            return float(-np.sum(p * np.log(p + 1e-8)))

        @staticmethod
        def loss(y_pred: np.ndarray, y_target: np.ndarray) -> float:
            return float(np.mean((y_pred - y_target) ** 2))

        @staticmethod
        def mean_std(data: np.ndarray) -> Tuple[np.ndarray, float, float]:
            media = float(np.mean(data))
            std = float(np.std(data))
            return (data - media) / max(1e-8, std), media, std

        @staticmethod
        def gumbel_softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
            gumbel = -np.log(-np.log(np.random.uniform(1e-8, 1.0, size=logits.shape)))
            y = logits + gumbel
            y /= max(1e-12, temperature)
            e = np.exp(y - np.max(y, axis=-1, keepdims=True))
            return e / np.sum(e, axis=-1, keepdims=True)

    class Buffers:
        """Buffers de experiencia simple y priorizada (PER)."""

        @staticmethod
        def experiencia(capacidad: Optional[int] = None) -> deque:
            cap = capacidad if capacidad is not None else int(LUCIA_RL_CONFIG.get("buffer_capacity", 10000))
            return deque(maxlen=cap)

        @staticmethod
        def muestrear(buf: deque, tamano: int) -> List[Any]:
            return random.sample(list(buf), min(tamano, len(buf)))

        @staticmethod
        def priorizado(capacidad: Optional[int] = None, alpha: Optional[float] = None) -> Dict:
            cap = capacidad if capacidad is not None else int(LUCIA_RL_CONFIG.get("buffer_capacity", 10000))
            a = alpha if alpha is not None else float(LUCIA_RL_CONFIG.get("per_alpha", 0.6))
            return {"buffer": deque(maxlen=cap), "prioridades": deque(maxlen=cap), "alpha": a}

        @staticmethod
        def muestrear_priorizado(buffer: Dict, tamano: int, beta: float = 0.4) -> List[Any]:
            buf = buffer["buffer"]
            pri = buffer["prioridades"]
            if len(buf) < tamano:
                return []
            pa = np.array(list(pri))
            pb = pa ** buffer["alpha"]
            pb /= np.sum(pb)
            idx = np.random.choice(len(buf), size=tamano, replace=False, p=pb)
            return [buf[i] for i in idx], idx, pb[idx]

        @staticmethod
        def actualizar_prioridades(buffer: Dict, indices: List[int],
                                   errores: np.ndarray, beta: float = 0.4) -> None:
            for idx, err in zip(indices, errores):
                if idx < len(buffer["prioridades"]):
                    buffer["prioridades"][idx] = (abs(err) + 1e-6) ** beta

    class Entrenamiento:
        """Clipping, scheduler, parada temprana y epochs sobre neuronas."""

        @staticmethod
        def clip_gradientes(gradiente: np.ndarray, max_norm: float = 0.5) -> np.ndarray:
            norma = np.linalg.norm(gradiente)
            if norma > max_norm:
                return gradiente * max_norm / (norma + 1e-8)
            return gradiente

        @staticmethod
        def lr_scheduler(step: int, initial_lr: float, decay: float = 0.99) -> float:
            return initial_lr * (decay ** step)

        @staticmethod
        def parada_temprana(historial: List[float], paciencia: int = 20,
                            umbral: float = 1e-4) -> bool:
            if len(historial) < paciencia + 5:
                return False
            reciente = historial[-paciencia:]
            mejor = min(reciente)
            mejor_idx = reciente.index(mejor)
            if paciencia - mejor_idx > paciencia * 0.8:
                return True
            return bool(np.var(reciente) < umbral)

        @staticmethod
        def lote(neurona, batch: List[Dict[str, Any]],
                 max_norm: float = 0.5) -> Optional[float]:
            if hasattr(neurona, "calcular_gradientes_rainbow"):
                gw, gs = neurona.calcular_gradientes_rainbow(batch)
                gw = HerramientasRefuerzo.Entrenamiento.clip_gradientes(gw, max_norm)
                gs = HerramientasRefuerzo.Entrenamiento.clip_gradientes(gs, max_norm)
                neurona.actualizar_pesos(gw, gs)
            elif hasattr(neurona, "calcular_gradientes_impala"):
                gw = neurona.calcular_gradientes_impala(batch, 0)
                neurona.actualizar_pesos_learner(*gw)
            else:
                return None
            return neurona.estadisticas_td3.get("loss_medio", 0.0) if hasattr(neurona, "estadisticas_td3") else 0.0

        @staticmethod
        def epoch(neurona, dataset: List, batch_size: int = 32,
                  max_norm: float = 0.5) -> float:
            random.shuffle(dataset)
            total_loss = 0.0
            n_batches = 0
            for i in range(0, len(dataset), batch_size):
                batch = dataset[i:i + batch_size]
                result = HerramientasRefuerzo.Entrenamiento.lote(neurona, batch, max_norm)
                if result is not None:
                    total_loss += result
                    n_batches += 1
            return total_loss / max(1, n_batches)

        @staticmethod
        def paralelo(neuronas: List, dataset: List, batch_size: int = 32) -> List[float]:
            return [HerramientasRefuerzo.Entrenamiento.epoch(n, dataset, batch_size) for n in neuronas]

    class Metricas:
        """Evaluación, convergencia y recuento de parámetros."""

        @staticmethod
        def optimizador(name: str) -> str:
            optimizers = {"sgd": "SGD", "adam": "Adam", "rmsprop": "RMSprop", "adagrad": "Adagrad"}
            return optimizers.get(name.lower(), "Adam")

        @staticmethod
        def contar_parametros(model) -> int:
            total = 0
            for attr in dir(model):
                if attr.startswith("pesos") or attr.startswith("sesgo"):
                    val = getattr(model, attr)
                    if isinstance(val, np.ndarray) and val.size > 0:
                        total += val.size
            return total

        @staticmethod
        def neurona_info(neurona) -> Dict[str, Any]:
            return {
                "nombre": neurona.nombre,
                "input_size": neurona.input_size,
                "output_size": neurona.output_size,
                "pasos": neurona.pasos,
                "params": HerramientasRefuerzo.Metricas.contar_parametros(neurona),
                "historial_len": len(neurona.historial_gradientes),
            }

        @staticmethod
        def evaluar(neurona, estados_test, acciones_test,
                    recompensas_test) -> Dict[str, float]:
            if (not hasattr(neurona, "pesos_q_principal")
                    and not hasattr(neurona, "pesos_actor")
                    and not hasattr(neurona, "pesos_actor_global")):
                neurona.inicializar_pesos()
            preds = neurona.forward(estados_test)
            if isinstance(preds, tuple):
                preds = preds[0]
            preds_2d = np.atleast_2d(preds) if preds.ndim == 1 else preds
            if preds_2d.shape[1] > 1:
                acc = float(np.mean(np.argmax(preds_2d, axis=1) == acciones_test))
                mse = float(np.mean(
                    (preds_2d[np.arange(len(acciones_test)), acciones_test] - recompensas_test) ** 2))
            else:
                acc = 0.0
                mse = float(np.mean((preds_2d.flatten() - recompensas_test) ** 2))
            return {"accuracy": acc, "mse": mse, "n_muestras": len(estados_test)}

        @staticmethod
        def convergencia(historial: List[float], ventana: int = 50) -> Dict[str, float]:
            if len(historial) < 2:
                return {"convergencia": 0.0, "tendencia": 0.0, "varianza": 0.0}
            reciente = np.array(historial[-ventana:])
            var = float(np.var(reciente))
            if len(reciente) >= 10:
                pendiente = float(np.polyfit(range(len(reciente)), reciente, 1)[0])
            else:
                pendiente = 0.0
            return {
                "convergencia": float(1.0 / (1.0 + var)),
                "tendencia": pendiente,
                "varianza": var,
                "media": float(np.mean(reciente)),
                "min": float(np.min(reciente)),
                "max": float(np.max(reciente)),
            }

    # ------------------------------------------------------------------
    # API de instancia: delega en las clases anidadas con la config global
    # ------------------------------------------------------------------
    def inicializar(self, shape, metodo: str = "he", fan_in: int = 1,
                    fan_out: int = 1) -> np.ndarray:
        return self.Inicializacion.por_metodo(metodo, shape, fan_in, fan_out)

    def recompensas_descontadas(self, recompensas: List[float],
                                gamma: Optional[float] = None) -> np.ndarray:
        g = gamma if gamma is not None else float(LUCIA_RL_CONFIG.get("gamma", 0.99))
        return self.Recompensas.descuento(recompensas, g)

    def ventajas_gae(self, recompensas: List[float], valores: List[float],
                     gamma: Optional[float] = None,
                     lambda_gae: Optional[float] = None) -> np.ndarray:
        g = gamma if gamma is not None else float(LUCIA_RL_CONFIG.get("gamma", 0.99))
        lam = lambda_gae if lambda_gae is not None else float(LUCIA_RL_CONFIG.get("lambda_gae", 0.95))
        return self.Recompensas.gae(recompensas, valores, g, lam)

    def clip(self, gradiente: np.ndarray, max_norm: Optional[float] = None) -> np.ndarray:
        m = max_norm if max_norm is not None else float(LUCIA_RL_CONFIG.get("grad_clip", 0.5))
        return self.Entrenamiento.clip_gradientes(gradiente, m)

    def buffer(self, capacidad: Optional[int] = None) -> deque:
        return self.Buffers.experiencia(capacidad)

    def buffer_priorizado(self, capacidad: Optional[int] = None,
                          alpha: Optional[float] = None) -> Dict:
        return self.Buffers.priorizado(capacidad, alpha)

    def muestrear(self, buf: deque, tamano: int) -> List[Any]:
        return self.Buffers.muestrear(buf, tamano)

    def evaluar(self, neurona, estados_test, acciones_test,
                recompensas_test) -> Dict[str, float]:
        return self.Metricas.evaluar(neurona, estados_test, acciones_test, recompensas_test)

    def convergencia(self, historial: List[float], ventana: int = 50) -> Dict[str, float]:
        return self.Metricas.convergencia(historial, ventana)

    def resumen_neurona(self, neurona) -> Dict[str, Any]:
        return self.Metricas.neurona_info(neurona)


class NeuronaRefuerzoBase:
    """Base de las neuronas de refuerzo (pesos, sesgo e historiales)."""

    def __init__(self, input_size, output_size, nombre="NeuronaRefuerzo"):
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.pesos = None
        self.sesgo = None
        self.historial_activaciones = []
        self.historial_gradientes = []
        self.pasos = 0

    def inicializar_pesos(self):
        raise NotImplementedError

    def forward(self, e):
        raise NotImplementedError

    def resetear_historial(self):
        self.historial_activaciones = []
        self.historial_gradientes = []

    def info(self) -> str:
        return f"{self.nombre}(in={self.input_size},out={self.output_size},pasos={self.pasos})"

    def params_count(self) -> int:
        total = 0
        if self.pesos is not None:
            total += self.pesos.size
        if self.sesgo is not None:
            total += self.sesgo.size
        return total

    def add_historial_activacion(self, activacion: np.ndarray) -> None:
        self.historial_activaciones.append(activacion.copy())

    def add_historial_gradiente(self, gradiente: Dict[str, np.ndarray]) -> None:
        self.historial_gradientes.append({k: v.copy() for k, v in gradiente.items()})


# ----------------------------------------------------------------------
# Fachada de funciones (API original): delega en HerramientasRefuerzo
# ----------------------------------------------------------------------
_H = HerramientasRefuerzo


def inicializar_pesos_he(shape, fan_in: int = 1) -> np.ndarray:
    return _H.Inicializacion.he(shape, fan_in)


def inicializar_pesos_xavier(shape, fan_in: int = 1, fan_out: int = 1) -> np.ndarray:
    return _H.Inicializacion.xavier(shape, fan_in, fan_out)


def inicializar_pesos_lecun(shape, fan_in: int = 1) -> np.ndarray:
    return _H.Inicializacion.lecun(shape, fan_in)


def inicializar_pesos_ortogonal(shape) -> np.ndarray:
    return _H.Inicializacion.ortogonal(shape)


def inicializar_pesos_espectral(shape) -> np.ndarray:
    return _H.Inicializacion.espectral(shape)


def inicializar_pesos_eficiente(shape, method: str = "he", fan_in: int = 1) -> np.ndarray:
    return _H.Inicializacion.por_metodo(method, shape, fan_in)


def layer_init(layer, method: str = "xavier", fan_in: int = 1) -> np.ndarray:
    return _H.Inicializacion.layer_init(layer, method, fan_in)


def comparar_inicializaciones(input_size: int, output_size: int,
                              n_pruebas: int = 100) -> Dict[str, float]:
    return _H.Inicializacion.comparar(input_size, output_size, n_pruebas)


def calcular_recompensa_descontada(recompensas: List[float], gamma: float) -> np.ndarray:
    return _H.Recompensas.descuento(recompensas, gamma)


def compute_returns(recompensas: List[float], gamma: float) -> np.ndarray:
    return _H.Recompensas.descuento(recompensas, gamma)


def discount_cumulative_returns(recompensas: List[float], gamma: float) -> np.ndarray:
    return _H.Recompensas.descuento(recompensas, gamma)


def normalizar_recompensas(recompensas: np.ndarray) -> np.ndarray:
    return _H.Recompensas.normalizar(recompensas)


def calcular_gae(recompensas: List[float], valores: List[float], gamma: float = 0.99,
                 lambda_gae: float = 0.95) -> np.ndarray:
    return _H.Recompensas.gae(recompensas, valores, gamma, lambda_gae)


def huber_loss(error: np.ndarray, delta: float = 1.0) -> float:
    return _H.Recompensas.huber(error, delta)


def calcular_entropy(prob: np.ndarray) -> float:
    return _H.Recompensas.entropia(prob)


def calcular_loss(y_pred: np.ndarray, y_target: np.ndarray) -> float:
    return _H.Recompensas.loss(y_pred, y_target)


def mean_std_normalize(data: np.ndarray) -> Tuple[np.ndarray, float, float]:
    return _H.Recompensas.mean_std(data)


def sample_gumbel_softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    return _H.Recompensas.gumbel_softmax(logits, temperature)


def crear_buffer_experiencia(capacidad: int = 10000) -> deque:
    return _H.Buffers.experiencia(capacidad)


def muestrear_buffer(buffer: deque, tamano: int) -> List[Any]:
    return _H.Buffers.muestrear(buffer, tamano)


def crear_buffer_priorizado(capacidad: int = 10000, alpha: float = 0.6) -> Dict:
    return _H.Buffers.priorizado(capacidad, alpha)


def muestrear_priorizado(buffer: Dict, tamano: int, beta: float = 0.4) -> List[Any]:
    return _H.Buffers.muestrear_priorizado(buffer, tamano, beta)


def actualizar_prioridades(buffer: Dict, indices: List[int], errores: np.ndarray,
                           beta: float = 0.4) -> None:
    _H.Buffers.actualizar_prioridades(buffer, indices, errores, beta)


def aplicar_clip_gradientes(gradiente: np.ndarray, max_norm: float = 0.5) -> np.ndarray:
    return _H.Entrenamiento.clip_gradientes(gradiente, max_norm)


def lr_scheduler(step: int, initial_lr: float, decay: float = 0.99) -> float:
    return _H.Entrenamiento.lr_scheduler(step, initial_lr, decay)


def early_stopping_check(historial: List[float], paciencia: int = 20,
                         umbral: float = 1e-4) -> bool:
    return _H.Entrenamiento.parada_temprana(historial, paciencia, umbral)


def train_batch_neuron(neurona, batch: List[Dict[str, Any]],
                       max_norm: float = 0.5) -> Optional[float]:
    return _H.Entrenamiento.lote(neurona, batch, max_norm)


def train_epoch(neurona, dataset: List, batch_size: int = 32,
                max_norm: float = 0.5) -> float:
    return _H.Entrenamiento.epoch(neurona, dataset, batch_size, max_norm)


def parallel_train(neuronas: List, dataset: List, batch_size: int = 32) -> List[float]:
    return _H.Entrenamiento.paralelo(neuronas, dataset, batch_size)


def get_optimizer(name: str, params, lr: float = 0.001):
    return _H.Metricas.optimizador(name)


def count_parameters(model) -> int:
    return _H.Metricas.contar_parametros(model)


def neuron_info(neurona) -> Dict[str, Any]:
    return _H.Metricas.neurona_info(neurona)


def evaluate_neurona(neurona, estados_test, acciones_test,
                     recompensas_test) -> Dict[str, float]:
    return _H.Metricas.evaluar(neurona, estados_test, acciones_test, recompensas_test)


def analizar_convergencia(historial: List[float], ventana: int = 50) -> Dict[str, float]:
    return _H.Metricas.convergencia(historial, ventana)


class GestorEntrenamientoRefuerzo:
    """Distribuye el entrenamiento entre varias neuronas de refuerzo.

    Reparte el dataset en lotes justos por neurona, acumula el historial de
    pérdidas por neurona, vigila la parada temprana y resume el estado final.
    """

    def __init__(self, neuronas: Optional[List[Any]] = None, batch_size: int = 32,
                 max_norm: float = 0.5, semilla: Optional[int] = None):
        self.neuronas: List[Any] = list(neuronas or [])
        self.batch_size = int(batch_size)
        self.max_norm = float(max_norm)
        self.semilla = int(LUCIA_RL_CONFIG.get("random_seed", 0)) if semilla is None else int(semilla)
        self.rng = random.Random(self.semilla)
        self.historial_loss: Dict[str, List[float]] = {}
        self.ultimo_reparto: Dict[str, int] = {}
        self._claves: Dict[int, str] = {}
        for neurona in self.neuronas:
            self._clave(neurona)

    def registrar(self, neurona) -> str:
        self.neuronas.append(neurona)
        return self._clave(neurona)

    def _clave(self, neurona) -> str:
        clave = self._claves.get(id(neurona))
        if clave is None:
            base = str(getattr(neurona, "nombre", type(neurona).__name__))
            usadas = set(self._claves.values())
            clave = base
            sufijo = 2
            while clave in usadas:
                clave = f"{base}#{sufijo}"
                sufijo += 1
            self._claves[id(neurona)] = clave
            self.historial_loss.setdefault(clave, [])
        return clave

    def repartir_lotes(self, dataset: List[Any]) -> Dict[str, List[Any]]:
        """Divide el dataset en bloques contiguos justos entre las neuronas."""
        reparto: Dict[str, List[Any]] = {}
        if not self.neuronas:
            self.ultimo_reparto = {}
            return reparto
        base, resto = divmod(len(dataset), len(self.neuronas))
        inicio = 0
        for i, neurona in enumerate(self.neuronas):
            tamano = base + (1 if i < resto else 0)
            reparto[self._clave(neurona)] = dataset[inicio:inicio + tamano]
            inicio += tamano
        self.ultimo_reparto = {k: len(v) for k, v in reparto.items()}
        return reparto

    def entrenar_epoch(self, dataset: List[Any], barajar: bool = True) -> Dict[str, float]:
        datos = list(dataset)
        if barajar:
            self.rng.shuffle(datos)
        reparto = self.repartir_lotes(datos)
        losses: Dict[str, float] = {}
        for neurona in self.neuronas:
            clave = self._clave(neurona)
            sub = reparto.get(clave, [])
            if not sub:
                continue
            loss = _H.Entrenamiento.epoch(neurona, sub, self.batch_size, self.max_norm)
            self.historial_loss[clave].append(float(loss))
            losses[clave] = float(loss)
        return losses

    def entrenar(self, dataset: List[Any], epocas: int = 1, paciencia: int = 20,
                 umbral: float = 1e-4) -> Dict[str, Any]:
        historial_epocas: List[Dict[str, float]] = []
        detenido = False
        for _ in range(max(0, int(epocas))):
            losses = self.entrenar_epoch(dataset)
            historial_epocas.append(losses)
            if self.parada_temprana(paciencia, umbral):
                detenido = True
                break
        return {
            "epocas": len(historial_epocas),
            "detenido": detenido,
            "loss": historial_epocas[-1] if historial_epocas else {},
            "historial": historial_epocas,
        }

    def parada_temprana(self, paciencia: int = 20, umbral: float = 1e-4) -> bool:
        historiales = [h for h in self.historial_loss.values() if h]
        if not historiales:
            return False
        return all(_H.Entrenamiento.parada_temprana(h, paciencia, umbral) for h in historiales)

    def evaluar(self, estados_test, acciones_test,
                recompensas_test) -> Dict[str, Dict[str, float]]:
        return {
            self._clave(neurona): _H.Metricas.evaluar(
                neurona, estados_test, acciones_test, recompensas_test)
            for neurona in self.neuronas
        }

    def mejor_neurona(self) -> Optional[Dict[str, Any]]:
        mejor = None
        for neurona in self.neuronas:
            clave = self._clave(neurona)
            historial = self.historial_loss[clave]
            if not historial:
                continue
            if mejor is None or historial[-1] < mejor["loss"]:
                mejor = {"clave": clave, "loss": historial[-1], "neurona": neurona}
        return mejor

    def resumen(self) -> Dict[str, Any]:
        detalle = []
        for neurona in self.neuronas:
            clave = self._clave(neurona)
            info = _H.Metricas.neurona_info(neurona)
            info["clave"] = clave
            info["loss_medio"] = (float(np.mean(self.historial_loss[clave]))
                                  if self.historial_loss[clave] else None)
            info["convergencia"] = _H.Metricas.convergencia(self.historial_loss[clave])
            detalle.append(info)
        return {
            "neuronas": detalle,
            "params_total": sum(d["params"] for d in detalle),
            "reparto": dict(self.ultimo_reparto),
            "semilla": self.semilla,
        }


__all__ = [
    "LUCIA_RL_CONFIG",
    "actualizar_config",
    "HerramientasRefuerzo",
    "NeuronaRefuerzoBase",
    "GestorEntrenamientoRefuerzo",
    "inicializar_pesos_he",
    "inicializar_pesos_xavier",
    "inicializar_pesos_lecun",
    "inicializar_pesos_ortogonal",
    "inicializar_pesos_espectral",
    "inicializar_pesos_eficiente",
    "layer_init",
    "comparar_inicializaciones",
    "calcular_recompensa_descontada",
    "compute_returns",
    "discount_cumulative_returns",
    "normalizar_recompensas",
    "calcular_gae",
    "huber_loss",
    "calcular_entropy",
    "calcular_loss",
    "mean_std_normalize",
    "sample_gumbel_softmax",
    "crear_buffer_experiencia",
    "muestrear_buffer",
    "crear_buffer_priorizado",
    "muestrear_priorizado",
    "actualizar_prioridades",
    "aplicar_clip_gradientes",
    "lr_scheduler",
    "early_stopping_check",
    "train_batch_neuron",
    "train_epoch",
    "parallel_train",
    "get_optimizer",
    "count_parameters",
    "neuron_info",
    "evaluate_neurona",
    "analizar_convergencia",
    "_Ring",
    "_RingBufferNumpy",
]


class _Ring:
    """Buffer circular en lista (capacidad fija)."""

    def __init__(self, cap: int):
        self.cap = cap
        self._d: List[Any] = []

    def append(self, x) -> None:
        self._d.append(x)
        if len(self._d) > self.cap:
            del self._d[0:len(self._d) - self.cap]

    def __len__(self) -> int:
        return len(self._d)

    def __getitem__(self, i: int) -> Any:
        return self._d[i]

    def __iter__(self):
        return iter(self._d)

    def clear(self) -> None:
        self._d.clear()

    @property
    def full(self) -> bool:
        return len(self._d) == self.cap


class _RingBufferNumpy:
    """Buffer circular sobre ndarray de objetos (posición y contador)."""

    def __init__(self, cap: int, dtype: np.dtype = np.float32):
        self.cap = cap
        self._pos = 0
        self._count = 0
        self._data = np.zeros((cap,), dtype=object)
        self._dtype = dtype

    def append(self, x) -> None:
        self._data[self._pos] = x
        self._pos = (self._pos + 1) % self.cap
        if self._count < self.cap:
            self._count += 1

    def __len__(self) -> int:
        return self._count

    def __getitem__(self, i: int) -> Any:
        if i >= self._count:
            raise IndexError(i)
        return self._data[(self._pos - self._count + i) % self.cap]

    def to_array(self) -> np.ndarray:
        return np.array(
            [self._data[(self._pos - self._count + i) % self.cap] for i in range(self._count)],
            dtype=self._dtype,
        )

    def sample(self, n: int) -> List[Any]:
        if n >= self._count:
            return list(self._data[:self._count])
        idx = np.random.choice(self._count, size=n, replace=False)
        return [self._data[i] for i in idx]

    def clear(self) -> None:
        self._pos = 0
        self._count = 0
        self._data = np.zeros((self.cap,), dtype=object)

    @property
    def full(self) -> bool:
        return self._count == self.cap
