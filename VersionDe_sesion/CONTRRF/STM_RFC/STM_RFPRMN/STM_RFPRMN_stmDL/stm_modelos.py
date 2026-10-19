"""Submodulo de RFPRMN (refactor: tope 400/450 lineas)."""
from __future__ import annotations
import ast, json, os, re, shutil, stat, subprocess, sys, textwrap, urllib.error, urllib.parse, urllib.request, uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional
try:
    from .stm_base import (E, informar, exito, advertir, reportar_error, ErrorProyecto, SRC_DIR, DESTINO, CONFIG_IA_LOCAL, _imprimir_seguro)
except ImportError:
    pass

# --- Refactorización con modelo local de código ("ds ialocal") ------------------
# Este bloque implementa el comando "ds ialocal": al dar Intro tras pedir el archivo
# descarga de inmediato un modelo de IA para código (no repetido, según el .md de
# registro), refactoriza, genera una respuesta interna a LucIA, LucIA lo apunta en el
# .md con sus propias palabras junto al nombre del modelo, y después se borra el
# modelo. Así cada archivo usa un modelo distinto sin repetir IAlocal.

#: Candidatos de código ligeros (HuggingFace/Ollama) aptos para 8 VRAM / 8 RAM.
#: Carpeta donde se descargan los pesos GGUF desde HuggingFace.
DIR_MODELOS_LOCAL = SRC_DIR / "STM_IA" / "modelosIAlocal" / "IAlocalDESCARGADA"
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

REGISTRO_REFACTOR_MD = SRC_DIR / "STM_IA" / "modelosIAlocal" / "registro_refactor.md"

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
        texto = "\n".join(texto.splitlines()[:LIMITE_LINEAS_REFACTOR])
    return texto, (usado or MODELOS_OR_CODIGO[0]), (diagnostico or
        f"Yo, LucIA, refactoricé {nombre} con IA gratuita de OpenRouter.")


