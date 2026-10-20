"""Submodulo de RFPRMN (refactor: tope 400/450 lineas)."""
from __future__ import annotations
import ast, json, os, re, shutil, stat, subprocess, sys, textwrap, urllib.error, urllib.parse, urllib.request, uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional
try:
    from .stm_base import (E, informar, exito, advertir, reportar_error, pedir_confirmacion, ErrorProyecto, CONFIG_IA_LOCAL, SRC_DIR, _panel, _imprimir_seguro)
    from .stm_analisis import AnalisisArchivo, analizar_archivo_local, crear_plan_refactorizacion, consultar_ia_local, ConsultorIA
    from .stm_modelos import (DIR_MODELOS_LOCAL, HF_REPO_CODIGO, HF_ARCHIVO_CODIGO, MODELOS_CODIGO_LIGEROS, LIMITE_LINEAS_REFACTOR, LINEAS_POR_FRAGMENTO, REGISTRO_REFACTOR_MD, MODELOS_OR_CODIGO, ENDPOINT_OPENROUTER, _leer_openrouter_key, _chat_openrouter, _descargar_peso_hf, _modelos_ollama_instalados, _es_modelo_codigo, _leer_candidatos_codigo, _borrar_peso_local, _descargar_modelo_ollama, _modelos_usados_registro, _asegurar_modelo_codigo, _borrar_modelo_ollama, _liberar_ollama)
except ImportError:
    pass


