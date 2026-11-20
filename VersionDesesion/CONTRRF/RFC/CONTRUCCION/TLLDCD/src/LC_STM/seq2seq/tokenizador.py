"""Tokenizador ligero para código y lenguaje natural.

No hay vocabulario entrenado: se tokeniza por expresiones regulares pensadas
para código (identificadores, números, operadores, cadenas) más palabras del
lenguaje natural de la descripción. Es determinista y no gasta memoria.
"""
from __future__ import annotations

import re

#: Identificadores y palabras (incluye acentos), números, operadores y saltos.
_PATRON = re.compile(
    r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ_][A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ_]*"  # identificadores
    r"|\d+(?:\.\d+)?"                                        # números
    r"|==|!=|<=|>=|->|=>|::|&&|\|\||[+\-*/%=<>!&|^~?:;,.(){}\[\]]"
    r"|\n",
)


class Tokenizador:
    """Convierte texto en una lista de tokens (sin normalizar a minúsculas)."""

    def __init__(self, minusculas: bool = True, min_longitud: int = 1) -> None:
        self.minusculas = minusculas
        self.min_longitud = max(1, int(min_longitud))

    def tokenizar(self, texto: str) -> list[str]:
        """Lista de tokens de ``texto`` (vacía si no hay nada)."""
        if not texto:
            return []
        tokens = _PATRON.findall(texto)
        if self.minusculas:
            tokens = [token.lower() for token in tokens]
        return [token for token in tokens if len(token) >= self.min_longitud]

    def a_texto(self, tokens: list[str]) -> str:
        """Reconstruye un texto legible a partir de tokens."""
        salida = []
        for token in tokens:
            if token == "\n":
                salida.append("\n")
            elif token in "),.;:]}":
                salida.append(token)
            elif salida and salida[-1] not in ("\n", "(", "[", "{"):
                salida.append(" " + token)
            else:
                salida.append(token)
        return "".join(salida)

    def vocabulario(self, textos: list[str]) -> list[str]:
        """Vocabulario ordenado por frecuencia de los textos dados."""
        from collections import Counter

        contador: Counter[str] = Counter()
        for texto in textos:
            contador.update(self.tokenizar(texto))
        return [token for token, _ in contador.most_common()]
