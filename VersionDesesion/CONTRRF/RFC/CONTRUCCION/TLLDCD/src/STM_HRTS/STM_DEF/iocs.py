"""Indicadores de compromiso (IOC) del ataque detectado.

Fuente unica de verdad: todos los indicadores del dropper "EtherHiding"
hallado en ``PRY`` viven aqui y ningun otro modulo repite literales.

Se puede ampliar sin tocar codigo creando ``iocs_extra.txt`` junto a este
fichero: una linea por dominio, ``#`` inicia comentario.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from .modelos import ALTA, BAJA, MEDIA, Patron

# --- Carteras C2 conocidas (EtherHiding) ----------------------------------
DIRECCIONES_C2: Tuple[str, ...] = (
    "0x3b1574417524c11a7403c4b232cacbb320ccebc6",
)

# --- Dominios usados por el dropper (explorador + JSON-RPC) ---------------
DOMINIOS_C2: Tuple[str, ...] = (
    "ethplorer.io",
    "api.ethplorer.io",
    "ethereum.publicnode.com",
)

# --- Familia de RPC publicos de Ethereum (canal C2 de EtherHiding) --------
SUFIJOS_RPC: Tuple[str, ...] = (
    ".publicnode.com",
    ".llamarpc.com",
    ".drpc.org",
    ".1rpc.io",
    ".ankr.com",
    ".alchemyapi.io",
    ".infura.io",
    ".quiknode.pro",
    ".blockpi.network",
)

# --- Puertos propios de nodos/RPC de Ethereum -----------------------------
PUERTOS_RPC: Tuple[int, ...] = (8545, 8546)

# --- Patrones de texto/codigo --------------------------------------------
PATRONES: Tuple[Patron, ...] = (
    Patron("c2.ethplorer", r"api\.ethplorer\.io", ALTA,
           "llamada a la API del explorador usado por el dropper (ethplorer)"),
    Patron("c2.rpc", r"eth_getTransactionByHash|eth_getTransactionReceipt|eth_getBlockByNumber", ALTA,
           "JSON-RPC de Ethereum: recupera el payload de una transaccion"),
    Patron("c2.gettx", r"getAddressTransactions", ALTA,
           "listado de transacciones de una cartera (paso 1 del dropper)"),
    Patron("c2.freekey", r"apiKey=freekey", MEDIA,
           "clave publica de ethplorer usada por el dropper"),
    Patron("c2.wallet", r"0x3b1574417524c11a7403c4b232cacbb320ccebc6", ALTA,
           "cartera C2 conocida (EtherHiding)"),
    Patron("drop.fromhex", r"bytes\.fromhex\s*\(", MEDIA,
           "decodifica hex (payload recuperado de la blockchain)"),
    Patron("drop.nodetmp", r"(NamedTemporaryFile|mkstemp)[^\n]{0,160}(node|\.js)", MEDIA,
           "fichero temporal .js preparado para ejecucion"),
    Patron("drop.node", r"(subprocess|_sp)\s*\.\s*(run|Popen|call)[^\n]{0,120}\bnode\b", ALTA,
           "ejecucion de 'node' sobre contenido descargado"),
    Patron("js.eval", r"\beval\s*\(|new\s+Function\s*\(", MEDIA,
           "evaluacion dinamica de codigo (tecnica de ofuscacion)"),
    Patron("js.childproc", r"require\(\s*['\"]child_process['\"]\s*\)|child_process\.exec", MEDIA,
           "acceso a child_process (ejecucion de comandos)"),
    Patron("js.hexid", r"\b_0x[0-9a-fA-F]{4,}\b", ALTA,
           "identificadores hex caracteristicos de obfuscator.io"),
    Patron("js.fromcharcode", r"String\.fromCharCode|fromCharCode\.apply", MEDIA,
           "reconstruccion de cadenas desde codigos (ofuscacion)"),
    Patron("js.textdecoder", r"TextDecoder\(|Buffer\.from\([^)]{0,40}['\"]hex['\"]", MEDIA,
           "decodificacion de buffers hex (ofuscacion)"),
    Patron("js.parseint16", r"parseInt\([^,]{1,32},\s*16\s*\)", BAJA,
           "parseo hexadecimal repetido (ofuscacion)"),
    Patron("js.atob", r"\batob\s*\(", BAJA,
           "decodificacion base64 (ofuscacion)"),
    Patron("js.whiletrue", r"while\s*\(\s*!!\[\s*\]\s*\)", MEDIA,
           "bucle de desempaquetado tipico de obfuscator.io"),
    Patron("drop.execjs", r"\.run\(\s*\[\s*['\"]node['\"]", ALTA,
           "invocacion directa de node sobre un fichero"),
    Patron("drop.tmpdel", r"os\.unlink\(|_os\.unlink\(", BAJA,
           "borrado del rastro del fichero temporal"),
    # --- disparadores automaticos (vector 1: tarea que corre al abrir) -----
    # Son indicadores de *fichero* (settings.json / tasks.json), no de linea de
    # comandos: por eso viven en PATRONES, que recorre todo el arbol, y asi el
    # mecanismo del vector 1 se delata en cualquier fichero.
    Patron("auto.allowautomatic", r"allowAutomaticTasks\s*\"?\s*[:=]\s*\"?true", ALTA,
           "habilita la ejecucion automatica de tareas de VS Code (disparador del vector 1)"),
    Patron("auto.runon", r"\"?runOn\"?\s*[:=]\s*\"?folderOpen", MEDIA,
           "tarea que se dispara al abrir la carpeta (runOn: folderOpen)"),
)

# --- Nombres de fichero usados como camuflaje -----------------------------
NOMBRES_CAMUFLAJE: Tuple[str, ...] = (
    "init",
    "transport.py",
    "fa-brand-400.orc",
)

# --- Extensiones que no deberian contener JavaScript ----------------------
EXTENSIONES_ANOMALAS: Tuple[str, ...] = (".orc",)

# --- Patrones peligrosos en lineas de comandos ----------------------------
PATRONES_COMANDO: Tuple[Tuple[str, str, str], ...] = (
    ("cmd.node", r"\bnode\b[^\n]*\.(js|mjs|cjs)\b", "ejecuta un fichero JavaScript con node"),
    ("cmd.nodeinit", r"\bnode\s+init\b", "ejecuta el loader 'init' (vector de 'npm start')"),
    ("cmd.pwshhidden", r"-enc(odedcommand)?\b|-(w|windowstyle)\s+hidden\b", "PowerShell codificado u oculto"),
    ("cmd.curlpipe", r"(curl|iwr|invoke-webrequest)[^\n|]*\|\s*(sh|bash|iex|node)", "descarga y ejecuta en tuberia"),
)


def _leer_extra() -> Tuple[str, ...]:
    """Dominios adicionales declarados en ``iocs_extra.txt`` (si existe)."""
    ruta = Path(__file__).resolve().parent / "iocs_extra.txt"
    if not ruta.is_file():
        return ()
    dominios: List[str] = []
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        limpio = linea.split("#", 1)[0].strip().lower()
        if limpio:
            dominios.append(limpio)
    return tuple(dominios)


#: Dominios extra definidos por el operador.
DOMINIOS_EXTRA: Tuple[str, ...] = _leer_extra()

#: Regex ya compiladas (coste cero en cada analisis).
REGEX_COMPILADAS: Tuple[Tuple[Patron, "re.Pattern[str]"], ...] = tuple(
    (patron, re.compile(patron.regex, re.IGNORECASE)) for patron in PATRONES
)

#: Regex de comandos ya compiladas.
REGEX_COMANDO: Tuple[Tuple[str, "re.Pattern[str]", str], ...] = tuple(
    (id_, re.compile(rx, re.IGNORECASE), desc) for id_, rx, desc in PATRONES_COMANDO
)


def normalizar_host(host: str) -> str:
    """Normaliza un host o URL a minusculas, sin esquema, ruta ni puerto."""
    texto = (host or "").strip().lower()
    if "://" in texto:
        texto = texto.split("://", 1)[1]
    texto = texto.split("/", 1)[0]
    if texto.startswith("[") and "]" in texto:  # IPv6 literal
        return texto.split("]", 1)[0] + "]"
    if texto.count(":") == 1:
        texto = texto.split(":", 1)[0]
    return texto.rstrip(".")


def es_dominio_c2(host: str) -> bool:
    """True si el host pertenece a la infraestructura C2 conocida."""
    limpio = normalizar_host(host)
    if not limpio:
        return False
    for dominio in (*DOMINIOS_C2, *DOMINIOS_EXTRA):
        if limpio == dominio or limpio.endswith("." + dominio):
            return True
    for sufijo in SUFIJOS_RPC:
        if limpio.endswith(sufijo):
            return True
    return False


def es_direccion_c2(texto: str) -> bool:
    """True si el texto contiene una cartera C2 conocida."""
    bajo = (texto or "").lower()
    return any(direccion in bajo for direccion in DIRECCIONES_C2)


def todos_los_dominios() -> Tuple[str, ...]:
    """Dominios a bloquear: conocidos + sufijos RPC + extra."""
    return tuple(dict.fromkeys((*DOMINIOS_C2, *SUFIJOS_RPC, *DOMINIOS_EXTRA)))


__all__ = [
    "DIRECCIONES_C2", "DOMINIOS_C2", "SUFIJOS_RPC", "PUERTOS_RPC", "PATRONES",
    "NOMBRES_CAMUFLAJE", "EXTENSIONES_ANOMALAS", "PATRONES_COMANDO",
    "REGEX_COMPILADAS", "REGEX_COMANDO", "DOMINIOS_EXTRA",
    "normalizar_host", "es_dominio_c2", "es_direccion_c2", "todos_los_dominios",
]
