import logging
import time
import json
import os
from typing import Tuple, Optional, List, Dict, Any, Callable
import numpy as np
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
import os
import json
import numpy as np
from typing import List, Callable, Dict, Any
import logging
from __init___p2 import *
from __init___p2 import *
from __init___p2 import *


class LucIANeuronBase:
    """Base local LucIA (sustituye a lucIA.CORE.base sin import externo)."""

    def __init__(self, input_size: int = 0, output_size: int = 0,
                 nombre: str = "LucIANeurona") -> None:
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.pesos: Optional[np.ndarray] = None
        self.sesgo: Optional[np.ndarray] = None
        self.historial_activaciones: List[np.ndarray] = []
        self.historial_gradientes: List[Dict[str, Any]] = []
        self.llm_connector = None

    def inicializar_pesos(self) -> None:
        raise NotImplementedError

    def forward(self, entrada: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def backward(self, g: np.ndarray, e: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError


class LucIAInitializers:
    """Inicializadores locales (sustituyen a lucIA.CORE.initializers)."""

    @staticmethod
    def he(shape: Tuple[int, ...], fan_in: int, rng=None) -> np.ndarray:
        r = rng or np.random.default_rng(LUCIA_CONFIG.get('random_seed', 42))
        return (r.normal(0.0, float(np.sqrt(2.0 / max(1, fan_in))), shape)).astype(_dtype())

    @staticmethod
    def xavier(shape: Tuple[int, ...], fan_in: int, fan_out: int, rng=None) -> np.ndarray:
        r = rng or np.random.default_rng(LUCIA_CONFIG.get('random_seed', 42))
        lim = float(np.sqrt(6.0 / max(1, fan_in + fan_out)))
        return (r.uniform(-lim, lim, shape)).astype(_dtype())

    @staticmethod
    def lecun(shape: Tuple[int, ...], fan_in: int, rng=None) -> np.ndarray:
        r = rng or np.random.default_rng(LUCIA_CONFIG.get('random_seed', 42))
        return (r.normal(0.0, float(np.sqrt(1.0 / max(1, fan_in))), shape)).astype(_dtype())


def core_he(*a, **k):
    return LucIAInitializers.he(a[0] if a else (1, 1), k.get('fan_in', 1))


LUCIA_CONFIG = {
    'precision': 'float32',
    'random_seed': 42,
    'default_learning_rate': 0.001,
    'weight_decay': 1e-4,
    'dropout_rate': 0.1,
    'batch_norm_momentum': 0.9,
    'batch_norm_epsilon': 1e-5
}


_DTYPE = np.float32


def _dtype():
    return _DTYPE


def _rng(seed: Optional[int] = None) -> np.random.Generator:
    return np.random.default_rng(seed or LUCIA_CONFIG.get('random_seed', 42))


def _uniform(shape: Tuple[int, ...], fan_in: int, fan_out: int) -> np.ndarray:
    lim = np.sqrt(6.0 / max(1, fan_in + fan_out))
    return _rng().uniform(-lim, lim, shape).astype(_dtype())


def _normal(shape: Tuple[int, ...], fan_in: int) -> np.ndarray:
    return _rng().normal(0.0, np.sqrt(1.0 / max(1, fan_in)), shape).astype(_dtype())


def core_he(shape: Tuple[int, ...], fan_in: int, rng: Optional[np.random.Generator] = None) -> np.ndarray:
    return _normal(shape, fan_in)


def core_xavier(shape: Tuple[int, ...], fan_in: int, fan_out: int, rng: Optional[np.random.Generator] = None) -> np.ndarray:
    return _uniform(shape, fan_in, fan_out)


def core_lecun(shape: Tuple[int, ...], fan_in: int, rng: Optional[np.random.Generator] = None) -> np.ndarray:
    return _normal(shape, fan_in)


class Neuron:
    def __init__(self, input_size: int, output_size: int, rng: Optional[np.random.Generator] = None):
        self.input_size = input_size
        self.output_size = output_size
        self.pesos = None
        self.sesgo = None
        self.historial_activaciones: List[np.ndarray] = []
        self.historial_gradientes: List[np.ndarray] = []
        self.llm_connector = None
        self._system_ref = None
        self.rng = rng or _rng()

    def initialize_weights(self, initializer: str = 'xavier', fan_in: Optional[int] = None):
        if initializer == 'xavier':
            self.pesos = core_xavier((self.output_size, self.input_size), fan_in or self.input_size, rng=self.rng)
        elif initializer == 'he':
            self.pesos = core_he((self.output_size, self.input_size), fan_in or self.input_size, rng=self.rng)
        elif initializer == 'lecun':
            self.pesos = core_lecun((self.output_size, self.input_size), fan_in or self.input_size, rng=self.rng)
        self.sesgo = np.zeros((self.output_size,), dtype=_dtype())

    def recibir_respuesta_llm(self, respuesta: str) -> None:
        logger.info(f"[Neurona {self.nombre}] Respuesta LLM recibida. Procesando...")
        self.ultima_respuesta_llm = respuesta
        prompt_propio = (
            f"Soy la neurona de entrada {self.nombre}. He recibido este analisis global: {respuesta}. "
            f"Basandote en tu fortaleza especifica (logica, codigo o eficiencia), "
            f"genera una directiva tecnica ultra-especifica para el resto de la red neuronal."
        )


def he_initialization(fan_in: int, fan_out: int) -> float:
    """Legacy wrapper for CORE He initialization."""
    try:
        return float(core_he((1, 1), fan_in=fan_in).item())
    except Exception:
        return float(np.sqrt(2.0 / max(1, fan_in)))


def xavier_initialization(fan_in: int, fan_out: int) -> float:
    """Legacy wrapper for CORE Xavier initialization."""
    try:
        return float(core_xavier((1, 1), fan_in=fan_in, fan_out=fan_out).item())
    except Exception:
        return float(np.sqrt(1.0 / max(1, (fan_in + fan_out) / 2.0)))


def lecun_initialization(fan_in: int, fan_out: int) -> float:
    """Legacy wrapper for CORE LeCun initialization."""
    try:
        return float(core_lecun((1, 1), fan_in=fan_in).item())
    except Exception:
        return float(np.sqrt(1.0 / max(1, fan_in)))


def normalizar_datos(datos: np.ndarray, metodo: str = 'z_score') -> np.ndarray:
    """Normaliza datos con z_score/min_max/robusta de forma vectorizada."""
    x = np.asarray(datos, dtype=_dtype())
    if metodo == 'z_score':
        return ((x - np.mean(x)) / (np.std(x) + 1e-8)).astype(_dtype())
    elif metodo == 'min_max':
        return ((x - np.min(x)) / (np.max(x) - np.min(x) + 1e-8)).astype(_dtype())
    elif metodo == 'robusta':
        med = np.median(x)
        iqr = float(np.percentile(x, 75) - np.percentile(x, 25)) + 1e-8
        return ((x - med) / iqr).astype(_dtype())
    return x


def crear_neurona(tipo: str, input_size: int, output_size: int, **kw) -> "NeuronaEntradaBase":
    mapa = {'basica': 'NeuronaEntradaBasica', 'xavier': 'NeuronaEntradaXavier',
            'lecun': 'NeuronaEntradaLeCun', 'normalizada': 'NeuronaEntradaNormalizada',
            'regularizada': 'NeuronaEntradaRegularizada', 'sigmoid': 'NeuronaEntradaSigmoid'}
    clases = {
        'NeuronaEntradaBasica': 'NeuronaEntradaBasica',
        'NeuronaEntradaXavier': 'NeuronaEntradaXavier',
        'NeuronaEntradaLeCun': 'NeuronaEntradaLeCun',
        'NeuronaEntradaNormalizada': 'NeuronaEntradaNormalizada',
        'NeuronaEntradaRegularizada': 'NeuronaEntradaRegularizada',
        'NeuronaEntradaSigmoid': 'NeuronaEntradaSigmoid'
    }
    nombre = mapa.get(str(tipo).lower(), 'NeuronaEntradaBasica')
    mod = __import__(f"{__name__}.{clases[nombre]}", fromlist=[nombre])
    return getattr(mod, nombre)(input_size, output_size, **kw)


def benchmark_neurona(neurona: "NeuronaEntradaBase", dim_in: int = 32, dim_out: int = 16,
                      iters: int = 50) -> Dict[str, float]:
    x = np.random.default_rng(0).normal(0, 1, (16, dim_in)).astype(_dtype())


_REGISTRO = {}


def _dtype() -> np.dtype:
    return np.float32


def _as_array(x: np.ndarray) -> np.ndarray:
    return np.asarray(x, dtype=_dtype())


def _validate_lote(x: np.ndarray, dim: int) -> np.ndarray:
    a = _as_array(x)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if a.shape[1] != dim:
        raise ValueError(f"lote dim {a.shape[1]} != {dim}")
    return np.ascontiguousarray(a, dtype=_dtype())


def forward_en_cascada(neuronas: List["NeuronaEntradaBase"], x: np.ndarray) -> np.ndarray:
    a = _validate_lote(x, neuronas[0].input_dim)
    for n in neuronas:
        a = n.forward(a)
    return a


def backward_en_cascada(neuronas: List["NeuronaEntradaBase"], g: np.ndarray) -> np.ndarray:
    a = _validate_lote(g, neuronas[-1].output_dim)
    for n in reversed(neuronas):
        if not hasattr(n, 'grad_entrada'):
            break
        a = n.grad_entrada(a)
    return a


def guardar_red(neuronas: List["NeuronaEntradaBase"], ruta: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump([n.a_dict() if hasattr(n, 'a_dict') else {} for n in neuronas], f)


def resumen_red(neuronas: List["NeuronaEntradaBase"]) -> Dict[str, Any]:
    total_params = 0
    for n in neuronas:
        if getattr(n, 'pesos', None) is not None:
            total_params += int(np.size(n.pesos)) + int(np.size(n.sesgo))
    return {'n_neuronas': len(neuronas), 'total_params': total_params,
            'tipos': [type(n).__name__ for n in neuronas]}


def registrar_tipo(clave: str, clase: Callable[..., "NeuronaEntradaBase"]) -> None:
    _REGISTRO[str(clave).lower()] = clase.__name__


def listar_tipos() -> List[str]:
    return sorted(_REGISTRO.keys()) or ['basica', 'xavier', 'lecun', 'normalizada',
                                        'regularizada', 'dropout', 'batchnorm',
                                        'relu', 'tanh', 'sigmoid']


def crear_neurona(tipo: str, input_size: int, output_size: int, **kw) -> "NeuronaEntradaBase":
    tipo = str(tipo).lower()
    if tipo not in _REGISTRO:
        raise ValueError(f"Tipo de neurona desconocido: {tipo}")
    mod = __import__(f"{__name__}.{_REGISTRO[tipo]}", fromlist=[_REGISTRO[tipo]])
    return getattr(mod, _REGISTRO[tipo])(input_size, output_size, **kw)


def benchmark_neurona(neurona: "NeuronaEntradaBase"):
    pass


def norma_global(neuronas: List["NeuronaEntradaBase"]) -> float:
    acc = 0.0
    for n in neuronas:
        if getattr(n, 'pesos', None) is not None:
            acc += float(np.sum(n.pesos.astype(np.float64) ** 2))
    return float(np.sqrt(acc))


def clip_global(neuronas: List["NeuronaEntradaBase"], max_norma: float = 5.0) -> float:
    ng = norma_global(neuronas)
    if ng > max_norma and ng > 0:
        f = max_norma / ng
        for n in neuronas:
            if getattr(n, 'pesos', None) is not None:
                n.pesos = (n.pesos.astype(np.float64) * f).astype(_dtype())
    return ng


def validar_lote(x: np.ndarray, dim: int) -> np.ndarray:
    return _validate_l


def semilla_global() -> int:
    return int(LUCIA_CONFIG.get('random_seed', 42))


def info_paquete() -> Dict[str, Any]:
    return {'nombre': 'ENRN', 'version': '1.1.0', 'precision': LUCIA_CONFIG.get('precision'),
            'tipos': listar_tipos(), 'n_tipos': len(listar_tipos())}


__version__ = '1.1.0'


__autor__ = 'LucIA Development Team'


def salud() -> Dict[str, Any]:
    try:
        n = crear_neurona('basica', 4, 2)
        a = n.forward(np.zeros((1, 4), dtype=_dtype()))
        ok = bool(np.all(np.isfinite(a)))
    except Exception as e:
        return {'ok': False, 'error': f"{type(e).__name__}: {e}"}
    return {'ok': ok, 'version': __version__, 'tipos': len(listar_tipos())}


def _cargar_submodulos() -> None:
    """Carga EN1..EN10 tanto como paquete como script directo."""
    pares = [('EN1_RN', 'NeuronaEntradaBasica'), ('EN2_RN', 'NeuronaEntradaXavier'), ('EN3_RN', 'NeuronaEntradaLeCun'), ('EN4_RN', 'NeuronaEntradaNormalizada'),
             ('EN5_RN', 'NeuronaEntradaRegularizada'), ('EN6_RN', 'NeuronaEntradaDropout'), ('EN7_RN', 'NeuronaEntradaBatchNorm'),
             ('EN8_RN', 'NeuronaEntradaReLU'), ('EN9_RN', 'NeuronaEntradaTanh'), ('EN10_RN', 'NeuronaEntradaSigmoid')]
    try:
        for _mod, _cls in pares:
            globals()[_cls] = getattr(__import__(f"{__name__}.{_mod}", fromlist=[_cls]), _cls)
        return
    except ImportError:
        pass
    import importlib.util as _ilu
    base = os.path.dirname(os.path.abspath(__file__))
    for _mod, _cls in pares:
        _spec = _ilu.spec_from_file_location(_mod, os.path.join(base, _mod + '.py'))
        _m = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_m)
        globals()[_cls] = getattr(_m, _cls)


def registrar_tipo(clave: str, clase: Callable[..., "NeuronaEntradaBase"]) -> None:
    _REGISTRO[str(clave).lower()] = clase.__name__


def listar_tipos() -> List[str]:
    return sorted(_REGISTRO.keys()) or ['basica', 'xavier', 'lecun', 'normalizada',
                                        'regularizada', 'dropout', 'batchnorm',
                                        'relu', 'tanh', 'sigmoid']


_cargar_submodulos()


__all__ = [
    'NeuronaEntradaBase',
    'NeuronaEntradaBasica',
    'NeuronaEntradaXavier',
    'NeuronaEntradaLeCun',
    'NeuronaEntradaNormalizada',
    'NeuronaEntradaRegularizada',
    'NeuronaEntradaDropout',
    'NeuronaEntradaBatchNorm',
    'NeuronaEntradaReLU',
    'NeuronaEntradaTanh',
    'NeuronaEntradaSigmoid',
    'LUCIA_CONFIG', 'crear_neurona', 'benchmark_neurona',
    'normalizar_datos', 'configurar_precision', 'fijar_semilla',
    'validar_lote', 'forward_en_cascada', 'backward_en_cascada',
    'guardar_red', 'resumen_red',
    'registrar_tipo', 'listar_tipos', 'norma_global', 'clip_global',
    'decaimiento_lr_lineal', 'aplicar_lr', 'semilla_global', 'info_paquete',
    'salud', '__version__',
]


logger = logging.getLogger('ENRN')


if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)


MAX_LINE_LENGTH = 100


def setup_logger():
    """Configura el logger."""
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_init():
    """Registra el inicio del paquete."""
    logger.info("Paquete ENRN inicializado correctamente para LucIA")


class NeuronaEntradaTanh:
    pass


class NeuronaEntradaSigmoid:
    pass


def crear_neurona(tipo):
    """Crea una neurona del tipo especificado."""
    if tipo == 'tanh':
        return NeuronaEntradaTanh()
    elif tipo == 'sigmoid':
        return NeuronaEntradaSigmoid()
    else:
        raise ValueError(f"Tipo de neurona no soportado: {tipo}")


def crear_neurona(tipo: str) -> "NeuronaEntradaBase":
    """Crea una neurona del tipo especificado."""
    tipo = str(tipo).lower()
    if tipo not in _REGISTRO:
        raise ValueError(f"Tipo de neurona desconocido: {tipo}")
    mod = __import__(f"{__name__}.{_REGISTRO[tipo]}", fromlist=[_REGISTRO[tipo]])
    return getattr(mod, _REGISTRO[tipo])()


def benchmark_neurona(neurona: "NeuronaEntradaBase", datos):
    """Realiza un benchmark de la neurona con los datos proporcionados."""
    pass


def normalizar_datos(datos):
    """Normaliza los datos de entrada."""
    pass

# --- Partes/subsistemas extraídos automáticamente ---
from __init___p2 import *  # noqa: F401,F403
