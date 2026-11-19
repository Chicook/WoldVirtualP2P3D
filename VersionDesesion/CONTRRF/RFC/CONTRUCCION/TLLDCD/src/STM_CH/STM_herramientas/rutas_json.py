"""Carga y resuelve las rutas declaradas en ``src/Rutas.json``.

``Rutas.json`` es la fuente única de rutas del taller. Las rutas del JSON son
relativas al propio archivo, de modo que el árbol se puede mover o clonar sin
editar el código fuente.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

RUTAS_JSON: Path = Path(__file__).resolve().parents[2] / "Rutas.json"
BASE: Path = RUTAS_JSON.parent

_CACHE: Dict[str, Any] | None = None


def cargar(forzar: bool = False) -> Dict[str, Any]:
    """Devuelve el contenido de ``Rutas.json`` (cacheado)."""
    global _CACHE
    if _CACHE is None or forzar:
        with RUTAS_JSON.open("r", encoding="utf-8") as archivo:
            _CACHE = json.load(archivo)
    return _CACHE


def resolver(valor: str | Path, base: Path | None = None) -> Path:
    """Resuelve una ruta relativa contra la carpeta de ``Rutas.json``."""
    ruta = Path(str(valor))
    if ruta.is_absolute():
        return ruta
    return ((base or BASE) / ruta).resolve()


def obtener(clave: str, datos: Dict[str, Any] | None = None) -> Path:
    """Resuelve una clave con puntos, por ejemplo ``archivos.mainLCSTM``."""
    actual: Any = datos if datos is not None else cargar()
    for parte in clave.split("."):
        if not isinstance(actual, dict) or parte not in actual:
            raise KeyError(f"Ruta no declarada en Rutas.json: {clave}")
        actual = actual[parte]
    if isinstance(actual, dict):
        for nombre in ("ruta", "raiz", "seccion"):
            if nombre in actual:
                actual = actual[nombre]
                break
        else:
            raise KeyError(f"La clave {clave} no contiene una ruta")
    return resolver(actual)


def _iterar_rutas(nodo: Any, prefijo: str = "") -> Iterator[Tuple[str, str]]:
    """Recorre el JSON y devuelve (clave, ruta) de los nodos de ruta."""
    if isinstance(nodo, dict):
        for nombre in ("ruta", "raiz", "seccion"):
            if nombre in nodo:
                yield prefijo, str(nodo[nombre])
                break
        for clave, valor in nodo.items():
            if clave in ("ruta", "raiz", "seccion"):
                continue
            subprefijo = f"{prefijo}.{clave}" if prefijo else clave
            yield from _iterar_rutas(valor, subprefijo)
    elif isinstance(nodo, list):
        for indice, valor in enumerate(nodo):
            yield from _iterar_rutas(valor, f"{prefijo}[{indice}]")
    elif isinstance(nodo, str) and prefijo.startswith(
            ("raices", "subsistemas", "archivos", "pythonpath")):
        yield prefijo, nodo


#: Carpetas que pueden no existir en un clon limpio (datos/runtime).
OPCIONALES = {
    "subsistemas.SBSTM.secciones.tts_models",
    "subsistemas.STM_CH.secciones.pycache",
}


def validar(incluir_runtime: bool = False,
            datos: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Comprueba que existan las rutas de código declaradas en el JSON."""
    contenido = datos if datos is not None else cargar()
    revisadas = 0
    faltan: list[Dict[str, str]] = []
    for clave, valor in _iterar_rutas(contenido):
        if clave in OPCIONALES:
            continue
        if not incluir_runtime and clave.startswith("runtime."):
            continue
        revisadas += 1
        ruta = resolver(valor)
        if not ruta.exists():
            faltan.append({"clave": clave, "ruta": str(ruta)})
    return {"ok": not faltan, "revisadas": revisadas, "faltan": faltan,
            "archivo": str(RUTAS_JSON)}


def main() -> int:
    """Valida Rutas.json y muestra el resultado por terminal."""
    informe = validar(incluir_runtime="--runtime" in __import__("sys").argv)
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    return 0 if informe["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
