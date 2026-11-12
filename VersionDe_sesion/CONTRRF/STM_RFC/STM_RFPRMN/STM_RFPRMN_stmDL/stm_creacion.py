"""Comando ``crear codigo``: generar un archivo nuevo a partir de LucIA.

A diferencia de ``ds ialocal`` (que refactoriza código existente), aquí no hay
archivo previo: se parte de una **descripción en lenguaje natural**, LucIA
redacta el diagnóstico y el plan, y el modelo local escribe el archivo completo.

Flujo:

1. Descripción + ruta + lenguaje (la extensión sale del lenguaje).
2. **Diagnóstico de creación**: LucIA (modelo local) propone estructura,
   responsabilidades y criterios de aceptación. Si el modelo no está, hay un
   plan de respaldo determinista.
3. **Generación**: el código se pide con el plan como contexto.
4. **Validación**: no vacío, tope de líneas y sintaxis (AST en Python).
5. **Escritura atómica** y aprendizaje del par (descripción → código) para que
   el ``seq2seq`` pueda reutilizarlo.
"""
from __future__ import annotations

import ast
import json
import os
import re
import urllib.request
from pathlib import Path

from .stm_analisis import (
    AnalisisArchivo, ConsultorIA, _cargar_configuracion_ia_local, _modelo_instalado,
)
from .stm_base import (
    EXTENSIONES_POR_LENGUAJE, E, ErrorProyecto, _panel, _imprimir_seguro,
    advertir, exito, informar, pedir_confirmacion, reportar_error,
)
from .stm_fragmentos import LIMITE_LINEAS_REFACTOR
from .stm_fs import escribir_texto_atomico
from .stm_modelos import _asegurar_modelo_codigo, _liberar_ollama
from .stm_refactor import _generar_fragmento

#: Rol del modelo en la fase de diagnóstico.
SISTEMA_DISENO = (
    "Eres LucIA, arquitecta de software. A partir de una petición en lenguaje "
    "natural, redacta un diagnóstico breve y un plan de implementación: "
    "responsabilidades, funciones y clases públicas, entradas y salidas, "
    "errores a manejar y criterios de aceptación. En español, sin código.")

#: Rol del modelo en la fase de generación.
SISTEMA_CREACION = (
    "Eres LucIA. Escribe el archivo COMPLETO y autocontenido que cumple el plan "
    "y la petición. Código limpio, documentado y sin dependencias innecesarias. "
    "Responde SOLO con el código, sin explicaciones ni cercas de markdown.")


def _extension(lenguaje: str, ruta: Path) -> str:
    """Extensión que corresponde al lenguaje (o la de la ruta si es válida)."""
    pedido = (lenguaje or "").strip().lower()
    if pedido in EXTENSIONES_POR_LENGUAJE:
        return EXTENSIONES_POR_LENGUAJE[pedido]
    if ruta.suffix:
        return ruta.suffix.lower()
    return ".py"


def _analisis_para(ruta: Path, lenguaje: str) -> AnalisisArchivo:
    """Análisis sintético (no hay archivo todavía) para inyectar un consultor."""
    return AnalisisArchivo(ruta=str(ruta), extension=_extension(lenguaje, ruta))


def plan_de_respaldo(descripcion: str, lenguaje: str) -> str:
    """Plan determinista cuando el modelo local no responde."""
    resumen = " ".join(str(descripcion).split())[:220]
    return (
        f"Yo, LucIA, no tengo el modelo local disponible, así que propongo este "
        f"plan para un archivo {lenguaje}:\n"
        f"1. Objetivo: {resumen}\n"
        "2. Definir la API pública mínima (funciones y clases) y documentarla.\n"
        "3. Validar entradas y manejar los errores previsibles.\n"
        "4. Evitar dependencias externas y efectos secundarios globales.\n"
        "5. Añadir un bloque de ejemplo de uso al final, protegido por el guard "
        "de ejecución cuando el lenguaje lo permita.")


