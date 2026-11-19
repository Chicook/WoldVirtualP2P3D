"""Motor de aprendizaje por recompensa (celebro_3D -> red neuronal principal).

Flujo por turno:
  1. La rubrica de celebro_3D ya puntua la respuesta (``met["calidad"]`` en [0,1]).
  2. Este motor convierte esa calidad en recompensa centrada en [-1, 1].
  3. Mapea el estado cognitivo a un estado/accion discretos para Q-Learning.
  4. Llama al conversor PRINCIPAL (``STM_BKCH.compat_local``) que actualiza las
     neuronas reales RF_EN (Q-Learning) y RF_SL (Gradient Boosting).
  5. Persiste los pesos en el PSNRL PRINCIPAL (src/STM_CH/PSNRL), no en el de
     celebro_3D, para que el sistema principal los recoja en su proximo turno.

Aislamiento de imports: el nucleo de celebro_3D inserta su propio directorio en
sys.path y cachea sus copias de STM_BKCH/STM_CH. Para no usar esas copias, este
motor carga el compat_local principal por ruta de archivo con un nombre de
modulo unico y pasa el PSNRL principal de forma explicita.

Todo es defensivo: si numpy o el src principal no estan disponibles,
``aplicar_turno`` devuelve ``activo=False`` con un motivo y nunca lanza.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ETIQUETA_REFUERZO = "refuerzo_lucia"
_TONOS = ("reflexivo", "analitico", "creativo", "pragmatico")

_SRC_PRINCIPAL: Optional[Path] = None
_MOD_PRINCIPAL: Any = None
_CONV: Any = None
_MOTIVO: str = ""


def _src_principal() -> Optional[Path]:
    """Sube por el arbol hasta encontrar el src principal (STMGNRL/mainLCSTM.py)."""
    global _SRC_PRINCIPAL
    if _SRC_PRINCIPAL is not None:
        return _SRC_PRINCIPAL
    for base in Path(__file__).resolve().parents:
        if (base / "STMGNRL" / "mainLCSTM.py").is_file():
            _SRC_PRINCIPAL = base
            return base
    return None


def _psnrl_principal() -> Optional[Path]:
    src = _src_principal()
    return None if src is None else src / "STM_CH" / "PSNRL"


def _conversor_principal() -> Any:
    """Carga (una vez) el conversor principal con sus neuronas reales."""
    global _MOD_PRINCIPAL, _CONV, _MOTIVO
    if _CONV is not None:
        return _CONV
    src = _src_principal()
    if src is None:
        _MOTIVO = "no se encontro el src principal (STMGNRL/mainLCSTM.py)"
        return None
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    ruta = src / "STM_BKCH" / "compat_local.py"
    try:
        spec = importlib.util.spec_from_file_location("_refuerzo_compat_principal", ruta)
        if spec is None or spec.loader is None:
            _MOTIVO = f"no se pudo crear spec para {ruta}"
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MOD_PRINCIPAL = mod
        _CONV = mod.ConversorRespuestaPesos()
        _CONV.cargar_pesos(ETIQUETA_REFUERZO, psnrl_dir=_psnrl_principal())
        return _CONV
    except Exception as error:
        _MOTIVO = f"fallo al cargar el conversor principal: {error}"
        return None


def _idx_tono(tono: Any) -> int:
    try:
        return _TONOS.index(str(tono).lower())
    except ValueError:
        return 0


def _bucket_valencia(val: float) -> int:
    bucket = int((float(val) + 1.0) / 2.0 * 4.0)
    return max(0, min(3, bucket))


def calcular_recompensa(met: Dict[str, Any]) -> float:
    """Calidad [0,1] -> recompensa centrada [-1,1] (0.5 = neutro)."""
    calidad = float(met.get("calidad", 0.0))
    recompensa = (calidad - 0.5) * 2.0
    return round(max(-1.0, min(1.0, recompensa)), 4)


def mapear_estado_accion(
    info: Dict[str, Any], met: Dict[str, Any]
) -> Tuple[int, int, int, List[float]]:
    """Estado discreto (tono x valencia, 16 estados), accion (tono adoptado, 4).

    Devuelve (estado, accion, siguiente_estado, features_rf_sl).
    """
    tono_prev = _idx_tono(info.get("tono_cognitivo", ""))
    val_prev = float(info.get("estado_emocional", 0.0))
    estado = tono_prev * 4 + _bucket_valencia(val_prev)

    tono_resp = _idx_tono(met.get("tono", info.get("tono_cognitivo", "")))
    accion = tono_resp
    val_resp = float(met.get("valencia_sinaptica", val_prev))
    siguiente = tono_resp * 4 + _bucket_valencia(val_resp)

    features = [
        tono_prev / 3.0,
        (val_prev + 1.0) / 2.0,
        float(met.get("calidad", 0.0)),
        float(info.get("norma_delta_aplicada", 0.0)),
    ]
    return estado, accion, siguiente, features


def aplicar_turno(info: Dict[str, Any], met: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica la recompensa del turno a las neuronas reales y persiste en PSNRL.

    Nunca lanza excepcion. ``activo=False`` indica que el refuerzo no pudo
    ejecutarse (sin numpy, sin src principal, etc.); el llamador no debe
    anunciar aprendizaje real en ese caso.
    """
    resumen: Dict[str, Any] = {"activo": False, "reales": False, "recompensa": 0.0}
    try:
        conv = _conversor_principal()
        if conv is None:
            resumen["motivo"] = _MOTIVO
            return resumen
        recompensa = calcular_recompensa(met)
        estado, accion, siguiente, features = mapear_estado_accion(info, met)
        resultado = conv.aplicar_recompensa(
            recompensa, estado, accion, siguiente, features=features
        )
        psnrl = _psnrl_principal()
        conv.persistir_pesos_en_psnrl(ETIQUETA_REFUERZO, psnrl_dir=psnrl)
        resumen.update(resultado)
        resumen.update({
            "activo": True,
            "recompensa": recompensa,
            "estado": estado,
            "accion": accion,
            "siguiente_estado": siguiente,
            "deriva": conv.deriva_acumulada,
            "psnrl": str(psnrl / f"{ETIQUETA_REFUERZO}.npz") if psnrl else "",
            "etiqueta": ETIQUETA_REFUERZO,
        })
        return resumen
    except Exception as error:
        resumen["motivo"] = f"fallo en aplicar_turno: {error}"
        return resumen


def estado_refuerzo() -> Dict[str, Any]:
    """Diagnostico del cableado: src, PSNRL, disponibilidad de neuronas reales."""
    conv = _conversor_principal()
    src = _src_principal()
    reales = bool(getattr(_MOD_PRINCIPAL, "NEURONAS_REALES_DISPONIBLE", False)) if conv else False
    return {
        "src_principal": str(src) if src else None,
        "psnrl_principal": str(_psnrl_principal()) if src else None,
        "conversor_cargado": conv is not None,
        "neuronas_reales": reales,
        "etiqueta": ETIQUETA_REFUERZO,
        "motivo": _MOTIVO,
    }