"""Troceado seguro de código en fragmentos para la IA local (issue #80).

Un fragmento mal cortado es la causa de la mayoría de refactors inválidos:
si el corte cae entre la cabecera de un ``def`` y su cuerpo, la IA recibe
código que no compila y devuelve basura. Aquí el corte se calcula así:

- ``.py`` parseable: se corta en **fronteras de sentencias de nivel superior**
  usando el AST, de modo que cada fragmento contiene sentencias completas.
- Resto (u origen no parseable): corte por líneas con profundidad de paréntesis
  cero y solo antes de una cabecera de bloque; en Python se excluyen
  ``else``/``elif``/``except``/``finally`` porque continúan el bloque anterior.
"""
from __future__ import annotations

import ast
import re
from typing import Optional

#: Cabeceras que abren un bloque: cortar antes de una deja ambos lados cerrados.
_INICIO_BLOQUE = re.compile(
    r"^(?:async\s+def|def|class|@|if|for|while|try|with|switch|public|private|"
    r"protected|internal|namespace|function)\b"
)
#: En Python estas palabras continúan el bloque anterior: nunca se corta antes.
_CONTINUACION_PY = re.compile(r"^(?:else|elif|except|finally)\b")
#: Máximo de líneas comparadas al deduplicar el solape.
MAX_SOLAPE = 20


def _delta_profundidad(linea: str) -> int:
    """Paréntesis/corchetes/llaves netos de ``linea``, ignorando cadenas."""
    delta, i, n = 0, 0, len(linea)
    comilla = ""
    while i < n:
        caracter = linea[i]
        if comilla:
            if caracter == "\\":
                i += 2
                continue
            if caracter == comilla:
                comilla = ""
        elif caracter in "\"'":
            comilla = caracter
        elif caracter == "#":
            break
        elif caracter in "([{":
            delta += 1
        elif caracter in ")]}":
            delta -= 1
        i += 1
    return delta


def _rangos_por_ast(contenido: str, minimo: int) -> Optional[list[tuple[int, int]]]:
    """Corta en fronteras de sentencias de nivel superior (1-based, contiguo).

    Cada rango contiene sentencias completas, así que siempre es válido por sí
    mismo. Devuelve ``None`` si el fuente no es Python parseable.
    """
    try:
        arbol = ast.parse(contenido)
    except (SyntaxError, ValueError):
        return None
    if not arbol.body:
        return None
    total = len(contenido.splitlines())
    rangos: list[tuple[int, int]] = []
    inicio = 1
    for nodo in arbol.body:
        fin = getattr(nodo, "end_lineno", None) or nodo.lineno
        if fin - inicio + 1 >= minimo:
            rangos.append((inicio, fin))
            inicio = fin + 1
    if inicio <= total:
        rangos.append((inicio, total))
    return rangos or None


def _rangos_heuristicos(contenido: str, minimo: int,
                        extension: str) -> list[tuple[int, int]]:
    """Corte por líneas cuando no hay AST (otros lenguajes o Python roto)."""
    lineas = contenido.splitlines()
    if not lineas:
        return []
    rangos: list[tuple[int, int]] = []
    inicio, profundidad = 1, 0
    for numero, linea in enumerate(lineas, start=1):
        limpia = linea.strip()
        es_python = extension == ".py"
        cabeceo = bool(_INICIO_BLOQUE.match(limpia)) and not (
            es_python and _CONTINUACION_PY.match(limpia))
        if profundidad == 0 and numero - inicio + 1 >= minimo and cabeceo:
            rangos.append((inicio, numero - 1))
            inicio = numero
        profundidad += _delta_profundidad(linea)
    rangos.append((inicio, len(lineas)))
    return [rango for rango in rangos if rango[1] >= rango[0]]


def calcular_rangos(contenido: str, extension: str,
                    minimo: int) -> list[tuple[int, int]]:
    """Rangos ``(inicio, fin)`` 1-based de los fragmentos del archivo."""
    if not contenido.strip():
        return []
    if extension == ".py":
        rangos = _rangos_por_ast(contenido, minimo)
        if rangos:
            return rangos
    return _rangos_heuristicos(contenido, minimo, extension)


def quitar_solape(previo: str, actual: str, maximo: int = MAX_SOLAPE) -> str:
    """Elimina del inicio de ``actual`` las líneas que ya cierran ``previo``.

    Evita duplicar el bloque de contexto cuando el modelo lo repite. Exige al
    menos dos líneas coincidentes para no recortar código legítimo.
    """
    if not previo or not actual:
        return actual
    nuevas, antiguas = actual.splitlines(), previo.splitlines()
    for k in range(min(len(nuevas), len(antiguas), maximo), 1, -1):
        if [linea.rstrip() for linea in nuevas[:k]] == [linea.rstrip()
                                                        for linea in antiguas[-k:]]:
            return "\n".join(nuevas[k:])
    return actual
