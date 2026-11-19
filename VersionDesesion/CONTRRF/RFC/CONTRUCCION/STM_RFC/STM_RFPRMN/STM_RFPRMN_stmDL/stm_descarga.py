"""Descarga verificada de pesos GGUF para la IA local (issue #80/#81).

Sustituye a la descarga directa sobre el archivo final que dejaba modelos
truncados aceptados como completos. Reglas:

- Se escribe en ``<archivo>.part`` y solo se renombra a definitivo cuando el
  tamaño coincide con el del servidor o el GGUF está completo.
- Se reanuda con ``Range`` cuando hay un ``.part`` previo; si el servidor no
  admite rangos se reinicia sin romper nada.
- Se reintenta con espera creciente ante cortes de red.
- Se valida la cabecera mágica ``GGUF`` y un tamaño mínimo: un archivo cortado
  nunca pasa por bueno.
"""
from __future__ import annotations

import contextlib
import http.client
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .stm_base import ErrorProyecto, advertir, exito, informar, _imprimir_seguro

#: Bloque de lectura (4 MB: buen equilibrio entre progreso y memoria).
BLOQUE = 4 * 1024 * 1024
#: Tamaño mínimo aceptable para un GGUF de código (Q4 de 1.5B ronda 1 GB).
TAMANO_MINIMO_GGUF = 400 * 1024 * 1024
#: Reintentos ante corte de red.
REINTENTOS_DESCARGA = 3
#: Tiempo máximo de espera entre bloques.
TIMEOUT_BLOQUE = 60
#: Pausa base entre reintentos (crece de forma lineal).
ESPERA_REINTENTO = 1.5


def peso_gguf_valido(ruta: Path, minimo: int = TAMANO_MINIMO_GGUF) -> bool:
    """True si ``ruta`` parece un GGUF completo (cabecera mágica y tamaño)."""
    try:
        if not ruta.is_file() or ruta.stat().st_size < minimo:
            return False
        with open(ruta, "rb") as archivo:
            return archivo.read(4) == b"GGUF"
    except OSError:
        return False


def _total_esperado(respuesta, bajados: int) -> int:
    """Tamaño total del archivo según ``Content-Range`` o ``Content-Length``."""
    rango = respuesta.headers.get("Content-Range", "") or ""
    if "/" in rango:
        try:
            return int(rango.rsplit("/", 1)[1])
        except (ValueError, IndexError):
            pass
    try:
        largo = int(respuesta.headers.get("Content-Length", "0") or 0)
    except ValueError:
        return 0
    return (bajados + largo) if largo else 0


def _progreso(bajados: int, total: int, ultimo: list[int]) -> None:
    """Informa del avance cada 5 % (o cada 100 MB si no hay total)."""
    if total > 0:
        porcentaje = int(bajados * 100 / total)
        if porcentaje != ultimo[0] and (porcentaje % 5 == 0 or porcentaje == 100):
            ultimo[0] = porcentaje
            _imprimir_seguro(f"[DESCARGA] {bajados / 1048576:.1f}/"
                             f"{total / 1048576:.1f} MB ({porcentaje}%)")
    elif bajados // (100 * 1048576) > ultimo[0]:
        ultimo[0] = bajados // (100 * 1048576)
        _imprimir_seguro(f"[DESCARGA] {bajados / 1048576:.1f} MB...")


def descargar_gguf(repo: str, archivo: str, destino: Path,
                   minimo: int = TAMANO_MINIMO_GGUF,
                   reintentos: int = REINTENTOS_DESCARGA,
                   url: str | None = None) -> Path:
    """Descarga ``archivo`` de ``repo`` en ``destino`` y devuelve la ruta final.

    Lanza ``ErrorProyecto`` si tras ``reintentos`` no se consigue un archivo
    completo y verificado; el ``.part`` se conserva para reanudar más tarde.
    """
    carpeta = Path(destino)
    carpeta.mkdir(parents=True, exist_ok=True)
    final = carpeta / archivo
    parcial = final.with_name(final.name + ".part")

    if peso_gguf_valido(final, minimo):
        informar(f"Peso ya presente y verificado: {final} "
                 f"({final.stat().st_size} bytes)")
        return final
    if final.exists():
        advertir(f"{final.name} está incompleto o no es un GGUF válido; "
                 "se descarta y se vuelve a descargar.")
        with contextlib.suppress(OSError):
            final.unlink()

    enlace = url or f"https://huggingface.co/{repo}/resolve/main/{archivo}"
    _imprimir_seguro(f"[DESCARGA] {repo}/{archivo}")
    _imprimir_seguro(f"[DESCARGA] URL: {enlace}")
    _imprimir_seguro(f"[DESCARGA] Destino visible: {final}")

    ultimo_error: object = None
    for intento in range(1, reintentos + 1):
        bajados = parcial.stat().st_size if parcial.exists() else 0
        cabeceras = {"User-Agent": "WoldVirtualP2P3D", "Accept-Encoding": "identity"}
        if bajados:
            cabeceras["Range"] = f"bytes={bajados}-"
            _imprimir_seguro(f"[DESCARGA] Reanudando en {bajados / 1048576:.1f} MB "
                             f"(intento {intento}/{reintentos}).")
        peticion = urllib.request.Request(enlace, headers=cabeceras)
        total = 0
        try:
            with urllib.request.urlopen(peticion, timeout=TIMEOUT_BLOQUE) as respuesta:
                if bajados and getattr(respuesta, "status", 200) != 206:
                    _imprimir_seguro("[DESCARGA] El servidor no admite reanudación: "
                                     "se empieza de cero.")
                    bajados = 0
                    with contextlib.suppress(OSError):
                        parcial.unlink()
                total = _total_esperado(respuesta, bajados)
                if total:
                    _imprimir_seguro(f"[DESCARGA] Tamano total: "
                                     f"{total / 1048576:.1f} MB")
                ultimo = [-1]
                with open(parcial, "ab" if bajados else "wb") as salida:
                    while True:
                        bloque = respuesta.read(BLOQUE)
                        if not bloque:
                            break
                        salida.write(bloque)
                        bajados += len(bloque)
                        _progreso(bajados, total, ultimo)
                    salida.flush()
                    os.fsync(salida.fileno())
        except (urllib.error.URLError, http.client.HTTPException, OSError) as error:
            ultimo_error = error
            advertir(f"[DESCARGA] Corte en el intento {intento}: {error}")
            if intento < reintentos:
                time.sleep(ESPERA_REINTENTO * intento)
            continue

        tamano = parcial.stat().st_size if parcial.exists() else 0
        if total and tamano != total:
            ultimo_error = ErrorProyecto(f"tamaño {tamano} != {total} esperados")
            advertir(f"[DESCARGA] Descarga incompleta ({tamano}/{total} bytes).")
            if intento < reintentos:
                continue
            break
        if not peso_gguf_valido(parcial, minimo):
            ultimo_error = ErrorProyecto("el archivo no es un GGUF completo")
            advertir("[DESCARGA] El archivo descargado no es un GGUF válido.")
            with contextlib.suppress(OSError):
                parcial.unlink()
            break
        os.replace(parcial, final)
        exito(f"Modelo HF descargado: {final} ({final.stat().st_size} bytes)")
        return final

    raise ErrorProyecto(
        f"No se pudo descargar {archivo}: {ultimo_error or 'error desconocido'}. "
        f"Se conserva {parcial.name} para reanudar en el próximo intento.")
