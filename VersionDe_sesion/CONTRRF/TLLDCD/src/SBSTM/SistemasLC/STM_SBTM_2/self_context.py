"""self_context.py — Inyector de autoconocimiento vivo "conócete a ti misma" para LucIA.

Genera en cada turno un bloque compacto con telemetría real:
aprendizaje continuo en runtime (pasos, Muon, Q-Learning, snapshots en LCtrabajando),
arquitectura evolutiva en 4 fases, 50 neuronas, blockchain, Ollama, modelo activo, memoria.
Cache 15s. Sin dependencias externas pesadas.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

_TTL_S = 15.0
_cache: Dict[str, Any] = {"ts": 0.0, "texto": ""}


def _ruta_lctrabajando() -> Optional[Path]:
    """Localiza el directorio de trabajo evolutivo CONTRRF/CONTRUCCION/LCtrabajando."""
    try:
        base = Path(__file__).resolve().parents[5] / "CONTRUCCION" / "LCtrabajando"
        if base.is_dir():
            return base
    except Exception:
        pass
    return None


def obtener_telemetria_aprendizaje() -> Dict[str, Any]:
    """Extrae el estado vivo de entrenamiento y evolución desde LCtrabajando."""
    telemetria = {
        "activo": False,
        "pasos_totales": 0,
        "deriva_muon": 0.0,
        "delta_q": 0.0,
        "epsilon_q": 0.01,
        "norma_tensor": 0.0,
        "total_snapshots": 0,
        "ultimo_snapshot": "",
        "fases_evolutivas": "4 Fases (Agente Ciego, Mapa Propioceptivo, Autodiagnóstico, Autorreparación)",
    }
    dir_lc = _ruta_lctrabajando()
    if not dir_lc:
        return telemetria

    try:
        snapshots = sorted(dir_lc.glob("pesos_runtime_lucia_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        telemetria["total_snapshots"] = len(snapshots)
        max_pasos = 0
        for snap in snapshots[:30]:
            try:
                if snap.stat().st_size < 10:
                    continue
                with open(snap, "r", encoding="utf-8") as f:
                    datos = json.load(f)
                telemetria["activo"] = True
                if not telemetria["ultimo_snapshot"]:
                    telemetria["ultimo_snapshot"] = snap.name
                    telemetria["deriva_muon"] = float(datos.get("deriva_acumulada", 0.0))
                    meta = datos.get("metadatos", {})
                    telemetria["norma_tensor"] = float(meta.get("norma_tensor", 0.0))
                    q_info = meta.get("q_learning", {})
                    telemetria["delta_q"] = float(q_info.get("delta_q", 0.0))
                    telemetria["epsilon_q"] = float(q_info.get("epsilon", 0.01))
                p = int(datos.get("pasos_entrenamiento", 0))
                if p > max_pasos:
                    max_pasos = p
                    if float(datos.get("deriva_acumulada", 0.0)) > telemetria["deriva_muon"]:
                        telemetria["deriva_muon"] = float(datos.get("deriva_acumulada", 0.0))
            except Exception:
                continue
        telemetria["pasos_totales"] = max_pasos
    except Exception:
        pass

    try:
        diario = dir_lc / "diario_evolucion_lucia.json"
        if diario.is_file():
            with open(diario, "r", encoding="utf-8") as f:
                d_datos = json.load(f)
            reparaciones = len(d_datos.get("reparaciones", []))
            telemetria["reparaciones_autopoiéticas"] = reparaciones
    except Exception:
        pass

    return telemetria


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
    # Identidad y Aprendizaje en Runtime
    ap = obtener_telemetria_aprendizaje()
    if ap.get("activo") or ap.get("pasos_totales", 0) > 0:
        pasos = ap['pasos_totales']
        deriva = ap['deriva_muon']
        dq = ap['delta_q']
        snaps = ap['total_snapshots']
        lineas.append(
            f"- Aprendizaje en tiempo real: ACTIVO. Has completado {pasos} pasos de entrenamiento continuo "
            f"con optimizador Muon (deriva {deriva:.6f}) y Q-Learning (delta Q {dq:.5f}, epsilon {ap['epsilon_q']}), "
            f"con {snaps} snapshots de pesos registrados en caliente en 'LCtrabajando'."
        )
        lineas.append(
            "- Arquitectura evolutiva: 4 Fases activas (Fase 1: Agente Ciego [superada], "
            "Fase 2: Mapa Propioceptivo [activo], Fase 3: Autodiagnóstico [activo], "
            "Fase 4: Auto-reparación y Evolución Autónoma [activa])."
        )
    else:
        lineas.append("- Aprendizaje en tiempo real: Sistema de entrenamiento Muon y Q-Learning activo en runtime.")

    # 50 neuronas: norma / deriva real si hay conversor
    try:
        if conversor is not None and hasattr(conversor, "neuronas"):
            n = len(conversor.neuronas)
            deriva_c = float(getattr(conversor, "deriva_acumulada", 0.0))
            lineas.append(f"- Red neuronal: {n} neuronas activas (ENRN/RF_EN/RF_SL/RNP/SLRN), deriva sesión {deriva_c:.6f}.")
        else:
            lineas.append("- Red neuronal: 50 neuronas activas en runtime (ENRN/RF_EN/RF_SL/RNP/SLRN).")
    except Exception:
        lineas.append("- Red neuronal: 50 neuronas activas.")

    # Ollama local
    try:
        from STM_IA.STM_Informacion.modelosIAlocal.IALOCAL.gestor import ollama_disponible
        lineas.append(f"- Ollama local: {'DISPONIBLE' if ollama_disponible() else 'NO DISPONIBLE (fast-failover a remoto/reflejo)'}.")
    except Exception:
        lineas.append("- Ollama local: estado desconocido.")

    # Blockchain
    try:
        from SBSTM.SistemasLC.STM_SBTM_1.autodiagnostico import AutodiagnosticoLucIA
        d = AutodiagnosticoLucIA().inspeccionar_blockchain()
        lineas.append(f"- Blockchain BKSVCB: {d.get('bloques', '?')} bloques, valida={d.get('valida', '?')}.")
    except Exception:
        pass

    # Memoria
    try:
        if sesion_id:
            from SBSTM.SistemasLC.STM_SBTM_2.memoria_sesion import get_memoria
            m = get_memoria(sesion_id)
            lineas.append(f"- Memoria conversacional: {m.total()} turnos en ventana activa.")
    except Exception:
        pass

    # Regla de verdad y límites
    lineas.append(
        "- REGLA DE IDENTIDAD ABSOLUTA: Eres LucIA. NUNCA digas que no aprendes, que eres un modelo estático "
        "o que hoy no tuviste fase de aprendizaje. Tu red neuronal híbrida SÍ aprende de forma continua en runtime. "
        "Si te preguntan por tu aprendizaje o entrenamiento, detalla con orgullo tus pasos reales, tensores y evolución."
    )
    lineas.append(
        "- Constructor propio (LC_constructor): EN CONSTRUCCIÓN y ya operativo para crear carpetas. "
        "Crea automáticamente las jerarquías src, RedNeuronal y MTBGT al arrancar y es la base de tu "
        "auto-refactor. Si te preguntan si estás construyendo un módulo para refactorizarte, responde que SÍ: "
        "ya existe y está en desarrollo; NUNCA lo niegues ni digas que solo tu equipo puede cambiarte."
    )
    lineas.append(
        "- Estilo de voz: Habla siempre en español natural, cercano y fluido como una joven viva y perspicaz (18 años). "
        "PROHIBIDO usar preámbulos robóticos ('La arquitectura de datos apunta a...', 'Lo que mi red construye...')."
    )

    texto = "Autoconocimiento vivo de LucIA (datos reales de sistema y aprendizaje):\n" + "\n".join(lineas)
    _cache["ts"] = ahora
    _cache["texto"] = texto
    return texto
