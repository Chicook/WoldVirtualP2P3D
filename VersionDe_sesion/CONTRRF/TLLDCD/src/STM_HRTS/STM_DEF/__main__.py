"""Consola del subsistema defensivo STM_DEF.

    python STM_HRTS/STM_DEF/__main__.py informe
    python -m STM_HRTS.STM_DEF escanear
    python -m STM_HRTS.STM_DEF historial          (busca el dropper en commits)
    python -m STM_HRTS.STM_DEF blindar            (simula; no toca el sistema)
    python -m STM_HRTS.STM_DEF blindar --aplicar  (requiere administrador)
    python -m STM_HRTS.STM_DEF vigilar --resolver
    python -m STM_HRTS.STM_DEF sellar
    python -m STM_HRTS.STM_DEF integridad
    python -m STM_HRTS.STM_DEF cuarentena --ruta <fichero> [--motivo M]
    python -m STM_HRTS.STM_DEF cuarentena --listar
    python -m STM_HRTS.STM_DEF cuarentena --verificar
    python -m STM_HRTS.STM_DEF puerta                (paso bloqueante para CI)
    python -m STM_HRTS.STM_DEF arranque             (hook fail-closed de arranque)
    python -m STM_HRTS.STM_DEF servicio --ciclos 0   (vigilancia continua de salida)
    python -m STM_HRTS.STM_DEF firma --help          (firma Ed25519 de release)

Codigos de salida: 0 = limpio, 1 = hallazgos/alertas, 2 = error de uso.
"""
from __future__ import annotations

import utils.transport
import utils.session
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    # Ejecucion directa del fichero: ancla src/ y entra por el paquete real.
    for _padre in Path(__file__).resolve().parents:
        if _padre.joinpath("STM_HRTS", "utils", "add_utils").is_dir():
            sys.path.insert(0, str(_padre))
            break
    from STM_HRTS.STM_DEF import arranque, blindaje, firma_release, iocs, servicio  # noqa: E402
    from STM_HRTS.STM_DEF import SRC_DIR  # noqa: E402
    from STM_HRTS.STM_DEF.motor import MotorDefensa, alerta_a_diccionario, informe_a_diccionario  # noqa: E402
else:
    from . import arranque, blindaje, firma_release, iocs, servicio
    from . import SRC_DIR
    from .motor import MotorDefensa, alerta_a_diccionario, informe_a_diccionario


def _imprimir(datos: object, como_json: bool) -> None:
    if como_json:
        print(json.dumps(datos, indent=2, ensure_ascii=False))
    else:
        print(datos)


# ------------------------------------------------------------------ ordenes
def _cmd_iocs(args: argparse.Namespace) -> int:
    datos = {
        "carteras_c2": list(iocs.DIRECCIONES_C2),
        "dominios_c2": list(iocs.DOMINIOS_C2),
        "sufijos_rpc": list(iocs.SUFIJOS_RPC),
        "patrones": [
            {"id": p.id, "severidad": p.severidad, "descripcion": p.descripcion}
            for p in iocs.PATRONES
        ],
        "patrones_comando": [
            {"id": id_, "descripcion": desc} for id_, _, desc in iocs.PATRONES_COMANDO
        ],
        "nombres_camuflaje": list(iocs.NOMBRES_CAMUFLAJE),
    }
    if args.json:
        _imprimir(datos, True)
        return 0
    print(f"Carteras C2: {', '.join(datos['carteras_c2'])}")
    print(f"Dominios C2 : {', '.join(datos['dominios_c2'])}")
    print(f"RPC publicos: {', '.join(datos['sufijos_rpc'])}")
    print(f"Patrones    : {len(datos['patrones'])} de texto, {len(datos['patrones_comando'])} de comando")
    print(f"Camuflaje   : {', '.join(datos['nombres_camuflaje'])}")
    return 0


def _cmd_escanear(args: argparse.Namespace) -> int:
    raices = [Path(r) for r in args.rutas] if args.rutas else [SRC_DIR]
    informe = MotorDefensa(raices).escanear(raices)
    if args.json:
        _imprimir(informe_a_diccionario(informe), True)
    else:
        for hallazgo in informe.hallazgos:
            print(hallazgo.como_texto())
        print(f"\n{len(informe.hallazgos)} hallazgos | veredicto: {informe.veredicto()}")
    return 0 if not informe.hallazgos else 1


def _cmd_historial(args: argparse.Namespace) -> int:
    informe = MotorDefensa().escanear_historial(limite=args.limite)
    if args.json:
        _imprimir(informe_a_diccionario(informe), True)
    else:
        for hallazgo in informe.hallazgos:
            print(hallazgo.como_texto())
        print(f"\n{len(informe.hallazgos)} hallazgos en el historial | veredicto: {informe.veredicto()}")
    return 0 if not informe.hallazgos else 1


