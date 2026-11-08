"""Evaluación objetiva de un candidato de refactor.

Aquí vive todo lo que convierte código en números: la parte semántica del
vector (embeddings o huella de hash como respaldo), la codificación del
candidato y la puntuación de calidad que usa la red de LucIA.

Se separó de ``stm_lucia`` para que el aprendizaje y la evaluación no crezcan
en el mismo archivo (tope de 450 líneas).
"""
from __future__ import annotations

import ast
import hashlib
import math

from .stm_embeddings import DIMENSIONES, contraer
from .stm_embeddings import codificar as embeber
from .stm_fragmentos import LIMITE_LINEAS_REFACTOR


def _norm(valor: float, maximo: float) -> float:
    """Normaliza a [0, 1] con escala logarítmica (los conteos son muy dispares)."""
    if maximo <= 0:
        return 0.0
    return min(1.0, math.log1p(max(valor, 0.0)) / math.log1p(maximo))


def _vector_hash(texto: str, dims: int = DIMENSIONES) -> list[float]:
    """Respaldo determinista cuando no hay embeddings (``dims`` valores en [0,1])."""
    digest = hashlib.sha256(texto.encode("utf-8", "replace")).digest()
    return [int.from_bytes(digest[k * 4:(k + 1) * 4], "big") / 0xFFFFFFFF
            for k in range(min(dims, 8))]


def _semantico(texto: str) -> list[float]:
    """Parte semántica del vector: embedding real o huella de hash como respaldo."""
    vector = embeber(texto)
    if vector:
        return contraer(vector)
    return _vector_hash(texto)


def definiciones(texto: str) -> set[str]:
    """Nombres de funciones y clases del texto (vacío si no es Python válido)."""
    try:
        arbol = ast.parse(texto)
    except (SyntaxError, ValueError):
        return set()
    return {nodo.name for nodo in ast.walk(arbol)
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def metricas_texto(texto: str) -> dict[str, float]:
    """Métricas básicas del código candidato (sin tocar disco)."""
    lineas = texto.splitlines()
    total = max(len(lineas), 1)
    documentadas = 0
    comentarios = sum(1 for linea in lineas if linea.strip().startswith("#"))
    try:
        arbol = ast.parse(texto)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if ast.get_docstring(nodo):
                    documentadas += 1
    except (SyntaxError, ValueError):
        pass
    return {
        "lineas": float(len(lineas)),
        "largas": float(sum(len(linea) > 100 for linea in lineas)),
        "vacias": float(sum(not linea.strip() for linea in lineas)),
        "definiciones": float(len(definiciones(texto))),
        "documentadas": float(documentadas),
        "comentarios": comentarios / total,
    }


def codificar_candidato(candidato: str) -> list[float]:
    """Vector del código propuesto: estructura + embedding del propio candidato.

    Sin esto la red solo vería el expediente y no podría distinguir dos
    versiones del mismo archivo.
    """
    metricas = metricas_texto(candidato)
    total_definiciones = max(metricas["definiciones"], 1.0)
    return [
        _norm(metricas["lineas"], 2000),
        _norm(metricas["largas"], 400),
        min(1.0, metricas["documentadas"] / total_definiciones),
        min(1.0, metricas["comentarios"] * 10),
    ] + _semantico(candidato[:4000])


def objetivo(original: str, candidato: str) -> list[float]:
    """Vector de calidad del candidato: fidelidad, limpieza y seguridad."""
    defs_original = definiciones(original)
    defs_candidato = definiciones(candidato)
    if defs_original:
        conservadas = len(defs_original & defs_candidato)
        fidelidad = conservadas / len(defs_original)
    else:
        fidelidad = 1.0 if candidato.strip() else 0.0
    metricas = metricas_texto(candidato)
    largas = min(1.0, (metricas["largas"] / max(metricas["lineas"], 1)) * 3)
    documentadas = metricas["documentadas"] / max(metricas["definiciones"], 1.0)
    # La documentación forma parte de la limpieza: un refactor que borra los
    # docstrings empeora, aunque el resto no cambie.
    limpieza = 0.75 * (1.0 - largas) + 0.25 * documentadas
    seguro = 1.0
    if not candidato.strip() or metricas["lineas"] > LIMITE_LINEAS_REFACTOR:
        seguro = 0.0
    elif original.strip() and not defs_candidato and defs_original:
        seguro = 0.0
    return [min(1.0, fidelidad), max(0.0, min(1.0, limpieza)), seguro]


def calidad(original: str, candidato: str) -> float:
    """Puntuación única: 50 % fidelidad, 30 % limpieza, 20 % seguridad."""
    fidelidad, limpieza, seguridad = objetivo(original, candidato)
    return round(0.5 * fidelidad + 0.3 * limpieza + 0.2 * seguridad, 4)
