"""Rutas oficiales de RFPRMN: **única fuente de verdad** (R1/R2 de la discusión #84).

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

Este módulo no importa nada del paquete (sólo stdlib) para que `stm_base` pueda
usarlo sin crear ciclos.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional

# --- Árbol del proyecto ------------------------------------------------------

#: Directorio de la herramienta (`.../STM_RFC/STM_RFPRMN`).
MODULO_DIR = Path(__file__).resolve().parent.parent
#: `.../VersionDe_sesion/CONTRRF`.
CONTRRF_DIR = MODULO_DIR.parent.parent
#: `.../CONTRRF/TLLDCD` (rama heredada que aún se conserva).
TLLDCD_DIR = CONTRRF_DIR / "TLLDCD"
#: `src` de trabajo: RFC legado o TLLDCD según lo que exista.
SRC_DIR = CONTRRF_DIR / "RFC" / "src"
if (TLLDCD_DIR / "src").is_dir():
    SRC_DIR = TLLDCD_DIR / "src"

#: Rutas oficiales fijas del sistema (deuda R5: deberían venir de configuración).
RUTA_RFC_OFICIAL = Path(
    r"C:\Users\User\Desktop\WoldVirtualP2P3D_v0.0.01LCV1\VersionDe_sesion\CONTRRF\RFC")
RUTA_PRY_OFICIAL = Path(
    r"C:\Users\User\Desktop\WoldVirtualP2P3D_v0.0.01LCV1\VersionDe_sesion\Sistema_Principal\PRY")

#: Árboles sincronizados (sólo lectura para la herramienta).
RFC_DIR = RUTA_RFC_OFICIAL if RUTA_RFC_OFICIAL.is_dir() else CONTRRF_DIR / "RFC"
PRY_DIR = (RUTA_PRY_OFICIAL if RUTA_PRY_OFICIAL.is_dir()
           else CONTRRF_DIR.parent / "Sistema_Principal" / "PRY")


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


# --- Rutas de escritura de la herramienta ------------------------------------

#: Raíz de datos propios (pesos, caché), FUERA de los árboles sincronizados.
DIR_DATOS = MODULO_DIR / ".modelos"
#: Carpeta donde se descargan los pesos GGUF.
DIR_MODELOS_LOCAL = DIR_DATOS / "IAlocalDESCARGADA"
#: Registro de qué archivo refactorizó cada modelo.
REGISTRO_REFACTOR_MD = MODULO_DIR / "registro_refactor.md"
#: Configuración propia de la herramienta (último recurso de la cadena).
DIR_CONFIG = MODULO_DIR / ".config"


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
    """Valida que ``ruta`` sea escribible por la herramienta y devuelve su ``Path``.

    Lanza ``ErrorProyecto`` si cae bajo RFC/PRY: escribir ahí ensucia el árbol
    sincronizado y el contenido desaparece al vaciarlo (R1/R2).
    """
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
