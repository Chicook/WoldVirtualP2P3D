"""Subpaquete SBRTM_IMPORT: base local LucIA autocontenida."""

import importlib.util as _ilu
import os as _os

_base = _os.path.dirname(_os.path.abspath(__file__))


def _cargar(nombre: str, nombres: list):
    """Carga un módulo del subpaquete por ruta y devuelve sus atributos."""
    _spec = _ilu.spec_from_file_location(
        nombre, _os.path.join(_base, nombre + '.py'))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    return {n: getattr(_mod, n) for n in nombres}


try:
    from .sbrtm_import1 import (
        LucIANeuronBase,
        LucIAInitializers,
        LUCIA_CONFIG,
        core_he,
        core_xavier,
        core_lecun,
    )
except ImportError:
    _m1 = _cargar('sbrtm_import1', [
        'LucIANeuronBase', 'LucIAInitializers', 'LUCIA_CONFIG',
        'core_he', 'core_xavier', 'core_lecun'])
    LucIANeuronBase = _m1['LucIANeuronBase']
    LucIAInitializers = _m1['LucIAInitializers']
    LUCIA_CONFIG = _m1['LUCIA_CONFIG']
    core_he = _m1['core_he']
    core_xavier = _m1['core_xavier']
    core_lecun = _m1['core_lecun']

try:
    from .sbrtm_import2 import (
        Neuron,
        he_initialization,
        xavier_initialization,
        lecun_initialization,
        guardar_red,
        resumen_red,
        registrar_tipo,
        listar_tipos,
        norma_global,
        clip_global,
        semilla_global,
        info_paquete,
    )
except ImportError:
    _m2 = _cargar('sbrtm_import2', [
        'Neuron', 'he_initialization', 'xavier_initialization',
        'lecun_initialization', 'guardar_red', 'resumen_red',
        'registrar_tipo', 'listar_tipos', 'norma_global', 'clip_global',
        'semilla_global', 'info_paquete'])
    Neuron = _m2['Neuron']
    he_initialization = _m2['he_initialization']
    xavier_initialization = _m2['xavier_initialization']
    lecun_initialization = _m2['lecun_initialization']
    guardar_red = _m2['guardar_red']
    resumen_red = _m2['resumen_red']
    registrar_tipo = _m2['registrar_tipo']
    listar_tipos = _m2['listar_tipos']
    norma_global = _m2['norma_global']
    clip_global = _m2['clip_global']
    semilla_global = _m2['semilla_global']
    info_paquete = _m2['info_paquete']

# sbrtm_import3 se importa al final para que sus versiones unificadas
# (crear_neurona, benchmark_neurona, normalizar_datos, validar_lote,
#  forward_en_cascada, backward_en_cascada) prevalezcan, igual que en ENRN.
try:
    from .sbrtm_import3 import (
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
    _m3 = _cargar('sbrtm_import3', [
        'NeuronaEntradaBase', 'NeuronaEntradaTanh', 'NeuronaEntradaSigmoid',
        'crear_neurona', 'benchmark_neurona', 'normalizar_datos',
        'configurar_precision', 'fijar_semilla', 'validar_lote',
        'forward_en_cascada', 'backward_en_cascada'])
    NeuronaEntradaBase = _m3['NeuronaEntradaBase']
    NeuronaEntradaTanh = _m3['NeuronaEntradaTanh']
    NeuronaEntradaSigmoid = _m3['NeuronaEntradaSigmoid']
    crear_neurona = _m3['crear_neurona']
    benchmark_neurona = _m3['benchmark_neurona']
    normalizar_datos = _m3['normalizar_datos']
    configurar_precision = _m3['configurar_precision']
    fijar_semilla = _m3['fijar_semilla']
    validar_lote = _m3['validar_lote']
    forward_en_cascada = _m3['forward_en_cascada']
    backward_en_cascada = _m3['backward_en_cascada']

__all__ = [
    'LucIANeuronBase',
    'LucIAInitializers',
    'LUCIA_CONFIG',
    'core_he',
    'core_xavier',
    'core_lecun',
    'Neuron',
    'he_initialization',
    'xavier_initialization',
    'lecun_initialization',
    'guardar_red',
    'resumen_red',
    'registrar_tipo',
    'listar_tipos',
    'norma_global',
    'clip_global',
    'semilla_global',
    'info_paquete',
    'NeuronaEntradaBase',
    'NeuronaEntradaTanh',
    'NeuronaEntradaSigmoid',
    'crear_neurona',
    'benchmark_neurona',
    'normalizar_datos',
    'configurar_precision',
    'fijar_semilla',
    'validar_lote',
    'forward_en_cascada',
    'backward_en_cascada',
]
