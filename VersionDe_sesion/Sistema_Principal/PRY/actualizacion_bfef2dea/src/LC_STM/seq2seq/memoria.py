"""Memoria de pares del seq2seq: petición → respuesta aceptada.

Persistencia en JSON (con los vectores como listas) para no depender de numpy
ni de formatos binarios. La memoria es lo que "aprende" el sistema: cada par
guardado es una respuesta que alguien dio por buena.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ._base import ErrorSeq2Seq
from .vectorizador import similitud_coseno


class MemoriaPares:
    """Colección acotada de pares con búsqueda por similitud."""

    def __init__(self, max_pares: int = 512) -> None:
        self.max_pares = max(1, int(max_pares))
        self._pares: list[dict[str, Any]] = []

    def __len__(self) -> int:
        return len(self._pares)

    def agregar(self, peticion: str, respuesta: str, vector: list[float],
                meta: dict | None = None) -> None:
        """Guarda un par; si la petición ya existe, actualiza la respuesta."""
        if not respuesta.strip():
            raise ErrorSeq2Seq("No se guarda una respuesta vacía.")
        clave = peticion.strip()
        for par in self._pares:
            if par["peticion"] == clave:
                par.update({"respuesta": respuesta, "vector": list(vector),
                            "meta": dict(meta or {}), "fecha": _ahora()})
                return
        self._pares.append({
            "peticion": clave,
            "respuesta": respuesta,
            "vector": [float(valor) for valor in vector],
            "meta": dict(meta or {}),
            "fecha": _ahora(),
        })
        if len(self._pares) > self.max_pares:
            self._pares = self._pares[-self.max_pares:]

    def buscar(self, vector: list[float], k: int = 3) -> list[tuple[float, dict]]:
        """Los ``k`` pares más parecidos, de mayor a menor similitud."""
        puntuados = [(similitud_coseno(vector, par["vector"]), par)
                     for par in self._pares]
        puntuados.sort(key=lambda item: item[0], reverse=True)
        return puntuados[:max(1, int(k))]

    def pares(self) -> list[dict]:
        """Copia de los pares guardados (texto y metadatos)."""
        return [dict(par) for par in self._pares]

    def vaciar(self) -> None:
        """Elimina todos los pares."""
        self._pares.clear()

    def guardar(self, ruta: str | Path | None) -> Path | None:
        """Escribe la memoria en JSON (sin escribir si ``ruta`` es ``None``)."""
        if not ruta:
            return None
        destino = Path(ruta)
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_name(destino.name + ".tmp")
            temporal.write_text(json.dumps(self._pares, ensure_ascii=False),
                                encoding="utf-8")
            os.replace(temporal, destino)
        except OSError as error:
            raise ErrorSeq2Seq(f"No se pudo guardar la memoria ({error}).") from error
        return destino

    def cargar(self, ruta: str | Path | None) -> int:
        """Carga la memoria si el archivo existe; devuelve cuántos pares leyó."""
        if not ruta:
            return 0
        origen = Path(ruta)
        if not origen.is_file():
            return 0
        try:
            datos = json.loads(origen.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ErrorSeq2Seq(f"Memoria ilegible ({error}).") from error
        if not isinstance(datos, list):
            raise ErrorSeq2Seq("La memoria no tiene el formato esperado.")
        validos = [par for par in datos
                   if isinstance(par, dict) and par.get("respuesta")
                   and isinstance(par.get("vector"), list)]
        self._pares = validos[-self.max_pares:]
        return len(self._pares)


def _ahora() -> str:
    """Marca temporal ISO (segundos)."""
    return time.strftime("%Y-%m-%dT%H:%M:%S")
