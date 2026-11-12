#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de arranque independiente del Servidor Neuronal de BLOK1.
Permite tener el backend escuchando en ws://127.0.0.1:8765 para que Godot
y cualquier otro cliente se conecten de forma persistente.
"""

import sys
import os
import signal
import time

# Configurar path a la raíz neuronal
ruta_raiz = os.path.abspath(r"E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\CONTRUCCION\Refactorizacion\src\LC_STM\RedNeuronal")
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

from CELEBRO.BLOK1.BASE_NEURONAL1 import BaseNeuronal1, ServidorNeuronal

def main():
    puerto = 8765
    host = "127.0.0.1"
    
    print("=" * 80)
    print(" INICIANDO BACKEND SERVIDOR NEURONAL BLOK1 (Godot / WebSocket RFC 6455)")
    print("=" * 80)
    
    cerebro = BaseNeuronal1()
    servidor = ServidorNeuronal(cerebro=cerebro, host=host, port=puerto)
    
    def signal_handler(sig, frame):
        print("\n[BACKEND] Señal de terminación recibida. Cerrando servidor...")
        servidor.detener()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print(f"\n[BACKEND] Servidor neuronal en ejecución en ws://{host}:{puerto}")
    print("[BACKEND] Presiona Ctrl+C en cualquier momento para detenerlo.")
    
    servidor.ejecutar()

if __name__ == "__main__":
    main()