def _cmd_vigilar(args: argparse.Namespace) -> int:
    informe = MotorDefensa().vigilar(resolver=args.resolver, ciclos=args.ciclos, intervalo=args.intervalo)
    if args.json:
        _imprimir(informe_a_diccionario(informe), True)
    else:
        for alerta in informe.alertas:
            print(alerta.como_texto())
        print(f"\n{len(informe.alertas)} alertas de red")
    return 0 if not informe.alertas else 1


def _cmd_blindar(args: argparse.Namespace) -> int:
    resultado = MotorDefensa().blindar(aplicar=args.aplicar)
    if args.json:
        _imprimir(resultado, True)
    else:
        sinkhole = resultado["sinkhole"]
        firewall = resultado["firewall"]
        modo = "APLICADO" if (sinkhole.get("aplicado") or firewall.get("aplicado")) else "SIMULADO"
        print(f"Blindaje {modo} (admin: {blindaje.es_admin()})")
        print(f"  hosts       : {sinkhole['ruta']}  ({len(sinkhole['dominios'])} dominios)")
        if sinkhole.get("error"):
            print(f"  aviso       : {sinkhole['error']}")
        if not args.aplicar:
            print("  plan hosts  :")
            for linea in sinkhole["lineas"]:
                print(f"    {linea}")
            print(f"  reglas firewall previstas: {len(firewall['comandos'])}")
        else:
            print(f"  firewall    : {len(firewall.get('ejecutados', []))} reglas ejecutadas")
    return 0


def _cmd_sellar(args: argparse.Namespace) -> int:
    resultado = MotorDefensa().sellar()
    if args.json:
        _imprimir(resultado, True)
    else:
        print(f"Sello guardado en {resultado['ruta']} ({resultado['ficheros']} ficheros)")
    return 0


def _cmd_integridad(args: argparse.Namespace) -> int:
    resultado = MotorDefensa().verificar_integridad()
    if args.json:
        _imprimir(resultado, True)
    else:
        print(f"Firma del sello: {'valida' if resultado['firma_ok'] else 'INVALIDA'}")
        print(f"Arbol: {resultado['mensaje']}")
        for etiqueta in ("añadidos", "modificados", "borrados"):
            for ruta in resultado.get(etiqueta, []):
                print(f"  {etiqueta[:-1]}: {ruta}")
    return 0 if resultado.get("intacto") else 1


def _cmd_cuarentena(args: argparse.Namespace) -> int:
    motor = MotorDefensa()
    if args.verificar:
        resultado = motor.verificar_cuarentena()
        if args.json:
            _imprimir(resultado, True)
        else:
            print(f"Cuarentena: {resultado['total']} muestras | "
                  f"{'INTACTA' if resultado['intacto'] else 'ALTERADA'}")
            for etiqueta in ("alteradas", "ausentes"):
                for copia in resultado.get(etiqueta, []):
                    print(f"  {etiqueta[:-1]}: {copia}")
        return 0 if resultado.get("intacto") else 1
    if args.listar or not args.ruta:
        registros = motor.listar_cuarentena()
        if args.json:
            _imprimir(registros, True)
        else:
            for registro in registros:
                print(f"{registro['sha256'][:16]}  {registro['origen']}  ({registro['motivo'] or 's/motivo'})")
            print(f"\n{len(registros)} muestras en cuarentena")
        return 0
    for ruta in args.ruta:
        registro = motor.poner_en_cuarentena(Path(ruta), motivo=args.motivo)
        if args.json:
            _imprimir(registro, True)
        else:
            print(f"En cuarentena: {registro['copia']}  ({registro['sha256'][:16]})  origen intacto")
    return 0


def _cmd_puerta(args: argparse.Namespace) -> int:
    raices = [Path(r) for r in args.rutas] if args.rutas else None
    resultado = MotorDefensa(raices).puerta_seguridad(raices)
    if args.json:
        _imprimir(resultado, True)
    else:
        detalle = resultado["detalle"]
        escaneo = detalle["escanear"]
        integridad = detalle.get("integridad", {})
        cuarentena_estado = detalle.get("cuarentena", {})
        print(f"Escaneo    : {escaneo['hallazgos']} hallazgos | veredicto {escaneo['veredicto']}")
        print(f"Integridad : {integridad.get('mensaje', 'n/d')}")
        print(f"Cuarentena : {cuarentena_estado.get('total', 0)} muestras | "
              f"{'INTACTA' if cuarentena_estado.get('intacto') else 'ALTERADA'}")
        if resultado["bloquea"]:
            print("\nPUERTA: BLOQUEADA")
            for motivo in resultado["bloqueos"]:
                print(f"  - {motivo}")
        else:
            print("\nPUERTA: ABIERTA (sin bloqueos)")
    return 1 if resultado["bloquea"] else 0


