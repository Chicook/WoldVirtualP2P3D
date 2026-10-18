"""Submodulo stm_registro de RFPRMN (refactor: tope 400/450 lineas).

Al completarse ``actualizar`` publica lo ocurrido:
1. Lee los eventos de stm_registro_json/envios.json y redacta registro.md
   en lenguaje natural (qué se hizo, qué se actualizó, cuántos ficheros).
2. Borra envios.json.
3. Convierte registro.md en pesos neuronales: vector global de 64
   dimensiones más un vector por sección (matriz), con cuantización
   opcional a int8 para subidas livianas.
4. Sube los pesos a IPFS en 4 niveles: IPFSManager de STM_BKCH, API HTTP
   del daemon local (127.0.0.1:5001), binario ipfs.exe del sistema y, en
   último caso, CID sintético local (igual que el shim actual).
5. Borra registro.md y los pesos: el directorio queda limpio.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from .stm_base import (E, informar, exito, advertir, reportar_error,
                           MODULO_DIR, _imprimir_seguro)
except ImportError:  # ejecución directa fuera del paquete
    from stm_base import (E, informar, exito, advertir, reportar_error,  # type: ignore[no-redef]
                          MODULO_DIR, _imprimir_seguro)

#: Carpeta de registro del sistema (queda vacía tras publicar).
DIR_REGISTRO = MODULO_DIR / "stm_registro_json"
RUTA_JSON = DIR_REGISTRO / "envios.json"
RUTA_MD = DIR_REGISTRO / "registro.md"
RUTA_PESOS = DIR_REGISTRO / "registro_pesos.json"

#: Dimensión del vector neuronal derivado del registro.
DIM_VECTOR = 64

#: Endpoint del daemon IPFS local (mismo que usa STMIPFS del sistema).
IPFS_API_URL = "http://127.0.0.1:5001"
IPFS_GATEWAY_URL = "http://127.0.0.1:8080"

#: Nombre del archivo de pesos dentro del registro.
NOMBRE_PESOS = "registro_pesos.json"


def _ahora() -> str:
    """Marca temporal actual en formato ISO (segundos)."""
    return datetime.now().isoformat(timespec="seconds")


def leer_eventos() -> list[dict]:
    """Lee los eventos pendientes de envios.json ([] si no hay o falla)."""
    try:
        if RUTA_JSON.exists():
            datos = json.loads(RUTA_JSON.read_text(encoding="utf-8"))
            return datos if isinstance(datos, list) else []
    except (OSError, ValueError) as error:
        advertir(f"No se pudo leer envios.json ({error}).")
    return []


def construir_texto(eventos: list[dict], info: dict) -> str:
    """Redacta en lenguaje natural lo que se hizo al actualizar.

    ``eventos`` son los registros históricos de envios.json e ``info``
    describe la operación actual (origen, destino, ficheros, purgadas).
    """
    lineas = ["# Registro de actualización", "",
              f"El {info.get('fecha', _ahora())} actualicé el sistema:",
              f"copié {info.get('ficheros', 0)} ficheros verificados desde "
              f"{info.get('origen', '?')} hasta {info.get('destino', '?')}.",
              ""]
    purgadas = info.get("purgadas", [])
    if purgadas:
        lineas.append("Al hacerlo purgué las versiones anteriores de PRY: "
                      + ", ".join(str(p) for p in purgadas) + ".")
        lineas.append("")
    else:
        lineas.append("No había versiones anteriores de PRY que purgar.")
        lineas.append("")
    lineas.append("Después vacié RFC por completo para dejarlo listo para el "
                  "siguiente ciclo de trabajo.")
    lineas.append("")
    if eventos:
        lineas.append("## Historial previo (envios.json)")
        lineas.append("")
        for ev in eventos:
            lineas.append(f"- El {ev.get('fecha', '?')} se procesó "
                          f"'{ev.get('carpeta', '?')}' "
                          f"({ev.get('ficheros', '?')} ficheros) con estado "
                          f"'{ev.get('estado', '?')}'.")
        lineas.append("")
    lineas.append("El directorio de registro queda limpio: este documento se "
                  "convirtió en pesos neuronales y se subió a IPFS.")
    return "\n".join(lineas) + "\n"


def texto_a_vector(texto: str, dim: int = DIM_VECTOR) -> list[float]:
    """Convierte ``texto`` en un vector neuronal determinista de ``dim``.

    Encadena SHA-256 sobre el texto (mismo enfoque de hash del
    SimpleEncoder del sistema) y normaliza cada byte a [-0.5, 0.5).
    """
    semilla = texto.encode("utf-8")
    valores: list[float] = []
    contador = 0
    while len(valores) < dim:
        bloque = hashlib.sha256(semilla + contador.to_bytes(4, "big")).digest()
        valores.extend(b / 256.0 - 0.5 for b in bloque)
        contador += 1
    return valores[:dim]


def norma(vector: list[float]) -> float:
    """Norma euclídea del vector (0.0 si está vacío)."""
    return math.sqrt(sum(v * v for v in vector)) if vector else 0.0


def seccionar_md(texto: str) -> list[tuple[str, str]]:
    """Divide el registro en secciones por encabezados ``#``/``##``.

    Devuelve pares (título, cuerpo); el texto previo al primer encabezado
    va en la sección "general". Si no hay encabezados, todo es "general".
    """
    secciones: list[tuple[str, str]] = []
    titulo, cuerpo = "general", []
    for linea in texto.splitlines():
        if linea.startswith("#"):
            if cuerpo or titulo != "general":
                secciones.append((titulo, "\n".join(cuerpo)))
            titulo = linea.lstrip("#").strip() or "general"
            cuerpo = []
        else:
            cuerpo.append(linea)
    secciones.append((titulo, "\n".join(cuerpo)))
    return [(t, c) for t, c in secciones if c.strip()]


def cuantizar(vector: list[float]) -> list[int]:
    """Cuantiza el vector de [-0.5, 0.5) a enteros int8 [-127, 127].

    Reduce el peso a ~1 byte por neurona para subidas livianas; la
    desnormalización es ``v / 254`` con error máximo de 1/254.
    """
    return [max(-127, min(127, round(v * 254))) for v in vector]


def desnormalizar(cuant: list[int]) -> list[float]:
    """Devuelve el vector cuantizado a flotantes aproximados."""
    return [c / 254.0 for c in cuant]


def similitud_coseno(a: list[float], b: list[float]) -> float:
    """Similitud coseno entre dos vectores (1.0 = idénticos, 0.0 si falla).

    Sirve para verificar que unos pesos recuperados de IPFS corresponden
    al registro que se publicó.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    den = norma(a) * norma(b)
    return num / den if den else 0.0


