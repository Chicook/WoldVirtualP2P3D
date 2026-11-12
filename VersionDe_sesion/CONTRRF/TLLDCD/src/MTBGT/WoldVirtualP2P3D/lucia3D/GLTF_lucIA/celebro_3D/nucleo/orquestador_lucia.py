"""NucleoLucia: orquestador neuronal del proyecto adaptado al puente TCP.

Encadena el nucleo real de WoldVirtualP2P3D:
  - Conversor PSN de 50 neuronas (5 capas x 10), con pesos persistentes en PSNRL.
  - RPLC (vectorizacion, modulacion hebbiana y reformulacion a la voz de LucIA).
  - Memoria de sesion persistente y rubrica de calidad.
Cada turno: prepara el estado neuronal, enriquece el prompt del modelo local,
reprocesa la respuesta y asimila los pesos del turno.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Tuple

CELEBRO_DIR = Path(__file__).resolve().parents[1]
if str(CELEBRO_DIR) not in sys.path:
    sys.path.insert(0, str(CELEBRO_DIR))

from STM_BKCH.compat_local import ConversorRespuestaPesos  # noqa: E402
from STM_CH.rutas import PSNRL_DIR, inicializar as inicializar_rutas  # noqa: E402
from sub_sistemas.RPLC import reprocesar_con_metricas  # noqa: E402
from sub_sistemas.memoria_sesion import get_memoria  # noqa: E402
from sub_sistemas.rubrica import evaluar_calidad  # noqa: E402

ETIQUETA_PESOS = "psnrl_lucia"
_TELEMETRIA_RPLC = re.compile(r"\n+\s*\*\([^\n]*?\)\*\s*$")

INSTRUCCION_ESTADO = (
    "Responde como LucIA usando ese estado interno como tu propia perspectiva. "
    "No enumeres las metricas ni hables de neuronas salvo que te lo pidan."
)


class ConversorPSNLucia(ConversorRespuestaPesos):
    """Conversor PSN de 50 neuronas que recupera sus pesos del ultimo checkpoint."""

    def __init__(self) -> None:
        super().__init__()
        self.cargar_pesos()

    def cargar_pesos(self) -> bool:
        ruta_npz = PSNRL_DIR / f"{ETIQUETA_PESOS}.npz"
        ruta_json = PSNRL_DIR / f"{ETIQUETA_PESOS}.json"
        if not ruta_npz.exists():
            return False
        try:
            import numpy as np
            with np.load(str(ruta_npz)) as datos:
                pesos = datos["pesos"].tolist()
            for neurona, peso in zip(self.neuronas, pesos):
                neurona["peso"] = round(float(peso), 5)
            if ruta_json.exists():
                meta = json.loads(ruta_json.read_text(encoding="utf-8"))
                self.deriva_acumulada = float(meta.get("deriva", 0.0))
            return True
        except Exception:
            return False

    def guardar_pesos(self) -> None:
        self.persistir_pesos_en_psnrl(ETIQUETA_PESOS)


class NucleoLucia:
    """Orquestador neuronal adaptado al ciclo consulta -> respuesta del socket."""

    def __init__(self, sesion_id: str = "") -> None:
        inicializar_rutas()
        self.sesion_id = sesion_id or time.strftime("LUCIA_%Y%m%d_%H%M%S")
        self.conversor = ConversorPSNLucia()
        self.memoria = get_memoria(self.sesion_id)
        self.turno = 0
        self._lock = threading.Lock()

    def preparar_turno(self, prompt: str) -> Dict[str, Any]:
        """Vectoriza la consulta y actualiza las 50 sinapsis antes de generar."""
        with self._lock:
            info = self.conversor.procesar_consulta_a_pesos(prompt)
            self.turno += 1
            info["turno"] = self.turno
            info["sesion_id"] = self.sesion_id
            info["deriva_acumulada"] = self.conversor.deriva_acumulada
            info["neuronas"] = len(self.conversor.neuronas)
            self.conversor.guardar_pesos()
            return info

    def contexto_para_prompt(self, info: Dict[str, Any]) -> str:
        """Bloque de estado interno + memoria que condiciona al modelo local."""
        partes = [
            "[Estado neuronal interno de LucIA]",
            f"- Red: {info.get('neuronas', 50)} sinapsis (ENRN, RF_EN, RF_SL, RNP, SLRN).",
            f"- Tono cognitivo: {info.get('tono_cognitivo', 'analitico')}.",
            f"- Valencia emocional: {float(info.get('estado_emocional', 0.0)):+.3f}.",
            f"- Delta sinaptico del turno: {float(info.get('norma_delta_aplicada', 0.0)):.5f}.",
            f"- Deriva acumulada: {float(info.get('deriva_acumulada', 0.0)):.6f}.",
            INSTRUCCION_ESTADO,
        ]
        memoria = self.memoria.resumen_contexto()
        if memoria:
            partes.extend(("", "[Memoria de la sesion]", memoria))
        return "\n".join(partes)

    def procesar_respuesta(
        self,
        prompt: str,
        crudo: str,
        info: Dict[str, Any],
        ms_generacion: float,
        modelo: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """Pasa la respuesta por RPLC, registra memoria, calidad y pesos."""
        texto, metricas = reprocesar_con_metricas(crudo, info)
        texto = _quitar_telemetria(texto)
        met = dict(metricas)
        met["calidad"] = float(evaluar_calidad(texto, str(met.get("tono", ""))).get("puntuacion", 0.0))
        try:
            from refuerzo.aprendizaje import aplicar_turno as _aplicar_refuerzo
            met["refuerzo"] = _aplicar_refuerzo(info, met)
        except Exception as error:
            met["refuerzo"] = {"activo": False, "motivo": f"refuerzo no disponible: {error}"}
        met["nucleo"] = {
            "neuronas": len(self.conversor.neuronas),
            "deriva": self.conversor.deriva_acumulada,
            "turno": self.turno,
            "tono": str(met.get("tono", "")),
            "valencia": float(met.get("valencia_sinaptica", 0.0)),
            "activas": int(met.get("neuronas_activas", 0)),
        }
        with self._lock:
            self.memoria.registrar_turno(
                prompt=prompt,
                respuesta=texto,
                tono=str(met.get("tono", "")),
                valencia=float(met.get("valencia_sinaptica", 0.0)),
                ms=ms_generacion,
                modelo=modelo,
                deriva=self.conversor.deriva_acumulada,
            )
            self.conversor.guardar_pesos()
        return texto, met

    def estado(self) -> Dict[str, Any]:
        return {
            "sesion": self.sesion_id,
            "neuronas": len(self.conversor.neuronas),
            "deriva": self.conversor.deriva_acumulada,
            "turnos": self.turno,
            "pesos": PSNRL_DIR / f"{ETIQUETA_PESOS}.npz",
        }


def _quitar_telemetria(texto: str) -> str:
    """Elimina el pie de metricas de RPLC para que no se muestre ni se sintetice."""
    limpio = _TELEMETRIA_RPLC.sub("", texto)
    return limpio.strip()
