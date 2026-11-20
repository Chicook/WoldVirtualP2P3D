"""Módulo local de neurona y utilidades de red (parte 2 de ENRN)."""

import functools
import json
import logging
import os
import time

import numpy as np
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from .sbrtm_import1 import (
        LUCIA_CONFIG,
        LucIANeuronBase,
        LucIAInitializers,
        core_he,
        core_xavier,
        core_lecun,
        _dtype,
        _rng,
    )
except ImportError:
    import importlib.util as _ilu
    _base = os.path.dirname(os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location('sbrtm_import1', os.path.join(_base, 'sbrtm_import1.py'))
    _m1 = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_m1)
    LUCIA_CONFIG = _m1.LUCIA_CONFIG
    LucIANeuronBase = _m1.LucIANeuronBase
    LucIAInitializers = _m1.LucIAInitializers
    core_he = _m1.core_he
    core_xavier = _m1.core_xavier
    core_lecun = _m1.core_lecun
    _dtype = _m1._dtype
    _rng = _m1._rng

logger = logging.getLogger('ENRN.Neuron')

__version__ = '1.1.0'
__autor__ = 'LucIA Development Team'

_REGISTRO: Dict[str, type] = {}


def _como_matriz(fn: Callable) -> Callable:
    """Decorador: fuerza la primera entrada a matriz 2D en dtype de trabajo."""
    @functools.wraps(fn)
    def envoltura(self: Any, x: np.ndarray, *args: Any, **kwargs: Any) -> np.ndarray:
        a = np.asarray(x, dtype=_dtype())
        if a.ndim == 1:
            a = a.reshape(1, -1)
        return fn(self, a, *args, **kwargs)
    return envoltura


class Neuron:
    """Neurona densa local con clases anidadas de soporte."""

    class Inicializacion:
        """Despachador unificado de inicializadores de pesos y sesgo."""

        @staticmethod
        def pesos(nombre: str, shape: Tuple[int, ...], fan_in: int,
                  fan_out: Optional[int] = None,
                  rng: Optional[np.random.Generator] = None) -> np.ndarray:
            nombre = (nombre or 'xavier').strip().lower()
            if nombre == 'xavier':
                return core_xavier(shape, fan_in, fan_out or fan_in, rng)
            if nombre == 'he':
                return core_he(shape, fan_in, rng)
            if nombre == 'lecun':
                return core_lecun(shape, fan_in, rng)
            raise ValueError(f"Inicializador no soportado: {nombre}")

        @staticmethod
        def sesgo(shape: Tuple[int, ...]) -> np.ndarray:
            return np.zeros(shape, dtype=_dtype())

    class Normalizacion:
        """Normalización vectorizada con despachador unificado."""

        @staticmethod
        def z_score(x: np.ndarray) -> np.ndarray:
            return ((x - np.mean(x)) / (np.std(x) + 1e-8)).astype(_dtype())

        @staticmethod
        def min_max(x: np.ndarray) -> np.ndarray:
            return ((x - np.min(x)) / (np.max(x) - np.min(x) + 1e-8)).astype(_dtype())

        @staticmethod
        def robusta(x: np.ndarray) -> np.ndarray:
            med = np.median(x)
            iqr = float(np.percentile(x, 75) - np.percentile(x, 25)) + 1e-8
            return ((x - med) / iqr).astype(_dtype())

        @staticmethod
        def aplicar(x: np.ndarray, metodo: str = 'z_score') -> np.ndarray:
            x = np.asarray(x, dtype=_dtype())
            metodos = {
                'z_score': Neuron.Normalizacion.z_score,
                'min_max': Neuron.Normalizacion.min_max,
                'robusta': Neuron.Normalizacion.robusta,
            }
            fn = metodos.get((metodo or 'z_score').strip().lower())
            return fn(x) if fn else x

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = 'Neurona',
                 rng: Optional[np.random.Generator] = None) -> None:
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.pesos: Optional[np.ndarray] = None
        self.sesgo: Optional[np.ndarray] = None
        self.historial_activaciones: List[np.ndarray] = []
        self.historial_gradientes: List[np.ndarray] = []
        self.llm_connector = None
        self._system_ref = None
        self.rng = rng or _rng()

    def initialize_weights(self, initializer: str = 'xavier',
                           fan_in: Optional[int] = None) -> None:
        self.pesos = self.Inicializacion.pesos(
            initializer, (self.output_size, self.input_size),
            fan_in or self.input_size, self.output_size, self.rng)
        self.sesgo = self.Inicializacion.sesgo((self.output_size,))

    @_como_matriz
    def forward(self, x: np.ndarray) -> np.ndarray:
        if self.pesos is None or self.sesgo is None:
            self.initialize_weights()
        a = x @ self.pesos.T + self.sesgo
        self.historial_activaciones.append(a)
        return a

    @_como_matriz
    def grad_entrada(self, g: np.ndarray) -> np.ndarray:
        if self.pesos is None:
            self.initialize_weights()
        return g @ self.pesos

    def recibir_respuesta_llm(self, respuesta: str) -> None:
        logger.info(f"[Neurona {self.nombre}] Respuesta LLM recibida. Procesando...")
        self.ultima_respuesta_llm = respuesta
        self.prompt_propio = (
            f"Soy la neurona de entrada {self.nombre}. He recibido este analisis global: {respuesta}. "
            f"Basandote en tu fortaleza especifica (logica, codigo o eficiencia), "
            f"genera una directiva tecnica ultra-especifica para el resto de la red neuronal."
        )

    def a_dict(self) -> Dict[str, Any]:
        return {
            'nombre': self.nombre,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'pesos': None if self.pesos is None else self.pesos.tolist(),
            'sesgo': None if self.sesgo is None else self.sesgo.tolist(),
        }


