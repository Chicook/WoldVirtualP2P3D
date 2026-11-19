"""Pruebas estáticas y diagnóstico de deuda técnica de un archivo.

Se llama ``test`` (como pidió el proyecto) y vive dentro del paquete, así que
solo se importa como ``STM_RFPRMN_stmDL.test``: no tapa el ``test`` de la
biblioteca estándar ni lo recoge pytest.

**Qué hace y qué no.** No ejecuta el código: compilar y analizar es seguro;
ejecutar código ajeno desde una herramienta de gestión no lo es. La batería es:

1. lectura y tamaño,
2. sintaxis (AST en Python; llaves y paréntesis en el resto),
3. lint con ``ruff`` si está instalado (solo ``.py``),
4. métricas estructurales y deuda con ``stm_lucia.deuda_tecnica``,
5. puntuación 0-100 y nivel (sano / aceptable / revisar / crítico).

Se usa para validar lo recién refactorizado (comparando antes/después) o
cualquier archivo que se quiera revisar.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from .stm_analisis import analizar_archivo_local
from .stm_base import (
    E, ErrorProyecto, _caja, _imprimir_seguro, informar, reportar_error,
)
from .stm_fragmentos import LIMITE_LINEAS_REFACTOR
from .stm_lucia import deuda_tecnica

#: Niveles de salud, de mejor a peor (umbral mínimo de puntuación).
NIVELES = ((85, "sano"), (70, "aceptable"), (50, "revisar"), (0, "crítico"))


def _lint(ruta: Path) -> dict:
    """Ejecuta ``ruff`` sobre un ``.py``; si no está, lo dice sin fallar."""
    if ruta.suffix.lower() != ".py":
        return {"disponible": False, "problemas": 0, "detalle": []}
    try:
        proceso = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--select", "E,F",
             "--no-cache", "--output-format", "concise", str(ruta)],
            capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return {"disponible": False, "problemas": 0, "detalle": []}
    if "No module named ruff" in (proceso.stderr or ""):
        return {"disponible": False, "problemas": 0, "detalle": []}
    # Formato conciso de ruff: "ruta:linea:col: CODIGO mensaje". Se filtra así
    # para no contar "All checks passed!" ni "Found N errors" como hallazgos.
    patron = re.compile(r".+:\d+:\d+: [A-Z]+\d+")
    lineas = [linea for linea in (proceso.stdout or "").splitlines()
              if patron.match(linea.strip())]
    return {"disponible": True, "problemas": len(lineas), "detalle": lineas[:3]}


def _balanceado(texto: str) -> bool:
    """Comprueba llaves, corchetes y paréntesis (aproximado, sin cadenas)."""
    parejas = {")": "(", "]": "[", "}": "{"}
    pila: list[str] = []
    comilla = ""
    for caracter in texto:
        if comilla:
            if caracter == comilla:
                comilla = ""
            continue
        if caracter in "\"'":
            comilla = caracter
        elif caracter in "([{":
            pila.append(caracter)
        elif caracter in parejas:
            if not pila or pila.pop() != parejas[caracter]:
                return False
    return not pila


def _descuentos(analisis, lint: dict, sintaxis_ok=True) -> list[tuple[str, int]]:
    """Lista (motivo, puntos) que se restan de los 100 iniciales."""
    motivos: list[tuple[str, int]] = []
    if analisis.sintaxis_valida is False:
        motivos.append((f"sintaxis inválida: {analisis.detalle_sintaxis}", 100))
    elif sintaxis_ok is False:
        motivos.append(("delimitadores desbalanceados", 60))
    if analisis.funciones_sin_docstring:
        motivos.append((f"{analisis.funciones_sin_docstring} funciones sin docstring",
                        min(20, analisis.funciones_sin_docstring * 4)))
    if analisis.except_genericos:
        motivos.append((f"{analisis.except_genericos} capturas genéricas",
                        min(20, analisis.except_genericos * 6)))
    if analisis.argumentos_mutables:
        motivos.append((f"{analisis.argumentos_mutables} argumentos mutables",
                        min(15, analisis.argumentos_mutables * 6)))
    if analisis.lineas_largas:
        motivos.append((f"{analisis.lineas_largas} líneas de más de 100 caracteres",
                        min(12, analisis.lineas_largas // 5 + 2)))
    if analisis.marcadores_pendientes:
        motivos.append((f"{analisis.marcadores_pendientes} TODO/FIXME",
                        min(10, analisis.marcadores_pendientes * 2)))
    if analisis.lineas > LIMITE_LINEAS_REFACTOR:
        motivos.append((f"{analisis.lineas} líneas (tope {LIMITE_LINEAS_REFACTOR})", 15))
    if analisis.puntos_decision > 20:
        motivos.append((f"complejidad alta ({analisis.puntos_decision} decisiones)", 10))
    if lint.get("problemas"):
        motivos.append((f"{lint['problemas']} avisos de ruff", min(24, lint["problemas"] * 3)))
    return motivos


def _nivel(puntuacion: int) -> str:
    """Etiqueta de salud para una puntuación 0-100."""
    for umbral, nombre in NIVELES:
        if puntuacion >= umbral:
            return nombre
    return "crítico"


def diagnostico_deuda(ruta: str | Path) -> dict:
    """Analiza ``ruta`` y devuelve el diagnóstico completo de deuda técnica."""
    objetivo = Path(ruta)
    if not objetivo.is_file():
        raise ErrorProyecto(f"No existe el archivo: {objetivo}")
    try:
        contenido = objetivo.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as error:
        raise ErrorProyecto(f"No se pudo leer {objetivo}: {error}") from error
    analisis = analizar_archivo_local(objetivo)
    lint = _lint(objetivo)
    sintaxis_ok = analisis.sintaxis_valida
    if sintaxis_ok is None and objetivo.suffix.lower() != ".py":
        sintaxis_ok = _balanceado(contenido)
    motivos = _descuentos(analisis, lint, bool(sintaxis_ok))
    puntuacion = max(0, min(100, 100 - sum(puntos for _, puntos in motivos)))
    return {
        "ruta": str(objetivo),
        "lenguaje": analisis.extension or "(sin extensión)",
        "lineas": analisis.lineas,
        "funciones": analisis.funciones,
        "clases": analisis.clases,
        "sintaxis_ok": sintaxis_ok,
        "hallazgos": deuda_tecnica(analisis),
        "motivos": motivos,
        "lint": lint,
        "puntuacion": puntuacion,
        "nivel": _nivel(puntuacion),
    }


def puntuacion_deuda(ruta: str | Path) -> int:
    """Puntuación 0-100 de un archivo (100 si no se puede medir)."""
    try:
        return int(diagnostico_deuda(ruta)["puntuacion"])
    except ErrorProyecto:
        return 100


def mensaje_comparacion(antes: int, ruta: str | Path) -> str:
    """Compara la puntuación previa con la actual y lo redacta en una línea."""
    ahora = puntuacion_deuda(ruta)
    cambio = ahora - antes
    if cambio > 0:
        return f"Deuda técnica: {antes} -> {ahora}/100 (mejora {cambio})."
    if cambio == 0:
        return f"Deuda técnica: {antes} -> {ahora}/100 (sin cambios)."
    return f"Deuda técnica: {antes} -> {ahora}/100 (empeora {abs(cambio)})."


def formatear(informe: dict) -> str:
    """Caja con el resumen del diagnóstico."""
    filas = [
        ("Archivo", Path(informe["ruta"]).name),
        ("Lenguaje", informe["lenguaje"]),
        ("Tamaño", f"{informe['lineas']} líneas · {informe['funciones']} funciones · "
                   f"{informe['clases']} clases"),
        ("Sintaxis", "válida" if informe["sintaxis_ok"] else "inválida"),
        ("Lint", ("ruff no disponible" if not informe["lint"]["disponible"]
                  else f"{informe['lint']['problemas']} avisos")),
        ("Puntuación", f"{informe['puntuacion']}/100 · {informe['nivel']}"),
    ]
    texto = _caja("Diagnóstico de deuda técnica", filas,
                  color="verde" if informe["puntuacion"] >= 70 else "amarillo")
    if informe["motivos"]:
        texto += f"\n{E.negrita}Descuentos{E.reset}: " + "; ".join(
            f"{motivo} (-{puntos})" for motivo, puntos in informe["motivos"])
    return texto


def comando_test_ruta(ruta: str | Path) -> dict:
    """Diagnostica ``ruta`` y lo muestra; devuelve el informe ({} si falla)."""
    try:
        informe = diagnostico_deuda(ruta)
    except ErrorProyecto as error:
        reportar_error(str(error))
        return {}
    _imprimir_seguro(formatear(informe))
    for hallazgo in informe["hallazgos"]:
        _imprimir_seguro(f"  · {hallazgo}")
    if informe["lint"]["problemas"]:
        for linea in informe["lint"]["detalle"]:
            _imprimir_seguro(f"  ! {linea}")
    return informe


def comando_test() -> None:
    """Comando interactivo: pide un archivo y muestra su diagnóstico de deuda."""
    entrada = input("Archivo a probar: ").strip().strip("\"'")
    if not entrada:
        reportar_error("No se indicó ningún archivo.")
        return
    informe = comando_test_ruta(entrada)
    if informe:
        informar(f"Diagnóstico guardado en memoria · nivel {informe['nivel']}")
