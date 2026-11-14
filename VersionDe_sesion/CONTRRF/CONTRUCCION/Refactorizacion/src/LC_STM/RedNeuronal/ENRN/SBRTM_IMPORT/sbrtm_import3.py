"""Módulo local de neuronas de entrada (parte 3 de ENRN)."""

import time

import numpy as np
from typing import Any, Dict, List

try:
    from .sbrtm_import1 import LUCIA_CONFIG, LucIANeuronBase, _dtype
except ImportError:
    import importlib.util as _ilu
    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec1 = _ilu.spec_from_file_location('sbrtm_import1', _os.path.join(_base, 'sbrtm_import1.py'))
    _m1 = _ilu.module_from_spec(_spec1)
    _spec1.loader.exec_module(_m1)
    LUCIA_CONFIG = _m1.LUCIA_CONFIG
    LucIANeuronBase = _m1.LucIANeuronBase
    _dtype = _m1._dtype


class NeuronaEntradaBase:
    """Neuronas de entrada y utilidades unificadas."""

    class Tanh(LucIANeuronBase):
        def __init__(self, input_size: int = 1, output_size: int = 1,
                     nombre: str = 'NeuronaEntradaTanh') -> None:
            super().__init__(input_size, output_size, nombre=nombre, activacion='tanh')

    class Sigmoid(LucIANeuronBase):
        def __init__(self, input_size: int = 1, output_size: int = 1,
                     nombre: str = 'NeuronaEntradaSigmoid') -> None:
            super().__init__(input_size, output_size, nombre=nombre, activacion='sigmoid')

    class Utilidades:
        """Configuración y transformaciones unificadas."""

        @staticmethod
        def validar(lote: Any) -> np.ndarray:
            a = np.asarray(lote, dtype=_dtype())
            if a.ndim == 1:
                a = a.reshape(1, -1)
            return np.ascontiguousarray(a, dtype=_dtype())

        @staticmethod
        def normalizar(datos: Any, metodo: str = 'z_score') -> np.ndarray:
            x = np.asarray(datos, dtype=_dtype())
            if metodo == 'min_max':
                return ((x - np.min(x)) / (np.max(x) - np.min(x) + 1e-8)).astype(_dtype())
            return ((x - np.mean(x)) / (np.std(x) + 1e-8)).astype(_dtype())

        @staticmethod
        def precision(valor: str) -> np.dtype:
            mapa = {'float16': np.float16, 'float32': np.float32, 'float64': np.float64}
            d = mapa.get(str(valor).lower(), np.float32)
            LUCIA_CONFIG['precision'] = str(valor)
            LucIANeuronBase.DTYPE = d
            return d

        @staticmethod
        def semilla(valor: int) -> int:
            LUCIA_CONFIG['random_seed'] = int(valor)
            return int(valor)

    class Red:
        """Cascada y evaluación unificadas."""

        @staticmethod
        def forward(neuronas: List[Any], entrada: Any) -> np.ndarray:
            a = NeuronaEntradaBase.Utilidades.validar(entrada)
            for n in neuronas:
                a = n.forward(a)
            return a

        @staticmethod
        def backward(neuronas: List[Any], entrada: Any, salida: Any) -> np.ndarray:
            a = NeuronaEntradaBase.Utilidades.validar(salida)
            for n in reversed(neuronas):
                if hasattr(n, 'grad_entrada'):
                    a = n.grad_entrada(a)
                elif hasattr(n, 'backward'):
                    a = n.backward(a, None)[0]
                else:
                    break
            return a

        @staticmethod
        def benchmark(neurona: Any, datos: Any) -> Dict[str, Any]:
            x = NeuronaEntradaBase.Utilidades.validar(datos)
            inicio = time.perf_counter()
            salida = neurona.forward(x)
            duracion = time.perf_counter() - inicio
            return {'segundos': duracion, 'forma_salida': tuple(np.shape(salida))}


NeuronaEntradaTanh = NeuronaEntradaBase.Tanh
NeuronaEntradaSigmoid = NeuronaEntradaBase.Sigmoid


def crear_neurona(tipo: str) -> Any:
    tipo = str(tipo).lower()
    if tipo == 'tanh':
        return NeuronaEntradaTanh()
    if tipo == 'sigmoid':
        return NeuronaEntradaSigmoid()
    raise ValueError(f"Tipo de neurona no soportado: {tipo}")


def benchmark_neurona(neurona: Any, datos: Any) -> Dict[str, Any]:
    return NeuronaEntradaBase.Red.benchmark(neurona, datos)


def normalizar_datos(datos: Any) -> np.ndarray:
    return NeuronaEntradaBase.Utilidades.normalizar(datos)


def configurar_precision(precision: str) -> np.dtype:
    return NeuronaEntradaBase.Utilidades.precision(precision)


def fijar_semilla(semilla: int) -> int:
    return NeuronaEntradaBase.Utilidades.semilla(semilla)


def validar_lote(lote: Any) -> np.ndarray:
    return NeuronaEntradaBase.Utilidades.validar(lote)


def forward_en_cascada(neuronas: List[Any], entrada: Any) -> np.ndarray:
    return NeuronaEntradaBase.Red.forward(neuronas, entrada)


def backward_en_cascada(neuronas: List[Any], entrada: Any, salida: Any) -> np.ndarray:
    return NeuronaEntradaBase.Red.backward(neuronas, entrada, salida)