def _diagnostico_local(descripcion: str, ruta: Path, lenguaje: str) -> str:
    """Pide el plan al modelo local; cae al plan de respaldo si falla."""
    try:
        endpoint, modelo = _cargar_configuracion_ia_local()
        modelo = _modelo_instalado(endpoint, modelo)
        carga = {
            "model": modelo, "stream": False,
            "options": {"temperature": 0.3, "num_predict": 350},
            "messages": [
                {"role": "system", "content": SISTEMA_DISENO},
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
        return texto or plan_de_respaldo(descripcion, lenguaje)
    except Exception as error:  # noqa: BLE001 - se degrada al plan local
        advertir(f"LucIA no pudo diagnosticar ({error}); se usa el plan local.")
        return plan_de_respaldo(descripcion, lenguaje)


def diagnosticar(descripcion: str, ruta: Path, lenguaje: str,
                 consultor: ConsultorIA | None = None) -> str:
    """Diagnóstico y plan de creación (modelo local, consultor o respaldo)."""
    if not str(descripcion).strip():
        raise ErrorProyecto("Sin descripción no hay nada que crear.")
    if consultor is not None:
        return str(consultor(descripcion, _analisis_para(Path(ruta), lenguaje)))
    return _diagnostico_local(descripcion, Path(ruta), lenguaje)


def validar_codigo(texto: str, ruta: Path) -> str:
    """Valida el código generado y devuelve el texto listo para escribir."""
    limpio = re.sub(r"^```[a-zA-Z0-9]*\n|```$", "", (texto or "").strip(),
                    flags=re.MULTILINE).strip()
    if not limpio:
        raise ErrorProyecto("El modelo devolvió código vacío.")
    lineas = limpio.splitlines()
    if len(lineas) > LIMITE_LINEAS_REFACTOR:
        raise ErrorProyecto(
            f"El código ocupa {len(lineas)} líneas (tope {LIMITE_LINEAS_REFACTOR}).")
    if Path(ruta).suffix.lower() == ".py":
        try:
            ast.parse(limpio)
        except SyntaxError as error:
            raise ErrorProyecto(
                f"Sintaxis inválida (línea {error.lineno}: {error.msg}).")
    return limpio + "\n"


def generar_codigo(descripcion: str, diagnostico: str, ruta: Path,
                   lenguaje: str) -> str:
    """Genera el archivo completo con el modelo local, usando el plan como contexto."""
    try:
        endpoint, _ = _cargar_configuracion_ia_local()
    except (OSError, ValueError) as error:
        raise ErrorProyecto(f"Configuración de IA local no disponible ({error}).")
    modelo = _asegurar_modelo_codigo()
    _liberar_ollama(excepto=modelo)
    contexto = (f"[PLAN DE LUCIA — cúmplelo]\n{diagnostico}\n[FIN DEL PLAN]\n"
                f"[LENGUAJE] {lenguaje}\n")
    return _generar_fragmento(endpoint, modelo, Path(ruta).name, descripcion,
                              1, 1, 90, contexto=contexto,
                              sistema=SISTEMA_CREACION)


def _aprender(descripcion: str, codigo: str) -> None:
    """Memoriza el par para el seq2seq (best-effort)."""
    try:
        from . import stm_seq2seq

        stm_seq2seq.aprender(descripcion, codigo)
    except Exception:  # noqa: BLE001 - el aprendizaje es opcional
        pass


def crear_codigo(ruta: str, descripcion: str, lenguaje: str = "python",
                 consultor: ConsultorIA | None = None) -> bool:
    """Crea el archivo ``ruta`` a partir de ``descripcion``; True si se escribió."""
    if not str(descripcion).strip():
        reportar_error("Sin descripción no hay nada que crear.")
        return False
    destino = Path(os.path.expandvars(os.path.expanduser(str(ruta)))).resolve()
    extension = _extension(lenguaje, destino)
    if destino.suffix.lower() != extension:
        destino = destino.with_suffix(extension)
    if destino.exists() and destino.stat().st_size > 0:
        advertir(f"{destino} ya existe y no está vacío.")
        if not pedir_confirmacion("¿Se sobrescribe?"):
            informar("Creación cancelada.")
            return False
    try:
        diagnostico = diagnosticar(descripcion, destino, lenguaje, consultor)
    except ErrorProyecto as error:
        reportar_error(str(error))
        return False
    _imprimir_seguro(_panel("LucIA · Diagnóstico de creación", diagnostico.strip()))
    print(f"\n{E.negrita}Petición{E.reset}: {' '.join(descripcion.split())[:200]}")
    if not pedir_confirmacion("¿Se genera el código con este plan?"):
        informar("Creación cancelada.")
        return False
    try:
        codigo = generar_codigo(descripcion, diagnostico, destino, lenguaje)
        codigo = validar_codigo(codigo, destino)
    except ErrorProyecto as error:
        reportar_error(f"No se pudo generar el código: {error}")
        return False
    try:
        escribir_texto_atomico(destino, codigo)
    except OSError as error:
        reportar_error(f"No se pudo escribir {destino}: {error}")
        return False
    exito(f"Código creado ({len(codigo.splitlines())} líneas): {destino}")
    _aprender(descripcion, codigo)
    from .test import comando_test_ruta

    comando_test_ruta(destino)
    return True


def comando_crear_codigo() -> None:
    """Comando interactivo: pide ruta, descripción y lenguaje, y crea el archivo."""
    ruta = input("Ruta del archivo a crear: ").strip().strip("\"'")
    if not ruta:
        reportar_error("No se indicó ninguna ruta.")
        return
    descripcion = input("¿Qué debe hacer el código? (lenguaje natural): ").strip()
    lenguaje = input("Lenguaje (python, csharp, javascript...): ").strip().lower()
    crear_codigo(ruta, descripcion, lenguaje or "python")


def copiar_codigo(ruta_origen: str | Path, ruta_destino: str | Path) -> dict[str, Any]:
    """Copia todas las líneas de un archivo de código fuente a otro archivo destino.

    Solo copia las líneas íntegras tal cual, sin alterar lógica ni dependencias,
    escribiendo de forma atómica en el archivo de destino.

    Parameters
    ----------
    ruta_origen : str | Path
        Ruta del archivo de código fuente existente a copiar.
    ruta_destino : str | Path
        Ruta del archivo de código destino donde se pegará el contenido.

    Returns
    -------
    dict[str, Any]
        Diccionario con 'ok', 'origen', 'destino', 'lineas' y 'caracteres'.
    """
    origen = Path(os.path.expandvars(os.path.expanduser(str(ruta_origen).strip().strip("\"'")))).resolve()
    destino = Path(os.path.expandvars(os.path.expanduser(str(ruta_destino).strip().strip("\"'")))).resolve()

    if not origen.exists():
        raise ErrorProyecto(f"El archivo fuente no existe: {origen}")
    if not origen.is_file():
        raise ErrorProyecto(f"La ruta de origen no es un archivo: {origen}")

    try:
        contenido = origen.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        contenido = origen.read_text(encoding="latin-1")

    destino.parent.mkdir(parents=True, exist_ok=True)
    escribir_texto_atomico(destino, contenido)

    num_lineas = len(contenido.splitlines())
    return {
        "ok": True,
        "origen": str(origen),
        "destino": str(destino),
        "lineas": num_lineas,
        "caracteres": len(contenido),
    }


def comando_copiar_codigo(ruta_origen: str = "", ruta_destino: str = "") -> bool:
    """Comando 'copiar codigo': copia las líneas de un archivo fuente a un archivo destino."""
    orig = ruta_origen.strip().strip("\"'")
    if not orig:
        orig = input("Ruta del archivo de código fuente: ").strip().strip("\"'")
    if not orig:
        reportar_error("Ruta de origen no válida.")
        return False

    dest = ruta_destino.strip().strip("\"'")
    if not dest:
        dest = input("Ruta del archivo de código vacío (destino): ").strip().strip("\"'")
    if not dest:
        reportar_error("Ruta de destino no válida.")
        return False

    try:
        res = copiar_codigo(orig, dest)
        exito(f"Código copiado exitosamente ({res['lineas']} líneas):")
        informar(f"  Origen : {res['origen']}")
        informar(f"  Destino: {res['destino']}")
        return True
    except (ErrorProyecto, OSError) as error:
        reportar_error(f"No se pudo copiar el código: {error}")
        return False

