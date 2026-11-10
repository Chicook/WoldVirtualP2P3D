"""H0 — Genera el manifiesto SHA-256 de artefactos grandes del taller.

Objetivo: congelar la línea base antes de cualquier cambio.  Produce
``manifiesto_h0.json`` en la raíz de src con sha-256, tamaño en bytes y
rol de cada artefacto relevante.

Uso:
    python STM_HRTS/utils/generar_manifiesto_h0.py

El script es de solo-lectura: no modifica, mueve ni borra nada.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

# ------------------------------------------------------------------ rutas
SRC_DIR = Path(__file__).resolve().parents[2]
VSC_DIR = SRC_DIR / "VSC#"

# Artefactos conocidos por el README: rol, ruta relativa a SRC_DIR
ARTEFACTOS_FIJOS: List[Dict] = [
    {"rol": "pck_visor",       "rel": "VSC#/wvp3d.pck"},
    {"rol": "godot_exe_win",   "rel": "VSC#/godot_exe.zip"},
    {"rol": "godot_exe_linux", "rel": "VSC#/godot_linux.zip"},
]

# Extensiones binarias o de build que no son código fuente
EXTENSIONES_BINARIO = {
    ".exe", ".dll", ".so", ".dylib", ".zip", ".tar", ".gz",
    ".pck", ".wasm", ".npz", ".db", ".sqlite",
}

# Tamaño mínimo para incluir en el manifiesto ampliado (5 MiB)
_MIN_BYTES = 5 * 1024 * 1024


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            bloque = f.read(chunk)
            if not bloque:
                break
            h.update(bloque)
    return h.hexdigest()


def _rol_inferido(path: Path) -> str:
    suf = path.suffix.lower()
    if suf == ".pck":
        return "godot_pck"
    if suf in (".zip", ".tar", ".gz"):
        return "archivo_comprimido"
    if suf in (".exe", ".dll"):
        return "binario_windows"
    if suf in (".so", ".dylib"):
        return "binario_linux"
    if suf == ".npz":
        return "pesos_neuronales"
    return "binario_grande"


def inventariar_artefactos_fijos() -> List[Dict]:
    """Procesa los artefactos listados explícitamente en el README."""
    filas = []
    for entrada in ARTEFACTOS_FIJOS:
        ruta = SRC_DIR / entrada["rel"]
        fila: Dict = {
            "rol": entrada["rol"],
            "ruta": entrada["rel"],
            "existe": ruta.exists(),
        }
        if ruta.exists():
            fila["bytes"] = ruta.stat().st_size
            print(f"  SHA-256 {ruta.name} ...", end=" ", flush=True)
            fila["sha256"] = _sha256(ruta)
            print(fila["sha256"][:16] + "...")
        else:
            fila["bytes"] = 0
            fila["sha256"] = ""
            print(f"  [AUSENTE] {entrada['rel']}")
        filas.append(fila)
    return filas


def descubrir_binarios_grandes() -> List[Dict]:
    """Recorre src/ buscando binarios > MIN_BYTES no listados explícitamente."""
    fijos = {SRC_DIR / e["rel"] for e in ARTEFACTOS_FIJOS}
    filas = []
    try:
        for p in sorted(SRC_DIR.rglob("*")):
            if not p.is_file():
                continue
            if p in fijos:
                continue
            if p.suffix.lower() not in EXTENSIONES_BINARIO:
                continue
            try:
                tam = p.stat().st_size
            except OSError:
                continue
            if tam < _MIN_BYTES:
                continue
            rel = str(p.relative_to(SRC_DIR)).replace("\\", "/")
            print(f"  SHA-256 {p.name} ...", end=" ", flush=True)
            sha = _sha256(p)
            print(sha[:16] + "...")
            filas.append({
                "rol": _rol_inferido(p),
                "ruta": rel,
                "existe": True,
                "bytes": tam,
                "sha256": sha,
            })
    except Exception as exc:
        print(f"  [ADVERTENCIA] descubrir_binarios_grandes: {exc}")
    return filas


def contar_arbol() -> Dict:
    """Cuenta ficheros y bytes totales del árbol src/."""
    total_ficheros = 0
    total_bytes = 0
    try:
        for p in SRC_DIR.rglob("*"):
            if p.is_file():
                total_ficheros += 1
                try:
                    total_bytes += p.stat().st_size
                except OSError:
                    pass
    except Exception:
        pass
    return {"ficheros": total_ficheros, "bytes": total_bytes}


def main() -> int:
    print("\n=== H0 - Manifiesto de linea base ===")
    print(f"Raiz src: {SRC_DIR}\n")

    print("[*] Artefactos fijos (README s3.1 y s3.2):")
    fijos = inventariar_artefactos_fijos()

    print("\n[*] Binarios grandes adicionales (>5 MiB):")
    grandes = descubrir_binarios_grandes()

    print("\n[*] Estadisticas del arbol src/ ...")
    arbol = contar_arbol()
    print(f"  {arbol['ficheros']} ficheros, {arbol['bytes']:,} bytes")

    manifiesto = {
        "version": "H0",
        "fecha_generacion": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "src_dir": str(SRC_DIR),
        "arbol": arbol,
        "artefactos_fijos": fijos,
        "binarios_grandes": grandes,
        "notas": (
            "Manifiesto de solo lectura. No se modifico codigo ni se ejecutaron "
            "pruebas. SHA-256 calculado byte a byte. "
            "Criterio H0: con este manifiesto se puede responder "
            "'que cambio?' sin necesidad de preguntar."
        ),
    }

    salida = Path(__file__).resolve().parent.parent / "manifiesto_h0.json"
    salida.write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n[OK] Manifiesto guardado en: {salida}")
    print("  H0 cerrado: linea base congelada.\n")
    return 0



if __name__ == "__main__":
    sys.exit(main())
