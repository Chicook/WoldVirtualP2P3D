"""Submodulo de RFPRMN (refactor: tope 400/450 lineas)."""
from __future__ import annotations
import ast
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Optional
# Imports explícitos: un nombre que falte debe romper el arranque con un
# mensaje claro, no dejar el módulo a medias (issue #80, punto 5).
from .stm_base import (  # noqa: F401
    E, informar, exito, advertir, reportar_error, pedir_confirmacion,
    ErrorProyecto, CONFIG_IA_LOCAL, SRC_DIR, _panel, _imprimir_seguro,
)
from .stm_analisis import (  # noqa: F401
    AnalisisArchivo, analizar_archivo_local, crear_plan_refactorizacion,
    consultar_ia_local, ConsultorIA, _cargar_configuracion_ia_local,
)
from .stm_modelos import (  # noqa: F401
    DIR_MODELOS_LOCAL, HF_REPO_CODIGO, HF_ARCHIVO_CODIGO, MODELOS_CODIGO_LIGEROS,
    LIMITE_LINEAS_REFACTOR, LINEAS_POR_FRAGMENTO, REGISTRO_REFACTOR_MD,
    MODELOS_OR_CODIGO, ENDPOINT_OPENROUTER, _leer_openrouter_key,
    _chat_openrouter, _refactorizar_con_openrouter, _descargar_peso_hf,
    _modelos_ollama_instalados, _es_modelo_codigo, _leer_candidatos_codigo,
    _borrar_peso_local, _descargar_modelo_ollama, _modelos_usados_registro,
    _asegurar_modelo_codigo, _borrar_modelo_ollama, _liberar_ollama,
)
from .stm_openrouter import describir_estado, habilitado as openrouter_habilitado


#: Prompt por defecto al refactorizar un fragmento.
SISTEMA_REFACTOR = (
    "Eres LucIA. Refactoriza el fragmento de verdad, no te limites a comentarlo: "
    "extrae constantes y funciones auxiliares, simplifica condiciones, elimina "
    "duplicación, valida entradas y aclara el cuerpo. Conserva el comportamiento "
    "y los nombres públicos (funciones, clases y métodos); los nombres locales sí "
    "puedes mejorarlos. Documentar no es refactorizar: si solo añades comentarios "
    "o docstrings, no has hecho el trabajo. Responde SOLO con código, sin cercas.")


def presupuesto_salida(fragmento: str) -> int:
    """Tokens de salida según el tamaño del fragmento (evita los truncados).

    Con un tope fijo de 800, un fragmento de 60+ líneas se cortaba a media
    cadena; el reintento volvía a truncarse igual y el fragmento se perdía.
    """
    lineas = (fragmento or "").count("\n") + 1
    return min(2200, max(600, lineas * 32))


def _generar_fragmento(endpoint: str, modelo: str, nombre_archivo: str,
                       fragmento: str, num: int, total: int,
                       timeout_primer_token: int, contexto: str = "",
                       sistema: str = "") -> str:
    """Genera un fragmento con el modelo local en stream.

    ``contexto`` lleva el expediente de LucIA (descripción funcional y deuda
    técnica del archivo) y ``sistema`` permite cambiar el rol del modelo (por
    ejemplo, crear código nuevo en vez de refactorizar).
    """
    import threading as _th, time as _tm
    presupuesto = presupuesto_salida(fragmento)
    carga = {"model": modelo, "messages": [
        {"role": "system", "content": sistema or SISTEMA_REFACTOR},
        {"role": "user", "content": (f"Archivo: {nombre_archivo} (parte {num}/{total})\n"
                                     f"{contexto}{fragmento}")}],
        "stream": True, "keep_alive": "10m",
        "options": {"temperature": 0.2, "num_predict": presupuesto,
                    "num_ctx": 4096}}
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
        raise ErrorProyecto(
            f"El refactor ocupa {len(lineas_out)} líneas "
            f"(tope {LIMITE_LINEAS_REFACTOR}): se rechaza para no truncar código "
            "y se conserva el original.")
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
    """Añade al .md de registro qué hizo el modelo y su nombre (evita re-descargas).

    Es best-effort: si el registro no se puede escribir (árbol de solo lectura,
    permisos), se avisa y el flujo continúa; antes reventaba con ``OSError``.
    """
    entrada = (f"\n## {ruta.name} — {modelo}\n"
               f"Fecha: {__import__('datetime').datetime.now().isoformat(timespec='seconds')}\n"
               f"Archivo: {ruta}\nDescripción del modelo: {descripcion.strip()}\n")
    try:
        REGISTRO_REFACTOR_MD.parent.mkdir(parents=True, exist_ok=True)
        with open(REGISTRO_REFACTOR_MD, "a", encoding="utf-8") as f:
            f.write(entrada)
    except OSError as error:
        advertir(f"No se pudo escribir el registro de refactor ({error}).")
        return
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


