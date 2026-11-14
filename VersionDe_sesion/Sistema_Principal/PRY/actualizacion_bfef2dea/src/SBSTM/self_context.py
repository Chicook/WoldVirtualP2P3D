"""self_context.py — Inyector de autoconocimiento vivo "conocete a ti misma" para LucIA.

Genera en cada turno un bloque compacto con telemetria real:
neuronas, blockchain, Ollama, modelo activo, memoria. Cache 15s.
Sin dependencias externas.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

_TTL_S = 15.0
_cache: Dict[str, Any] = {"ts": 0.0, "texto": ""}


def construir_self_context(
    conversor: Any = None,
    sesion_id: str = "",
    forzar: bool = False,
) -> str:
    """Devuelve bloque de autoconocimiento listo para inyectar al prompt."""
    ahora = time.monotonic()
    if not forzar and _cache["texto"] and (ahora - _cache["ts"]) < _TTL_S:
        return str(_cache["texto"])
    lineas = []
    # 50 neuronas: norma / deriva real si hay conversor
    try:
        if conversor is not None and hasattr(conversor, "neuronas"):
            n = len(conversor.neuronas)
            deriva = float(getattr(conversor, "deriva_acumulada", 0.0))
            lineas.append(f"- Red neuronal: {n} neuronas activas (ENRN/RF_EN/RF_SL/RNP/SLRN), deriva {deriva:.6f}.")
        else:
            lineas.append("- Red neuronal: 50 neuronas (ENRN/RF_EN/RF_SL/RNP/SLRN).")
    except Exception:
        lineas.append("- Red neuronal: 50 neuronas.")
    # Ollama local
    try:
        from STM_IA.modelosIAlocal.IALOCAL.gestor import ollama_disponible
        lineas.append(f"- Ollama local: {'DISPONIBLE' if ollama_disponible() else 'NO DISPONIBLE (fast-failover a remoto/reflejo)'}.")
    except Exception:
        lineas.append("- Ollama local: estado desconocido.")
    # Blockchain
    try:
        from SBSTM.autodiagnostico import AutodiagnosticoLucIA
        d = AutodiagnosticoLucIA().inspeccionar_blockchain()
        lineas.append(f"- Blockchain: {d.get('bloques', '?')} bloques, valida={d.get('valida', '?')}.")
    except Exception:
        pass
    # Memoria
    try:
        if sesion_id:
            from SBSTM.memoria_sesion import get_memoria
            m = get_memoria(sesion_id)
            lineas.append(f"- Memoria conversacional: {m.total()} turnos en ventana.")
    except Exception:
        pass
    lineas.append("- Limites honestos: si no se algo, digo 'no lo se' antes que alucinar; no navego por internet; no ejecuto codigo arbitrario; respondo en espanol, clara y directa.")
    texto = "Autoconocimiento vivo de LucIA (datos reales):\n" + "\n".join(lineas)
    _cache["ts"] = ahora
    _cache["texto"] = texto
    return texto
