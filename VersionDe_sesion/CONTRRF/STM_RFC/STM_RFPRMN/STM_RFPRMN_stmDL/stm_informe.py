"""Comando ``informacion codigo``: el código va a una IA y LucIA escribe el ``.md``.

Cadena completa:

1. Se lee el archivo y se parte en **unidades completas** (clases y ``def``),
   para que la IA de código nunca reciba un trozo cortado.
2. La **IA de código** (modelo local) analiza cada bloque y devuelve Markdown
   detallado: propósito, responsabilidades, deuda y riesgos.
3. **LucIA lo reescribe con sus propias palabras**, sin resumir, y se comprueba
   que no se pierda ningún detalle (nombres entre comillas y cifras). Si falta
   algo se reintenta con la lista; si sigue faltando, se añade al final.
4. Se completa con **datos objetivos** calculados aquí (métricas, estructura,
   deuda y hoja de ruta), así el documento nunca queda incompleto aunque el
   modelo omita algo.
5. Se escribe en ``TLLDCD/src/STM_DOC/informe_<nombre>.md``.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import urllib.request
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
#: Caracteres máximos por envío (para no truncar en el contexto del modelo).
MAX_CARACTERES_ENVIO = 6000

#: Rol de la IA de código que analiza el archivo.
SISTEMA_ANALISIS = (
    "Eres una IA especializada en código. Analiza el fragmento y devuelve "
    "Markdown detallado en español: propósito del archivo, responsabilidad de "
    "cada clase y función, deuda técnica concreta, riesgos y pasos de refactor. "
    "No inventes: si algo no se ve en el código, dilo.")

#: Rol de LucIA al reescribir el informe.
SISTEMA_REESCRITURA = (
    "Eres LucIA. Reescribe este informe con tus propias palabras, en español, "
    "conservando TODOS los datos: nombres de clases y funciones, cifras, rutas y "
    "pasos. No resumas ni omitas nada. Devuelve solo Markdown, sin comentarios.")


def _pedir(sistema: str, contenido: str, modelo: str, endpoint: str,
           num_predict: int = 900) -> str:
    """Una petición de chat completa (sin stream) al modelo local."""
    carga = {
        "model": modelo, "stream": False,
        "options": {"temperature": 0.2, "num_predict": num_predict,
                    "num_ctx": 8192},
        "messages": [{"role": "system", "content": sistema},
                     {"role": "user", "content": contenido}],
    }
    peticion = urllib.request.Request(
        f"{endpoint}/api/chat", data=json.dumps(carga).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(peticion, timeout=600) as respuesta:
        datos = json.loads(respuesta.read().decode("utf-8"))
    mensaje = datos.get("message") if isinstance(datos, dict) else None
    return str((mensaje or {}).get("content", "")).strip()


# --- Troceado sin cortar unidades -------------------------------------------

def trocear_codigo(contenido: str, maximo: int = MAX_CARACTERES_ENVIO) -> list[str]:
    """Parte el código en bloques completos (clases y ``def`` enteras)."""
    try:
        cabecera, unidades = separar_unidades(contenido)
    except ErrorProyecto:
        return _trocear_por_lineas(contenido, maximo)
    bloques: list[str] = []
    actual = [cabecera] if cabecera else []
    usados = len(cabecera) + 2
    for unidad in unidades:
        if actual and usados + len(unidad["texto"]) + 2 > maximo:
            bloques.append("\n\n\n".join(actual).strip())
            actual, usados = [], 0
        actual.append(unidad["texto"])
        usados += len(unidad["texto"]) + 2
    if actual:
        bloques.append("\n\n\n".join(actual).strip())
    return [bloque for bloque in bloques if bloque]


def _trocear_por_lineas(contenido: str, maximo: int) -> list[str]:
    """Respaldo para lenguajes sin AST: corta en líneas, nunca a media palabra."""
    bloques: list[str] = []
    actual: list[str] = []
    usados = 0
    for linea in (contenido or "").splitlines():
        if actual and usados + len(linea) + 1 > maximo:
            bloques.append("\n".join(actual).strip())
            actual, usados = [], 0
        actual.append(linea)
        usados += len(linea) + 1
    if actual:
        bloques.append("\n".join(actual).strip())
    return [bloque for bloque in bloques if bloque]


# --- Análisis con la IA de código -------------------------------------------

def analizar_con_ia(contenido: str, ruta: Path, modelo: str) -> str:
    """Pide a la IA de código el informe de cada bloque completo y los une."""
    bloques = trocear_codigo(contenido)
    if not bloques:
        return ""
    partes: list[str] = []
    for indice, bloque in enumerate(bloques, start=1):
        cabecera = (f"Archivo: {ruta.name} (bloque {indice}/{len(bloques)})\n"
                    f"Lenguaje: {ruta.suffix or 'desconocido'}\n\n")
        try:
            respuesta = _pedir(SISTEMA_ANALISIS, cabecera + bloque, modelo,
                               _endpoint())
        except Exception as error:  # noqa: BLE001 - se anota y se sigue
            informar(f"Bloque {indice} sin respuesta ({error}).")
            continue
        if respuesta:
            partes.append(respuesta)
    return "\n\n".join(partes)


def _endpoint() -> str:
    """Endpoint de Ollama desde la configuración de IA local."""
    from .stm_analisis import _cargar_configuracion_ia_local

    endpoint, _ = _cargar_configuracion_ia_local()
    return endpoint


# --- Reescritura de LucIA, sin perder detalle -------------------------------

def _detalles(texto: str) -> list[str]:
    """Datos que no pueden perderse: identificadores entre comillas y cifras."""
    entre_comillas = re.findall(r"`([^`\n]{2,60})`", texto or "")
    cifras = re.findall(r"\b\d+(?:[.,]\d+)?\b", texto or "")
    vistos: list[str] = []
    for detalle in entre_comillas + cifras:
        if detalle not in vistos:
            vistos.append(detalle)
    return vistos


def faltantes(original: str, reescrito: str) -> list[str]:
    """Detalles del informe original que no aparecen en la reescritura."""
    return [detalle for detalle in _detalles(original)
            if detalle not in (reescrito or "")]


def reescribir_con_lucia(informe: str, modelo: str) -> dict:
    """Reescribe el informe y verifica que no se pierda ningún detalle.

    Devuelve ``{"texto", "faltantes", "completo"}``. Si tras el reintento sigue
    faltando algo, ``faltantes`` lo lista para añadirlo al documento final.
    """
    pendientes: list[str] = []
    texto = ""
    for intento in (1, 2):
        aviso = ""
        if pendientes:
            aviso = ("\n\nNO OMITAS estos datos: " + ", ".join(pendientes[:40]))
        try:
            texto = _pedir(SISTEMA_REESCRITURA, informe + aviso, modelo,
                           _endpoint(), num_predict=1600)
        except Exception:  # noqa: BLE001 - se reintenta una vez
            texto = ""
        if not texto:
            informar(f"Reescritura {intento}/2 sin respuesta; reintento...")
            continue
        pendientes = faltantes(informe, texto)
        if not pendientes:
            break
        informar(f"Reescritura {intento}/2: faltan {len(pendientes)} detalles.")
    return {"texto": texto, "faltantes": pendientes, "completo": not pendientes}


# --- Bloques deterministas (datos objetivos) --------------------------------

def _cabecera(ruta: Path, analisis: AnalisisArchivo, informe: dict) -> list[str]:
    """Bloque de información básica del archivo."""
    sintaxis = "válida" if informe["sintaxis_ok"] else "inválida"
    return [
        f"- **Generado**: {_dt.date.today().isoformat()}",
        f"- **Ruta**: `{ruta}`",
        f"- **Lenguaje**: `{analisis.extension or '(sin extensión)'}`",
        f"- **Tamaño**: {analisis.lineas} líneas · {analisis.funciones} funciones "
        f"· {analisis.clases} clases",
        f"- **Sintaxis**: {sintaxis}",
        f"- **Puntuación de deuda**: {informe['puntuacion']}/100 "
        f"({informe['nivel']})",
    ]


def _estructura(contenido: str) -> list[str]:
    """Tabla con clases y funciones del archivo."""
    try:
        _, unidades = separar_unidades(contenido)
    except ErrorProyecto:
        return ["_No se pudo analizar la estructura._"]
    if not unidades:
        return ["_Sin clases ni funciones de nivel superior._"]
    filas = ["| Tipo | Nombre | Líneas |", "|---|---|---:|"]
    for unidad in unidades:
        filas.append(f"| {unidad['tipo']} | `{unidad['nombre']}` | "
                     f"{unidad['lineas']} |")
    return filas


def _deuda(informe: dict) -> list[str]:
    """Descuentos, hallazgos y lint."""
    lineas: list[str] = []
    for motivo, puntos in informe["motivos"]:
        lineas.append(f"- {motivo} (-{puntos})")
    if informe["hallazgos"]:
        lineas += [f"- {hallazgo}" for hallazgo in informe["hallazgos"]]
    if informe["lint"]["problemas"]:
        lineas.append(f"- Lint: {informe['lint']['problemas']} avisos")
    return lineas or ["_Sin hallazgos relevantes: el archivo está sano._"]


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
                     f"({analisis.puntos_decision} puntos de decisión).")
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
    return [f"{indice}. {paso}" for indice, paso in enumerate(pasos, start=1)]


def construir_informe(ruta: str | Path, consultor: ConsultorIA | None = None) -> str:
    """Markdown determinista del archivo (datos objetivos, sin IA)."""
    origen = Path(ruta)
    try:
        contenido = origen.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise ErrorProyecto(f"No se pudo leer {origen}: {error}")
    analisis = analizar_archivo_local(origen)
    informe = diagnostico_deuda(origen)
    bloques = [f"# Informe de código · {origen.name}", ""]
    bloques += _cabecera(origen, analisis, informe) + [""]
    bloques += ["## Estructura", ""] + _estructura(contenido) + [""]
    bloques += ["## Deuda técnica", ""] + _deuda(informe) + [""]
    bloques += ["## Hoja de ruta", ""] + hoja_de_ruta(analisis, informe) + [""]
    if consultor is not None:
        try:
            diagnostico = str(consultor(contenido, analisis)).strip()
        except Exception as error:  # noqa: BLE001 - el informe no depende de la IA
            diagnostico = f"_LucIA no respondió ({error})._"
        bloques += ["## Diagnóstico de LucIA", "", diagnostico, ""]
    return "\n".join(bloques).rstrip() + "\n"


# --- Documento final ---------------------------------------------------------

def generar_informe(ruta: str | Path, consultor: ConsultorIA | None = None,
                    destino: str | Path | None = None,
                    con_ia: bool = False) -> Path | None:
    """Construye el ``.md`` (con IA de código y reescritura de LucIA) y lo escribe."""
    origen = Path(ruta)
    if not origen.is_file():
        reportar_error(f"No existe el archivo: {origen}")
        return None
    try:
        contenido = origen.read_text(encoding="utf-8-sig")
        datos = construir_informe(origen, consultor)
    except (OSError, ErrorProyecto) as error:
        reportar_error(str(error))
        return None
    texto = datos
    if con_ia:
        modelo = _modelo_codigo()
        if not modelo:
            advertir("No hay IA de código disponible; el informe será el de datos.")
        else:
            informar(f"Enviando el código a la IA ({modelo}) por bloques completos...")
            crudo = analizar_con_ia(contenido, origen, modelo)
            if not crudo:
                advertir("La IA de código no devolvió análisis.")
            else:
                reescrito = reescribir_con_lucia(crudo, modelo)
                cuerpo = reescrito["texto"] or crudo
                texto = (f"# Informe de código · {origen.name}\n\n"
                         f"> Redactado por LucIA a partir del análisis de la IA de "
                         f"código (`{modelo}`).\n\n{cuerpo}\n\n"
                         f"## Datos objetivos\n\n" + datos.split("\n", 1)[1])
                if reescrito["faltantes"]:
                    texto += ("\n## Detalles del análisis original\n\n"
                              + "\n".join(f"- `{d}`" for d in reescrito["faltantes"])
                              + "\n")
    carpeta = Path(destino) if destino else DIR_DOCS
    archivo = carpeta / f"informe_{origen.stem}.md"
    try:
        escribir_texto_atomico(archivo, texto)
    except OSError as error:
        reportar_error(f"No se pudo escribir {archivo}: {error}")
        return None
    exito(f"Informe escrito: {archivo}")
    return archivo


def _modelo_codigo() -> str:
    """Modelo de código más ligero disponible (o cadena vacía)."""
    try:
        from .stm_modelos import _asegurar_modelo_codigo, _liberar_ollama

        modelo = _asegurar_modelo_codigo()
        _liberar_ollama(excepto=modelo)
        return modelo
    except Exception:  # noqa: BLE001 - sin modelo se usa solo el informe de datos
        return ""


def comando_informacion_codigo() -> None:
    """Comando interactivo: pide el archivo y genera su informe en STM_DOC."""
    entrada = input("Archivo del que sacar el informe: ").strip().strip("\"'")
    if not entrada:
        reportar_error("No se indicó ningún archivo.")
        return
    ruta = Path(os.path.expandvars(os.path.expanduser(entrada)))
    con_ia = pedir_confirmacion(
        "¿Enviar el código a la IA para que redacte el informe?")
    archivo = generar_informe(ruta, con_ia=con_ia)
    if archivo:
        _imprimir_seguro(f"Informe completo en {archivo}")
    else:
        advertir("No se generó el informe.")
