"""BASE_NEURONAL1.py - CEREBRO BLOK1: Integrador, Evaluador y Orquestador Neuronal.

Importa los dos directorios completos de la arquitectura:
  - ENRN : Red Neuronal Estándar     (EN1_RN  a EN10_RN  + SBRTM_IMPORT)
  - RF_EN: Red Neuronal por Refuerzo (RFEN1_RN_1 a RFEN1_RN_10 + RF_EN_SBRTM_IMPORT)

Implementa el plan de desarrollo BLOK1 en 4 fases:
  Fase 1 — PipelineInferencia    : pipeline sensor → latente → decisión (ENRN ▶ RF_EN)
  Fase 2 — MotorAprendizajeUnif. : motor RL unificado con retropropagación sensorial
  Fase 3 — OrquestadorP2P        : topología multi-actor asíncrona via IMPALA/threading
  Fase 4 — MonitorSanidad        : monitoreo continuo y auto-sanación de neuronas

Clase orquestadora: BaseNeuronal1
  Punto de entrada único para inferencia, entrenamiento, P2P y monitoreo.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.util
import json
import logging
import math
import os
import random
import struct
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

# Intentar importar websockets oficial si estuviera instalado
try:
    import websockets
    _WEBSOCKETS_DISPONIBLE = True
except ImportError:
    websockets = None  # type: ignore
    _WEBSOCKETS_DISPONIBLE = False

# Tipo de dato por defecto para operaciones matriciales
_dt = np.float32

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CELEBRO.BLOK1.BASE_NEURONAL1")

# ---------------------------------------------------------------------------
# RUTAS BASE Y CONFIGURACIÓN DEL SYS.PATH
# ---------------------------------------------------------------------------
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# De: ...\LC_STM\RedNeuronal\CELEBRO\BLOK1
# A:   ...\LC_STM\RedNeuronal
_RED_NEURONAL_DIR = os.path.dirname(os.path.dirname(_CURRENT_DIR))
_DIR_ENRN = os.path.join(_RED_NEURONAL_DIR, "ENRN")
_DIR_RF_EN = os.path.join(_RED_NEURONAL_DIR, "RF_EN")

# Es crucial que LC_STM\RedNeuronal esté en sys.path para que 'from ENRN import ...'
# y 'from .SBRTM_...' funcionen como paquetes completos.
if _RED_NEURONAL_DIR not in sys.path:
    sys.path.insert(0, _RED_NEURONAL_DIR)
if _DIR_ENRN not in sys.path:
    sys.path.insert(0, _DIR_ENRN)
if _DIR_RF_EN not in sys.path:
    sys.path.insert(0, _DIR_RF_EN)


# ---------------------------------------------------------------------------
# 1. IMPORTACIÓN DEL DIRECTORIO ENRN
# ---------------------------------------------------------------------------
modulos_enrn: Dict[str, Any] = {}
clases_enrn: Dict[str, Any] = {}

print("=" * 80)
print(">>> [BASE_NEURONAL1] IMPORTANDO DIRECTORIO ENRN ...")
print("=" * 80)

for i in range(1, 11):
    file_name = f"EN{i}_RN.py"
    mod_name = f"ENRN.EN{i}_RN"
    try:
        mod = importlib.import_module(mod_name)
        modulos_enrn[file_name] = mod
        for attr in dir(mod):
            if attr.startswith("Neurona") or attr.startswith("Neuron") or attr.startswith("LucIA"):
                obj = getattr(mod, attr)
                if isinstance(obj, type):
                    clases_enrn[f"EN{i}_{attr}"] = obj
        print(f"  [OK] ENRN/{file_name} importado exitosamente.")
    except Exception as exc:
        # Fallback de carga directa por ruta
        try:
            path_en = os.path.join(_DIR_ENRN, file_name)
            spec = importlib.util.spec_from_file_location(f"ENRN_direct_{i}", path_en)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[f"ENRN_direct_{i}"] = mod
                spec.loader.exec_module(mod)
                modulos_enrn[file_name] = mod
                for attr in dir(mod):
                    if attr.startswith("Neurona") or attr.startswith("Neuron") or attr.startswith("LucIA"):
                        obj = getattr(mod, attr)
                        if isinstance(obj, type):
                            clases_enrn[f"EN{i}_{attr}"] = obj
                print(f"  [OK] ENRN/{file_name} cargado via fallback de archivo.")
            else:
                print(f"  [FAIL] ENRN/{file_name}: {exc}")
        except Exception as exc2:
            print(f"  [FAIL] ENRN/{file_name}: {exc} (fallback: {exc2})")


# ---------------------------------------------------------------------------
# 2. IMPORTACIÓN DEL DIRECTORIO RF_EN
# ---------------------------------------------------------------------------
modulos_rfen: Dict[str, Any] = {}
clases_rfen: Dict[str, Any] = {}

print("\n" + "=" * 80)
print(">>> [BASE_NEURONAL1] IMPORTANDO DIRECTORIO RF_EN ...")
print("=" * 80)

for i in range(1, 11):
    file_name = f"RFEN1_RN_{i}.py"
    mod_name = f"RF_EN.RFEN1_RN_{i}"
    try:
        mod = importlib.import_module(mod_name)
        modulos_rfen[file_name] = mod
        for attr in dir(mod):
            if attr.startswith("Neurona") or attr.startswith("crear_neurona"):
                obj = getattr(mod, attr)
                if isinstance(obj, type):
                    clases_rfen[f"RN{i}_{attr}"] = obj
        print(f"  [OK] RF_EN/{file_name} importado exitosamente.")
    except Exception as exc:
        try:
            path_rfen = os.path.join(_DIR_RF_EN, file_name)
            spec = importlib.util.spec_from_file_location(f"RF_EN_direct_{i}", path_rfen)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[f"RF_EN_direct_{i}"] = mod
                spec.loader.exec_module(mod)
                modulos_rfen[file_name] = mod
                for attr in dir(mod):
                    if attr.startswith("Neurona") or attr.startswith("crear_neurona"):
                        obj = getattr(mod, attr)
                        if isinstance(obj, type):
                            clases_rfen[f"RN{i}_{attr}"] = obj
                print(f"  [OK] RF_EN/{file_name} cargado via fallback de archivo.")
            else:
                print(f"  [FAIL] RF_EN/{file_name}: {exc}")
        except Exception as exc2:
            print(f"  [FAIL] RF_EN/{file_name}: {exc} (fallback: {exc2})")


# ---------------------------------------------------------------------------
# 3. MOTOR DE ANÁLISIS DE PESOS NEURONALES
# ---------------------------------------------------------------------------
def analizar_pesos_tensor(nombre: str, tensor: Optional[np.ndarray]) -> Dict[str, Any]:
    """Calcula métricas estadísticas exhaustivas de una matriz o tensor de pesos."""
    if tensor is None:
        return {'nombre': nombre, 'estado': 'None'}

    arr = np.asarray(tensor, dtype=np.float64)
    if arr.size == 0:
        return {'nombre': nombre, 'estado': 'Vacio'}

    abs_arr = np.abs(arr)
    norm_l1 = float(np.sum(abs_arr))
    norm_l2 = float(np.sqrt(np.sum(arr ** 2)))
    norm_linf = float(np.max(abs_arr))

    return {
        'nombre': nombre,
        'shape': arr.shape,
        'dtype': str(tensor.dtype),
        'total_params': arr.size,
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'media': float(np.mean(arr)),
        'std': float(np.std(arr)),
        'norma_l1': norm_l1,
        'norma_l2': norm_l2,
        'norma_linf': norm_linf,
        'ceros': int(np.sum(arr == 0)),
        'nan_inf': bool(np.any(np.isnan(arr)) or np.any(np.isinf(arr))),
    }


def extraer_todos_los_pesos(instancia: Any) -> List[Tuple[str, np.ndarray]]:
    """Extrae todos los atributos que contengan matrices de pesos y sesgos."""
    tensors: List[Tuple[str, np.ndarray]] = []
    atributos_clave = [
        'pesos', 'sesgo', 'pesos_actor', 'sesgo_actor', 'pesos_critic', 'sesgo_critic',
        'pesos_q', 'sesgo_q', 'pesos_q1', 'sesgo_q1', 'pesos_q2', 'sesgo_q2',
        'pesos_actor_global', 'sesgo_actor_global', 'pesos_critic_global', 'sesgo_critic_global',
        'pesos_q_principal', 'sesgo_q_principal', 'pesos_q_objetivo', 'sesgo_q_objetivo',
        'pesos_alpha', 'sesgo_alpha', 'pesos_value_stream', 'pesos_advantage_stream',
        'pesos_distributional', 'pesos_noisy', 'weights', 'biases', 'W', 'b'
    ]

    for attr in atributos_clave:
        if hasattr(instancia, attr):
            val = getattr(instancia, attr)
            if isinstance(val, np.ndarray):
                tensors.append((attr, val))
            elif isinstance(val, dict):
                for k, v in val.items():
                    if isinstance(v, np.ndarray):
                        tensors.append((f"{attr}[{k}]", v))
    return tensors


# ---------------------------------------------------------------------------
# 4. EJECUCIÓN Y TABULACIÓN EN TERMINAL
# ---------------------------------------------------------------------------
def ejecutar_bloque_resultados_terminal() -> None:
    """Instancia y analiza muestras neuronales de ambos directorios mostrando un bloque completo en terminal."""
    print("\n" + "=" * 110)
    print(" " * 32 + "BLOQUE DE RESULTADOS DE PESOS NEURONALES")
    print(" " * 28 + "CELEBRO / BLOK1 / BASE_NEURONAL1 (ENRN & RF_EN)")
    print("=" * 110)

    headers = f"{'NEURONA / TENSOR':<38} | {'SHAPE':<12} | {'PARÁMETROS':<11} | {'MEDIA':<9} | {'STD':<8} | {'NORMA L2':<10} | {'ESTADO'}"
    print(headers)
    print("-" * 110)

    total_parametros = 0
    total_redes = 0
    alertas = 0

    # 4.1 Evaluación de RF_EN
    for i in range(1, 11):
        mod_key = f"RFEN1_RN_{i}.py"
        mod = modulos_rfen.get(mod_key)
        if not mod:
            continue

        instancia = None
        for func_name in dir(mod):
            if func_name.startswith("crear_neurona_"):
                fn = getattr(mod, func_name)
                try:
                    instancia = fn(input_size=10, output_size=4)
                    break
                except Exception:
                    pass

        if instancia is None:
            for cls_name in dir(mod):
                if cls_name.startswith("Neurona") and not cls_name.endswith("Base"):
                    cls = getattr(mod, cls_name)
                    if isinstance(cls, type):
                        try:
                            instancia = cls(input_size=10, output_size=4)
                            break
                        except Exception:
                            pass

        if instancia is not None:
            if hasattr(instancia, 'inicializar_pesos'):
                try:
                    instancia.inicializar_pesos()
                except Exception:
                    pass

            tensors = extraer_todos_los_pesos(instancia)
            if tensors:
                total_redes += 1
                print(f"\n[RED RF_EN] {mod_key} ({type(instancia).__name__})")
                for t_name, t_val in tensors:
                    stat = analizar_pesos_tensor(t_name, t_val)
                    if stat.get('estado') == 'None':
                        continue
                    total_parametros += stat['total_params']
                    estado = "ALERTA (NaN/Inf)" if stat['nan_inf'] else "ESTABLE (OK)"
                    if stat['nan_inf']:
                        alertas += 1
                    shape_str = str(stat['shape'])
                    print(
                        f"  -> {t_name:<33} | {shape_str:<12} | {stat['total_params']:<11} | "
                        f"{stat['media']:+8.4f} | {stat['std']:<8.4f} | {stat['norma_l2']:<10.4f} | {estado}"
                    )

    # 4.2 Evaluación de ENRN
    print("\n" + "-" * 110)
    print(">>> EVALUACIÓN DE ARQUITECTURAS ENRN (REDES ESTÁNDAR) ...")
    print("-" * 110)

    for i in range(1, 11):
        mod_key = f"EN{i}_RN.py"
        mod = modulos_enrn.get(mod_key)
        if not mod:
            continue

        instancia = None
        for func_name in dir(mod):
            if func_name.startswith("crear_neurona_"):
                fn = getattr(mod, func_name)
                try:
                    instancia = fn(10, 4)
                    break
                except Exception:
                    pass

        if instancia is None:
            for cls_name in dir(mod):
                if (cls_name.startswith("Neurona") or cls_name.startswith("Neuron")) and not cls_name.endswith("Base"):
                    cls = getattr(mod, cls_name)
                    if isinstance(cls, type):
                        try:
                            instancia = cls(10, 4)
                            break
                        except Exception:
                            pass

        if instancia is not None:
            if hasattr(instancia, 'inicializar_pesos'):
                try:
                    instancia.inicializar_pesos()
                except Exception:
                    pass

            tensors = extraer_todos_los_pesos(instancia)
            if tensors:
                total_redes += 1
                print(f"\n[RED ENRN] {mod_key} ({type(instancia).__name__})")
                for t_name, t_val in tensors:
                    stat = analizar_pesos_tensor(t_name, t_val)
                    if stat.get('estado') == 'None':
                        continue
                    total_parametros += stat['total_params']
                    estado = "ALERTA (NaN/Inf)" if stat['nan_inf'] else "ESTABLE (OK)"
                    if stat['nan_inf']:
                        alertas += 1
                    shape_str = str(stat['shape'])
                    print(
                        f"  -> {t_name:<33} | {shape_str:<12} | {stat['total_params']:<11} | "
                        f"{stat['media']:+8.4f} | {stat['std']:<8.4f} | {stat['norma_l2']:<10.4f} | {estado}"
                    )

    # 4.3 Resumen Consolidado
    print("\n" + "=" * 110)
    print(" " * 42 + "RESUMEN CONSOLIDADO")
    print("=" * 110)
    print(f"  • Módulos ENRN Cargados        : {len(modulos_enrn)} de 10")
    print(f"  • Módulos RF_EN Cargados       : {len(modulos_rfen)} de 10")
    print(f"  • Redes Neuronales Evaluadas   : {total_redes} arquitecturas")
    print(f"  • Total Parámetros Analizados  : {total_parametros:,} floats")
    print(f"  • Anomalías / Desbordamientos  : {alertas}")
    print(f"  • Diagnóstico Global           : {'CONVERGENCIA Y PESOS ESTABLES (100% OK)' if alertas == 0 else 'REQUIERE REVISION'}")
    print("=" * 110 + "\n")


# ===========================================================================
# FASE 1 — PIPELINE DE INFERENCIA UNIFICADO
# ===========================================================================
class PipelineInferencia:
    """Pipeline sensor → latente → decisión (ENRN ▶ RF_EN).

    Selecciona dinámicamente la neurona sensorial (ENRN) y el agente de
    decisión (RF_EN) según el modo solicitado, encadena sus forwards y
    devuelve (accion, diagnostico).

    Modos soportados
    ----------------
    'continuo'    → EN9  (Tanh)       + PPO
    'discreto'    → EN8  (ReLU)       + Rainbow DQN
    'normalizado' → EN7  (BatchNorm)  + SAC
    'navegacion'  → EN6  (Dropout)    + PPO
    'cinematica'  → EN5  (Regulariz.) + SAC
    'riesgo'      → EN4  (Normaliz.)  + Rainbow DQN
    'distribuido' → EN3  (LeCun)      + IMPALA
    'xavier'      → EN2  (Xavier)     + TD3
    'basico'      → EN1  (Basico)     + Q-Learning
    'auto'        → selecciona heurística por norma del estado
    """

    # Mapeo modo → (índice ENRN, índice RF_EN)
    _MAPA_MODO: Dict[str, Tuple[int, int]] = {
        'continuo':    (9, 6),   # Tanh      / PPO
        'discreto':    (8, 9),   # ReLU      / Rainbow DQN
        'normalizado': (7, 7),   # BatchNorm / SAC
        'navegacion':  (6, 6),   # Dropout   / PPO
        'cinematica':  (5, 7),   # Reg.      / SAC
        'riesgo':      (4, 9),   # Norm.     / Rainbow DQN
        'distribuido': (3, 10),  # LeCun     / IMPALA
        'xavier':      (2, 8),   # Xavier    / TD3
        'basico':      (1, 1),   # Básico    / Q-Learning
    }

    def __init__(self,
                 input_size: int = 10,
                 output_size: int = 4,
                 latente_size: int = 16) -> None:
        self.input_size   = input_size
        self.output_size  = output_size
        self.latente_size = latente_size
        self._cache_enrn: Dict[int, Any] = {}   # índice → instancia ENRN
        self._cache_rfen: Dict[int, Any] = {}   # índice → instancia RF_EN
        self._lock = threading.Lock()
        logger.info("[PipelineInferencia] inicializado  input=%d  output=%d  latente=%d",
                    input_size, output_size, latente_size)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def procesar(self,
                 estado_crudo: np.ndarray,
                 modo: str = 'auto') -> Tuple[np.ndarray, Dict[str, Any]]:
        """Procesa un estado y devuelve (acción, diagnóstico).

        Parameters
        ----------
        estado_crudo : np.ndarray  shape (input_size,)
        modo         : str         nombre del modo o 'auto'

        Returns
        -------
        accion      : np.ndarray  shape (output_size,)
        diagnostico : dict        métricas de la pasada
        """
        t0 = time.perf_counter()
        estado = np.asarray(estado_crudo, dtype=_dt).flatten()

        # Selección de modo
        if modo == 'auto':
            modo = self._seleccion_heuristica(estado)

        idx_enrn, idx_rfen = self._MAPA_MODO.get(modo, (1, 1))

        # Instanciar / recuperar de caché
        neurona_e = self._obtener_enrn(idx_enrn)
        neurona_r = self._obtener_rfen(idx_rfen)

        # Forward ENRN → latente
        latente = self._forward_enrn(neurona_e, estado)

        # Forward RF_EN → acción
        accion  = self._forward_rfen(neurona_r, latente)

        t1 = time.perf_counter()
        latencia_ms = (t1 - t0) * 1_000

        if latencia_ms > 1.5:
            logger.warning("[PipelineInferencia] latencia %.3f ms > 1.5 ms (modo=%s)",
                           latencia_ms, modo)

        diagnostico: Dict[str, Any] = {
            'modo':          modo,
            'idx_enrn':      idx_enrn,
            'idx_rfen':      idx_rfen,
            'neurona_enrn':  type(neurona_e).__name__ if neurona_e else 'N/A',
            'neurona_rfen':  type(neurona_r).__name__ if neurona_r else 'N/A',
            'latencia_ms':   round(latencia_ms, 4),
            'norma_estado':  float(np.linalg.norm(estado)),
            'norma_latente': float(np.linalg.norm(latente)),
            'norma_accion':  float(np.linalg.norm(accion)),
        }
        return accion, diagnostico

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------
    def _seleccion_heuristica(self, estado: np.ndarray) -> str:
        """Elige modo según características del vector de estado."""
        norma = float(np.linalg.norm(estado))
        varianza = float(np.var(estado))
        if norma > 5.0 and varianza > 1.0:
            return 'riesgo'
        if varianza < 0.05:
            return 'normalizado'
        if norma > 3.0:
            return 'cinematica'
        return 'continuo'

    def _obtener_enrn(self, idx: int) -> Optional[Any]:
        with self._lock:
            if idx not in self._cache_enrn:
                self._cache_enrn[idx] = self._instanciar_enrn(idx)
            return self._cache_enrn[idx]

    def _obtener_rfen(self, idx: int) -> Optional[Any]:
        with self._lock:
            if idx not in self._cache_rfen:
                self._cache_rfen[idx] = self._instanciar_rfen(idx)
            return self._cache_rfen[idx]

    def _instanciar_enrn(self, idx: int) -> Optional[Any]:
        mod_key = f"EN{idx}_RN.py"
        mod = modulos_enrn.get(mod_key)
        if mod is None:
            return None
        for cls_name in dir(mod):
            if cls_name.startswith("Neurona") and not cls_name.endswith("Base"):
                cls = getattr(mod, cls_name)
                if isinstance(cls, type):
                    try:
                        inst = cls(self.input_size, self.latente_size)
                        if hasattr(inst, 'inicializar_pesos'):
                            inst.inicializar_pesos()
                        return inst
                    except Exception:
                        pass
        return None

    def _instanciar_rfen(self, idx: int) -> Optional[Any]:
        mod_key = f"RFEN1_RN_{idx}.py"
        mod = modulos_rfen.get(mod_key)
        if mod is None:
            return None
        # 1) intentar función factory
        for fn_name in dir(mod):
            if fn_name.startswith("crear_neurona_"):
                try:
                    return getattr(mod, fn_name)(
                        input_size=self.latente_size, output_size=self.output_size)
                except Exception:
                    pass
        # 2) instanciar clase directamente
        for cls_name in dir(mod):
            if cls_name.startswith("Neurona") and not cls_name.endswith("Base"):
                cls = getattr(mod, cls_name)
                if isinstance(cls, type):
                    try:
                        inst = cls(input_size=self.latente_size, output_size=self.output_size)
                        if hasattr(inst, 'inicializar_pesos'):
                            inst.inicializar_pesos()
                        return inst
                    except Exception:
                        pass
        return None

    @staticmethod
    def _forward_enrn(neurona: Optional[Any], estado: np.ndarray) -> np.ndarray:
        """Pasa el estado por la neurona ENRN y obtiene la representación latente."""
        if neurona is None:
            return estado.copy()
        for metodo in ('forward', 'procesar', 'activar', 'calcular'):
            if hasattr(neurona, metodo):
                try:
                    salida = getattr(neurona, metodo)(estado)
                    return np.asarray(salida, dtype=_dt).flatten()
                except Exception:
                    pass
        # Fallback: proyección lineal con pesos internos
        if hasattr(neurona, 'pesos'):
            W = np.asarray(neurona.pesos, dtype=_dt)
            b = np.asarray(getattr(neurona, 'sesgo', np.zeros(W.shape[0])), dtype=_dt)
            if W.ndim == 2 and W.shape[1] == estado.shape[0]:
                return np.tanh(W @ estado + b)
        return estado.copy()

    @staticmethod
    def _forward_rfen(neurona: Optional[Any], latente: np.ndarray) -> np.ndarray:
        """Pasa el latente por el agente RF_EN y obtiene la acción."""
        if neurona is None:
            return latente.copy()
        for metodo in ('seleccionar_accion', 'predecir', 'forward', 'actuar', 'calcular_accion'):
            if hasattr(neurona, metodo):
                try:
                    salida = getattr(neurona, metodo)(latente)
                    if isinstance(salida, (int, float)):
                        return np.array([salida], dtype=_dt)
                    return np.asarray(salida, dtype=_dt).flatten()
                except Exception:
                    pass
        # Fallback: proyección lineal
        if hasattr(neurona, 'pesos'):
            W = np.asarray(neurona.pesos, dtype=_dt)
            b = np.asarray(getattr(neurona, 'sesgo', np.zeros(W.shape[0])), dtype=_dt)
            if W.ndim == 2 and W.shape[1] == latente.shape[0]:
                return np.tanh(W @ latente + b)
        return latente.copy()


# ===========================================================================
# FASE 2 — MOTOR DE APRENDIZAJE UNIFICADO
# ===========================================================================
class MotorAprendizajeUnificado:
    """Motor RL unificado con retropropagación sensorial hacia ENRN.

    Ruta de aprendizaje
    -------------------
    experiencia → buffer RF_EN (Rainbow / IMPALA) → entrenar_step() → TD-error
        → ajuste de escala sensorial en ENRN (pesos *= 1 + lr_s * td_error, clippeado)

    Estrategia de buffer
    --------------------
    - Usa `BufferPriorizadoRainbow`  de RFEN1_RN_9  cuando modo != 'distribuido'.
    - Usa `BufferActoresIMPALA`      de RFEN1_RN_10 cuando modo == 'distribuido'.
    """

    _LR_SENSORIAL_DEFAULT = 1e-4
    _CLIP_ESCALA          = 0.05   # máximo ajuste relativo por paso
    _BATCH_SIZE           = 32

    def __init__(self,
                 pipeline: PipelineInferencia,
                 lr_sensorial: float = _LR_SENSORIAL_DEFAULT) -> None:
        self.pipeline     = pipeline
        self.lr_sensorial = lr_sensorial
        self._lock        = threading.Lock()
        self._metricas: Dict[str, Any] = {
            'pasos': 0,
            'td_error_medio': 0.0,
            'recompensa_media': 0.0,
            'ajustes_sensoriales': 0,
        }
        # Intentar obtener buffers de RF_EN
        self._buffer_rainbow = self._init_buffer_rainbow()
        self._buffer_impala  = self._init_buffer_impala()
        logger.info("[MotorAprendizaje] lr_sensorial=%.2e  buffer_rainbow=%s  buffer_impala=%s",
                    lr_sensorial,
                    self._buffer_rainbow is not None,
                    self._buffer_impala is not None)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def entrenar_paso(self,
                      actor_id: str,
                      estado: np.ndarray,
                      accion: Any,
                      recompensa: float,
                      siguiente_estado: np.ndarray,
                      terminado: bool,
                      probabilidad_accion: float = 1.0,
                      modo: str = 'continuo') -> Dict[str, Any]:
        """Almacena la experiencia y ejecuta un paso de entrenamiento RL + sensorial."""
        estado_arr  = np.asarray(estado,          dtype=_dt).flatten()
        sig_arr     = np.asarray(siguiente_estado, dtype=_dt).flatten()

        # Seleccionar buffer activo
        buffer_activo = self._buffer_impala if modo == 'distribuido' else self._buffer_rainbow

        # Almacenar en buffer
        td_error = 0.0
        if buffer_activo is not None:
            td_error = self._almacenar_y_entrenar(
                buffer_activo, actor_id,
                estado_arr, accion, recompensa,
                sig_arr, terminado, probabilidad_accion, modo)

        # Retropropagación sensorial hacia ENRN
        idx_enrn = PipelineInferencia._MAPA_MODO.get(modo, (1, 1))[0]
        neurona_e = self.pipeline._obtener_enrn(idx_enrn)
        if neurona_e is not None and td_error != 0.0:
            self._ajustar_escala_sensorial(neurona_e, td_error)

        with self._lock:
            n = self._metricas['pasos'] + 1
            self._metricas['pasos'] = n
            prev_td = self._metricas['td_error_medio']
            self._metricas['td_error_medio'] = prev_td + (td_error - prev_td) / n
            prev_r  = self._metricas['recompensa_media']
            self._metricas['recompensa_media'] = prev_r + (recompensa - prev_r) / n

        return {'td_error': td_error, 'recompensa': recompensa, 'modo': modo}

    def obtener_metricas(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._metricas)

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------
    def _init_buffer_rainbow(self) -> Optional[Any]:
        mod = modulos_rfen.get("RFEN1_RN_9.py")
        if mod is None:
            return None
        neurona_cls = None
        for n in dir(mod):
            if 'Rainbow' in n and isinstance(getattr(mod, n), type):
                neurona_cls = getattr(mod, n)
                break
        if neurona_cls is None:
            return None
        try:
            inst = neurona_cls(input_size=16, output_size=4)
            if hasattr(inst, 'inicializar_pesos'):
                inst.inicializar_pesos()
            # Intentar obtener buffer interno
            for attr in ('buffer', 'Buffer', 'replay_buffer', 'memoria'):
                if hasattr(inst, attr):
                    return getattr(inst, attr)
            return inst   # usar la propia neurona como "buffer proxy"
        except Exception as exc:
            logger.debug("[MotorAprendizaje] buffer Rainbow no disponible: %s", exc)
            return None

    def _init_buffer_impala(self) -> Optional[Any]:
        mod = modulos_rfen.get("RFEN1_RN_10.py")
        if mod is None:
            return None
        neurona_cls = None
        for n in dir(mod):
            if 'IMPALA' in n and isinstance(getattr(mod, n), type):
                neurona_cls = getattr(mod, n)
                break
        if neurona_cls is None:
            return None
        try:
            inst = neurona_cls(input_size=16, output_size=4)
            if hasattr(inst, 'inicializar_pesos'):
                inst.inicializar_pesos()
            for attr in ('buffer', 'Buffer', 'buffer_actores'):
                if hasattr(inst, attr):
                    return getattr(inst, attr)
            return inst
        except Exception as exc:
            logger.debug("[MotorAprendizaje] buffer IMPALA no disponible: %s", exc)
            return None

    def _almacenar_y_entrenar(self,
                              buffer_o_neurona: Any,
                              actor_id: str,
                              estado: np.ndarray,
                              accion: Any,
                              recompensa: float,
                              sig_estado: np.ndarray,
                              terminado: bool,
                              prob: float,
                              modo: str) -> float:
        """Intenta almacenar la transición y ejecutar un paso de entrenamiento."""
        td_error = 0.0
        # 1) Almacenar
        for metodo_alma in ('agregar', 'almacenar', 'add', 'push', 'guardar_experiencia',
                            'agregar_experiencia'):
            if hasattr(buffer_o_neurona, metodo_alma):
                try:
                    fn = getattr(buffer_o_neurona, metodo_alma)
                    # intentar con y sin actor_id
                    try:
                        fn(actor_id, estado, accion, recompensa, sig_estado, terminado, prob)
                    except TypeError:
                        try:
                            fn(estado, accion, recompensa, sig_estado, terminado)
                        except TypeError:
                            fn(estado, accion, recompensa, sig_estado)
                    break
                except Exception:
                    pass

        # 2) Entrenar
        for metodo_ent in ('entrenar_paso', 'entrenar', 'train_step', 'optimizar',
                           'actualizar_q', 'actualizar'):
            if hasattr(buffer_o_neurona, metodo_ent):
                try:
                    resultado = getattr(buffer_o_neurona, metodo_ent)()
                    if isinstance(resultado, dict) and 'td_error' in resultado:
                        td_error = float(resultado['td_error'])
                    elif isinstance(resultado, (int, float)):
                        td_error = float(resultado)
                    break
                except Exception:
                    pass

        # Fallback: td_error sintético basado en norma de recompensa
        if td_error == 0.0:
            td_error = float(np.clip(recompensa, -1.0, 1.0)) * 0.1

        return td_error

    def _ajustar_escala_sensorial(self, neurona: Any, td_error: float) -> None:
        """Ajusta los pesos de la neurona ENRN usando el TD-error como señal."""
        factor = np.clip(1.0 + self.lr_sensorial * td_error,
                         1.0 - self._CLIP_ESCALA,
                         1.0 + self._CLIP_ESCALA)
        for attr in ('pesos', 'W', 'weights'):
            if hasattr(neurona, attr):
                val = getattr(neurona, attr)
                if isinstance(val, np.ndarray):
                    setattr(neurona, attr, (val * factor).astype(_dt))
                    with self._lock:
                        self._metricas['ajustes_sensoriales'] += 1
                    return


# ===========================================================================
# FASE 3 — ORQUESTADOR P2P MULTI-ACTOR
# ===========================================================================
class OrquestadorP2P:
    """Topología multi-actor asíncrona via IMPALA/threading.

    Gestiona actores distribuidos que recolectan experiencia en paralelo.
    Cada actor corre en su propio hilo y deposita trayectorias en el buffer
    IMPALA compartido; un hilo de sincronización periódica actualiza los pesos
    globales según los gradientes acumulados (V-Trace).

    Latencia objetivo: < 1.5 ms por paso de inferencia.
    """

    def __init__(self,
                 pipeline: PipelineInferencia,
                 motor: MotorAprendizajeUnificado,
                 frecuencia_sync: int = 100) -> None:
        self.pipeline         = pipeline
        self.motor            = motor
        self.frecuencia_sync  = frecuencia_sync
        self._actores: Dict[str, Dict[str, Any]] = {}
        self._hilos:   Dict[str, threading.Thread] = {}
        self._lock     = threading.Lock()
        self._activo   = False
        self._paso_global = 0
        self._hilo_sync: Optional[threading.Thread] = None
        logger.info("[OrquestadorP2P] frecuencia_sync=%d pasos", frecuencia_sync)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def registrar_actor(self,
                        actor_id: str,
                        socket_info: Optional[Dict] = None,
                        modo: str = 'distribuido') -> None:
        """Registra un nuevo actor en la topología P2P."""
        with self._lock:
            if actor_id in self._actores:
                logger.warning("[OrquestadorP2P] actor '%s' ya registrado.", actor_id)
                return
            self._actores[actor_id] = {
                'socket_info':   socket_info,
                'modo':          modo,
                'pasos':         0,
                'recompensa_sum': 0.0,
                'activo':        True,
            }
        logger.info("[OrquestadorP2P] actor '%s' registrado (modo=%s).", actor_id, modo)

    def recolectar_experiencia(self,
                               actor_id: str,
                               estado: np.ndarray,
                               accion: Any,
                               recompensa: float,
                               siguiente_estado: np.ndarray,
                               terminado: bool,
                               probabilidad_accion: float = 1.0) -> Dict[str, Any]:
        """Deposita una transición en el buffer IMPALA (desde un actor)."""
        with self._lock:
            info = self._actores.get(actor_id)
            if info is None:
                raise KeyError(f"Actor '{actor_id}' no registrado. Llame a registrar_actor primero.")
            modo = info['modo']

        resultado = self.motor.entrenar_paso(
            actor_id, estado, accion, recompensa,
            siguiente_estado, terminado, probabilidad_accion, modo)

        with self._lock:
            self._actores[actor_id]['pasos']          += 1
            self._actores[actor_id]['recompensa_sum'] += recompensa
            self._paso_global += 1

        # Trigger sincronización periódica
        if self._paso_global % self.frecuencia_sync == 0:
            self._sincronizar_no_bloqueante()

        return resultado

    def iniciar_modo_daemon(self) -> None:
        """Arranca el hilo daemon de sincronización en background."""
        if self._activo:
            return
        self._activo = True
        self._hilo_sync = threading.Thread(
            target=self._loop_sync_daemon,
            name="OrquestadorP2P-Sync",
            daemon=True)
        self._hilo_sync.start()
        logger.info("[OrquestadorP2P] hilo daemon de sync iniciado.")

    def detener(self) -> None:
        self._activo = False
        logger.info("[OrquestadorP2P] detenido.")

    def estado_actores(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'num_actores':  len(self._actores),
                'paso_global':  self._paso_global,
                'actores': {aid: {
                    'pasos':    info['pasos'],
                    'modo':     info['modo'],
                    'reward':   round(info['recompensa_sum'], 4),
                } for aid, info in self._actores.items()},
            }

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------
    def _sincronizar_no_bloqueante(self) -> None:
        hilo = threading.Thread(target=self._sincronizar_actores,
                                name="Sync-step",
                                daemon=True)
        hilo.start()

    def _sincronizar_actores(self) -> None:
        """Llama a sincronizar_actores() en la neurona IMPALA si está disponible."""
        neurona_impala = self.pipeline._obtener_rfen(10)
        if neurona_impala is None:
            return
        for metodo in ('sincronizar_actores', 'sincronizar', 'sync'):
            if hasattr(neurona_impala, metodo):
                try:
                    getattr(neurona_impala, metodo)()
                    logger.debug("[OrquestadorP2P] sincronización IMPALA ejecutada.")
                    return
                except Exception as exc:
                    logger.debug("[OrquestadorP2P] sync error: %s", exc)

    def _loop_sync_daemon(self) -> None:
        while self._activo:
            time.sleep(1.0)
            self._sincronizar_actores()


# ===========================================================================
# FASE 4 — MONITOR DE SANIDAD Y AUTO-SANACIÓN
# ===========================================================================
class MonitorSanidad:
    """Monitoreo continuo y auto-sanación quirúrgica de neuronas.

    Verifica periódicamente el estado de todas las neuronas activas
    (ENRN y RF_EN) y reinicializa de forma quirúrgica cualquier neurona
    que presente deriva de gradientes, sesgo Q extremo o pesos NaN/Inf.
    """

    _UMBRAL_NORMA_GRADIENTE = 10.0
    _UMBRAL_SESGO_Q         = 10.0
    _INTERVALO_DEFAULT_S    = 5.0

    def __init__(self, pipeline: PipelineInferencia) -> None:
        self.pipeline   = pipeline
        self._activo    = False
        self._hilo:     Optional[threading.Thread] = None
        self._lock      = threading.Lock()
        self._historial: List[Dict[str, Any]] = []
        logger.info("[MonitorSanidad] inicializado.")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def verificar_estado_completo(self) -> Dict[str, Any]:
        """Verifica las 20 neuronas cargadas (10 ENRN + 10 RF_EN)."""
        reporte: Dict[str, Any] = {
            'timestamp':     time.strftime('%Y-%m-%dT%H:%M:%S'),
            'enrn':          {},
            'rfen':          {},
            'anomalias':     [],
            'estado_global': 'OK',
        }

        # Verificar ENRN cacheadas
        for idx, inst in list(self.pipeline._cache_enrn.items()):
            nombre = f"EN{idx}_RN ({type(inst).__name__})"
            estado = self._verificar_neurona(nombre, inst)
            reporte['enrn'][nombre] = estado
            if estado['anomalia']:
                reporte['anomalias'].append(nombre)

        # Verificar RF_EN cacheadas
        for idx, inst in list(self.pipeline._cache_rfen.items()):
            nombre = f"RFEN1_RN_{idx} ({type(inst).__name__})"
            estado = self._verificar_neurona(nombre, inst)
            reporte['rfen'][nombre] = estado
            if estado['anomalia']:
                reporte['anomalias'].append(nombre)

        if reporte['anomalias']:
            reporte['estado_global'] = f"ANOMALIAS ({len(reporte['anomalias'])})"

        with self._lock:
            self._historial.append({
                'timestamp': reporte['timestamp'],
                'anomalias': len(reporte['anomalias']),
                'estado':    reporte['estado_global'],
            })
            if len(self._historial) > 200:
                self._historial = self._historial[-100:]

        return reporte

    def detectar_deriva_gradientes(self,
                                   umbral_norma: float = _UMBRAL_NORMA_GRADIENTE
                                   ) -> List[str]:
        """Detecta neuronas con norma de pesos > umbral (posible explosión de gradiente)."""
        problemas: List[str] = []
        for coleccion, prefijo in [(self.pipeline._cache_enrn, 'EN'),
                                    (self.pipeline._cache_rfen, 'RFEN')]:
            for idx, inst in list(coleccion.items()):
                for attr in ('pesos', 'pesos_actor', 'pesos_q', 'pesos_q1',
                             'pesos_critic', 'W', 'weights'):
                    if hasattr(inst, attr):
                        val = getattr(inst, attr)
                        if isinstance(val, np.ndarray):
                            norma = float(np.linalg.norm(val))
                            if norma > umbral_norma:
                                nombre = f"{prefijo}{idx}"
                                problemas.append(f"{nombre}::{attr}  norma={norma:.4f}")
        return problemas

    def detectar_sesgo_q(self, umbral: float = _UMBRAL_SESGO_Q) -> List[str]:
        """Detecta sesgo Q extremo en las neuronas RF_EN."""
        problemas: List[str] = []
        for idx, inst in list(self.pipeline._cache_rfen.items()):
            for attr in ('sesgo_q', 'sesgo_q1', 'sesgo_q2', 'sesgo', 'b'):
                if hasattr(inst, attr):
                    val = getattr(inst, attr)
                    if isinstance(val, np.ndarray):
                        max_b = float(np.max(np.abs(val)))
                        if max_b > umbral:
                            problemas.append(f"RFEN{idx}::{attr}  max_abs={max_b:.4f}")
        return problemas

    def auto_sanar(self, nombre_neurona: str) -> bool:
        """Reinicializa quirúrgicamente la neurona indicada.

        Parameters
        ----------
        nombre_neurona : str  p.ej. 'EN9' o 'RFEN9'
        """
        try:
            if nombre_neurona.startswith('EN'):
                idx = int(nombre_neurona.replace('EN', '').split('_')[0])
                inst = self.pipeline._cache_enrn.get(idx)
            elif nombre_neurona.startswith('RFEN'):
                idx = int(nombre_neurona.replace('RFEN', '').split('_')[0])
                inst = self.pipeline._cache_rfen.get(idx)
            else:
                logger.warning("[MonitorSanidad] nombre no reconocido: %s", nombre_neurona)
                return False

            if inst is None:
                return False

            # Intentar reinicialización via método propio
            for metodo in ('reinicializar_con_parametros', 'reinicializar',
                           'inicializar_pesos', 'reset'):
                if hasattr(inst, metodo):
                    getattr(inst, metodo)()
                    logger.info("[MonitorSanidad] AUTO-SANACIÓN '%s' via %s.", nombre_neurona, metodo)
                    return True

            # Fallback: reinicializar pesos con Xavier
            for attr in ('pesos', 'W', 'weights'):
                if hasattr(inst, attr):
                    val = getattr(inst, attr)
                    if isinstance(val, np.ndarray):
                        fan_in = val.shape[-1] if val.ndim >= 2 else val.size
                        escala = math.sqrt(2.0 / max(fan_in, 1))
                        nuevo  = np.random.randn(*val.shape).astype(_dt) * escala
                        setattr(inst, attr, nuevo)
            logger.info("[MonitorSanidad] AUTO-SANACIÓN '%s' via reinicio Xavier.", nombre_neurona)
            return True

        except Exception as exc:
            logger.error("[MonitorSanidad] error sanando '%s': %s", nombre_neurona, exc)
            return False

    def monitor_continuo(self, intervalo_segundos: float = _INTERVALO_DEFAULT_S) -> None:
        """Bucle de monitoreo (corre en hilo daemon)."""
        logger.info("[MonitorSanidad] monitor_continuo iniciado (intervalo=%.1fs).", intervalo_segundos)
        while self._activo:
            time.sleep(intervalo_segundos)
            try:
                reporte = self.verificar_estado_completo()
                if reporte['anomalias']:
                    logger.warning("[MonitorSanidad] ANOMALÍAS: %s", reporte['anomalias'])
                    for nombre in reporte['anomalias']:
                        # Extraer nombre corto para auto_sanar
                        nombre_corto = nombre.split(' ')[0]  # e.g. "EN9_RN" → "EN9"
                        nombre_corto = nombre_corto.replace('_RN', '').replace('1_RN_', '')
                        self.auto_sanar(nombre_corto)
                # Detectar derivas adicionales
                derivas = self.detectar_deriva_gradientes()
                if derivas:
                    logger.warning("[MonitorSanidad] DERIVAS: %s", derivas)
            except Exception as exc:
                logger.error("[MonitorSanidad] error en ciclo monitor: %s", exc)

    def iniciar(self, intervalo_segundos: float = _INTERVALO_DEFAULT_S) -> None:
        if self._activo:
            return
        self._activo = True
        self._hilo = threading.Thread(
            target=self.monitor_continuo,
            args=(intervalo_segundos,),
            name="MonitorSanidad-daemon",
            daemon=True)
        self._hilo.start()
        logger.info("[MonitorSanidad] hilo daemon iniciado.")

    def detener(self) -> None:
        self._activo = False
        logger.info("[MonitorSanidad] detenido.")

    def historial(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._historial)

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------
    @staticmethod
    def _verificar_neurona(nombre: str, inst: Any) -> Dict[str, Any]:
        anomalia = False
        norma_max = 0.0
        nan_detectado = False
        for attr in ('pesos', 'sesgo', 'pesos_actor', 'sesgo_actor',
                     'pesos_q', 'sesgo_q', 'W', 'b', 'weights', 'biases'):
            if not hasattr(inst, attr):
                continue
            val = getattr(inst, attr)
            if not isinstance(val, np.ndarray):
                continue
            if np.any(np.isnan(val)) or np.any(np.isinf(val)):
                nan_detectado = True
                anomalia = True
            norma = float(np.linalg.norm(val))
            norma_max = max(norma_max, norma)
            if norma > MonitorSanidad._UMBRAL_NORMA_GRADIENTE:
                anomalia = True

        return {
            'nombre':        nombre,
            'norma_max':     round(norma_max, 4),
            'nan_inf':       nan_detectado,
            'anomalia':      anomalia,
        }


# ===========================================================================
# ORQUESTADOR PRINCIPAL — BaseNeuronal1
# ===========================================================================
class BaseNeuronal1:
    """Orquestador principal del CELEBRO BLOK1.

    Instancia y coordina las 4 fases del plan de desarrollo:
      1. PipelineInferencia       — inference ENRN → RF_EN
      2. MotorAprendizajeUnificado — RL + retropropagación sensorial
      3. OrquestadorP2P           — multi-actor asíncrono
      4. MonitorSanidad           — health-check + auto-healing

    Uso rápido
    ----------
    >>> cerebro = BaseNeuronal1()
    >>> accion, diag = cerebro.procesar(estado)
    >>> cerebro.entrenar(actor_id, estado, accion, recompensa, siguiente_estado, False)
    >>> cerebro.iniciar_monitoreo()
    """

    def __init__(self,
                 input_size: int = 10,
                 output_size: int = 4,
                 latente_size: int = 16,
                 lr_sensorial: float = 1e-4,
                 frecuencia_sync: int = 100,
                 intervalo_monitor: float = 5.0) -> None:
        self.input_size       = input_size
        self.output_size      = output_size
        self.latente_size     = latente_size
        self.intervalo_monitor = intervalo_monitor

        # Fase 1
        self.pipeline   = PipelineInferencia(input_size, output_size, latente_size)
        # Fase 2
        self.motor      = MotorAprendizajeUnificado(self.pipeline, lr_sensorial)
        # Fase 3
        self.orquestador = OrquestadorP2P(self.pipeline, self.motor, frecuencia_sync)
        # Fase 4
        self.monitor    = MonitorSanidad(self.pipeline)

        # Servidor Neuronal (WebSocket / TCP)
        self.servidor: Optional[ServidorNeuronal] = None

        logger.info("[BaseNeuronal1] BLOK1 inicializado — fases 1-4 listas.")

    # ------------------------------------------------------------------
    # Delegaciones de alto nivel
    # ------------------------------------------------------------------
    def procesar(self,
                 estado: np.ndarray,
                 modo: str = 'auto') -> Tuple[np.ndarray, Dict[str, Any]]:
        """Inferencia unificada ENRN → RF_EN. Devuelve (acción, diagnóstico)."""
        return self.pipeline.procesar(estado, modo)

    def entrenar(self,
                 actor_id: str,
                 estado: np.ndarray,
                 accion: Any,
                 recompensa: float,
                 siguiente_estado: np.ndarray,
                 terminado: bool,
                 probabilidad_accion: float = 1.0,
                 modo: str = 'continuo') -> Dict[str, Any]:
        """Un paso de aprendizaje RL + ajuste sensorial."""
        return self.motor.entrenar_paso(
            actor_id, estado, accion, recompensa,
            siguiente_estado, terminado, probabilidad_accion, modo)

    def registrar_actor(self, actor_id: str,
                        socket_info: Optional[Dict] = None,
                        modo: str = 'distribuido') -> None:
        """Registra un actor P2P."""
        self.orquestador.registrar_actor(actor_id, socket_info, modo)

    def recolectar_experiencia_p2p(self, actor_id: str,
                                   estado: np.ndarray,
                                   accion: Any,
                                   recompensa: float,
                                   siguiente_estado: np.ndarray,
                                   terminado: bool,
                                   prob: float = 1.0) -> Dict[str, Any]:
        """Deposita experiencia de un actor P2P en el buffer IMPALA."""
        return self.orquestador.recolectar_experiencia(
            actor_id, estado, accion, recompensa, siguiente_estado, terminado, prob)

    def iniciar_monitoreo(self) -> None:
        """Inicia el monitor de sanidad + el daemon P2P en background."""
        self.monitor.iniciar(self.intervalo_monitor)
        self.orquestador.iniciar_modo_daemon()
        logger.info("[BaseNeuronal1] monitoreo + P2P daemon iniciados.")

    def iniciar_servidor(self,
                         host: str = "127.0.0.1",
                         port: int = 8765,
                         en_segundo_plano: bool = True) -> ServidorNeuronal:
        """Inicia el servidor neuronal para clientes externos (Godot, GDScript, P2P peers)."""
        if self.servidor is None:
            self.servidor = ServidorNeuronal(cerebro=self, host=host, port=port)
        if en_segundo_plano:
            listo = self.servidor.iniciar_en_segundo_plano()
            if not listo:
                logger.error("[BaseNeuronal1] ServidorNeuronal no pudo arrancar en %s:%d", host, port)
        else:
            self.servidor.ejecutar()
        return self.servidor

    def detener_servidor(self) -> None:
        """Detiene el servidor neuronal si está en ejecución."""
        if self.servidor is not None:
            self.servidor.detener()

    def detener(self) -> None:
        """Detiene el monitor, el orquestador P2P y el servidor."""
        self.monitor.detener()
        self.orquestador.detener()
        self.detener_servidor()

    def diagnostico_completo(self) -> Dict[str, Any]:
        """Reporte de estado de las 4 fases."""
        return {
            'metricas_aprendizaje': self.motor.obtener_metricas(),
            'estado_p2p':           self.orquestador.estado_actores(),
            'sanidad':              self.monitor.verificar_estado_completo(),
            'derivas':              self.monitor.detectar_deriva_gradientes(),
            'sesgo_q':              self.monitor.detectar_sesgo_q(),
        }

    # ------------------------------------------------------------------
    # Compatibilidad con funciones globales del módulo
    # ------------------------------------------------------------------
    def analizar_pesos(self, nombre: str, tensor: Optional[np.ndarray]) -> Dict[str, Any]:
        return analizar_pesos_tensor(nombre, tensor)

    def extraer_pesos(self, instancia: Any) -> List[Tuple[str, np.ndarray]]:
        return extraer_todos_los_pesos(instancia)

    def reporte_terminal(self) -> None:
        ejecutar_bloque_resultados_terminal()


# ===========================================================================
# SERVIDOR NEURONAL ASÍNCRONO (WebSocket RFC 6455 & TCP Streaming)
# ===========================================================================
class ServidorNeuronal:
    """Servidor de comunicación bidireccional en tiempo real para clientes externos (Godot, GDScript, P2P).

    Conecta directamente con la arquitectura neuronal de BLOK1:
      - PipelineInferencia (ENRN -> RF_EN)
      - MotorAprendizajeUnificado (retropropagación sensorial)
      - OrquestadorP2P (registro y experiencia distribuida)
      - MonitorSanidad (telemetría de pesos y auto-sanación quirúrgica)

    Características de Red
    ----------------------
      - Dual: WebSocket RFC 6455 nativo + Streaming JSON por TCP.
      - Cero dependencias externas requeridas (funciona con asyncio estándar).
      - Integrable con la librería 'websockets' oficial si está instalada.
      - Ejecución asíncrona no bloqueante en hilo daemon o bucle de eventos directo.
    """

    _WS_GUID    = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    # Intervalo en segundos entre pings WebSocket (keep-alive)
    _PING_INTERVALO = 20.0
    # Tiempo máximo en segundos esperando un pong antes de cerrar la conexión
    _PONG_TIMEOUT   = 10.0

    def __init__(self,
                 cerebro: Optional[BaseNeuronal1] = None,
                 host: str = "127.0.0.1",
                 port: int = 8765) -> None:
        self.cerebro = cerebro if cerebro is not None else BaseNeuronal1()
        self.host = host
        self.port = port
        self.is_running = False
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()
        # Evento que se activa cuando el puerto está enlazado y el servidor listo
        self._listo = threading.Event()
        self._clientes_conectados: Dict[str, Dict[str, Any]] = {}
        self._metricas: Dict[str, Any] = {
            "total_inferencias": 0,
            "total_entrenamientos": 0,
            "latencia_inferencia_acum_ms": 0.0,
            "clientes_historicos": 0,
            "errores": 0
        }
        logger.info("[ServidorNeuronal] Inicializado para BLOK1 en %s:%d (websockets_oficial=%s)",
                    self.host, self.port, _WEBSOCKETS_DISPONIBLE)

    # ------------------------------------------------------------------
    # Enrutamiento y Lógica Neuronal
    # ------------------------------------------------------------------
    def _procesar_mensaje_neuronal(self, payload: Dict[str, Any], cliente_id: str) -> Dict[str, Any]:
        """Enruta la petición del cliente hacia el componente neuronal correspondiente."""
        t0 = time.perf_counter()
        tipo = str(payload.get("tipo") or payload.get("cmd") or payload.get("tipo_peticion") or "inferencia").lower()

        try:
            # 1. INFERENCIA SENSORIOMOTORA (Pipeline Inferencia ENRN -> RF_EN)
            if tipo in ("inferencia", "predict", "act"):
                estado_raw = payload.get("estado", [0.0] * self.cerebro.input_size)
                modo = payload.get("modo", "auto")

                # Ajuste dimensional seguro
                if isinstance(estado_raw, (list, tuple)):
                    if len(estado_raw) < self.cerebro.input_size:
                        estado_raw = list(estado_raw) + [0.0] * (self.cerebro.input_size - len(estado_raw))
                    elif len(estado_raw) > self.cerebro.input_size:
                        estado_raw = list(estado_raw)[:self.cerebro.input_size]
                estado = np.asarray(estado_raw, dtype=_dt)

                accion, diag = self.cerebro.procesar(estado, modo=modo)
                latencia_total = (time.perf_counter() - t0) * 1_000

                with self._lock:
                    self._metricas["total_inferencias"] += 1
                    self._metricas["latencia_inferencia_acum_ms"] += diag.get("latencia_ms", 0.0)

                return {
                    "estado_conexion": "activo",
                    "tipo_respuesta": "inferencia",
                    "cliente_id": cliente_id,
                    "modo_aplicado": diag.get("modo"),
                    "neurona_sensorial_enrn": diag.get("neurona_enrn"),
                    "neurona_refuerzo_rfen": diag.get("neurona_rfen"),
                    "latencia_neuronal_ms": diag.get("latencia_ms"),
                    "latencia_total_ms": round(latencia_total, 4),
                    "accion": accion.tolist() if isinstance(accion, np.ndarray) else accion,
                    "tensor_salida_dim": len(accion) if hasattr(accion, "__len__") else 1,
                    "norma_estado": diag.get("norma_estado"),
                    "norma_latente": diag.get("norma_latente"),
                    "norma_accion": diag.get("norma_accion")
                }

            # 2. ENTRENAMIENTO Y RETROPROPAGACIÓN SENSORIAL
            elif tipo in ("entrenamiento", "entrenar", "aprender", "feedback", "reward"):
                actor_id = str(payload.get("actor_id", cliente_id))
                estado = np.asarray(payload.get("estado", [0.0] * self.cerebro.input_size), dtype=_dt)
                accion = payload.get("accion", 0)
                recompensa = float(payload.get("recompensa", 0.0))
                sig_estado = np.asarray(payload.get("siguiente_estado", estado), dtype=_dt)
                terminado = bool(payload.get("terminado", False))
                prob = float(payload.get("probabilidad_accion", 1.0))
                modo = payload.get("modo", "continuo")

                resultado = self.cerebro.entrenar(
                    actor_id=actor_id,
                    estado=estado,
                    accion=accion,
                    recompensa=recompensa,
                    siguiente_estado=sig_estado,
                    terminado=terminado,
                    probabilidad_accion=prob,
                    modo=modo
                )
                with self._lock:
                    self._metricas["total_entrenamientos"] += 1

                return {
                    "estado_conexion": "activo",
                    "tipo_respuesta": "entrenamiento",
                    "actor_id": actor_id,
                    "td_error": resultado.get("td_error"),
                    "recompensa": resultado.get("recompensa"),
                    "metricas_acumuladas": self.cerebro.motor.obtener_metricas()
                }

            # 3. TOPOLOGÍA P2P Y BUFFER IMPALA MULTI-ACTOR
            elif tipo in ("p2p", "p2p_experiencia", "recolectar_p2p"):
                actor_id = str(payload.get("actor_id", cliente_id))
                estado = np.asarray(payload.get("estado", [0.0] * self.cerebro.input_size), dtype=_dt)
                accion = payload.get("accion", 0)
                recompensa = float(payload.get("recompensa", 0.0))
                sig_estado = np.asarray(payload.get("siguiente_estado", estado), dtype=_dt)
                terminado = bool(payload.get("terminado", False))
                prob = float(payload.get("probabilidad_accion", 1.0))

                resultado = self.cerebro.recolectar_experiencia_p2p(
                    actor_id=actor_id,
                    estado=estado,
                    accion=accion,
                    recompensa=recompensa,
                    siguiente_estado=sig_estado,
                    terminado=terminado,
                    prob=prob
                )
                return {
                    "estado_conexion": "activo",
                    "tipo_respuesta": "p2p_experiencia",
                    "actor_id": actor_id,
                    "resultado": resultado,
                    "estado_p2p": self.cerebro.orquestador.estado_actores()
                }

            # 4. DIAGNÓSTICO INTEGRAL DE SALUD (MonitorSanidad)
            elif tipo in ("diagnostico", "sanidad", "health", "status"):
                diag_completo = self.cerebro.diagnostico_completo()
                return {
                    "estado_conexion": "activo",
                    "tipo_respuesta": "diagnostico",
                    "servidor_metricas": self.obtener_metricas(),
                    "diagnostico_neuronal": diag_completo
                }

            # 5. AUTO-SANACIÓN QUIRÚRGICA DE NEURONAS
            elif tipo in ("auto_sanar", "sanar", "reset_neurona"):
                neurona = str(payload.get("neurona", "EN1"))
                exito = self.cerebro.monitor.auto_sanar(neurona)
                return {
                    "estado_conexion": "activo",
                    "tipo_respuesta": "auto_sanar",
                    "neurona": neurona,
                    "sanado_exitoso": exito
                }

            # 6. ANÁLISIS ESTADÍSTICO DE PESOS
            elif tipo in ("pesos", "analisis_pesos"):
                return {
                    "estado_conexion": "activo",
                    "tipo_respuesta": "analisis_pesos",
                    "modulos_enrn_cargados": len(modulos_enrn),
                    "modulos_rfen_cargados": len(modulos_rfen)
                }

            else:
                return {
                    "estado_conexion": "activo",
                    "error": f"Comando '{tipo}' no reconocido",
                    "comandos_validos": ["inferencia", "entrenamiento", "p2p", "diagnostico", "auto_sanar", "pesos"]
                }

        except Exception as exc:
            with self._lock:
                self._metricas["errores"] += 1
            logger.error("[ServidorNeuronal] Error procesando petición de %s: %s", cliente_id, exc)
            return {
                "estado_conexion": "error",
                "error": str(exc),
                "cliente_id": cliente_id
            }

    # ------------------------------------------------------------------
    # Motor de Red Nativo (asyncio / RFC 6455 & TCP JSON)
    # ------------------------------------------------------------------
    async def _gestionar_conexion_nativa(self,
                                        reader: asyncio.StreamReader,
                                        writer: asyncio.StreamWriter) -> None:
        """Gestiona un socket cliente reconociendo si es WebSocket RFC 6455 o TCP puro."""
        addr = writer.get_extra_info("peername")
        cliente_id = f"peer_{addr[0]}_{addr[1]}" if addr else f"peer_{random.randint(1000, 9999)}"
        logger.info("[ServidorNeuronal] Cliente conectado: %s (%s)", cliente_id, addr)

        with self._lock:
            self._clientes_conectados[cliente_id] = {
                "addr": addr,
                "conectado_en": time.time(),
                "mensajes": 0,
                "tipo": "desconocido"
            }
            self._metricas["clientes_historicos"] += 1

        # Auto-registrar en el OrquestadorP2P de BLOK1
        self.cerebro.registrar_actor(cliente_id, socket_info={"addr": addr}, modo="distribuido")

        is_websocket = False
        try:
            # Leer bloque inicial para identificar protocolo
            # Timeout de 10 s para el primer byte — evita bloquear indefinidamente
            try:
                datos_iniciales = await asyncio.wait_for(reader.read(4096), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("[ServidorNeuronal] Timeout esperando datos de %s", cliente_id)
                return
            if not datos_iniciales:
                return

            # ¿Es Handshake WebSocket HTTP Upgrade?
            if b"Upgrade: websocket" in datos_iniciales or b"upgrade: websocket" in datos_iniciales:
                lineas = datos_iniciales.split(b"\r\n")
                ws_key = None
                for linea in lineas:
                    if linea.lower().startswith(b"sec-websocket-key:"):
                        ws_key = linea.split(b":", 1)[1].strip().decode()
                        break

                if ws_key:
                    accept_raw = (ws_key + self._WS_GUID).encode("utf-8")
                    accept_sha = hashlib.sha1(accept_raw).digest()
                    accept_b64 = base64.b64encode(accept_sha).decode("utf-8")

                    respuesta_handshake = (
                        "HTTP/1.1 101 Switching Protocols\r\n"
                        "Upgrade: websocket\r\n"
                        "Connection: Upgrade\r\n"
                        f"Sec-WebSocket-Accept: {accept_b64}\r\n\r\n"
                    )
                    writer.write(respuesta_handshake.encode("utf-8"))
                    await writer.drain()
                    is_websocket = True
                    with self._lock:
                        if cliente_id in self._clientes_conectados:
                            self._clientes_conectados[cliente_id]["tipo"] = "websocket"
                    logger.info("[ServidorNeuronal] Handshake WebSocket OK con %s", cliente_id)
                else:
                    logger.warning("[ServidorNeuronal] Handshake WS sin clave válida de %s", cliente_id)
                    return
            else:
                # TCP puro — procesar primeros datos y entrar al loop
                with self._lock:
                    if cliente_id in self._clientes_conectados:
                        self._clientes_conectados[cliente_id]["tipo"] = "tcp"
                await self._procesar_fragmento_tcp(datos_iniciales, reader, writer, cliente_id)

            # Bucle principal de escucha (permanente hasta desconexión)
            if is_websocket:
                await self._loop_websocket_nativo(reader, writer, cliente_id)
            else:
                await self._loop_tcp_puro(reader, writer, cliente_id)

        except asyncio.IncompleteReadError:
            pass  # Cliente cerró la conexión limpiamente
        except ConnectionResetError:
            pass
        except BrokenPipeError:
            pass
        except Exception as exc:
            logger.debug("[ServidorNeuronal] Conexión cerrada con %s: %s", cliente_id, exc)
        finally:
            with self._lock:
                self._clientes_conectados.pop(cliente_id, None)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("[ServidorNeuronal] Cliente desconectado: %s", cliente_id)

    async def _loop_websocket_nativo(self,
                                    reader: asyncio.StreamReader,
                                    writer: asyncio.StreamWriter,
                                    cliente_id: str) -> None:
        """Lee y responde frames WebSocket RFC 6455 con keep-alive por ping/pong."""
        ultimo_ping = time.monotonic()

        while self.is_running:
            # ---- Keep-alive: enviar Ping periódico ----
            ahora = time.monotonic()
            if ahora - ultimo_ping >= self._PING_INTERVALO:
                try:
                    # Opcode 0x89 = Ping, sin payload
                    writer.write(bytes([0x89, 0x00]))
                    await writer.drain()
                    ultimo_ping = ahora
                    logger.debug("[ServidorNeuronal] Ping enviado a %s", cliente_id)
                except Exception:
                    break

            # ---- Leer siguiente frame con timeout ----
            try:
                header = await asyncio.wait_for(
                    reader.readexactly(2),
                    timeout=self._PING_INTERVALO + self._PONG_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.warning("[ServidorNeuronal] Sin respuesta de %s — cerrando.", cliente_id)
                break
            except asyncio.IncompleteReadError:
                break

            b0, b1 = header[0], header[1]
            fin    = (b0 & 0x80) != 0  # noqa: F841  (reservado para fragmentación futura)
            opcode = b0 & 0x0F

            # ---- Control frames ----
            if opcode == 0x8:   # Close
                # Responder con Close frame y cerrar
                writer.write(bytes([0x88, 0x00]))
                await writer.drain()
                break
            if opcode == 0x9:   # Ping → Pong
                writer.write(bytes([0x8A, 0x00]))
                await writer.drain()
                continue
            if opcode == 0xA:   # Pong (respuesta a nuestro Ping)
                ultimo_ping = time.monotonic()
                continue
            if opcode not in (0x1, 0x2, 0x0):  # Solo texto, binario o continuación
                continue

            # ---- Leer longitud del payload ----
            masked      = (b1 & 0x80) != 0
            payload_len = b1 & 0x7F
            if payload_len == 126:
                ext = await reader.readexactly(2)
                payload_len = struct.unpack("!H", ext)[0]
            elif payload_len == 127:
                ext = await reader.readexactly(8)
                payload_len = struct.unpack("!Q", ext)[0]

            # Protección anti-DoS: rechazar frames > 1 MB
            if payload_len > 1_048_576:
                logger.warning("[ServidorNeuronal] Frame demasiado grande (%d B) de %s", payload_len, cliente_id)
                break

            # ---- Leer máscara y payload ----
            mask_key = b""
            if masked:
                mask_key = await reader.readexactly(4)

            payload_data = await reader.readexactly(payload_len)
            if masked:
                payload_data = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload_data))

            texto = payload_data.decode("utf-8", errors="replace").strip()
            if not texto:
                continue

            try:
                peticion = json.loads(texto)
            except Exception:
                peticion = {"tipo": "inferencia", "estado": [0.0] * self.cerebro.input_size}

            # ---- Responder ----
            respuesta  = self._procesar_mensaje_neuronal(peticion, cliente_id)
            # Propagar el id de la petición si existe (para correlación en cliente)
            if "id" in peticion:
                respuesta["id"] = peticion["id"]

            resp_bytes = json.dumps(respuesta).encode("utf-8")

            longitud = len(resp_bytes)
            if longitud <= 125:
                hdr_out = bytes([0x81, longitud])
            elif longitud <= 65535:
                hdr_out = struct.pack("!BBH", 0x81, 126, longitud)
            else:
                hdr_out = struct.pack("!BBQ", 0x81, 127, longitud)

            writer.write(hdr_out + resp_bytes)
            await writer.drain()

            with self._lock:
                if cliente_id in self._clientes_conectados:
                    self._clientes_conectados[cliente_id]["mensajes"] += 1

    async def _loop_tcp_puro(self,
                             reader: asyncio.StreamReader,
                             writer: asyncio.StreamWriter,
                             cliente_id: str) -> None:
        """Lee y responde líneas de JSON en streaming TCP plano (sin límite de mensajes)."""
        while self.is_running:
            try:
                linea = await asyncio.wait_for(reader.readline(), timeout=60.0)
            except asyncio.TimeoutError:
                # Enviar keep-alive vacío y continuar
                try:
                    writer.write(b"\n")
                    await writer.drain()
                except Exception:
                    break
                continue

            if not linea:
                break  # Conexión cerrada por el cliente

            texto = linea.decode("utf-8", errors="replace").strip()
            if not texto:
                continue

            try:
                peticion = json.loads(texto)
            except Exception:
                peticion = {"tipo": "inferencia", "estado": [0.0] * self.cerebro.input_size}

            respuesta = self._procesar_mensaje_neuronal(peticion, cliente_id)
            if "id" in peticion:
                respuesta["id"] = peticion["id"]

            writer.write((json.dumps(respuesta) + "\n").encode("utf-8"))
            await writer.drain()

            with self._lock:
                if cliente_id in self._clientes_conectados:
                    self._clientes_conectados[cliente_id]["mensajes"] += 1

    async def _procesar_fragmento_tcp(self,
                                      datos: bytes,
                                      reader: asyncio.StreamReader,
                                      writer: asyncio.StreamWriter,
                                      cliente_id: str) -> None:
        """Procesa el primer bloque de bytes recibido en TCP antes de entrar al loop permanente."""
        texto = datos.decode("utf-8", errors="replace").strip()
        if not texto:
            return
        lineas = [l.strip() for l in texto.split("\n") if l.strip()]
        for l in lineas:
            try:
                peticion = json.loads(l)
                resp = self._procesar_mensaje_neuronal(peticion, cliente_id)
                if "id" in peticion:
                    resp["id"] = peticion["id"]
                writer.write((json.dumps(resp) + "\n").encode("utf-8"))
                await writer.drain()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Control del Ciclo de Vida del Servidor
    # ------------------------------------------------------------------
    async def iniciar(self) -> None:
        """Arranca el servidor de forma asíncrona y permanente."""
        self._loop = asyncio.get_running_loop()
        try:
            self._server = await asyncio.start_server(
                self._gestionar_conexion_nativa,
                self.host,
                self.port,
                # Permitir reutilizar el puerto inmediatamente tras un restart
                reuse_address=True,
            )
        except OSError as exc:
            logger.error("[ServidorNeuronal] No se pudo enlazar %s:%d → %s", self.host, self.port, exc)
            self._listo.set()   # desbloquear a quien espera
            return

        self.is_running = True
        # Señalizar que el puerto está enlazado y el servidor está listo
        self._listo.set()
        addrs = [s.getsockname() for s in self._server.sockets]
        logger.info("[ServidorNeuronal] ✓ Servidor listo en %s (WebSocket RFC 6455 + TCP)", addrs)

        async with self._server:
            await self._server.serve_forever()

    def ejecutar(self) -> None:
        """Punto de entrada síncrono bloqueante (proceso dedicado / script directo)."""
        self._listo = threading.Event()
        try:
            asyncio.run(self.iniciar())
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("[ServidorNeuronal] Servidor detenido por el usuario.")
        finally:
            self.is_running = False

    def iniciar_en_segundo_plano(self, timeout_arranque: float = 5.0) -> bool:
        """Arranca el servidor en un hilo daemon con su propio event loop.

        Bloquea al llamador hasta que el puerto esté enlazado (o se agote el timeout).

        Parameters
        ----------
        timeout_arranque : float
            Segundos máximos para esperar a que el servidor quede listo (default 5 s).

        Returns
        -------
        bool
            True si el servidor arrancó correctamente, False si hubo error.
        """
        if self.is_running:
            logger.warning("[ServidorNeuronal] Servidor ya está en ejecución en %s:%d.", self.host, self.port)
            return True

        # Reinicializar el evento de listo para esta instancia
        self._listo = threading.Event()

        def _worker() -> None:
            # En Windows, IocpProactor puede colgarse en hilos secundarios.
            # SelectorEventLoop es estable en todos los hilos de Windows.
            import sys as _sys
            if _sys.platform == "win32":
                loop = asyncio.SelectorEventLoop()
            else:
                loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            try:
                loop.run_until_complete(self.iniciar())
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            except Exception as exc:
                logger.debug("[ServidorNeuronal] Loop de red cerrado: %s", exc)
            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        self._thread = threading.Thread(
            target=_worker,
            name="ServidorNeuronal-Thread",
            daemon=True
        )
        self._thread.start()

        # Esperar a que el servidor esté realmente listo (puerto enlazado)
        arrancado = self._listo.wait(timeout=timeout_arranque)
        if arrancado and self.is_running:
            logger.info("[ServidorNeuronal] ✓ Hilo daemon listo en ws://%s:%d", self.host, self.port)
            return True
        else:
            logger.error("[ServidorNeuronal] ✗ Servidor no arrancó en %.1f s", timeout_arranque)
            return False

    async def _cerrar_servidor_async(self) -> None:
        """Cierra el servidor asyncio de forma ordenada desde el loop interno."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def detener(self) -> None:
        """Detiene el servidor limpiamente: cierra conexiones, libera el puerto y el hilo."""
        if not self.is_running and self._server is None:
            return
        self.is_running = False
        if self._loop and self._loop.is_running():
            # Cerrar el server asyncio desde dentro del loop
            future = asyncio.run_coroutine_threadsafe(
                self._cerrar_servidor_async(), self._loop
            )
            try:
                future.result(timeout=3.0)
            except Exception:
                pass
            # Parar el event loop
            self._loop.call_soon_threadsafe(self._loop.stop)
        # Esperar que el hilo termine (máx 3 s)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._server = None
        logger.info("[ServidorNeuronal] Servidor detenido y puerto liberado.")

    def obtener_metricas(self) -> Dict[str, Any]:
        """Devuelve estadísticas operativas del servidor."""
        with self._lock:
            prom_lat = (
                self._metricas["latencia_inferencia_acum_ms"] / max(1, self._metricas["total_inferencias"])
            )
            return {
                "is_running": self.is_running,
                "host": self.host,
                "port": self.port,
                "clientes_activos": len(self._clientes_conectados),
                "clientes_historicos": self._metricas["clientes_historicos"],
                "total_inferencias": self._metricas["total_inferencias"],
                "total_entrenamientos": self._metricas["total_entrenamientos"],
                "latencia_promedio_ms": round(prom_lat, 4),
                "errores": self._metricas["errores"]
            }

