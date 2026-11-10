"""Comandos de gestión del proyecto PRY <-> RFC (issue #81).

Las operaciones destructivas son transaccionales:

- ``_refactorizar_layout_actual`` y ``comando_enviar`` ya **no borran el
  destino antes de copiar**: usan ``reemplazar_directorio`` (copia temporal +
  verificación por huella + intercambio con rollback).
- ``_actualizar_layout_actual`` verifica la nueva versión **antes** de purgar
  las anteriores, y reporta con precisión los restos que no pudo limpiar.
- ``_registrar_envio`` escribe el JSON de forma atómica y con bloqueo, y
  conserva el registro corrupto en vez de perderlo.
- Las rutas críticas (RAIZ, PRY, RFC, CONTRRF, TLLDCD y la propia herramienta)
  están protegidas contra borrado.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from .stm_base import (
    advertir, exito, informar, reportar_error, pedir_confirmacion, ErrorProyecto,
    RAIZ, RFC_DIR, PRY_DIR, MODULO_DIR, TLLDCD_DIR,
    CONTRRF_DIR, EXTENSIONES_POR_LENGUAJE, carpetas_creadas,
)
from .stm_fs import (  # noqa: F401  (re-exportados: compatibilidad de RFPRMN)
    bloqueo, borrar_contenido, copiar_contenido, eliminar_ruta,
    encontrar_contenido_actual, es_subruta, escribir_json_atomico,
    hacer_escribible, reemplazar_directorio, rutas_se_solapan,
    _contar_ficheros, _forzar_borrado,
)
from .stm_registro import (  # noqa: F401  (re-exportados: compatibilidad de RFPRMN)
    DIR_REGISTRO as DIR_REGISTRO_JSON, RUTA_JSON as REGISTRO_ENVIOS,
)
from .stm_rutas import (
    rutas_protegidas, ultima_actualizacion_pry as _ultima_actualizacion_pry,
    actualizar_rutas_finales,
)

#: Mensaje único cuando el layout no es el esperado (P4: sin rama heredada).
_MENSAJE_LAYOUT = (
    "No se reconoce el layout del proyecto (faltan las carpetas de RFC/PRY). "
    "Configúralas con 'configurar rutas' o con RFPRMN_RFC_DIR / RFPRMN_PRY_DIR.")


# --- Utilidades --------------------------------------------------------------

#: Carpeta de la herramienta dentro de TLLDCD: SIEMPRE se conserva al limpiar.
CARPETA_HERRAMIENTA = TLLDCD_DIR / "STM_RFC"


def _misma_ruta(a: str | Path, b: str | Path) -> bool:
    """True si ambas rutas apuntan al mismo sitio (comparación normalizada)."""
    return es_subruta(a, b) and es_subruta(b, a)


def _zonas_protegidas() -> tuple[Path, ...]:
    """Raíces del proyecto que nunca deben borrarse como un todo."""
    return tuple(rutas_protegidas())


def _comprobar_borrado(ruta: str | Path) -> None:
    """Aborta si ``ruta`` es una raíz crítica o vive dentro de la herramienta."""
    objetivo = Path(ruta)
    if any(_misma_ruta(objetivo, zona) for zona in _zonas_protegidas()):
        raise ErrorProyecto(f"Borrado bloqueado: {objetivo} es una ruta crítica.")
    if es_subruta(objetivo, MODULO_DIR):
        raise ErrorProyecto(
            f"Borrado bloqueado: {objetivo} pertenece a la herramienta.")


def _es_layout_actual() -> bool:
    """True si existe el árbol VersionDe_sesion (RFC y/o PRY del flujo actual)."""
    try:
        if _ultima_actualizacion_pry() is not None:
            return True
        return (CONTRRF_DIR / "RFC").is_dir() or PRY_DIR.is_dir()
    except Exception:
        return False


# --- Comandos PRY <-> RFC ----------------------------------------------------

def comando_refactorizar() -> None:
    """Copia el contenido actual de PRY hacia RFC, previa confirmación."""
    if not _es_layout_actual():
        reportar_error(_MENSAJE_LAYOUT)
        return
    _refactorizar_layout_actual()


def _refactorizar_layout_actual() -> None:
    """Rama actual: ``PRY/<última actualizacion>/src`` -> ``RFC/src`` verificado.

    La copia se verifica por huella (ruta + tamaño + SHA-256) y solo entonces
    sustituye al ``src`` anterior; si la copia falla, RFC queda como estaba.
    """
    ultima = _ultima_actualizacion_pry()
    if ultima is None:
        reportar_error("PRY no tiene ninguna actualizacion_* para traer.")
        return
    origen = ultima / "src" if (ultima / "src").is_dir() else ultima
    destino = RFC_DIR / "src"

    advertir(f"Se copiará {origen} a {destino} (reemplaza el src de RFC).")
    if not pedir_confirmacion("¿Desea continuar?"):
        informar("Operación cancelada.")
        return
    try:
        info = reemplazar_directorio(origen, destino)
    except (ErrorProyecto, OSError) as error:
        _registrar_envio(origen, destino, 0, f"FALLO {error}")
        reportar_error(f"Error al copiar el contenido: {error}")
        return
    exito(f"Contenido copiado de {origen} a {destino} "
          f"({info['ficheros']} ficheros verificados)")
    _registrar_envio(origen, destino, info["ficheros"], "OK refactorizar")


def crear_carpeta(ruta: str, nombre: str) -> str:
    """Crea (si no existe) ``nombre`` dentro de ``ruta`` y devuelve la ruta final.

    El nombre debe ser un nombre simple: se rechazan ``.``, ``..`` y cualquier
    separador de ruta, en lugar de «sanearlo» en silencio.
    """
    base = Path(ruta)
    limpio = nombre.strip()
    if not limpio or limpio in {".", ".."} or Path(limpio).name != limpio:
        raise ErrorProyecto(f"Nombre de carpeta no válido: {nombre!r}")
    carpeta = base / limpio
    if not es_subruta(carpeta, base):
        raise ErrorProyecto(f"La carpeta saldría de {base}: {carpeta}")
    carpeta.mkdir(parents=True, exist_ok=True)
    return str(carpeta)


def comando_crear_carpeta() -> None:
    """Solicita interactivamente una ruta y un nombre, y crea la carpeta."""
    ruta = input("Ruta donde crear: ").strip().strip("\"'")
    nombre = input("Nombre de la carpeta: ").strip()
    try:
        carpeta = crear_carpeta(ruta, nombre)
    except (ErrorProyecto, OSError) as error:
        reportar_error(f"No se pudo crear la carpeta: {error}")
        return
    exito(f"Carpeta creada en: {carpeta}")
    relativa = os.path.relpath(carpeta, RAIZ)
    if relativa not in carpetas_creadas:
        carpetas_creadas.append(relativa)


def comando_crear_archivo() -> None:
    """Solicita interactivamente ruta, nombre y lenguaje, y crea un archivo vacío."""
    ruta = input("Ruta donde crear: ").strip().strip("\"'")
    nombre = input("Nombre del archivo (sin extensión): ").strip()
    lenguaje = input("Lenguaje de programación (ej: python, csharp, html): ").strip().lower()

    extension = EXTENSIONES_POR_LENGUAJE.get(lenguaje, f".{lenguaje}" if lenguaje else "")
    if not nombre or not extension:
        reportar_error("Nombre o lenguaje no válido.")
        return
    if Path(nombre).name != nombre:
        reportar_error(f"El nombre del archivo no puede incluir rutas: {nombre!r}")
        return
    if not nombre.endswith(extension):
        nombre += extension
    archivo = Path(ruta) / nombre
    try:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        if not archivo.exists():
            archivo.touch()
    except OSError as error:
        reportar_error(f"No se pudo crear el archivo: {error}")
        return
    exito(f"Archivo creado en: {archivo}")


def _registrar_envio(origen: Path, destino: Path, ficheros: int, estado: str) -> None:
    """Anota el envío en ``stm_registro_json/envios.json`` (issue #81, punto 6).

    Escritura atómica bajo bloqueo: si el JSON estuviera corrupto se conserva
    una copia ``.corrupto`` y se empieza una lista nueva, sin perder el rastro.
    """
    evento = {
        "carpeta": Path(origen).name, "origen": str(origen), "destino": str(destino),
        "ficheros": ficheros, "estado": estado,
        "fecha": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }
    try:
        REGISTRO_ENVIOS.parent.mkdir(parents=True, exist_ok=True)
        with bloqueo(REGISTRO_ENVIOS):
            datos: object = []
            if REGISTRO_ENVIOS.exists():
                try:
                    datos = json.loads(REGISTRO_ENVIOS.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    with_ = REGISTRO_ENVIOS.with_name(REGISTRO_ENVIOS.name + ".corrupto")
                    try:
                        shutil.copy2(REGISTRO_ENVIOS, with_)
                        advertir(f"Registro ilegible; copia conservada en {with_.name}.")
                    except OSError:
                        pass
                    datos = []
            if not isinstance(datos, list):
                datos = []
            datos.append(evento)
            escribir_json_atomico(REGISTRO_ENVIOS, datos)
    except (ErrorProyecto, OSError) as error:
        advertir(f"No se pudo registrar el envío ({error}).")


def comando_enviar() -> None:
    """Pide una carpeta y envía el directorio COMPLETO a su destino.

    El destino se sustituye solo cuando la copia está verificada (nada de
    borrar-y-luego-copiar). Registra el envío y, si todo cuadra, limpia el
    origen salvo las rutas protegidas.
    """
    entrada = input("Ruta de la carpeta a enviar: ").strip().strip("\"'")
    if not entrada:
        reportar_error("No se indicó ninguna carpeta.")
        return
    origen = Path(os.path.expandvars(os.path.expanduser(entrada))).resolve()
    if not origen.exists() or not origen.is_dir():
        reportar_error(f"La carpeta no existe: {origen}")
        return
    if es_subruta(origen, MODULO_DIR) or _misma_ruta(origen, MODULO_DIR.parent):
        reportar_error("No se puede enviar la carpeta propia de la herramienta.")
        return
    if any(_misma_ruta(origen, zona) for zona in (RAIZ, PRY_DIR, RFC_DIR, CONTRRF_DIR)):
        reportar_error(f"Origen protegido (raíz del proyecto): {origen}")
        return

    if _misma_ruta(origen, RFC_DIR) or es_subruta(origen, RFC_DIR):
        destino = (TLLDCD_DIR / origen.name).resolve()
    else:
        destino = (RFC_DIR / origen.name).resolve()
    if es_subruta(destino, MODULO_DIR):
        reportar_error("El destino chocaría con la herramienta.")
        return
    if rutas_se_solapan(origen, destino) and not _misma_ruta(origen, destino):
        reportar_error(f"Origen y destino se solapan: {origen} / {destino}")
        return
    if _misma_ruta(origen, destino):
        reportar_error("El origen y el destino son la misma carpeta.")
        return

    advertir(f"Se enviará el directorio completo {origen} a {destino} "
             "y se limpiará el origen.")
    if not pedir_confirmacion("¿Desea continuar?"):
        informar("Operación cancelada.")
        return
    try:
        info = reemplazar_directorio(origen, destino)
    except (ErrorProyecto, OSError) as error:
        _registrar_envio(origen, destino, 0, f"FALLO {error}")
        reportar_error(f"Error al enviar ({error}): no se borra el origen.")
        return
    exito(f"Directorio {origen.name} enviado a {destino} "
          f"({info['ficheros']} ficheros verificados)")
    _registrar_envio(origen, destino, info["ficheros"], "OK")
    if _misma_ruta(origen, TLLDCD_DIR):
        _limpiar_tlldcd(origen)
        return
    try:
        _comprobar_borrado(origen)
        eliminar_ruta(str(origen))
        exito(f"Origen eliminado: {origen}")
    except (ErrorProyecto, OSError) as error:
        advertir(f"El envío se completó, pero el origen no se pudo limpiar: {error}")


def _limpiar_tlldcd(origen: Path) -> None:
    """Vacía TLLDCD conservando la herramienta y su carpeta contenedora."""
    fallos: list[str] = []
    protegidas = {MODULO_DIR.resolve(), CARPETA_HERRAMIENTA.resolve()}
    for hijo in list(origen.iterdir()):
        try:
            if hijo.resolve() in protegidas:
                continue
            _comprobar_borrado(hijo)
            eliminar_ruta(str(hijo))
        except (ErrorProyecto, OSError) as error:
            fallos.append(f"{hijo.name}: {error}")
    if fallos:
        for fallo in fallos:
            advertir(f"No se pudo borrar: {fallo}")
        reportar_error("Limpieza parcial: reintenta 'enviar' tras cerrar el daemon IPFS.")
    else:
        exito(f"TLLDCD limpio; solo queda: {MODULO_DIR.name}")


# --- Actualización PRY -------------------------------------------------------

def actualizar() -> None:
    """Promueve el contenido de RFC a PRY como una nueva versión histórica."""
    if not _es_layout_actual():
        reportar_error(_MENSAJE_LAYOUT)
        return
    _actualizar_layout_actual()


def _actualizar_layout_actual() -> None:
    """Rama actual: RFC (CONTRRF) -> PRY versionado y verificado (issue #81).

    Orden seguro: copiar -> verificar huella -> registrar -> purgar versiones
    anteriores -> vaciar RFC -> publicar el registro. Nunca se purga nada antes
    de que la nueva versión esté verificada.
    """
    if not RFC_DIR.is_dir() or not os.listdir(RFC_DIR):
        reportar_error("No hay contenido en RFC para actualizar.")
        return
    if not PRY_DIR.is_dir():
        reportar_error(f"PRY no encontrado: {PRY_DIR}")
        return

    advertir("PRY recibirá una nueva versión del contenido de RFC; "
             "las anteriores se purgan.")
    if not pedir_confirmacion("¿Seguro que deseas continuar?"):
        informar("Operación cancelada.")
        return
    origen = Path(encontrar_contenido_actual(str(RFC_DIR)))
    numero = uuid.uuid4().hex[:8]
    destino = PRY_DIR / f"actualizacion_{numero}"
    try:
        info = reemplazar_directorio(origen, destino)
    except (ErrorProyecto, OSError) as error:
        _registrar_envio(origen, destino, 0, f"FALLO {error}")
        reportar_error(f"Copia incompleta ({error}): PRY y RFC intactos.")
        return
    exito(f"Actualización completada en: {destino} "
          f"({info['ficheros']} ficheros verificados)")
    _registrar_envio(origen, destino, info["ficheros"], "OK actualizar")
    _actualizar_rutas_finales(destino)
    purgadas, fallos_purga = _purgar_versiones_anteriores(destino)
    if fallos_purga:
        advertir(f"{len(fallos_purga)} versión(es) anterior(es) no se pudieron purgar.")
    _vaciar_rfc()
    _publicar(origen, destino, info["ficheros"], purgadas)


def _purgar_versiones_anteriores(destino: Path) -> tuple[list[str], list[str]]:
    """Borra las ``actualizacion_*`` de PRY salvo la recién creada.

    Solo se llama con la nueva versión ya verificada, de modo que un fallo de
    limpieza nunca deja el proyecto sin versión válida.
    """
    purgadas: list[str] = []
    fallos: list[str] = []
    for hijo in list(PRY_DIR.iterdir()):
        if hijo == destino or not hijo.name.startswith("actualizacion_"):
            continue
        try:
            eliminar_ruta(str(hijo))
            purgadas.append(hijo.name)
            exito(f"Versión anterior purgada: {hijo.name}")
        except OSError as error:
            fallos.append(f"{hijo.name}: {error}")
            advertir(f"No se pudo purgar {hijo.name}: {error}")
    return purgadas, fallos


def _vaciar_rfc() -> bool:
    """Vacía RFC y verifica que no quede ningún resto."""
    try:
        borrar_contenido(str(RFC_DIR))
    except OSError as error:
        advertir(f"Limpieza RFC parcial: {error}")
    restos = [p.name for p in RFC_DIR.iterdir()] if RFC_DIR.is_dir() else []
    if restos:
        reportar_error(f"RFC no quedó vacío (posible bloqueo): {restos}. "
                       "Reintenta tras cerrar el daemon IPFS.")
        return False
    informar(f"Contenido eliminado de: {RFC_DIR}")
    return True


def _actualizar_rutas_finales(destino: Path) -> None:
    """Registra las rutas finales de la nueva versión (nunca invalida actualizar)."""
    try:
        archivo = actualizar_rutas_finales(destino)
        informar(f"Rutas finales actualizadas en {archivo}")
    except Exception as error:  # noqa: BLE001 - no invalida la actualización
        advertir(f"No se pudieron actualizar las rutas finales ({error}).")


def _publicar(origen: Path, destino: Path, ficheros: int,
              purgadas: list[str]) -> None:
    """Publica el registro de la actualización (md -> pesos -> IPFS -> limpio)."""
    try:
        from .stm_registro import publicar_registro_actualizar
        publicar_registro_actualizar({
            "origen": str(origen), "destino": str(destino),
            "ficheros": ficheros, "purgadas": purgadas})
    except Exception as error_pub:  # noqa: BLE001 - nunca invalida la actualización
        advertir(f"No se pudo publicar el registro ({error_pub}).")
