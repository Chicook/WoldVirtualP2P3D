"""
demo_conciencia.py - Demostración del Sistema de Autoconciencia STM_PRCS
=========================================================================
Ejecuta el sistema completo de autoconciencia de rendimiento de LucIA:
  1. Inicializa el MotorRendimientoNeuronal
  2. Ingesta métricas de ejemplo de todos los subsistemas
  3. Ejecuta N ciclos de aprendizaje con actualización de pesos
  4. Muestra la representación matemática en consola
  5. Genera el contexto de autoconciencia para el prompt de LucIA

Uso:
    python demo_conciencia.py
    python demo_conciencia.py --ciclos 20 --verbose
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Asegurar importación desde src/
_THIS = Path(__file__).resolve()
_SRC = _THIS.parent.parent.parent
sys.path.insert(0, str(_SRC))

from LC_STM.STM_PRCS import (
    inicializar_stm_prcs,
    ciclo_conciencia,
    contexto_lucia,
    render_estado,
    get_motor,
    estado_paquete,
)
from LC_STM.STM_PRCS.rendimiento_neuronal import CAPAS, IDX


def simular_metricas_ejemplo() -> dict:
    """Genera un dict de métricas de ejemplo que simula actividad del sistema."""
    import random
    import math
    t = time.time()
    return {
        # SO
        "cpu_pct":           random.uniform(5, 65),
        "ram_mb":            random.uniform(80, 400),
        "ram_pct":           random.uniform(20, 70),
        "disco_io_mb":       random.uniform(0, 50),
        "latencia_ms":       random.uniform(50, 2000),
        "thrpt_tokens_s":    random.uniform(10, 120),
        "threads_activos":   float(random.randint(4, 20)),
        "swap_mb":           random.uniform(0, 100),
        "gc_colecciones":    float(random.randint(0, 50)),
        "uptime_s":          t % 86400,
        # Blockchain
        "bk_bloques":        float(random.randint(1, 50)),
        "bk_transacciones":  float(random.randint(0, 10)),
        "bk_hash_entropía":  random.uniform(0.7, 0.95),
        "bk_dificultad":     float(random.randint(2, 4)),
        "bk_nonce":          float(random.randint(0, 100000)),
        "bk_merkle_bits":    float(random.randint(100, 256)),
        "bk_time_minar_ms":  random.uniform(100, 5000),
        "bk_cid_presente":   float(random.randint(0, 1)),
        "bk_deriva_acum":    random.uniform(0, 0.5),
        "bk_pasos_sesion":   float(random.randint(0, 200)),
        # Sesión P2P
        "sb_session_active": 1.0,
        "sb_turnos":         float(random.randint(1, 100)),
        "sb_sesiones_total": float(random.randint(1, 20)),
        "sb_checkpoint_age": random.uniform(0, 300),
        "modelo_id_hash":    abs(math.sin(t)) % 1.0,
        "tokens_prompt_avg": random.uniform(100, 800),
        "tokens_resp_avg":   random.uniform(200, 1500),
        "ratio_error_resp":  random.uniform(0, 0.1),
        "costo_acum_usd":    0.0,
        "voz_activa":        0.0,
        # RNP
        "rnp_loss_actual":   random.uniform(0.1, 3.0),
        "rnp_loss_delta":    random.uniform(-0.5, 0.5),
        "rnp_grad_norm":     random.uniform(0.01, 2.0),
        "rnp_weight_norm":   random.uniform(1.0, 15.0),
        "rnp_lr_efectivo":   0.003,
        "rnp_momentum_mag":  random.uniform(0.0, 0.5),
        "rnp_var_mag":       random.uniform(0.0, 0.3),
        "rnp_iter_global":   float(random.randint(0, 1000)),
        "rnp_switch_sgd":    0.0,
        "rnp_score_global":  random.uniform(0.4, 0.95),
        # SLRN
        "sl_loss_bp":        random.uniform(0.05, 2.0),
        "sl_shannon_entr":   random.uniform(1.0, 3.5),
        "sl_muon_drift":     random.uniform(0.0, 0.3),
        "sl_gsnr":           random.uniform(0.5, 8.0),
        "sl_cosine_sim":     random.uniform(0.5, 1.5),
        "sl_weight_decay_e": random.uniform(0.7, 1.0),
        "sl_cond_estimate":  random.uniform(1.0, 100.0),
        "sl_update_eff":     random.uniform(0.5, 1.0),
        "sl_prec_score":     random.uniform(0.6, 1.0),
        "sl_iter_sl":        float(random.randint(0, 500)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo de autoconciencia STM_PRCS de LucIA"
    )
    parser.add_argument("--ciclos", type=int, default=5,
                        help="Número de ciclos de aprendizaje a ejecutar")
    parser.add_argument("--verbose", action="store_true",
                        help="Muestra información detallada del estado")
    args = parser.parse_args()

    print("\n" + "═" * 72)
    print("  🧠 LucIA — STM_PRCS · Sistema de Autoconciencia de Rendimiento")
    print("  WoldVirtualP2P3D 2026  —  v2026.1.0")
    print("═" * 72)

    # Inicializar el sistema completo
    print("\n[1/4] Inicializando STM_PRCS...")
    ctx = inicializar_stm_prcs(
        arrancar_colector_auto=False,  # En demo no arrancamos el hilo
        propagar_bksvcb=False,         # BKSVCB puede no estar activo
        propagar_psnrl=True,
    )
    print(f"  → Motor: {'✓' if ctx.get('motor') else '✗'}")
    print(f"  → Actualizador: {'✓' if ctx.get('actualizador') else '✗'}")
    print(f"  → Visualizador: {'✓' if ctx.get('visualizador') else '✗'}")

    # Ejecutar ciclos de aprendizaje
    print(f"\n[2/4] Ejecutando {args.ciclos} ciclos de aprendizaje neuronal...")
    for i in range(args.ciclos):
        metricas = simular_metricas_ejemplo()
        snap = ciclo_conciencia(metricas)
        if snap:
            barra = "█" * int(snap.conciencia_global * 30) + "░" * (30 - int(snap.conciencia_global * 30))
            print(f"  Ciclo {snap.ciclo:>4} │ {barra} │ Ξ={snap.conciencia_global:.4f} "
                  f"L={sum(snap.perdida_por_capa.values()):.5f} "
                  f"[{snap.capa_dominante}]")
        time.sleep(0.05)

    # Mostrar representación matemática
    print("\n[3/4] Representación matemática del estado neuronal:")
    print(render_estado())

    # Mostrar contexto de autoconciencia para LucIA
    print("\n[4/4] Contexto de autoconciencia para LucIA:")
    print("─" * 72)
    print(contexto_lucia(verbose=args.verbose))
    print("─" * 72)

    # Estado del paquete
    estado = estado_paquete()
    print(f"\n  Ciclos totales ejecutados: {estado.get('ultimo_ciclo', 0)}")
    print(f"  Conciencia global final Ξ: {estado.get('conciencia_global', 0):.6f}")
    print(f"  Capa dominante:            {estado.get('capa_dominante', 'N/A')}")

    print("\n  ✓ Demo completada. LucIA tiene conciencia de su propio rendimiento.")
    print("═" * 72 + "\n")


if __name__ == "__main__":
    main()
