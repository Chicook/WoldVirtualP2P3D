"""Respaldo de refactorización con modelos gratuitos de OpenRouter.

**Desactivado por defecto.** Queda como opción pendiente de configuración: la
IA local es el camino normal y OpenRouter solo se usa si se activa de forma
explícita (variable ``RFPRMN_OPENROUTER=1`` o ``"openrouter": true`` en
``STM_RFPRMN/.config/opciones.json``).

La clave se lee del Vault de STM_SGR, del ``.env`` real o del entorno; nunca se
escribe en disco ni se imprime.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .stm_base import DESTINO, SRC_DIR, ErrorProyecto, advertir, informar, _imprimir_seguro
from .stm_fragmentos import LIMITE_LINEAS_REFACTOR, LINEAS_POR_FRAGMENTO
from .stm_rutas import DIR_CONFIG

#: Archivo de opciones de la herramienta (por ahora solo el interruptor OR).
ARCHIVO_OPCIONES = DIR_CONFIG / "opciones.json"

#: Valores que activan el respaldo.
_AFIRMATIVOS = frozenset({"1", "si", "sí", "s", "y", "yes", "true", "on"})
_NEGATIVOS = frozenset({"0", "no", "n", "false", "off"})

#: Modelos de código gratuitos de OpenRouter (fallback cuando la IA local falla).
MODELOS_OR_CODIGO = (
    "cohere/north-mini-code:free",
    "poolside/laguna-xs-2.1:free",
    "poolside/laguna-s-2.1:free",
    "openrouter/free",
)
ENDPOINT_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"


def _leer_opciones() -> dict:
    """Contenido de ``.config/opciones.json`` (``{}`` si no existe o está roto)."""
    try:
        datos = json.loads(ARCHIVO_OPCIONES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def habilitado() -> bool:
    """True si el respaldo OpenRouter está activado. Por defecto, **no**."""
    entorno = os.environ.get("RFPRMN_OPENROUTER", "").strip().lower()
    if entorno in _AFIRMATIVOS:
        return True
    if entorno in _NEGATIVOS:
        return False
    valor = _leer_opciones().get("openrouter")
    if isinstance(valor, str):
        return valor.strip().lower() in _AFIRMATIVOS
    return bool(valor)


def describir_estado() -> str:
    """Línea de ayuda con el estado y cómo activarlo."""
    if habilitado():
        return "Respaldo OpenRouter: activado."
    return ("Respaldo OpenRouter: desactivado (pendiente de configuración). "
            "Actívalo con --openrouter, RFPRMN_OPENROUTER=1 o "
            f'"openrouter": true en {ARCHIVO_OPCIONES}')


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
                for linea in ruta.read_text(encoding="utf-8-sig",
                                            errors="replace").splitlines():
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
    except ErrorProyecto:
        raise
    except Exception as error:
        raise ErrorProyecto(f"OpenRouter {modelo_id} falló ({error}).")


def _refactorizar_con_openrouter(contenido: str, analisis, clave: str) -> tuple[str, str, str]:
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
    modelos = list(MODELOS_OR_CODIGO)
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
