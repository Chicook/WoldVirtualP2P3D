"""Submodulo de RFPRMN (refactor: tope 400/450 lineas)."""
from __future__ import annotations
import ast, json, os, re, shutil, stat, subprocess, sys, textwrap, time, urllib.error, urllib.parse, urllib.request, uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional
try:
    from .stm_base import (E, informar, exito, advertir, reportar_error, pedir_confirmacion, ErrorProyecto, RaizProyectoNoEncontrada, encontrar_raiz, RAIZ, ORIGEN, DESTINO, CONFIG_IA_LOCAL, RFC_DIR, PRY_DIR, SRC_DIR, MODULO_DIR, TLLDCD_DIR, CONTRRF_DIR, _caja, _panel, ANCHO_TERMINAL, _imprimir_seguro, RESPUESTAS_AFIRMATIVAS, LIMITE_TAMANO_ANALISIS, EXTENSIONES_POR_LENGUAJE, PATRON_MARCADOR_PENDIENTE, carpetas_creadas, __version__)
except ImportError:
    pass
# --- Utilidades de sistema de archivos --------------------------------------

def hacer_escribible(ruta: str) -> None:
    """Otorga permiso de escritura a ``ruta`` de forma recursiva."""
    if os.path.islink(ruta):
        return
    os.chmod(ruta, os.stat(ruta).st_mode | stat.S_IWRITE)
    if os.path.isdir(ruta):
        with os.scandir(ruta) as entradas:
            for entrada in entradas:
                hacer_escribible(entrada.path)


def _forzar_borrado(funcion, ruta: str, _info) -> None:
    """Manejador onerror de rmtree: quita solo-lectura y reintenta."""
    try:
        os.chmod(ruta, stat.S_IWRITE)
    except OSError:
        pass
    try:
        funcion(ruta)
    except OSError:
        pass


def eliminar_ruta(ruta: str) -> None:
    """Elimina un archivo o un árbol de directorios completo.

    Tolera atributos de solo-lectura (repo IPFS) y bloqueos transitorios
    de Windows (reintenta con espera); si el sistema lo bloquea de forma
    persistente, lanza el OSError original.
    """
    ultimo_error: Optional[OSError] = None
    for intento in range(4):
        try:
            if os.path.isdir(ruta) and not os.path.islink(ruta):
                shutil.rmtree(ruta, onerror=_forzar_borrado)
            else:
                try:
                    os.remove(ruta)
                except PermissionError:
                    os.chmod(ruta, stat.S_IWRITE)
                    os.remove(ruta)
            if not os.path.exists(ruta):
                return
            ultimo_error = OSError(f"No se pudo eliminar (posible bloqueo): {ruta}")
        except OSError as error:
            ultimo_error = error
            try:
                hacer_escribible(ruta)
            except OSError:
                pass
        time.sleep(0.5 * (intento + 1))
    raise ultimo_error if ultimo_error is not None else OSError(f"No se pudo eliminar: {ruta}")


def borrar_contenido(carpeta: str) -> None:
    """Vacía ``carpeta``, reintentando tras corregir permisos si es necesario."""
    for item in os.listdir(carpeta):
        ruta = os.path.join(carpeta, item)
        try:
            eliminar_ruta(ruta)
        except PermissionError:
            hacer_escribible(ruta)
            eliminar_ruta(ruta)


def copiar_contenido(origen: str, destino: str) -> None:
    """Copia recursivamente el contenido de ``origen`` dentro de ``destino``."""
    os.makedirs(destino, exist_ok=True)
    for item in os.listdir(origen):
        origen_item = os.path.join(origen, item)
        destino_item = os.path.join(destino, item)
        if os.path.isdir(origen_item) and not os.path.islink(origen_item):
            shutil.copytree(origen_item, destino_item, dirs_exist_ok=True)
        else:
            shutil.copy2(origen_item, destino_item)


def encontrar_contenido_actual(carpeta: str) -> str:
    """Desciende por carpetas ``actualizacion_*`` anidadas hasta el contenido real."""
    actual = carpeta
    while True:
        contenido = os.listdir(actual)
        if len(contenido) != 1:
            return actual
        hijo = contenido[0]
        ruta = os.path.join(actual, hijo)
        if not hijo.startswith("actualizacion_") or not os.path.isdir(ruta):
            return actual
        actual = ruta


# --- Comandos de gestión del proyecto ---------------------------------------