def _legacy_inicial(nombre: str, fan_in: int, fan_out: int) -> float:
    """Despachador unificado de los wrappers legacy de inicialización."""
    fan_in = max(1, int(fan_in))
    fan_out = max(1, int(fan_out))
    tabla = {
        'he': (core_he, float(np.sqrt(2.0 / fan_in))),
        'xavier': (core_xavier, float(np.sqrt(1.0 / max(1, (fan_in + fan_out) / 2.0)))),
        'lecun': (core_lecun, float(np.sqrt(1.0 / fan_in))),
    }
    fn, respaldo = tabla[nombre]
    try:
        if nombre == 'xavier':
            return float(fn((1, 1), fan_in=fan_in, fan_out=fan_out).item())
        return float(fn((1, 1), fan_in=fan_in).item())
    except Exception:
        return respaldo


def he_initialization(fan_in: int, fan_out: int) -> float:
    return _legacy_inicial('he', fan_in, fan_out)


def xavier_initialization(fan_in: int, fan_out: int) -> float:
    return _legacy_inicial('xavier', fan_in, fan_out)


def lecun_initialization(fan_in: int, fan_out: int) -> float:
    return _legacy_inicial('lecun', fan_in, fan_out)


def normalizar_datos(datos: np.ndarray, metodo: str = 'z_score') -> np.ndarray:
    return Neuron.Normalizacion.aplicar(datos, metodo)


def crear_neurona(tipo: str, input_size: int, output_size: int, **kw: Any) -> Neuron:
    """Crea una neurona por tipo, usando el registro o una Neurona por defecto."""
    clave = str(tipo).lower()
    clase = _REGISTRO.get(clave)
    if clase is not None:
        return clase(input_size, output_size, **kw)
    inicializador = {'xavier': 'xavier', 'lecun': 'lecun'}.get(clave, 'he')
    n = Neuron(input_size, output_size, **kw)
    n.initialize_weights(inicializador)
    return n


def benchmark_neurona(neurona: Neuron, dim_in: int = 32, dim_out: int = 16,
                      iters: int = 50) -> Dict[str, float]:
    x = np.random.default_rng(0).normal(0, 1, (16, dim_in)).astype(_dtype())
    iters = max(1, int(iters))
    inicio = time.perf_counter()
    for _ in range(iters):
        neurona.forward(x)
    duracion = time.perf_counter() - inicio
    return {'iters': iters, 'segundos': duracion, 'media_ms': duracion / iters * 1000.0}


def _as_array(x: np.ndarray) -> np.ndarray:
    return np.asarray(x, dtype=_dtype())


def _validate_lote(x: np.ndarray, dim: int) -> np.ndarray:
    a = _as_array(x)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if a.shape[1] != dim:
        raise ValueError(f"lote dim {a.shape[1]} != {dim}")
    return np.ascontiguousarray(a, dtype=_dtype())


def validar_lote(x: np.ndarray, dim: int) -> np.ndarray:
    return _validate_lote(x, dim)


def forward_en_cascada(neuronas: List[Neuron], x: np.ndarray) -> np.ndarray:
    a = _validate_lote(x, neuronas[0].input_size)
    for n in neuronas:
        a = n.forward(a)
    return a


def backward_en_cascada(neuronas: List[Neuron], g: np.ndarray) -> np.ndarray:
    a = _validate_lote(g, neuronas[-1].output_size)
    for n in reversed(neuronas):
        if not hasattr(n, 'grad_entrada'):
            break
        a = n.grad_entrada(a)
    return a


def guardar_red(neuronas: List[Neuron], ruta: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump([n.a_dict() if hasattr(n, 'a_dict') else {} for n in neuronas], f)


def resumen_red(neuronas: List[Neuron]) -> Dict[str, Any]:
    total_params = 0
    for n in neuronas:
        if getattr(n, 'pesos', None) is not None:
            total_params += int(np.size(n.pesos)) + int(np.size(n.sesgo))
    return {'n_neuronas': len(neuronas), 'total_params': total_params,
            'tipos': [type(n).__name__ for n in neuronas]}


def registrar_tipo(clave: str, clase: Callable[..., Neuron]) -> None:
    _REGISTRO[str(clave).lower()] = clase


def listar_tipos() -> List[str]:
    return sorted(_REGISTRO.keys()) or ['basica', 'xavier', 'lecun', 'normalizada',
                                        'regularizada', 'dropout', 'batchnorm',
                                        'relu', 'tanh', 'sigmoid']


def norma_global(neuronas: List[Neuron]) -> float:
    acc = 0.0
    for n in neuronas:
        if getattr(n, 'pesos', None) is not None:
            acc += float(np.sum(n.pesos.astype(np.float64) ** 2))
    return float(np.sqrt(acc))


def clip_global(neuronas: List[Neuron], max_norma: float = 5.0) -> float:
    ng = norma_global(neuronas)
    if ng > max_norma and ng > 0:
        f = max_norma / ng
        for n in neuronas:
            if getattr(n, 'pesos', None) is not None:
                n.pesos = (n.pesos.astype(np.float64) * f).astype(_dtype())
    return ng


def semilla_global() -> int:
    return int(LUCIA_CONFIG.get('random_seed', 42))


def info_paquete() -> Dict[str, Any]:
    return {'nombre': 'ENRN', 'version': __version__, 'precision': LUCIA_CONFIG.get('precision'),
            'tipos': listar_tipos(), 'n_tipos': len(listar_tipos())}