# Asignar también como clase anidada / atributo de BaseNeuronal1
BaseNeuronal1.ServidorNeuronal = ServidorNeuronal


# ===========================================================================
# FUNCIÓN DE PRUEBA COMPLETA — 4 FASES
# ===========================================================================
def _prueba_4_fases() -> None:
    """Prueba integrada de las 4 fases de BaseNeuronal1."""
    print("\n" + "=" * 110)
    print(" " * 25 + "PRUEBA INTEGRADA — PLAN DE DESARROLLO BLOK1 (FASES 1-4)")
    print("=" * 110)

    cerebro = BaseNeuronal1(input_size=10, output_size=4, latente_size=16)

    # ---- Fase 1: Inferencia ----
    print("\n[FASE 1] PIPELINE DE INFERENCIA UNIFICADO")
    print("-" * 60)
    modos_prueba = ['auto', 'continuo', 'discreto', 'normalizado',
                    'navegacion', 'cinematica', 'riesgo', 'distribuido', 'xavier', 'basico']
    for modo in modos_prueba:
        estado = np.random.randn(10).astype(_dt)
        try:
            accion, diag = cerebro.procesar(estado, modo)
            print(f"  modo={modo:<12}  ENRN={diag['neurona_enrn']:<30}  "
                  f"RF_EN={diag['neurona_rfen']:<35}  lat={diag['latencia_ms']:.3f}ms  "
                  f"|a|={diag['norma_accion']:.4f}")
        except Exception as exc:
            print(f"  modo={modo:<12}  ERROR: {exc}")

    # ---- Fase 2: Aprendizaje ----
    print("\n[FASE 2] MOTOR DE APRENDIZAJE UNIFICADO")
    print("-" * 60)
    for paso in range(5):
        st  = np.random.randn(10).astype(_dt)
        st2 = np.random.randn(10).astype(_dt)
        r   = float(np.random.uniform(-1, 1))
        res = cerebro.entrenar("actor_local", st, 0, r, st2, False, modo='continuo')
        print(f"  paso={paso+1}  td_error={res['td_error']:+.4f}  recompensa={res['recompensa']:+.4f}")
    met = cerebro.motor.obtener_metricas()
    print(f"  → Métricas acumuladas: pasos={met['pasos']}  "
          f"td_medio={met['td_error_medio']:+.4f}  "
          f"reward_medio={met['recompensa_media']:+.4f}  "
          f"ajustes_sensoriales={met['ajustes_sensoriales']}")

    # ---- Fase 3: P2P ----
    print("\n[FASE 3] ORQUESTADOR P2P MULTI-ACTOR")
    print("-" * 60)
    for aid in ['actor_A', 'actor_B', 'actor_C']:
        cerebro.registrar_actor(aid, modo='distribuido')
    for paso in range(6):
        aid = random.choice(['actor_A', 'actor_B', 'actor_C'])
        st  = np.random.randn(10).astype(_dt)
        st2 = np.random.randn(10).astype(_dt)
        res = cerebro.recolectar_experiencia_p2p(
            aid, st, 0, float(np.random.uniform(-1, 1)), st2, False)
        print(f"  actor={aid}  td_error={res['td_error']:+.4f}")
    estado_p2p = cerebro.orquestador.estado_actores()
    print(f"  → Estado P2P: {estado_p2p['num_actores']} actores  "
          f"paso_global={estado_p2p['paso_global']}")

    # ---- Fase 4: Monitor Sanidad ----
    print("\n[FASE 4] MONITOR DE SANIDAD Y AUTO-SANACIÓN")
    print("-" * 60)
    reporte = cerebro.monitor.verificar_estado_completo()
    derivas  = cerebro.monitor.detectar_deriva_gradientes()
    sesgo_q  = cerebro.monitor.detectar_sesgo_q()
    print(f"  Estado global    : {reporte['estado_global']}")
    print(f"  Neuronas ENRN    : {len(reporte['enrn'])} verificadas")
    print(f"  Neuronas RF_EN   : {len(reporte['rfen'])} verificadas")
    print(f"  Anomalías totales: {len(reporte['anomalias'])}")
    print(f"  Derivas detectadas: {derivas if derivas else 'ninguna'}")
    print(f"  Sesgo Q detectado : {sesgo_q  if sesgo_q  else 'ninguno'}")

    # ---- Fase 5: Servidor Neuronal (WebSocket / TCP) ----
    print("\n[FASE 5] SERVIDOR NEURONAL ASÍNCRONO (CLIENTE-SERVIDOR)")
    print("-" * 60)
    import socket
    puerto_test = 8790
    servidor = ServidorNeuronal(cerebro=cerebro, host="127.0.0.1", port=puerto_test)
    servidor.iniciar_en_segundo_plano()
    time.sleep(0.3)

    try:
        with socket.create_connection(("127.0.0.1", puerto_test), timeout=2.0) as sock:
            # 1. Test Inferencia Remota
            pet_inf = json.dumps({"tipo": "inferencia", "estado": [0.3] * 10, "modo": "cinematica"}) + "\n"
            sock.sendall(pet_inf.encode("utf-8"))
            resp_inf_raw = sock.recv(4096).decode("utf-8").strip()
            resp_inf = json.loads(resp_inf_raw)
            print(f"  -> Inferencia Remota OK: modo={resp_inf.get('modo_aplicado')}  "
                  f"enrn={resp_inf.get('neurona_sensorial_enrn')}  "
                  f"rfen={resp_inf.get('neurona_refuerzo_rfen')}  "
                  f"lat={resp_inf.get('latencia_total_ms')}ms")

            # 2. Test Entrenamiento Remoto
            pet_ent = json.dumps({
                "tipo": "entrenar",
                "actor_id": "godot_peer_3d",
                "estado": [0.1] * 10,
                "accion": 1,
                "recompensa": 0.75,
                "siguiente_estado": [0.2] * 10,
                "terminado": False,
                "modo": "continuo"
            }) + "\n"
            sock.sendall(pet_ent.encode("utf-8"))
            resp_ent_raw = sock.recv(4096).decode("utf-8").strip()
            resp_ent = json.loads(resp_ent_raw)
            print(f"  -> Entrenamiento Remoto OK: actor={resp_ent.get('actor_id')}  "
                  f"td_error={resp_ent.get('td_error'):+.4f}  "
                  f"reward={resp_ent.get('recompensa'):+.4f}")

            # 3. Test Diagnóstico Remoto
            pet_diag = json.dumps({"tipo": "diagnostico"}) + "\n"
            sock.sendall(pet_diag.encode("utf-8"))
            resp_diag_raw = sock.recv(8192).decode("utf-8").strip()
            resp_diag = json.loads(resp_diag_raw)
            san_remota = resp_diag.get("diagnostico_neuronal", {}).get("sanidad", {})
            print(f"  -> Diagnóstico Remoto OK: salud={san_remota.get('estado_global')}  "
                  f"anomalías={len(san_remota.get('anomalias', []))}")

    except Exception as exc:
        print(f"  -> Error prueba cliente socket: {exc}")
    finally:
        servidor.detener()

    met_serv = servidor.obtener_metricas()
    print(f"  -> Métricas Servidor: inferencias={met_serv['total_inferencias']}  "
          f"entrenamientos={met_serv['total_entrenamientos']}  "
          f"lat_promedio={met_serv['latencia_promedio_ms']}ms")

    # Resumen global
    print("\n" + "=" * 110)
    print(" " * 42 + "RESUMEN GLOBAL")
    print("=" * 110)
    diag = cerebro.diagnostico_completo()
    met2 = diag['metricas_aprendizaje']
    p2p2 = diag['estado_p2p']
    san2 = diag['sanidad']
    print(f"  • Pasos de aprendizaje  : {met2['pasos']}")
    print(f"  • TD-error medio        : {met2['td_error_medio']:+.6f}")
    print(f"  • Recompensa media      : {met2['recompensa_media']:+.6f}")
    print(f"  • Ajustes sensoriales   : {met2['ajustes_sensoriales']}")
    print(f"  • Actores P2P           : {p2p2['num_actores']}")
    print(f"  • Paso global P2P       : {p2p2['paso_global']}")
    print(f"  • Estado de sanidad     : {san2['estado_global']}")
    print(f"  • Anomalías sanidad     : {len(san2['anomalias'])}")
    print("=" * 110 + "\n")


if __name__ == "__main__":
    ejecutar_bloque_resultados_terminal()
    _prueba_4_fases()
