"""Selección y ciclo de vida de los modelos de IA para código.

Política (R6 de la discusión #84): **siempre el modelo de código más ligero**.

- Los candidatos se ordenan de menor a mayor número de parámetros.
- Si hay varios instalados, se reutiliza el **más ligero** (sin descargar nada).
- Si no hay ninguno, se descarga el más ligero que quepa en la RAM del equipo.
- Si `ollama pull` falla, se descarga el GGUF verificado y se **registra** en
  Ollama con `ollama create` (antes se descargaba ~1 GB que nunca se usaba).
- Los modelos del usuario **no se borran** salvo petición explícita (R3).
"""
from __future__ import annotations

import ctypes
import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

from .stm_analisis import _cargar_configuracion_ia_local
from .stm_base import (
    ErrorProyecto, SRC_DIR, _imprimir_seguro, advertir, exito, informar,
    reportar_error,
)
from .stm_descarga import descargar_gguf
from .stm_fragmentos import LIMITE_LINEAS_REFACTOR, LINEAS_POR_FRAGMENTO  # noqa: F401
from .stm_openrouter import (  # noqa: F401  (re-exportados)
    ENDPOINT_OPENROUTER, MODELOS_OR_CODIGO, _chat_openrouter,
    _leer_openrouter_key, _refactorizar_con_openrouter,
)
from .stm_rutas import (
    DIR_MODELOS_LOCAL, REGISTRO_REFACTOR_MD, comprobar_ruta_segura,
    ruta_config_ia_local,
)

#: Repo/archivo GGUF pequeño de código (Qwen2.5-Coder 1.5B Q4, ~1 GB, apto 8 RAM).
HF_REPO_CODIGO = "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"
HF_ARCHIVO_CODIGO = "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
#: Nombre con el que se registra ese GGUF en Ollama.
NOMBRE_MODELO_GGUF = "wvp-coder-1.5b"

#: Candidatos de código ordenados de **más ligero a más pesado**.
MODELOS_CODIGO_LIGEROS = (
    "qwen2.5-coder:1.5b",
    "qwen2.5-coder:3b",
    "qwen2.5-coder:7b",
    "starcoder2:3b",
    "starcoder2:7b",
    "codellama:7b",
    "deepseek-coder:6.7b",
)
#: Por encima de este tamaño (miles de millones) no se descarga con poca RAM.
TAMANO_MAXIMO_SIN_RAM = 4.0
#: RAM mínima (GB) para atreverse con un modelo de 7B.
RAM_MINIMA_PARA_7B = 6.0


# --- Tamaño y orden ----------------------------------------------------------

