"""RFEN1_RN_3.py - Neurona Actor-Critic (refactor eficiente)."""
import numpy as np
import math
import time
import logging
from typing import Tuple, Optional, Dict, Any, List

try:
    from ._rfen_base import (
        LUCIA_RL_CONFIG,
        _dt,
        NeuronaRefuerzoBase,
        InicializadoresRL,
        inicializar_pesos_ortogonal,
        inicializar_pesos_espectral,
        inicializar_pesos_xavier,
        _Ring,
    )
except ImportError:
    import importlib.util as _ilu_base
    import os as _os_base

    _base_path = _os_base.path.join(
        _os_base.path.dirname(_os_base.path.abspath(__file__)),
        "_rfen_base.py",
    )
    _spec_base = _ilu_base.spec_from_file_location("RF_EN_rfen_base", _base_path)
    if _spec_base and _spec_base.loader:
        _mod_base = _ilu_base.module_from_spec(_spec_base)
        _spec_base.loader.exec_module(_mod_base)
        LUCIA_RL_CONFIG = _mod_base.LUCIA_RL_CONFIG
        _dt = _mod_base._dt
        NeuronaRefuerzoBase = _mod_base.NeuronaRefuerzoBase
        InicializadoresRL = _mod_base.InicializadoresRL
        inicializar_pesos_ortogonal = _mod_base.inicializar_pesos_ortogonal
        inicializar_pesos_espectral = _mod_base.inicializar_pesos_espectral
        inicializar_pesos_xavier = _mod_base.inicializar_pesos_xavier
        _Ring = _mod_base._Ring
    else:
        raise ImportError(f"No se pudo cargar _rfen_base desde {_base_path}")

