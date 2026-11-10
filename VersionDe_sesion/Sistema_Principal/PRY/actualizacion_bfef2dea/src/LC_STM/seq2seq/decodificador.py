"""Decodificador: del vector de búsqueda a la respuesta aceptada.

No inventa: elige entre lo que ya se aprobó. Si nada supera el umbral de
similitud, **se niega** — devolver código inventado sería peor que no devolver
nada, porque el flujo lo escribiría en un archivo del proyecto.
"""
from __future__ import annotations

from typing import Any

from ._base import ConfigSeq2Seq, ErrorSeq2Seq
from .memoria import MemoriaPares


class Decodificador:
    """Decoder del seq2seq: vecino más cercano sobre la memoria de pares."""

    def __init__(self, configuracion: ConfigSeq2Seq | None = None) -> None:
        self.config = configuracion or ConfigSeq2Seq()

    def decodificar(self, vector: list[float],
                    memoria: MemoriaPares) -> tuple[str, float, dict[str, Any]]:
        """Devuelve ``(respuesta, similitud, meta)`` o lanza ``ErrorSeq2Seq``."""
        if not len(memoria):
            raise ErrorSeq2Seq("La memoria está vacía: no hay respuestas aprendidas.")
        candidatos = memoria.buscar(vector, k=3)
        if not candidatos:
            raise ErrorSeq2Seq("No hay candidatos en la memoria.")
        similitud, mejor = candidatos[0]
        if similitud < self.config.umbral:
            raise ErrorSeq2Seq(
                f"Ninguna respuesta se parece lo suficiente "
                f"(mejor similitud {similitud:.2f} < umbral {self.config.umbral:.2f}).")
        meta = dict(mejor.get("meta") or {})
        meta["segunda_opcion"] = round(candidatos[1][0], 4) if len(candidatos) > 1 else 0.0
        return str(mejor["respuesta"]), float(similitud), meta