def _generar_fragmento(endpoint: str, modelo: str, nombre_archivo: str,
                       fragmento: str, num: int, total: int,
                       timeout_primer_token: int) -> str:
    """Refactoriza UN fragmento (~60 líneas) con el modelo local en stream."""
    import threading as _th, time as _tm
    carga = {"model": modelo, "messages": [
        {"role": "system", "content": (
            "Eres LucIA. Refactoriza el fragmento de código sin cambiar su "
            "comportamiento: nombres claros, sin duplicados, documenta lo esencial. "
            "Responde SOLO con código, sin explicaciones ni cercas.")},
        {"role": "user", "content": f"Archivo: {nombre_archivo} (parte {num}/{total})\n{fragmento}"}],
        "stream": True, "keep_alive": "10m",
        "options": {"temperature": 0.2, "num_predict": 800, "num_ctx": 2048}}
    pet = urllib.request.Request(
        f"{endpoint}/api/chat", data=json.dumps(carga).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    piezas: list[str] = []
    estado: dict = {"error": None, "resp": None}
    primer_token = _th.Event()
    terminado = _th.Event()

    def _trabajar() -> None:
        try:
            with urllib.request.urlopen(pet, timeout=900) as resp:
                estado["resp"] = resp
                while True:
                    linea = resp.readline()
                    if not linea:
                        break
                    try:
                        evento = json.loads(linea.decode("utf-8"))
                    except ValueError:
                        continue
                    delta = str(evento.get("message", {}).get("content", ""))
                    if delta:
                        piezas.append(delta)
                        primer_token.set()
                    if evento.get("done"):
                        break
        except Exception as error:  # noqa: BLE001 - se reporta al hilo principal
            estado["error"] = error
        finally:
            primer_token.set()
            terminado.set()

    _t0 = _tm.time()
    _th.Thread(target=_trabajar, daemon=True).start()
    while not primer_token.wait(20):
        trasc = int(_tm.time() - _t0)
        if trasc >= timeout_primer_token:
            try:
                if estado["resp"] is not None:
                    estado["resp"].close()
            except Exception:
                pass
            raise ErrorProyecto(f"{modelo} sin respuesta en {timeout_primer_token}s (frag {num}).")
        _imprimir_seguro(f"[REFACTOR {num}/{total}] esperando... {trasc}s")
    if estado["error"] is not None and not piezas:
        raise ErrorProyecto(f"El modelo {modelo} no respondió ({estado['error']}).")
    # Espera al fin del stream con progreso por líneas (tope 10 min/fragmento).
    _t1, ultimo_n = _tm.time(), 0
    while not terminado.wait(15):
        n = "".join(piezas).count("\n") + 1
        if n != ultimo_n:
            _imprimir_seguro(f"[REFACTOR {num}/{total}] ...{n} líneas")
            ultimo_n = n
        if _tm.time() - _t1 > 600:
            _imprimir_seguro(f"[REFACTOR {num}/{total}] Tope 10 min; se usa lo generado.")
            break
    if not piezas:
        raise ErrorProyecto(f"El modelo {modelo} devolvió vacío (frag {num}).")
    texto = "".join(piezas).strip()
    return re.sub(r"^```[a-zA-Z]*\n|```$", "", texto, flags=re.MULTILINE).strip()


def _refactorizar_con_modelo(contenido: str, analisis: AnalisisArchivo, modelo: str,
                             timeout_primer_token: int = 60) -> str:
    """Refactoriza POR FRAGMENTOS de 60 líneas (viable en CPU) y une el resultado.

    Cada fragmento entra en el vigilante de ``timeout_primer_token`` segundos;
    el total respeta el tope 400/450 líneas.
    """
    import time as _tm
    endpoint, _ = _cargar_configuracion_ia_local()
    lineas = contenido.splitlines()
    # Corte en fronteras seguras (línea en blanco o def/class), nunca a mitad
    # de llamada/expresión: previene el caso mainLCSTM.py:153 '(' sin cerrar.
    fragmentos: list[list[str]] = []
    actual: list[str] = []
    for ln in lineas:
        actual.append(ln)
        if len(actual) >= LINEAS_POR_FRAGMENTO and (
                not ln.strip() or re.match(r"\s*(def |class |if |for |while |try:|else:|elif )", ln)):
            fragmentos.append(actual)
            actual = []
    if actual:
        fragmentos.append(actual)
    fragmentos_txt = ["\n".join(f) for f in fragmentos]
    total = len(fragmentos_txt)
    _imprimir_seguro(f"[REFACTOR] {len(lineas)} líneas en {total} fragmentos con {modelo}.")
    _imprimir_seguro(f"[VIGILANTE] {timeout_primer_token}s por fragmento; si falla, "
                     f"se borra {modelo} y se prueba con otra IA.")
    nombre = Path(analisis.ruta).name
    salidas: list[str] = []
    for num, frag in enumerate(fragmentos_txt, start=1):
        _t0 = _tm.time()
        salidas.append(_generar_fragmento(endpoint, modelo, nombre, frag, num, total,
                                          timeout_primer_token))
        _imprimir_seguro(f"[REFACTOR {num}/{total}] OK en {int(_tm.time() - _t0)}s")
    texto = "\n".join(salidas).strip()
    lineas_out = texto.splitlines()
    if len(lineas_out) > LIMITE_LINEAS_REFACTOR:
        advertir(f"El resultado tiene {len(lineas_out)} líneas; se recorta a {LIMITE_LINEAS_REFACTOR}.")
        texto = "\n".join(lineas_out[:LIMITE_LINEAS_REFACTOR])
    _imprimir_seguro("[REFACTOR] Generación terminada.")
    return texto


def _validar_refactor(original: str, nuevo: str, ruta: Path) -> str:
    """Previene refactors rotos: valida sintaxis, tope 400/450 y fidelidad mínima.

    - ``.py``: debe compilar con ``ast`` (evita paréntesis sin cerrar, cortes
      entre fragmentos como el de ``mainLCSTM.py:153``).
    - No vacío y como máximo ``LIMITE_LINEAS_REFACTOR`` líneas.
    - Conserva al menos el 80% de las funciones/clases originales (detecta
      fragmentos perdidos o inventados).
    Lanza ``ErrorProyecto`` con el motivo si no es seguro sobrescribir.
    """
    texto = nuevo.strip()
    if not texto:
        raise ErrorProyecto("Refactor vacío: no se sobrescribe.")
    lineas = texto.splitlines()
    if len(lineas) > LIMITE_LINEAS_REFACTOR:
        raise ErrorProyecto(f"Refactor con {len(lineas)} líneas (tope {LIMITE_LINEAS_REFACTOR}).")
    if ruta.suffix.lower() == ".py":
        try:
            ast.parse(texto, filename=str(ruta))
        except SyntaxError as error:
            raise ErrorProyecto(
                f"Sintaxis inválida (línea {error.lineno}: {error.msg}): no se sobrescribe.")

        def _nombres(src: str) -> set[str]:
            try:
                arbol = ast.parse(src)
            except SyntaxError:
                return set()
            return {n.name for n in ast.walk(arbol)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}

        orig, sal = _nombres(original), _nombres(texto)
        if orig and len(orig - sal) / len(orig) > 0.2:
            faltan = sorted(orig - sal)[:8]
            raise ErrorProyecto(f"Se perderían definiciones {faltan}: no se sobrescribe.")
    return texto + "\n"


def _registrar_refactor_md(ruta: Path, modelo: str, descripcion: str) -> None:
    """Añade al .md de registro qué hizo el modelo y su nombre (evita re-descargas)."""
    REGISTRO_REFACTOR_MD.parent.mkdir(parents=True, exist_ok=True)
    entrada = (f"\n## {ruta.name} — {modelo}\n"
               f"Fecha: {__import__('datetime').datetime.now().isoformat(timespec='seconds')}\n"
               f"Archivo: {ruta}\nDescripción del modelo: {descripcion.strip()}\n")
    with open(REGISTRO_REFACTOR_MD, "a", encoding="utf-8") as f:
        f.write(entrada)
    exito(f"Registro guardado en: {REGISTRO_REFACTOR_MD}")


def _pedir_extra_o_diagnostico(contenido: str, analisis: AnalisisArchivo) -> None:
    """Tras un 'no', ofrece: 1 = el usuario añade algo, 2 = diagnóstico completo."""
    print(f"{E.negrita}¿Quieres tú añadir algo? ¿Necesitas un diagnóstico más completo?{E.reset}")
    print("  1 · Añadir algo propio al plan")
    print("  2 · Diagnóstico más completo")
    opcion = input("Selecciona 1 o 2: ").strip()
    if opcion == "1":
        extra = input("Escribe lo que quieres añadir al plan: ").strip()
        if extra:
            informar(f"Añadido a tu plan: {extra}")
    elif opcion == "2":
        _imprimir_seguro(_panel("LucIA · Diagnóstico completo",
                     f"Archivo {Path(analisis.ruta).name}: {analisis.lineas} líneas, "
                     f"{analisis.funciones} funciones, {analisis.clases} clases, "
                     f"{analisis.importaciones} importaciones, {analisis.puntos_decision} "
                     f"puntos de decisión, {analisis.lineas_largas} líneas largas, "
                     f"{analisis.marcadores_pendientes} pendientes, sintaxis válida: "
                     f"{analisis.sintaxis_valida}. Recomiendo dividir por responsabilidad, "
                     f"documentar, tipar y cubrir con pruebas antes de tocar nada."))
    else:
        informar("Opción no válida; no se hizo nada más.")


def comando_ds_ialocal(consultor: Optional[ConsultorIA] = None) -> bool:
    """Comando 'ds ialocal': delega todo el pipeline en FlujoRefactorLucIA."""
    entrada = input("Archivo al cual hay que refactorizar: ").strip().strip("\"'")
    if not entrada:
        reportar_error("No se indicó ningún archivo.")
        return False
    ruta = Path(os.path.expandvars(os.path.expanduser(entrada))).resolve()
    if not ruta.is_file():
        reportar_error(f"Archivo no válido: {ruta}")
        return False
    try:
        contenido = ruta.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as error:
        reportar_error(f"No se pudo leer: {error}")
        return False
    return FlujoRefactorLucIA(ruta, contenido, consultor).ejecutar()


def _fallback_openrouter(ruta: Path, contenido: str, analisis: AnalisisArchivo,
                         modelo_local: str, motivo: str) -> bool:
    """La IA local falló: se borra y se usa una free de OpenRouter (1 análisis + 2 refactor)."""
    _imprimir_seguro(f"[OR] La IA local {modelo_local} falló ({motivo}). Se borra.")
    try:
        endpoint, _ = _cargar_configuracion_ia_local()
        _borrar_modelo_ollama(endpoint, modelo_local)
    except Exception:
        pass
    clave = _leer_openrouter_key()
    if not clave:
        reportar_error("[OR] Sin OPENROUTER_API_KEY en Vault STM_SGR ni .env; no hay fallback.")
        return False
    _borrar_peso_local()
    _imprimir_seguro("[OR 1/2] Análisis con IA gratuita de OpenRouter...")
    try:
        nuevo, modelo_or, nota = _refactorizar_con_openrouter(contenido, analisis, clave)
        nuevo = _validar_refactor(contenido, nuevo, ruta)
    except ErrorProyecto as error:
        reportar_error(f"[OR] Falló también OpenRouter: {error}")
        _registrar_refactor_md(ruta, modelo_or if 'modelo_or' in dir() else "openrouter",
                               f"FALLO OpenRouter: {error}")
        return False
    ruta.write_text(nuevo, encoding="utf-8")
    exito(f"[OR 2/2] Refactorizado con {modelo_or} ({len(nuevo.splitlines())} líneas).")
    _registrar_refactor_md(ruta, modelo_or, nota)
    exito("Flujo ds ialocal completado vía OpenRouter.")
    return True


# --- Flujo de refactorización con LucIA --------------------------------------
# Esta clase centraliza el pipeline "ds ialocal": plan, IA local por fragmentos
# con validación inmediata y auto-reparación, rotación con `ollama rm` ante fallo,
# fallback a OpenRouter free y anotación de errores en registro_refactor.md.

