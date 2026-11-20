"""Neurona Actor-Critic y Gestión Avanzada de Gradientes (RF_EN · SBRTM · RN_3).

Módulo especializado en cálculo, recorte, estabilización y optimización de
gradientes en arquitecturas Actor-Critic (GAE, normalización espectral y meta-learning).

Convención de dimensiones:
  - pesos_actor: (input_size, output_size), sesgo_actor: (1, output_size)
  - pesos_critic: (input_size, 1), sesgo_critic: (1, 1)
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from .._rfen_base import (
        NeuronaRefuerzoBase,
        InicializadoresRL,
        _dt,
        _Ring,
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
        NeuronaRefuerzoBase = _mod.NeuronaRefuerzoBase
        InicializadoresRL = _mod.InicializadoresRL
        _dt = _mod._dt
        _Ring = _mod._Ring
        inicializar_pesos_espectral = _mod.inicializar_pesos_espectral
        inicializar_pesos_ortogonal = _mod.inicializar_pesos_ortogonal
        inicializar_pesos_xavier = _mod.inicializar_pesos_xavier
    else:
        # Fallback de contingencia si no se resuelve la ruta base
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

logger = logging.getLogger(__name__)


class GestorGradientesAC:
    """Subrutina especializada de cálculo, estabilización y gestión de gradientes."""

    @staticmethod
    def normalizar_ventajas(advantages: np.ndarray, eps: float = 1e-8) -> np.ndarray:
        """Estabilización numérica de ventajas (media cero y varianza unitaria robusta)."""
        adv = np.asarray(advantages, dtype=np.float64)
        if adv.size > 1:
            std = float(np.std(adv))
            return (adv - float(np.mean(adv))) / (std + eps)
        return adv / max(eps, abs(float(adv[0])) + 1.0)

    @staticmethod
    def recortar_gradientes(
        gradientes: List[np.ndarray], max_norm: float
    ) -> Tuple[List[np.ndarray], float]:
        """Recorte por norma L2 global conjunta para preservar coherencia angular."""
        if not gradientes:
            return gradientes, 0.0
        norma_total = math.sqrt(sum(float(np.sum(g.astype(np.float64) ** 2)) for g in gradientes))
        if max_norm > 0 and norma_total > max_norm:
            factor = max_norm / (norma_total + 1e-12)
            gradientes = [g * factor for g in gradientes]
            norma_total = max_norm
        return gradientes, norma_total

    @staticmethod
    def calcular_gae(
        recompensas: List[float],
        valores: List[float],
        gamma: float,
        lambda_gae: float,
        siguiente_valor: float = 0.0,
    ) -> np.ndarray:
        """Generalized Advantage Estimation (GAE) vectorizado."""
        r = np.asarray(recompensas, dtype=np.float64)
        v = np.asarray(valores, dtype=np.float64)
        v_next = np.append(v[1:], siguiente_valor)
        deltas = r + gamma * v_next - v
        adv = np.zeros_like(deltas)
        acc = 0.0
        descuento = gamma * lambda_gae
        for t in range(len(deltas) - 1, -1, -1):
            acc = deltas[t] + descuento * acc
            adv[t] = acc
        return adv


class NeuronaGestionGradientesAC(NeuronaRefuerzoBase):
    """Neurona Actor-Critic especializada en gestión y optimización de gradientes.

    Incorpora:
      - Gestión de gradientes Actor-Critic con bonus de entropía.
      - Recorte de gradiente por norma L2 global integrada.
      - Normalización espectral por iteración de potencia.
      - Meta-learning adaptativo de tasas de aprendizaje.
      - Métricas de estabilidad y convergencia en tiempo real.
    """

    def __init__(
        self,
        input_size: int,
        output_size: int,
        nombre: str = "NeuronaGestionGradientesAC",
        learning_rate_actor: float = 0.001,
        learning_rate_critic: float = 0.002,
        gamma: float = 0.99,
        lambda_gae: float = 0.95,
        usar_espectral: bool = True,
        meta_learning: bool = True,
        entropy_coef: float = 0.01,
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
        self.entropy_coef = float(entropy_coef)
        self.grad_clip = float(grad_clip)
        self.semilla = int(semilla)
        self.rng = np.random.default_rng(self.semilla)

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
            'entropia_media': 0.0,
            'norma_grad_global': 0.0,
            'meta_adaptaciones': 0,
            'espectral_updates': 0,
        }

        self.historial_actor_loss = _Ring(capacidad_historial)
        self.historial_critic_loss = _Ring(capacidad_historial)
        self.historial_advantages = _Ring(capacidad_historial * 4)
        self.historial_valores = _Ring(capacidad_historial)
        self.historial_politicas = _Ring(capacidad_historial)
        self.historial_normas_grad = _Ring(capacidad_historial)

        logger.info(f"NeuronaGestionGradientesAC inicializada: {self.nombre}")

    def inicializar_pesos(self, modo: Optional[str] = None) -> None:
        m = (modo or ('espectral' if self.usar_espectral else 'ortogonal')).lower()
        shp_a = (self.input_size, self.output_size)
        shp_c = (self.input_size, 1)

        if m == 'espectral':
            self.pesos_actor = inicializar_pesos_espectral(shp_a, seed=self.semilla)
            self.pesos_critic = inicializar_pesos_espectral(shp_c, seed=self.semilla)
        elif m == 'ortogonal':
            self.pesos_actor = inicializar_pesos_ortogonal(shp_a, seed=self.semilla)
            self.pesos_critic = inicializar_pesos_ortogonal(shp_c, seed=self.semilla)
        elif m in ('xavier', 'he'):
            self.pesos_actor = inicializar_pesos_xavier(shp_a, self.input_size, self.output_size, seed=self.semilla)
            self.pesos_critic = inicializar_pesos_xavier(shp_c, self.input_size, 1, seed=self.semilla)
        else:
            raise ValueError(f"Modo de inicialización '{m}' desconocido")

        self.pesos_actor = np.ascontiguousarray(self.pesos_actor, dtype=_dt())
        self.pesos_critic = np.ascontiguousarray(self.pesos_critic, dtype=_dt())
        self.sesgo_actor = np.zeros((1, self.output_size), dtype=_dt())
        self.sesgo_critic = np.zeros((1, 1), dtype=_dt())

        self.sigma_actor = self._sigma(self.pesos_actor)
        self.sigma_critic = self._sigma(self.pesos_critic)
        logger.info(f"Pesos inicializados con modo '{m}'")

    def _asegurar(self) -> None:
        if (
            self.pesos_actor is None
            or self.pesos_critic is None
            or self.sesgo_actor is None
            or self.sesgo_critic is None
        ):
            self.inicializar_pesos()

    @staticmethod
    def _sigma(w: np.ndarray, iters: int = 4) -> float:
        wf = w.astype(np.float64)
        rng = np.random.default_rng(0)
        v = rng.normal(0, 1, (wf.shape[1], 1))
        v /= max(1e-12, float(np.linalg.norm(v)))
        u = np.zeros((wf.shape[0], 1), dtype=np.float64)
        for _ in range(iters):
            u = wf @ v
            u /= max(1e-12, float(np.linalg.norm(u)))
            v = wf.T @ u
            v /= max(1e-12, float(np.linalg.norm(v)))
        return float((u.T @ wf @ v)[0, 0])

    def _norma_espectral(self, w: np.ndarray, sigma: float) -> np.ndarray:
        if not self.usar_espectral:
            return w
        return (w.astype(np.float64) / max(1e-12, sigma)).astype(_dt())

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

    def forward_actor(self, estado: np.ndarray) -> np.ndarray:
        self._asegurar()
        assert self.pesos_actor is not None and self.sesgo_actor is not None
        x = self._prep(estado)
        w = self._norma_espectral(self.pesos_actor, self.sigma_actor)
        probs = self._softmax(np.dot(x, w).astype(np.float64) + self.sesgo_actor.astype(np.float64))
        p_res = probs.astype(_dt(), copy=False)
        self.historial_politicas.append(p_res.copy())
        return np.ascontiguousarray(p_res, dtype=_dt())

    def forward_critic(self, estado: np.ndarray) -> np.ndarray:
        self._asegurar()
        assert self.pesos_critic is not None and self.sesgo_critic is not None
        x = self._prep(estado)
        w = self._norma_espectral(self.pesos_critic, self.sigma_critic)
        v = (np.dot(x, w).astype(np.float64) + self.sesgo_critic.astype(np.float64)).astype(_dt(), copy=False)
        self.historial_valores.append(v.copy())
        return np.ascontiguousarray(v, dtype=_dt())

    def forward(self, estado: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        t0 = time.perf_counter()
        probs = self.forward_actor(estado)
        vals = self.forward_critic(estado)
        self.tiempo_fwd += time.perf_counter() - t0
        return probs, vals

    def seleccionar_accion(self, estado: np.ndarray) -> Tuple[int, float, float]:
        probs, valor = self.forward(estado)
        p = np.asarray(probs[0], dtype=np.float64)
        p = p / max(1e-12, float(p.sum()))
        acc = int(self.rng.choice(self.output_size, p=p))
        return acc, float(probs[0, acc]), float(valor[0, 0])

    def calcular_gae_advantages(
        self, recompensas: List[float], valores: List[float], siguiente_valor: float = 0.0
    ) -> np.ndarray:
        adv = GestorGradientesAC.calcular_gae(
            recompensas, valores, self.gamma, self.lambda_gae, siguiente_valor
        )
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
        """Calcula y estabiliza gradientes para actor y crítico con bonus de entropía."""
        self._asegurar()
        assert self.pesos_actor is not None and self.pesos_critic is not None
        assert self.sesgo_actor is not None and self.sesgo_critic is not None

        X = np.vstack([self._prep(s) for s in estados]).astype(np.float64)
        A = np.asarray(acciones, dtype=np.int64) % self.output_size
        Adv_raw = np.asarray(advantages, dtype=np.float64)
        Vt = np.asarray(valores_objetivo, dtype=np.float64).reshape(-1, 1)
        n = len(X)
        if not (len(A) == n and len(Adv_raw) == n and len(Vt) == n):
            raise ValueError("estados, acciones, advantages y valores_objetivo deben tener la misma longitud")

        wa = self._norma_espectral(self.pesos_actor, self.sigma_actor).astype(np.float64)
        wc = self._norma_espectral(self.pesos_critic, self.sigma_critic).astype(np.float64)

        logits = X @ wa + self.sesgo_actor.astype(np.float64)
        probs = self._softmax(logits)
        vals = X @ wc + self.sesgo_critic.astype(np.float64)

        Adv_norm = GestorGradientesAC.normalizar_ventajas(Adv_raw)

        # Gradientes del Actor
        oh = np.zeros_like(probs)
        oh[np.arange(n), A] = 1.0
        dlog = (oh - probs) * Adv_norm[:, None] / n
        ga_w = X.T @ dlog
        ga_b = dlog.sum(axis=0, keepdims=True)

        # Bonus de Entropía
        ent = float(np.mean(-np.sum(probs * np.log(probs + 1e-8), axis=1)))
        self.estadisticas_ac['entropia_media'] = ent
        if self.entropy_coef > 0:
            ent_grad = -(np.log(probs + 1e-8) + 1.0) * probs
            coef = self.entropy_coef / n
            ga_w = ga_w + (X.T @ ent_grad) * coef
            ga_b = ga_b + ent_grad.sum(axis=0, keepdims=True) * coef

        # Gradientes del Crítico (MSE)
        err = (Vt - vals) / n
        gc_w = X.T @ err
        gc_b = err.sum(axis=0, keepdims=True)

        # Recorte conjunto de gradientes
        grads = [ga_w, ga_b, gc_w, gc_b]
        grads_clip, norma_global = GestorGradientesAC.recortar_gradientes(grads, self.grad_clip)
        ga_w, ga_b, gc_w, gc_b = grads_clip
        self.historial_normas_grad.append(norma_global)
        self.estadisticas_ac['norma_grad_global'] = norma_global

        pl = float(np.mean(-np.log(probs[np.arange(n), A] + 1e-8) * Adv_raw))
        cl = float(0.5 * np.mean((Vt - vals) ** 2))
        self.historial_actor_loss.append(pl)
        self.historial_critic_loss.append(cl)
        self.estadisticas_ac['policy_loss_medio'] = pl
        self.estadisticas_ac['valor_error_medio'] = cl

        return ga_w.astype(_dt()), ga_b.astype(_dt()), gc_w.astype(_dt()), gc_b.astype(_dt())

    def actualizar_pesos(
        self,
        grad_actor_pesos: np.ndarray,
        grad_actor_sesgo: np.ndarray,
        grad_critic_pesos: np.ndarray,
        grad_critic_sesgo: np.ndarray,
    ) -> Dict[str, float]:
        t0 = time.perf_counter()
        self._asegurar()
        assert self.pesos_actor is not None and self.pesos_critic is not None
        assert self.sesgo_actor is not None and self.sesgo_critic is not None

        # Ascenso por gradiente para el Actor, descenso para el Crítico
        self.pesos_actor = np.ascontiguousarray(
            (self.pesos_actor.astype(np.float64) + self.learning_rate_actor * np.asarray(grad_actor_pesos, dtype=np.float64)).astype(_dt())
        )
        self.sesgo_actor = np.ascontiguousarray(
            (self.sesgo_actor.astype(np.float64) + self.learning_rate_actor * np.asarray(grad_actor_sesgo, dtype=np.float64)).astype(_dt())
        )
        self.pesos_critic = np.ascontiguousarray(
            (self.pesos_critic.astype(np.float64) + self.learning_rate_critic * np.asarray(grad_critic_pesos, dtype=np.float64)).astype(_dt())
        )
        self.sesgo_critic = np.ascontiguousarray(
            (self.sesgo_critic.astype(np.float64) + self.learning_rate_critic * np.asarray(grad_critic_sesgo, dtype=np.float64)).astype(_dt())
        )

        self.pasos += 1

        if self.meta_learning:
            self._adaptar_meta_learning()

        if self.usar_espectral:
            self.sigma_actor = self._sigma(self.pesos_actor)
            self.sigma_critic = self._sigma(self.pesos_critic)
            self.estadisticas_ac['espectral_updates'] += 1

        self._calcular_convergencia_ac()
        self.tiempo_upd += time.perf_counter() - t0
        return {
            'paso': float(self.pasos),
            'norma_grad_global': self.estadisticas_ac['norma_grad_global'],
            'actor_loss': self.estadisticas_ac['policy_loss_medio'],
            'critic_loss': self.estadisticas_ac['valor_error_medio'],
        }

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
        if len(self.historial_actor_loss) < 10 or len(self.historial_critic_loss) < 10:
            return
        ta = float(np.mean(np.diff(np.asarray(self.historial_actor_loss.tail(10), dtype=np.float64))))
        tc = float(np.mean(np.diff(np.asarray(self.historial_critic_loss.tail(10), dtype=np.float64))))
        self.learning_rate_actor = float(np.clip(self.learning_rate_actor * (0.95 if ta > 0 else 1.05), 1e-6, 1e-2))
        self.learning_rate_critic = float(np.clip(self.learning_rate_critic * (0.95 if tc > 0 else 1.05), 1e-6, 1e-2))
        self.estadisticas_ac['meta_adaptaciones'] += 1

    def _calcular_convergencia_ac(self) -> None:
        if len(self.historial_actor_loss) < 10 or len(self.historial_critic_loss) < 10:
            return
        va = float(np.var(np.asarray(self.historial_actor_loss.tail(10), dtype=np.float64)))
        vc = float(np.var(np.asarray(self.historial_critic_loss.tail(10), dtype=np.float64)))
        self.estadisticas_ac['convergencia_actor'] = 1.0 / (1.0 + va)
        self.estadisticas_ac['convergencia_critic'] = 1.0 / (1.0 + vc)

    def calcular_estabilidad_ac(self) -> Tuple[float, float]:
        ea = ec = 0.0
        if len(self.historial_politicas) >= 20:
            arr_p = np.stack(self.historial_politicas.tail(20), axis=0).astype(np.float64)
            ea = 1.0 / (1.0 + float(np.mean(np.var(arr_p, axis=0))))
        if len(self.historial_valores) >= 20:
            arr_v = np.stack(self.historial_valores.tail(20), axis=0).astype(np.float64)
            ec = 1.0 / (1.0 + float(np.mean(np.var(arr_v, axis=0))))
        self.estadisticas_ac['estabilidad_actor'] = ea
        self.estadisticas_ac['estabilidad_critic'] = ec
        return ea, ec

    def obtener_estadisticas_ac(self) -> Dict[str, Any]:
        if self.pesos_actor is None or self.pesos_critic is None:
            return {'estado': 'no_inicializada'}
        ea, ec = self.calcular_estabilidad_ac()
        stats: Dict[str, Any] = {
            'learning_rate_actor': self.learning_rate_actor,
            'learning_rate_critic': self.learning_rate_critic,
            'gamma': self.gamma,
            'lambda_gae': self.lambda_gae,
            'convergencia_actor': self.estadisticas_ac['convergencia_actor'],
            'convergencia_critic': self.estadisticas_ac['convergencia_critic'],
            'estabilidad_actor': ea,
            'estabilidad_critic': ec,
            'norma_grad_global': self.estadisticas_ac['norma_grad_global'],
            'entropia_media': self.estadisticas_ac['entropia_media'],
            'meta_adaptaciones': self.estadisticas_ac['meta_adaptaciones'],
            'espectral_updates': self.estadisticas_ac['espectral_updates'],
            'usar_espectral': self.usar_espectral,
            'meta_learning': self.meta_learning,
            't_medio_fwd_us': self.tiempo_fwd / max(1, self.pasos + 1) * 1e6,
            't_medio_upd_us': self.tiempo_upd / max(1, self.pasos) * 1e6,
        }
        if len(self.historial_advantages):
            arr = np.concatenate([np.asarray(a, dtype=np.float64).flatten() for a in self.historial_advantages.tail(10)])
            stats.update({
                'advantage_media': float(arr.mean()),
                'advantage_std': float(arr.std()),
                'advantage_min': float(arr.min()),
                'advantage_max': float(arr.max()),
            })
        if len(self.historial_actor_loss):
            stats['actor_loss_medio'] = float(np.mean(np.asarray(self.historial_actor_loss.tail(10), dtype=np.float64)))
        if len(self.historial_critic_loss):
            stats['critic_loss_medio'] = float(np.mean(np.asarray(self.historial_critic_loss.tail(10), dtype=np.float64)))
        return stats

    def verificar_estabilidad(self) -> Dict[str, bool]:
        ea, ec = self.calcular_estabilidad_ac()
        est = {
            'actor_convergencia_ok': self.estadisticas_ac['convergencia_actor'] > 0.7,
            'critic_convergencia_ok': self.estadisticas_ac['convergencia_critic'] > 0.7,
            'actor_estable': ea > 0.7,
            'critic_estable': ec > 0.7,
            'lr_actor_ok': 1e-6 <= self.learning_rate_actor <= 1e-2,
            'lr_critic_ok': 1e-6 <= self.learning_rate_critic <= 1e-2,
            'gradientes_no_explosivos': self.estadisticas_ac['norma_grad_global'] < 20.0,
        }
        if self.pesos_actor is not None and self.pesos_critic is not None:
            est['pesos_actor_no_explosivos'] = float(np.max(np.abs(self.pesos_actor))) < 5.0
            est['pesos_critic_no_explosivos'] = float(np.max(np.abs(self.pesos_critic))) < 5.0
            est['sin_nan'] = bool(not np.isnan(self.pesos_actor).any() and not np.isnan(self.pesos_critic).any())
        else:
            est.update({'pesos_actor_no_explosivos': True, 'pesos_critic_no_explosivos': True, 'sin_nan': True})
        return est

    def resetear_historial(self) -> None:
        self.historial_actor_loss.clear()
        self.historial_critic_loss.clear()
        self.historial_advantages.clear()
        self.historial_valores.clear()
        self.historial_politicas.clear()
        self.historial_normas_grad.clear()

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
    def cargar(cls, ruta: str) -> "NeuronaGestionGradientesAC":
        import json
        with open(ruta, 'r', encoding='utf-8') as f:
            d = json.load(f)
        o = cls(
            d['input_size'],
            d['output_size'],
            d.get('nombre', 'NeuronaGestionGradientesAC'),
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
        return o

    def reinicializar_con_parametros(
        self,
        learning_rate_actor: Optional[float] = None,
        learning_rate_critic: Optional[float] = None,
        gamma: Optional[float] = None,
        lambda_gae: Optional[float] = None,
    ) -> None:
        if learning_rate_actor is not None:
            self.learning_rate_actor = float(learning_rate_actor)
        if learning_rate_critic is not None:
            self.learning_rate_critic = float(learning_rate_critic)
        if gamma is not None:
            self.gamma = float(gamma)
        if lambda_gae is not None:
            self.lambda_gae = float(lambda_gae)
        self.inicializar_pesos()
        self.resetear_historial()
        self.estadisticas_ac['meta_adaptaciones'] = 0
        self.estadisticas_ac['espectral_updates'] = 0
        self.pasos = 0
        logger.info(
            f"Actor-Critic reinicializada: lr_a={self.learning_rate_actor}, lr_c={self.learning_rate_critic}"
        )

    def __str__(self) -> str:
        return (
            f"NeuronaGestionGradientesAC(in={self.input_size}, out={self.output_size}, "
            f"lr_actor={self.learning_rate_actor}, lr_critic={self.learning_rate_critic}, "
            f"espectral={self.usar_espectral})"
        )

    def __repr__(self) -> str:
        return self.__str__()


__all__ = [
    "GestorGradientesAC",
    "NeuronaGestionGradientesAC",
]