def comando_ds_ialocal(consultor: Optional[ConsultorIA] = None,
                      consumir_modelos: Optional[bool] = None) -> bool:
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
    if not contenido.strip():
        reportar_error(f"El archivo está vacío ({ruta}): no hay nada que refactorizar.")
        return False
    try:
        from .stm_flujo import FlujoRefactorLucIA  # diferido: evita el ciclo de import
    except ImportError as error:
        reportar_error(f"No se pudo cargar el flujo de refactor: {error}")
        return False
    try:
        exito_flujo = FlujoRefactorLucIA(ruta, contenido, consultor,
                                         consumir_modelos=consumir_modelos).ejecutar()
    except ErrorProyecto as error:
        reportar_error(str(error))
        return False
    if exito_flujo:
        # Cierra el ciclo: se prueba lo recién escrito y se diagnostica su deuda.
        from .test import comando_test_ruta

        comando_test_ruta(ruta)
        # Si el resultado supera el tope, se reparte en módulos y subsistemas.
        from .stm_particion import partir_si_excede

        partir_si_excede(ruta)
    return exito_flujo


def _generar_con_memoria(ruta: Path, contenido: str, modelo_local: str) -> bool:
    """Último recurso: recuperar de la memoria del seq2seq un refactor previo.

    Solo devuelve código que ya se aceptó para un código equivalente; si no hay
    nada suficientemente parecido, se niega (no inventa).
    """
    from . import stm_seq2seq

    nuevo = stm_seq2seq.generar(contenido)
    if not nuevo:
        informar("Seq2Seq: no hay ningún refactor memorizado para este código.")
        return False
    try:
        nuevo = _validar_refactor(contenido, nuevo, ruta)
    except ErrorProyecto as error:
        reportar_error(f"Seq2Seq devolvió un refactor inválido: {error}")
        return False
    ruta.write_text(nuevo, encoding="utf-8")
    exito(f"[SEQ2SEQ] Refactor recuperado de la memoria "
          f"({len(nuevo.splitlines())} líneas).")
    _registrar_refactor_md(ruta, f"seq2seq:{modelo_local}",
                           "Refactor recuperado de la memoria del subsistema.")
    return True


def _fallback_openrouter(ruta: Path, contenido: str, analisis: AnalisisArchivo,
                         modelo_local: str, motivo: str,
                         borrar_modelo: bool = False) -> bool:
    """La IA local falló: se usa una free de OpenRouter (1 análisis + 2 refactor).

    ``borrar_modelo`` respeta la política R3: por defecto el modelo del usuario
    se conserva y solo se excluye de la sesión.

    El respaldo está **desactivado por defecto**: si no se ha configurado, se
    informa y se devuelve ``False`` sin hacer ninguna llamada de red.
    """
    if not openrouter_habilitado():
        informar(f"[OR] {describir_estado()}")
        return _generar_con_memoria(ruta, contenido, modelo_local)
    if borrar_modelo:
        _imprimir_seguro(f"[OR] La IA local {modelo_local} falló ({motivo}). Se borra.")
        try:
            endpoint, _ = _cargar_configuracion_ia_local()
            _borrar_modelo_ollama(endpoint, modelo_local)
        except Exception:
            pass
    else:
        _imprimir_seguro(f"[OR] La IA local {modelo_local} falló ({motivo}); "
                         "se conserva y se continúa con OpenRouter.")
    clave = _leer_openrouter_key()
    if not clave:
        reportar_error("[OR] Sin OPENROUTER_API_KEY en Vault STM_SGR ni .env; no hay fallback.")
        return False
    _borrar_peso_local()
    _imprimir_seguro("[OR 1/2] Análisis con IA gratuita de OpenRouter...")
    modelo_or = "openrouter"
    try:
        nuevo, modelo_or, nota = _refactorizar_con_openrouter(contenido, analisis, clave)
        nuevo = _validar_refactor(contenido, nuevo, ruta)
    except ErrorProyecto as error:
        reportar_error(f"[OR] Falló también OpenRouter: {error}")
        _registrar_refactor_md(ruta, modelo_or, f"FALLO OpenRouter: {error}")
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

