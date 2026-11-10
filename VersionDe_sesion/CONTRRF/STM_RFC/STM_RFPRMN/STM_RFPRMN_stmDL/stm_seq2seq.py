"""Puente al subsistema ``LC_STM/seq2seq`` (generar en vez de solo evaluar).

La red de ``red_neuronal`` evalúa; el ``seq2seq`` **recupera** la respuesta que
ya se aprobó para un código equivalente. Este módulo lo conecta con el flujo:

- al aceptar un refactor, el par ``(original → refactorizado)`` se memoriza;
- si las IAs locales fallan y OpenRouter está apagado, se intenta recuperar de
  la memoria antes de darse por vencido.

La memoria vive en ``STM_RFPRMN/.modelos/seq2seq.json``, fuera de los árboles
sincronizados. Si el subsistema no está disponible, todo esto se ignora.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

from .stm_rutas import DIR_DATOS, ultima_actualizacion_pry

#: Memoria de pares original → refactorizado.
RUTA_MEMORIA = DIR_DATOS / "seq2seq.json"
#: Similitud mínima para aceptar una respuesta memorizada.
UMBRAL = 0.90
#: Caché del generador (una sola carga por proceso).
_CACHE: dict = {"generador": None, "error": "", "cargado": False}


def _src_pry():
    """Raíz ``src`` de la última actualización de PRY (donde vive LC_STM)."""
    ultima = ultima_actualizacion_pry()
    if ultima is None:
        return None
    candidata = ultima / "src"
    return candidata if (candidata / "LC_STM" / "seq2seq").is_dir() else None


def _importar():
    """Importa el paquete ``LC_STM.seq2seq``; devuelve ``(modulo, error)``."""
    src = _src_pry()
    if src is None:
        return None, "no hay ninguna actualizacion_* de PRY con LC_STM/seq2seq"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        from LC_STM import seq2seq  # type: ignore[import]
    except Exception as error:  # noqa: BLE001 - puede faltar numpy o el paquete
        return None, f"LC_STM.seq2seq no importable ({error})"
    return seq2seq, ""


def _umbral() -> float:
    """Umbral configurable por ``RFPRMN_SEQ2SEQ_UMBRAL``."""
    try:
        valor = float(os.environ.get("RFPRMN_SEQ2SEQ_UMBRAL", UMBRAL))
    except ValueError:
        return UMBRAL
    return min(max(valor, 0.5), 0.999)


def _generador():
    """Generador cacheado apuntando a la memoria del módulo."""
    if _CACHE["cargado"]:
        return _CACHE["generador"]
    _CACHE["cargado"] = True
    modulo, error = _importar()
    if modulo is None:
        _CACHE["error"] = error
        return None
    try:
        _CACHE["generador"] = modulo.crear(ruta_memoria=str(RUTA_MEMORIA),
                                           umbral=_umbral())
    except Exception as fallo:  # noqa: BLE001 - se degrada sin romper
        _CACHE["error"] = f"no se pudo crear el generador ({fallo})"
        return None
    return _CACHE["generador"]


def disponible() -> bool:
    """True si el subsistema seq2seq puede usarse."""
    return _generador() is not None


def motivo_no_disponible() -> str:
    """Explicación cuando no está disponible (vacío si lo está)."""
    _generador()
    return _CACHE["error"]


def aprender(original: str, refactorizado: str) -> bool:
    """Memoriza el par ``original → refactorizado``; True si se guardó."""
    generador = _generador()
    if generador is None or not original.strip() or not refactorizado.strip():
        return False
    try:
        generador.aprender(original, refactorizado, {"origen": "ds_ialocal"})
        generador.guardar()
    except Exception:  # noqa: BLE001 - el aprendizaje no debe romper el flujo
        return False
    return True


def generar(original: str) -> Optional[str]:
    """Código refactorizado memorizado para ``original`` (o ``None``)."""
    generador = _generador()
    if generador is None or not original.strip():
        return None
    resultado = generador.intentar_generar(original)
    return resultado.texto if resultado else None


def estado() -> dict:
    """Resumen del subsistema para diagnósticos."""
    generador = _generador()
    if generador is None:
        return {"disponible": False, "motivo": _CACHE["error"],
                "memoria": str(RUTA_MEMORIA), "pares": 0}
    datos = generador.estado()
    datos.update({"disponible": True, "motivo": "", "memoria": str(RUTA_MEMORIA)})
    return datos


def describir() -> str:
    """Línea de estado legible."""
    datos = estado()
    if not datos["disponible"]:
        return f"Seq2Seq: no disponible ({datos['motivo']})."
    return (f"Seq2Seq: {datos['pares']} pares memorizados · umbral "
            f"{datos['umbral']} · memoria en {datos['memoria']}")


def olvidar() -> bool:
    """Vacía la memoria de pares (para empezar de cero)."""
    generador = _generador()
    if generador is None:
        return False
    generador.memoria.vaciar()
    try:
        generador.guardar()
    except Exception:  # noqa: BLE001
        return False
    return True
