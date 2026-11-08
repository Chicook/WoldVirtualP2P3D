"""Partición de un módulo que supera el tope de 450 líneas.

Es la solución al problema recurrente: el modelo genera (o refactoriza) un
``.py`` de más de 450 líneas y el presupuesto del proyecto lo rechaza. Aquí se
corta por **unidades de nivel superior** (clases, funciones y bloques), nunca a
mitad de una definición:

1. La cabecera (docstring + imports) se repite en cada parte.
2. La **parte 1** se queda en el archivo original, hasta el límite.
3. El resto se reparte en ``<nombre>_p2.py``, ``_p3.py``… que se escriben como
   **subsistemas** en ``ENRN/STM_SBSISTEMA``.
4. La parte 1 re-exporta los subsistemas (añade su carpeta a ``sys.path``), así
   los nombres siguen disponibles desde el módulo original.
5. Se escribe un informe ``particion_<nombre>.md`` con el reparto.

Si una sola unidad no cabe en 450 líneas, no se puede partir sin tocarla: se
deja en su parte, se avisa y se anota como problema.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

from .stm_base import (
    ErrorProyecto, _imprimir_seguro, _panel, advertir, exito, informar,
    pedir_confirmacion, reportar_error,
)
from .stm_fragmentos import LIMITE_LINEAS_REFACTOR
from .stm_fs import escribir_texto_atomico

#: Ruta relativa al árbol donde viven los subsistemas (desde CONTRUCCION).
SUBSISTEMA_REL = "../TLLDCD/src/LC_STM/red_neuronal/ENRN/STM_SBSISTEMA"
#: Líneas que ocupa el bloque de importación de subsistemas en la parte 1.
BOOTSTRAP = 7


def _texto(contenido: str, nodo) -> str:
    """Código fuente exacto de un nodo (sin líneas vacías en los extremos)."""
    return (ast.get_source_segment(contenido, nodo) or "").strip("\n")


def _es_docstring(nodo) -> bool:
    """True si el nodo es el docstring del módulo."""
    return (isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Constant)
            and isinstance(nodo.value.value, str))


def _es_import(nodo) -> bool:
    """True para ``import`` y ``from ... import ...``."""
    return isinstance(nodo, (ast.Import, ast.ImportFrom))


def _nombre(nodo) -> str:
    """Nombre legible de una unidad (o ``bloque_<línea>`` si es una asignación)."""
    if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return nodo.name
    return f"bloque_{getattr(nodo, 'lineno', 0)}"


def _tipo(nodo) -> str:
    """Clase, función, import o bloque."""
    if isinstance(nodo, ast.ClassDef):
        return "clase"
    if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return "funcion"
    return "bloque"


def separar_unidades(contenido: str) -> tuple[str, list[dict]]:
    """Devuelve ``(cabecera, unidades)`` del módulo; lanza si no es Python válido."""
    try:
        arbol = ast.parse(contenido)
    except SyntaxError as error:
        raise ErrorProyecto(f"Sintaxis inválida (línea {error.lineno}: {error.msg}).")
    cabecera: list[str] = []
    unidades: list[dict] = []
    for nodo in arbol.body:
        if _es_docstring(nodo) or _es_import(nodo):
            cabecera.append(_texto(contenido, nodo))
            continue
        texto = _texto(contenido, nodo)
        unidades.append({"nombre": _nombre(nodo), "tipo": _tipo(nodo),
                         "lineas": len(texto.splitlines()), "texto": texto})
    return "\n".join(cabecera), unidades


def _empaquetar(cabecera: str, unidades: list[dict], limite: int,
                reserva: int = BOOTSTRAP) -> list[list[dict]]:
    """Reparte las unidades en partes que quepan en ``limite`` líneas."""
    coste_cabecera = len(cabecera.splitlines()) + 4
    partes: list[list[dict]] = [[]]
    usadas = 0
    for unidad in unidades:
        capacidad = limite - coste_cabecera - (reserva if not partes[1:] else 0)
        extra = unidad["lineas"] + 2
        if partes[-1] and usadas + extra > capacidad:
            partes.append([])
            usadas = 0
            capacidad = limite - coste_cabecera
        partes[-1].append(unidad)
        usadas += extra
    return partes


def plan_de_particion(contenido: str, limite: int = LIMITE_LINEAS_REFACTOR) -> dict:
    """Calcula cómo quedaría el módulo sin escribir nada."""
    cabecera, unidades = separar_unidades(contenido)
    if not unidades:
        raise ErrorProyecto("El archivo no tiene clases ni funciones que repartir.")
    total = len(contenido.splitlines())
    if total <= limite:
        return {"necesita": False, "total": total, "cabecera": cabecera,
                "unidades": unidades, "partes": [unidades], "problemas": []}
    partes = _empaquetar(cabecera, unidades, limite)
    # El bloque de subsistemas crece con el número de partes: se reserva de más
    # y, si cambia el reparto, se recalcula una vez.
    reserva = 6 + max(1, len(partes) - 1)
    if reserva != BOOTSTRAP:
        partes = _empaquetar(cabecera, unidades, limite, reserva)
    coste = len(cabecera.splitlines()) + 4
    problemas = [unidad["nombre"] for parte in partes for unidad in parte
                 if unidad["lineas"] + coste > limite]
    return {"necesita": True, "total": total, "cabecera": cabecera,
            "unidades": unidades, "partes": partes, "problemas": problemas}


def _bloque_subsistemas(stem: str, indices: list[int]) -> str:
    """Código que re-exporta los subsistemas desde la parte 1."""
    lineas = ["", "# --- Subsistemas: resto del código extraído automáticamente ---",
              "import sys as _sys",
              "from pathlib import Path as _Path",
              f'_subs = _Path(__file__).resolve().parent / "{SUBSISTEMA_REL}"',
              "if _subs.is_dir() and str(_subs) not in _sys.path:",
              "    _sys.path.insert(0, str(_subs))"]
    lineas += [f"from {stem}_p{indice} import *  # noqa: F401,F403"
               for indice in indices]
    return "\n".join(lineas) + "\n"


def _componente_principal(cabecera: str, unidades: list[dict],
                          stem: str, indices: list[int]) -> str:
    """Texto del archivo original: cabecera + primeras unidades + subsistemas."""
    piezas = [cabecera] if cabecera else []
    piezas += [unidad["texto"] for unidad in unidades]
    cuerpo = "\n\n\n".join(piezas).rstrip() + "\n"
    if indices:
        cuerpo += _bloque_subsistemas(stem, indices)
    return cuerpo


def _informe(ruta: Path, destino: Path, partes: list[list[dict]],
             problemas: list[str]) -> str:
    """Markdown con el reparto, para no perder de vista qué se movió."""
    filas = ["| Parte | Archivo | Unidades | Líneas |", "|---|---|---|---:|"]
    filas.append(f"| 1 | `{ruta.name}` | {len(partes[0])} | (ver archivo) |")
    for indice, parte in enumerate(partes[1:], start=2):
        filas.append(f"| {indice} | `{destino / f'{ruta.stem}_p{indice}.py'}` | "
                     f"{len(parte)} | {sum(u['lineas'] + 2 for u in parte)} |")
    detalle = [f"- p{indice}: " + ", ".join(u["nombre"] for u in parte)
               for indice, parte in enumerate(partes[1:], start=2)]
    aviso = ("\n## Problemas\n" + "\n".join(f"- `{n}` no cabe en {LIMITE_LINEAS_REFACTOR} "
                                            "líneas: hay que dividirla a mano."
                                            for n in problemas)) if problemas else ""
    return (f"# Partición de {ruta.name}\n\n" + "\n".join(filas)
            + "\n\n## Contenido de cada subsistema\n" + "\n".join(detalle)
            + aviso + "\n")


def partir_archivo(ruta: str | Path, destino_subsistema: str | Path | None = None,
                   limite: int = LIMITE_LINEAS_REFACTOR) -> dict:
    """Parte ``ruta`` si supera ``limite``; devuelve el plan ejecutado."""
    origen = Path(ruta)
    if not origen.is_file():
        reportar_error(f"No existe el archivo: {origen}")
        return {"partido": False, "motivo": "no existe"}
    try:
        contenido = origen.read_text(encoding="utf-8-sig")
    except OSError as error:
        reportar_error(f"No se pudo leer {origen}: {error}")
        return {"partido": False, "motivo": str(error)}
    try:
        plan = plan_de_particion(contenido, limite)
    except ErrorProyecto as error:
        reportar_error(str(error))
        return {"partido": False, "motivo": str(error)}
    if not plan["necesita"]:
        informar(f"{origen.name} tiene {plan['total']} líneas: no hay que partir.")
        return {"partido": False, "motivo": "cabe en el tope"}
    partes = plan["partes"]
    destino = Path(destino_subsistema) if destino_subsistema else (
        origen.parent / "STM_SBSISTEMA")
    resumen = " · ".join(f"p{indice}: {len(parte)} unidades"
                         for indice, parte in enumerate(partes, start=1))
    _imprimir_seguro(_panel("LucIA · Partición del módulo",
                            f"{origen.name}: {plan['total']} líneas en "
                            f"{len(partes)} partes ({resumen}).\n"
                            f"Subsistemas en: {destino}"))
    if plan["problemas"]:
        advertir("No caben solas y habrá que dividirlas a mano: "
                 + ", ".join(plan["problemas"]))
    if not pedir_confirmacion("¿Se reparte el archivo?"):
        informar("Partición cancelada.")
        return {"partido": False, "motivo": "cancelado"}
    indices = list(range(2, len(partes) + 1))
    escritos: list[str] = []
    try:
        for indice, parte in zip(indices, partes[1:]):
            texto = (plan["cabecera"] + "\n\n\n" if plan["cabecera"] else "")
            texto += "\n\n\n".join(unidad["texto"] for unidad in parte).rstrip() + "\n"
            archivo_parte = destino / f"{origen.stem}_p{indice}.py"
            escribir_texto_atomico(archivo_parte, texto)
            escritos.append(str(archivo_parte))
        escribir_texto_atomico(
            origen, _componente_principal(plan["cabecera"], partes[0],
                                          origen.stem, indices))
        escribir_texto_atomico(origen.parent / f"particion_{origen.stem}.md",
                               _informe(origen, destino, partes, plan["problemas"]))
    except OSError as error:
        reportar_error(f"No se pudo escribir la partición: {error}")
        return {"partido": False, "motivo": str(error)}
    exito(f"{origen.name} repartido en {len(partes)} partes; "
          f"{len(escritos)} subsistema(s) en {destino}.")
    return {"partido": True, "partes": len(partes), "subsistemas": escritos,
            "problemas": plan["problemas"]}


def partir_si_excede(ruta: str | Path, limite: int = LIMITE_LINEAS_REFACTOR) -> bool:
    """Comprueba el tamaño y, si hace falta, ofrece partir el archivo."""
    origen = Path(ruta)
    try:
        total = len(origen.read_text(encoding="utf-8-sig").splitlines())
    except OSError:
        return False
    if total <= limite:
        return False
    advertir(f"{origen.name} tiene {total} líneas (tope {limite}).")
    if not pedir_confirmacion("¿Se reparte en módulos de 450 para cumplir el tope?"):
        return False
    return bool(partir_archivo(origen, limite=limite).get("partido"))


def comando_partir_archivo() -> None:
    """Comando interactivo: pide el archivo y lo reparte en módulos."""
    entrada = input("Archivo .py que supera el tope: ").strip().strip("\"'")
    if not entrada:
        reportar_error("No se indicó ningún archivo.")
        return
    partir_archivo(os.path.expandvars(os.path.expanduser(entrada)))
