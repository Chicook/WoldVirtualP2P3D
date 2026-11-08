"""Semilla de entrenamiento de la red de LucIA con código real.

No hay corpus de refactorizaciones humanas, así que la semilla se construye con
lo que sí existe: los archivos reales del proyecto. Para cada uno se generan
**dos muestras con el mismo expediente y candidatos distintos**:

- el archivo tal cual (documentado),
- el mismo código sin docstrings (``_sin_documentacion``).

La etiqueta sale de las métricas objetivas (``stm_lucia.calidad``), no de una
refactorización inventada. Es una semilla honesta: enseña a la red que la
documentación y la estructura pesan, y la deja fuera del estado «aprendiendo».
"""
from __future__ import annotations

import ast
from pathlib import Path

from .stm_analisis import analizar_archivo_local
from .stm_lucia import (
    MIN_PASOS, _entrada, _guardar_red, _obtener_red, calidad, pasos_aprendidos,
    preparar,
)


def descripcion_breve(contenido: str, ruta: Path) -> str:
    """Primera línea del docstring del módulo (o el nombre del archivo)."""
    try:
        documento = ast.get_docstring(ast.parse(contenido)) or ""
    except (SyntaxError, ValueError):
        documento = ""
    primera = (documento.strip().splitlines() or [""])[0].strip()
    return primera or f"Archivo {Path(ruta).name}"


def sin_documentacion(texto: str) -> str:
    """Copia del código sin docstrings (muestra negativa del corpus)."""
    try:
        arbol = ast.parse(texto)
    except (SyntaxError, ValueError):
        return texto
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        cuerpo = list(getattr(nodo, "body", []) or [])
        if not cuerpo:
            continue
        primero = cuerpo[0]
        valor = getattr(primero, "value", None)
        if (isinstance(primero, ast.Expr) and isinstance(valor, ast.Constant)
                and isinstance(valor.value, str)):
            nodo.body = cuerpo[1:] or [ast.Pass()]
    try:
        return ast.unparse(arbol) + "\n"
    except Exception:  # noqa: BLE001 - se usa el texto original
        return texto


def sembrar_corpus(carpeta: Path, limite: int = 12) -> dict:
    """Entrena la red con archivos reales de ``carpeta`` (sin llamar a la IA).

    Devuelve ``{"disponible", "muestras", "archivos", "pasos", "pesos", "motivo"}``.
    """
    red = _obtener_red()
    if red is None:
        return {"disponible": False, "muestras": 0, "pasos": 0,
                "motivo": "red no disponible"}
    import numpy as np

    archivos = [ruta for ruta in sorted(Path(carpeta).rglob("*.py"))
                if ruta.is_file() and ruta.stat().st_size < 200_000][:limite]
    entradas: list[list[float]] = []
    notas: list[list[float]] = []
    usados = 0
    for ruta in archivos:
        try:
            contenido = ruta.read_text(encoding="utf-8-sig", errors="replace")
            analisis = analizar_archivo_local(ruta)
        except OSError:
            continue
        expediente = preparar(ruta, contenido, analisis,
                              descripcion_breve(contenido, ruta))
        for candidato in (contenido, sin_documentacion(contenido)):
            entradas.append(_entrada(expediente, candidato))
            notas.append([calidad(contenido, candidato)])
        usados += 1
    if not entradas:
        return {"disponible": True, "muestras": 0, "archivos": 0,
                "pasos": pasos_aprendidos(), "pesos": "", "motivo":
                "no se encontraron archivos válidos"}
    try:
        # ``pasos`` de la red cuenta pasadas de entrenamiento, así que se usan
        # las mínimas para que la semilla deje la red fuera de "aprendiendo".
        red.fit(np.asarray(entradas, dtype=np.float32),
                np.asarray(notas, dtype=np.float32), epochs=MIN_PASOS)
        _guardar_red(red)
    except Exception as error:  # noqa: BLE001 - se informa sin romper
        return {"disponible": True, "muestras": 0, "archivos": usados,
                "pasos": pasos_aprendidos(), "pesos": "",
                "motivo": f"error de entrenamiento ({error})"}
    return {"disponible": True, "muestras": len(entradas), "archivos": usados,
            "pasos": pasos_aprendidos(), "pesos": "", "motivo": ""}