def _descargar_peso_hf(destino: Path | None = None) -> Path:
    """Descarga el GGUF de código desde HuggingFace DIRECTO en modelosIAlocal/IAlocalDESCARGADA.

    Stream con progreso visible (MB / %): el archivo crece en la carpeta durante
    la descarga para que se vea el modelo y su proceso en el explorador/terminal.
    """
    from huggingface_hub import hf_hub_url
    dest = Path(destino) if destino else DIR_MODELOS_LOCAL
    dest.mkdir(parents=True, exist_ok=True)
    final = dest / HF_ARCHIVO_CODIGO
    parcial = dest / (HF_ARCHIVO_CODIGO + ".part")
    if final.exists() and final.stat().st_size > 0:
        informar(f"Peso ya presente (sin descarga): {final} ({final.stat().st_size} bytes)")
        return final
    # Si quedó un .part completo de una descarga anterior, adoptarlo.
    if parcial.exists() and parcial.stat().st_size > 1000 * 1024 * 1024:
        try:
            parcial.replace(final)
            exito(f"Modelo HF recuperado: {final} ({final.stat().st_size} bytes)")
            return final
        except OSError:
            informar(f"Peso visible en: {parcial} ({parcial.stat().st_size} bytes)")
            return parcial
    url = hf_hub_url(repo_id=HF_REPO_CODIGO, filename=HF_ARCHIVO_CODIGO)
    _imprimir_seguro(f"[DESCARGA] {HF_REPO_CODIGO}/{HF_ARCHIVO_CODIGO}")
    _imprimir_seguro(f"[DESCARGA] URL: {url}")
    _imprimir_seguro(f"[DESCARGA] Destino visible: {final}")
    req = urllib.request.Request(url, headers={"User-Agent": "WoldVirtualP2P3D"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", "0") or 0)
        _imprimir_seguro(f"[DESCARGA] Tamano total: {total / 1048576:.1f} MB")
        bajados = 0
        ultimo_pct = -1
        with open(final, "wb") as f:
            while True:
                bloque = resp.read(4 * 1024 * 1024)
                if not bloque:
                    break
                f.write(bloque)
                bajados += len(bloque)
                if total > 0:
                    pct = int(bajados * 100 / total)
                    if pct != ultimo_pct and (pct % 5 == 0 or pct == 100):
                        ultimo_pct = pct
                        _imprimir_seguro(
                            f"[DESCARGA] {bajados / 1048576:.1f}/{total / 1048576:.1f} MB ({pct}%)")
                elif bajados % (100 * 1048576) < 4 * 1024 * 1024:
                    _imprimir_seguro(f"[DESCARGA] {bajados / 1048576:.1f} MB...")
    # Limpia resto .part antiguo si ya no está bloqueado.
    try:
        if parcial.exists() and final.exists() and parcial.stat().st_size == final.stat().st_size:
            parcial.unlink()
    except OSError:
        pass
    exito(f"Modelo HF descargado: {final} ({final.stat().st_size} bytes)")
    return final


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
        with open(CONFIG_IA_LOCAL, "r", encoding="utf-8") as f:
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


def _modelos_usados_registro() -> set[str]:
    """Lee el .md de registro y devuelve los modelos ya usados (para no repetir)."""
    try:
        if REGISTRO_REFACTOR_MD.exists():
            return set(re.findall(r"[A-Za-z0-9._:-]+:[A-Za-z0-9._-]+",
                                  REGISTRO_REFACTOR_MD.read_text(encoding="utf-8")))
    except OSError:
        pass
    return set()


def _asegurar_modelo_codigo(excluir: set[str] | None = None) -> str:
    """Descarga de inmediato un modelo de código NO usado antes (sin repetir IAlocal)."""
    # 1) Peso HF en modelosIAlocal/IAlocalDESCARGADA (corrige "no se descarga el modelo").
    try:
        _descargar_peso_hf()
    except Exception as error:
        raise ErrorProyecto(f"No se pudo descargar el peso HF ({error}).")
    usados = {u.lower() for u in _modelos_usados_registro()}
    usados |= {e.lower() for e in (excluir or set())}
    candidatos = [c for c in _leer_candidatos_codigo() if c.lower() not in usados]
    if not candidatos:  # todos usados: se permite reutilizar desde el primero
        candidatos = [c for c in _leer_candidatos_codigo()
                      if c.lower() not in {e.lower() for e in (excluir or set())}]
    if not candidatos:
        raise ErrorProyecto("No quedan IAs locales por probar (todas fallaron o se usaron).")
    endpoint, _ = _cargar_configuracion_ia_local()
    instalados = _modelos_ollama_instalados()
    for candidato in candidatos:  # reutiliza sin descargar si ya está en Ollama
        base = candidato.lower().split(":")[0]
        if candidato.lower() in instalados or base in instalados:
            informar(f"Modelo reutilizado (ya en Ollama, sin descarga): {candidato}")
            return candidato
    # Solo se descarga UN modelo: el primer candidato no usado.
    elegido = candidatos[0]
    informar(f"Descargando modelo de IA para código (uno solo): {elegido}...")
    if _descargar_modelo_ollama(endpoint, elegido):
        exito(f"Modelo descargado: {elegido}")
        return elegido
    raise ErrorProyecto(f"No se pudo descargar {elegido}; revisa Ollama y conexión.")


def _borrar_modelo_ollama(endpoint: str, modelo: str) -> None:
    """Borra el modelo local tras registrar, para no acumular IAlocal repetidas."""
    try:
        carga = json.dumps({"model": modelo}).encode("utf-8")
        pet = urllib.request.Request(
            f"{endpoint}/api/delete", data=carga,
            headers={"Content-Type": "application/json"}, method="DELETE")
        with urllib.request.urlopen(pet, timeout=120):
            pass
    except Exception:
        try:
            subprocess.run(["ollama", "rm", modelo], timeout=300)
        except Exception as error:
            advertir(f"No se pudo borrar {modelo} ({error}).")
    informar(f"Modelo local borrado tras el registro: {modelo}")


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
