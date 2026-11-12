"""RF_EN_SBRTM_RFEN1_RN_3_2.py
Módulo especializado en inicialización avanzada de pesos y ejecución optimizada Actor-Critic.

Incluye:
  - Decorador `@requiere_pesos_inicializados`: asegura el estado de tensores antes de inferencias.
  - Decorador `@tiempo_ejecucion`: telemetría de rendimiento y profiling de operaciones neuronales.
  - `NeuronaIniciacionDePesos`: clase dedicada exclusivamente a estrategias avanzadas de inicialización
    (espectral calibrada, ortogonal con ganancia, Xavier, He, inicializaciones mixtas y normalización espectral).
  - `NeuronaActorCriticOptimizada`: neurona Actor-Critic completa que fusiona la inicialización especializada
    con la gestión de gradientes, inferencia hacia adelante y GAE.
"""

from __future__ import annotations

import functools
import logging
import math
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

try:
    from .._rfen_base import (
        LUCIA_RL_CONFIG,
        _dt,
        _Ring,
        NeuronaRefuerzoBase,
        InicializadoresRL,
        inicializar_pesos_espectral,
        inicializar_pesos_ortogonal,
        inicializar_pesos_xavier,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os

    _base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    _spec = _ilu.spec_from_file_location(
        "RF_EN_rfen_base", _os.path.join(_base, "_rfen_base.py")
    )
    if _spec and _spec.loader:
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        LUCIA_RL_CONFIG = _mod.LUCIA_RL_CONFIG
        _dt = _mod._dt
        _Ring = _mod._Ring
        NeuronaRefuerzoBase = _mod.NeuronaRefuerzoBase
        InicializadoresRL = _mod.InicializadoresRL
        inicializar_pesos_espectral = _mod.inicializar_pesos_espectral
        inicializar_pesos_ortogonal = _mod.inicializar_pesos_ortogonal
        inicializar_pesos_xavier = _mod.inicializar_pesos_xavier
    else:
        # Fallback de contingencia
        class _Ring:  # type: ignore[no-redef]
            def __init__(self, cap: int = 512):
                self.cap = cap
                self._d: List[Any] = []
            def append(self, x: Any) -> None:
                self._d.append(x)
                if len(self._d) > self.cap:
                    del self._d[0:len(self._d) - self.cap]
            def __len__(self) -> int: return len(self._d)
            def tail(self, n: int) -> List[Any]: return self._d[-n:]
            def clear(self) -> None: self._d.clear()

        def _dt() -> np.dtype:  # type: ignore[no-redef]
            return np.dtype(np.float32)

        class NeuronaRefuerzoBase:  # type: ignore[no-redef]
            def __init__(self, input_size: int, output_size: int, nombre: str = "NeuronaBase"):
                self.input_size = int(input_size)
                self.output_size = int(output_size)
                self.nombre = str(nombre)
                self.pesos = None
                self.sesgo = None

        def inicializar_pesos_espectral(shape, seed=42):
            w = np.random.default_rng(seed).normal(0, 1, shape)
            s = np.linalg.svd(w, compute_uv=False)
            return (w / max(1e-12, s[0])).astype(np.float32)

        def inicializar_pesos_ortogonal(shape, seed=42, ganancia=1.0):
            a = np.random.default_rng(seed).normal(0, 1, shape)
            q, _ = np.linalg.qr(a) if shape[0] >= shape[1] else np.linalg.qr(a.T)
            q = q if shape[0] >= shape[1] else q.T
            return (q[:, :shape[1]] * ganancia).astype(np.float32)

        def inicializar_pesos_xavier(shape, fan_in=1, fan_out=1, seed=42):
            lim = math.sqrt(6.0 / max(1, fan_in + fan_out))
            return np.random.default_rng(seed).uniform(-lim, lim, shape).astype(np.float32)

# Subrutina de gradientes delegada
try:
    from .RF_EN_SBRTM_RFEN1_RN_3_1 import GestorGradientesAC, NeuronaGestionGradientesAC
except ImportError:
    try:
        from RF_EN_SBRTM_RFEN1_RN_3_1 import GestorGradientesAC, NeuronaGestionGradientesAC  # type: ignore[no-redef]
    except ImportError:
        import importlib.util as _ilu2
        import os as _os2
        _s3_1 = _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), "RF_EN_SBRTM_RFEN1_RN_3_1.py")
        _spec3_1 = _ilu2.spec_from_file_location("RF_EN_SBRTM_RFEN1_RN_3_1", _s3_1)
        if _spec3_1 and _spec3_1.loader:
            _m3_1 = _ilu2.module_from_spec(_spec3_1)
            _spec3_1.loader.exec_module(_m3_1)
            GestorGradientesAC = _m3_1.GestorGradientesAC
            NeuronaGestionGradientesAC = _m3_1.NeuronaGestionGradientesAC
        else:
            GestorGradientesAC = None  # type: ignore[assignment]
            NeuronaGestionGradientesAC = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ===========================================================================