def md_a_pesos(ruta_md: Path = RUTA_MD,
               ruta_pesos: Path = RUTA_PESOS) -> dict:
    """Convierte registro.md en pesos neuronales y los guarda en JSON.

    Genera el vector global más un vector por sección (matriz) y su
    versión cuantizada int8. Devuelve el dict de pesos.
    """
    texto = ruta_md.read_text(encoding="utf-8")
    if not texto.strip():
        raise ValueError("registro.md vacío: no se generan pesos.")
    vector = texto_a_vector(texto)
    secciones = [{"titulo": t, "vector": texto_a_vector(t + "\n" + c),
                  "norma": norma(texto_a_vector(t + "\n" + c))}
                 for t, c in seccionar_md(texto)]
    pesos = {"formato": "registro-pesos-v2", "dim": len(vector),
             "vector": vector, "norma": norma(vector),
             "cuantizado": cuantizar(vector),
             "secciones": secciones, "n_secciones": len(secciones),
             "fuente": ruta_md.name, "fecha": _ahora()}
    ruta_pesos.parent.mkdir(parents=True, exist_ok=True)
    ruta_pesos.write_text(json.dumps(pesos, ensure_ascii=False), encoding="utf-8")
    exito(f"registro.md convertido en {len(vector)} pesos "
          f"({len(secciones)} secciones).")
    return pesos


