"""Re-mide la matriz de modos de la puerta headless (arbol frente a PCK).

La tabla `PCK_OBLIGATORIO` de `herramientas.py` no se deduce del contenido del
guion: se midio el 2026-11-05 y hay que poder volver a medirla. Lanza cada prueba
con veredicto dos veces —una desde el arbol y otra con `--main-pack`— y escribe el
resultado en JSON, ademas de irlo imprimiendo por linea.

    python tests/godot/medicion_modos.py                 # los dos modos
    python tests/godot/medicion_modos.py --timeout 90    # techo por guion
    python tests/godot/medicion_modos.py --solo arbol

Sale 0 siempre que la matriz se haya escrito, aunque habra pruebas rojas: aqui el
interes es la medicion, no el veredicto (la puerta con veredicto es
`test_headless.py`). Coste medido: ~4 min para los dos modos en esta maquina,
dominados por los techos de timeout de los guiones que se cuelgan.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

SRC_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from STM_HRTS.utils.add_utils import herramientas, rutas  # noqa: E402

# Los argumentos documentados de cada guion viven en la puerta: reutilizarlos
# evita medir `probar_red_invitacion` sin su `--peer-url` y anotarlo luego como
# si fuera un fallo del arbol.
from test_headless import ARGUMENTOS  # noqa: E402

# `SCRIPT ERROR` y los `Parse Error` de codigo; los de `[ext_resource]` son la
# falta de `.godot/imported` y son justo lo que se quiere medir.
ERROR_DE_CODIGO = re.compile(r"SCRIPT ERROR:|Parse Error:")
VEREDICTO = re.compile(r"fallo", re.IGNORECASE)


def _candidatos() -> List[Path]:
    return [
        h.archivo for h in herramientas.catalogo()
        if h.tipo == "godot" and h.headless and herramientas.emite_veredicto(h.archivo)
    ]


def _medir(archivo: Path, modo: str, entorno: Dict[str, str], timeout: float) -> Dict[str, object]:
    argv = [str(rutas.binario_godot()), "--path", str(rutas.GODOT_DIR)]
    if modo == herramientas.MODO_PCK:
        if not rutas.PCK_EMBEBIDO.is_file():
            return {"script": archivo.stem, "modo": modo, "estado": "SIN PCK"}
        argv.extend(["--main-pack", str(rutas.PCK_EMBEBIDO)])
    argv += ["--headless", "--script", str(archivo)]
    extra = ARGUMENTOS.get(archivo.stem, ())
    if extra:
        argv.append("--")
        argv.extend(extra)
    inicio = time.time()
    destino = rutas.USER_DATA_DIR / f"medicion_{archivo.stem}_{modo}.txt"
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(destino, "wb") as fp:
            codigo = subprocess.run(argv, cwd=str(rutas.SRC_DIR), env=entorno,
                                    stdout=fp, stderr=subprocess.STDOUT,
                                    timeout=timeout).returncode
        estado = "ok"
    except subprocess.TimeoutExpired:
        codigo, estado = None, "TIMEOUT"
    salida = destino.read_text(encoding="utf-8", errors="replace")
    lineas = salida.splitlines()
    return {
        "script": archivo.stem,
        "modo": modo,
        "estado": estado,
        "exit": codigo,
        "segundos": round(time.time() - inicio, 1),
        "declara_pck": archivo.stem in herramientas.PCK_OBLIGATORIO,
        "veredicto": next((l.strip() for l in reversed(lineas) if VEREDICTO.search(l)), None),
        "errores": len([l for l in lineas if ERROR_DE_CODIGO.search(l)]),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timeout", type=float, default=90.0, help="techo por guion (s)")
    parser.add_argument("--solo", choices=(herramientas.MODO_ARBOL, herramientas.MODO_PCK))
    parser.add_argument("--salida", type=Path,
                        default=rutas.USER_DATA_DIR / "matriz_modos.json")
    args = parser.parse_args(argv)

    modos = [args.solo] if args.solo else [herramientas.MODO_ARBOL, herramientas.MODO_PCK]
    entorno = herramientas.entorno_aislado()
    filas: List[Dict[str, object]] = []
    for archivo in _candidatos():
        for modo in modos:
            fila = _medir(archivo, modo, entorno, args.timeout)
            filas.append(fila)
            print(json.dumps(fila, ensure_ascii=False), flush=True)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(filas)} mediciones en {args.salida}")
    for fila in filas:
        declarado = fila["declara_pck"]
        verde = fila["estado"] == "ok" and fila["exit"] == 0
        if declarado and not verde:
            print(f"  {fila['script']}[{fila['modo']}] declarado PCK y sale {fila['estado']}/{fila['exit']}")
        if not declarado and not verde and fila["modo"] == herramientas.MODO_ARBOL:
            print(f"  {fila['script']}[arbol] falla desde el arbol: candidate a PCK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