# Decoradores funcionales para optimización y robustez
# ===========================================================================

def requiere_pesos_inicializados(metodo: Callable[..., Any]) -> Callable[..., Any]:
    """Decorador que garantiza que los pesos estén inicializados antes de computar."""
    @functools.wraps(metodo)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        if getattr(self, "pesos_actor", None) is None or getattr(self, "pesos_critic", None) is None:
            self.inicializar_pesos()
        return metodo(self, *args, **kwargs)
    return wrapper


def tiempo_ejecucion(clave_metrica: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorador para telemetría y profiling preciso de tiempo acumulado."""
    def decorador(metodo: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(metodo)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            resultado = metodo(self, *args, **kwargs)
            dt_s = time.perf_counter() - t0
            if hasattr(self, clave_metrica):
                setattr(self, clave_metrica, getattr(self, clave_metrica) + dt_s)
            return resultado
        return wrapper
    return decorador


# ===========================================================================
# 1. Clase Especializada en Inicialización de Pesos
# ===========================================================================

class NeuronaIniciacionDePesos:
    """Clase especializada en gestión, cálculo y normalización de pesos neuronales.

    Resuelve y optimiza:
      - Inicialización espectral precisa (radio espectral acotado <= 1.0).
      - Inicialización ortogonal con ganancia ajustada para políticas discretas.
      - Inicialización Xavier/Glorot y He/Kaiming.
      - Cálculo rápido del mayor valor singular por iteración de potencia acotada.
      - Normalización espectral por capa para estabilizar el entrenamiento Actor-Critic.
    """

    def __init__(self, seed: int = 42):
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)

    def inicializar_capa(
        self,
        shape: Tuple[int, int],
        modo: str = "espectral",
        ganancia: float = 1.0,
        fan_in: Optional[int] = None,
        fan_out: Optional[int] = None,
    ) -> np.ndarray:
        """Inicializa una matriz de pesos de acuerdo al modo seleccionado."""
        m = modo.lower()
        fi = fan_in if fan_in is not None else shape[0]
        fo = fan_out if fan_out is not None else shape[1]

        if m == "espectral":
            w = self.rng.normal(0.0, 1.0, shape)
            s0 = self.calcular_sigma(w, iters=5)
            w = (w / max(1e-12, s0)) * float(ganancia)
        elif m == "ortogonal":
            a = self.rng.normal(0.0, 1.0, shape)
            q, _ = np.linalg.qr(a) if shape[0] >= shape[1] else np.linalg.qr(a.T)
            q = q if shape[0] >= shape[1] else q.T
            w = q[:, :shape[1]] * float(ganancia)
        elif m in ("xavier", "glorot"):
            lim = math.sqrt(6.0 / max(1, fi + fo)) * float(ganancia)
            w = self.rng.uniform(-lim, lim, shape)
        elif m in ("he", "kaiming"):
            desv = math.sqrt(2.0 / max(1, fi)) * float(ganancia)
            w = self.rng.normal(0.0, desv, shape)
        else:
            raise ValueError(f"Modo de inicialización '{modo}' no reconocido")

        return np.ascontiguousarray(w, dtype=_dt())

    def calcular_sigma(self, w: np.ndarray, iters: int = 4) -> float:
        """Calcula el mayor valor singular por el método de potencia (rápido, sin SVD completo)."""
        wf = w.astype(np.float64)
        v = self.rng.normal(0.0, 1.0, (wf.shape[1], 1))
        v /= max(1e-12, float(np.linalg.norm(v)))
        u = np.zeros((wf.shape[0], 1), dtype=np.float64)
        for _ in range(iters):
            u = wf @ v
            u /= max(1e-12, float(np.linalg.norm(u)))
            v = wf.T @ u
            v /= max(1e-12, float(np.linalg.norm(v)))
        return float((u.T @ wf @ v)[0, 0])

    def aplicar_norma_espectral(self, w: np.ndarray, sigma: float) -> np.ndarray:
        """Aplica compresión por norma espectral garantizando Lipschitz <= 1."""
        return np.ascontiguousarray((w.astype(np.float64) / max(1e-12, sigma)).astype(_dt()))

    def inicializar_red_ac(
        self,
        input_size: int,
        output_size: int,
        modo: str = "espectral",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, float]:
        """Inicializa conjuntamente todos los tensores del Actor y del Crítico."""
        shp_a = (input_size, output_size)
        shp_c = (input_size, 1)

        # Para el actor, si es ortogonal se usa ganancia 0.01 o 1.0; para crítico 1.0
        w_actor = self.inicializar_capa(shp_a, modo=modo, ganancia=1.0)
        w_critic = self.inicializar_capa(shp_c, modo=modo, ganancia=1.0)

        b_actor = np.zeros((1, output_size), dtype=_dt())
        b_critic = np.zeros((1, 1), dtype=_dt())

        sig_a = self.calcular_sigma(w_actor)
        sig_c = self.calcular_sigma(w_critic)

        return w_actor, b_actor, w_critic, b_critic, sig_a, sig_c


# ===========================================================================
# 2. Clase Fusionada: Neurona Actor-Critic Optimizada
# ===========================================================================

class NeuronaActorCriticOptimizada(NeuronaRefuerzoBase):
    """Neurona Actor-Critic que fusiona la gestión de inicialización de pesos con gradientes y GAE.

    Utiliza:
      - `NeuronaIniciacionDePesos` para configuración y control de Lipschitz.
      - `GestorGradientesAC` para estabilización de gradientes y actualización.
      - Decoradores para precondición de inicialización y medición de rendimiento.
    """

    def __init__(
        self,
        input_size: int,
        output_size: int,
        nombre: str = "NeuronaActorCriticOptimizada",
        learning_rate_actor: float = 0.001,
        learning_rate_critic: float = 0.002,
        gamma: float = 0.99,
        lambda_gae: float = 0.95,
        usar_espectral: bool = True,
        meta_learning: bool = True,
        grad_clip: float = 5.0,
        semilla: int = 42,
        capacidad_historial: int = 512,
    ):
        super().__init__(input_size, output_size, nombre)
        self.learning_rate_actor = float(learning_rate_actor)
        self.learning_rate_critic = float(learning_rate_critic)
        self.gamma = float(gamma)
        self.lambda_gae = float(lambda_gae)
        self.usar_espectral = bool(usar_espectral)
        self.meta_learning = bool(meta_learning)
        self.grad_clip = float(grad_clip)
        self.semilla = int(semilla)
        self.rng = np.random.default_rng(self.semilla)

        # Gestor especializado de inicialización
        self.iniciador = NeuronaIniciacionDePesos(seed=self.semilla)

        self.pesos_actor: Optional[np.ndarray] = None
        self.sesgo_actor: Optional[np.ndarray] = None
        self.pesos_critic: Optional[np.ndarray] = None
        self.sesgo_critic: Optional[np.ndarray] = None
        self.sigma_actor: float = 1.0
        self.sigma_critic: float = 1.0

        self.pasos: int = 0
        self.tiempo_fwd: float = 0.0
        self.tiempo_upd: float = 0.0

        self.estadisticas_ac: Dict[str, Any] = {
            'convergencia_actor': 0.0,
            'convergencia_critic': 0.0,
            'estabilidad_actor': 0.0,
            'estabilidad_critic': 0.0,
            'advantage_media': 0.0,
            'advantage_std': 0.0,
            'valor_error_medio': 0.0,
            'policy_loss_medio': 0.0,
            'meta_adaptaciones': 0,
            'espectral_updates': 0,
        }

        self.historial_actor_loss = _Ring(capacidad_historial)
        self.historial_critic_loss = _Ring(capacidad_historial)
        self.historial_advantages = _Ring(capacidad_historial * 4)
        self.historial_valores = _Ring(capacidad_historial)
        self.historial_politicas = _Ring(capacidad_historial)

        logger.info(f"NeuronaActorCriticOptimizada creada: {self.nombre}")

    def inicializar_pesos(self, modo: Optional[str] = None) -> None:
        """Inicializa pesos mediante la clase especializada NeuronaIniciacionDePesos."""
        m = (modo or ('espectral' if self.usar_espectral else 'ortogonal')).lower()
        wa, ba, wc, bc, sa, sc = self.iniciador.inicializar_red_ac(
            self.input_size, self.output_size, modo=m
        )
        self.pesos_actor = wa
        self.sesgo_actor = ba
        self.pesos_critic = wc
        self.sesgo_critic = bc
        self.sigma_actor = sa
        self.sigma_critic = sc
        logger.info(f"Pesos inicializados con modo especializado: '{m}'")

    def _norma_espectral(self, w: np.ndarray, sigma: float) -> np.ndarray:
        if not self.usar_espectral:
            return w
        return self.iniciador.aplicar_norma_espectral(w, sigma)

    def _prep(self, estado: np.ndarray) -> np.ndarray:
        x = np.asarray(estado, dtype=_dt())
        if x.ndim == 1:
            x = x.reshape(1, -1)
        if x.shape[1] != self.input_size:
            raise ValueError(f"Dimensión de estado {x.shape[1]} != input_size {self.input_size}")
        return np.ascontiguousarray(x, dtype=_dt())

    @staticmethod
    def _softmax(z: np.ndarray) -> np.ndarray:
        z = np.asarray(z, dtype=np.float64)
        z = z - np.max(z, axis=1, keepdims=True)
        e = np.exp(np.clip(z, -30.0, 30.0))
        return e / np.maximum(np.sum(e, axis=1, keepdims=True), 1e-12)

    @requiere_pesos_inicializados
    def forward_actor(self, estado: np.ndarray) -> np.ndarray:
        assert self.pesos_actor is not None and self.sesgo_actor is not None
        x = self._prep(estado)
        w = self._norma_espectral(self.pesos_actor, self.sigma_actor)
        probs = self._softmax(np.dot(x, w).astype(np.float64) + self.sesgo_actor.astype(np.float64))
        p_res = probs.astype(_dt(), copy=False)
        self.historial_politicas.append(p_res.copy())
        return np.ascontiguousarray(p_res, dtype=_dt())

    @requiere_pesos_inicializados
    def forward_critic(self, estado: np.ndarray) -> np.ndarray:
        assert self.pesos_critic is not None and self.sesgo_critic is not None
        x = self._prep(estado)
        w = self._norma_espectral(self.pesos_critic, self.sigma_critic)
        v = (np.dot(x, w).astype(np.float64) + self.sesgo_critic.astype(np.float64)).astype(_dt(), copy=False)
        self.historial_valores.append(v.copy())
        return np.ascontiguousarray(v, dtype=_dt())

    @tiempo_ejecucion("tiempo_fwd")
    def forward(self, estado: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        return self.forward_actor(estado), self.forward_critic(estado)

    def seleccionar_accion(self, estado: np.ndarray) -> Tuple[int, float, float]:
        probs, valor = self.forward(estado)
        p = np.asarray(probs[0], dtype=np.float64)
        p = p / max(1e-12, float(p.sum()))
        acc = int(self.rng.choice(self.output_size, p=p))
        return acc, float(probs[0, acc]), float(valor[0, 0])

    def calcular_gae_advantages(
        self, recompensas: List[float], valores: List[float], siguiente_valor: float = 0.0
    ) -> np.ndarray:
        if GestorGradientesAC is not None:
            adv = GestorGradientesAC.calcular_gae(
                recompensas, valores, self.gamma, self.lambda_gae, siguiente_valor
            )
        else:
            r = np.asarray(recompensas, dtype=np.float64)
            v = np.asarray(valores, dtype=np.float64)
            v_next = np.append(v[1:], siguiente_valor)
            deltas = r + self.gamma * v_next - v
            adv = np.zeros_like(deltas)
            acc = 0.0
            descuento = self.gamma * self.lambda_gae
            for t in range(len(deltas) - 1, -1, -1):
                acc = deltas[t] + descuento * acc
                adv[t] = acc
        self.historial_advantages.append(adv.copy())
        self.estadisticas_ac['advantage_media'] = float(adv.mean())
        self.estadisticas_ac['advantage_std'] = float(adv.std())
        return adv

    def calcular_gradientes_ac(
        self,
        estados: List[np.ndarray],
        acciones: List[int],
        advantages: List[float],
        valores_objetivo: List[float],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if NeuronaGestionGradientesAC is not None:
            return NeuronaGestionGradientesAC.calcular_gradientes_ac(
                self, estados, acciones, advantages, valores_objetivo
            )
        # Fallback inline
        if self.pesos_actor is None or self.pesos_critic is None:
            raise ValueError("Pesos no inicializados")
        X = np.vstack([self._prep(s) for s in estados]).astype(np.float64)
        A = np.asarray(acciones, dtype=np.int64) % self.output_size
        Adv = np.asarray(advantages, dtype=np.float64)
        Vt = np.asarray(valores_objetivo, dtype=np.float64).reshape(-1, 1)
        n = len(X)
        wa = self._norma_espectral(self.pesos_actor, self.sigma_actor).astype(np.float64)
        wc = self._norma_espectral(self.pesos_critic, self.sigma_critic).astype(np.float64)
        logits = X @ wa + self.sesgo_actor.astype(np.float64)
        probs = self._softmax(logits).astype(np.float64)
        vals = X @ wc + self.sesgo_critic.astype(np.float64)
        oh = np.zeros_like(probs)
        oh[np.arange(n), A] = 1.0
        dlog = (oh - probs) * (Adv / max(1e-12, abs(Adv).std() + 1.0))[:, None] / n
        ga_w = X.T @ dlog
        ga_b = dlog.sum(axis=0, keepdims=True)
        err = (Vt - vals) / n
        gc_w = X.T @ err
        gc_b = err.sum(axis=0, keepdims=True)
        for g in (ga_w, ga_b, gc_w, gc_b):
            ng = float(np.linalg.norm(g))
            if self.grad_clip > 0 and ng > self.grad_clip:
                g *= self.grad_clip / (ng + 1e-12)
        return ga_w.astype(_dt()), ga_b.astype(_dt()), gc_w.astype(_dt()), gc_b.astype(_dt())

    @tiempo_ejecucion("tiempo_upd")
    def actualizar_pesos(
        self,
        grad_actor_pesos: np.ndarray,
        grad_actor_sesgo: np.ndarray,
        grad_critic_pesos: np.ndarray,
        grad_critic_sesgo: np.ndarray,
    ) -> Dict[str, float]:
        if NeuronaGestionGradientesAC is not None:
            return NeuronaGestionGradientesAC.actualizar_pesos(
                self, grad_actor_pesos, grad_actor_sesgo, grad_critic_pesos, grad_critic_sesgo
            )
        # Fallback inline
        self.pesos_actor = (self.pesos_actor.astype(np.float64) + self.learning_rate_actor * np.asarray(grad_actor_pesos, dtype=np.float64)).astype(_dt())
        self.sesgo_actor = (self.sesgo_actor.astype(np.float64) + self.learning_rate_actor * np.asarray(grad_actor_sesgo, dtype=np.float64)).astype(_dt())
        self.pesos_critic = (self.pesos_critic.astype(np.float64) + self.learning_rate_critic * np.asarray(grad_critic_pesos, dtype=np.float64)).astype(_dt())
        self.sesgo_critic = (self.sesgo_critic.astype(np.float64) + self.learning_rate_critic * np.asarray(grad_critic_sesgo, dtype=np.float64)).astype(_dt())
        self.pasos += 1
        if self.usar_espectral and self.pesos_actor is not None and self.pesos_critic is not None:
            self.sigma_actor = self.iniciador.calcular_sigma(self.pesos_actor)
            self.sigma_critic = self.iniciador.calcular_sigma(self.pesos_critic)
        return {'paso': float(self.pasos)}

    def entrenar_paso(
        self,
        estados: List[np.ndarray],
        acciones: List[int],
        recompensas: List[float],
        valores: List[float],
        siguiente_valor: float = 0.0,
    ) -> Dict[str, float]:
        adv = self.calcular_gae_advantages(recompensas, valores, siguiente_valor)
        vt = (adv + np.asarray(valores, dtype=np.float64)).tolist()
        ga = self.calcular_gradientes_ac(estados, acciones, adv.tolist(), vt)
        info = self.actualizar_pesos(*ga)
        return {'ventaja_media': float(np.mean(adv)), **info}

    def _adaptar_meta_learning(self) -> None:
        if NeuronaGestionGradientesAC is not None:
            NeuronaGestionGradientesAC._adaptar_meta_learning(self)

    def _calcular_convergencia_ac(self) -> None:
        if NeuronaGestionGradientesAC is not None:
            NeuronaGestionGradientesAC._calcular_convergencia_ac(self)

    def calcular_estabilidad_ac(self) -> Tuple[float, float]:
        if NeuronaGestionGradientesAC is not None:
            return NeuronaGestionGradientesAC.calcular_estabilidad_ac(self)
        return 0.0, 0.0

    def obtener_estadisticas_ac(self) -> Dict[str, Any]:
        if NeuronaGestionGradientesAC is not None:
            return NeuronaGestionGradientesAC.obtener_estadisticas_ac(self)
        return {'estado': 'no_inicializada' if self.pesos_actor is None else 'activa'}

    def verificar_estabilidad(self) -> Dict[str, bool]:
        if NeuronaGestionGradientesAC is not None:
            return NeuronaGestionGradientesAC.verificar_estabilidad(self)
        return {'estable': True}

    def reinicializar_con_parametros(
        self,
        learning_rate_actor: Optional[float] = None,
        learning_rate_critic: Optional[float] = None,
        gamma: Optional[float] = None,
        lambda_gae: Optional[float] = None,
    ) -> None:
        if NeuronaGestionGradientesAC is not None:
            NeuronaGestionGradientesAC.reinicializar_con_parametros(
                self, learning_rate_actor, learning_rate_critic, gamma, lambda_gae
            )
        else:
            if learning_rate_actor is not None: self.learning_rate_actor = float(learning_rate_actor)
            if learning_rate_critic is not None: self.learning_rate_critic = float(learning_rate_critic)
            if gamma is not None: self.gamma = float(gamma)
            if lambda_gae is not None: self.lambda_gae = float(lambda_gae)
            self.inicializar_pesos()

    def resetear_historial(self) -> None:
        self.historial_actor_loss.clear()
        self.historial_critic_loss.clear()
        self.historial_advantages.clear()
        self.historial_valores.clear()
        self.historial_politicas.clear()

    def a_dict(self) -> Dict[str, Any]:
        return {
            'input_size': self.input_size,
            'output_size': self.output_size,
            'nombre': self.nombre,
            'lr_actor': self.learning_rate_actor,
            'lr_critic': self.learning_rate_critic,
            'gamma': self.gamma,
            'lambda_gae': self.lambda_gae,
            'pesos_actor': self.pesos_actor.tolist() if self.pesos_actor is not None else None,
            'sesgo_actor': self.sesgo_actor.tolist() if self.sesgo_actor is not None else None,
            'pesos_critic': self.pesos_critic.tolist() if self.pesos_critic is not None else None,
            'sesgo_critic': self.sesgo_critic.tolist() if self.sesgo_critic is not None else None,
        }

    def guardar(self, ruta: str) -> None:
        import json
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(self.a_dict(), f)

    @classmethod
    def cargar(cls, ruta: str) -> "NeuronaActorCriticOptimizada":
        import json
        with open(ruta, 'r', encoding='utf-8') as f:
            d = json.load(f)
        o = cls(
            d['input_size'],
            d['output_size'],
            d.get('nombre', 'NeuronaActorCriticOptimizada'),
            learning_rate_actor=d.get('lr_actor', 0.001),
            learning_rate_critic=d.get('lr_critic', 0.002),
            gamma=d.get('gamma', 0.99),
            lambda_gae=d.get('lambda_gae', 0.95),
        )
        if d.get('pesos_actor') is not None:
            o.pesos_actor = np.asarray(d['pesos_actor'], dtype=_dt())
            o.pesos_critic = np.asarray(d['pesos_critic'], dtype=_dt())
            o.sesgo_actor = (
                np.asarray(d['sesgo_actor'], dtype=_dt())
                if d.get('sesgo_actor') is not None
                else np.zeros((1, o.output_size), dtype=_dt())
            )
            o.sesgo_critic = (
                np.asarray(d['sesgo_critic'], dtype=_dt())
                if d.get('sesgo_critic') is not None
                else np.zeros((1, 1), dtype=_dt())
            )
            o.sigma_actor = o.iniciador.calcular_sigma(o.pesos_actor)
            o.sigma_critic = o.iniciador.calcular_sigma(o.pesos_critic)
        return o

    def __str__(self) -> str:
        return (
            f"NeuronaActorCriticOptimizada(in={self.input_size}, out={self.output_size}, "
            f"lr_actor={self.learning_rate_actor}, lr_critic={self.learning_rate_critic}, "
            f"espectral={self.usar_espectral})"
        )

    def __repr__(self) -> str:
        return self.__str__()


__all__ = [
    "requiere_pesos_inicializados",
    "tiempo_ejecucion",
    "NeuronaIniciacionDePesos",
    "NeuronaActorCriticOptimizada",
]
