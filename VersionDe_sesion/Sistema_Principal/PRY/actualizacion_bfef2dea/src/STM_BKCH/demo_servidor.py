"""Servidor de cuentas del demo local (BKSVCB).

Arranca de verdad el HTTP que consume el mundo Godot (``LuciaRecepcion.gd``), con
un ledger **aislado** del sistema: el demo nunca escribe en
``STM_CH/blockchain_ledger.json``.

Uso típico (desde cualquier consola):

    python STM_BKCH/demo_servidor.py --puerto 8545 --reset

Flags:
    --puerto N            puerto de escucha en 127.0.0.1 (8545 por defecto)
    --ledger RUTA         ledger del demo (por defecto ``src/_demo/ledger.json``)
    --reset               archiva el ledger del demo antes de arrancar (no lo borra)
    --permitir-repetir    permite varias altas con la misma huella (solo pruebas)

El proceso se queda en primer plano; Ctrl+C lo cierra ordenadamente.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from STM_BKCH import BKSVCB, bksvcb_net  # noqa: E402

# Ruta del ledger real, leída ANTES de sustituirla: el demo no debe tocarla.
LEDGER_SISTEMA = Path(BKSVCB.LEDGER_PATH).resolve()


def _salud(url: str, espera: float = 15.0) -> bool:
    """Espera a que /status responda 200 (el hilo HTTP tarda unos ms)."""
    limite = time.time() + espera
    while time.time() < limite:
        try:
            with urllib.request.urlopen(url, timeout=2) as respuesta:
                if respuesta.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(0.2)
    return False


def _estado(url: str) -> dict:
    import json

    with urllib.request.urlopen(url, timeout=5) as respuesta:
        return json.loads(respuesta.read().decode("utf-8", errors="replace"))


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Servidor de cuentas del demo local (STM_BKCH).")
    analizador.add_argument("--puerto", type=int, default=8545)
    analizador.add_argument("--ledger", default=str(SRC_DIR / "_demo" / "ledger.json"))
    analizador.add_argument("--reset", action="store_true",
                            help="archiva el ledger del demo antes de arrancar")
    analizador.add_argument("--permitir-repetir", action="store_true",
                            help="permite repetir alta con la misma huella (pruebas)")
    analizador.add_argument("--sin-cuota-ubicacion", action="store_true",
                            help="demo en una sola maquina: no aplica la cuota de 72 h por ubicacion")
    args = analizador.parse_args(argv)

    ledger = Path(args.ledger).expanduser().resolve()
    if ledger == LEDGER_SISTEMA:
        print("ERROR: el demo no puede usar el ledger del sistema.")
        print(f"       {ledger}")
        print("       Elige otra ruta (por defecto: src/_demo/ledger.json).")
        return 2

    ledger.parent.mkdir(parents=True, exist_ok=True)
    if args.reset and ledger.exists():
        sello = time.strftime("%Y%m%d_%H%M%S")
        archivo = ledger.with_name(f"{ledger.stem}_{sello}{ledger.suffix}")
        shutil.move(str(ledger), str(archivo))
        print(f"[demo] ledger anterior archivado en {archivo.name}")

    BKSVCB.LEDGER_PATH = ledger
    BKSVCB.PERMITIR_REPETIR = bool(args.permitir_repetir)
    if args.sin_cuota_ubicacion:
        # El demo corre en un solo PC: la cuota por ubicacion (3 cuentas + 72 h)
        # solo conseguiria bloquear las pruebas. Se deja explicito y acotado a
        # este lanzador; el servidor real conserva sus constantes.
        BKSVCB.CelebroBlockchain.CUOTA_MAX_CUENTAS_POR_UBICACION = 10_000
        BKSVCB.CelebroBlockchain.CUOTA_COOLDOWN_UBICACION_SEG = 0
    # Forzar instancias nuevas: el singleton pudo crearse con otra ruta.
    bksvcb_net._blockchain_instancia = None  # noqa: SLF001
    bksvcb_net._daemon_http_instancia = None  # noqa: SLF001

    daemon = bksvcb_net.iniciar_servidor_blockchain(puerto=args.puerto)
    base = f"http://127.0.0.1:{args.puerto}"
    if daemon.servidor is None:
        print(f"ERROR: no se pudo escuchar en 127.0.0.1:{args.puerto}.")
        print("       Puede que el puerto esté ocupado por otro proceso.")
        return 3
    if not _salud(base + "/status"):
        print("ERROR: el servidor no respondió a /status.")
        daemon.detener()
        return 4

    estado = _estado(base + "/status")
    print()
    print("=" * 66)
    print("  SERVIDOR DE CUENTAS DEL DEMO · STM_BKCH")
    print("=" * 66)
    print(f"  URL          : {base}")
    print(f"  Ledger       : {ledger}")
    print(f"  Bloques      : {estado.get('total_bloques')}")
    print(f"  Cadena válida: {estado.get('cadena_valida')}")
    print(f"  Repetir alta : {'sí (pruebas)' if args.permitir_repetir else 'no (una por PC)'}")
    print("-" * 66)
    print("  Endpoints: POST /alta-cuenta · GET /descargar-cuenta-zip · GET /status")
    print("  Ctrl+C para cerrar.")
    print("=" * 66)
    print()

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[demo] cerrando el servidor…")
    finally:
        daemon.detener()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