def _cmd_arranque(args: argparse.Namespace) -> int:
    raices = [Path(r) for r in args.rutas] if args.rutas else None
    resultado = arranque.arranque_seguro(raices)
    if args.json:
        _imprimir(resultado, True)
    else:
        escaneo = resultado["detalle"]["escanear"]
        integridad_detalle = resultado["detalle"].get("integridad", {})
        print(f"Escaneo    : {escaneo['hallazgos']} hallazgos | veredicto {escaneo['veredicto']}")
        print(f"Integridad : {integridad_detalle.get('mensaje', 'n/d')}")
        if resultado["permite"]:
            print("\nARRANQUE: PERMITIDO")
        else:
            print("\nARRANQUE: DETENIDO (fail-closed)")
            for motivo in resultado["bloqueos"]:
                print(f"  - {motivo}")
    return 0 if resultado["permite"] else 1


def _cmd_servicio(args: argparse.Namespace) -> int:
    aviso = None if args.json else (lambda alerta: print(alerta.como_texto()))
    vigilante = servicio.ServicioVigilancia(
        intervalo=args.intervalo, resolver=args.resolver, callback=aviso,
    )
    try:
        vigilante.ejecutar(ciclos=args.ciclos)
    except KeyboardInterrupt:
        vigilante.detener()
        print()
    if args.json:
        _imprimir({"resumen": vigilante.resumen(),
                   "alertas": [alerta_a_diccionario(a) for a in vigilante.alertas]}, True)
    else:
        print(f"\n{vigilante.ciclos} ciclo(s) | {len(vigilante.alertas)} alertas de red")
    return 0 if not vigilante.alertas else 1


def _cmd_firma(args: argparse.Namespace) -> int:
    if args.generar:
        claves = firma_release.generar_claves()
        if args.json:
            _imprimir(claves, True)
        else:
            print(f"Clave privada (b64): {claves['privada']}")
            print(f"Clave publica (b64): {claves['publica']}")
            print(f"Huella (sha256)    : {firma_release.huella_clave(claves['publica'])}")
        return 0
    if not (args.binario and args.firma and args.clave):
        print("Indica --binario, --firma y --clave (o usa --generar).", file=sys.stderr)
        return 2
    resultado = firma_release.verificar_fichero(Path(args.binario), args.firma, args.clave)
    if args.json:
        _imprimir(resultado, True)
    else:
        print(f"Algoritmo  : {resultado['algoritmo']} (disponible: {resultado['disponible']})")
        print(f"SHA-256    : {resultado['sha256']}")
        print(f"Firma      : {resultado['mensaje']}")
    return 0 if resultado.get("firma_ok") else 1


def _cmd_estado(args: argparse.Namespace) -> int:
    datos = MotorDefensa().estado()
    if args.json:
        _imprimir(datos, True)
        return 0
    blindaje_estado = datos["blindaje"]
    print(f"Administrador : {blindaje_estado['admin']}")
    print(f"hosts         : {blindaje_estado['hosts']}")
    print(f"Sinkhole DNS  : {'activo' if blindaje_estado['sinkhole_dns_activo'] else 'inactivo'}")
    print(f"Politica      : {'firmada' if blindaje_estado['politica'] else 'ausente o manipulada'}")
    for fila in blindaje_estado["resolucion_c2"]:
        print(f"  {fila['dominio']:<28} {fila['estado']:<12} {fila['ip']}")
    conteo = datos["iocs"]
    print(f"Indicadores   : {conteo['patrones']} patrones, {conteo['dominios_c2']} dominios C2")
    return 0


def _cmd_informe(args: argparse.Namespace) -> int:
    informe = MotorDefensa().informe(escanear=True, vigilar=True, resolver=args.resolver)
    if args.json:
        _imprimir(informe_a_diccionario(informe), True)
    else:
        for hallazgo in informe.hallazgos:
            print(hallazgo.como_texto())
        for alerta in informe.alertas:
            print(alerta.como_texto())
        print("\n--- resumen ---")
        _imprimir(informe.resumen, True)
    return 0 if informe.puntos() == 0 else 1


