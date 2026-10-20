"""Submodulo de RFPRMN (refactor: tope 400/450 lineas)."""
from __future__ import annotations
import ast, json, os, re, shutil, stat, subprocess, sys, textwrap, urllib.error, urllib.parse, urllib.request, uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional
try:
    from .stm_base import (E, informar, exito, advertir, reportar_error, pedir_confirmacion, CONFIG_IA_LOCAL, LIMITE_TAMANO_ANALISIS, PATRON_MARCADOR_PENDIENTE, _panel, _imprimir_seguro)
except ImportError:
    pass

# --- Análisis estático de código --------------------------------------------

@dataclass
class AnalisisArchivo:
    """Resultado del análisis estático de un archivo local."""

    ruta: str
    extension: str
    lineas: int = 0
    lineas_vacias: int = 0
    lineas_largas: int = 0
    marcadores_pendientes: int = 0
    funciones: int = 0
    clases: int = 0
    importaciones: int = 0
    funciones_sin_docstring: int = 0
    bloques_except: int = 0
    except_genericos: int = 0
    argumentos_mutables: int = 0
    puntos_decision: int = 0
    sintaxis_valida: Optional[bool] = None
    detalle_sintaxis: str = ""

    def a_dict(self) -> dict:
        """Convierte el análisis en un diccionario serializable a JSON."""
        return asdict(self)


def analizar_archivo_local(ruta: Path) -> AnalisisArchivo:
    """Analiza el archivo: métricas textuales para cualquier extensión y,
    para ``.py``, un recorrido AST (funciones, clases, docstrings ausentes,
    excepciones genéricas, argumentos mutables) útil para planear el cambio."""
    ruta = ruta.resolve()
    contenido = ruta.read_text(encoding="utf-8-sig", errors="replace")
    lineas = contenido.splitlines()

    analisis = AnalisisArchivo(
        ruta=str(ruta),
        extension=ruta.suffix.lower(),
        lineas=len(lineas),
        lineas_vacias=sum(not linea.strip() for linea in lineas),
        lineas_largas=sum(len(linea) > 100 for linea in lineas),
        marcadores_pendientes=sum(
            len(PATRON_MARCADOR_PENDIENTE.findall(linea)) for linea in lineas
        ),
    )
    if analisis.extension != ".py":
        return analisis

    try:
        arbol = ast.parse(contenido, filename=str(ruta))
        analisis.sintaxis_valida = True
    except SyntaxError as error:
        analisis.sintaxis_valida = False
        analisis.detalle_sintaxis = f"línea {error.lineno}, columna {error.offset}: {error.msg}"
        return analisis

    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            analisis.funciones += 1
            if ast.get_docstring(nodo) is None:
                analisis.funciones_sin_docstring += 1
            valores_por_defecto = list(nodo.args.defaults) + [
                valor for valor in nodo.args.kw_defaults if valor is not None
            ]
            analisis.argumentos_mutables += sum(
                isinstance(valor, (ast.List, ast.Dict, ast.Set)) for valor in valores_por_defecto
            )
        elif isinstance(nodo, ast.ClassDef):
            analisis.clases += 1
        elif isinstance(nodo, (ast.Import, ast.ImportFrom)):
            analisis.importaciones += 1
        elif isinstance(nodo, ast.ExceptHandler):
            analisis.bloques_except += 1
            if nodo.type is None:
                analisis.except_genericos += 1
        elif isinstance(nodo, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.BoolOp)):
            analisis.puntos_decision += 1

    return analisis


def crear_plan_refactorizacion(analisis: AnalisisArchivo) -> list[str]:
    """Deriva un plan de pasos concretos a partir de un :class:`AnalisisArchivo`."""
    plan: list[str] = []

    if analisis.sintaxis_valida is False:
        plan.append("Corregir primero el error de sintaxis y agregar una prueba que lo detecte.")
    if analisis.funciones_sin_docstring:
        plan.append(
            f"Documentar las {analisis.funciones_sin_docstring} funciones que no declaran su propósito."
        )
    if analisis.argumentos_mutables:
        plan.append("Eliminar argumentos mutables predeterminados para evitar estado compartido.")
    if analisis.except_genericos or analisis.bloques_except:
        plan.append("Reemplazar capturas generales por errores específicos y contexto de recuperación.")
    if analisis.puntos_decision > 20 or analisis.lineas > 400:
        plan.append("Dividir funciones largas y separar responsabilidades en componentes cohesivos.")
    if analisis.lineas_largas:
        plan.append("Reorganizar las líneas extensas para legibilidad sin cambiar el comportamiento.")
    if analisis.marcadores_pendientes:
        plan.append("Resolver o documentar los marcadores TODO y FIXME antes del cambio.")
    if analisis.extension != ".py":
        plan.append("Definir pruebas de contrato para el lenguaje y conservar la API existente.")

    plan.append("Establecer una línea base con pruebas, lint y métricas antes de modificar el archivo.")
    plan.append("Aplicar cambios pequeños y reversibles, uno por responsabilidad.")
    plan.append("Ejecutar pruebas, lint y typecheck; comparar el resultado con la línea base.")
    return plan


# --- Diagnóstico asistido por LucIA (IA local) ------------------------------

