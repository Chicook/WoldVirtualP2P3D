"""Comando ``informacion codigo``: ficha ``.md`` de un archivo y su hoja de ruta.

Genera un documento en ``TLLDCD/src/STM_DOC`` con tres bloques:

1. **Información del código**: ruta, lenguaje, tamaño, estructura (clases y
   funciones con sus líneas) y estado de la sintaxis.
2. **Deuda técnica**: puntuación 0-100, descuentos concretos, hallazgos y avisos
   de lint (reutiliza ``test.diagnostico_deuda``).
3. **Hoja de ruta**: pasos ordenados por gravedad, derivados de la deuda real
   del archivo (no una lista genérica), indicando qué comando usar en cada uno.

Opcionalmente incluye el diagnóstico de LucIA con el modelo local.
"""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path

from .stm_analisis import AnalisisArchivo, ConsultorIA, analizar_archivo_local
from .stm_base import (
    CONTRRF_DIR, ErrorProyecto, _imprimir_seguro, advertir, exito, informar,
    pedir_confirmacion, reportar_error,
)
from .stm_fragmentos import LIMITE_LINEAS_REFACTOR
from .stm_fs import escribir_texto_atomico
from .stm_particion import separar_unidades
from .test import diagnostico_deuda

#: Carpeta de documentación del proyecto.
DIR_DOCS = CONTRRF_DIR / "TLLDCD" / "src" / "STM_DOC"


def _cabecera(ruta: Path, analisis: AnalisisArchivo, informe: dict) -> list[str]:
    """Bloque de información básica del archivo."""
    sintaxis = "válida" if informe["sintaxis_ok"] else "inválida"
    return [
        f"# Informe de código · {ruta.name}",
        "",
        f"- **Generado**: {_dt.date.today().isoformat()}",
        f"- **Ruta**: `{ruta}`",
        f"- **Lenguaje**: `{analisis.extension or '(sin extensión)'}`",
        f"- **Tamaño**: {analisis.lineas} líneas · {analisis.funciones} funciones "
        f"· {analisis.clases} clases",
        f"- **Sintaxis**: {sintaxis}",
        f"- **Puntuación de deuda**: {informe['puntuacion']}/100 "
        f"({informe['nivel']})",
        "",
    ]


def _estructura(contenido: str, ruta: Path) -> list[str]:
    """Tabla con clases y funciones del archivo."""
    try:
        _, unidades = separar_unidades(contenido)
    except ErrorProyecto:
        return ["## Estructura", "", "_No se pudo analizar la estructura._", ""]
    if not unidades:
        return ["## Estructura", "", "_Sin clases ni funciones de nivel superior._", ""]
    filas = ["## Estructura", "", "| Tipo | Nombre | Líneas |", "|---|---|---:|"]
    for unidad in unidades:
        filas.append(f"| {unidad['tipo']} | `{unidad['nombre']}` | "
                     f"{unidad['lineas']} |")
    filas.append("")
    return filas


def _deuda(informe: dict, analisis: AnalisisArchivo) -> list[str]:
    """Bloque de deuda: puntuación, descuentos, hallazgos y lint."""
    lineas = ["## Deuda técnica", ""]
    if informe["motivos"]:
        lineas.append("**Descuentos aplicados**")
        lineas.append("")
        for motivo, puntos in informe["motivos"]:
            lineas.append(f"- {motivo} (-{puntos})")
        lineas.append("")
    if informe["hallazgos"]:
        lineas.append("**Hallazgos**")
        lineas.append("")
        lineas += [f"- {hallazgo}" for hallazgo in informe["hallazgos"]]
        lineas.append("")
    if informe["lint"]["problemas"]:
        lineas.append(f"**Lint** ({informe['lint']['problemas']} avisos)")
        lineas.append("")
        lineas += [f"- `{aviso}`" for aviso in informe["lint"]["detalle"]]
        lineas.append("")
    if len(lineas) == 2:
        lineas += ["_Sin hallazgos relevantes: el archivo está sano._", ""]
    return lineas


