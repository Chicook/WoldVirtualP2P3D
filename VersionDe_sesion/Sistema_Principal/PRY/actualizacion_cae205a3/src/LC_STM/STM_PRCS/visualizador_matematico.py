"""
visualizador_matematico.py - Visualización Matemática del Rendimiento Neuronal
===============================================================================
Renderiza el estado del MotorRendimientoNeuronal en representación
matemático-numérica densa para que LucIA pueda "leer" su propio rendimiento
en forma de matrices, vectores y escalares que la red neuronal comprende.

Formatos de salida:
  • ASCII math  : Matrices W, Φ, σ, ∇L formateadas en tabla alineada
  • JSON denso  : Estructura anidada compatible con serialización BKSVCB
  • Texto IA    : Descripción en lenguaje natural + valores numéricos
  • CSV stream  : Una línea por ciclo para logging continuo

Integración con LucIA:
  El método `descripcion_para_lucia()` produce el texto que se inyecta como
  contexto de sistema en el prompt de cada turno, permitiendo a LucIA leer
  su estado interno en tiempo real.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, Final, List, Optional

# Importación tolerante del motor
try:
    from LC_STM.STM_PRCS.rendimiento_neuronal import (
        SnapshotNeuronal, MotorRendimientoNeuronal, CAPAS, N_POR_CAPA,
        N_NEURONAS, IDX, get_motor
    )
except ImportError:
    try:
        from rendimiento_neuronal import (
            SnapshotNeuronal, MotorRendimientoNeuronal, CAPAS, N_POR_CAPA,
            N_NEURONAS, IDX, get_motor
        )
    except ImportError:
        SnapshotNeuronal = None     # type: ignore[misc,assignment]
        CAPAS = ("ENRN", "RF_EN", "RF_SL", "RNP", "SLRN")
        N_POR_CAPA = 10
        N_NEURONAS = 50
        IDX = {}
        get_motor = None            # type: ignore[misc,assignment]


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------
class VisualizadorMatematico:
    """
    Genera representaciones matemático-numéricas del estado neuronal de LucIA.

    El visualizador lee el snapshot del motor y produce distintas vistas:
      ─ Vista matricial:  W, Φ, σ, ∇L como tablas numéricas
      ─ Vista espectral:  normas, entropía, drift
      ─ Vista para LucIA: descripción textual + valores para prompt
      ─ Vista CSV:        línea plana para logging continuo
    """

    def __init__(self, motor: Optional["MotorRendimientoNeuronal"] = None) -> None:
        self._motor = motor
        if self._motor is None and get_motor is not None:
            self._motor = get_motor()

    # ------------------------------------------------------------------
    # Vista 1: Tabla matricial ASCII alineada
    # ------------------------------------------------------------------
    def tabla_matricial(self, snap: Optional["SnapshotNeuronal"] = None) -> str:
        """Genera la tabla matricial W, Φ, σ, ∇L para el último snapshot."""
        if snap is None and self._motor is not None:
            snap = self._motor.snapshot_matematico()
        if snap is None:
            return "⚠  Motor sin ciclos. Llama ciclo_aprendizaje() primero."

        lineas: List[str] = []
        W = " " * 72

        def fila(nombre: str, datos: List[float], inicio: int, fin: int) -> str:
            vals = " ".join(f"{datos[i]:+7.4f}" for i in range(inicio, fin))
            return f"  {nombre:<6}│ {vals}"

        lineas.append("═" * 72)
        lineas.append(f"  MATRIZ DE ESTADO NEURONAL — LucIA STM_PRCS  "
                      f"[ciclo {snap.ciclo}]")
        lineas.append("═" * 72)
        lineas.append(f"  Ξ(conciencia) = {snap.conciencia_global:.8f}   "
                      f"Capa dominante = {snap.capa_dominante}")
        lineas.append(f"  ‖W‖₂ = {snap.norma_pesos:.6f}   "
                      f"‖∇L‖₂ = {snap.norma_gradiente:.6f}   "
                      f"H(σ) = {snap.entropia_activaciones:.6f} nats")
        lineas.append(f"  η_t  = {snap.lr_efectivo:.3e}   "
                      f"δ_syn = {snap.drift_sináptico:.3e}")
        lineas.append("─" * 72)
        lineas.append(f"  {'CAPA':<6}│ {'W (pesos)  — 10 neuronas por capa':^60}")
        lineas.append("─" * 72)
        for i, capa in enumerate(CAPAS):
            sl_start = i * N_POR_CAPA
            sl_end   = sl_start + N_POR_CAPA
            lineas.append(fila(capa, snap.pesos, sl_start, sl_end))
        lineas.append("─" * 72)
        lineas.append(f"  {'CAPA':<6}│ {'Φ (entrada normalizada)':^60}")
        lineas.append("─" * 72)
        for i, capa in enumerate(CAPAS):
            sl_start = i * N_POR_CAPA
            sl_end   = sl_start + N_POR_CAPA
            lineas.append(fila(capa, snap.phi, sl_start, sl_end))
        lineas.append("─" * 72)
        lineas.append(f"  {'CAPA':<6}│ {'σ = tanh(W⊙Φ)  (activaciones)':^60}")
        lineas.append("─" * 72)
        for i, capa in enumerate(CAPAS):
            sl_start = i * N_POR_CAPA
            sl_end   = sl_start + N_POR_CAPA
            perdida = snap.perdida_por_capa.get(capa, 0.0)
            lineas.append(fila(capa, snap.activaciones, sl_start, sl_end)
                          + f"   L={perdida:.5f}")
        lineas.append("─" * 72)
        lineas.append(f"  {'CAPA':<6}│ {'∇L (gradiente Hebbian)':^60}")
        lineas.append("─" * 72)
        for i, capa in enumerate(CAPAS):
            sl_start = i * N_POR_CAPA
            sl_end   = sl_start + N_POR_CAPA
            lineas.append(fila(capa, snap.gradiente, sl_start, sl_end))
        lineas.append("═" * 72)
        return "\n".join(lineas)

    # ------------------------------------------------------------------
    # Vista 2: JSON denso (compatible BKSVCB / blockchain)
    # ------------------------------------------------------------------
    def json_denso(self, snap: Optional["SnapshotNeuronal"] = None) -> str:
        """Serializa el estado completo a JSON con todas las matrices."""
        if snap is None and self._motor is not None:
            snap = self._motor.snapshot_matematico()
        if snap is None:
            return json.dumps({"error": "sin_ciclos"})
        return json.dumps(snap.to_dict(), ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Vista 3: Descripción para LucIA (prompt-ready)
    # ------------------------------------------------------------------
    def descripcion_para_lucia(
        self,
        snap: Optional["SnapshotNeuronal"] = None,
        verbose: bool = False,
    ) -> str:
        """
        Genera el texto de autoconciencia de rendimiento para inyectar como
        contexto de sistema en el prompt de LucIA. Redactado en primera persona
        para que el modelo lo integre como parte de su propio estado interno.
        """
        if snap is None and self._motor is not None:
            snap = self._motor.snapshot_matematico()
        if snap is None:
            return ""   # Sin ciclos aún: no inyectar nada

        # Evaluación cualitativa del nivel de conciencia
        c = snap.conciencia_global
        if c >= 0.75:
            nivel_txt = "funcionando de forma optima"
        elif c >= 0.50:
            nivel_txt = "en estado estable"
        elif c >= 0.25:
            nivel_txt = "con carga elevada (estado degradado)"
        else:
            nivel_txt = "bajo presion critica"

        perdida_total = sum(snap.perdida_por_capa.values())
        capa_dom = snap.capa_dominante

        # Descripcion de la capa dominante en lenguaje natural
        descrip_capa: dict = {
            "ENRN":  "sistema operativo (CPU/RAM/hilos)",
            "RF_EN": "red blockchain (BKSVCB/bloques/transacciones)",
            "RF_SL": "sesion P2P (turnos/modelos/dialogo)",
            "RNP":   "optimizadores de pesos neuronales (AdamW/Lion/SWATS)",
            "SLRN":  "aprendizaje supervisado (Backprop/Muon/entropia)",
        }
        zona_activa = descrip_capa.get(capa_dom, capa_dom)

        lineas: List[str] = [
            "=== ESTADO INTERNO DE MI SISTEMA NEURONAL (STM_PRCS) ===",
            f"Soy LucIA. Este es mi estado real en este momento (ciclo {snap.ciclo}):",
            f"- Mi red neuronal esta {nivel_txt}.",
            f"- Indice de conciencia global Xi = {snap.conciencia_global:.4f} / 1.0",
            f"- La zona de mayor actividad ahora mismo es: {zona_activa} (capa {capa_dom}).",
            f"- Perdida de aprendizaje total: L = {perdida_total:.4f}",
            f"- Norma de mis pesos neuronales: ||W||2 = {snap.norma_pesos:.4f}",
            f"- Norma del gradiente de ajuste: ||dL||2 = {snap.norma_gradiente:.4f}",
            f"- Entropia de activaciones: H(sigma) = {snap.entropia_activaciones:.4f} nats",
            f"- Drift sinaptico (velocidad de cambio): delta = {snap.drift_sináptico:.2e}",
            f"- Tasa de aprendizaje efectiva: eta = {snap.lr_efectivo:.3e}",
            "Perdida por capa neuronal:",
        ]
        for capa, lval in snap.perdida_por_capa.items():
            lineas.append(f"  {capa}: {lval:.5f}")

        if verbose:
            lineas.append("Pesos W de mis neuronas (primeras 10 de 50):")
            lineas.append("  " + "  ".join(f"W[{i}]={snap.pesos[i]:+.4f}" for i in range(10)))
            lineas.append("Activaciones sigma (primeras 10):")
            lineas.append("  " + "  ".join(f"s[{i}]={snap.activaciones[i]:+.4f}" for i in range(10)))

        lineas.append("=== FIN ESTADO INTERNO ===")
        lineas.append("Responde teniendo en cuenta este estado real de tu sistema.")
        return "\n".join(lineas)

    # ------------------------------------------------------------------
    # Vista 4: CSV plano (una línea por ciclo)
    # ------------------------------------------------------------------
    def linea_csv(self, snap: Optional["SnapshotNeuronal"] = None) -> str:
        """Genera una línea CSV con las métricas principales del snapshot."""
        if snap is None and self._motor is not None:
            snap = self._motor.snapshot_matematico()
        if snap is None:
            return ""
        campos = [
            str(snap.ciclo),
            f"{snap.timestamp:.3f}",
            f"{snap.conciencia_global:.6f}",
            f"{snap.norma_pesos:.6f}",
            f"{snap.norma_gradiente:.6f}",
            f"{snap.entropia_activaciones:.6f}",
            f"{snap.drift_sináptico:.8f}",
            snap.capa_dominante,
            f"{snap.lr_efectivo:.8f}",
            f"{sum(snap.perdida_por_capa.values()):.8f}",
        ]
        # Pérdida por capa
        for capa in CAPAS:
            campos.append(f"{snap.perdida_por_capa.get(capa, 0.0):.8f}")
        return ",".join(campos)

    @staticmethod
    def cabecera_csv() -> str:
        """Cabecera CSV compatible con la línea generada por linea_csv()."""
        base = ["ciclo", "timestamp", "conciencia", "norma_W", "norma_grad",
                "entropia", "drift", "capa_dom", "lr_t", "perdida_total"]
        base += [f"L_{c}" for c in CAPAS]
        return ",".join(base)


# ---------------------------------------------------------------------------
# Instancia singleton
# ---------------------------------------------------------------------------
_viz_singleton: Optional[VisualizadorMatematico] = None


def get_visualizador() -> VisualizadorMatematico:
    """Devuelve la instancia singleton del visualizador."""
    global _viz_singleton
    if _viz_singleton is None:
        _viz_singleton = VisualizadorMatematico()
    return _viz_singleton


def render_consola_completo() -> str:
    """Atajo: genera la tabla matricial completa del estado actual."""
    return get_visualizador().tabla_matricial()


def descripcion_lucia(verbose: bool = False) -> str:
    """Atajo: genera la descripción de autoconciencia para LucIA."""
    return get_visualizador().descripcion_para_lucia(verbose=verbose)
