"""Codificador de texto a vector (*feature hashing* de tokens).

Es el "encoder" del seq2seq: no aprende embeddings, los **cuenta**. Cada token
se proyecta de forma determinista en ``dims`` posiciones con signo, se acumula
y se normaliza a norma 1. Dos peticiones parecidas quedan cerca en coseno, que
es justo lo que necesita el decodificador para recuperar.
"""
from __future__ import annotations

import hashlib
import math

from .tokenizador import Tokenizador


class Vectorizador:
    """Vectoriza texto con hashing de tokens (numpy si está, si no listas)."""

    def __init__(self, dims: int = 256, tokenizador: Tokenizador | None = None) -> None:
        self.dims = max(8, int(dims))
        self.tokenizador = tokenizador or Tokenizador()

    def _indice(self, token: str) -> tuple[int, float]:
        """Posición y signo deterministas de un token."""
        digest = hashlib.sha256(token.encode("utf-8", "replace")).digest()
        posicion = int.from_bytes(digest[:4], "big") % self.dims
        signo = 1.0 if digest[4] % 2 == 0 else -1.0
        return posicion, signo

    def vector(self, texto: str) -> list[float]:
        """Vector normalizado de ``texto`` (lista de ``dims`` floats)."""
        valores = [0.0] * self.dims
        tokens = self.tokenizador.tokenizar(texto)
        if not tokens:
            return valores
        for token in tokens:
            posicion, signo = self._indice(token)
            valores[posicion] += signo
        norma = math.sqrt(sum(valor * valor for valor in valores))
        if norma <= 0.0:
            return valores
        return [valor / norma for valor in valores]

    def a_numpy(self, texto: str):
        """Vector como ``numpy.ndarray`` (float32) si numpy está disponible."""
        try:
            import numpy as np
        except ImportError:  # pragma: no cover - numpy es dependencia del proyecto
            return self.vector(texto)
        return np.asarray(self.vector(texto), dtype=np.float32)


def similitud_coseno(a, b) -> float:
    """Similitud de coseno entre dos vectores ya normalizados (0.0 si falla)."""
    if a is None or b is None or len(a) != len(b) or not len(a):
        return 0.0
    producto = sum(float(x) * float(y) for x, y in zip(a, b))
    norma_a = math.sqrt(sum(float(x) * float(x) for x in a))
    norma_b = math.sqrt(sum(float(y) * float(y) for y in b))
    if norma_a <= 0.0 or norma_b <= 0.0:
        return 0.0
    return max(-1.0, min(1.0, producto / (norma_a * norma_b)))
