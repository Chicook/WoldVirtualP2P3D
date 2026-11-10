"""Codificador: de la petición (código + descripción) al vector de búsqueda."""
from __future__ import annotations

from ._base import ConfigSeq2Seq, ErrorSeq2Seq
from .vectorizador import Vectorizador


class Codificador:
    """Encoder del seq2seq: texto libre → vector normalizado."""

    def __init__(self, configuracion: ConfigSeq2Seq | None = None) -> None:
        self.config = configuracion or ConfigSeq2Seq()
        self.vectorizador = Vectorizador(self.config.dims)

    def codificar(self, peticion: str) -> list[float]:
        """Vector de la petición (recortada a ``max_caracteres``)."""
        if not peticion or not peticion.strip():
            raise ErrorSeq2Seq("La petición está vacía: no hay nada que codificar.")
        recorte = peticion[: self.config.max_caracteres]
        return self.vectorizador.vector(recorte)

    def tokens(self, peticion: str) -> list[str]:
        """Tokens usados por el codificador (para diagnósticos)."""
        return self.vectorizador.tokenizador.tokenizar(peticion)
