"""Primitivas de sistema de archivos de RFPRMN, seguras y reversibles (#81).

Reglas que aplica este módulo:

- **Nada se borra antes de estar copiado y verificado.** El reemplazo de un
  directorio se hace en tres tiempos: copia a ``.tmp``, verificación por huella
  (ruta relativa + tamaño + SHA-256) e intercambio atómico con ``os.replace``,
  con rollback si el intercambio falla.
- **Los errores de borrado se reportan.** ``eliminar_ruta`` ya no se conforma
  con ``ignore_errors``: enumera los restos y lanza ``OSError`` si quedan.
- **Los enlaces simbólicos son explícitos**: se copian como enlaces
  (``symlinks=True``) y nunca se sigue un enlace al recorrer árboles.
- **El JSON se escribe de forma atómica** (temporal + ``os.replace``) y con
  bloqueo entre procesos, para no dejar registros truncados.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import stat
import time
import uuid
from pathlib import Path
from typing import Any, Iterator, Optional

from .stm_base import ErrorProyecto, advertir

#: Tamaño de bloque usado al hashear y copiar.
BLOQUE = 1024 * 1024
#: Por encima de este tamaño solo se compara el tamaño (evita hashear .pck).
TAMANO_MAX_HASH = 64 * 1024 * 1024
#: Reintentos y espera incremental ante bloqueos transitorios de Windows.
INTENTOS_BORRADO = 4
ESPERA_REINTENTO = 0.4
#: Antigüedad a partir de la cual un cerrojo se considera huérfano.
EDAD_CERROJO_HUERFANO = 60.0


# --- Rutas -------------------------------------------------------------------

def ruta_larga(ruta: str | Path) -> str:
    """Devuelve ``ruta`` con prefijo ``\\\\?\\`` en Windows (evita MAX_PATH)."""
    texto = str(ruta)
    if os.name == "nt" and not texto.startswith("\\\\?\\"):
        return "\\\\?\\" + texto
    return texto


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


def _existe(ruta: Path) -> bool:
    """``exists`` que cuenta también los enlaces simbólicos rotos."""
    return ruta.exists() or ruta.is_symlink()


def _listar(ruta: Path) -> list[str]:
    """Nombres de las entradas de ``ruta`` (vacío si no se puede leer)."""
    try:
        return sorted(hijo.name for hijo in ruta.iterdir())
    except OSError:
        return []


# --- Permisos y borrado ------------------------------------------------------

def _quitar_solo_lectura(ruta: Path) -> None:
    """Añade el bit de escritura (los ficheros de solo lectura bloquean el borrado)."""
    try:
        modo = os.stat(ruta, follow_symlinks=False).st_mode
        if not modo & stat.S_IWRITE:
            os.chmod(ruta, modo | stat.S_IWRITE)
    except OSError:
        pass


def hacer_escribible(ruta: str | Path, errores: Optional[list[str]] = None) -> None:
    """Otorga permiso de escritura a ``ruta`` de forma recursiva.

    ``errores`` permite acumular fallos en lugar de tragárselos.
    """
    objetivo = Path(ruta)
    if objetivo.is_symlink():
        return
    try:
        os.chmod(objetivo, os.stat(objetivo).st_mode | stat.S_IWRITE)
    except OSError as error:
        if errores is not None:
            errores.append(f"{objetivo}: {error}")
        return
    if objetivo.is_dir():
        try:
            with os.scandir(objetivo) as entradas:
                for entrada in entradas:
                    hacer_escribible(entrada.path, errores)
        except OSError as error:
            if errores is not None:
                errores.append(f"{objetivo}: {error}")


def _forzar_borrado(funcion, ruta: str, _info) -> None:
    """Compatibilidad: manejador ``onerror`` de ``rmtree`` (no se usa ya).

    Se conserva porque ``RFPRMN`` re-exporta el símbolo; el borrado real lo
    hace :func:`_borrar_arbol`, que sí reporta los fallos.
    """
    try:
        os.chmod(ruta, stat.S_IWRITE)
    except OSError:
        pass
    try:
        funcion(ruta)
    except OSError:
        pass


def _borrar_arbol(ruta: Path, errores: list[str]) -> None:
    """Borra ``ruta`` de abajo arriba acumulando cada fallo en ``errores``."""
    for raiz, dirs, ficheros in os.walk(ruta, topdown=False, followlinks=False):
        for nombre in ficheros:
            objetivo = Path(raiz) / nombre
            try:
                _quitar_solo_lectura(objetivo)
                objetivo.unlink()
            except FileNotFoundError:
                continue
            except OSError as error:
                errores.append(f"{objetivo}: {error}")
        for nombre in dirs:
            objetivo = Path(raiz) / nombre
            try:
                if objetivo.is_symlink():
                    objetivo.unlink()
                else:
                    objetivo.rmdir()
            except FileNotFoundError:
                continue
            except OSError as error:
                errores.append(f"{objetivo}: {error}")
    try:
        ruta.rmdir()
    except FileNotFoundError:
        pass
    except OSError as error:
        errores.append(f"{ruta}: {error}")


def eliminar_ruta(ruta: str | Path, intentos: int = INTENTOS_BORRADO) -> None:
    """Elimina un archivo o un árbol completo, reintentando ante bloqueos.

    Si tras ``intentos`` siguen quedando restos, lanza ``OSError`` con la lista
    de lo que sobrevivió y la causa del último fallo (issue #81, punto 5).
    """
    objetivo = Path(ruta)
    if not _existe(objetivo):
        return
    errores: list[str] = []
    for intento in range(1, intentos + 1):
        errores = []
        try:
            if objetivo.is_symlink() or objetivo.is_file():
                _quitar_solo_lectura(objetivo)
                objetivo.unlink()
            else:
                _borrar_arbol(objetivo, errores)
        except OSError as error:
            errores.append(f"{objetivo}: {error}")
        if not _existe(objetivo):
            return
        if intento < intentos:
            time.sleep(ESPERA_REINTENTO * intento)
            hacer_escribible(objetivo, errores)
    restos = _listar(objetivo)
    causa = "; ".join(errores[:3]) or "sin detalle"
    raise OSError(
        f"No se pudo eliminar {objetivo}: quedan {len(restos)} elemento(s) "
        f"{restos[:5]}. Causa: {causa}")


def eliminar_ruta_seguro(ruta: str | Path) -> bool:
    """Borra sin lanzar; True si ya no queda nada (limpieza de temporales)."""
    try:
        eliminar_ruta(ruta)
    except OSError as error:
        advertir(f"No se pudo limpiar {ruta}: {error}")
        return False
    return True


def borrar_contenido(carpeta: str | Path) -> None:
    """Vacía ``carpeta`` conservando el directorio; reporta los restos."""
    objetivo = Path(carpeta)
    if not objetivo.is_dir():
        return
    fallos: list[str] = []
    for hijo in list(objetivo.iterdir()):
        try:
            eliminar_ruta(hijo)
        except OSError as error:
            fallos.append(str(error))
    if fallos:
        raise OSError(f"Limpieza incompleta de {objetivo}: " + " | ".join(fallos))


# --- Copia -------------------------------------------------------------------

def copiar_contenido(origen: str | Path, destino: str | Path) -> None:
    """Copia recursivamente el contenido de ``origen`` dentro de ``destino``.

    Rechaza copiar un directorio dentro de sí mismo o de un descendiente.
    """
    origen_p, destino_p = Path(origen), Path(destino)
    if es_subruta(destino_p, origen_p):
        raise ErrorProyecto(
            f"Copia recursiva imposible: {destino_p} está dentro de {origen_p}.")
    destino_p.mkdir(parents=True, exist_ok=True)
    for item in origen_p.iterdir():
        salida = destino_p / item.name
        if item.is_dir() and not item.is_symlink():
            shutil.copytree(item, salida, dirs_exist_ok=True, symlinks=True)
        else:
            shutil.copy2(item, salida, follow_symlinks=False)


def encontrar_contenido_actual(carpeta: str | Path) -> str:
    """Desciende por carpetas ``actualizacion_*`` anidadas hasta el contenido real."""
    actual = str(carpeta)
    while True:
        try:
            contenido = os.listdir(actual)
        except OSError:
            return actual
        if len(contenido) != 1:
            return actual
        hijo = contenido[0]
        ruta = os.path.join(actual, hijo)
        if not hijo.startswith("actualizacion_") or not os.path.isdir(ruta):
            return actual
        actual = ruta


def _contar_ficheros(carpeta: str | Path) -> int:
    """Cuenta ficheros recursivos (sin seguir enlaces simbólicos)."""
    total = 0
    for _raiz, _dirs, ficheros in os.walk(carpeta, followlinks=False):
        total += len(ficheros)
    return total


def sha256_archivo(ruta: str | Path) -> str:
    """SHA-256 hexadecimal del contenido de ``ruta``."""
    digest = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(BLOQUE), b""):
            digest.update(bloque)
    return digest.hexdigest()


def huella_directorio(carpeta: str | Path) -> dict[str, tuple[int, str]]:
    """Huella de un árbol: ``{ruta_relativa: (tamaño, sha256|marca)}``.

    Los ficheros mayores de ``TAMANO_MAX_HASH`` se identifican por tamaño para
    no bloquear la verificación con binarios grandes.
    """
    base = Path(carpeta)
    huella: dict[str, tuple[int, str]] = {}
    for raiz, _dirs, ficheros in os.walk(base, followlinks=False):
        for nombre in ficheros:
            ruta = Path(raiz) / nombre
            relativa = ruta.relative_to(base).as_posix()
            try:
                tamano = ruta.stat().st_size
            except OSError as error:
                huella[relativa] = (-1, f"error: {error}")
                continue
            if tamano <= TAMANO_MAX_HASH:
                try:
                    huella[relativa] = (tamano, sha256_archivo(ruta))
                except OSError as error:
                    huella[relativa] = (tamano, f"error: {error}")
            else:
                huella[relativa] = (tamano, f"tamano:{tamano}")
    return huella


def verificar_copia(origen: str | Path, destino: str | Path) -> dict[str, Any]:
    """Compara origen y destino por ruta, tamaño y contenido (issue #81, punto 3).

    Devuelve ``{"ok", "origen", "destino", "faltan", "distintos", "sobran"}``.
    ``sobran`` no invalida la copia: un destino con ficheros de más no pierde
    datos del origen.
    """
    huella_origen = huella_directorio(origen)
    huella_destino = huella_directorio(destino)
    faltan = sorted(set(huella_origen) - set(huella_destino))
    sobran = sorted(set(huella_destino) - set(huella_origen))
    distintos = sorted(
        relativa for relativa in set(huella_origen) & set(huella_destino)
        if huella_origen[relativa] != huella_destino[relativa]
    )
    return {
        "ok": not faltan and not distintos,
        "origen": len(huella_origen),
        "destino": len(huella_destino),
        "faltan": faltan,
        "distintos": distintos,
        "sobran": sobran,
    }


def reemplazar_directorio(origen: str | Path, destino: str | Path) -> dict[str, Any]:
    """Sustituye ``destino`` por una copia verificada de ``origen`` (#81, puntos 1 y 2).

    El destino original **no se toca** hasta que la copia temporal está
    completa y verificada. Si el intercambio falla, se restaura el original.
    Devuelve ``{"destino", "ficheros", "reemplazado", "respaldo"}``.
    """
    origen_p = Path(origen)
    destino_p = Path(destino)
    if not origen_p.is_dir():
        raise ErrorProyecto(f"El origen no es un directorio: {origen_p}")
    if rutas_se_solapan(origen_p, destino_p):
        raise ErrorProyecto(
            f"Origen y destino se solapan ({origen_p} / {destino_p}): "
            "la copia recursiva destruiría datos.")
    destino_p.parent.mkdir(parents=True, exist_ok=True)
    sello = uuid.uuid4().hex[:8]
    temporal = destino_p.parent / f".{destino_p.name}.tmp-{sello}"
    respaldo = destino_p.parent / f".{destino_p.name}.old-{sello}"
    try:
        shutil.copytree(origen_p, temporal, symlinks=True)
    except OSError:
        eliminar_ruta_seguro(temporal)
        raise
    verificacion = verificar_copia(origen_p, temporal)
    if not verificacion["ok"]:
        eliminar_ruta_seguro(temporal)
        raise ErrorProyecto(
            f"Copia incompleta de {origen_p}: faltan {len(verificacion['faltan'])} "
            f"y difieren {len(verificacion['distintos'])} fichero(s); "
            f"el destino {destino_p} queda intacto.")
    reemplazado = destino_p.exists()
    try:
        if reemplazado:
            os.replace(destino_p, respaldo)
        os.replace(temporal, destino_p)
    except OSError:
        if reemplazado and not destino_p.exists() and respaldo.exists():
            with contextlib.suppress(OSError):
                os.replace(respaldo, destino_p)
        eliminar_ruta_seguro(temporal)
        raise
    if reemplazado:
        if eliminar_ruta_seguro(respaldo):
            respaldo = None
        else:
            advertir(f"Respaldo conservado por bloqueo: {respaldo}")
    return {"destino": str(destino_p), "ficheros": verificacion["origen"],
            "reemplazado": reemplazado,
            "respaldo": str(respaldo) if respaldo is not None else None}


# --- Escritura atómica -------------------------------------------------------

def escribir_texto_atomico(ruta: str | Path, texto: str, encoding: str = "utf-8") -> None:
    """Escribe ``texto`` en ``ruta`` sin dejar estados intermedios.

    Usa un temporal en el mismo directorio y ``os.replace``; si algo falla, el
    archivo original permanece intacto.
    """
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(
        f".{destino.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:6]}")
    try:
        with open(temporal, "w", encoding=encoding, newline="") as archivo:
            archivo.write(texto)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, destino)
    except OSError:
        with contextlib.suppress(OSError):
            temporal.unlink()
        raise


def escribir_json_atomico(ruta: str | Path, datos: Any) -> None:
    """Serializa ``datos`` como JSON y lo escribe de forma atómica."""
    escribir_texto_atomico(ruta, json.dumps(datos, indent=2, ensure_ascii=False))


@contextlib.contextmanager
def bloqueo(ruta: str | Path, timeout: float = 5.0) -> Iterator[Path]:
    """Bloqueo entre procesos mediante fichero ``.lock`` (issue #81, punto 6)."""
    cerrojo = Path(str(ruta) + ".lock")
    cerrojo.parent.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(cerrojo, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - cerrojo.stat().st_mtime > EDAD_CERROJO_HUERFANO:
                    cerrojo.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() > limite:
                raise ErrorProyecto(
                    f"Registro bloqueado por otro proceso: {cerrojo}")
            time.sleep(0.05)
        else:
            try:
                os.write(descriptor, str(os.getpid()).encode("ascii"))
            finally:
                os.close(descriptor)
            break
    try:
        yield cerrojo
    finally:
        with contextlib.suppress(OSError):
            cerrojo.unlink()
