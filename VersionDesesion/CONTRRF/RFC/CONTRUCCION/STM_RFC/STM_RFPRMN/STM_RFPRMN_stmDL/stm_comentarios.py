"""Comando ``comentar archivo``: LucIA documenta cada función del archivo.

El flujo es el mismo que en el resto: **la IA local redacta, LucIA decide y
escribe**.

1. Análisis del archivo: se localizan las funciones y clases **sin docstring**
   (AST en Python; firmas por patrón en el resto).
2. La IA local recibe esas firmas con su cuerpo y devuelve una línea por
   función (``nombre :: comentario``).
3. LucIA valida cada comentario (longitud, que no sea el nombre repetido, sin
   cercas) y descarta los que no sirven.
4. Se insertan como docstring (Python) o como comentario de línea (C#, JS…).
5. **Invariante**: el archivo resultante debe ser idéntico al original al quitar
   los comentarios. Si la inserción toca código, no se escribe nada.
6. Diagnóstico de deuda con el módulo ``test``.
"""
from __future__ import annotations

import ast
import json
import re
import textwrap
import urllib.request
from pathlib import Path
from typing import Callable

from .stm_analisis import _cargar_configuracion_ia_local
from .stm_base import (
    _imprimir_seguro, exito, informar, pedir_confirmacion, reportar_error,
)
from .stm_calidad import solo_documenta
from .stm_fs import escribir_texto_atomico
from .stm_modelos import _asegurar_modelo_codigo, _liberar_ollama
from .test import comando_test_ruta

#: Rol del modelo: redactar la documentación de cada función.
SISTEMA_COMENTARIO = (
    "Eres LucIA y documentas código. Para cada función recibirás su firma y su "
    "cuerpo. Devuelve EXACTAMENTE una línea por función con el formato\n"
    "nombre_de_la_funcion :: comentario en español, 1 o 2 frases que expliquen "
    "QUÉ hace y PARA QUÉ sirve (no cómo se llama, ni que 'es una función').\n"
    "Cada línea, como máximo 80 caracteres. Sin markdown, sin cercas, sin "
    "numeración, sin líneas extra.")

#: Palabras que no son nombres de método al detectar firmas.
_CONTROL = frozenset({"if", "for", "while", "switch", "catch", "using", "lock",
                      "foreach", "else", "do", "try", "return", "new", "throw",
                      "get", "set", "init", "operator"})

#: Firma de método en C#, Java, JS, Go… (conservadora).
_FIRMA = re.compile(
    r"^(?P<sangria>[ \t]*)"
    r"(?:(?:public|private|protected|internal|static|async|virtual|override|"
    r"sealed|final|synchronized|func|function|void|int|string|bool|double|"
    r"float|long|var|Task|List|IEnumerable|object|char|byte)[ \t]+)+"
    r"(?P<nombre>[A-Za-z_]\w*)[ \t]*\([^;{}]*\)[ \t]*(?:\{|=>|:)?[ \t]*$")


def _firma_python(nodo) -> str:
    """Firma legible de una función o clase de Python."""
    if isinstance(nodo, ast.ClassDef):
        return f"class {nodo.name}"
    argumentos = [arg.arg for arg in getattr(nodo.args, "args", [])]
    return f"def {nodo.name}({', '.join(argumentos)})"


def funciones_sin_documentar(contenido: str, ruta: Path) -> list[dict]:
    """Funciones y clases sin docstring, con lo necesario para insertarlo."""
    if Path(ruta).suffix.lower() != ".py":
        return _objetivos_por_patron(contenido)
    try:
        arbol = ast.parse(contenido)
    except SyntaxError:
        return []
    lineas = contenido.splitlines()
    objetivos: list[dict] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if ast.get_docstring(nodo):
            continue
        cuerpo = getattr(nodo, "body", [])
        if not cuerpo or cuerpo[0].lineno == nodo.lineno:
            continue  # cuerpo en la misma línea: no se puede insertar sin riesgo
        indice = cuerpo[0].lineno - 1
        if indice >= len(lineas):
            continue
        linea = lineas[indice]
        objetivos.append({
            "clave": f"{nodo.name}@{nodo.lineno}",
            "nombre": nodo.name,
            "linea": indice,
            "sangria": linea[: len(linea) - len(linea.lstrip())],
            "firma": _firma_python(nodo),
            "cuerpo": (ast.get_source_segment(contenido, nodo) or "")[:1200],
        })
    return objetivos


