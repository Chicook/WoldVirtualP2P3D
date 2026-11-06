"""Memoria contextual de sesion para LucIA (SBSTM).

Ventana de ultimos turnos + resumen comprimido por turno.
Persistencia en STM_CH/PSNRL/memoria_<sesion_id>.json.
Sin dependencias externas.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

VENTANA_DEFECTO: int = 20
MAX_CHARS_TURNO: int = 400
UMBRAL_RESUMEN: int = 10


def _dir_psnrl() -> Path:
    try:
        from STM_CH.rutas import PSNRL_DIR
        d = Path(PSNRL_DIR)
    except ImportError:
        d = Path(__file__).resolve().parents[1] / "STM_CH" / "PSNRL"
    d.mkdir(parents=True, exist_ok=True)
    return d


class MemoriaSesion:
    """Ventana deslizante de turnos con resumen inyectable en el prompt."""

    def __init__(self, sesion_id: str = "", ventana: int = VENTANA_DEFECTO) -> None:
        self.sesion_id: str = sesion_id or time.strftime("%Y%m%d_%H%M%S")
        self.ventana: int = max(1, int(ventana))
        self._turnos: List[Dict[str, Any]] = []
        self._resumen_largo: str = ""
        self._ult_telemetria: str = ""
        self._ruta: Path = _dir_psnrl() / f"memoria_{self.sesion_id}.json"
        self.cargar()

    # ── REGISTRO ──────────────────────────────────────────────────────────
    def registrar_turno(
        self,
        prompt: str,
        respuesta: str,
        tono: str = "",
        valencia: float = 0.0,
        ms: float = 0.0,
        modelo: str = "",
        deriva: float = 0.0,
    ) -> Dict[str, Any]:
        turno = {
            "n": len(self._turnos) + 1,
            "ts": time.time(),
            "prompt": (prompt or "")[:MAX_CHARS_TURNO],
            "respuesta": (respuesta or "")[:MAX_CHARS_TURNO],
            "tono": tono,
            "valencia": round(float(valencia), 3),
        }
        self._turnos.append(turno)
        self._turnos = self._turnos[-self.ventana:]
        if len(self._turnos) >= UMBRAL_RESUMEN:
            self._compactar_resumen()
        if ms > 0 or modelo:
            self._ult_telemetria = f"Ultimo turno: {ms:.0f}ms modelo={modelo} deriva={deriva:.4f}"
        self.guardar()
        return turno

    def _compactar_resumen(self) -> None:
        """Resumen jerarquico: conserva hechos (nombres, temas) de turnos antiguos."""
        antiguos = self._turnos[: len(self._turnos) - self.ventana // 2]
        if not antiguos:
            return
        hechos = "; ".join(f"{t['prompt'][:80]}" for t in antiguos[-5:])
        if hechos:
            self._resumen_largo = (self._resumen_largo + " | " + hechos)[-800:]

    # ── CONSULTA ──────────────────────────────────────────────────────────
    def resumen_contexto(self) -> str:
        """Texto compacto para anteponer al prompt del modelo."""
        if not self._turnos and not self._resumen_largo and not self._ult_telemetria:
            return ""
        partes = []
        if self._resumen_largo:
            partes.append(f"Resumen largo:{self._resumen_largo}")
        lineas = []
        for t in self._turnos[-6:]:
            lineas.append(
                f"[T{t['n']}] U:{t['prompt'][:120]} | L:{t['respuesta'][:120]}"
            )
        if lineas:
            partes.append("Contexto previo (ultimos 6):\n" + "\n".join(lineas))
        if self._ult_telemetria:
            partes.append(f"Telemetria propia: {self._ult_telemetria} (puedes opinar sobre tu latencia).")
        return "\n".join(partes)

    def ultimos(self, n: int = 3) -> List[Dict[str, Any]]:
        return list(self._turnos[-max(1, n):])

    def total(self) -> int:
        return len(self._turnos)

    # ── PERSISTENCIA ──────────────────────────────────────────────────────
    def guardar(self) -> Path:
        self._ruta.write_text(
            json.dumps(
                {
                    "sesion_id": self.sesion_id,
                    "ventana": self.ventana,
                    "resumen_largo": self._resumen_largo,
                    "ult_telemetria": self._ult_telemetria,
                    "turnos": self._turnos,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return self._ruta

    def cargar(self) -> bool:
        if not self._ruta.exists():
            return False
        try:
            data = json.loads(self._ruta.read_text(encoding="utf-8"))
            self._resumen_largo = str(data.get("resumen_largo", ""))
            self._ult_telemetria = str(data.get("ult_telemetria", ""))
            self._turnos = list(data.get("turnos", []))[-self.ventana:]
            return True
        except Exception:
            return False

    def limpiar(self) -> None:
        self._turnos = []
        try:
            self._ruta.unlink(missing_ok=True)
        except Exception:
            pass


_memoria_inst: Optional[MemoriaSesion] = None


def get_memoria(sesion_id: str = "") -> MemoriaSesion:
    global _memoria_inst
    if _memoria_inst is None or (sesion_id and _memoria_inst.sesion_id != sesion_id):
        _memoria_inst = MemoriaSesion(sesion_id=sesion_id)
    return _memoria_inst