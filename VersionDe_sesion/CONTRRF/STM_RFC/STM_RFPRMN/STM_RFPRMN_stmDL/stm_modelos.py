"""Submodulo de RFPRMN (refactor: tope 400/450 lineas)."""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from .stm_base import (
    E, informar, exito, advertir, reportar_error, ErrorProyecto, SRC_DIR,
    DESTINO, _imprimir_seguro,
)
from .stm_analisis import AnalisisArchivo, _cargar_configuracion_ia_local
from .stm_descarga import descargar_gguf
from .stm_rutas import (
    DIR_MODELOS_LOCAL, REGISTRO_REFACTOR_MD, comprobar_ruta_segura,
    ruta_config_ia_local,
)

# --- Refactorización con modelo local de código ("ds ialocal") ------------------
# Este bloque implementa el comando "ds ialocal": al dar Intro tras pedir el archivo
# descarga de inmediato un modelo de IA para código (no repetido, según el .md de
# registro), refactoriza, genera una respuesta interna a LucIA, LucIA lo apunta en el
# .md con sus propias palabras junto al nombre del modelo, y después se borra el
# modelo. Así cada archivo usa un modelo distinto sin repetir IAlocal.

#: Candidatos de código ligeros (HuggingFace/Ollama) aptos para 8 VRAM / 8 RAM.
#: Repo/archivo GGUF pequeño de código (Qwen2.5-Coder 1.5B Q4, ~1 GB, apto 8 RAM).
HF_REPO_CODIGO = "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"
HF_ARCHIVO_CODIGO = "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"

#: Candidatos de código ligeros (HuggingFace/Ollama) aptos para 8 VRAM / 8 RAM.
MODELOS_CODIGO_LIGEROS = (
    "qwen2.5-coder:7b",
    "starcoder2:7b",
    "codellama:7b",
    "deepseek-coder:6.7b",
)

#: Límite de líneas por archivo refactorizado (regla 400/450).
LIMITE_LINEAS_REFACTOR = 450

#: Modelos de código gratuitos de OpenRouter (fallback cuando la IA local falla).
MODELOS_OR_CODIGO = (
    "cohere/north-mini-code:free",
    "poolside/laguna-xs-2.1:free",
    "poolside/laguna-s-2.1:free",
    "openrouter/free",
)
ENDPOINT_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"


def _leer_openrouter_key() -> str:
    """Lee OPENROUTER_API_KEY del Vault STM_SGR, del .env real o del entorno."""
    try:
        from STM_SGR.vault_openrouter import obtener_key  # pyrefly: ignore[missing-import]
        clave_vault = obtener_key()
        if clave_vault and len(clave_vault) > 10:
            return clave_vault
    except Exception:
        pass
    candidatos = [
        SRC_DIR / "STM_SGR" / ".env",  # ubicación real en este árbol
        DESTINO / "LC" / "LC" / ".env",
        DESTINO / "LC" / ".env",
        DESTINO / ".env",
    ]
    for ruta in candidatos:
        try:
            if ruta.exists():
                for linea in ruta.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                    if linea.strip().startswith("OPENROUTER_API_KEY="):
                        clave = linea.strip().split("=", 1)[1].strip().strip("'\"")
                        if len(clave) > 10:
                            return clave
        except OSError:
            pass
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def _chat_openrouter(modelo_id: str, clave: str, mensajes: list[dict],
                     max_tokens: int = 1500, timeout: int = 120) -> str:
    """Una llamada chat a OpenRouter; rota con error si 429/404/timeout."""
    carga = json.dumps({"model": modelo_id, "messages": mensajes,
                        "temperature": 0.2, "max_tokens": max_tokens}).encode("utf-8")
    pet = urllib.request.Request(
        ENDPOINT_OPENROUTER, data=carga,
        headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://woldvirtualp2p3d.network",
                 "X-Title": "WoldVirtualP2P3D-ds-ialocal"}, method="POST")
    try:
        with urllib.request.urlopen(pet, timeout=timeout) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
        msg = datos["choices"][0].get("message", {})
        texto = (msg.get("content") or "").strip()
        if not texto:  # algunos free devuelven reasoning en vez de content
            texto = str(msg.get("reasoning", "") or "").strip()
        if not texto:
            raise ErrorProyecto(f"OpenRouter {modelo_id} devolvió vacío (se rota).")
        return texto
    except urllib.error.HTTPError as error:
        raise ErrorProyecto(f"OpenRouter {modelo_id} HTTP {error.code}.")
    except Exception as error:
        raise ErrorProyecto(f"OpenRouter {modelo_id} falló ({error}).")