def hoja_de_ruta(analisis: AnalisisArchivo, informe: dict) -> list[str]:
    """Pasos ordenados por gravedad, según la deuda real del archivo."""
    pasos: list[str] = []
    if not informe["sintaxis_ok"]:
        pasos.append("**Arreglar la sintaxis** antes de cualquier otra cosa: el "
                     "archivo no compila y nada más se puede validar.")
    if analisis.lineas > LIMITE_LINEAS_REFACTOR:
        pasos.append(f"**Partir el archivo**: {analisis.lineas} líneas superan el "
                     f"tope de {LIMITE_LINEAS_REFACTOR}. Usa el particionador de "
                     "`ds ialocal` (guarda las partes en CONTRUCCION).")
    if analisis.funciones_sin_docstring:
        pasos.append(f"**Documentar {analisis.funciones_sin_docstring} funciones** "
                     "con `comentar archivo` (solo añade comentarios).")
    if analisis.except_genericos:
        pasos.append(f"**Sustituir {analisis.except_genericos} capturas genéricas** "
                     "por errores concretos y contexto de recuperación.")
    if analisis.argumentos_mutables:
        pasos.append(f"**Quitar {analisis.argumentos_mutables} argumentos mutables** "
                     "por defecto (`None` y lista dentro de la función).")
    if analisis.puntos_decision > 20:
        pasos.append(f"**Dividir la lógica más compleja** "
                     f"({analisis.puntos_decision} puntos de decisión): funciones "
                     "pequeñas con una sola responsabilidad.")
    if analisis.lineas_largas:
        pasos.append(f"**Reformatear {analisis.lineas_largas} líneas largas** "
                     "(más de 100 caracteres).")
    if analisis.marcadores_pendientes:
        pasos.append(f"**Resolver o registrar {analisis.marcadores_pendientes} "
                     "TODO/FIXME** para que no se pierdan.")
    if informe["lint"]["problemas"]:
        pasos.append(f"**Pasar lint**: {informe['lint']['problemas']} avisos de ruff.")
    pasos.append("**Línea base**: ejecutar pruebas y `test` antes de tocar nada, y "
                 "volver a ejecutarlos después de cada cambio.")
    pasos.append("**Cambios pequeños y reversibles**, uno por responsabilidad.")
    return ["## Hoja de ruta", ""] + [
        f"{indice}. {paso}" for indice, paso in enumerate(pasos, start=1)] + [""]


def construir_informe(ruta: Path, consultor: ConsultorIA | None = None) -> str:
    """Markdown completo del informe (sin escribir nada)."""
    try:
        contenido = ruta.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise ErrorProyecto(f"No se pudo leer {ruta}: {error}")
    analisis = analizar_archivo_local(ruta)
    informe = diagnostico_deuda(ruta)
    bloques = _cabecera(ruta, analisis, informe)
    bloques += _estructura(contenido, ruta)
    bloques += _deuda(informe, analisis)
    bloques += hoja_de_ruta(analisis, informe)
    if consultor is not None:
        try:
            diagnostico = str(consultor(contenido, analisis)).strip()
        except Exception as error:  # noqa: BLE001 - el informe no depende de la IA
            diagnostico = f"_LucIA no respondió ({error})._"
        bloques += ["## Diagnóstico de LucIA", "", diagnostico, ""]
    return "\n".join(bloques).rstrip() + "\n"


def generar_informe(ruta: str | Path, consultor: ConsultorIA | None = None,
                    destino: str | Path | None = None) -> Path | None:
    """Escribe el informe en ``STM_DOC``; devuelve la ruta o ``None`` si falla."""
    origen = Path(ruta)
    if not origen.is_file():
        reportar_error(f"No existe el archivo: {origen}")
        return None
    try:
        texto = construir_informe(origen, consultor)
    except ErrorProyecto as error:
        reportar_error(str(error))
        return None
    carpeta = Path(destino) if destino else DIR_DOCS
    archivo = carpeta / f"informe_{origen.stem}.md"
    try:
        escribir_texto_atomico(archivo, texto)
    except OSError as error:
        reportar_error(f"No se pudo escribir {archivo}: {error}")
        return None
    exito(f"Informe escrito: {archivo}")
    return archivo


def comando_informacion_codigo() -> None:
    """Comando interactivo: pide el archivo y genera su informe en STM_DOC."""
    entrada = input("Archivo del que sacar el informe: ").strip().strip("\"'")
    if not entrada:
        reportar_error("No se indicó ningún archivo.")
        return
    ruta = Path(os.path.expandvars(os.path.expanduser(entrada)))
    consultor = None
    if pedir_confirmacion("¿Incluir también el diagnóstico de LucIA (modelo local)?"):
        from .stm_analisis import consultar_ia_local

        informar("Consultando a LucIA; puede tardar un poco...")
        consultor = consultar_ia_local
    archivo = generar_informe(ruta, consultor)
    if archivo:
        _imprimir_seguro(f"Deuda y hoja de ruta en {archivo}")
    else:
        advertir("No se generó el informe.")
