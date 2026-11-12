import logging
import time
import json
import os
from typing import Tuple, Optional, List, Dict, Any, Callable
import numpy as np

try:
    from .SBRTM_IMPORT.sbrtm_import1 import (
        LucIANeuronBase,
        LucIAInitializers,
        LUCIA_CONFIG,
        core_he,
        core_xavier,
        core_lecun,
        _dtype,
        _rng,
    )
except ImportError:
    import importlib.util as _ilu
    _base = os.path.dirname(os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location('sbrtm_import1', os.path.join(_base, 'SBRTM_IMPORT', 'sbrtm_import1.py'))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    LucIANeuronBase = _mod.LucIANeuronBase
    LucIAInitializers = _mod.LucIAInitializers
    LUCIA_CONFIG = _mod.LUCIA_CONFIG
    core_he = _mod.core_he
    core_xavier = _mod.core_xavier
    core_lecun = _mod.core_lecun
    _dtype = _mod._dtype
    _rng = _mod._rng

try:
    from .SBRTM_IMPORT.sbrtm_import2 import (
        Neuron,
        he_initialization,
        xavier_initialization,
        lecun_initialization,
        normalizar_datos,
        crear_neurona,
        benchmark_neurona,
        forward_en_cascada,
        backward_en_cascada,
        guardar_red,
        resumen_red,
        registrar_tipo,
        listar_tipos,
        norma_global,
        clip_global,
        validar_lote,
        semilla_global,
        info_paquete,
        __version__,
        __autor__,
    )
except ImportError:
    import importlib.util as _ilu2
    _base2 = os.path.dirname(os.path.abspath(__file__))
    _spec2 = _ilu2.spec_from_file_location('sbrtm_import2', os.path.join(_base2, 'SBRTM_IMPORT', 'sbrtm_import2.py'))
    _mod2 = _ilu2.module_from_spec(_spec2)
    _spec2.loader.exec_module(_mod2)
    Neuron = _mod2.Neuron
    he_initialization = _mod2.he_initialization
    xavier_initialization = _mod2.xavier_initialization
    lecun_initialization = _mod2.lecun_initialization
    normalizar_datos = _mod2.normalizar_datos
    crear_neurona = _mod2.crear_neurona
    benchmark_neurona = _mod2.benchmark_neurona
    forward_en_cascada = _mod2.forward_en_cascada
    backward_en_cascada = _mod2.backward_en_cascada
    guardar_red = _mod2.guardar_red
    resumen_red = _mod2.resumen_red
    registrar_tipo = _mod2.registrar_tipo
    listar_tipos = _mod2.listar_tipos
    norma_global = _mod2.norma_global
    clip_global = _mod2.clip_global
    validar_lote = _mod2.validar_lote
    semilla_global = _mod2.semilla_global
    info_paquete = _mod2.info_paquete
    __version__ = _mod2.__version__
    __autor__ = _mod2.__autor__

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
        ruta = os.path.join(base, _mod + '.py')
        if not os.path.isfile(ruta):
            continue
        _spec = _ilu.spec_from_file_location(_mod, ruta)
        _m = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_m)
        globals()[_cls] = getattr(_m, _cls)

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
import logging

logger = logging.getLogger('ENRN')
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.info("Paquete ENRN inicializado correctamente para LucIA")

# Constantes
MAX_LINE_LENGTH = 100

# Funciones auxiliares
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

# Clases y funciones principales
try:
    from .SBRTM_IMPORT.sbrtm_import3 import (
        NeuronaEntradaBase,
        NeuronaEntradaTanh,
        NeuronaEntradaSigmoid,
        crear_neurona,
        benchmark_neurona,
        normalizar_datos,
        configurar_precision,
        fijar_semilla,
        validar_lote,
        forward_en_cascada,
        backward_en_cascada,
    )
except ImportError:
    import importlib.util as _ilu3
    _base3 = os.path.dirname(os.path.abspath(__file__))
    _spec3 = _ilu3.spec_from_file_location('sbrtm_import3', os.path.join(_base3, 'SBRTM_IMPORT', 'sbrtm_import3.py'))
    _mod3 = _ilu3.module_from_spec(_spec3)
    _spec3.loader.exec_module(_mod3)
    NeuronaEntradaBase = _mod3.NeuronaEntradaBase
    NeuronaEntradaTanh = _mod3.NeuronaEntradaTanh
    NeuronaEntradaSigmoid = _mod3.NeuronaEntradaSigmoid
    crear_neurona = _mod3.crear_neurona
    benchmark_neurona = _mod3.benchmark_neurona
    normalizar_datos = _mod3.normalizar_datos
    configurar_precision = _mod3.configurar_precision
    fijar_semilla = _mod3.fijar_semilla
    validar_lote = _mod3.validar_lote
    forward_en_cascada = _mod3.forward_en_cascada
    backward_en_cascada = _mod3.backward_en_cascada

def guardar_red(red, ruta):
    """Guarda la red neuronal en la ruta especificada."""
    pass

def resumen_red(red):
    """Genera un resumen de la red neuronal."""
    pass

def registrar_tipo(tipo, neurona):
    """Registra el tipo de neurona."""
    pass

def listar_tipos():
    """Lista los tipos de neuronas registradas."""
    pass

def norma_global(tensor):
    """Calcula la norma global del tensor."""
    pass

def clip_global(tensor, min_val, max_val):
    """Ajusta el valor global del tensor."""
    pass

def decaimiento_lr_lineal(lr, it, max_it):
    """Calcula el decaimiento lineal de la tasa de aprendizaje."""
    pass

def aplicar_lr(optimizer, lr):
    """Aplica la tasa de aprendizaje al optimizador."""
    pass

def semilla_global(semilla):
    """Fija la semilla global para la generación de números aleatorios."""
    pass

def info_paquete():
    """Muestra información sobre el paquete."""
    pass

def salud():
    """Muestra la salud del sistema."""
    pass

__version__ = '1.1.0'