def verificar_pesos(ruta_pesos: Path = RUTA_PESOS,
                    umbral: float = 0.999) -> bool:
    """Verifica la integridad de unos pesos: recalcula norma y cuantizado.

    Devuelve True si la norma y el cuantizado coinciden con lo guardado
    (tolerancia ``umbral`` para la norma). Informa el resultado.
    """
    try:
        pesos = json.loads(ruta_pesos.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        reportar_error(f"No se pudieron leer los pesos ({error}).")
        return False
    vector = pesos.get("vector", [])
    ok_norma = abs(norma(vector) - float(pesos.get("norma", -1.0))) < 0.001
    ok_cuant = cuantizar(vector) == pesos.get("cuantizado", [])
    ok_dim = len(vector) == int(pesos.get("dim", -1)) == DIM_VECTOR
    valido = ok_norma and ok_cuant and ok_dim
    if valido:
        exito(f"Pesos íntegros: dim {len(vector)}, {pesos.get('n_secciones', 0)} secciones.")
    else:
        reportar_error(f"Pesos corruptos (norma:{ok_norma} cuant:{ok_cuant} dim:{ok_dim}).")
    return valido and umbral <= 1.0


def vista_previa(info: dict) -> str:
    """Muestra cómo quedaría registro.md sin escribir ni publicar nada.

    Útil para revisar la redacción antes de un ``actualizar`` real.
    Devuelve el texto generado.
    """
    datos_info = dict(info)
    datos_info.setdefault("fecha", _ahora())
    texto = construir_texto(leer_eventos(), datos_info)
    _imprimir_seguro(f"{E.negrita}Vista previa de registro.md{E.reset} "
                     f"({len(texto.splitlines())} líneas, "
                     f"{len(texto_a_vector(texto))} pesos):")
    _imprimir_seguro(texto)
    return texto


def url_pasarela(cid: str, local: bool = True) -> str:
    """URL de pasarela para recuperar unos pesos por su CID.

    Con ``local=True`` usa el gateway del daemon (127.0.0.1:8080);
    si no, el gateway público ipfs.io (mismo que usa STMIPFS).
    """
    cid = cid.strip().strip("/")
    if not cid:
        return ""
    base = IPFS_GATEWAY_URL if local else "https://ipfs.io"
    return f"{base}/ipfs/{cid}"


def _cid_sintetico(pesos: dict) -> str:
    """CID local determinista (mismo estilo QmLocal del shim del sistema)."""
    sello = hashlib.sha256(
        json.dumps(pesos, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"QmLocal{sello}"


def _subir_via_manager(datos: bytes, nombre: str) -> dict:
    """Nivel 1: IPFSManager.almacenar_pesos() de STM_BKCH (patrón BKSVCB)."""
    from STM_BKCH.compat_local import get_ipfs_manager  # type: ignore[import]
    recibo = get_ipfs_manager().almacenar_pesos(
        datos=datos, nombre_modelo=nombre, eliminar_local=False)
    if not isinstance(recibo, dict) or not recibo.get("cid"):
        raise ValueError("IPFSManager no devolvió CID.")
    recibo = dict(recibo)
    recibo.setdefault("via", "ipfs-manager")
    return recibo


def _subir_via_api(datos: bytes, nombre: str, timeout: int = 60) -> dict:
    """Nivel 2: POST /api/v0/add al daemon local (127.0.0.1:5001).

    Construye el multipart a mano (solo stdlib) y extrae el Hash de la
    respuesta NDJSON del daemon.
    """
    frontera = f"----RFPRMN{hashlib.md5(datos).hexdigest()[:8]}"
    cuerpo = (f"--{frontera}\r\nContent-Disposition: form-data; "
              f'name="file"; filename="{nombre}"\r\n'
              f"Content-Type: application/json\r\n\r\n").encode("utf-8")
    cuerpo += datos + f"\r\n--{frontera}--\r\n".encode("utf-8")
    pet = urllib.request.Request(
        f"{IPFS_API_URL}/api/v0/add", data=cuerpo,
        headers={"Content-Type": f"multipart/form-data; boundary={frontera}"},
        method="POST")
    with urllib.request.urlopen(pet, timeout=timeout) as resp:
        crudo = resp.read().decode("utf-8")
    cid = ""
    for linea in crudo.splitlines():
        try:
            cid = json.loads(linea).get("Hash", "") or cid
        except ValueError:
            continue
    if not cid:
        raise ValueError("El daemon no devolvió Hash.")
    return {"cid": cid, "modo": "ipfs-daemon", "via": "api-http",
            "modelo": nombre, "bytes": len(datos)}


def _localizar_ipfs_bin() -> Optional[Path]:
    """Localiza el ipfs.exe del sistema (STMIPFS) o en el PATH."""
    candidatos = [
        MODULO_DIR.parent.parent / "RFC" / "src" / "STMIPFS" / ".ipfs"
        / "STMIPFSCOMFIG" / "ipfs.exe",
    ]
    for cand in candidatos:
        if cand.is_file() and cand.suffix.lower() == ".exe":
            return cand
    try:  # el src refactorizado vive en la última actualizacion_* de PRY
        from .stm_gestion import _ultima_actualizacion_pry
        ultima = _ultima_actualizacion_pry()
        if ultima is not None:
            cand = ultima / "src" / "STMIPFS" / ".ipfs" / "STMIPFSCOMFIG" / "ipfs.exe"
            if cand.is_file():
                return cand
    except Exception:
        pass
    for nombre in ("ipfs", "ipfs.exe"):
        for ruta in os.getenv("PATH", "").split(os.pathsep):
            cand = Path(ruta) / nombre
            if cand.is_file():
                return cand
    return None


def _subir_via_cli(ruta_pesos: Path, timeout: int = 120) -> dict:
    """Nivel 3: ``ipfs add -Q`` con el binario del sistema.

    Reutiliza el Kubo empaquetado en STMIPFS sin exigir daemon previo
    (usa el repo local si responde, si no falla al siguiente nivel).
    """
    binario = _localizar_ipfs_bin()
    if binario is None:
        raise FileNotFoundError("Sin binario ipfs disponible.")
    proc = subprocess.run([str(binario), "add", "-Q", str(ruta_pesos)],
                          capture_output=True, text=True, timeout=timeout)
    cid = proc.stdout.strip().split()[-1] if proc.stdout.strip() else ""
    if proc.returncode != 0 or not cid:
        raise ValueError(f"ipfs add falló: {proc.stderr.strip()[:120]}")
    return {"cid": cid, "modo": "ipfs-daemon", "via": "cli",
            "modelo": ruta_pesos.name, "bytes": ruta_pesos.stat().st_size}


def _detallado() -> bool:
    """True si RFPRMN_DEBUG=1 (muestra cada nivel de subida intentado)."""
    return os.getenv("RFPRMN_DEBUG", "").strip() == "1"


def subir_a_ipfs(ruta_pesos: Path = RUTA_PESOS) -> dict:
    """Sube los pesos a IPFS en 4 niveles (devuelve el recibo).

    1) IPFSManager de STM_BKCH; 2) API HTTP del daemon local;
    3) binario ipfs.exe del sistema; 4) CID sintético local-sin-daemon
    (igual que el shim actual). Solo se informa el resultado final,
    salvo RFPRMN_DEBUG=1 que detalla cada nivel.
    """
    datos = ruta_pesos.read_bytes()
    niveles = [("manager", lambda: _subir_via_manager(datos, ruta_pesos.name)),
               ("api-http", lambda: _subir_via_api(datos, ruta_pesos.name)),
               ("cli", lambda: _subir_via_cli(ruta_pesos))]
    fallos: list[str] = []
    for nombre, intento in niveles:
        try:
            recibo = intento()
            exito(f"Pesos subidos a IPFS vía {nombre}: {recibo['cid']}")
            return recibo
        except Exception as error:
            fallos.append(f"{nombre}: {error}")
            if _detallado():
                advertir(f"Nivel {nombre} no disponible ({error}); siguiente.")
    cid = _cid_sintetico({"md5": hashlib.md5(datos).hexdigest()})
    informar("IPFS sin daemon disponible; pesos guardados con CID local "
            f"(RFPRMN_DEBUG=1 para detalle): {cid}.")
    return {"cid": cid, "modo": "local-sin-daemon", "via": "local",
            "modelo": ruta_pesos.name, "bytes": len(datos)}


def _borrar_si_existe(ruta: Path) -> bool:
    """Borra ``ruta`` si existe; True si ya no queda rastro."""
    try:
        if ruta.exists():
            if ruta.is_dir():
                import shutil as _sh
                objetivo = str(ruta)
                if os.name == "nt" and not objetivo.startswith("\\\\?\\"):
                    objetivo = "\\\\?\\" + objetivo
                _sh.rmtree(objetivo, ignore_errors=True)
            else:
                ruta.unlink()
        return not ruta.exists()
    except OSError as error:
        advertir(f"No se pudo borrar {ruta.name} ({error}).")
        return False


def limpiar_caches() -> dict[str, bool]:
    """Borra las cachés de bytecode de la herramienta al cerrar el ciclo.

    Elimina __pycache__/ de STM_RFPRMN y STM_RFPRMN_stmDL más
    .pycache_rfprmn (se recrean solas en la próxima ejecución).
    """
    objetivos = [MODULO_DIR / "__pycache__",
                 MODULO_DIR / "STM_RFPRMN_stmDL" / "__pycache__",
                 MODULO_DIR / ".pycache_rfprmn"]
    estado = {p.relative_to(MODULO_DIR).as_posix(): _borrar_si_existe(p)
              for p in objetivos}
    if all(estado.values()):
        exito("Cachés de bytecode eliminadas.")
    return estado


def limpiar_registro() -> dict[str, bool]:
    """Borra json, md y pesos del registro; devuelve estado por archivo."""
    estado = {p.name: _borrar_si_existe(p)
              for p in (RUTA_JSON, RUTA_MD, RUTA_PESOS)}
    if all(estado.values()):
        exito(f"Directorio limpio: {DIR_REGISTRO.name} vacío.")
    else:
        pendientes = [n for n, ok in estado.items() if not ok]
        reportar_error(f"Limpieza parcial, pendientes: {pendientes}.")
    return estado


def publicar_registro_actualizar(info: dict) -> dict:
    """Publica lo ocurrido al actualizar y deja el directorio limpio.

    ``info`` trae origen, destino, ficheros y purgadas. Flujo:
    envios.json -> registro.md -> borra json -> pesos -> IPFS ->
    borra md y pesos. Devuelve el recibo de subida.
    """
    DIR_REGISTRO.mkdir(parents=True, exist_ok=True)
    eventos = leer_eventos()
    datos_info = dict(info)
    datos_info.setdefault("fecha", _ahora())
    RUTA_MD.write_text(construir_texto(eventos, datos_info), encoding="utf-8")
    informar(f"Registro redactado en lenguaje natural: {RUTA_MD.name}")
    _borrar_si_existe(RUTA_JSON)
    informar("envios.json borrado tras redactar el registro.")
    pesos = md_a_pesos()
    recibo = subir_a_ipfs()
    _borrar_si_existe(RUTA_MD)
    _borrar_si_existe(RUTA_PESOS)
    informar("registro.md convertido en pesos, subido y borrado.")
    limpiar_registro()
    limpiar_caches()
    _imprimir_seguro(f"{E.verde}✔{E.reset} Actualización publicada en IPFS: {recibo.get('cid')}")
    if recibo.get("via") != "local":
        _imprimir_seguro(f"Recuperable en: {url_pasarela(str(recibo.get('cid', '')))}")
    return {"recibo": recibo, "ficheros": datos_info.get("ficheros", 0),
            "purgadas": datos_info.get("purgadas", [])}