def _ram_gb() -> float:
    """RAM física del equipo en GB (8.0 si no se puede consultar)."""
    try:
        class _Mem(ctypes.Structure):
            _fields_ = [("wLength", ctypes.c_ulong), ("wMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong)] + [("x", ctypes.c_ulonglong)] * 5

        memoria = _Mem()
        memoria.wLength = ctypes.sizeof(_Mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memoria))
        return round(memoria.ullTotalPhys / (1024 ** 3), 1)
    except Exception:  # noqa: BLE001 - en Linux/macOS no existe windll
        return 8.0


def tamano_modelo(nombre: str) -> float:
    """Parámetros del modelo en miles de millones (9.0 si no se sabe)."""
    coincidencia = re.search(r"(\d+(?:\.\d+)?)\s*b\b", nombre.lower())
    if coincidencia:
        return float(coincidencia.group(1))
    return 9.0 if "latest" in nombre.lower() else 9.5


def ordenar_por_tamano(nombres: list[str]) -> list[str]:
    """Ordena de más ligero a más pesado (desempata por nombre)."""
    return sorted(nombres, key=lambda nombre: (tamano_modelo(nombre), nombre.lower()))


def _es_modelo_codigo(nombre: str) -> bool:
    """True solo si el nombre indica modelo de código (coder/code/starcoder...)."""
    bajo = nombre.lower()
    return any(m in bajo for m in ("coder", "code", "starcoder", "codellama", "deepseek"))


# --- Candidatos --------------------------------------------------------------

def _leer_candidatos_codigo() -> list[str]:
    """Candidatos EXCLUSIVAMENTE de código, ordenados de más ligero a más pesado.

    Primero los configurados en ``IAlocal.json``; después los respaldos. Se
    queda con la etiqueta más ligera de cada familia (``qwen2.5-coder:3b``
    antes que ``:latest``).
    """
    candidatos: list[str] = []
    try:
        with open(ruta_config_ia_local(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for modelo in cfg.get("models_available", []):
            nombre = str(modelo).strip()
            if nombre and _es_modelo_codigo(nombre) and nombre not in candidatos:
                candidatos.append(nombre)
    except (OSError, ValueError) as error:
        advertir(f"No se pudo leer candidatos de IAlocal.json ({error}).")
    # Respaldos de OTRAS familias: no se pisa la etiqueta que eligió el usuario.
    familias = {candidato.lower().split(":")[0] for candidato in candidatos}
    for respaldo in MODELOS_CODIGO_LIGEROS:
        base = respaldo.lower().split(":")[0]
        if base not in familias:
            candidatos.append(respaldo)
            familias.add(base)
    ordenados = ordenar_por_tamano(candidatos)
    unicos: list[str] = []
    bases: set[str] = set()
    for nombre in ordenados:
        base = nombre.lower().split(":")[0]
        if base not in bases:
            bases.add(base)
            unicos.append(nombre)
    return unicos


def _candidatos_disponibles() -> list[str]:
    """Configuración + modelos de código ya instalados, el más ligero primero."""
    candidatos = _leer_candidatos_codigo()
    bases = {candidato.lower().split(":")[0] for candidato in candidatos}
    for instalado in _modelos_ollama_instalados():
        if not _es_modelo_codigo(instalado):
            continue
        if instalado.lower().split(":")[0] in bases:
            continue
        candidatos.append(instalado)
        bases.add(instalado.lower().split(":")[0])
    return ordenar_por_tamano(candidatos)


def _elegir_para_descargar(candidatos: list[str]) -> str:
    """El más ligero que quepa en la RAM disponible."""
    tope = TAMANO_MAXIMO_SIN_RAM if _ram_gb() < RAM_MINIMA_PARA_7B else 99.0
    for candidato in candidatos:
        if tamano_modelo(candidato) <= tope:
            return candidato
    advertir("Ningún modelo cabe con holgura en la RAM del equipo; "
             f"se usa el más ligero disponible: {candidatos[0]}")
    return candidatos[0]


# --- Cliente de Ollama -------------------------------------------------------

def _modelos_ollama_instalados() -> set[str]:
    """Devuelve los modelos ya descargados en Ollama (vacío si no responde)."""
    try:
        endpoint, _ = _cargar_configuracion_ia_local()
        with urllib.request.urlopen(f"{endpoint}/api/tags", timeout=10) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
        instalados = set()
        for modelo in datos.get("models", []):
            if not isinstance(modelo, dict):
                continue
            for clave in ("name", "model"):
                nombre = str(modelo.get(clave, "") or "").strip().lower()
                if nombre:
                    instalados.add(nombre)
                    # "qwen2.5-coder:7b" y "qwen2.5-coder:latest" matchean por base.
                    instalados.add(nombre.split(":")[0])
        return instalados
    except Exception as error:  # noqa: BLE001 - Ollama puede estar apagado
        advertir(f"No se pudo listar modelos Ollama ({error}).")
        return set()


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
                    print(f"\r{modelo}: {estado[:70]}      ", end="", flush=True)
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
    except Exception as error:  # noqa: BLE001 - se intenta el CLI como respaldo
        print()
        advertir(f"Fallo /api/pull para {modelo} ({error}); se prueba 'ollama pull'.")
    try:
        proc = subprocess.run(["ollama", "pull", modelo], timeout=1800)
        return proc.returncode == 0 and modelo.lower() in _modelos_ollama_instalados()
    except Exception as error:  # noqa: BLE001 - sin Ollama no hay nada que hacer
        reportar_error(f"No se pudo descargar {modelo}: {error}")
        return False


def _borrar_modelo_ollama(endpoint: str, modelo: str) -> bool:
    """Borra el modelo local; True si Ollama lo dio por borrado.

    Solo se llama cuando el usuario pidió consumir modelos (R3).
    """
    borrado = False
    try:
        carga = json.dumps({"model": modelo}).encode("utf-8")
        pet = urllib.request.Request(
            f"{endpoint}/api/delete", data=carga,
            headers={"Content-Type": "application/json"}, method="DELETE")
        with urllib.request.urlopen(pet, timeout=120):
            borrado = True
    except Exception:  # noqa: BLE001 - se intenta el CLI
        try:
            proc = subprocess.run(["ollama", "rm", modelo], timeout=300,
                                  capture_output=True, text=True)
            borrado = proc.returncode == 0
        except Exception as error:  # noqa: BLE001
            advertir(f"No se pudo borrar {modelo} ({error}).")
    if borrado:
        informar(f"Modelo local borrado: {modelo}")
    return borrado


def _liberar_ollama(excepto: str = "") -> None:
    """Descarga de CPU/RAM los modelos Ollama cargados salvo ``excepto``.

    Ollama en este equipo corre 100 % CPU (GPU Intel Arc no soportada): dos
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
                except Exception:  # noqa: BLE001
                    pass
    except Exception as error:  # noqa: BLE001 - sin CLI no hay nada que liberar
        advertir(f"No se pudo liberar Ollama ({error}).")


# --- GGUF: descarga y registro en Ollama (R6) --------------------------------

def _descargar_peso_hf(destino: Path | None = None) -> Path:
    """Descarga el GGUF verificado en ``IAlocalDESCARGADA`` (ver stm_descarga)."""
    return descargar_gguf(HF_REPO_CODIGO, HF_ARCHIVO_CODIGO,
                          Path(destino) if destino else DIR_MODELOS_LOCAL)


def _registrar_gguf_en_ollama(endpoint: str, ruta_gguf: Path,
                              nombre: str = NOMBRE_MODELO_GGUF) -> bool:
    """Registra el GGUF descargado como modelo de Ollama con ``ollama create``.

    Sin este paso el respaldo GGUF no servía de nada: se descargaba 1 GB y se
    borraba sin haberse usado nunca (R6).
    """
    modelfile = Path(ruta_gguf).with_name(f"Modelfile.{nombre}")
    try:
        modelfile.write_text(f'FROM "{Path(ruta_gguf).resolve()}"\n', encoding="utf-8")
    except OSError as error:
        advertir(f"No se pudo escribir el Modelfile ({error}).")
        return False
    _imprimir_seguro(f"[IA] Registrando el GGUF en Ollama como '{nombre}'...")
    try:
        proceso = subprocess.run(
            ["ollama", "create", nombre, "-f", str(modelfile)],
            timeout=600, capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as error:
        advertir(f"No se pudo ejecutar 'ollama create' ({error}).")
        return False
    finally:
        try:
            modelfile.unlink(missing_ok=True)
        except OSError:
            pass
    if proceso.returncode != 0:
        detalle = (proceso.stderr or proceso.stdout or "").strip()[:160]
        advertir(f"'ollama create' falló ({detalle or 'sin detalle'}).")
        return False
    base = nombre.lower().split(":")[0]
    if any(m.lower().split(":")[0] == base for m in _modelos_ollama_instalados()):
        exito(f"Modelo local '{nombre}' registrado en Ollama.")
        return True
    advertir(f"'ollama create' terminó pero '{nombre}' no aparece en Ollama.")
    return False


def _borrar_peso_local() -> None:
    """Borra TODO lo descargado en IAlocalDESCARGADA (pesos, .part y carpeta).

    Se invoca en el ``finally`` de ``FlujoRefactorLucIA.ejecutar`` para que
    nunca queden restos de ~1 GB. Nunca actúa fuera de su carpeta.
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


# --- Registro de modelos usados ---------------------------------------------

def _ruta_registro_refactor() -> Path:
    """Registro de refactor vigente; si no existe, el heredado de ``RFC/src``."""
    if REGISTRO_REFACTOR_MD.exists():
        return REGISTRO_REFACTOR_MD
    heredado = SRC_DIR / "STM_IA" / "modelosIAlocal" / "registro_refactor.md"
    return heredado if heredado.exists() else REGISTRO_REFACTOR_MD


def _modelos_usados_registro() -> set[str]:
    """Modelos ya usados, leídos de las cabeceras ``## archivo — modelo`` del .md."""
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
    """Elige el modelo de código **más ligero** disponible, sin descargar de más.

    Orden de decisión:
    1. reutiliza el más ligero de los ya instalados (no descarga nada),
    2. si no hay ninguno, descarga el más ligero que quepa en RAM,
    3. si `pull` falla, descarga el GGUF verificado y lo registra con
       ``ollama create``.
    """
    usados = {u.lower() for u in _modelos_usados_registro()}
    usados |= {e.lower() for e in (excluir or set())}
    candidatos = _candidatos_disponibles()
    libres = [c for c in candidatos if c.lower() not in usados]
    if not libres:  # todos usados: se permite reutilizar desde el más ligero
        libres = [c for c in candidatos
                  if c.lower() not in {e.lower() for e in (excluir or set())}]
    if not libres:
        raise ErrorProyecto("No quedan IAs locales por probar (todas fallaron o se usaron).")
    libres = ordenar_por_tamano(libres)  # el más ligero siempre primero
    try:
        endpoint, _ = _cargar_configuracion_ia_local()
    except (OSError, ValueError) as error:
        raise ErrorProyecto(f"Configuración de IA local no disponible ({error}).")
    instalados = _modelos_ollama_instalados()
    for candidato in libres:  # ordenados: el primero es el más ligero instalado
        exacto = candidato.lower()
        base = exacto.split(":")[0]
        if exacto in instalados:
            informar(f"Modelo reutilizado (ya en Ollama, sin descarga): {candidato}")
            return candidato
        if base in instalados:
            # Hay otra etiqueta de la misma familia instalada: se usa esa (no se
            # devuelve la del catálogo, que puede no estar descargada -> 404).
            for instalado in sorted(instalados):
                if ":" in instalado and instalado.split(":")[0] == base:
                    informar(f"Modelo reutilizado (misma familia): {instalado}")
                    return instalado
    elegido = _elegir_para_descargar(libres)
    informar(f"Descargando el modelo de código más ligero: {elegido}...")
    if _descargar_modelo_ollama(endpoint, elegido):
        exito(f"Modelo descargado: {elegido}")
        return elegido
    # Respaldo GGUF: descargar verificado y registrarlo en Ollama.
    try:
        ruta_gguf = _descargar_peso_hf()
    except Exception as error:  # noqa: BLE001 - se informa con contexto
        advertir(f"El respaldo GGUF tampoco está disponible ({error}).")
        raise ErrorProyecto(
            f"No se pudo descargar {elegido}; revisa Ollama y la conexión.")
    if _registrar_gguf_en_ollama(endpoint, ruta_gguf):
        return NOMBRE_MODELO_GGUF
    raise ErrorProyecto(
        f"{elegido} no quedó disponible y el GGUF no se pudo registrar en Ollama. "
        "Revisa `ollama list` y vuelve a intentarlo.")