try:
    from .RF_EN_SBRTM_RFEN1_RN_3.RF_EN_SBRTM_RFEN1_RN_3_1 import (
        GestorGradientesAC,
        NeuronaGestionGradientesAC as _GestorDelegado,
    )
    from .RF_EN_SBRTM_RFEN1_RN_3.RF_EN_SBRTM_RFEN1_RN_3_2 import (
        requiere_pesos_inicializados,
        tiempo_ejecucion,
        NeuronaIniciacionDePesos,
        NeuronaActorCriticOptimizada,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _dir_rn3 = _os.path.join(
        _os.path.dirname(_os.path.abspath(__file__)),
        "RF_EN_SBRTM_RFEN1_RN_3",
    )
    _sbrtm3_1_path = _os.path.join(_dir_rn3, "RF_EN_SBRTM_RFEN1_RN_3_1.py")
    _spec3_1 = _ilu.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_3_1", _sbrtm3_1_path)
    _mod3_1 = _ilu.module_from_spec(_spec3_1)
    _spec3_1.loader.exec_module(_mod3_1)
    GestorGradientesAC = _mod3_1.GestorGradientesAC
    _GestorDelegado = _mod3_1.NeuronaGestionGradientesAC

    _sbrtm3_2_path = _os.path.join(_dir_rn3, "RF_EN_SBRTM_RFEN1_RN_3_2.py")
    _spec3_2 = _ilu.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_3_2", _sbrtm3_2_path)
    _mod3_2 = _ilu.module_from_spec(_spec3_2)
    _spec3_2.loader.exec_module(_mod3_2)
    requiere_pesos_inicializados = _mod3_2.requiere_pesos_inicializados
    tiempo_ejecucion = _mod3_2.tiempo_ejecucion
    NeuronaIniciacionDePesos = _mod3_2.NeuronaIniciacionDePesos
    NeuronaActorCriticOptimizada = _mod3_2.NeuronaActorCriticOptimizada

logger = logging.getLogger('RFENRN1.RFEN1_RN_3')


class NeuronaRefuerzoActorCritic(NeuronaRefuerzoBase):
    """Actor-Critic eficiente: GAE vectorizado, espectral por potencia, RNG propio."""

    def __init__(self, input_size: int, output_size: int,
                 nombre: str = "NeuronaRefuerzoActorCritic",
                 learning_rate_actor: float = 0.001,
                 learning_rate_critic: float = 0.002,
                 gamma: float = 0.99,
                 lambda_gae: float = 0.95,
                 usar_espectral: bool = True,
                 meta_learning: bool = True,
                 grad_clip: float = 5.0,
                 semilla: int = 42,
                 capacidad_historial: int = 512):
        super().__init__(input_size, output_size, nombre)
        self.learning_rate_actor = float(learning_rate_actor)
        self.learning_rate_critic = float(learning_rate_critic)
        self.gamma = float(gamma)
        self.lambda_gae = float(lambda_gae)
        self.usar_espectral = bool(usar_espectral)
        self.meta_learning = bool(meta_learning)
        self.grad_clip = float(grad_clip)
        self.rng = np.random.default_rng(semilla)
        self.pesos_actor = None
        self.sesgo_actor = None
        self.pesos_critic = None
        self.sesgo_critic = None
        self.sigma_actor = 1.0
        self.sigma_critic = 1.0
        self.iniciador = NeuronaIniciacionDePesos(seed=semilla)
        self.pasos = 0
        self.tiempo_fwd = 0.0
        self.tiempo_upd = 0.0
        self.estadisticas_ac = {
            'convergencia_actor': 0.0, 'convergencia_critic': 0.0,
            'estabilidad_actor': 0.0, 'estabilidad_critic': 0.0,
            'advantage_media': 0.0, 'advantage_std': 0.0,
            'valor_error_medio': 0.0, 'policy_loss_medio': 0.0,
            'meta_adaptaciones': 0, 'espectral_updates': 0}
        self.historial_actor_loss = _Ring(capacidad_historial)
        self.historial_critic_loss = _Ring(capacidad_historial)
        self.historial_advantages = _Ring(capacidad_historial * 4)
        self.historial_valores = _Ring(capacidad_historial)
        self.historial_politicas = _Ring(capacidad_historial)
        logger.info(f"NeuronaRefuerzoActorCritic creada: {self}")

    # ---------------------------------------------------------------------------
    # Inicialización y ejecución delegadas en NeuronaIniciacionDePesos y
    # NeuronaActorCriticOptimizada (sustituye líneas 109-248 integrando 3_1 y 3_2)
    # ---------------------------------------------------------------------------
    def inicializar_pesos(self, modo: Optional[str] = None) -> None:
        NeuronaActorCriticOptimizada.inicializar_pesos(self, modo)

    @staticmethod
    def _sigma(w: np.ndarray, iters: int = 4) -> float:
        return NeuronaIniciacionDePesos(seed=0).calcular_sigma(w, iters)

    def _norma_espectral(self, w: np.ndarray, sigma: float) -> np.ndarray:
        if not self.usar_espectral:
            return w
        return NeuronaIniciacionDePesos().aplicar_norma_espectral(w, sigma)

    def _prep(self, estado: np.ndarray) -> np.ndarray:
        return NeuronaActorCriticOptimizada._prep(self, estado)

    @staticmethod
    def _softmax(z: np.ndarray) -> np.ndarray:
        return NeuronaActorCriticOptimizada._softmax(z)

    @requiere_pesos_inicializados
    def forward_actor(self, estado: np.ndarray) -> np.ndarray:
        return NeuronaActorCriticOptimizada.forward_actor(self, estado)

    @requiere_pesos_inicializados
    def forward_critic(self, estado: np.ndarray) -> np.ndarray:
        return NeuronaActorCriticOptimizada.forward_critic(self, estado)

    @tiempo_ejecucion("tiempo_fwd")
    def forward(self, estado: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        return NeuronaActorCriticOptimizada.forward(self, estado)

    def seleccionar_accion(self, estado: np.ndarray) -> Tuple[int, float, float]:
        return NeuronaActorCriticOptimizada.seleccionar_accion(self, estado)

    def calcular_gae_advantages(self, recompensas: List[float], valores: List[float],
                                siguiente_valor: float = 0.0) -> np.ndarray:
        return NeuronaActorCriticOptimizada.calcular_gae_advantages(self, recompensas, valores, siguiente_valor)

    def calcular_gradientes_ac(self, estados: List[np.ndarray], acciones: List[int],
                               advantages: List[float], valores_objetivo: List[float]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        return NeuronaActorCriticOptimizada.calcular_gradientes_ac(self, estados, acciones, advantages, valores_objetivo)

    @tiempo_ejecucion("tiempo_upd")
    def actualizar_pesos(self, grad_actor_pesos: np.ndarray, grad_actor_sesgo: np.ndarray,
                         grad_critic_pesos: np.ndarray, grad_critic_sesgo: np.ndarray) -> Dict[str, float]:
        return NeuronaActorCriticOptimizada.actualizar_pesos(self, grad_actor_pesos, grad_actor_sesgo, grad_critic_pesos, grad_critic_sesgo)

    def entrenar_paso(self, estados: List[np.ndarray], acciones: List[int],
                      recompensas: List[float], valores: List[float], siguiente_valor: float = 0.0) -> Dict[str, float]:
        return NeuronaActorCriticOptimizada.entrenar_paso(self, estados, acciones, recompensas, valores, siguiente_valor)

    def _adaptar_meta_learning(self) -> None:
        NeuronaActorCriticOptimizada._adaptar_meta_learning(self)

    def _calcular_convergencia_ac(self) -> None:
        NeuronaActorCriticOptimizada._calcular_convergencia_ac(self)

    def calcular_estabilidad_ac(self) -> Tuple[float, float]:
        return NeuronaActorCriticOptimizada.calcular_estabilidad_ac(self)

    def obtener_estadisticas_ac(self) -> Dict[str, Any]:
        return NeuronaActorCriticOptimizada.obtener_estadisticas_ac(self)

    def verificar_estabilidad(self) -> Dict[str, bool]:
        return NeuronaActorCriticOptimizada.verificar_estabilidad(self)

    def reinicializar_con_parametros(self, learning_rate_actor: float = None, learning_rate_critic: float = None,
                                     gamma: float = None, lambda_gae: float = None) -> None:
        NeuronaActorCriticOptimizada.reinicializar_con_parametros(self, learning_rate_actor, learning_rate_critic, gamma, lambda_gae)

    def resetear_historial(self) -> None:
        NeuronaActorCriticOptimizada.resetear_historial(self)

    def a_dict(self) -> Dict[str, Any]:
        return NeuronaActorCriticOptimizada.a_dict(self)

    def guardar(self, ruta: str) -> None:
        NeuronaActorCriticOptimizada.guardar(self, ruta)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaRefuerzoActorCritic":
        obj = _GestorDelegado.cargar(ruta)
        c = cls(obj.input_size, obj.output_size, obj.nombre,
                learning_rate_actor=obj.learning_rate_actor, learning_rate_critic=obj.learning_rate_critic,
                gamma=obj.gamma, lambda_gae=obj.lambda_gae, usar_espectral=obj.usar_espectral)
        c.pesos_actor = obj.pesos_actor
        c.sesgo_actor = obj.sesgo_actor
        c.pesos_critic = obj.pesos_critic
        c.sesgo_critic = obj.sesgo_critic
        c.sigma_actor = obj.sigma_actor
        c.sigma_critic = obj.sigma_critic
        return c

    def __str__(self) -> str:
        return _GestorDelegado.__str__(self)

    def __repr__(self) -> str:
        return self.__str__()


def crear_neurona_actor_critic(input_size: int, output_size: int,
                               configuracion: Dict[str, Any] = None) -> NeuronaRefuerzoActorCritic:
    cfg = configuracion or {}
    return NeuronaRefuerzoActorCritic(
        input_size=input_size, output_size=output_size,
        nombre=cfg.get('nombre', 'NeuronaRefuerzoActorCritic'),
        learning_rate_actor=cfg.get('learning_rate_actor', 0.001),
        learning_rate_critic=cfg.get('learning_rate_critic', 0.002),
        gamma=cfg.get('gamma', 0.99), lambda_gae=cfg.get('lambda_gae', 0.95),
        usar_espectral=cfg.get('usar_espectral', True), meta_learning=cfg.get('meta_learning', True))


def analizar_ac(neurona: NeuronaRefuerzoActorCritic) -> Dict[str, Any]:
    return {'estadisticas': neurona.obtener_estadisticas_ac(), 'estable': neurona.verificar_estabilidad()}


RFEN3_CONFIG = {'inicializacion_preferida': 'espectral', 'learning_rate_actor_default': 0.001,
                'learning_rate_critic_default': 0.002, 'gamma_default': 0.99, 'lambda_gae_default': 0.95,
                'meta_learning_default': True, 'espectral_default': True,
                'umbral_convergencia': 0.7, 'umbral_estabilidad': 0.7}
logger.info("RFEN1_RN_3.py cargado correctamente - Neurona de Refuerzo Actor-Critic Avanzado")