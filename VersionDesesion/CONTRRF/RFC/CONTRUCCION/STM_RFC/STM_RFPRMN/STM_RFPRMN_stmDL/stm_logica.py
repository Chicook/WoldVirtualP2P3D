"""Comando ``crear logica``: de «qué quiero que haga» a la función.

A diferencia de ``crear codigo`` (archivo completo, pide ruta y lenguaje desde
el principio), aquí **lo único obligatorio es la petición en lenguaje natural**.
LucIA diseña la lógica —firma, entradas y salidas, casos límite, algoritmo— y el
modelo local escribe la función. Después:

- si indicas un archivo existente, la lógica se **añade** al final sin tocar lo
  que ya había (y se valida el conjunto);
- si no indicas archivo, se crea uno con nombre derivado de la petición.

Se valida, se escribe de forma atómica y se pasa el módulo ``test`` para dar el
diagnóstico de deuda del resultado.
"""
from __future__ import annotations

import ast
import json
import os
import re
import unicodedata
import urllib.request
from pathlib import Path

from .stm_analisis import (
    AnalisisArchivo, ConsultorIA, _cargar_configuracion_ia_local, _modelo_instalado,
)
from .stm_base import (
    EXTENSIONES_POR_LENGUAJE, ErrorProyecto, _panel, _imprimir_seguro,
    advertir, exito, informar, pedir_confirmacion, reportar_error,
)
from .stm_fragmentos import LIMITE_LINEAS_REFACTOR
from .stm_fs import escribir_texto_atomico
from .stm_modelos import _asegurar_modelo_codigo, _liberar_ollama
from .stm_refactor import _generar_fragmento
from .test import comando_test_ruta

#: Rol del modelo al diseñar la lógica.
SISTEMA_LOGICA_DISENO = (
    "Eres LucIA, diseñadora de algoritmos. A partir de una petición en lenguaje "
    "natural define la lógica: nombre y firma de la función o funciones, "
    "parámetros y tipos, qué devuelve, casos límite y errores, y el algoritmo "
    "paso a paso. En español y sin escribir código.")

#: Rol del modelo al escribir la lógica.
SISTEMA_LOGICA_CODIGO = (
    "Eres LucIA. Escribe SOLO la lógica pedida como función o funciones "
    "autocontenidas, con docstring y validación de entradas. Sin ejemplo de uso, "
    "sin explicaciones y sin cercas de markdown.")