def _objetivos_por_patron(contenido: str) -> list[dict]:
    """Firmas de método detectadas por patrón (lenguajes sin AST disponible)."""
    lineas = contenido.splitlines()
    objetivos: list[dict] = []
    for indice, linea in enumerate(lineas):
        coincidencia = _FIRMA.match(linea.rstrip())
        if not coincidencia or coincidencia.group("nombre").lower() in _CONTROL:
            continue
        previa = _linea_previa(lineas, indice)
        if previa.startswith(("//", "/*", "*", "@", "#")):
            continue  # ya tiene un comentario o atributo justo encima
        objetivos.append({
            "clave": f"{coincidencia.group('nombre')}@{indice + 1}",
            "nombre": coincidencia.group("nombre"),
            "linea": indice,
            "sangria": coincidencia.group("sangria"),
            "firma": linea.strip(),
            "cuerpo": linea.strip(),
        })
    return objetivos


def _linea_previa(lineas: list[str], indice: int) -> str:
    """Última línea no vacía antes de ``indice`` (cadena vacía si no hay)."""
    for posicion in range(indice - 1, -1, -1):
        if lineas[posicion].strip():
            return lineas[posicion].strip()
    return ""


def sanear(texto: str) -> str:
    """Deja el comentario en una línea limpia (sin cercas ni comillas)."""
    limpio = re.sub(r"^```[a-zA-Z0-9]*\s*|\s*```$", "", (texto or "").strip())
    limpio = limpio.strip().strip("\"'").strip()
    limpio = re.sub(r'^"""|"""$', "", limpio).strip()
    return " ".join(limpio.split())


def comentario_valido(texto: str, nombre: str) -> bool:
    """LucIA acepta el comentario si aporta información y cabe en la línea."""
    if not texto:
        return False
    if len(texto) < 15 or len(texto) > 300:
        return False
    simplificado = texto.lower().strip(" .:")
    if simplificado == nombre.lower() or simplificado.startswith(f"{nombre.lower()} "):
        return False
    if "```" in texto or "\n" in texto:
        return False
    return True


def envolver(texto: str, sangria: str, ancho: int = 88) -> list[str]:
    """Parte el comentario para que ninguna línea pase de ``ancho`` caracteres."""
    disponible = max(24, ancho - len(sangria) - 4)
    return textwrap.wrap(texto, width=disponible) or [texto]


def insertar(contenido: str, objetivos: list[dict], comentarios: dict,
             es_python: bool) -> str:
    """Inserta los comentarios de abajo arriba (los índices no se desplazan)."""
    lineas = contenido.splitlines()
    for objetivo in sorted(objetivos, key=lambda item: item["linea"], reverse=True):
        texto = comentarios.get(objetivo["clave"])
        if not texto:
            continue
        sangria = objetivo["sangria"]
        trozos = envolver(texto, sangria)
        if es_python:
            cuerpo = ("\n" + sangria).join(trozos)
            lineas.insert(objetivo["linea"], f'{sangria}"""{cuerpo}"""')
        else:
            nuevas = [f"{sangria}// {trozo}" for trozo in trozos]
            lineas[objetivo["linea"]:objetivo["linea"]] = nuevas
    return "\n".join(lineas) + "\n"


def _bloque_peticion(objetivos: list[dict]) -> str:
    """Contexto con las firmas y cuerpos que debe documentar el modelo."""
    partes = [f"### {objetivo['nombre']}\nFirma: {objetivo['firma']}\n"
              f"Código:\n{objetivo['cuerpo']}\n" for objetivo in objetivos]
    return "\n".join(partes)


