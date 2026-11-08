"""Puente LucIA ↔ red neuronal para el refactor de código.

Implementa el diseño del comando ``ds ialocal``:

1. **Expediente.** Se reúne el código del archivo, la descripción funcional que
   LucIA hace en lenguaje natural y un README detallado con la deuda técnica de
   *ese* archivo concreto.
2. **Envío.** El expediente viaja al modelo local como contexto; el modelo
   devuelve código candidato.
3. **Aprendizaje.** Las métricas del expediente y del candidato se convierten
   en vectores que la red de ``LC_STM/red_neuronal`` entiende, y la red entrena
   con el par (expediente → calidad).
4. **Escritura.** LucIA puntúa el resultado con su red y, tras el veredicto, es
   ella quien escribe el archivo final (escritura atómica).

Honestidad sobre el alcance: la red **no genera texto**. Lo que aprende es a
*evaluar*: dada la ficha de un archivo, estimar la calidad del refactor. La
generación la hace el modelo local; la decisión y la escritura, LucIA.

La red es :class:`NeuralNetworkOptimizer` de
``LC_STM/red_neuronal/RF_SL/RFSL1/RF_SL1_4.py`` (numpy puro, con
``fit/predict/save/load``). Si ``numpy`` o ``LC_STM`` no están disponibles, el
módulo se declara no disponible y el flujo sigue sin aprendizaje.
"""
from __future__ import annotations

import hashlib
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .stm_base import advertir, informar
from .stm_fragmentos import LIMITE_LINEAS_REFACTOR
from .stm_rutas import DIR_DATOS, ultima_actualizacion_pry

#: Dimensión del vector de entrada (ficha del archivo + descripción).
ALTO = 12
#: Dimensión de salida: fidelidad, limpieza y seguridad del candidato.
SALIDA = 3
#: Muestras mínimas antes de que la red emita un veredicto con criterio.
MIN_PASOS = 8
#: Puntuación mínima para aceptar sin preguntar una vez entrenada.
UMBRAL = 0.55
#: Pesos persistentes de la red de LucIA (fuera de los árboles sincronizados).
RUTA_RED = DIR_DATOS / "lucia_rn.pkl"
#: Carpeta donde se archiva el README de cada expediente procesado.
DIR_EXPEDIENTES = DIR_DATOS / "expedientes"

_CACHE: dict[str, Any] = {"red": None, "error": "", "cargada": False}


# --- Disponibilidad de la red ------------------------------------------------

def _src_pry() -> Optional[Path]:
    """Raíz ``src`` de la última actualización de PRY (donde vive LC_STM)."""
    ultima = ultima_actualizacion_pry()
    if ultima is None:
        return None
    candidata = ultima / "src"
    return candidata if (candidata / "LC_STM").is_dir() else None


def _importar_creador():
    """Importa la fábrica de la red; devuelve ``(creador, error)``."""
    try:
        import numpy as np  # noqa: F401  (comprobación de dependencia)
    except ImportError as error:
        return None, f"numpy no disponible ({error})"
    src = _src_pry()
    if src is None:
        return None, "no hay ninguna actualizacion_* de PRY con LC_STM"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from LC_STM.red_neuronal.RF_SL.RFSL1.RF_SL1_4 import (  # type: ignore[import]
            create_neural_network_optimizer,
        )
    except Exception as error:  # noqa: BLE001 - LC_STM puede no estar completo
        return None, f"LC_STM.red_neuronal no importable ({error})"
    return create_neural_network_optimizer, ""


def disponible() -> bool:
    """True si la red neuronal de LucIA puede usarse."""
    return _importar_creador()[0] is not None


def motivo_no_disponible() -> str:
    """Explicación de por qué no está disponible (vacío si lo está)."""
    return _importar_creador()[1]


