"""Consola de STM_HRTS: rutas, verificacion y herramientas del arbol.

    python -m STM_HRTS rutas
    python -m STM_HRTS verificar
    python -m STM_HRTS herramientas
    python -m STM_HRTS ejecutar probar_construccion
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # ejecucion directa del fichero
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from STM_HRTS import herramientas, rutas


def _cmd_rutas(args: argparse.Namespace) -> int:
    datos = rutas.como_diccionario()
    if args.json:
        print(json.dumps(datos, indent=2, ensure_ascii=False))
        return 0
    ancho = max(len(nombre) for nombre in datos)
    for nombre, ruta in datos.items():
        marca = "ok " if Path(ruta).exists() else "FALTA"
        print(f"{marca:5} {nombre:<{ancho}}  {ruta}")
    return 0


def _cmd_verificar(args: argparse.Namespace) -> int:
    informe = rutas.verificar()
    faltan = rutas.faltantes(informe)
    if args.json:
        print(json.dumps(informe, indent=2, ensure_ascii=False))
    else:
        for fila in informe:
            marca = "ok " if fila["existe"] else "FALTA"
            print(f"{marca:5} {fila['nombre']:<22} {fila['ruta']}")
        print(f"\n{len(informe) - len(faltan)}/{len(informe)} rutas presentes")
    return 0 if not faltan else 1


def _cmd_herramientas(args: argparse.Namespace) -> int:
    lista = herramientas.catalogo()
    if args.json:
        print(json.dumps([
            {"nombre": h.nombre, "tipo": h.tipo, "headless": h.headless,
             "archivo": h.relativa, "resumen": h.resumen}
            for h in lista
        ], indent=2, ensure_ascii=False))
        return 0
    ancho = max((len(h.nombre) for h in lista), default=10)
    for h in lista:
        modo = "headless" if h.headless else "ventana "
        print(f"{h.nombre:<{ancho}}  {h.tipo:<10} {modo}  {h.resumen}")
    print(f"\n{len(lista)} herramientas en {rutas.HERRAMIENTAS_DIR}")
    return 0


def _cmd_ejecutar(args: argparse.Namespace) -> int:
    try:
        return herramientas.ejecutar(args.nombre, args.extra)
    except herramientas.ErrorHerramienta as exc:
        print(f"[STM_HRTS] {exc}", file=sys.stderr)
        return 2


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m STM_HRTS",
        description="Rutas y herramientas del arbol WoldVirtualP2P3D.",
    )
    sub = parser.add_subparsers(dest="orden", required=True)

    p_rutas = sub.add_parser("rutas", help="muestra las rutas clave")
    p_rutas.add_argument("--json", action="store_true")
    p_rutas.set_defaults(func=_cmd_rutas)

    p_ver = sub.add_parser("verificar", help="comprueba que las rutas existen")
    p_ver.add_argument("--json", action="store_true")
    p_ver.set_defaults(func=_cmd_verificar)

    p_herr = sub.add_parser("herramientas", help="lista las herramientas de utils/")
    p_herr.add_argument("--json", action="store_true")
    p_herr.set_defaults(func=_cmd_herramientas)

    p_ejec = sub.add_parser("ejecutar", help="lanza una herramienta de utils/")
    p_ejec.add_argument("nombre")
    p_ejec.add_argument("extra", nargs=argparse.REMAINDER)
    p_ejec.set_defaults(func=_cmd_ejecutar)
    return parser


def _configurar_salida() -> None:
    """Salida UTF-8 al redirigir; en consola se respeta el codepage nativo."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            if flujo.isatty():
                continue
            codificacion = (flujo.encoding or "").lower().replace("-", "")
            if codificacion != "utf8":
                flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _configurar_salida()
    args = construir_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