def _parsear(texto: str, objetivos: list[dict]) -> dict:
    """Convierte la respuesta del modelo en ``{clave: comentario}`` válido."""
    por_nombre = {objetivo["nombre"].lower(): objetivo for objetivo in objetivos}
    comentarios: dict[str, str] = {}
    for linea in (texto or "").splitlines():
        if "::" not in linea:
            continue
        nombre, comentario = linea.split("::", 1)
        objetivo = por_nombre.get(nombre.strip().strip("*`# ").lower())
        if objetivo is None:
            continue
        limpio = sanear(comentario)
        if comentario_valido(limpio, objetivo["nombre"]):
            comentarios[objetivo["clave"]] = limpio
    return comentarios


def _generar_comentarios(objetivos: list[dict], ruta: Path) -> dict:
    """Pide los comentarios a la IA local (una sola petición)."""
    endpoint, _ = _cargar_configuracion_ia_local()
    modelo = _asegurar_modelo_codigo()
    _liberar_ollama(excepto=modelo)
    carga = {
        "model": modelo, "stream": False,
        "options": {"temperature": 0.2, "num_predict": 700, "num_ctx": 4096},
        "messages": [
            {"role": "system", "content": SISTEMA_COMENTARIO},
            {"role": "user", "content": (f"Archivo: {Path(ruta).name}\n\n"
                                         f"{_bloque_peticion(objetivos)}")}],
    }
    peticion = urllib.request.Request(
        f"{endpoint}/api/chat", data=json.dumps(carga).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(peticion, timeout=600) as respuesta:
        datos = json.loads(respuesta.read().decode("utf-8"))
    mensaje = datos.get("message") if isinstance(datos, dict) else None
    return _parsear(str((mensaje or {}).get("content", "")), objetivos)


def comentar_archivo(ruta: str | Path, limite: int = 8,
                     generador: Callable[[list[dict], Path], dict] | None = None) -> bool:
    """Documenta las funciones de ``ruta``; True si se escribió el archivo."""
    destino = Path(ruta)
    if not destino.is_file():
        reportar_error(f"No existe el archivo: {destino}")
        return False
    try:
        contenido = destino.read_text(encoding="utf-8-sig")
    except OSError as error:
        reportar_error(f"No se pudo leer {destino}: {error}")
        return False
    objetivos = funciones_sin_documentar(contenido, destino)[:max(1, limite)]
    if not objetivos:
        informar("No hay funciones sin documentar (o el archivo no se pudo analizar).")
        return False
    _imprimir_seguro(f"LucIA: {len(objetivos)} función(es) sin documentar en "
                     f"{destino.name}: " + ", ".join(o["nombre"] for o in objetivos))
    if not pedir_confirmacion("¿Se piden los comentarios a la IA local y se escriben?"):
        informar("Comentado cancelado.")
        return False
    try:
        comentarios = (generador(objetivos, destino) if generador
                       else _generar_comentarios(objetivos, destino))
    except Exception as error:  # noqa: BLE001 - red caída, modelo ausente, etc.
        reportar_error(f"La IA local no devolvió comentarios: {error}")
        return False
    descartados = len(objetivos) - len(comentarios)
    if descartados:
        informar(f"LucIA descartó {descartados} comentario(s) por no aportar.")
    if not comentarios:
        reportar_error("Ningún comentario pasó la validación de LucIA.")
        return False
    es_python = destino.suffix.lower() == ".py"
    nuevo = insertar(contenido, objetivos, comentarios, es_python)
    if not solo_documenta(contenido, nuevo, es_python):
        reportar_error("El resultado cambia código, no solo comentarios: no se escribe.")
        return False
    try:
        escribir_texto_atomico(destino, nuevo)
    except OSError as error:
        reportar_error(f"No se pudo escribir {destino}: {error}")
        return False
    exito(f"LucIA documentó {len(comentarios)} función(es) en {destino.name} "
          f"(solo comentarios).")
    comando_test_ruta(destino)
    return True


def comando_comentar_archivo() -> None:
    """Comando interactivo: pide el archivo y lo documenta."""
    entrada = input("Archivo a comentar: ").strip().strip("\"'")
    if not entrada:
        reportar_error("No se indicó ningún archivo.")
        return
    comentar_archivo(entrada)
