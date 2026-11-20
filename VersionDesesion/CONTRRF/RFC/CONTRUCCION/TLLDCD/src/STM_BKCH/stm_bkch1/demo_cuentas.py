"""Servidor de cuentas para el DEMO: bloques locales, sin tuneles ni red P2P.

Arranca el mismo motor de blockchain que usa el proyecto (`STM_BKCH`) pero con
un ledger aparte (`demo_ledger.json`) para no tocar la cadena real:

    python demo_cuentas.py            # escucha en 127.0.0.1:8545
    python demo_cuentas.py --puerto 8546

El visor/demo habla con el por HTTP: /alta-cuenta, /migrar-cuenta,
/descargar-cuenta-zip y /blocks.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from STM_BKCH.stm_bkch1 import bksvcb_net

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from STM_BKCH.stm_bkch1 import BKSVCB  # noqa: E402

LEDGER_DEMO = Path(__file__).resolve().parent / "demo_ledger.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Servidor de cuentas del demo")
    parser.add_argument("--puerto", type=int,
                        default=int(os.environ.get("BKSVCB_PUERTO", "8545")))
    parser.add_argument("--reiniciar", action="store_true",
                        help="borra el ledger del demo antes de arrancar")
    parser.add_argument("--libre", action="store_true",
                        help="permite repetir alta y migración con la misma huella o nick")
    args = parser.parse_args()

    if args.reiniciar:
        LEDGER_DEMO.unlink(missing_ok=True)

    # Ledger aparte: el demo nunca escribe en la cadena real.
    BKSVCB.LEDGER_PATH = LEDGER_DEMO
    # En el demo se pueden repetir alta y migración para probar los dos caminos.
    BKSVCB.PERMITIR_REPETIR = bool(args.libre)
    bksvcb_net._blockchain_instancia = None  # noqa: SLF001
    bksvcb_net._daemon_http_instancia = None  # noqa: SLF001

    daemon = bksvcb_net.BlockchainServerDaemon(puerto=args.puerto)
    if not daemon.iniciar():
        print(f"[demo] no se pudo abrir el puerto {args.puerto}")
        return 1
    print(f"[demo] servidor de cuentas en http://127.0.0.1:{args.puerto}")
    print(f"[demo] ledger: {LEDGER_DEMO}")
    print("[demo] Ctrl+C para parar")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        daemon.detener()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