def _refactorizar_con_openrouter(contenido: str, analisis: AnalisisArchivo,
                                 clave: str) -> tuple[str, str, str]:
    """Fallback OpenRouter: 1) análisis de IA free + 2) refactor por fragmentos.

    Devuelve (código, modelo_id, diagnóstico). Rota entre modelos free de código.
    """
    lineas = contenido.splitlines()
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
    nombre = Path(analisis.ruta).name
    modelos = [m for m in MODELOS_OR_CODIGO]
    salidas: list[str] = []
    usado = ""
    for num, frag in enumerate(["\n".join(f) for f in fragmentos], start=1):
        ok = False
        for modelo_id in modelos:
            _imprimir_seguro(f"[OR {num}/{len(fragmentos)}] {modelo_id}...")
            try:
                texto = _chat_openrouter(modelo_id, clave, [
                    {"role": "system", "content": (
                        "Refactoriza el fragmento sin cambiar su comportamiento. "
                        "Responde SOLO con código, sin explicaciones ni cercas.")},
                    {"role": "user", "content": f"Archivo: {nombre} (parte {num})\n{frag}"}],
                    max_tokens=1500)
                salidas.append(re.sub(r"^```[a-zA-Z]*\n|```$", "", texto,
                                      flags=re.MULTILINE).strip())
                usado = usado or modelo_id
                ok = True
                break
            except ErrorProyecto as error:
                advertir(str(error))
                continue
        if not ok:
            raise ErrorProyecto("Todas las IAs free de OpenRouter fallaron en fragmento "
                                f"{num}.")
    diagnostico = ""
    for modelo_id in modelos:
        try:
            diagnostico = _chat_openrouter(modelo_id, clave, [
                {"role": "system", "content": (
                    "Eres LucIA, programadora. En primera persona, máximo 90 palabras, "
                    "sin código: qué se refactorizó y primer paso seguro.")},
                {"role": "user", "content": (
                    f"Archivo: {nombre}, {analisis.lineas} líneas, {analisis.funciones} "
                    f"funciones, {analisis.clases} clases.")}],
                max_tokens=300)
            usado = usado or modelo_id
            break
        except ErrorProyecto:
            continue
    texto = "\n".join(salidas).strip()
    if len(texto.splitlines()) > LIMITE_LINEAS_REFACTOR:
        raise ErrorProyecto(
            f"El refactor ocupa {len(texto.splitlines())} líneas "
            f"(tope {LIMITE_LINEAS_REFACTOR}): se rechaza para no truncar código.")
    return texto, (usado or MODELOS_OR_CODIGO[0]), (diagnostico or
        f"Yo, LucIA, refactoricé {nombre} con IA gratuita de OpenRouter.")


def _descargar_peso_hf(destino: Path | None = None) -> Path:
    """Descarga el GGUF de código verificado en modelosIAlocal/IAlocalDESCARGADA.

    Delegado en :func:`stm_descarga.descargar_gguf`: escritura en ``.part``,
    reanudación por ``Range``, reintentos y validación de la cabecera GGUF,
    de modo que un archivo truncado nunca se da por bueno.
    """
    return descargar_gguf(HF_REPO_CODIGO, HF_ARCHIVO_CODIGO,
                          Path(destino) if destino else DIR_MODELOS_LOCAL)


def _modelos_ollama_instalados() -> set[str]:
    """Devuelve los modelos ya descargados en Ollama (vacío si no responde)."""
    try:
        endpoint, _ = _cargar_configuracion_ia_local()
        with urllib.request.urlopen(f"{endpoint}/api/tags", timeout=10) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
        instalados = set()
        for m in datos.get("models", []):
            if not isinstance(m, dict):
                continue
            for clave in ("name", "model"):
                nombre = str(m.get(clave, "") or "").strip().lower()
                if nombre:
                    instalados.add(nombre)
                    # "qwen2.5-coder:7b" y "qwen2.5-coder:latest" deben matchear por base.
                    instalados.add(nombre.split(":")[0])
        return instalados
    except Exception as error:
        advertir(f"No se pudo listar modelos Ollama ({error}).")
        return set()


def _es_modelo_codigo(nombre: str) -> bool:
    """True solo si el nombre indica modelo de código (coder/code/code-lite)."""
    bajo = nombre.lower()
    return any(m in bajo for m in ("coder", "code", "starcoder", "codellama", "deepseek"))


