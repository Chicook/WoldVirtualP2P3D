"""Servidor Oficial de Cuentas y Blockchain (STM_BKCH).

Arranca el servicio HTTP REST y la blockchain neuronal inmutable que
consume el visor de Wold Virtual 3D y la recepción de LucIA 3D en Godot.
Usa el libro mayor (ledger) oficial del sistema: STM_CH/blockchain_ledger.json.

Uso:
    python STM_BKCH/servidor_oficial.py [--puerto 8545]
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from STM_BKCH.stm_bkch1 import bksvcb_net

SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from STM_BKCH.stm_bkch1 import BKSVCB  # noqa: E402
from STM_CH.STM_herramientas.rutas import LEDGER_PATH, PSNRL_DIR  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Servidor Oficial de Cuentas y Blockchain (WoldVirtualP2P3D)."
    )
    parser.add_argument("--puerto", type=int, default=8545, help="Puerto de escucha (8545 por defecto)")
    parser.add_argument("--permitir-repetir", action="store_true", help="Permite repetir alta para pruebas")
    parser.add_argument("--sin-cuota-ubicacion", action="store_true", help="Desactiva límite de 72h por ubicación")
    args = parser.parse_args(argv)

    # Configurar rutas oficiales
    BKSVCB.LEDGER_PATH = LEDGER_PATH
    BKSVCB.PSNRL_DIR = PSNRL_DIR
    BKSVCB.PERMITIR_REPETIR = bool(args.permitir_repetir)

    if args.sin_cuota_ubicacion:
        BKSVCB.CelebroBlockchain.CUOTA_MAX_CUENTAS_POR_UBICACION = 10_000
        BKSVCB.CelebroBlockchain.CUOTA_COOLDOWN_UBICACION_SEG = 0

    # Reiniciar instancias para asegurar rutas oficiales
    bksvcb_net._blockchain_instancia = None  # noqa: SLF001
    bksvcb_net._daemon_http_instancia = None  # noqa: SLF001

    daemon = bksvcb_net.iniciar_servidor_blockchain(puerto=args.puerto)
    if daemon.servidor is None:
        print(f"[ERROR] No se pudo abrir el servidor en 127.0.0.1:{args.puerto} (puerto ocupado?)", file=sys.stderr)
        return 1

    bks = bksvcb_net.get_blockchain_server()
    valida, err = bks.validar_cadena()

    print("==================================================================")
    print("  WOLD VIRTUAL 3D · SERVIDOR OFICIAL BLOCKCHAIN & CUENTAS")
    print(f"  Escuchando en http://127.0.0.1:{args.puerto}")
    print(f"  Ledger oficial: {LEDGER_PATH}")
    print(f"  Bloques en cadena: {len(bks.cadena)} | Cadena íntegra: {valida}")
    print("==================================================================")
    sys.stdout.flush()

    # Bucle de espera hasta señal de terminación
    detener = False

    def _sig_handler(signum, frame):
        nonlocal detener
        detener = True

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    try:
        while not detener:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[servidor_oficial] Cerrando servidor HTTP de blockchain...")
        daemon.detener()
        print("[servidor_oficial] Servidor cerrado correctamente.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