def _obtener_red():
    """Instancia (y cachea) la red, cargando los pesos si existen."""
    if _CACHE["cargada"]:
        return _CACHE["red"]
    creador, error = _importar_creador()
    _CACHE["cargada"] = True
    _CACHE["error"] = error
    if creador is None:
        return None
    red = creador(ALTO, SALIDA)
    if RUTA_RED.is_file():
        try:
            red.load(str(RUTA_RED))
        except Exception as fallo:  # noqa: BLE001 - pesos incompatibles
            advertir(f"No se pudo cargar la red de LucIA ({fallo}); se parte de cero.")
    _CACHE["red"] = red
    return red


def _guardar_red(red) -> None:
    """Persiste los pesos de la red (silencioso si falla)."""
    try:
        RUTA_RED.parent.mkdir(parents=True, exist_ok=True)
        red.save(str(RUTA_RED))
    except Exception as error:  # noqa: BLE001 - no debe tumbar el refactor
        advertir(f"No se pudieron guardar los pesos de LucIA ({error}).")


def pasos_aprendidos() -> int:
    """Número de muestras con las que se ha entrenado la red."""
    red = _obtener_red()
    if red is None:
        return 0
    try:
        return int(red.obtener_estadisticas().get("pasos", 0))
    except Exception:  # noqa: BLE001
        return 0


# --- Expediente --------------------------------------------------------------

@dataclass
class Expediente:
    """Ficha completa de un archivo para que LucIA lo refactorice."""

    ruta: Path
    descripcion: str
    readme: str
    deuda: list[str] = field(default_factory=list)
    vector: list[float] = field(default_factory=list)

    @property
    def contexto(self) -> str:
        """Fragmento compacto que se adjunta al prompt del modelo local."""
        deuda = "; ".join(self.deuda[:6]) or "sin hallazgos relevantes"
        descripcion = " ".join(self.descripcion.split())[:400]
        return (f"[CONTEXTO DEL ARCHIVO — según LucIA] {descripcion}\n"
                f"[DEUDA TÉCNICA A RESOLVER] {deuda}\n")


def _norm(valor: float, maximo: float) -> float:
    """Normaliza a [0, 1] con escala logarítmica (los conteos son muy dispares)."""
    if maximo <= 0:
        return 0.0
    return min(1.0, math.log1p(max(valor, 0.0)) / math.log1p(maximo))


def _hash_semantico(texto: str) -> float:
    """Byte de hash normalizado: aproxima el 'tono' del texto de forma estable."""
    if not texto:
        return 0.0
    digest = hashlib.sha256(texto.encode("utf-8", "replace")).digest()
    return digest[0] / 255.0


def deuda_tecnica(analisis) -> list[str]:
    """Lista legible de la deuda técnica concreta de un archivo."""
    deuda: list[str] = []
    if analisis.sintaxis_valida is False:
        deuda.append(f"sintaxis inválida ({analisis.detalle_sintaxis})")
    if analisis.funciones_sin_docstring:
        deuda.append(f"{analisis.funciones_sin_docstring} funciones sin docstring")
    if analisis.except_genericos:
        deuda.append(f"{analisis.except_genericos} capturas de excepción genéricas")
    if analisis.argumentos_mutables:
        deuda.append(f"{analisis.argumentos_mutables} argumentos mutables por defecto")
    if analisis.lineas_largas:
        deuda.append(f"{analisis.lineas_largas} líneas de más de 100 caracteres")
    if analisis.marcadores_pendientes:
        deuda.append(f"{analisis.marcadores_pendientes} marcadores TODO/FIXME")
    if analisis.lineas > LIMITE_LINEAS_REFACTOR:
        deuda.append(f"{analisis.lineas} líneas (tope {LIMITE_LINEAS_REFACTOR}): "
                     "hay que dividirlo")
    if analisis.puntos_decision > 20:
        deuda.append(f"{analisis.puntos_decision} puntos de decisión: "
                     "complejidad alta")
    if not deuda:
        deuda.append("sin hallazgos relevantes: el archivo está sano")
    return deuda