#: Palabras que no aportan al nombre del archivo.
_VACIAS = frozenset({"una", "un", "el", "la", "los", "las", "que", "de", "del",
                     "para", "con", "por", "como", "y", "o", "en", "al", "se",
                     "me", "mi", "quiero", "necesito", "funcion", "funciones",
                     "codigo", "logica", "cree", "crea", "haga"})


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos (para nombres de archivo seguros)."""
    sin_acentos = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_acentos if not unicodedata.combining(c)).lower()


def nombre_desde(descripcion: str, maximo: int = 4) -> str:
    """Nombre de archivo derivado de la petición (``logica_<palabras>.py``)."""
    palabras = re.findall(r"[a-z0-9]+", _normalizar(descripcion))
    utiles = [palabra for palabra in palabras if palabra not in _VACIAS]
    elegidas = (utiles or palabras)[:maximo]
    base = "_".join(elegidas) or "nueva"
    return f"logica_{base[:48]}.py"


def _extension(lenguaje: str, ruta: Path) -> str:
    """Extensión del lenguaje pedido (o la de la ruta)."""
    pedido = (lenguaje or "").strip().lower()
    if pedido in EXTENSIONES_POR_LENGUAJE:
        return EXTENSIONES_POR_LENGUAJE[pedido]
    return ruta.suffix.lower() or ".py"


def _lenguaje_de(ruta: Path) -> str:
    """Lenguaje a partir de la extensión (``python`` si no se reconoce)."""
    sufijo = ruta.suffix.lower()
    for nombre, extension in EXTENSIONES_POR_LENGUAJE.items():
        if extension == sufijo:
            return nombre
    return "python"


def _analisis_para(ruta: Path, lenguaje: str) -> AnalisisArchivo:
    """Análisis sintético para inyectar un consultor en las pruebas."""
    return AnalisisArchivo(ruta=str(ruta), extension=_extension(lenguaje, ruta))


def diseno_de_respaldo(descripcion: str, lenguaje: str) -> str:
    """Diseño determinista cuando el modelo local no responde."""
    resumen = " ".join(str(descripcion).split())[:220]
    return (
        f"Yo, LucIA, diseñaría esta lógica en {lenguaje}:\n"
        f"1. Objetivo: {resumen}\n"
        "2. Una función principal con nombre descriptivo y parámetros tipados.\n"
        "3. Devolver el resultado; no imprimir ni tener efectos globales.\n"
        "4. Validar entradas y lanzar un error claro si no cumplen.\n"
        "5. Cubrir los casos límite: vacío, cero, negativos y tipos erróneos.")


def _diseno_local(descripcion: str, ruta: Path, lenguaje: str) -> str:
    """Pide el diseño al modelo local; cae al respaldo si falla."""
    try:
        endpoint, modelo = _cargar_configuracion_ia_local()
        modelo = _modelo_instalado(endpoint, modelo)
        carga = {
            "model": modelo, "stream": False,
            "options": {"temperature": 0.3, "num_predict": 320},
            "messages": [
                {"role": "system", "content": SISTEMA_LOGICA_DISENO},
                {"role": "user", "content": (
                    f"Archivo: {ruta.name}\nLenguaje: {lenguaje}\n"
                    f"Petición: {descripcion}")}],
        }
        peticion = urllib.request.Request(
            f"{endpoint}/api/chat", data=json.dumps(carga).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(peticion, timeout=90) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        mensaje = datos.get("message") if isinstance(datos, dict) else None
        texto = str((mensaje or {}).get("content", "")).strip()
        return texto or diseno_de_respaldo(descripcion, lenguaje)
    except Exception as error:  # noqa: BLE001 - se degrada al diseño local
        advertir(f"LucIA no pudo diseñar ({error}); se usa el diseño local.")
        return diseno_de_respaldo(descripcion, lenguaje)


def disenar(descripcion: str, ruta: Path, lenguaje: str,
            consultor: ConsultorIA | None = None) -> str:
    """Diseño de la lógica (modelo local, consultor o respaldo determinista)."""
    if not str(descripcion).strip():
        raise ErrorProyecto("Sin petición no hay nada que diseñar.")
    if consultor is not None:
        return str(consultor(descripcion, _analisis_para(Path(ruta), lenguaje)))
    return _diseno_local(descripcion, Path(ruta), lenguaje)


def validar_logica(texto: str, ruta: Path) -> str:
    """Valida la lógica generada y la devuelve lista para escribir."""
    limpio = re.sub(r"^```[a-zA-Z0-9]*\n|```$", "", (texto or "").strip(),
                    flags=re.MULTILINE).strip()
    if not limpio:
        raise ErrorProyecto("El modelo devolvió una lógica vacía.")
    if len(limpio.splitlines()) > LIMITE_LINEAS_REFACTOR:
        raise ErrorProyecto(f"La lógica ocupa demasiadas líneas "
                            f"(tope {LIMITE_LINEAS_REFACTOR}).")
    if Path(ruta).suffix.lower() == ".py":
        try:
            ast.parse(limpio)
        except SyntaxError as error:
            raise ErrorProyecto(
                f"Sintaxis inválida (línea {error.lineno}: {error.msg}).")
    return limpio + "\n"


def generar_logica(descripcion: str, diseno: str, ruta: Path,
                   lenguaje: str) -> str:
    """Genera la lógica con el modelo local, usando el diseño como contexto."""
    try:
        endpoint, _ = _cargar_configuracion_ia_local()
    except (OSError, ValueError) as error:
        raise ErrorProyecto(f"Configuración de IA local no disponible ({error}).")
    modelo = _asegurar_modelo_codigo()
    _liberar_ollama(excepto=modelo)
    contexto = (f"[DISEÑO DE LUCIA — cúmplelo]\n{diseno}\n[FIN DEL DISEÑO]\n"
                f"[LENGUAJE] {lenguaje}\n")
    return _generar_fragmento(endpoint, modelo, Path(ruta).name, descripcion,
                              1, 1, 90, contexto=contexto,
                              sistema=SISTEMA_LOGICA_CODIGO)


def _aprender(descripcion: str, codigo: str) -> None:
    """Memoriza el par para el seq2seq (best-effort)."""
    try:
        from . import stm_seq2seq

        stm_seq2seq.aprender(descripcion, codigo)
    except Exception:  # noqa: BLE001 - el aprendizaje es opcional
        pass


def crear_logica(descripcion: str, ruta: str | None = None,
                 lenguaje: str = "", consultor: ConsultorIA | None = None) -> bool:
    """Crea (o amplía) la lógica pedida; True si se escribió."""
    if not str(descripcion).strip():
        reportar_error("Sin petición no hay nada que crear.")
        return False
    destino = Path(os.path.expandvars(os.path.expanduser(
        str(ruta) if ruta else nombre_desde(descripcion)))).resolve()
    lenguaje = (lenguaje or "").strip().lower() or _lenguaje_de(destino)
    extension = _extension(lenguaje, destino)
    if destino.suffix.lower() != extension:
        destino = destino.with_suffix(extension)
    try:
        original = destino.read_text(encoding="utf-8-sig") if destino.is_file() else ""
    except OSError as error:
        reportar_error(f"No se pudo leer {destino}: {error}")
        return False
    try:
        diseno = disenar(descripcion, destino, lenguaje, consultor)
    except ErrorProyecto as error:
        reportar_error(str(error))
        return False
    _imprimir_seguro(_panel("LucIA · Diseño de la lógica", diseno.strip()))
    informar(f"Destino: {destino}"
             + (f" (se añade a {len(original.splitlines())} líneas)"
                if original.strip() else " (archivo nuevo)"))
    if not pedir_confirmacion("¿Se genera la lógica con este diseño?"):
        informar("Creación cancelada.")
        return False
    try:
        codigo = generar_logica(descripcion, diseno, destino, lenguaje)
        codigo = validar_logica(codigo, destino)
        nuevo = (original.rstrip() + "\n\n\n" + codigo) if original.strip() else codigo
        if original.strip():
            validar_logica(nuevo, destino)
    except ErrorProyecto as error:
        reportar_error(f"No se pudo generar la lógica: {error}")
        return False
    try:
        escribir_texto_atomico(destino, nuevo)
    except OSError as error:
        reportar_error(f"No se pudo escribir {destino}: {error}")
        return False
    exito(f"Lógica escrita ({len(codigo.splitlines())} líneas): {destino}")
    _aprender(descripcion, codigo)
    comando_test_ruta(destino)
    return True


def comando_crear_logica() -> None:
    """Comando interactivo: lo único obligatorio es qué quieres que haga."""
    descripcion = input("¿Qué lógica quieres? (en lenguaje natural): ").strip()
    if not descripcion:
        reportar_error("No se indicó qué lógica crear.")
        return
    ruta = input("Archivo donde añadirla (vacío = archivo nuevo): ").strip().strip("\"'")
    lenguaje = input("Lenguaje (vacío = deducir): ").strip().lower()
    crear_logica(descripcion, ruta or None, lenguaje)