def _leer_candidatos_codigo() -> list[str]:
    """Candidatos EXCLUSIVAMENTE de código: filtra IAlocal.json y añade respaldos."""
    candidatos: list[str] = []
    try:
        with open(ruta_config_ia_local(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for m in cfg.get("models_available", []):
            nombre = str(m).strip()
            if nombre and _es_modelo_codigo(nombre) and nombre not in candidatos:
                candidatos.append(nombre)
    except (OSError, ValueError) as error:
        advertir(f"No se pudo leer candidatos de IAlocal.json ({error}).")
    for respaldo in MODELOS_CODIGO_LIGEROS:
        if respaldo not in candidatos:
            candidatos.append(respaldo)
    # Solo modelos de código, pequeños primero (un 7b en CPU no llega a 60s).
    def _tamano(nombre: str) -> float:
        m = re.search(r"(\d+(?:\.\d+)?)\s*b", nombre.lower())
        return float(m.group(1)) if m else 9.0
    candidatos.sort(key=_tamano)
    # Quita aliases duplicados (qwen2.5-coder:latest == qwen2.5-coder:7b).
    unicos: list[str] = []
    bases: set[str] = set()
    for nombre in candidatos:
        base = nombre.lower().split(":")[0]
        if base not in bases:
            bases.add(base)
            unicos.append(nombre)
    return unicos


def _borrar_peso_local() -> None:
    """Borra TODO lo descargado en IAlocalDESCARGADA (pesos, .part y carpeta).

    Se invoca en el ``finally`` de ``FlujoRefactorLucIA.ejecutar`` para que
    nunca queden restos de ~1 GB, ni en éxito ni en error ni al cancelar.
    """
    try:
        comprobar_ruta_segura(DIR_MODELOS_LOCAL, "pesos locales")
    except ErrorProyecto as error:
        advertir(f"No se limpian los pesos: {error}")
        return
    try:
        if not DIR_MODELOS_LOCAL.exists():
            return
        for hijo in DIR_MODELOS_LOCAL.iterdir():
            if hijo.is_file():
                try:
                    hijo.unlink()
                    exito(f"Peso local borrado: {hijo}")
                except PermissionError:
                    advertir(f"Windows bloquea {hijo.name}; se reintentará al cerrar.")
                    return
            elif hijo.is_dir():
                shutil.rmtree(hijo, ignore_errors=True)
        shutil.rmtree(DIR_MODELOS_LOCAL, ignore_errors=True)
    except OSError as error:
        advertir(f"No se pudo limpiar IAlocalDESCARGADA ({error}).")


def _descargar_modelo_ollama(endpoint: str, modelo: str) -> bool:
    """Descarga ``modelo`` vía /api/pull leyendo el stream NDJSON; True si OK."""
    carga = json.dumps({"model": modelo, "stream": True}).encode("utf-8")
    pet = urllib.request.Request(
        f"{endpoint}/api/pull", data=carga,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(pet, timeout=1800) as resp:
            # La API devuelve NDJSON por líneas: hay que consumirlo hasta "completed".
            while True:
                linea = resp.readline()
                if not linea:
                    break
                try:
                    evento = json.loads(linea.decode("utf-8"))
                except ValueError:
                    continue
                estado = str(evento.get("status", ""))
                if estado:
                    print(f"\r{E.tenue}{modelo}: {estado[:70]}{E.reset}      ", end="", flush=True)
                if evento.get("status") == "success" or "success" in estado.lower():
                    print()
                    return True
                if "error" in evento:
                    print()
                    reportar_error(f"Error al descargar {modelo}: {evento['error']}")
                    return False
        print()
        # Si el stream terminó sin error, verificar con /api/tags.
        return modelo.lower() in _modelos_ollama_instalados()
    except Exception as error:
        print()
        advertir(f"Fallo /api/pull para {modelo} ({error}); se prueba 'ollama pull'.")
    # Respaldo: CLI de Ollama (muestra progreso nativo).
    try:
        proc = subprocess.run(["ollama", "pull", modelo], timeout=1800)
        return proc.returncode == 0 and modelo.lower() in _modelos_ollama_instalados()
    except Exception as error:
        reportar_error(f"No se pudo descargar {modelo}: {error}")
        return False


def _ruta_registro_refactor() -> Path:
    """Registro de refactor vigente; si no existe, el heredado de ``RFC/src``.

    El registro se movió a ``STM_RFPRMN/registro_refactor.md`` (R2): dentro de
    ``RFC/src`` desaparecía al vaciar RFC y viajaba a PRY en cada actualización.
    Se mantiene la lectura del heredado para no perder el historial.
    """
    if REGISTRO_REFACTOR_MD.exists():
        return REGISTRO_REFACTOR_MD
    heredado = SRC_DIR / "STM_IA" / "modelosIAlocal" / "registro_refactor.md"
    return heredado if heredado.exists() else REGISTRO_REFACTOR_MD


def _modelos_usados_registro() -> set[str]:
    """Modelos ya usados, leídos de las cabeceras ``## archivo — modelo`` del .md.

    Antes se aplicaba una regex sobre todo el texto y capturaba marcas de
    tiempo (``12:50``); ahora solo cuenta la cabecera que escribe
    ``_registrar_refactor_md`` (issue #80, punto 6).
    """
    usados: set[str] = set()
    ruta_md = _ruta_registro_refactor()
    try:
        if not ruta_md.exists():
            return usados
        for linea in ruta_md.read_text(encoding="utf-8").splitlines():
            if not linea.startswith("## "):
                continue
            partes = linea[3:].split("—")
            if len(partes) < 2:
                continue
            modelo = partes[-1].strip().lower()
            if modelo:
                usados.add(modelo)
    except OSError:
        pass
    return usados


def _asegurar_modelo_codigo(excluir: set[str] | None = None) -> str:
    """Elige un modelo de código NO usado, prefiriendo lo que ya está instalado.

    Solo descarga si no hay ningún candidato disponible en Ollama: antes se
    bajaban ~1 GB de HuggingFace en cada ejecución aunque el modelo estuviera
    ya instalado (issue #80, gestión del ciclo de vida de los modelos).
    """
    usados = {u.lower() for u in _modelos_usados_registro()}
    usados |= {e.lower() for e in (excluir or set())}
    candidatos = [c for c in _leer_candidatos_codigo() if c.lower() not in usados]
    if not candidatos:  # todos usados: se permite reutilizar desde el primero
        candidatos = [c for c in _leer_candidatos_codigo()
                      if c.lower() not in {e.lower() for e in (excluir or set())}]
    if not candidatos:
        raise ErrorProyecto("No quedan IAs locales por probar (todas fallaron o se usaron).")
    try:
        endpoint, _ = _cargar_configuracion_ia_local()
    except (OSError, ValueError) as error:
        raise ErrorProyecto(f"Configuración de IA local no disponible ({error}).")
    instalados = _modelos_ollama_instalados()
    for candidato in candidatos:  # reutiliza sin descargar si ya está en Ollama
        base = candidato.lower().split(":")[0]
        if candidato.lower() in instalados or base in instalados:
            informar(f"Modelo reutilizado (ya en Ollama, sin descarga): {candidato}")
            return candidato
    # No hay nada instalado: se descarga UN modelo, el primer candidato no usado.
    elegido = candidatos[0]
    informar(f"Descargando modelo de IA para código (uno solo): {elegido}...")
    if _descargar_modelo_ollama(endpoint, elegido):
        exito(f"Modelo descargado: {elegido}")
        return elegido
    # Último recurso: peso GGUF suelto de HuggingFace (verificado y reanudable).
    try:
        _descargar_peso_hf()
    except Exception as error:
        advertir(f"El respaldo GGUF tampoco está disponible ({error}).")
        raise ErrorProyecto(
            f"No se pudo descargar {elegido}; revisa Ollama y la conexión.")
    raise ErrorProyecto(
        f"{elegido} no quedó disponible: el GGUF se descargó pero Ollama no lo "
        "registró. Revisa `ollama list` y vuelve a intentarlo.")


def _borrar_modelo_ollama(endpoint: str, modelo: str) -> bool:
    """Borra el modelo local tras registrar; True si Ollama lo dio por borrado.

    Nunca miente: antes informaba siempre de éxito aunque `ollama rm` fallara
    (issue #80, punto 6).
    """
    borrado = False
    try:
        carga = json.dumps({"model": modelo}).encode("utf-8")
        pet = urllib.request.Request(
            f"{endpoint}/api/delete", data=carga,
            headers={"Content-Type": "application/json"}, method="DELETE")
        with urllib.request.urlopen(pet, timeout=120):
            borrado = True
    except Exception:
        try:
            proc = subprocess.run(["ollama", "rm", modelo], timeout=300,
                                  capture_output=True, text=True)
            borrado = proc.returncode == 0
        except Exception as error:
            advertir(f"No se pudo borrar {modelo} ({error}).")
    if borrado:
        informar(f"Modelo local borrado tras el registro: {modelo}")
    return borrado


def _liberar_ollama(excepto: str = "") -> None:
    """Descarga de CPU/RAM los modelos Ollama cargados salvo ``excepto``.

    Ollama en este equipo corre 100% CPU (GPU Intel Arc no soportada): dos
    modelos a la vez se reparten el Ryzen y ninguno genera a tiempo.
    """
    try:
        proc = subprocess.run(["ollama", "ps"], timeout=30, capture_output=True, text=True)
        for linea in proc.stdout.splitlines()[1:]:
            nombre = linea.split()[0] if linea.split() else ""
            if nombre and nombre.lower() != excepto.lower():
                _imprimir_seguro(f"[VIGILANTE] Liberando CPU: ollama stop {nombre}")
                try:
                    subprocess.run(["ollama", "stop", nombre], timeout=120,
                                   capture_output=True)
                except Exception:
                    pass
    except Exception as error:
        advertir(f"No se pudo liberar Ollama ({error}).")


#: Líneas por fragmento en refactorización por chunks (calibrado en CPU:
#: 60 líneas -> primer token ~11s, completo ~2 min con qwen2.5-coder:3b).
LINEAS_POR_FRAGMENTO = 60