def _ultima_actualizacion_pry() -> Optional[Path]:
    """Devuelve la actualizacion_* más reciente de PRY (None si no hay)."""
    try:
        cands = [h for h in PRY_DIR.iterdir()
                 if h.is_dir() and h.name.startswith("actualizacion_")]
    except OSError:
        return None
    if not cands:
        return None
    return max(cands, key=lambda p: p.stat().st_mtime)


def _es_layout_actual() -> bool:
    """True si existe el árbol VersionDe_sesion (RFC y/o PRY del flujo actual)."""
    try:
        if _ultima_actualizacion_pry() is not None:
            return True
        return (CONTRRF_DIR / "RFC").is_dir() or PRY_DIR.is_dir()
    except Exception:
        return False


def comando_refactorizar() -> None:
    """Copia el contenido actual de PRY hacia RFC, previa confirmación."""
    if _es_layout_actual():
        _refactorizar_layout_actual()
        return
    if not ORIGEN.is_dir():
        reportar_error(f"Origen no encontrado: {ORIGEN}")
        return

    advertir("esta acción reemplazará todo el contenido de RFC.")
    if not pedir_confirmacion("¿Desea continuar?"):
        informar("Operación cancelada.")
        return

    try:
        os.makedirs(DESTINO, exist_ok=True)
        origen = encontrar_contenido_actual(str(ORIGEN))
        borrar_contenido(str(DESTINO))
        copiar_contenido(origen, str(DESTINO))
        exito(f"Contenido copiado de {origen} a {DESTINO}")
    except OSError as error:
        reportar_error(f"Error al copiar el contenido: {error}")