def readme_detallado(ruta: Path, contenido: str, analisis,
                     descripcion: str = "") -> str:
    """README del archivo con su funcionalidad y su deuda técnica.

    Es el documento que se adjunta junto al código para que el modelo local
    entienda qué hace el archivo antes de tocarlo.
    """
    nombre = Path(ruta).name
    lineas = [
        f"# {nombre}", "",
        f"- **Ruta:** `{ruta}`",
        f"- **Tipo:** `{analisis.extension or 'desconocido'}`",
        f"- **Tamaño:** {len(contenido)} caracteres en {analisis.lineas} líneas",
        f"- **Estructura:** {analisis.funciones} funciones, {analisis.clases} clases, "
        f"{analisis.importaciones} importaciones",
        f"- **Complejidad:** {analisis.puntos_decision} puntos de decisión",
        f"- **Sintaxis:** {'válida' if analisis.sintaxis_valida else 'inválida'}",
        "",
        "## Qué hace según LucIA", "",
        descripcion.strip() or "(sin descripción disponible)",
        "",
        "## Deuda técnica", "",
    ]
    lineas += [f"- {item}" for item in deuda_tecnica(analisis)]
    lineas += ["", "## Criterios para el refactor", "",
               "- No cambiar el comportamiento observable.",
               "- Conservar la API pública y los nombres de los símbolos.",
               f"- No superar {LIMITE_LINEAS_REFACTOR} líneas.",
               "- Documentar lo esencial y eliminar duplicación."]
    return "\n".join(lineas) + "\n"


def codificar(ruta: Path, contenido: str, analisis,
              descripcion: str) -> list[float]:
    """Convierte la ficha del archivo en el vector que entiende la red."""
    return [
        _norm(analisis.lineas, 2000),
        _norm(analisis.funciones, 120),
        _norm(analisis.clases, 40),
        _norm(analisis.importaciones, 80),
        _norm(analisis.puntos_decision, 400),
        _norm(analisis.lineas_largas, 400),
        _norm(analisis.marcadores_pendientes, 40),
        _norm(analisis.except_genericos, 40),
        _norm(analisis.funciones_sin_docstring, 120),
        _norm(analisis.argumentos_mutables, 40),
        _norm(len(contenido), 200_000),
        _hash_semantico(descripcion or str(ruta.name)),
    ]


def preparar(ruta: Path, contenido: str, analisis, descripcion: str) -> Expediente:
    """Construye el expediente completo de un archivo."""
    deuda = deuda_tecnica(analisis)
    return Expediente(
        ruta=Path(ruta),
        descripcion=descripcion or "",
        readme=readme_detallado(ruta, contenido, analisis, descripcion),
        deuda=deuda,
        vector=codificar(ruta, contenido, analisis, descripcion),
    )


def guardar_expediente(expediente: Expediente) -> Path:
    """Archiva el README del expediente en ``.modelos/expedientes/``.

    Es el documento con la deuda técnica del archivo concreto que se adjuntó al
    modelo; se guarda fuera de los árboles sincronizados.
    """
    from .stm_fs import escribir_texto_atomico

    destino = DIR_EXPEDIENTES / f"{expediente.ruta.stem}.md"
    try:
        escribir_texto_atomico(destino, expediente.readme)
    except OSError as error:
        advertir(f"No se pudo archivar el expediente ({error}).")
    return destino


# --- Vectores de aprendizaje -------------------------------------------------

