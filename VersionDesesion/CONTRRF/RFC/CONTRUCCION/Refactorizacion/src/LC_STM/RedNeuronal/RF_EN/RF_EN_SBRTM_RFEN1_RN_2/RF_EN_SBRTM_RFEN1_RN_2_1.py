"""RF_EN_SBRTM_RFEN1_RN_2_1.py
Neurona Policy Gradient y comunicación neuronal (RF_EN · SBRTM).

Importa directamente desde RFEN1_RN_2.py (líneas 89-333):
  · _Ring                            — buffer circular de historial
  · NeuronaRefuerzoPolicyGradient    — REINFORCE vectorizado con baseline

Sobre esa base añade:
  · NeuronaTest                      — resuelve los conflictos de integración
  · NeuronaDeComunicacionPolicyGradient — PG + sincronización por sockets/JSON/binario

Convención de formas: pesos (input_size, output_size), sesgo (1, output_size).
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import logging
import math
import os as _os
import socket
import struct
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Localización y carga de RFEN1_RN_2.py (módulo fuente, líneas 89-333)
# ---------------------------------------------------------------------------
_RFEN1_RN2_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    "RFEN1_RN_2.py",
)

try:
    _rn2_spec = _ilu.spec_from_file_location("RFEN1_RN_2", _RFEN1_RN2_PATH)
    _rn2_mod  = _ilu.module_from_spec(_rn2_spec)
    _rn2_spec.loader.exec_module(_rn2_mod)
    _RFEN1_RN2_OK = True
except Exception as _e_load:
    _rn2_mod       = None          # type: ignore[assignment]
    _RFEN1_RN2_OK  = False
    logging.getLogger(__name__).warning(
        f"No se pudo cargar RFEN1_RN_2.py desde '{_RFEN1_RN2_PATH}': {_e_load}"
    )

# ---------------------------------------------------------------------------
# Importaciones desde RFEN1_RN_2  (líneas 89-333)
# ---------------------------------------------------------------------------
# -- _Ring  (líneas 89-106) --------------------------------------------------
if _RFEN1_RN2_OK:
    _Ring             = _rn2_mod._Ring              # type: ignore[union-attr]
    _dt               = _rn2_mod._dt                # type: ignore[union-attr]
    InicializadoresRL = _rn2_mod.InicializadoresRL  # type: ignore[union-attr]
    NeuronaRefuerzoBase = _rn2_mod.NeuronaRefuerzoBase  # type: ignore[union-attr]
    # NeuronaRefuerzoPolicyGradient  (líneas 109-332) importada más abajo
    _NeuronaRefuerzoPolicyGradient_RN2 = _rn2_mod.NeuronaRefuerzoPolicyGradient  # type: ignore[union-attr]
else:
    # Fallback mínimo si RFEN1_RN_2.py no está disponible
    class _Ring:                                    # type: ignore[no-redef]
        def __init__(self, cap: int = 512):
            self.cap = cap
            self._d: List[Any] = []
        def append(self, x: Any) -> None:
            self._d.append(x)
            if len(self._d) > self.cap:
                del self._d[0:len(self._d) - self.cap]
        def __len__(self) -> int:
            return len(self._d)
        def tail(self, n: int) -> List[Any]:
            return self._d[-n:]
        def clear(self) -> None:
            self._d.clear()

    def _dt() -> np.dtype:                          # type: ignore[no-redef]
        return np.dtype(np.float32)

    class NeuronaRefuerzoBase:                      # type: ignore[no-redef]
        def __init__(self, input_size, output_size, nombre="NeuronaRefuerzo"):
            self.input_size  = int(input_size)
            self.output_size = int(output_size)
            self.nombre      = str(nombre)
            self.pesos       = None
            self.sesgo       = None
            self.historial_activaciones: List[np.ndarray] = []
            self.historial_gradientes: List[Any]          = []
        def inicializar_pesos(self): raise NotImplementedError
        def forward(self, e): raise NotImplementedError
        def resetear_historial(self):
            self.historial_activaciones = []
            self.historial_gradientes   = []

    class InicializadoresRL:                        # type: ignore[no-redef]
        @staticmethod
        def _rng(seed=42): return np.random.default_rng(seed)
        @classmethod
        def he(cls, shape, fan_in=1, seed=42):
            return cls._rng(seed).normal(0, math.sqrt(2/max(1, fan_in)), shape).astype(np.float32)
        @classmethod
        def xavier(cls, shape, fan_in=1, fan_out=1, seed=42):
            lim = math.sqrt(6/max(1, fan_in + fan_out))
            return cls._rng(seed).uniform(-lim, lim, shape).astype(np.float32)
        @classmethod
        def ortogonal(cls, shape, seed=42, ganancia=1.0):
            a = cls._rng(seed).normal(0, 1, shape)
            q, _ = (np.linalg.qr(a) if shape[0] >= shape[1] else np.linalg.qr(a.T))
            q = q if shape[0] >= shape[1] else q.T
            return (q[:, :shape[1]] * ganancia).astype(np.float32)

    _NeuronaRefuerzoPolicyGradient_RN2 = None      # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ===========================================================================
# NeuronaRefuerzoPolicyGradient  —  importada desde RFEN1_RN_2.py (L109-332)
# ===========================================================================
# Se expone con el mismo nombre para que el resto del paquete pueda importarla
# desde aquí sin importar directamente RFEN1_RN_2.
if _RFEN1_RN2_OK:
    # Referencia directa: es la clase definida en RFEN1_RN_2.py líneas 109-332
    NeuronaRefuerzoPolicyGradient = _NeuronaRefuerzoPolicyGradient_RN2
else:
    # Implementación de emergencia (sin RFEN1_RN_2.py disponible)
    class NeuronaRefuerzoPolicyGradient(NeuronaRefuerzoBase):   # type: ignore[no-redef]
        """Implementación de emergencia (RFEN1_RN_2.py no encontrado)."""

        @staticmethod
        def _softmax(z: np.ndarray) -> np.ndarray:
            z = z - np.max(z, axis=1, keepdims=True)
            e = np.exp(np.clip(z, -30, 30))
            return e / np.maximum(np.sum(e, axis=1, keepdims=True), 1e-12)

        def __init__(self, input_size, output_size,
                     nombre="NeuronaRefuerzoPolicyGradient",
                     learning_rate=0.001, gamma=0.99,
                     usar_ortogonal=True, entropy_coef=0.01,
                     grad_clip=5.0, usar_baseline=True,
                     semilla=42, capacidad_historial=512):
            super().__init__(input_size, output_size, nombre)
            self.learning_rate  = float(learning_rate)
            self.gamma          = float(gamma)
            self.usar_ortogonal = bool(usar_ortogonal)
            self.entropy_coef   = float(entropy_coef)
            self.grad_clip      = float(grad_clip)
            self.usar_baseline  = bool(usar_baseline)
            self.rng            = np.random.default_rng(semilla)
            self.semilla        = int(semilla)
            self.pasos          = 0
            self.tiempo_fwd     = 0.0
            self.tiempo_upd     = 0.0
            self.estadisticas_pg = {
                'gradiente_politica_norma': 0.0, 'entropia_politica': 0.0,
                'probabilidad_accion_media': 0.0, 'probabilidad_accion_std': 0.0,
                'convergencia_politica': 0.0, 'estabilidad_politica': 0.0,
                'actualizaciones_politica': 0, 'exploracion_efectiva': 0.0}
            self.historial_politicas                = _Ring(capacidad_historial)
            self.historial_gradientes               = _Ring(capacidad_historial)
            self.historial_entropias                = _Ring(capacidad_historial)
            self.historial_recompensas_descontadas  = _Ring(capacidad_historial)

        @property
        def num_estados(self):  return self.input_size
        @property
        def num_acciones(self): return self.output_size

        def inicializar_pesos(self, modo=None):
            m   = (modo or ('ortogonal' if self.usar_ortogonal else 'xavier')).lower()
            shp = (self.input_size, self.output_size)
            if m == 'ortogonal':
                self.pesos = InicializadoresRL.ortogonal(shp, seed=self.semilla)
            elif m == 'xavier':
                self.pesos = InicializadoresRL.xavier(shp, self.input_size, self.output_size, seed=self.semilla)
            elif m == 'he':
                self.pesos = InicializadoresRL.he(shp, self.input_size, seed=self.semilla)
            else:
                raise ValueError(f"modo {m} desconocido")
            self.pesos = np.ascontiguousarray(self.pesos, dtype=_dt())
            self.sesgo = np.zeros((1, self.output_size), dtype=_dt())

        def _asegurar(self):
            if self.pesos is None or self.sesgo is None:
                self.inicializar_pesos()

        def _prep(self, estado):
            x = np.asarray(estado, dtype=_dt())
            if x.ndim == 1: x = x.reshape(1, -1)
            if x.shape[1] != self.input_size:
                raise ValueError(f"estado dim {x.shape[1]} != input {self.input_size}")
            return np.ascontiguousarray(x, dtype=_dt())

        def forward(self, estado):
            t0 = time.perf_counter(); self._asegurar()
            x = self._prep(estado)
            probs = self._softmax(np.dot(x, self.pesos) + self.sesgo).astype(_dt(), copy=False)
            self.historial_politicas.append(probs.copy())
            ent = float(np.mean(-np.sum(probs.astype(np.float64)*np.log(probs.astype(np.float64)+1e-8), axis=1)))
            self.historial_entropias.append(ent)
            self.tiempo_fwd += time.perf_counter() - t0
            return np.ascontiguousarray(probs, dtype=_dt())

        def resetear_historial(self):
            super().resetear_historial()
            for b in (self.historial_politicas, self.historial_gradientes,
                      self.historial_entropias, self.historial_recompensas_descontadas):
                b.clear()

        def seleccionar_accion(self, estado):
            probs = self.forward(estado)
            p = probs[0].astype(np.float64); p /= max(1e-12, p.sum())
            acc = int(self.rng.choice(self.output_size, p=p))
            return acc, float(probs[0, acc])

        def recompensas_descontadas(self, recompensas):
            g = np.zeros(len(recompensas)); acc = 0.0
            for t in range(len(recompensas)-1, -1, -1):
                acc = recompensas[t] + self.gamma*acc; g[t] = acc
            return g

        def calcular_gradiente_politica(self, estados, acciones, recompensas_descontadas):
            self._asegurar()
            X = np.vstack([self._prep(s) for s in estados]).astype(np.float64)
            A = np.asarray(acciones, dtype=np.int64)
            G = np.asarray(recompensas_descontadas, dtype=np.float64); n = len(X)
            logits = X @ self.pesos.astype(np.float64) + self.sesgo.astype(np.float64)
            probs  = self._softmax(logits).astype(np.float64)
            if self.usar_baseline and n > 1:
                G = (G - G.mean()) / (G.std() + 1e-8)
            one_hot = np.zeros_like(probs)
            one_hot[np.arange(n), A % self.output_size] = 1.0
            dlogits = (one_hot - probs) * G[:, None] / n
            grad_w  = X.T @ dlogits
            grad_b  = dlogits.sum(axis=0, keepdims=True)
            if self.entropy_coef > 0:
                logp = np.log(probs+1e-8); ec = self.entropy_coef/n
                grad_w += (X.T @ (-(logp+1.0)*probs))*ec
                grad_b += (-(logp+1.0)*probs).sum(axis=0, keepdims=True)*ec
            ng = float(np.linalg.norm(grad_w))
            if self.grad_clip > 0 and ng > self.grad_clip:
                f = self.grad_clip/(ng+1e-12); grad_w *= f; grad_b *= f
                ng = float(np.linalg.norm(grad_w))
            self.historial_gradientes.append(ng)
            self.estadisticas_pg['gradiente_politica_norma'] = ng
            self.historial_recompensas_descontadas.append(float(np.mean(G)))
            return grad_w.astype(_dt()), grad_b.astype(_dt())

        def actualizar_politica(self, gw, gb):
            t0 = time.perf_counter()
            if self.pesos is None or self.sesgo is None:
                raise ValueError("Pesos no inicializados")
            self.pesos = np.ascontiguousarray((self.pesos.astype(np.float64)+self.learning_rate*np.asarray(gw, dtype=np.float64)).astype(_dt()))
            self.sesgo = np.ascontiguousarray((self.sesgo.astype(np.float64)+self.learning_rate*np.asarray(gb, dtype=np.float64)).astype(_dt()))
            self.pasos += 1; self.estadisticas_pg['actualizaciones_politica'] += 1
            self._calcular_convergencia_politica()
            self.tiempo_upd += time.perf_counter() - t0
            return {'paso': float(self.pasos), 'norma_grad': self.estadisticas_pg['gradiente_politica_norma']}

        def entrenar_episodio(self, estados, acciones, recompensas):
            g = self.recompensas_descontadas(recompensas)
            gw, gb = self.calcular_gradiente_politica(estados, acciones, g.tolist())
            info = self.actualizar_politica(gw, gb)
            return {'retorno': float(np.sum(recompensas)), **info}

        def _calcular_convergencia_politica(self):
            if len(self.historial_gradientes) < 10: return
            var = float(np.var(np.asarray(self.historial_gradientes.tail(10), dtype=np.float64)))
            self.estadisticas_pg['convergencia_politica'] = 1.0/(1.0+var)

        def calcular_estabilidad_politica(self):
            if len(self.historial_politicas) < 20: return 0.0
            arr = np.stack(self.historial_politicas.tail(20), axis=0).astype(np.float64)
            est = 1.0/(1.0+float(np.mean(np.var(arr, axis=0))))
            self.estadisticas_pg['estabilidad_politica'] = est; return est

        def calcular_exploracion_efectiva(self):
            if not len(self.historial_entropias): return 0.0
            ent = float(np.mean(np.asarray(self.historial_entropias.tail(10), dtype=np.float64)))
            exp = ent / max(1e-12, math.log(self.output_size))
            self.estadisticas_pg['exploracion_efectiva'] = exp; return exp

        def obtener_estadisticas_pg(self):
            if self.pesos is None: return {'estado': 'no_inicializada'}
            if len(self.historial_politicas):
                arr = np.stack(self.historial_politicas.tail(10), axis=0).astype(np.float64)
                self.estadisticas_pg['probabilidad_accion_media'] = float(np.mean(arr))
                self.estadisticas_pg['probabilidad_accion_std']   = float(np.std(arr))
            if len(self.historial_entropias):
                self.estadisticas_pg['entropia_politica'] = float(np.mean(np.asarray(self.historial_entropias.tail(10), dtype=np.float64)))
            return {'learning_rate': self.learning_rate, 'gamma': self.gamma,
                    'entropy_coef': self.entropy_coef,
                    'convergencia_politica': self.estadisticas_pg['convergencia_politica'],
                    'estabilidad_politica': self.calcular_estabilidad_politica(),
                    'exploracion_efectiva': self.calcular_exploracion_efectiva(),
                    'actualizaciones_politica': self.estadisticas_pg['actualizaciones_politica'],
                    'gradiente_politica_norma': self.estadisticas_pg['gradiente_politica_norma'],
                    'entropia_politica': self.estadisticas_pg['entropia_politica'],
                    'probabilidad_accion_media': self.estadisticas_pg['probabilidad_accion_media'],
                    'probabilidad_accion_std': self.estadisticas_pg['probabilidad_accion_std'],
                    't_medio_fwd_us': self.tiempo_fwd/max(1, self.pasos+1)*1e6,
                    't_medio_upd_us': self.tiempo_upd/max(1, self.pasos)*1e6}

        def verificar_estabilidad(self):
            est = {'convergencia_ok': self.estadisticas_pg['convergencia_politica'] > 0.7,
                   'politica_estable': self.calcular_estabilidad_politica() > 0.7,
                   'exploracion_efectiva': 0.1 <= self.calcular_exploracion_efectiva() <= 0.9,
                   'gradientes_no_explosivos': self.estadisticas_pg['gradiente_politica_norma'] < 10.0,
                   'gradientes_no_desaparecen': self.estadisticas_pg['gradiente_politica_norma'] > 1e-8}
            if self.pesos is not None:
                pmax = float(np.max(np.abs(self.pesos)))
                pmin = max(float(np.min(np.abs(self.pesos))), 1e-12)
                est.update({'pesos_no_explosivos': pmax < 5.0,
                            'pesos_no_desaparecen': pmin > 1e-6,
                            'pesos_balanceados': pmax/pmin < 1000.0,
                            'sin_nan': bool(not np.isnan(self.pesos).any())})
            else:
                est.update({'pesos_no_explosivos': True, 'pesos_no_desaparecen': True,
                            'pesos_balanceados': True, 'sin_nan': True})
            return est


# ===========================================================================
# NeuronaTest — resuelve los conflictos de integración entre los dos módulos
# ===========================================================================

class NeuronaTest(NeuronaRefuerzoPolicyGradient):
    """Adaptador de integración entre RF_EN_SBRTM_RFEN1_RN_2_1 y RFEN1_RN_2.

    Hereda directamente de ``NeuronaRefuerzoPolicyGradient`` tal y como está
    definida en RFEN1_RN_2.py (líneas 109-332) y resuelve los siguientes
    conflictos punto a punto:

    C1  _Ring / _dt — unificados
        RFEN1_RN_2 los define localmente; este archivo los importa y re-expone
        con el mismo nombre.  Todos los buffers de historial usan el mismo
        ``_Ring`` de RFEN1_RN_2.

    C2  inicializar_pesos — sin ``Inicializacion.crear``
        La versión de RFEN1_RN_2 llama a ``InicializadoresRL`` directamente
        (sin atributo ``Inicializacion``).  ``NeuronaTest`` hereda esa
        implementación correcta; no necesita ``self.Inicializacion.crear``.

    C3  SubrutinaPG — añadida como clase anidada
        RFEN1_RN_2 hace el cálculo inline; ``NeuronaTest`` expone
        ``SubrutinaPG`` como clase anidada (misma interfaz que la versión
        SBRTM) sin romper los métodos heredados.

    C4  forward — más robusto
        ``NeuronaTest.forward`` usa ``SubrutinaPG.softmax`` (float64, clip ±30)
        en lugar del ``_softmax`` estático heredado, eliminando posibles
        desbordamientos con logits extremos.

    C5  calcular_exploracion_efectiva — protección contra log(1)
        RFEN1_RN_2 llama ``math.log(self.output_size)`` sin guardia; si
        ``output_size == 1``, da ``log(1) = 0`` → división por cero.
        ``NeuronaTest`` sobreescribe el método con ``max(2, self.output_size)``.

    C6  recorte de gradiente — norma conjunta pesos + sesgo
        RFEN1_RN_2 recorta solo por la norma de ``grad_w``.  ``NeuronaTest``
        sobreescribe ``calcular_gradiente_politica`` usando
        ``SubrutinaPG.recortar`` (norma conjunta), que es más conservador.
    """

    # ------------------------------------------------------------------
    # C3 — SubrutinaPG como clase anidada (misma API que versión SBRTM)
    # ------------------------------------------------------------------
    class SubrutinaPG:
        """Subrutina unificada de cálculo de política (REINFORCE + entropía)."""

        @staticmethod
        def softmax(logits: np.ndarray) -> np.ndarray:
            z = np.asarray(logits, dtype=np.float64)
            z = z - np.max(z, axis=1, keepdims=True)
            e = np.exp(np.clip(z, -30.0, 30.0))
            return e / np.maximum(np.sum(e, axis=1, keepdims=True), 1e-12)

        @staticmethod
        def entropia(probs: np.ndarray) -> float:
            p = np.asarray(probs, dtype=np.float64)
            return float(np.mean(-np.sum(p * np.log(p + 1e-8), axis=1)))

        @staticmethod
        def descontar(recompensas: List[float], gamma: float) -> np.ndarray:
            r = np.asarray(recompensas, dtype=np.float64)
            g = np.zeros(r.size, dtype=np.float64)
            acc = 0.0
            for t in range(r.size - 1, -1, -1):
                acc = r[t] + gamma * acc
                g[t] = acc
            return g

        @staticmethod
        def ventajas(G: np.ndarray, usar_baseline: bool = True) -> np.ndarray:
            G = np.asarray(G, dtype=np.float64)
            if usar_baseline and G.size > 1:
                G = (G - G.mean()) / (G.std() + 1e-8)
            return G

        @staticmethod
        def gradientes_reinforce(
            X: np.ndarray, probs: np.ndarray,
            acciones: np.ndarray, ventajas: np.ndarray,
            entropy_coef: float,
        ) -> Tuple[np.ndarray, np.ndarray, float]:
            n = probs.shape[0]
            one_hot = np.zeros_like(probs)
            one_hot[np.arange(n), acciones] = 1.0
            dlogits = (one_hot - probs) * ventajas[:, None] / n
            grad_w  = X.T @ dlogits
            grad_b  = dlogits.sum(axis=0, keepdims=True)
            ent     = float(np.mean(-np.sum(probs * np.log(probs + 1e-8), axis=1)))
            if entropy_coef > 0:
                ent_grad = -(np.log(probs + 1e-8) + 1.0) * probs
                coef     = entropy_coef / n
                grad_w   = grad_w + (X.T @ ent_grad) * coef
                grad_b   = grad_b + ent_grad.sum(axis=0, keepdims=True) * coef
            return grad_w, grad_b, ent

        @staticmethod
        def recortar(
            grad_w: np.ndarray, grad_b: np.ndarray, max_norm: float
        ) -> Tuple[np.ndarray, np.ndarray, float]:
            """Recorte por norma conjunta pesos + sesgo (C6)."""
            norma = float(np.sqrt(np.sum(grad_w ** 2) + np.sum(grad_b ** 2)))
            if max_norm > 0 and norma > max_norm:
                f      = max_norm / (norma + 1e-12)
                grad_w = grad_w * f
                grad_b = grad_b * f
                norma  = float(np.sqrt(np.sum(grad_w ** 2) + np.sum(grad_b ** 2)))
            return grad_w, grad_b, norma

        @staticmethod
        def elegir(
            probs: np.ndarray, rng: np.random.Generator, n_acciones: int
        ) -> Tuple[int, float]:
            p   = np.asarray(probs, dtype=np.float64)
            p   = p / max(1e-12, float(p.sum()))
            acc = int(rng.choice(n_acciones, p=p))
            return acc, float(p[acc])

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------
    def __init__(
        self,
        input_size: int,
        output_size: int,
        nombre: str = "NeuronaTest",
        learning_rate: float = 0.001,
        gamma: float = 0.99,
        usar_ortogonal: bool = True,
        entropy_coef: float = 0.01,
        grad_clip: float = 5.0,
        usar_baseline: bool = True,
        semilla: int = 42,
        capacidad_historial: int = 512,
    ):
        super().__init__(
            input_size=input_size, output_size=output_size, nombre=nombre,
            learning_rate=learning_rate, gamma=gamma,
            usar_ortogonal=usar_ortogonal, entropy_coef=entropy_coef,
            grad_clip=grad_clip, usar_baseline=usar_baseline,
            semilla=semilla, capacidad_historial=capacidad_historial,
        )
        self._rn2_cargado = _RFEN1_RN2_OK
        logger.info(
            f"NeuronaTest creada "
            f"(RFEN1_RN_2={'cargado' if _RFEN1_RN2_OK else 'FALLBACK'}): "
            f"input={input_size}, output={output_size}, nombre={nombre}"
        )

    # ------------------------------------------------------------------
    # C4 — forward con SubrutinaPG.softmax (float64, clip ±30)
    # ------------------------------------------------------------------
    def forward(self, estado: np.ndarray) -> np.ndarray:
        t0 = time.perf_counter()
        self._asegurar()
        assert self.pesos is not None and self.sesgo is not None
        x     = self._prep(estado)
        probs = self.SubrutinaPG.softmax(
            np.dot(x, self.pesos).astype(np.float64) + self.sesgo
        ).astype(_dt(), copy=False)
        self.historial_politicas.append(probs.copy())
        self.historial_entropias.append(self.SubrutinaPG.entropia(probs))
        self.tiempo_fwd += time.perf_counter() - t0
        return np.ascontiguousarray(probs, dtype=_dt())

    # ------------------------------------------------------------------
    # C5 — calcular_exploracion_efectiva protegida contra log(1)
    # ------------------------------------------------------------------
    def calcular_exploracion_efectiva(self) -> float:
        if not len(self.historial_entropias):
            return 0.0
        ent = float(np.mean(
            np.asarray(self.historial_entropias.tail(10), dtype=np.float64)
        ))
        exp = ent / max(1e-12, math.log(max(2, self.output_size)))   # C5
        self.estadisticas_pg['exploracion_efectiva'] = exp
        return exp

    # ------------------------------------------------------------------
    # C6 — calcular_gradiente_politica con norma conjunta (SubrutinaPG.recortar)
    # ------------------------------------------------------------------
    def calcular_gradiente_politica(
        self,
        estados: List[np.ndarray],
        acciones: List[int],
        recompensas_descontadas: List[float],
    ) -> Tuple[np.ndarray, np.ndarray]:
        self._asegurar()
        assert self.pesos is not None and self.sesgo is not None
        X = np.vstack([self._prep(s) for s in estados]).astype(np.float64)
        A = np.asarray(acciones, dtype=np.int64) % self.output_size
        G = np.asarray(recompensas_descontadas, dtype=np.float64)
        n = len(X)
        if not (len(A) == n and len(G) == n):
            raise ValueError(
                "estados, acciones y recompensas deben tener la misma longitud"
            )
        logits   = X @ self.pesos.astype(np.float64) + self.sesgo.astype(np.float64)
        probs    = self.SubrutinaPG.softmax(logits)
        ventajas = self.SubrutinaPG.ventajas(G, self.usar_baseline)
        grad_w, grad_b, ent = self.SubrutinaPG.gradientes_reinforce(
            X, probs, A, ventajas, self.entropy_coef
        )
        grad_w, grad_b, ng = self.SubrutinaPG.recortar(   # C6: norma conjunta
            grad_w, grad_b, self.grad_clip
        )
        self.historial_gradientes.append(ng)
        self.estadisticas_pg['gradiente_politica_norma'] = ng
        self.estadisticas_pg['entropia_politica']        = ent
        self.historial_recompensas_descontadas.append(float(np.mean(G)))
        return grad_w.astype(_dt()), grad_b.astype(_dt())

    # ------------------------------------------------------------------
    # seleccionar_accion  — usa SubrutinaPG.elegir
    # ------------------------------------------------------------------
    def seleccionar_accion(self, estado: np.ndarray) -> Tuple[int, float]:
        probs = self.forward(estado)
        return self.SubrutinaPG.elegir(probs[0], self.rng, self.output_size)

    # ------------------------------------------------------------------
    # recompensas_descontadas — vectorizado via SubrutinaPG.descontar
    # ------------------------------------------------------------------
    def recompensas_descontadas(self, recompensas: List[float]) -> np.ndarray:
        return self.SubrutinaPG.descontar(recompensas, self.gamma)

    # ------------------------------------------------------------------
    # API de diagnóstico de integración
    # ------------------------------------------------------------------
    def info_integracion(self) -> Dict[str, Any]:
        """Metadatos sobre el estado de integración con RFEN1_RN_2."""
        return {
            'rn2_cargado'       : self._rn2_cargado,
            'rn2_path'          : _RFEN1_RN2_PATH,
            'dtype_activo'      : str(_dt()),
            'ring_clase'        : type(self.historial_politicas).__name__,
            'inicializadores'   : 'InicializadoresRL(RFEN1_RN_2)' if _RFEN1_RN2_OK else 'numpy-fallback',
            'softmax'           : 'SubrutinaPG.softmax (float64, clip±30)',
            'recorte_gradiente' : 'norma conjunta pesos+sesgo (SubrutinaPG.recortar)',
            'log_guard'         : f'max(2, output_size) = max(2, {self.output_size})',
            'conflictos_resueltos': [
                'C1: _Ring/_dt importados desde RFEN1_RN_2.py',
                'C2: inicializar_pesos usa InicializadoresRL (sin Inicializacion.crear)',
                'C3: SubrutinaPG disponible como clase anidada',
                'C4: forward con SubrutinaPG.softmax (float64, clip±30)',
                'C5: calcular_exploracion_efectiva protegida contra log(1)',
                'C6: recorte de gradiente por norma conjunta pesos+sesgo',
            ],
        }


# ===========================================================================
# NeuronaDeComunicacionPolicyGradient
# Sincronización por sockets, serialización JSON/binaria (protocolo RFPG)
# ===========================================================================

class NeuronaDeComunicacionPolicyGradient(NeuronaTest):
    """Policy Gradient con sincronización neuronal para sockets e intercambio.

    Hereda de ``NeuronaTest`` (todos los conflictos C1-C6 ya resueltos).
    Añade protocolo JSON para otros lenguajes y trama binaria (cabecera RFPG)
    para transferir pesos sin pérdida de formato.  Permite sincronizar pesos
    entre procesos (cliente/servidor) y fusionarlos de forma ponderada.
    """

    PROTOCOLO = "RFEN1-PG/1.0"
    MAGIC     = b"RFPG"

    def __init__(
        self,
        input_size: int,
        output_size: int,
        nombre: str = "NeuronaDeComunicacionPolicyGradient",
        learning_rate: float = 0.001,
        gamma: float = 0.99,
        usar_ortogonal: bool = True,
        entropy_coef: float = 0.01,
        grad_clip: float = 5.0,
        usar_baseline: bool = True,
        semilla: int = 42,
        capacidad_historial: int = 512,
    ):
        super().__init__(
            input_size=input_size, output_size=output_size, nombre=nombre,
            learning_rate=learning_rate, gamma=gamma,
            usar_ortogonal=usar_ortogonal, entropy_coef=entropy_coef,
            grad_clip=grad_clip, usar_baseline=usar_baseline,
            semilla=semilla, capacidad_historial=capacidad_historial,
        )

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------
    def paquete_estado(self) -> Dict[str, Any]:
        return {
            'protocolo'    : self.PROTOCOLO,
            'input_size'   : self.input_size,
            'output_size'  : self.output_size,
            'nombre'       : self.nombre,
            'learning_rate': self.learning_rate,
            'gamma'        : self.gamma,
            'entropy_coef' : self.entropy_coef,
            'grad_clip'    : self.grad_clip,
            'usar_baseline': self.usar_baseline,
            'usar_ortogonal': self.usar_ortogonal,
            'pasos'        : self.pasos,
            'pesos'        : self.pesos.tolist() if self.pesos is not None else None,
            'sesgo'        : self.sesgo.tolist() if self.sesgo is not None else None,
            'estadisticas' : dict(self.estadisticas_pg),
        }

    @classmethod
    def esquema_intercambio(cls) -> Dict[str, Any]:
        return {
            'protocolo': cls.PROTOCOLO,
            'formato_json': {
                'pesos'   : 'lista [input_size][output_size] de float (C-order)',
                'sesgo'   : 'lista [1][output_size] de float',
                'enteros' : 'input_size, output_size, pasos',
                'flotantes': 'learning_rate, gamma, entropy_coef, grad_clip',
                'booleanos': 'usar_baseline, usar_ortogonal',
            },
            'formato_binario': {
                'magic'    : cls.MAGIC.decode('ascii'),
                'cabecera' : '4 bytes magic + uint32 BE len(header) + uint32 BE len(vector)',
                'header'   : 'JSON UTF-8 con dimensiones e hiperparámetros',
                'vector'   : 'float32 LE, pesos (input_size*output_size) seguidos de sesgo',
            },
            'socket': 'frames con prefijo uint32 BE con la longitud del payload',
        }

    def exportar_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.paquete_estado(), indent=indent)

    def importar_json(self, texto: str) -> "NeuronaDeComunicacionPolicyGradient":
        d = json.loads(texto)
        self._validar_dimensiones(d.get('input_size'), d.get('output_size'))
        self.nombre        = str(d.get('nombre', self.nombre))
        self.learning_rate = float(d.get('learning_rate', self.learning_rate))
        self.gamma         = float(d.get('gamma', self.gamma))
        self.entropy_coef  = float(d.get('entropy_coef', self.entropy_coef))
        self.grad_clip     = float(d.get('grad_clip', self.grad_clip))
        self.usar_baseline = bool(d.get('usar_baseline', self.usar_baseline))
        self.usar_ortogonal= bool(d.get('usar_ortogonal', self.usar_ortogonal))
        self.pasos         = int(d.get('pasos', self.pasos))
        if d.get('pesos') is not None:
            pesos = np.asarray(d['pesos'], dtype=_dt())
            if pesos.shape != (self.input_size, self.output_size):
                raise ValueError(
                    f"forma de pesos {pesos.shape} != {(self.input_size, self.output_size)}"
                )
            self.pesos = np.ascontiguousarray(pesos)
        if d.get('sesgo') is not None:
            sesgo = np.asarray(d['sesgo'], dtype=_dt())
            if sesgo.size != self.output_size:
                raise ValueError(f"sesgo de {sesgo.size} != output {self.output_size}")
            self.sesgo = np.ascontiguousarray(sesgo.reshape(1, self.output_size))
        if d.get('estadisticas') is not None:
            for clave, valor in d['estadisticas'].items():
                if clave in self.estadisticas_pg:
                    self.estadisticas_pg[clave] = valor
        return self

    @classmethod
    def desde_json(cls, texto: str) -> "NeuronaDeComunicacionPolicyGradient":
        d   = json.loads(texto)
        obj = cls(int(d['input_size']), int(d['output_size']),
                  nombre=d.get('nombre', 'NeuronaDeComunicacionPolicyGradient'))
        return obj.importar_json(texto)

    def a_bytes(self) -> bytes:
        if self.pesos is None or self.sesgo is None:
            raise ValueError("Pesos no inicializados")
        vector = np.concatenate([
            self.pesos.ravel(order='C'),
            self.sesgo.ravel(order='C'),
        ]).astype(np.float32)
        header = json.dumps({
            'protocolo': self.PROTOCOLO, 'input_size': self.input_size,
            'output_size': self.output_size, 'nombre': self.nombre,
            'learning_rate': self.learning_rate, 'gamma': self.gamma,
            'entropy_coef': self.entropy_coef, 'grad_clip': self.grad_clip,
            'usar_baseline': self.usar_baseline, 'usar_ortogonal': self.usar_ortogonal,
            'pasos': self.pasos,
        }).encode('utf-8')
        return self.MAGIC + struct.pack(">II", len(header), vector.size) + header + vector.tobytes()

    @classmethod
    def desde_bytes(cls, data: bytes) -> "NeuronaDeComunicacionPolicyGradient":
        if data[:4] != cls.MAGIC:
            raise ValueError("cabecera binaria desconocida")
        len_header, n_vector = struct.unpack(">II", data[4:12])
        header  = json.loads(data[12:12 + len_header].decode('utf-8'))
        obj     = cls(int(header['input_size']), int(header['output_size']),
                      nombre=header.get('nombre', 'NeuronaDeComunicacionPolicyGradient'))
        obj.importar_json(json.dumps({**header, 'pesos': None, 'sesgo': None}))
        inicio  = 12 + len_header
        vector  = np.frombuffer(data[inicio:inicio + 4 * n_vector], dtype=np.float32)
        n_pesos = obj.input_size * obj.output_size
        if vector.size != n_pesos + obj.output_size:
            raise ValueError(
                f"vector de {vector.size} != esperado {n_pesos + obj.output_size}"
            )
        obj.pesos = np.ascontiguousarray(
            vector[:n_pesos].reshape(obj.input_size, obj.output_size), dtype=_dt()
        )
        obj.sesgo = np.ascontiguousarray(
            vector[n_pesos:].reshape(1, obj.output_size), dtype=_dt()
        )
        return obj

    # ------------------------------------------------------------------
    # Sincronización neuronal
    # ------------------------------------------------------------------
    def _validar_dimensiones(self, input_size: Any, output_size: Any) -> None:
        if input_size is None or output_size is None:
            return
        if int(input_size) != self.input_size or int(output_size) != self.output_size:
            raise ValueError("dimensiones incompatibles entre neuronas")

    def fusionar(
        self,
        otra: "NeuronaRefuerzoPolicyGradient",
        peso: float = 0.5,
    ) -> "NeuronaDeComunicacionPolicyGradient":
        """Mezcla los pesos propios con los de otra neurona (0 = intacta, 1 = copia)."""
        self._asegurar()
        self._validar_dimensiones(otra.input_size, otra.output_size)
        if otra.pesos is None or otra.sesgo is None:
            raise ValueError("la neurona remota no tiene pesos")
        if self.pesos.shape != otra.pesos.shape or self.sesgo.shape != otra.sesgo.shape:
            raise ValueError("formas de pesos o sesgo incompatibles")
        w = float(np.clip(peso, 0.0, 1.0))
        self.pesos = np.ascontiguousarray(
            ((1.0 - w) * self.pesos.astype(np.float64)
             + w * otra.pesos.astype(np.float64)).astype(_dt())
        )
        self.sesgo = np.ascontiguousarray(
            ((1.0 - w) * self.sesgo.astype(np.float64)
             + w * otra.sesgo.astype(np.float64)).astype(_dt())
        )
        return self

    @classmethod
    def promedio_federado(
        cls,
        neuronas: List["NeuronaRefuerzoPolicyGradient"],
        pesos: Optional[List[float]] = None,
        nombre: Optional[str] = None,
    ) -> "NeuronaDeComunicacionPolicyGradient":
        """Promedio ponderado de varias neuronas (sincronización federada)."""
        if not neuronas:
            raise ValueError("se requiere al menos una neurona")
        ref = neuronas[0]; ref._asegurar()
        w   = (np.full(len(neuronas), 1.0 / len(neuronas)) if pesos is None
               else np.asarray(pesos, dtype=np.float64) / max(1e-12, float(np.sum(pesos))))
        nueva     = cls(ref.input_size, ref.output_size,
                        nombre=nombre or (str(ref.nombre) + "::federada"))
        pesos_acc = np.zeros_like(ref.pesos, dtype=np.float64)
        sesgo_acc = np.zeros_like(ref.sesgo, dtype=np.float64)
        for wi, neu in zip(w, neuronas):
            if neu.pesos is None or neu.sesgo is None:
                raise ValueError("todas las neuronas deben tener pesos")
            if neu.pesos.shape != ref.pesos.shape or neu.sesgo.shape != ref.sesgo.shape:
                raise ValueError("formas de pesos incompatibles")
            pesos_acc += wi * neu.pesos.astype(np.float64)
            sesgo_acc += wi * neu.sesgo.astype(np.float64)
        nueva.pesos = np.ascontiguousarray(pesos_acc.astype(_dt()))
        nueva.sesgo = np.ascontiguousarray(sesgo_acc.astype(_dt()))
        return nueva

    # ------------------------------------------------------------------
    # Transporte por sockets (frames con prefijo de longitud uint32 BE)
    # ------------------------------------------------------------------
    @staticmethod
    def _enviar_frame(sock: socket.socket, payload: bytes) -> int:
        sock.sendall(struct.pack(">I", len(payload)) + payload)
        return 4 + len(payload)

    @staticmethod
    def _recibir_exacto(sock: socket.socket, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            trozo = sock.recv(n - len(buf))
            if not trozo:
                raise ConnectionError("socket cerrado antes de completar el frame")
            buf.extend(trozo)
        return bytes(buf)

    @classmethod
    def _recibir_frame(cls, sock: socket.socket) -> bytes:
        (n,) = struct.unpack(">I", cls._recibir_exacto(sock, 4))
        return cls._recibir_exacto(sock, n)

    @staticmethod
    def conectar(host: str, puerto: int, timeout: float = 5.0) -> socket.socket:
        return socket.create_connection((host, int(puerto)), timeout=timeout)

    @staticmethod
    def escuchar(host: str, puerto: int, backlog: int = 1) -> socket.socket:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, int(puerto)))
        srv.listen(backlog)
        return srv

    def enviar_estado(self, sock: socket.socket, formato: str = "json") -> int:
        payload = (self.exportar_json().encode('utf-8') if formato == "json"
                   else self.a_bytes())
        return self._enviar_frame(sock, payload)

    @classmethod
    def recibir_estado(
        cls, sock: socket.socket, formato: str = "json"
    ) -> "NeuronaDeComunicacionPolicyGradient":
        payload = cls._recibir_frame(sock)
        return cls.desde_json(payload.decode('utf-8')) if formato == "json" else cls.desde_bytes(payload)

    def sincronizar_socket(
        self, sock: socket.socket, formato: str = "json", fusion: float = 0.5
    ) -> Dict[str, Any]:
        """Rol cliente: envía el estado, recibe el del par y fusiona."""
        self.enviar_estado(sock, formato)
        self.fusionar(self.recibir_estado(sock, formato), fusion)
        return self.obtener_estadisticas_pg()

    def servir_sincronizacion(
        self, sock: socket.socket, formato: str = "json", fusion: float = 0.5
    ) -> Dict[str, Any]:
        """Rol servidor: recibe el estado del par, fusiona y responde."""
        self.fusionar(self.recibir_estado(sock, formato), fusion)
        self.enviar_estado(sock, formato)
        return self.obtener_estadisticas_pg()


# ---------------------------------------------------------------------------
__all__ = [
    # Importados desde RFEN1_RN_2.py (líneas 89-333)
    "_Ring",
    "_dt",
    "InicializadoresRL",
    "NeuronaRefuerzoBase",
    "NeuronaRefuerzoPolicyGradient",
    # Definidos en este archivo
    "NeuronaTest",
    "NeuronaDeComunicacionPolicyGradient",
]