def _refactorizar_layout_actual() -> None:
    """Rama actual: PRY/<última actualizacion>/src -> RFC/src verificado.

    Trae de vuelta solo la carpeta ``src`` (sin la envoltura
    actualizacion_*) y registra el movimiento en envios.json.
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
        RFC_DIR.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            eliminar_ruta(str(destino))
        shutil.copytree(str(origen), str(destino))
        n_origen = _contar_ficheros(origen)
        n_destino = _contar_ficheros(destino)
        if n_origen != n_destino:
            _registrar_envio(origen, destino, n_destino, f"FALLO verificacion {n_destino}/{n_origen}")
            reportar_error(f"Copia incompleta ({n_destino}/{n_origen} ficheros).")
            return
        exito(f"Contenido copiado de {origen} a {destino} ({n_destino} ficheros verificados)")
        _registrar_envio(origen, destino, n_destino, "OK refactorizar")
    except OSError as error:
        reportar_error(f"Error al copiar el contenido: {error}")


def crear_carpeta(ruta: str, nombre: str) -> str:
    """Crea (si no existe) ``nombre`` dentro de ``ruta`` y devuelve la ruta final."""
    carpeta = os.path.join(ruta, nombre)
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)
    return carpeta


def comando_crear_carpeta() -> None:
    """Solicita interactivamente una ruta y un nombre, y crea la carpeta."""
    ruta = input("Ruta donde crear: ")
    nombre = input("Nombre de la carpeta: ")
    carpeta = crear_carpeta(ruta, nombre)
    exito(f"Carpeta creada en: {carpeta}")
    relativa = os.path.relpath(carpeta, RAIZ)
    if relativa not in carpetas_creadas:
        carpetas_creadas.append(relativa)


def comando_crear_archivo() -> None:
    """Solicita interactivamente ruta, nombre y lenguaje, y crea un archivo vacío."""
    ruta = input("Ruta donde crear: ").strip()
    nombre = input("Nombre del archivo (sin extensión): ").strip()
    lenguaje = input("Lenguaje de programación (ej: python, csharp, html): ").strip().lower()

    extension = EXTENSIONES_POR_LENGUAJE.get(lenguaje, f".{lenguaje}")
    if not nombre.endswith(extension):
        nombre += extension

    archivo = os.path.join(ruta, nombre)
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    if not os.path.exists(archivo):
        open(archivo, "w", encoding="utf-8").close()
    exito(f"Archivo creado en: {archivo}")


#: Carpeta de la herramienta dentro de TLLDCD: SIEMPRE se conserva al limpiar
#: TLLDCD (contiene el registro de envíos, que debe viajar con el proyecto).
CARPETA_HERRAMIENTA = TLLDCD_DIR / "STM_RFC"
#: Registro de envíos ("github minimalista"): vive en TLLDCD/STM_RFC/envios.json
#: para viajar con TLLDCD y sobrevivir al vaciado de RFC.
DIR_REGISTRO_JSON = CARPETA_HERRAMIENTA
REGISTRO_ENVIOS = DIR_REGISTRO_JSON / "envios.json"


def _contar_ficheros(carpeta: Path) -> int:
    """Cuenta ficheros recursivos (sin seguir symlinks)."""
    total = 0
    for _raiz, _dirs, fichs in os.walk(carpeta, followlinks=False):
        total += len(fichs)
    return total


def _registrar_envio(origen: Path, destino: Path, ficheros: int, estado: str) -> None:
    """Anota el envío en stm_registro_json/envios.json (sobrevive al vaciado)."""
    try:
        datos = json.loads(REGISTRO_ENVIOS.read_text(encoding="utf-8")) if REGISTRO_ENVIOS.exists() else []
    except (OSError, ValueError):
        datos = []
    datos.append({
        "carpeta": origen.name, "origen": str(origen), "destino": str(destino),
        "ficheros": ficheros, "estado": estado,
        "fecha": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    })
    try:
        REGISTRO_ENVIOS.parent.mkdir(parents=True, exist_ok=True)
        REGISTRO_ENVIOS.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as error:
        advertir(f"No se pudo registrar el envío ({error}).")


def comando_enviar() -> None:
    """Pide una carpeta y envía el directorio COMPLETO a su destino.

    Registra la ruta completa del origen en stm_registro_json/envios.json.
    Destino según ubicación: si el origen está en CONTRRF/RFC se envía
    a TLLDCD/<nombre> (p. ej. RFC/src -> TLLDCD/src); en caso contrario
    se envía a RFC/<nombre>. La copia se verifica por conteo y solo
    entonces se limpia el origen (TLLDCD conserva siempre STM_RFC).
    """
    entrada = input("Ruta de la carpeta a enviar: ").strip().strip("\"'")
    if not entrada:
        reportar_error("No se indicó ninguna carpeta.")
        return
    origen = Path(os.path.expandvars(os.path.expanduser(entrada))).resolve()
    if not origen.exists() or not origen.is_dir():
        reportar_error(f"La carpeta no existe: {origen}")
        return
    if (origen == MODULO_DIR or MODULO_DIR in origen.parents
            or origen in MODULO_DIR.parents):
        reportar_error("No se puede enviar la carpeta propia de la herramienta.")
        return
    if origen == RFC_DIR.resolve() or RFC_DIR.resolve() in origen.parents:
        destino = (TLLDCD_DIR / origen.name).resolve()
        if destino == MODULO_DIR or MODULO_DIR in destino.parents:
            reportar_error("El destino chocaría con la herramienta.")
            return
    else:
        destino = (RFC_DIR / origen.name).resolve()
        if destino == MODULO_DIR or MODULO_DIR in destino.parents:
            reportar_error("El destino chocaría con la herramienta.")
            return

    advertir(f"Se enviará el directorio completo {origen} a {destino} y se limpiará el origen.")
    if not pedir_confirmacion("¿Desea continuar?"):
        informar("Operación cancelada.")
        return
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            eliminar_ruta(str(destino))
        shutil.copytree(str(origen), str(destino))
        n_origen = _contar_ficheros(origen)
        n_destino = _contar_ficheros(destino)
        if n_origen != n_destino:
            _registrar_envio(origen, destino, n_destino, f"FALLO verificacion {n_destino}/{n_origen}")
            reportar_error(f"Copia incompleta ({n_destino}/{n_origen} ficheros): no se borra el origen.")
            return
        exito(f"Directorio {origen.name} enviado a {destino} ({n_destino} ficheros verificados)")
        _registrar_envio(origen, destino, n_destino, "OK")
        if origen == TLLDCD_DIR:
            fallos: list[str] = []
            protegidas = {MODULO_DIR.resolve(), CARPETA_HERRAMIENTA.resolve()}
            for hijo in list(origen.iterdir()):
                if hijo.resolve() in protegidas:
                    continue
                try:
                    eliminar_ruta(str(hijo))
                except OSError as error_hijo:
                    fallos.append(f"{hijo.name}: {error_hijo}")
            if fallos:
                for f in fallos:
                    advertir(f"No se pudo borrar: {f}")
                reportar_error("Limpieza parcial: reintenta 'enviar' tras cerrar el daemon IPFS.")
            else:
                exito(f"TLLDCD limpio; solo queda: {MODULO_DIR.name}")
        else:
            eliminar_ruta(str(origen))
            exito(f"Origen eliminado: {origen}")
    except OSError as error:
        reportar_error(f"Error al enviar: {error}")


def actualizar() -> None:
    """Promueve el contenido de RFC a PRY como una nueva versión histórica."""
    if _es_layout_actual():
        _actualizar_layout_actual()
        return
    if not ORIGEN.is_dir():
        reportar_error(f"Origen no encontrado: {ORIGEN}")
        return
    if not DESTINO.is_dir() or not os.listdir(DESTINO):
        reportar_error("No hay contenido refactorizado para actualizar.")
        return

    advertir("PRY será reemplazado por una nueva versión de RFC.")
    if not pedir_confirmacion("¿Seguro que deseas continuar?"):
        informar("Operación cancelada.")
        return

    try:
        origen = encontrar_contenido_actual(str(DESTINO))
        borrar_contenido(str(ORIGEN))
        numero = uuid.uuid4().hex[:8]
        destino = os.path.join(ORIGEN, f"actualizacion_{numero}")
        copiar_contenido(origen, destino)
        borrar_contenido(str(DESTINO))
        exito(f"Actualización completada en: {destino}")
        informar(f"Contenido eliminado de: {DESTINO}")
    except OSError as error:
        reportar_error(f"Error al actualizar: {error}")


def _actualizar_layout_actual() -> None:
    """Rama actual: RFC (CONTRRF) -> PRY (Sistema_Principal) versionado.

    Copia verificada (conteo), purga las versiones anteriores de PRY
    (solo queda la nueva) y vacía RFC por completo, verificando que
    no quede ningún resto. Al terminar publica registro.md en lenguaje
    natural, lo convierte en pesos, lo sube a IPFS y limpia el registro.
    """
    if not RFC_DIR.is_dir() or not os.listdir(RFC_DIR):
        reportar_error("No hay contenido en RFC para actualizar.")
        return
    if not PRY_DIR.is_dir():
        reportar_error(f"PRY no encontrado: {PRY_DIR}")
        return

    advertir("PRY recibirá una nueva versión del contenido de RFC; las anteriores se purgan.")
    if not pedir_confirmacion("¿Seguro que deseas continuar?"):
        informar("Operación cancelada.")
        return
    try:
        origen = encontrar_contenido_actual(str(RFC_DIR))
        n_origen = _contar_ficheros(Path(origen))
        numero = uuid.uuid4().hex[:8]
        destino = PRY_DIR / f"actualizacion_{numero}"
        copiar_contenido(origen, str(destino))
        n_destino = _contar_ficheros(destino)
        if n_origen != n_destino:
            _registrar_envio(Path(origen), destino, n_destino, f"FALLO verificacion {n_destino}/{n_origen}")
            reportar_error(f"Copia incompleta ({n_destino}/{n_origen}): PRY y RFC intactos.")
            try:
                eliminar_ruta(str(destino))
            except OSError:
                pass
            return
        exito(f"Actualización completada en: {destino} ({n_destino} ficheros verificados)")
        _registrar_envio(Path(origen), destino, n_destino, "OK actualizar")
        purgadas: list[str] = []
        for hijo in list(PRY_DIR.iterdir()):
            if hijo == destino or not hijo.name.startswith("actualizacion_"):
                continue
            try:
                eliminar_ruta(str(hijo))
                purgadas.append(hijo.name)
                exito(f"Versión anterior purgada: {hijo.name}")
            except OSError as error_hijo:
                advertir(f"No se pudo purgar {hijo.name}: {error_hijo}")
        try:
            borrar_contenido(str(RFC_DIR))
        except OSError as error_rfc:
            advertir(f"Limpieza RFC parcial: {error_rfc}")
        restos = [p.name for p in RFC_DIR.iterdir()] if RFC_DIR.is_dir() else []
        if restos:
            reportar_error(f"RFC no quedó vacío (posible bloqueo): {restos}. Reintenta tras cerrar el daemon IPFS.")
        else:
            informar(f"Contenido eliminado de: {RFC_DIR}")
            try:
                from .stm_registro import publicar_registro_actualizar
                publicar_registro_actualizar({
                    "origen": str(origen), "destino": str(destino),
                    "ficheros": n_destino, "purgadas": purgadas})
            except Exception as error_pub:
                advertir(f"No se pudo publicar el registro ({error_pub}).")
    except OSError as error:
        reportar_error(f"Error al actualizar: {error}")

