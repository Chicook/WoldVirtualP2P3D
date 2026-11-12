"""Reparto de módulos que superan el tope de 450 líneas.

Dos fases, que es como lo pide el proyecto:

1. **Durante el refactor** (``partir_archivo``): si el resultado pasa de 450
   líneas, el exceso se escribe en un ``.py`` aparte **en CONTRUCCION**; el
   archivo principal re-exporta las partes (mismo directorio, sin trucos de
   ``sys.path``).
2. **Al cerrar la sesión** (``repartir_carpeta``): se recorre CONTRUCCION y se
   **reparten clases y funciones completas** entre los ``.py`` que ya existen,
   aprovechando su hueco hasta 450. Lo que no cabe en ninguno se escribe como
   **subsistema** en ``ENRN/STM_SBSISTEMA``.

Nunca se corta una clase ni una ``def`` por la mitad: las unidades son nodos de
nivel superior (AST). Si una sola unidad supera el tope, se avisa: eso hay que
dividirlo a mano.

El análisis y el empaquetado viven en ``sbstm_mdl/sbstm_ptcn.py`` (clase
``Particionador``); aquí se re-exportan para conservar la API histórica.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

#: Directorio que contiene el paquete (``.../STM_RFPRMN``). Se añade al path
#: para que los imports absolutos resuelvan también en ejecución directa (F5).
_RAIZ_PAQUETE = Path(__file__).resolve().parents[1]
if str(_RAIZ_PAQUETE) not in sys.path:
    sys.path.insert(0, str(_RAIZ_PAQUETE))

from STM_RFPRMN_stmDL.stm_base import (  # noqa: E402
    CONTRRF_DIR, ErrorProyecto, _imprimir_seguro, _panel, advertir, exito,
    informar, pedir_confirmacion, reportar_error,
)
from STM_RFPRMN_stmDL.stm_fragmentos import LIMITE_LINEAS_REFACTOR  # noqa: E402
from STM_RFPRMN_stmDL.stm_fs import escribir_texto_atomico  # noqa: E402
from STM_RFPRMN_stmDL.sbstm_mdl.sbstm_ptcn import Particionador  # noqa: E402

#: Carpeta donde aterriza el código refactorizado.
DIR_CONSTRUCCION = CONTRRF_DIR / "CONTRUCCION"
#: Subsistemas: el código que ya no cabe en ningún archivo de CONTRUCCION.
DIR_SUBSISTEMA = (CONTRRF_DIR / "TLLDCD" / "src" / "LC_STM" / "red_neuronal"
                  / "ENRN" / "STM_SBSISTEMA")
#: Líneas que ocupa el bloque de importación de subsistemas en la parte 1.
BOOTSTRAP = Particionador.BOOTSTRAP

#: API histórica: antes eran funciones sueltas en este módulo.
separar_unidades = Particionador.separar_unidades
plan_de_particion = Particionador.plan_de_particion
_imports = Particionador._imports
_empaquetar = Particionador._empaquetar
_componente = Particionador._componente


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
    aviso = ""
    if problemas:
        aviso = ("\n## Problemas\n" + "\n".join(
            f"- `{n}` no cabe en {LIMITE_LINEAS_REFACTOR} líneas: "
            "hay que dividirla a mano." for n in problemas))
    return (f"# Partición de {ruta.name}\n\n" + "\n".join(filas)
            + "\n\n## Contenido de cada subsistema\n" + "\n".join(detalle)
            + aviso + "\n")


def guardar_candidato(texto: str, ruta: str | Path) -> Path | None:
    """Guarda un candidato rechazado en CONTRUCCION para revisarlo sin riesgo.

    No se aplica: el archivo original queda intacto. Sirve para ver qué
    proponía la IA cuando la validación lo descartó (p. ej. por perder
    definiciones) sin que llegue al código del proyecto.
    """
    if not (texto or "").strip():
        return None
    destino = DIR_CONSTRUCCION / f"{Path(ruta).stem}_candidato.py"
    try:
        escribir_texto_atomico(destino, texto if texto.endswith("\n") else texto + "\n")
    except OSError as error:
        advertir(f"No se pudo guardar el candidato ({error}).")
        return None
    advertir(f"Candidato rechazado guardado para revisión: {destino}")
    return destino


def partir_archivo(ruta: str | Path, destino_subsistema: str | Path | None = None,
                   limite: int = LIMITE_LINEAS_REFACTOR) -> dict:
    """Parte ``ruta`` si supera ``limite``; el exceso va a otro ``.py``."""
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
    destino = Path(destino_subsistema) if destino_subsistema else origen.parent
    resumen = " · ".join(f"p{indice}: {len(parte)} unidades"
                         for indice, parte in enumerate(partes, start=1))
    _imprimir_seguro(_panel("LucIA · Partición del módulo",
                            f"{origen.name}: {plan['total']} líneas en "
                            f"{len(partes)} partes ({resumen}).\n"
                            f"El exceso se escribe en: {destino}"))
    if plan["problemas"]:
        advertir("No caben solas y habrá que dividirlas a mano: "
                 + ", ".join(plan["problemas"]))
    if not pedir_confirmacion("¿Se reparte el archivo?"):
        informar("Partición cancelada.")
        return {"partido": False, "motivo": "cancelado"}
    indices = list(range(2, len(partes) + 1))
    rel = None
    if destino.resolve() != origen.parent.resolve():
        rel = os.path.relpath(destino.resolve(), origen.parent.resolve())
        rel = rel.replace("\\", "/")
    escritos: list[str] = []
    try:
        for indice, parte in zip(indices, partes[1:]):
            texto = (plan["cabecera"] + "\n\n\n" if plan["cabecera"] else "")
            texto += "\n\n\n".join(unidad["texto"] for unidad in parte).rstrip() + "\n"
            archivo_parte = destino / f"{origen.stem}_p{indice}.py"
            escribir_texto_atomico(archivo_parte, texto)
            escritos.append(str(archivo_parte))
        escribir_texto_atomico(
            origen, _componente(plan["cabecera"], partes[0], origen.stem,
                                indices, rel))
        escribir_texto_atomico(origen.parent / f"particion_{origen.stem}.md",
                               _informe(origen, destino, partes, plan["problemas"]))
    except OSError as error:
        reportar_error(f"No se pudo escribir la partición: {error}")
        return {"partido": False, "motivo": str(error)}
    exito(f"{origen.name} repartido en {len(partes)} partes; "
          f"{len(escritos)} archivo(s) nuevo(s) en {destino}.")
    return {"partido": True, "partes": len(partes), "subsistemas": escritos,
            "problemas": plan["problemas"]}


def repartir_carpeta(carpeta: str | Path | None = None,
                     limite: int = LIMITE_LINEAS_REFACTOR,
                     destino_subsistema: str | Path | None = None) -> dict:
    """Reparte clases y def completas entre los ``.py`` de ``carpeta``.

    Rellena los archivos que tienen hueco hasta ``limite``; lo que no cabe en
    ninguno se escribe como subsistema. Los archivos que ya caben no se tocan.
    """
    base = Path(carpeta) if carpeta else DIR_CONSTRUCCION
    if not base.is_dir():
        return {"archivos": [], "movidas": 0, "creados": 0, "motivo": "no existe"}
    archivos = [p for p in sorted(base.glob("*.py")) if p.name != "__init__.py"]
    contenidos: dict[Path, str] = {}
    for archivo in archivos:
        try:
            contenidos[archivo] = archivo.read_text(encoding="utf-8-sig")
        except OSError:
            continue
    if not any(len(c.splitlines()) > limite for c in contenidos.values()):
        return {"archivos": 0, "movidas": 0, "creados": 0, "motivo": "nada que repartir"}
    originales = dict(contenidos)
    hueco = {p: limite - len(c.splitlines()) for p, c in contenidos.items()}
    movidas, creados = 0, 0
    for origen in list(contenidos):
        if len(contenidos[origen].splitlines()) <= limite:
            continue
        try:
            cabecera, unidades = separar_unidades(contenidos[origen])
        except ErrorProyecto:
            advertir(f"{origen.name} no es Python válido: se omite.")
            continue
        imports = _imports(cabecera)
        sobran: list[dict] = []
        for unidad in unidades:
            destino = _con_hueco(hueco, origen, unidad["lineas"])
            if destino is None:
                sobran.append(unidad)
                continue
            faltan = [linea for linea in imports
                      if linea not in contenidos[destino]]
            bloque = "\n".join(faltan + [unidad["texto"]])
            contenidos[destino] = (contenidos[destino].rstrip()
                                   + "\n\n\n" + bloque + "\n")
            hueco[destino] -= unidad["lineas"] + len(faltan) + 2
            movidas += 1
        if not sobran:
            contenidos[origen] = cabecera + "\n" if cabecera else ""
            continue
        try:
            partes = _empaquetar(cabecera, sobran, limite)
        except ErrorProyecto:
            partes = [sobran]
        indices = list(range(2, len(partes) + 1))
        for indice, parte in zip(indices, partes[1:]):
            texto = (cabecera + "\n\n\n" if cabecera else "")
            texto += "\n\n\n".join(u["texto"] for u in parte).rstrip() + "\n"
            escribir_texto_atomico(base / f"{origen.stem}_p{indice}.py", texto)
            creados += 1
        contenidos[origen] = _componente(cabecera, partes[0], origen.stem, indices)
    escritos = 0
    for archivo, texto in contenidos.items():
        if not texto.strip() or texto == originales.get(archivo):
            continue  # solo se escribe lo que cambió
        try:
            escribir_texto_atomico(archivo, texto)
            escritos += 1
        except OSError as error:
            reportar_error(f"No se pudo escribir {archivo.name}: {error}")
    if movidas or creados:
        exito(f"CONTRUCCION repartida: {movidas} unidad(es) movida(s) y "
              f"{creados} archivo(s) nuevo(s) en {base.name}.")
    _ = destino_subsistema  # reservado: los sobrantes ya van a partes propias
    return {"archivos": escritos, "movidas": movidas, "creados": creados}


def _con_hueco(hueco: dict, origen: Path, lineas: int) -> Path | None:
    """Archivo con espacio para ``lineas`` (el más lleno que aún quepa)."""
    candidatos = [(p, h) for p, h in hueco.items() if p != origen and h >= lineas + 2]
    if not candidatos:
        return None
    return sorted(candidatos, key=lambda par: par[1])[0][0]


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
    # El exceso va a un .py aparte en CONTRUCCION, como pide el proyecto.
    return bool(partir_archivo(origen, destino_subsistema=DIR_CONSTRUCCION,
                               limite=limite).get("partido"))


def comando_partir_archivo() -> None:
    """Comando interactivo: pide el archivo y lo reparte en módulos."""
    entrada = input("Archivo .py que supera el tope: ").strip().strip("\"'")
    if not entrada:
        reportar_error("No se indicó ningún archivo.")
        return
    partir_archivo(os.path.expandvars(os.path.expanduser(entrada)))


if __name__ == "__main__":
    # Ejecución directa (F5 / python stm_particion.py): confirma que carga.
    print(f"stm_particion OK · {Particionador.__name__} · "
          f"tope {LIMITE_LINEAS_REFACTOR} líneas")