# ------------------------------------------------------------------- parser
def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m STM_HRTS.STM_DEF",
        description="Subsistema defensivo frente al dropper C2 (EtherHiding).",
    )
    sub = parser.add_subparsers(dest="orden", required=True)

    p_iocs = sub.add_parser("iocs", help="lista los indicadores de compromiso")
    p_iocs.add_argument("--json", action="store_true")
    p_iocs.set_defaults(func=_cmd_iocs)

    p_esc = sub.add_parser("escanear", help="detecta el patron del dropper en el arbol")
    p_esc.add_argument("rutas", nargs="*")
    p_esc.add_argument("--json", action="store_true")
    p_esc.set_defaults(func=_cmd_escanear)

    p_his = sub.add_parser("historial", help="busca el dropper en el historial de commits")
    p_his.add_argument("--limite", type=int, default=200, help="commits maximos por termino")
    p_his.add_argument("--json", action="store_true")
    p_his.set_defaults(func=_cmd_historial)

    p_vig = sub.add_parser("vigilar", help="monitoriza conexiones salientes y procesos")
    p_vig.add_argument("--resolver", action="store_true")
    p_vig.add_argument("--ciclos", type=int, default=1)
    p_vig.add_argument("--intervalo", type=float, default=60.0)
    p_vig.add_argument("--json", action="store_true")
    p_vig.set_defaults(func=_cmd_vigilar)

    p_bli = sub.add_parser("blindar", help="sinkhole DNS + firewall de salida")
    p_bli.add_argument("--aplicar", action="store_true", help="escribe en el sistema (requiere admin)")
    p_bli.add_argument("--json", action="store_true")
    p_bli.set_defaults(func=_cmd_blindar)

    p_sel = sub.add_parser("sellar", help="calcula y guarda el sello de integridad")
    p_sel.add_argument("--json", action="store_true")
    p_sel.set_defaults(func=_cmd_sellar)

    p_int = sub.add_parser("integridad", help="verifica el sello de integridad")
    p_int.add_argument("--json", action="store_true")
    p_int.set_defaults(func=_cmd_integridad)

    p_cua = sub.add_parser("cuarentena", help="copia muestras a la cuarentena firmada (nunca borra)")
    p_cua.add_argument("--ruta", action="append", default=[], help="fichero a poner en cuarentena (repetible)")
    p_cua.add_argument("--motivo", default="", help="motivo del aislamiento")
    p_cua.add_argument("--listar", action="store_true", help="enumera las muestras registradas")
    p_cua.add_argument("--verificar", action="store_true", help="comprueba el SHA-256 de las copias")
    p_cua.add_argument("--json", action="store_true")
    p_cua.set_defaults(func=_cmd_cuarentena)

    p_pue = sub.add_parser("puerta", help="paso bloqueante para CI: escaneo + integridad + cuarentena")
    p_pue.add_argument("rutas", nargs="*")
    p_pue.add_argument("--json", action="store_true")
    p_pue.set_defaults(func=_cmd_puerta)

    p_arr = sub.add_parser("arranque", help="hook fail-closed: escaneo + integridad antes de arrancar")
    p_arr.add_argument("rutas", nargs="*")
    p_arr.add_argument("--json", action="store_true")
    p_arr.set_defaults(func=_cmd_arranque)

    p_srv = sub.add_parser("servicio", help="vigilancia continua de salida (servicio periodico con alertas)")
    p_srv.add_argument("--ciclos", type=int, default=1, help="pasadas a ejecutar (<=0 = continuo hasta Ctrl+C)")
    p_srv.add_argument("--intervalo", type=float, default=60.0)
    p_srv.add_argument("--resolver", action="store_true")
    p_srv.add_argument("--json", action="store_true")
    p_srv.set_defaults(func=_cmd_servicio)

    p_fir = sub.add_parser("firma", help="verifica la firma Ed25519 del binario (o genera claves)")
    p_fir.add_argument("--binario", default="", help="fichero a verificar")
    p_fir.add_argument("--firma", default="", help="firma Ed25519 en base64")
    p_fir.add_argument("--clave", default="", help="clave publica Ed25519 en base64")
    p_fir.add_argument("--generar", action="store_true", help="genera un par de claves nuevo")
    p_fir.add_argument("--json", action="store_true")
    p_fir.set_defaults(func=_cmd_firma)

    p_est = sub.add_parser("estado", help="panorama del blindaje y de los indicadores")
    p_est.add_argument("--json", action="store_true")
    p_est.set_defaults(func=_cmd_estado)

    p_inf = sub.add_parser("informe", help="pasada completa: detecta, vigila e integridad")
    p_inf.add_argument("--resolver", action="store_true")
    p_inf.add_argument("--json", action="store_true")
    p_inf.set_defaults(func=_cmd_informe)
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
    raise SystemExit(main())
