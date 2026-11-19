"""Codificador semántico real para LucIA mediante *embeddings* locales.

Sustituye la huella de hash por un vector con significado: el expediente
(código + descripción funcional) se embebe con un modelo de embeddings de
Ollama y se **contrae** a unas pocas dimensiones para alimentar la red.

Cadena de detección del modelo:

1. ``RFPRMN_EMBEDDING_MODEL``,
2. ``"embedding_model"`` en ``STM_RFPRMN/.config/opciones.json``,
3. el **más ligero** de los modelos de embeddings instalados.

Se prueban los dos endpoints de Ollama (``/api/embed`` y el heredado
``/api/embeddings``). Si no hay modelo, el servidor no responde o devuelve
error, se informa y LucIA cae en la huella de hash de siempre: el refactor
nunca se rompe por no tener embeddings.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.error
import urllib.request
from typing import Optional

from .stm_analisis import _cargar_configuracion_ia_local
from .stm_rutas import leer_opciones

#: Modelos de embeddings conocidos, de más ligero a más pesado (nombre -> GB).
MODELOS_EMBEDDING: dict[str, float] = {
    "all-minilm": 0.05,
    "nomic-embed-text": 0.27,
    "snowflake-arctic-embed": 0.67,
    "mxbai-embed-large": 0.67,
    "bge-m3": 1.2,
}
#: Dimensiones a las que se contrae el embedding para la red de LucIA.
DIMENSIONES = 8
#: Máximo de texto enviado al modelo (los embeddings truncan de todos modos).
MAX_CARACTERES = 8000
#: Caché de vectores ya calculados (texto corto -> vector).
_CACHE_TEXTO: dict[tuple[str, str], list[float]] = {}
#: Estado de la sonda de capacidades (se calcula una vez por proceso).
_SONDA: dict = {"hecha": False, "ok": False, "modelo": "", "dim": 0, "motivo": ""}


def _afirmativo(valor: object) -> bool:
    if isinstance(valor, str):
        return valor.strip().lower() in {"1", "si", "sí", "s", "y", "yes", "true"}
    return bool(valor)


def modelo_configurado() -> str:
    """Modelo de embeddings pedido por entorno o por opciones (o cadena vacía)."""
    desde_entorno = os.environ.get("RFPRMN_EMBEDDING_MODEL", "").strip()
    if desde_entorno:
        return desde_entorno
    valor = leer_opciones().get("embedding_model")
    return str(valor).strip() if valor else ""


def modelos_instalados() -> set[str]:
    """Nombres de los modelos instalados en Ollama (vacío si no responde)."""
    try:
        endpoint, _ = _cargar_configuracion_ia_local()
        with urllib.request.urlopen(f"{endpoint}/api/tags", timeout=5) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - Ollama puede estar apagado
        return set()
    nombres: set[str] = set()
    for modelo in datos.get("models", []):
        if isinstance(modelo, dict):
            for clave in ("name", "model"):
                nombre = str(modelo.get(clave, "") or "").strip().lower()
                if nombre:
                    nombres.add(nombre)
                    nombres.add(nombre.split(":")[0])
    return nombres


def detectar_modelo() -> str:
    """Modelo de embeddings a usar: el configurado o el más ligero instalado."""
    pedido = modelo_configurado()
    if pedido:
        return pedido
    instalados = modelos_instalados()
    for nombre in sorted(MODELOS_EMBEDDING, key=lambda n: MODELOS_EMBEDDING[n]):
        if nombre in instalados:
            return nombre
    return ""


def _peticion(endpoint: str, ruta: str, carga: dict, timeout: int) -> list[float]:
    """POST a Ollama y devuelve el vector; lanza si no hay embedding."""
    peticion = urllib.request.Request(
        f"{endpoint}{ruta}", data=json.dumps(carga).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
        datos = json.loads(respuesta.read().decode("utf-8"))
    vector = datos.get("embedding")
    if not vector:
        lista = datos.get("embeddings") or []
        vector = lista[0] if lista else None
    if not isinstance(vector, list) or not vector:
        raise ValueError("Ollama no devolvió un embedding válido.")
    return [float(valor) for valor in vector]


def _embeber(endpoint: str, modelo: str, texto: str, timeout: int = 30) -> list[float]:
    """Prueba ``/api/embed`` y, si falla, el endpoint heredado."""
    recorte = texto[:MAX_CARACTERES]
    try:
        return _peticion(endpoint, "/api/embed",
                         {"model": modelo, "input": recorte}, timeout)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, OSError):
        return _peticion(endpoint, "/api/embeddings",
                         {"model": modelo, "prompt": recorte}, timeout)


def estado() -> dict:
    """Estado del codificador semántico (con sonda cacheada)."""
    if _SONDA["hecha"]:
        return dict(_SONDA)
    _SONDA["hecha"] = True
    modelo = detectar_modelo()
    _SONDA["modelo"] = modelo
    if not modelo:
        _SONDA["motivo"] = ("sin modelo de embeddings instalado "
                            "(p. ej. `ollama pull all-minilm`, 46 MB)")
        return dict(_SONDA)
    if modelo not in modelos_instalados():
        _SONDA["motivo"] = (f"el modelo de embeddings '{modelo}' no está "
                            "instalado en Ollama")
        return dict(_SONDA)
    try:
        endpoint, _ = _cargar_configuracion_ia_local()
        vector = _embeber(endpoint, modelo, "sonda de LucIA", timeout=10)
    except Exception as error:  # noqa: BLE001 - se informa y se degrada
        _SONDA["motivo"] = f"Ollama no devolvió embeddings ({error})"
        return dict(_SONDA)
    _SONDA.update({"ok": True, "dim": len(vector), "motivo": ""})
    return dict(_SONDA)


def disponible() -> bool:
    """True si hay un modelo de embeddings utilizable."""
    return bool(estado()["ok"])


def codificar(texto: str) -> Optional[list[float]]:
    """Embedding del texto, o ``None`` si no se puede calcular."""
    datos = estado()
    if not datos["ok"]:
        return None
    clave = (datos["modelo"], hashlib.sha256(texto.encode("utf-8", "replace")).hexdigest())
    if clave in _CACHE_TEXTO:
        return _CACHE_TEXTO[clave]
    try:
        endpoint, _ = _cargar_configuracion_ia_local()
        vector = _embeber(endpoint, datos["modelo"], texto)
    except Exception as error:  # noqa: BLE001 - se degrada a hash
        _SONDA["ok"] = False
        _SONDA["motivo"] = f"fallo al embeber ({error})"
        return None
    if len(_CACHE_TEXTO) >= 64:
        _CACHE_TEXTO.clear()
    _CACHE_TEXTO[clave] = vector
    return vector


def _signo(indice: int) -> float:
    """Signo determinista (paridad Thue-Morse): estable entre procesos."""
    return 1.0 if bin(indice).count("1") % 2 == 0 else -1.0


def contraer(vector: list[float], dims: int = DIMENSIONES) -> list[float]:
    """Contrae un embedding de cualquier dimensión a ``dims`` valores en [0,1].

    *Feature hashing* con signos alternos, normalización L2 y compresión con
    ``tanh``: preserva de forma aproximada las distancias, mantiene un rango
    útil (no todo pegado a 0.5) y no depende de la dimensión del modelo
    (384, 768, 1024...).
    """
    if not vector:
        return [0.5] * dims
    acumulado = [0.0] * dims
    for indice, valor in enumerate(vector):
        acumulado[indice % dims] += _signo(indice) * float(valor)
    norma = math.sqrt(sum(valor * valor for valor in acumulado))
    if norma <= 0.0:
        return [0.5] * dims
    return [0.5 + 0.5 * math.tanh(3.0 * valor / norma) for valor in acumulado]


def describir() -> str:
    """Línea de estado legible del codificador."""
    datos = estado()
    if not datos["ok"]:
        return f"Embeddings: no disponibles ({datos['motivo']}); se usa huella de hash."
    return (f"Embeddings: {datos['modelo']} · {datos['dim']} dimensiones "
            f"contráidas a {DIMENSIONES} para la red de LucIA.")