def _crear_diagnostico_respaldo(analisis: AnalisisArchivo) -> str:
    """Genera un diagnóstico determinista cuando el motor de IA local no responde."""
    nombre = Path(analisis.ruta).name
    if analisis.sintaxis_valida is False:
        detalle = f"detecté un error de sintaxis en {analisis.detalle_sintaxis}"
    else:
        detalles = [
            f"{analisis.lineas} líneas",
            f"{analisis.funciones} funciones",
            f"{analisis.clases} clases",
        ]
        if analisis.funciones_sin_docstring:
            detalles.append(f"{analisis.funciones_sin_docstring} funciones sin documentar")
        if analisis.argumentos_mutables:
            detalles.append("argumentos mutables riesgosos")
        if analisis.except_genericos:
            detalles.append("capturas de excepciones demasiado generales")
        detalle = "identifiqué " + ", ".join(detalles)

    return (
        f"Yo, LucIA, revisé {nombre} y {detalle}. "
        "El archivo es un punto válido para refactorizar si primero fijamos su comportamiento "
        "actual y verificamos cada cambio con pruebas."
    )


def _cargar_configuracion_ia_local() -> tuple[str, str]:
    """Lee ``IAlocal.json`` y valida que el endpoint apunte a este mismo equipo."""
    with open(CONFIG_IA_LOCAL, "r", encoding="utf-8") as archivo_config:
        configuracion = json.load(archivo_config)

    endpoint = str(configuracion.get("endpoint", "http://localhost:11434")).rstrip("/")
    uri_local = urllib.parse.urlparse(endpoint)
    if uri_local.scheme not in ("http", "https") or uri_local.hostname not in (
        "localhost", "127.0.0.1", "::1",
    ):
        raise ValueError("El endpoint de IA local debe estar en este equipo.")

    modelo = str(configuracion.get("default_model", "cogito:3b"))
    return endpoint, modelo


def consultar_ia_local(contenido: str, analisis: AnalisisArchivo) -> str:
    """Pide un diagnóstico a LucIA vía un modelo local (Ollama); si el motor
    no responde o la configuración es inválida, cae en el respaldo local."""
    prompt_sistema = (
        "Eres LucIA, una programadora que diagnostica código. Responde en español, "
        "en primera persona y en máximo 90 palabras. Describe solo hallazgos verificables "
        "del archivo, sus riesgos y el primer paso seguro. No generes código."
    )
    try:
        endpoint, modelo = _cargar_configuracion_ia_local()
        contexto = (
            f"Archivo: {Path(analisis.ruta).name}\n"
            f"Métricas: {json.dumps(analisis.a_dict(), ensure_ascii=False)}\n"
            f"Código:\n{contenido[:12000]}"
        )
        carga = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": contexto},
            ],
            "stream": False,
            "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": 300},
        }
        peticion = urllib.request.Request(
            f"{endpoint}/api/chat",
            data=json.dumps(carga).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            resultado = json.loads(respuesta.read().decode("utf-8"))

        if not isinstance(resultado, dict):
            raise ValueError("La respuesta de IA local no es válida.")
        mensaje = resultado.get("message")
        if not isinstance(mensaje, dict):
            raise ValueError("La respuesta de IA local no contiene un mensaje.")

        diagnostico = " ".join(str(mensaje.get("content", "")).split()[:100]).strip()
        return diagnostico or _crear_diagnostico_respaldo(analisis)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as error:
        advertir(f"Motor IA local no disponible ({error}); se usa el diagnóstico local de LucIA.")
        return _crear_diagnostico_respaldo(analisis)


ConsultorIA = Callable[[str, AnalisisArchivo], str]


def comando_ia_local(consultor: Optional[ConsultorIA] = None) -> bool:
    """Analiza el archivo indicado por el usuario y muestra el diagnóstico de
    LucIA; ``consultor`` permite inyectar otra implementación (p. ej. pruebas)."""
    entrada = input("Ruta del archivo a refactorizar: ").strip().strip("\"'")
    if not entrada:
        reportar_error("No se adjuntó ninguna ruta.")
        return False

    ruta = Path(os.path.expandvars(os.path.expanduser(entrada))).resolve()
    if not ruta.exists():
        reportar_error(f"El archivo no existe: {ruta}")
        return False
    if not ruta.is_file():
        reportar_error(f"La ruta no corresponde a un archivo: {ruta}")
        return False

    try:
        if ruta.stat().st_size > LIMITE_TAMANO_ANALISIS:
            reportar_error("El archivo supera el límite local de 2 MB.")
            return False
        contenido = ruta.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as error:
        reportar_error(f"No se pudo leer el archivo: {error}")
        return False

    informar(f"Archivo adjunto: {ruta}")
    informar(f"Tamaño: {ruta.stat().st_size} bytes | Líneas: {len(contenido.splitlines())}")
    if not pedir_confirmacion("¿Desea que se analice el código y se cree un plan de refactorización?"):
        informar("Análisis cancelado.")
        return False

    try:
        analisis = analizar_archivo_local(ruta)
        generador = consultor or consultar_ia_local
        diagnostico = generador(contenido, analisis)
        plan = crear_plan_refactorizacion(analisis)
    except (OSError, ValueError, TypeError) as error:
        reportar_error(f"El análisis local falló: {error}")
        return False

    print()
    _imprimir_seguro(_panel("LucIA · Diagnóstico", diagnostico.strip()))
    _imprimir_seguro(f"\n{E.negrita}Plan de refactorización{E.reset}")
    for indice, paso in enumerate(plan, start=1):
        _imprimir_seguro(f"  {E.cian}{indice}.{E.reset} {paso}")
    return True

