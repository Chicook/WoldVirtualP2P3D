"""RFEN1_RN_2.py - Neurona de Refuerzo con Policy Gradient (refactor eficiente)."""
import numpy as np
import math
import time
import logging
from typing import Tuple, Optional, Dict, Any, List

LUCIA_RL_CONFIG = {'precision': 'float32', 'random_seed': 42,
                   'default_learning_rate': 0.001}


class NeuronaRefuerzoBase:
    """Base minimalista local (evita importar .base inexistente)."""

    def __init__(self, input_size: int, output_size: int, nombre: str = "NeuronaRefuerzo"):
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.nombre = str(nombre)
        self.pesos = None
        self.sesgo = None
        self.historial_activaciones: List[np.ndarray] = []
        self.historial_gradientes: List[Any] = []

    def inicializar_pesos(self) -> None:
        raise NotImplementedError

    def forward(self, e: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def resetear_historial(self) -> None:
        self.historial_activaciones = []
        self.historial_gradientes = []


class InicializadoresRL:
    """Inicializadores minimalistas locales."""

    @staticmethod
    def _rng(seed: int = 42) -> np.random.Generator:
        return np.random.default_rng(seed)

    @classmethod
    def he(cls, shape, fan_in=1, seed=42):
        return cls._rng(seed).normal(0.0, math.sqrt(2.0 / max(1, fan_in)), shape).astype(LUCIA_RL_CONFIG['precision'])

    @classmethod
    def xavier(cls, shape, fan_in=1, fan_out=1, seed=42):
        lim = math.sqrt(6.0 / max(1, fan_in + fan_out))
        return cls._rng(seed).uniform(-lim, lim, shape).astype(LUCIA_RL_CONFIG['precision'])

    @classmethod
    def ortogonal(cls, shape, seed=42, ganancia: float = 1.0):
        a = cls._rng(seed).normal(0, 1, shape)
        q, _ = np.linalg.qr(a) if shape[0] >= shape[1] else np.linalg.qr(a.T)
        q = q if shape[0] >= shape[1] else q.T
        return (q[:, :shape[1]] * ganancia).astype(LUCIA_RL_CONFIG['precision'])

    @classmethod
    def espectral(cls, shape, seed=42):
        w = cls._rng(seed).normal(0, 1, shape)
        s = np.linalg.svd(w, compute_uv=False)
        return (w / max(1e-12, s[0])).astype(LUCIA_RL_CONFIG['precision'])


def inicializar_pesos_he(shape, fan_in=1, seed=42):
    return InicializadoresRL.he(shape, fan_in, seed)


def inicializar_pesos_xavier(shape, fan_in=1, fan_out=1, seed=42):
    return InicializadoresRL.xavier(shape, fan_in, fan_out, seed)


def inicializar_pesos_ortogonal(shape, seed=42):
    return InicializadoresRL.ortogonal(shape, seed)


def inicializar_pesos_espectral(shape, seed=42):
    return InicializadoresRL.espectral(shape, seed)


logger = logging.getLogger('RFENRN1.RFEN1_RN_2')
_DTYPE = {'float32': np.float32, 'float64': np.float64}


def _dt() -> np.dtype:
    return np.dtype(_DTYPE.get(LUCIA_RL_CONFIG.get('precision', 'float32'), np.float32))


# ---------------------------------------------------------------------------
# Importación desde RF_EN_SBRTM_RFEN1_RN_2_1.py  (sustituye líneas 89-332)
# ---------------------------------------------------------------------------
import importlib.util as _ilu_rn2
import os as _os_rn2

_SBRTM_PATH = _os_rn2.path.join(
    _os_rn2.path.dirname(_os_rn2.path.abspath(__file__)),
    "RF_EN_SBRTM_RFEN1_RN_2",
    "RF_EN_SBRTM_RFEN1_RN_2_1.py",
)
_sbrtm_spec = _ilu_rn2.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_2_1", _SBRTM_PATH)
_sbrtm_mod  = _ilu_rn2.module_from_spec(_sbrtm_spec)
_sbrtm_spec.loader.exec_module(_sbrtm_mod)

_Ring                          = _sbrtm_mod._Ring
NeuronaRefuerzoPolicyGradient  = _sbrtm_mod.NeuronaRefuerzoPolicyGradient
NeuronaTest                    = _sbrtm_mod.NeuronaTest
NeuronaDeComunicacionPolicyGradient = _sbrtm_mod.NeuronaDeComunicacionPolicyGradient

# ---------------------------------------------------------------------------
# Métodos adicionales añadidos a NeuronaRefuerzoPolicyGradient (importada)
# ---------------------------------------------------------------------------
import json as _json_rn2

def _reinicializar_con_parametros(self, learning_rate=None, gamma=None, entropy_coef=None):
    if learning_rate is not None: self.learning_rate = float(learning_rate)
    if gamma         is not None: self.gamma         = float(gamma)
    if entropy_coef  is not None: self.entropy_coef  = float(entropy_coef)
    self.inicializar_pesos(); self.resetear_historial()
    self.historial_politicas.clear(); self.historial_gradientes.clear()
    self.historial_entropias.clear(); self.historial_recompensas_descontadas.clear()
    self.estadisticas_pg['actualizaciones_politica'] = 0; self.pasos = 0
    logger.info(f"Policy Gradient reinicializada: lr={self.learning_rate}, gamma={self.gamma}")

def _a_dict(self):
    return {'input_size': self.input_size, 'output_size': self.output_size, 'nombre': self.nombre,
            'learning_rate': self.learning_rate, 'gamma': self.gamma, 'entropy_coef': self.entropy_coef,
            'pesos': self.pesos.tolist() if self.pesos is not None else None,
            'sesgo': self.sesgo.tolist() if self.sesgo is not None else None}

def _guardar(self, ruta):
    with open(ruta, 'w', encoding='utf-8') as f: _json_rn2.dump(self.a_dict(), f)

@classmethod
def _cargar(cls, ruta):
    with open(ruta, 'r', encoding='utf-8') as f: d = _json_rn2.load(f)
    o = cls(d['input_size'], d['output_size'], d.get('nombre', 'NeuronaRefuerzoPolicyGradient'))
    if d.get('pesos') is not None:
        o.pesos = np.asarray(d['pesos'], dtype=_dt())
        o.sesgo = np.asarray(d['sesgo'], dtype=_dt())
    return o

def _str_pg(self):
    return (f"NeuronaRefuerzoPolicyGradient(entrada={self.input_size}, salida={self.output_size}, "
            f"lr={self.learning_rate}, gamma={self.gamma}, entropy_coef={self.entropy_coef})")

NeuronaRefuerzoPolicyGradient.reinicializar_con_parametros = _reinicializar_con_parametros
NeuronaRefuerzoPolicyGradient.a_dict   = _a_dict
NeuronaRefuerzoPolicyGradient.guardar  = _guardar
NeuronaRefuerzoPolicyGradient.cargar   = _cargar
NeuronaRefuerzoPolicyGradient.__str__  = _str_pg
NeuronaRefuerzoPolicyGradient.__repr__ = _str_pg


def crear_neurona_policy_gradient(input_size: int, output_size: int,
                                  configuracion: Dict[str, Any] = None) -> NeuronaRefuerzoPolicyGradient:
    configuracion = configuracion or {}
    return NeuronaRefuerzoPolicyGradient(
        input_size=input_size, output_size=output_size,
        nombre=configuracion.get('nombre', 'NeuronaRefuerzoPolicyGradient'),
        learning_rate=configuracion.get('learning_rate', 0.001),
        gamma=configuracion.get('gamma', 0.99),
        usar_ortogonal=configuracion.get('usar_ortogonal', True),
        entropy_coef=configuracion.get('entropy_coef', 0.01))


RFEN2_CONFIG = {'inicializacion_preferida': 'ortogonal', 'learning_rate_default': 0.001,
                'gamma_default': 0.99, 'entropy_coef_default': 0.01, 'umbral_convergencia': 0.7,
                'umbral_estabilidad': 0.7, 'umbral_exploracion_min': 0.1, 'umbral_exploracion_max': 0.9}


def analizar_convergencia_pg(neurona: NeuronaRefuerzoPolicyGradient) -> Dict[str, Any]:
    return {'convergencia': neurona.estadisticas_pg['convergencia_politica'],
            'estabilidad': neurona.calcular_estabilidad_politica(),
            'exploracion': neurona.calcular_exploracion_efectiva(),
            'actualizaciones': neurona.estadisticas_pg['actualizaciones_politica'],
            'norma_grad': neurona.estadisticas_pg['gradiente_politica_norma'],
            'estadisticas': neurona.obtener_estadisticas_pg(),
            'estable': neurona.verificar_estabilidad()}


def comparar_inicializaciones_pg(input_size: int, output_size: int, pasos: int = 200) -> Dict[str, Any]:
    rng = np.random.default_rng(0)
    out = {}
    for k, m in (('ortogonal', 'ortogonal'), ('xavier', 'xavier')):
        n = NeuronaRefuerzoPolicyGradient(input_size, output_size)
        n.inicializar_pesos(m)
        X = rng.normal(0, 1, (pasos, input_size)).astype(np.float32)
        A = rng.integers(0, output_size, pasos).tolist()
        G = rng.random(pasos).tolist()
        gw, gb = n.calcular_gradiente_politica([x for x in X], A, G)
        out[k] = {'norma_grad': float(np.linalg.norm(gw)), 'entropia': float(np.mean(n.historial_entropias.tail(10)))}
    return out
logger.info("RFEN1_RN_2.py cargado correctamente - Neurona de Refuerzo Policy Gradient")