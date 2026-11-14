"""LCBS_NEURONAL.py - modulo principal de la red neuronal LC_STM.

Centraliza el acceso a todas las familias neuronales del sistema y ofrece
``RedNeuronal`` como fachada de calculo y orquestacion:

  - ENRN      : red neuronal estandar de entrada.
  - RF_EN     : neuronas de refuerzo (Q-Learning, DQN, PPO, SAC, TD3...).
  - RF_SL     : red supervisada completa (10 optimizadores + puentes).
  - RNP       : optimizacion de pesos (AdamW, SAM, Lion, SWAT...).
  - SLRN      : optimizadores supervisados neuronales (SL1..SL10).
  - CELEBRO   : BLOK1, pipeline ENRN -> RF_EN y servidor neuronal.

``RedNeuronal`` permite:
  - consultar el catalogo y la salud de todos los subsistemas;
  - construir y entrenar cualquier modelo RF_SL;
  - ejecutar una inferencia de refuerzo ENRN -> RF_EN;
  - calcular y comparar todos los modelos supervisados con sus metricas;
  - arrancar/detener el servidor neuronal;
  - guardar el resultado completo de los calculos en JSON.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# Permitir ejecucion directa del archivo ademas de la importacion como paquete.
try:
    from .RedNeuronal import ENRN, RF_EN, RF_SL, RNP, SLRN
    from .RedNeuronal.ENRN import (
        crear_neurona as crear_neurona_enrn,
        listar_tipos as listar_tipos_enrn,
    )
    from .RedNeuronal.RF_SL import (
        DataPipeline,
        MetricsCollector,
        ModelRegistry,
        NeuronaMemoriaBase,
        TrainingConfig,
        build_model,
        compare_models,
        deserialize_model,
        get_available_models,
        quick_evaluate,
        quick_predict,
        quick_train,
        serialize_model,
        train_all_models,
    )
    from .RedNeuronal.RNP import (
        RNPBenchmark,
        RNPFactory,
        RNPRegistry,
        health_check as salud_rnp,
        list_optimizers as listar_optimizadores_rnp,
    )
    from .RedNeuronal.SLRN import (
        SLRNSystem,
        SupervisedLearningNeuralConfig,
        get_version as version_slrn,
        list_optimizers as listar_optimizadores_slrn,
    )
except ImportError:  # pragma: no cover - ejecucion directa / script
    _DIR_LC_STM = os.path.dirname(os.path.abspath(__file__))
    if _DIR_LC_STM not in sys.path:
        sys.path.insert(0, _DIR_LC_STM)

    from RedNeuronal import ENRN, RF_EN, RF_SL, RNP, SLRN  # type: ignore
    from RedNeuronal.ENRN import (  # type: ignore
        crear_neurona as crear_neurona_enrn,
        listar_tipos as listar_tipos_enrn,
    )
    from RedNeuronal.RF_SL import (  # type: ignore
        DataPipeline,
        MetricsCollector,
        ModelRegistry,
        NeuronaMemoriaBase,
        TrainingConfig,
        build_model,
        compare_models,
        deserialize_model,
        get_available_models,
        quick_evaluate,
        quick_predict,
        quick_train,
        serialize_model,
        train_all_models,
    )
    from RedNeuronal.RNP import (  # type: ignore
        RNPBenchmark,
        RNPFactory,
        RNPRegistry,
        health_check as salud_rnp,
        list_optimizers as listar_optimizadores_rnp,
    )
    from RedNeuronal.SLRN import (  # type: ignore
        SLRNSystem,
        SupervisedLearningNeuralConfig,
        get_version as version_slrn,
        list_optimizers as listar_optimizadores_slrn,
    )

logger = logging.getLogger("LC_STM.LCBS_NEURONAL")

__version__ = "2026.1.0"
__author__ = "WoldVirtualP2P3D Team"


class RedNeuronal:
    """Fachada principal de toda la red neuronal LC_STM.

    Parameters
    ----------
    input_size, output_size:
        Dimensiones del pipeline sensorial y de acciones de CELEBRO.
    latente_size:
        Tamano del espacio latente ENRN -> RF_EN.
    seed:
        Semilla de referencia.
    """

    VERSION = __version__
    FAMILIAS = ("ENRN", "RF_EN", "RF_SL", "RNP", "SLRN", "CELEBRO")

    def __init__(
        self,
        input_size: int = 10,
        output_size: int = 4,
        latente_size: int = 16,
        seed: int = 2026,
    ) -> None:
        self.input_size = int(input_size)
        self.output_size = int(output_size)
        self.latente_size = int(latente_size)
        self.seed = int(seed)

        # Referencias a las familias (importadas en la cabecera).
        self.ENRN = ENRN
        self.RF_EN = RF_EN
        self.RF_SL = RF_SL
        self.RNP = RNP
        self.SLRN = SLRN

        self._cerebro: Optional[Any] = None
        self._servidor: Optional[Any] = None
        self._modelos: Dict[str, Any] = {}
        self._ultimo_resultado: Dict[str, Any] = {}
        self._reporte_recursos: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Catalogo y salud
    # ------------------------------------------------------------------
    def catalogo(self) -> Dict[str, Any]:
        """Catalogo completo de clases, tipos y optimizadores disponibles."""
        try:
            from .RedNeuronal.ENRN.SBRTM_IMPORT.sbrtm_import2 import (
                listar_tipos as _listar_enrn_directo,
            )
        except ImportError:  # pragma: no cover
            from RedNeuronal.ENRN.SBRTM_IMPORT.sbrtm_import2 import (  # type: ignore
                listar_tipos as _listar_enrn_directo,
            )
        tipos_enrn = listar_tipos_enrn() or _listar_enrn_directo()
        catalogo: Dict[str, Any] = {
            'ENRN': {
                'modulo': ENRN.__name__,
                'tipos': list(tipos_enrn or []),
                'clases': sorted(
                    nombre for nombre in dir(ENRN)
                    if nombre.startswith('Neurona')
                ),
            },
            'RF_EN': {
                'modulo': RF_EN.__name__,
                'clases': sorted(
                    nombre for nombre in dir(RF_EN)
                    if nombre.startswith('NeuronaRefuerzo')
                ),
            },
            'RF_SL': {
                'modulo': RF_SL.__name__,
                'modelos': list(get_available_models()),
                'clases': sorted(
                    nombre for nombre in dir(RF_SL)
                    if nombre.startswith(('Neurona', 'Neural'))
                ),
            },
            'RNP': {
                'modulo': RNP.__name__,
                'optimizadores': list(listar_optimizadores_rnp()),
            },
            'SLRN': {
                'modulo': SLRN.__name__,
                'optimizadores': list(listar_optimizadores_slrn()),
            },
            'CELEBRO': {
                'modulo': 'CELEBRO.BLOK1',
                'clases': ['BaseNeuronal1', 'ServidorNeuronal',
                           'PipelineInferencia', 'MotorAprendizajeUnificado',
                           'OrquestadorP2P', 'MonitorSanidad'],
            },
        }
        return catalogo

    def salud(self) -> Dict[str, Any]:
        """Estado de importacion/salud de las 6 familias."""
        try:
            from .RedNeuronal import salud_red
        except ImportError:  # pragma: no cover
            from RedNeuronal import salud_red  # type: ignore

        estado = salud_red()
        estado['LCBS_NEURONAL'] = {
            'importa': True,
            'version': __version__,
            'ok': True,
        }
        return estado

    def info(self) -> Dict[str, Any]:
        """Metadatos de la red y de sus familias."""
        return {
            'nombre': 'RedNeuronal',
            'version': __version__,
            'input_size': self.input_size,
            'output_size': self.output_size,
            'latente_size': self.latente_size,
            'seed': self.seed,
            'familias': list(self.FAMILIAS),
            'catalogo': self.catalogo(),
            'salud': self.salud(),
        }

    # ------------------------------------------------------------------
    # Construccion de componentes
    # ------------------------------------------------------------------
    def crear_modelo(self, tipo: str = "neural_network",
                     input_size: Optional[int] = None,
                     output_size: Optional[int] = None,
                     **kwargs: Any) -> Any:
        """Construye un modelo supervisado RF_SL por nombre."""
        entrada = self.input_size if input_size is None else int(input_size)
        salida = self.output_size if output_size is None else int(output_size)
        modelo = build_model(tipo, entrada, salida)
        self._modelos[tipo] = modelo
        return modelo

    def crear_neurona_enrn(self, tipo: str = "basica",
                           input_size: Optional[int] = None,
                           output_size: Optional[int] = None) -> Any:
        """Construye una neurona de entrada ENRN."""
        entrada = self.input_size if input_size is None else int(input_size)
        salida = self.output_size if output_size is None else int(output_size)
        try:
            return crear_neurona_enrn(tipo, entrada, salida)
        except TypeError:
            # El __init__ de ENRN conserva stubs historicos sin argumentos;
            # se usa la fabrica real de SBRTM_IMPORT.
            try:
                from .RedNeuronal.ENRN.SBRTM_IMPORT.sbrtm_import2 import (
                    crear_neurona as _crear_enrn_directo,
                )
            except ImportError:  # pragma: no cover
                from RedNeuronal.ENRN.SBRTM_IMPORT.sbrtm_import2 import (  # type: ignore
                    crear_neurona as _crear_enrn_directo,
                )
            return _crear_enrn_directo(tipo, entrada, salida)

    def crear_optimizador_rnp(self, clave: str = "adamw") -> Any:
        """Construye un optimizador de pesos RNP."""
        return RNPFactory.create(clave)

    def crear_sistema_slrn(
        self, configuracion: Optional[Any] = None,
    ) -> SLRNSystem:
        """Construye el orquestador de optimizadores supervisados SLRN."""
        return SLRNSystem(configuracion or SupervisedLearningNeuralConfig())

    # ------------------------------------------------------------------
    # Pipeline CELEBRO / refuerzo
    # ------------------------------------------------------------------
    @property
    def cerebro(self) -> Any:
        """Instancia perezosa de BaseNeuronal1 (BLOK1)."""
        if self._cerebro is None:
            try:
                from .RedNeuronal.CELEBRO import BaseNeuronal1
            except ImportError:  # pragma: no cover
                from RedNeuronal.CELEBRO import BaseNeuronal1  # type: ignore
            self._cerebro = BaseNeuronal1(
                input_size=self.input_size,
                output_size=self.output_size,
                latente_size=self.latente_size,
            )
        return self._cerebro

    def procesar(self, estado: Optional[Sequence[float]] = None,
                 modo: str = "auto") -> Tuple[np.ndarray, Dict[str, Any]]:
        """Inferencia completa ENRN -> RF_EN a traves de BLOK1."""
        vector = (np.zeros(self.input_size, dtype=np.float32)
                  if estado is None else np.asarray(estado, dtype=np.float32))
        if vector.size != self.input_size:
            raise ValueError(
                f"El estado debe tener {self.input_size} valores y tiene "
                f"{vector.size}"
            )
        return self.cerebro.procesar(vector, modo)

    def entrenar_refuerzo(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Delega en ``BaseNeuronal1.entrenar`` (RL + ajuste sensorial)."""
        return self.cerebro.entrenar(*args, **kwargs)

    def iniciar_servidor(self, host: str = "127.0.0.1", port: int = 8765,
                         en_segundo_plano: bool = True) -> Any:
        """Arranca el servidor neuronal de BLOK1."""
        self._servidor = self.cerebro.iniciar_servidor(
            host=host, port=port, en_segundo_plano=en_segundo_plano
        )
        return self._servidor

    def detener_servidor(self) -> None:
        """Detiene el servidor neuronal si esta activo."""
        if self._servidor is not None:
            self._servidor.detener()
            self._servidor = None

    def cerrar(self) -> None:
        """Detiene servidor, monitor y orquestador."""
        try:
            self.detener_servidor()
        finally:
            if self._cerebro is not None:
                self._cerebro.detener()
                self._cerebro = None

    def __enter__(self) -> "RedNeuronal":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.cerrar()

    # ------------------------------------------------------------------
    # Entrenamiento supervisado
    # ------------------------------------------------------------------
    @staticmethod
    def _inferir_salida(y: np.ndarray) -> Tuple[str, int]:
        arreglo = np.asarray(y)
        if arreglo.ndim == 2 and arreglo.shape[1] >= 2:
            if np.allclose(
                np.sum(arreglo.astype(np.float64), axis=1), 1.0
            ):
                return 'clasificacion', int(arreglo.shape[1])
        if arreglo.dtype.kind in "biuUSO":
            return 'clasificacion', int(len(np.unique(arreglo)))
        valores = arreglo.astype(np.float64)
        unicos = np.unique(valores)
        entero = bool(np.allclose(valores, np.round(valores)))
        if entero and unicos.size <= max(2, min(20, max(1, valores.size // 3))):
            return 'clasificacion', int(unicos.size)
        if valores.ndim == 2:
            return 'regresion', int(valores.shape[1])
        return 'regresion', 1

    @staticmethod
    def _objetivo_clasificacion(
        y: np.ndarray, salidas: int,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, str]:
        """Devuelve (etiquetas, one-hot, clases, formato)."""
        arreglo = np.asarray(y)
        if arreglo.ndim == 2 and arreglo.shape[1] == salidas:
            if np.allclose(
                np.sum(arreglo.astype(np.float64), axis=1), 1.0
            ):
                etiquetas = np.argmax(arreglo, axis=1)
                return etiquetas, arreglo, np.arange(salidas), 'onehot'
        etiquetas = arreglo.reshape(-1)
        clases, codificado = np.unique(etiquetas, return_inverse=True)
        onehot = np.zeros((len(etiquetas), len(clases)), dtype=np.float64)
        onehot[np.arange(len(etiquetas)), codificado] = 1.0
        return etiquetas, onehot, clases, 'etiquetas'

    def entrenar_modelo(self, tipo: str, X: np.ndarray, y: np.ndarray,
                        epochs: int = 100, verbose: bool = False
                        ) -> Dict[str, Any]:
        """Entrena un modelo RF_SL y devuelve sus metricas.

        Para clasificacion prueba primero etiquetas y, si el modelo exige
        salidas multiples (GradientBoosting/MLP), reintenta con one-hot.
        """
        matriz = np.asarray(X, dtype=np.float64)
        if matriz.ndim != 2:
            raise ValueError("X debe ser una matriz 2D")
        tarea, salidas = self._inferir_salida(y)
        inicio = time.perf_counter()
        metodo = 'fit'

        intentos: List[Tuple[np.ndarray, str]] = [(np.asarray(y), 'directo')]
        if tarea == 'clasificacion':
            _etiquetas, onehot, _clases, formato = (
                self._objetivo_clasificacion(y, salidas)
            )
            if formato == 'etiquetas':
                intentos.append((onehot, 'onehot'))

        ultimo_error: Optional[Exception] = None
        modelo: Optional[Any] = None
        y_entrenamiento: np.ndarray = np.asarray(y)
        formato_usado = 'directo'
        for objetivo, formato in intentos:
            modelo = build_model(tipo, matriz.shape[1], salidas)
            try:
                if hasattr(modelo, 'fit'):
                    try:
                        modelo.fit(
                            X, objetivo, epochs=epochs, verbose=verbose
                        )
                    except TypeError:
                        modelo.fit(X, objetivo)
                elif hasattr(modelo, 'train'):
                    metodo = 'train'
                    modelo.train(
                        X, objetivo, epochs=epochs, verbose=verbose
                    )
                else:
                    raise TypeError(
                        f"{type(modelo).__name__} no implementa fit/train"
                    )
                y_entrenamiento = objetivo
                formato_usado = formato
                ultimo_error = None
                break
            except Exception as exc:  # noqa: BLE001
                ultimo_error = exc
                continue

        if modelo is None or ultimo_error is not None:
            return {
                'tipo': tipo,
                'clase': (type(modelo).__name__
                          if modelo is not None else 'desconocida'),
                'tarea': tarea,
                'error': (f"{type(ultimo_error).__name__}: {ultimo_error}"
                          if ultimo_error is not None
                          else 'No se pudo entrenar'),
                'exito': False,
            }

        try:
            metricas = modelo.evaluate(X, y_entrenamiento)
        except Exception:
            metricas = modelo.evaluate(X, y)
        resumen = self._resumir_metricas(metricas)
        self._modelos[tipo] = modelo
        return {
            'tipo': tipo,
            'clase': type(modelo).__name__,
            'tarea': tarea,
            'objetivo': formato_usado,
            'metodo': metodo,
            'epochs': int(epochs),
            'tiempo_s': float(time.perf_counter() - inicio),
            'params': int(modelo.params_count())
            if hasattr(modelo, 'params_count') else None,
            'metricas': resumen,
            'score': self._score(resumen),
            'exito': True,
        }

    @staticmethod
    def _resumir_metricas(metricas: Dict[str, Any]) -> Dict[str, Any]:
        resumen: Dict[str, Any] = {}
        for clave, valor in metricas.items():
            if isinstance(valor, (int, float, bool, str)) or valor is None:
                resumen[clave] = valor
            elif isinstance(valor, np.ndarray):
                resumen[clave] = {
                    'shape': list(valor.shape),
                    'dtype': str(valor.dtype),
                }
            else:
                resumen[clave] = str(valor)
        return resumen

    @staticmethod
    def _score(metricas: Dict[str, Any]) -> float:
        if 'accuracy' in metricas:
            return float(metricas['accuracy'])
        if 'r2' in metricas:
            return float(metricas['r2'])
        return float('-inf')

    def calcular_todo(
        self, X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None,
        modelos: Optional[Sequence[str]] = None,
        epochs: int = 40, verbose: bool = False,
        incluir_refuerzo: bool = True,
        incluir_salud: bool = True,
    ) -> Dict[str, Any]:
        """Ejecuta el calculo completo de la red neuronal.

        - Entrena y evalua los modelos RF_SL indicados (por defecto todos).
        - Ejecuta una inferencia de refuerzo ENRN -> RF_EN.
        - Recopila catalogo, salud, metricas, tiempos y mejor modelo.
        - Deja el resultado en ``self.resultado`` y lo devuelve.
        """
        inicio = time.perf_counter()
        resultado: Dict[str, Any] = {
            'version': __version__,
            'timestamp': time.time(),
            'input_size': self.input_size,
            'output_size': self.output_size,
            'catalogo': self.catalogo(),
            'modelos': {},
            'errores': [],
            'refuerzo': None,
            'salud': None,
        }
        if incluir_salud:
            resultado['salud'] = self.salud()

        if X is not None and y is not None:
            tipos = list(modelos) if modelos is not None else list(
                get_available_models()
            )
            for tipo in tipos:
                try:
                    informacion = self.entrenar_modelo(
                        tipo, X, y, epochs=epochs, verbose=verbose
                    )
                except Exception as exc:  # noqa: BLE001
                    informacion = {
                        'tipo': tipo,
                        'exito': False,
                        'error': f"{type(exc).__name__}: {exc}",
                    }
                resultado['modelos'][tipo] = informacion
                if not informacion.get('exito'):
                    resultado['errores'].append({
                        'tipo': tipo,
                        'error': informacion.get('error'),
                    })

            exitosos = {
                tipo: info for tipo, info in resultado['modelos'].items()
                if info.get('exito')
            }
            if exitosos:
                mejor_tipo = max(
                    exitosos,
                    key=lambda tipo: exitosos[tipo].get('score', -np.inf),
                )
                resultado['mejor_modelo'] = {
                    'tipo': mejor_tipo,
                    'score': exitosos[mejor_tipo].get('score'),
                    'metricas': exitosos[mejor_tipo].get('metricas'),
                }
            resultado['resumen_modelos'] = {
                'total': len(resultado['modelos']),
                'exitos': len(exitosos),
                'fallidos': len(resultado['modelos']) - len(exitosos),
            }

        if incluir_refuerzo:
            try:
                accion, diagnostico = self.procesar(None, modo="auto")
                resultado['refuerzo'] = {
                    'exito': True,
                    'accion': np.asarray(accion).ravel().tolist(),
                    'diagnostico': self._resumir_metricas(diagnostico),
                }
            except Exception as exc:  # noqa: BLE001
                resultado['refuerzo'] = {
                    'exito': False,
                    'error': f"{type(exc).__name__}: {exc}",
                }
                resultado['errores'].append({
                    'tipo': 'CELEBRO',
                    'error': resultado['refuerzo']['error'],
                })

        resultado['tiempo_total_s'] = float(
            time.perf_counter() - inicio
        )
        resultado['ok'] = not resultado['errores']
        self._ultimo_resultado = resultado
        return resultado

    def resultado(self) -> Dict[str, Any]:
        """Ultimo resultado completo calculado por ``calcular_todo``."""
        return self._ultimo_resultado

    def guardar_resultado(self, ruta: str) -> str:
        """Guarda el ultimo resultado en JSON (sin arrays no serializables)."""
        if not self._ultimo_resultado:
            raise RuntimeError("No hay resultados: llama a calcular_todo()")
        with open(ruta, 'w', encoding='utf-8') as archivo:
            json.dump(
                self._ultimo_resultado, archivo,
                indent=2, ensure_ascii=False, default=str,
            )
        return os.path.abspath(ruta)

    def reporte(self) -> str:
        """Resumen legible del ultimo calculo completo."""
        if not self._ultimo_resultado:
            return f"{self.nombre} sin calculos"
        resultado = self._ultimo_resultado
        lineas = [
            "=" * 78,
            f" RED NEURONAL LC_STM v{__version__}",
            "=" * 78,
            f"Entrada: {self.input_size} | Salida: {self.output_size}",
        ]
        salud = resultado.get('salud') or {}
        if salud:
            lineas.append(
                "Familias: " + ", ".join(
                    f"{familia}={'OK' if info.get('ok') else 'ERR'}"
                    for familia, info in salud.items()
                )
            )
        else:
            lineas.append("Familias: salud no consultada")
        resumen = resultado.get('resumen_modelos')
        if resumen:
            lineas.append(
                f"Modelos: {resumen['exitos']}/{resumen['total']} OK"
            )
            for tipo, info in resultado.get('modelos', {}).items():
                if info.get('exito'):
                    lineas.append(
                        f"  - {tipo:18s} score={info.get('score'):.4f} "
                        f"tiempo={info.get('tiempo_s', 0):.3f}s"
                    )
                else:
                    lineas.append(f"  - {tipo:18s} ERROR")
        if resultado.get('mejor_modelo'):
            mejor = resultado['mejor_modelo']
            lineas.append(
                f"Mejor modelo: {mejor['tipo']} (score={mejor['score']:.4f})"
            )
        refuerzo = resultado.get('refuerzo') or {}
        if refuerzo.get('exito'):
            lineas.append(
                f"Refuerzo: accion={refuerzo['accion']}"
            )
        lineas.append(
            f"Tiempo total: {resultado.get('tiempo_total_s', 0):.3f}s"
        )
        lineas.append("=" * 78)
        return "\n".join(lineas)

    @property
    def nombre(self) -> str:
        return "RedNeuronal(LC_STM)"

    def __str__(self) -> str:
        return (f"{self.nombre}(ent={self.input_size},"
                f"sal={self.output_size},lat={self.latente_size})")

    def __repr__(self) -> str:
        return self.__str__()


def demo() -> Dict[str, Any]:
    """Demostracion autocontenida del modulo principal."""
    generador = np.random.default_rng(2026)
    n = 240
    X = generador.normal(size=(n, 3))
    y = (
        (X[:, 0] > 0.0).astype(int)
        + (X[:, 1] > 0.0).astype(int)
    )

    red = RedNeuronal(input_size=10, output_size=4, seed=7)
    print("=" * 78)
    print(" LCBS_NEURONAL :: RedNeuronal", red.VERSION)
    print("=" * 78)
    print("Catalogo RF_SL:", red.catalogo()['RF_SL']['modelos'])
    resultado = red.calcular_todo(
        X, y,
        modelos=("linear_regression", "logistic_regression",
                 "decision_tree", "neural_network"),
        epochs=30,
        incluir_salud=False,
        incluir_refuerzo=True,
    )
    print(red.reporte())
    ruta = os.path.join(
        os.getcwd(),
        "LCBS_NEURONAL_resultado.json",
    )
    red.guardar_resultado(ruta)
    print("Resultado guardado en:", ruta)
    red.cerrar()
    return resultado


__all__ = [
    'RedNeuronal',
    'ENRN',
    'RF_EN',
    'RF_SL',
    'RNP',
    'SLRN',
    'build_model',
    'get_available_models',
    'train_all_models',
    'compare_models',
    'quick_train',
    'quick_predict',
    'quick_evaluate',
    'serialize_model',
    'deserialize_model',
    'ModelRegistry',
    'TrainingConfig',
    'MetricsCollector',
    'DataPipeline',
    'NeuronaMemoriaBase',
    'RNPFactory',
    'RNPRegistry',
    'RNPBenchmark',
    'SLRNSystem',
    'SupervisedLearningNeuralConfig',
    'demo',
    '__version__',
]


if __name__ == "__main__":
    demo()
