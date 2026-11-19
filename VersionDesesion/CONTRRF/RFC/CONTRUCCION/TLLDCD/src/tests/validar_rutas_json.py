#!/usr/bin/env python3
"""Validador de Rutas.json — tarea R1.1 del plan de refactorizacion.

Comprueba que cada ruta del mapa canonico existe realmente en disco:

  - subsistemas (raiz, seccion, secciones) -> obligatorio (directorio)
  - archivos dentro de src/                -> obligatorio (archivo)
  - archivos externos (rutas ../../...)    -> aviso (arbol fuera de este taller)
  - runtime y pythonpath                   -> aviso (se generan o resuelven al ejecutar)

Uso:
    python tests/validar_rutas_json.py [ruta_alternativa_a_Rutas.json]

Codigo de salida: 0 si no hay faltas obligatorias; 1 en caso contrario.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OK, FALTA, AVISO = "OK    ", "FALTA ", "AVISO "


def main() -> int:
    ruta_json = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parent.parent / "Rutas.json"
    )
    if not ruta_json.is_file():
        print(f"No se encontro {ruta_json}")
        return 1

    base = ruta_json.parent
    datos = json.loads(ruta_json.read_text(encoding="utf-8-sig"))
    print(f"== Validador de Rutas.json (version {datos.get('version', '?')}) ==")
    print(f"Base: {base}\n")

    faltas = 0
    avisos = 0
    total = 0

    def etiqueta(existe: bool, obligatorio: bool) -> str:
        nonlocal faltas, avisos
        if existe:
            return OK
        if obligatorio:
            faltas += 1
            return FALTA
        avisos += 1
        return AVISO

    def chequear(ruta: str, obligatorio: bool, modo: str, nota: str = "") -> None:
        nonlocal total
        total += 1
        destino = (base / ruta).resolve()
        if modo == "archivo":
            existe = destino.is_file()
        elif modo == "directorio":
            existe = destino.is_dir()
        else:
            existe = destino.exists()
        print(f"{etiqueta(existe, obligatorio)} {ruta}{nota}")

    print("-- subsistemas (obligatorio) --")
    for nombre, info in datos.get("subsistemas", {}).items():
        chequear(info["raiz"], True, "directorio", f"  ({nombre}/raiz)")
        if "seccion" in info:
            chequear(info["seccion"], True, "directorio", f"  ({nombre}/seccion)")
        for clave, ruta in info.get("secciones", {}).items():
            chequear(ruta, True, "directorio", f"  ({nombre}/{clave})")

    print("\n-- archivos (obligatorio dentro de src; aviso si es externo) --")
    for clave, ruta in datos.get("archivos", {}).items():
        externo = ruta.startswith("..")
        nota = "  (externo)" if externo else f"  ({clave})"
        chequear(ruta, not externo, "archivo", nota)

    print("\n-- runtime (aviso si falta: se genera al ejecutar) --")
    for clave, ruta in datos.get("runtime", {}).items():
        chequear(ruta, False, "cualquiera", f"  ({clave})")

    print("\n-- pythonpath (aviso si falta) --")
    for ruta in datos.get("pythonpath", []):
        chequear(ruta, False, "directorio")

    print("\n== Resumen ==")
    print(f"Comprobaciones: {total} | Faltas obligatorias: {faltas} | Avisos: {avisos}")
    if faltas:
        print("Resultado: CON FALTAS")
        return 1
    print("Resultado: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