def _definiciones(texto: str) -> set[str]:
    """Nombres de funciones y clases del texto (vacío si no es Python válido)."""
    import ast

    try:
        arbol = ast.parse(texto)
    except (SyntaxError, ValueError):
        return set()
    return {nodo.name for nodo in ast.walk(arbol)
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def _metricas_texto(texto: str) -> dict[str, float]:
    """Métricas básicas del código candidato (sin tocar disco)."""
    lineas = texto.splitlines()
    return {
        "lineas": float(len(lineas)),
        "largas": float(sum(len(linea) > 100 for linea in lineas)),
        "vacias": float(sum(not linea.strip() for linea in lineas)),
        "definiciones": float(len(_definiciones(texto))),
    }


def objetivo(original: str, candidato: str) -> list[float]:
    """Vector de calidad del candidato: fidelidad, limpieza y seguridad."""
    defs_original = _definiciones(original)
    defs_candidato = _definiciones(candidato)
    if defs_original:
        conservadas = len(defs_original & defs_candidato)
        fidelidad = conservadas / len(defs_original)
    else:
        fidelidad = 1.0 if candidato.strip() else 0.0
    metricas = _metricas_texto(candidato)
    limpieza = 1.0 - min(1.0, (metricas["largas"] / max(metricas["lineas"], 1)) * 3)
    seguro = 1.0
    if not candidato.strip() or metricas["lineas"] > LIMITE_LINEAS_REFACTOR:
        seguro = 0.0
    elif original.strip() and not defs_candidato and _definiciones(original):
        seguro = 0.0
    return [min(1.0, fidelidad), max(0.0, min(1.0, limpieza)), seguro]


def _puntuacion(red, vector: list[float]) -> tuple[float, int]:
    """Media de la salida de la red ANTES de entrenar con esta muestra."""
    import numpy as np

    try:
        salida = np.asarray(red.predict(np.asarray([vector], dtype=np.float32)))
        return float(np.mean(salida[0])), int(red.obtener_estadisticas().get("pasos", 0))
    except Exception:  # noqa: BLE001 - red recién creada sin forma válida
        return 0.0, 0


def evaluar_y_aprender(expediente: Expediente, candidato: str,
                       original: str) -> dict:
    """Puntúa el candidato con la red y entrena con el resultado.

    Devuelve ``{"disponible", "aceptado", "puntuacion", "pasos", "motivo"}``.
    La puntuación se calcula **antes** de entrenar, para que el veredicto no sea
    circular; después la red aprende del par (expediente → calidad).
    """
    red = _obtener_red()
    if red is None:
        return {"disponible": False, "aceptado": True, "puntuacion": 0.0,
                "pasos": 0, "motivo": _CACHE.get("error") or "red no disponible"}
    import numpy as np

    vector = expediente.vector or [0.0] * ALTO
    calidad = objetivo(original, candidato)
    puntuacion, pasos_previos = _puntuacion(red, vector)
    try:
        red.fit(np.asarray([vector], dtype=np.float32),
                np.asarray([calidad], dtype=np.float32), epochs=1)
        _guardar_red(red)
    except Exception as error:  # noqa: BLE001 - el refactor sigue adelante
        advertir(f"LucIA no pudo entrenar con esta muestra ({error}).")
        return {"disponible": True, "aceptado": True, "puntuacion": puntuacion,
                "pasos": pasos_previos, "motivo": "error de entrenamiento"}
    if pasos_previos < MIN_PASOS:
        return {"disponible": True, "aceptado": True, "puntuacion": puntuacion,
                "pasos": pasos_previos, "motivo":
                f"la red está aprendiendo ({pasos_previos}/{MIN_PASOS} muestras)"}
    aceptado = puntuacion >= UMBRAL
    return {"disponible": True, "aceptado": aceptado, "puntuacion": puntuacion,
            "pasos": pasos_previos,
            "motivo": f"puntuación {puntuacion:.2f} (umbral {UMBRAL:.2f})"}


def estado() -> dict:
    """Resumen del estado de aprendizaje (para diagnóstico)."""
    red = _obtener_red()
    if red is None:
        return {"disponible": False, "motivo": _CACHE.get("error", ""),
                "pesos": str(RUTA_RED), "pasos": 0}
    return {"disponible": True, "motivo": "", "pesos": str(RUTA_RED),
            "pasos": pasos_aprendidos(),
            "arquitectura": f"{ALTO}x{SALIDA}", "umbral": UMBRAL,
            "min_muestras": MIN_PASOS}


def describir() -> str:
    """Línea de estado legible para la consola."""
    datos = estado()
    if not datos["disponible"]:
        return (f"LucIA · red neuronal no disponible ({datos['motivo']}). "
                "El refactor sigue funcionando sin aprendizaje.")
    return (f"LucIA · red neuronal {datos['arquitectura']} · "
            f"{datos['pasos']} muestras · umbral {datos['umbral']} · "
            f"pesos en {datos['pesos']}")
