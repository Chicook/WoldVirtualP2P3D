"""Rutas oficiales de RFPRMN: **única fuente de verdad** (R1/R2/R5).

Reglas que impone este módulo:

- **Nada que la herramienta escriba puede vivir bajo `CONTRRF/RFC` ni bajo
  `Sistema_Principal/PRY`.** Esos árboles se sincronizan y `actualizar` los
  vacía al final de cada ciclo; un modelo o un registro ahí dentro se pierde o
  contamina la siguiente versión.
- **La configuración de IA local se busca en una cadena explícita** que empieza
  por la variable de entorno y por la última `actualizacion_*` de PRY, que es
  donde vive de verdad. El `RFC/src` legado queda como último recurso.
- **Los pesos y el registro de refactor van bajo `STM_RFPRMN/`**, así viajan con
  la herramienta y sobreviven al vaciado de RFC.

R5 · rutas elegidas por el usuario
----------------------------------
``RFC_DIR`` y ``PRY_DIR`` se resuelven, por este orden, desde:

1. las variables ``RFPRMN_RFC_DIR`` / ``RFPRMN_PRY_DIR``,
2. ``STM_RFPRMN/.config/rutas.json`` (lo escribe ``--configurar-rutas``),
3. las rutas oficiales del escritorio (compatibilidad),
4. el layout junto a la herramienta.

Este módulo no importa nada del paquete (sólo stdlib) para que `stm_base` pueda
usarlo sin crear ciclos; los comandos interactivos importan el estilo de forma
diferida dentro de cada función.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

# --- Árbol del proyecto ------------------------------------------------------

#: Directorio de la herramienta (`.../STM_RFC/STM_RFPRMN`).
MODULO_DIR = Path(__file__).resolve().parent.parent
#: `.../VersionDe_sesion/CONTRRF`.
CONTRRF_DIR = MODULO_DIR.parent.parent
#: `.../CONTRRF/TLLDCD` (rama heredada que aún se conserva).
TLLDCD_DIR = CONTRRF_DIR / "TLLDCD"
#: `src` de trabajo: RFC legado, TLLDCD, o actualizacion_* en PRY según lo que exista.
SRC_DIR = CONTRRF_DIR / "RFC" / "src"
if (TLLDCD_DIR / "src").is_dir():
    SRC_DIR = TLLDCD_DIR / "src"
else:
    # Buscar en la última actualización de PRY
    pry_dir = CONTRRF_DIR.parent / "Sistema_Principal" / "PRY"
    if pry_dir.is_dir():
        try:
            actualizaciones = [hijo for hijo in pry_dir.iterdir()
                              if hijo.is_dir() and hijo.name.startswith("actualizacion_")]
            if actualizaciones:
                ultima = max(actualizaciones, key=lambda ruta: ruta.stat().st_mtime)
                if (ultima / "src").is_dir():
                    SRC_DIR = ultima / "src"
        except (OSError, FileNotFoundError):
            pass

# --- Datos propios de la herramienta -----------------------------------------

#: Configuración de la herramienta (rutas elegidas, `IAlocal.json` de reserva).
DIR_CONFIG = MODULO_DIR / ".config"
#: Archivo donde se guardan las rutas elegidas por el usuario.
ARCHIVO_RUTAS = DIR_CONFIG / "rutas.json"
#: Opciones de la herramienta (respaldo OpenRouter, modelo de embeddings...).
ARCHIVO_OPCIONES = DIR_CONFIG / "opciones.json"
#: Raíz de datos propios (pesos, caché), FUERA de los árboles sincronizados.
DIR_DATOS = MODULO_DIR / ".modelos"
#: Carpeta donde se descargan los pesos GGUF.
DIR_MODELOS_LOCAL = DIR_DATOS / "IAlocalDESCARGADA"
#: Registro de qué archivo refactorizó cada modelo.
REGISTRO_REFACTOR_MD = MODULO_DIR / "registro_refactor.md"


# --- Rutas oficiales (compatibilidad, R5) ------------------------------------
#: Valores históricos del equipo de desarrollo: ya no son obligatorios.
RUTA_RFC_OFICIAL = Path(
    r"C:\Users\User\Desktop\WoldVirtualP2P3D_v0.0.01LCV1\VersionDe_sesion\CONTRRF\RFC")
RUTA_PRY_OFICIAL = Path(
    r"C:\Users\User\Desktop\WoldVirtualP2P3D_v0.0.01LCV1\VersionDe_sesion\Sistema_Principal\PRY")


def _leer_config_rutas() -> dict:
    """Contenido de ``.config/rutas.json`` (``{}`` si no existe o está roto)."""
    try:
        datos = json.loads(ARCHIVO_RUTAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def leer_opciones() -> dict:
    """Contenido de ``.config/opciones.json`` (``{}`` si no existe o está roto)."""
    try:
        datos = json.loads(ARCHIVO_OPCIONES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _resolver_directorio(clave_entorno: str, clave_config: str, oficial: Path,
                         derivada: Path, config: dict) -> tuple[Path, str]:
    """Resuelve un directorio y devuelve ``(ruta, origen)``."""
    desde_entorno = os.environ.get(clave_entorno, "").strip()
    if desde_entorno:
        return Path(os.path.expandvars(desde_entorno)).expanduser(), "entorno"
    desde_config = str(config.get(clave_config) or "").strip()
    if desde_config:
        return Path(os.path.expandvars(desde_config)).expanduser(), "archivo"
    if oficial.is_dir():
        return oficial, "oficial"
    return derivada, "layout"


_CONFIG_AL_IMPORTAR = _leer_config_rutas()
RFC_DIR, ORIGEN_RFC = _resolver_directorio(
    "RFPRMN_RFC_DIR", "rfc", RUTA_RFC_OFICIAL, CONTRRF_DIR / "RFC", _CONFIG_AL_IMPORTAR)
PRY_DIR, ORIGEN_PRY = _resolver_directorio(
    "RFPRMN_PRY_DIR", "pry", RUTA_PRY_OFICIAL,
    CONTRRF_DIR.parent / "Sistema_Principal" / "PRY", _CONFIG_AL_IMPORTAR)


# --- Localización de la raíz -------------------------------------------------

def encontrar_raiz(ruta: str | Path) -> str:
    """Localiza la raíz del proyecto soportando los tres layouts conocidos."""
    actual = Path(ruta).resolve()
    if actual.is_file():
        actual = actual.parent
    for candidato in (actual, *actual.parents):
        if (candidato / "src" / "STMGNRL" / "mainLCSTM.py").is_file():
            return str(candidato)
        if (candidato / "RFC" / "src" / "STMGNRL" / "mainLCSTM.py").is_file():
            return str(candidato)
        if (candidato / "RFC").is_dir() and (
                candidato.parent / "Sistema_Principal" / "PRY").is_dir():
            return str(candidato.parent)
        if (candidato / "CONTRRF" / "RFC").is_dir() and (
                candidato / "Sistema_Principal" / "PRY").is_dir():
            return str(candidato)
        if (candidato / "RFC").is_dir() and (
                candidato / "Sistema_Principal" / "PRY").is_dir():
            return str(candidato)
        if (candidato / "VersionDe_sesion" / "CONTRRF" / "RFC").is_dir() and (
                candidato / "VersionDe_sesion" / "Sistema_Principal" / "PRY").is_dir():
            return str(candidato / "VersionDe_sesion")
        if (candidato / "CONTRRF" / "STM_RFC").is_dir() and (
                candidato / "Sistema_Principal" / "PRY").is_dir():
            return str(candidato)
        if (candidato / "VersionDe_sesion" / "CONTRRF" / "STM_RFC").is_dir() and (
                candidato / "VersionDe_sesion" / "Sistema_Principal" / "PRY").is_dir():
            return str(candidato / "VersionDe_sesion")
        if (candidato / "Construccion" / "CPRZ" / "PRY").is_dir():
            return str(candidato)
    from .stm_base import RaizProyectoNoEncontrada  # diferido: stm_base usa este módulo
    raise RaizProyectoNoEncontrada("No se encontró la raíz del proyecto.")


RAIZ = Path(encontrar_raiz(__file__))
if (RAIZ / "RFC" / "src" / "STMGNRL" / "mainLCSTM.py").is_file():
    ORIGEN = RAIZ / "RFC" / "src"
    DESTINO = RAIZ / "RFC"
elif (RAIZ / "src" / "STMGNRL" / "mainLCSTM.py").is_file():
    ORIGEN = RAIZ / "src"
    DESTINO = RAIZ / "STM_RFC" / "sync"
elif (RAIZ / "Sistema_Principal" / "PRY").is_dir():
    ORIGEN = RAIZ / "Sistema_Principal" / "PRY"
    DESTINO = RAIZ / "CONTRRF" / "RFC"
else:
    ORIGEN = RAIZ / "Construccion" / "CPRZ" / "PRY"
    DESTINO = RAIZ / "Construccion" / "CONTRRF" / "RFC"


# --- Predicados de ruta ------------------------------------------------------

def _normalizada(ruta: str | Path) -> str:
    """Ruta absoluta normalizada para comparar (sin distinguir mayúsculas en Windows)."""
    return os.path.normcase(os.path.abspath(str(Path(ruta).resolve(strict=False))))


def es_subruta(hijo: str | Path, padre: str | Path) -> bool:
    """True si ``hijo`` es ``padre`` o está dentro de él."""
    ruta_hija, ruta_padre = _normalizada(hijo), _normalizada(padre)
    if ruta_hija == ruta_padre:
        return True
    try:
        return os.path.commonpath([ruta_hija, ruta_padre]) == ruta_padre
    except ValueError:  # unidades distintas
        return False


def rutas_se_solapan(a: str | Path, b: str | Path) -> bool:
    """True si una ruta contiene a la otra (copia recursiva imposible)."""
    return es_subruta(a, b) or es_subruta(b, a)


def es_zona_sincronizada(ruta: str | Path) -> bool:
    """True si ``ruta`` cae dentro de los árboles que se sincronizan (RFC/PRY)."""
    return es_subruta(ruta, RFC_DIR) or es_subruta(ruta, PRY_DIR)


def comprobar_ruta_segura(ruta: str | Path, motivo: str = "") -> Path:
    """Valida que ``ruta`` sea escribible por la herramienta y devuelve su ``Path``."""
    objetivo = Path(ruta)
    if es_zona_sincronizada(objetivo):
        from .stm_base import ErrorProyecto  # diferido: stm_base importa este módulo
        detalle = f" ({motivo})" if motivo else ""
        raise ErrorProyecto(
            f"Ruta no permitida{detalle}: {objetivo} está dentro de un árbol "
            "sincronizado (RFC/PRY). Usa STM_RFPRMN/.modelos.")
    return objetivo


# --- Configuración de IA local ----------------------------------------------

def ultima_actualizacion_pry() -> Optional[Path]:
    """Devuelve la ``actualizacion_*`` más reciente de PRY (None si no hay)."""
    try:
        candidatas = [hijo for hijo in PRY_DIR.iterdir()
                      if hijo.is_dir() and hijo.name.startswith("actualizacion_")]
    except OSError:
        return None
    if not candidatas:
        return None
    try:
        return max(candidatas, key=lambda ruta: ruta.stat().st_mtime)
    except OSError:
        return candidatas[0]


def candidatos_config_ia_local() -> tuple[Path, ...]:
    """Rutas donde se busca ``IAlocal.json``, en orden de prioridad."""
    candidatas: list[Path] = []
    entorno = os.environ.get("RFPRMN_IALOCAL_JSON", "").strip()
    if entorno:
        candidatas.append(Path(os.path.expandvars(os.path.expanduser(entorno))))
    ultima = ultima_actualizacion_pry()
    if ultima is not None:
        candidatas.append(ultima / "src" / "STM_JSON" / "IAlocal.json")
    candidatas.append(RFC_DIR / "src" / "STM_JSON" / "IAlocal.json")
    candidatas.append(DIR_CONFIG / "IAlocal.json")
    vistas: set[str] = set()
    unicas: list[Path] = []
    for candidata in candidatas:
        clave = _normalizada(candidata)
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(candidata)
    return tuple(unicas)


def ruta_config_ia_local() -> Path:
    """Primera configuración existente de la cadena, o la preferida si no hay."""
    opciones = candidatos_config_ia_local()
    for candidata in opciones:
        if candidata.is_file():
            return candidata
    return opciones[0]


def describir_config_ia_local() -> str:
    """Texto de ayuda con la cadena de búsqueda (para mensajes de error).

    Se usa un separador ASCII a propósito: la consola de Windows en cp1252 no
    puede representar ``→`` y el mensaje de error rompería al imprimirse.
    """
    return " | ".join(str(ruta) for ruta in candidatos_config_ia_local())


#: Compatibilidad: valor resuelto al importar el módulo.
CONFIG_IA_LOCAL = ruta_config_ia_local()


def rutas_protegidas() -> Iterable[Path]:
    """Raíces que nunca deben borrarse como un todo."""
    return (RAIZ, PRY_DIR, RFC_DIR, CONTRRF_DIR, TLLDCD_DIR, MODULO_DIR,
            MODULO_DIR.parent)


# --- R5: rutas elegidas por el usuario ---------------------------------------

def estado_rutas() -> dict:
    """Estado actual de RFC/PRY y de dónde salió cada ruta."""
    return {
        "rfc": str(RFC_DIR),
        "pry": str(PRY_DIR),
        "origen_rfc": ORIGEN_RFC,
        "origen_pry": ORIGEN_PRY,
        "archivo": str(ARCHIVO_RUTAS),
        "archivo_existe": ARCHIVO_RUTAS.is_file(),
        "entorno_rfc": os.environ.get("RFPRMN_RFC_DIR", ""),
        "entorno_pry": os.environ.get("RFPRMN_PRY_DIR", ""),
        "rutas_finales": leer_rutas_finales(),
    }


def guardar_rutas(rfc: str | Path, pry: str | Path) -> Path:
    """Guarda en ``.config/rutas.json`` los directorios elegidos por el usuario.

    Valida que ambos existan, que no se solapen y que no sean la misma carpeta.
    Devuelve la ruta del archivo escrito. Se aplica en la siguiente ejecución.
    """
    from .stm_base import ErrorProyecto  # diferido: stm_base importa este módulo

    destino_rfc = Path(os.path.expandvars(str(rfc))).expanduser().resolve()
    destino_pry = Path(os.path.expandvars(str(pry))).expanduser().resolve()
    if es_subruta(destino_rfc, destino_pry) or es_subruta(destino_pry, destino_rfc):
        raise ErrorProyecto(
            "RFC y PRY no pueden estar uno dentro del otro: "
            f"{destino_rfc} / {destino_pry}")
    for ruta, nombre in ((destino_rfc, "RFC"), (destino_pry, "PRY")):
        if not ruta.is_dir():
            raise ErrorProyecto(
                f"{nombre} no es un directorio existente: {ruta}. "
                "Créalo antes de configurarlo.")
    DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    datos = _leer_config_rutas()
    datos.update({"rfc": str(destino_rfc), "pry": str(destino_pry)})
    temporal = ARCHIVO_RUTAS.with_name(ARCHIVO_RUTAS.name + ".tmp")
    temporal.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporal, ARCHIVO_RUTAS)
    return ARCHIVO_RUTAS


def actualizar_rutas_finales(destino: str | Path) -> Path:
    """Registra las rutas finales de la última ``actualizacion_*`` generada.

    La llama ``actualizar`` cuando crea y verifica la nueva carpeta de versión
    en PRY. Guarda en ``.config/rutas.json`` la carpeta final, su ``src`` y la
    fecha, bajo la clave ``rutas_finales``. NO altera ``rfc``/``pry`` (los
    directorios de trabajo): repuntar ``pry`` a la subcarpeta rompería
    ``ultima_actualizacion_pry`` y la purga de versiones. Escritura atómica;
    devuelve la ruta del archivo escrito.
    """
    final = Path(os.path.expandvars(str(destino))).expanduser().resolve()
    src_final = final / "src" if (final / "src").is_dir() else final
    DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    datos = _leer_config_rutas()
    datos["rutas_finales"] = {
        "carpeta": str(final),
        "src": str(src_final),
        "nombre": final.name,
        "fecha": datetime.now().isoformat(timespec="seconds"),
    }
    temporal = ARCHIVO_RUTAS.with_name(ARCHIVO_RUTAS.name + ".tmp")
    temporal.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporal, ARCHIVO_RUTAS)
    return ARCHIVO_RUTAS


def leer_rutas_finales() -> dict:
    """Rutas finales registradas por ``actualizar`` (``{}`` si aún no hay)."""
    finales = _leer_config_rutas().get("rutas_finales")
    return finales if isinstance(finales, dict) else {}


def comando_rutas() -> None:
    """Muestra por pantalla las rutas activas y su origen."""
    from .stm_base import _caja, _imprimir_seguro  # diferido (evita el ciclo)

    estado = estado_rutas()
    filas = [
        ("RFC", f"{estado['rfc']}  [{estado['origen_rfc']}]"),
        ("PRY", f"{estado['pry']}  [{estado['origen_pry']}]"),
        ("Config", estado["archivo"] + ("" if estado["archivo_existe"] else " (sin crear)")),
        ("Modelos", str(DIR_MODELOS_LOCAL)),
        ("Registro", str(REGISTRO_REFACTOR_MD)),
    ]
    _imprimir_seguro(_caja("Rutas del proyecto", filas, color="azul"))
    print()


def comando_configurar_rutas() -> None:
    """Pide al usuario los directorios de RFC y PRY y los guarda (R5)."""
    from .stm_base import (  # diferido (evita el ciclo)
        ErrorProyecto, exito, informar, reportar_error,
    )

    estado = estado_rutas()
    informar("Deja vacío para mantener el valor actual.")
    rfc = input(f"Directorio de RFC [{estado['rfc']}]: ").strip().strip("\"'")
    pry = input(f"Directorio de PRY [{estado['pry']}]: ").strip().strip("\"'")
    try:
        archivo = guardar_rutas(rfc or estado["rfc"], pry or estado["pry"])
    except (ErrorProyecto, OSError) as error:
        reportar_error(f"No se guardaron las rutas: {error}")
        return
    exito(f"Rutas guardadas en {archivo}")
    informar("Se aplican en la próxima ejecución (o exporta RFPRMN_RFC_DIR/RFPRMN_PRY_DIR).")
