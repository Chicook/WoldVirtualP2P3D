"""Base local LucIA (sustituye a lucIA.CORE.base sin import externo).

Una única clase con clases anidadas de soporte: utilidades numéricas,
inicializadores, activaciones, pérdidas y optimizador.
"""

import numpy as np
from typing import Any, Callable, Dict, List, Optional, Tuple


class LucIANeuronBase:
    """Neurona densa local con soporte anidado autocontenido."""

    CONFIG = {
        'precision': 'float32',
        'random_seed': 42,
        'default_learning_rate': 0.001,
        'weight_decay': 1e-4,
        'dropout_rate': 0.1,
        'batch_norm_momentum': 0.9,
        'batch_norm_epsilon': 1e-5,
    }

    DTYPE = np.float32

    class Utilidades:
        """Utilidades numéricas unificadas."""

        @staticmethod
        def dtype() -> np.dtype:
            return LucIANeuronBase.DTYPE

        @staticmethod
        def rng(seed: Optional[int] = None) -> np.random.Generator:
            semilla = seed if seed is not None else LucIANeuronBase.CONFIG['random_seed']
            return np.random.default_rng(semilla)

        @staticmethod
        def normal(shape: Tuple[int, ...], escala: float,
                   rng: Optional[np.random.Generator] = None) -> np.ndarray:
            r = rng or LucIANeuronBase.Utilidades.rng()
            return r.normal(0.0, float(escala), shape).astype(LucIANeuronBase.DTYPE)

        @staticmethod
        def uniform(shape: Tuple[int, ...], lim: float,
                    rng: Optional[np.random.Generator] = None) -> np.ndarray:
            r = rng or LucIANeuronBase.Utilidades.rng()
            return r.uniform(-float(lim), float(lim), shape).astype(LucIANeuronBase.DTYPE)

        @staticmethod
        def zeros(shape: Tuple[int, ...]) -> np.ndarray:
            return np.zeros(shape, dtype=LucIANeuronBase.DTYPE)

        @staticmethod
        def ones(shape: Tuple[int, ...]) -> np.ndarray:
            return np.ones(shape, dtype=LucIANeuronBase.DTYPE)

    class Inicializadores:
        """Inicializadores de pesos y despachador unificado."""

        @staticmethod
        def he(shape: Tuple[int, ...], fan_in: int,
               rng: Optional[np.random.Generator] = None) -> np.ndarray:
            return LucIANeuronBase.Utilidades.normal(shape, np.sqrt(2.0 / max(1, fan_in)), rng)

        @staticmethod
        def xavier(shape: Tuple[int, ...], fan_in: int, fan_out: int,
                   rng: Optional[np.random.Generator] = None) -> np.ndarray:
            lim = np.sqrt(6.0 / max(1, fan_in + fan_out))
            return LucIANeuronBase.Utilidades.uniform(shape, lim, rng)

        @staticmethod
        def lecun(shape: Tuple[int, ...], fan_in: int,
                  rng: Optional[np.random.Generator] = None) -> np.ndarray:
            return LucIANeuronBase.Utilidades.normal(shape, np.sqrt(1.0 / max(1, fan_in)), rng)

        @staticmethod
        def obtener(nombre: str) -> Callable:
            """Devuelve la función de inicialización por nombre."""
            nombre = (nombre or 'he').strip().lower()
            tabla = {
                'he': LucIANeuronBase.Inicializadores.he,
                'xavier': LucIANeuronBase.Inicializadores.xavier,
                'lecun': LucIANeuronBase.Inicializadores.lecun,
            }
            if nombre not in tabla:
                raise ValueError(f"Inicializador no soportado: {nombre}")
            return tabla[nombre]

    class Activacion:
        """Funciones de activación explícitas con sus derivadas."""

        @staticmethod
        def identidad(x: np.ndarray) -> np.ndarray:
            return x

        @staticmethod
        def d_identidad(x: np.ndarray) -> np.ndarray:
            return LucIANeuronBase.Utilidades.ones(np.shape(x))

        @staticmethod
        def relu(x: np.ndarray) -> np.ndarray:
            return np.maximum(0.0, x)

        @staticmethod
        def d_relu(x: np.ndarray) -> np.ndarray:
            return (x > 0.0).astype(LucIANeuronBase.DTYPE)

        @staticmethod
        def leaky_relu(x: np.ndarray, alpha: float = 0.01) -> np.ndarray:
            return np.where(x > 0.0, x, alpha * x)

        @staticmethod
        def d_leaky_relu(x: np.ndarray, alpha: float = 0.01) -> np.ndarray:
            return np.where(x > 0.0, 1.0, alpha).astype(LucIANeuronBase.DTYPE)

        @staticmethod
        def sigmoid(x: np.ndarray) -> np.ndarray:
            x = np.clip(x, -500.0, 500.0)
            return 1.0 / (1.0 + np.exp(-x))

        @staticmethod
        def d_sigmoid(x: np.ndarray) -> np.ndarray:
            s = LucIANeuronBase.Activacion.sigmoid(x)
            return s * (1.0 - s)

        @staticmethod
        def tanh(x: np.ndarray) -> np.ndarray:
            return np.tanh(x)

        @staticmethod
        def d_tanh(x: np.ndarray) -> np.ndarray:
            t = np.tanh(x)
            return 1.0 - t * t

        @staticmethod
        def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
            x = x - np.max(x, axis=axis, keepdims=True)
            e = np.exp(x)
            return e / np.sum(e, axis=axis, keepdims=True)

        @staticmethod
        def obtener(nombre: str) -> Tuple[Callable, Callable]:
            """Devuelve (función, derivada) para un nombre de activación."""
            nombre = (nombre or 'relu').strip().lower()
            tabla = {
                'identidad': (LucIANeuronBase.Activacion.identidad, LucIANeuronBase.Activacion.d_identidad),
                'relu': (LucIANeuronBase.Activacion.relu, LucIANeuronBase.Activacion.d_relu),
                'leaky_relu': (LucIANeuronBase.Activacion.leaky_relu, LucIANeuronBase.Activacion.d_leaky_relu),
                'sigmoid': (LucIANeuronBase.Activacion.sigmoid, LucIANeuronBase.Activacion.d_sigmoid),
                'tanh': (LucIANeuronBase.Activacion.tanh, LucIANeuronBase.Activacion.d_tanh),
            }
            if nombre not in tabla:
                raise ValueError(f"Activación no soportada: {nombre}")
            return tabla[nombre]

    class Perdida:
        """Funciones de pérdida explícitas con sus derivadas."""

        @staticmethod
        def mse(pred: np.ndarray, objetivo: np.ndarray) -> float:
            return float(np.mean((pred - objetivo) ** 2))

        @staticmethod
        def d_mse(pred: np.ndarray, objetivo: np.ndarray) -> np.ndarray:
            return 2.0 * (pred - objetivo) / float(pred.size)

        @staticmethod
        def cross_entropy(pred: np.ndarray, objetivo: np.ndarray) -> float:
            pred = np.clip(pred, 1e-12, 1.0)
            return float(-np.sum(objetivo * np.log(pred)) / pred.shape[0])

        @staticmethod
        def d_cross_entropy(pred: np.ndarray, objetivo: np.ndarray) -> np.ndarray:
            pred = np.clip(pred, 1e-12, 1.0)
            return -objetivo / (pred * float(pred.shape[0]))

    class Optimizador:
        """SGD con momento y decaimiento de pesos."""

        def __init__(self, tasa_aprendizaje: Optional[float] = None,
                     momento: float = 0.0, decaimiento: float = 0.0) -> None:
            self.tasa = float(tasa_aprendizaje if tasa_aprendizaje is not None
                              else LucIANeuronBase.CONFIG['default_learning_rate'])
            self.momento = float(momento)
            self.decaimiento = float(decaimiento)
            self.velocidades: Dict[str, np.ndarray] = {}

        def paso(self, parametro: np.ndarray, gradiente: np.ndarray, nombre: str) -> np.ndarray:
            """Devuelve el parámetro actualizado (no muta el original)."""
            v = self.velocidades.get(nombre)
            if v is None:
                v = LucIANeuronBase.Utilidades.zeros(np.shape(parametro))
            grad_total = gradiente + self.decaimiento * parametro
            v = self.momento * v - self.tasa * grad_total
            self.velocidades[nombre] = v
            return parametro + v

        def reiniciar(self) -> None:
            self.velocidades.clear()

    def __init__(self, input_size: int = 0, output_size: int = 0,
                 nombre: str = "LucIANeurona",
                 activacion: str = 'relu',
                 tasa_aprendizaje: Optional[float] = None) -> None:
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.pesos: Optional[np.ndarray] = None
        self.sesgo: Optional[np.ndarray] = None
        self.historial_activaciones: List[np.ndarray] = []
        self.historial_gradientes: List[Dict[str, Any]] = []
        self.llm_connector = None
        self.activacion, self.d_activacion = self.Activacion.obtener(activacion)
        self.optimizador = self.Optimizador(
            tasa_aprendizaje=tasa_aprendizaje,
            decaimiento=self.CONFIG['weight_decay'])
        self._cache_entrada: Optional[np.ndarray] = None
        self._cache_z: Optional[np.ndarray] = None
        self._cache_a: Optional[np.ndarray] = None

    def inicializar_pesos(self, semilla: Optional[int] = None) -> None:
        """Inicializa pesos (He) y sesgo (ceros) para una capa densa."""
        if self.input_size <= 0:
            raise ValueError(f"{self.nombre}: input_size debe ser mayor que 0.")
        rng = self.Utilidades.rng(semilla)
        self.pesos = self.Inicializadores.he((self.input_size, self.output_size), self.input_size, rng)
        self.sesgo = self.Utilidades.zeros((self.output_size,))

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        """Propaga hacia delante: z = entrada @ pesos + sesgo; a = activacion(z)."""
        if self.pesos is None or self.sesgo is None:
            self.inicializar_pesos()
        entrada = np.asarray(entrada, dtype=self.DTYPE)
        if entrada.ndim == 1:
            entrada = entrada.reshape(1, -1)
        self._cache_entrada = entrada
        self._cache_z = entrada @ self.pesos + self.sesgo
        self._cache_a = self.activacion(self._cache_z)
        self.historial_activaciones.append(self._cache_a)
        return self._cache_a

    def backward(self, g: Optional[np.ndarray], e: Optional[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """Retropropaga el gradiente.

        Si `g` es None, se deriva del error `e` usando MSE sobre la última salida.
        Devuelve (gradiente respecto a la entrada, gradiente respecto a la salida).
        """
        if self._cache_a is None:
            raise RuntimeError(f"{self.nombre}: ejecute forward() antes de backward().")
        if g is None:
            g = self.Perdida.d_mse(self._cache_a, e)
        g = np.asarray(g, dtype=self.DTYPE)
        d_z = g * self.d_activacion(self._cache_z)
        d_entrada = d_z @ self.pesos.T
        d_pesos = self._cache_entrada.T @ d_z
        d_sesgo = np.sum(d_z, axis=0)
        self.historial_gradientes.append({'d_pesos': d_pesos, 'd_sesgo': d_sesgo, 'd_z': d_z})
        return d_entrada, d_z

    def actualizar(self) -> None:
        """Aplica los gradientes acumulados con el optimizador."""
        if not self.historial_gradientes:
            return
        grad = self.historial_gradientes[-1]
        self.pesos = self.optimizador.paso(self.pesos, grad['d_pesos'], f'{self.nombre}_pesos')
        self.sesgo = self.optimizador.paso(self.sesgo, grad['d_sesgo'], f'{self.nombre}_sesgo')
        self.historial_gradientes.clear()


# Nombres a nivel de módulo para mantener la compatibilidad con el paquete ENRN.
LUCIA_CONFIG = LucIANeuronBase.CONFIG
LucIAInitializers = LucIANeuronBase.Inicializadores
_DTYPE = LucIANeuronBase.DTYPE
_dtype = LucIANeuronBase.Utilidades.dtype
_rng = LucIANeuronBase.Utilidades.rng


def core_he(shape: Tuple[int, ...], fan_in: int = 1,
            rng: Optional[np.random.Generator] = None) -> np.ndarray:
    return LucIAInitializers.he(shape, fan_in, rng)


def core_xavier(shape: Tuple[int, ...], fan_in: int = 1, fan_out: int = 1,
                rng: Optional[np.random.Generator] = None) -> np.ndarray:
    return LucIAInitializers.xavier(shape, fan_in, fan_out, rng)


def core_lecun(shape: Tuple[int, ...], fan_in: int = 1,
               rng: Optional[np.random.Generator] = None) -> np.ndarray:
    return LucIAInitializers.lecun(shape, fan_in, rng)
