from __future__ import annotations
"""Shims locales BKSVCB: conversor PSNRCV e IPFSManager mínimos.

Evitan el crash cuando los módulos originales LC.celebro no existen en src/.
El conversor expone la interfaz usada por mainLCSTM y BKSVCB:
neuronas, deriva_acumulada, procesar_consulta_a_pesos().

H1 (contención P0):
  - IPFSManager es un shim deliberadamente no-op.  NUNCA borra archivos.
  - Cualquier método que antes simulaba éxito ahora devuelve ok=False con
    un campo ``error`` descriptivo, salvo ``almacenar_pesos`` que sigue
    generando un CID sintético para no romper el flujo de registro.
  - IPFS_DISPONIBLE = False: el caller debe consultarlo antes de anunciar
    sincronización como completada.
"""
import hashlib
import math
import time
from typing import Any, Dict, List, Optional, Tuple

# H1: constante pública para que el llamador pueda comprobar el estado real
IPFS_DISPONIBLE: bool = False



class SimpleEncoder:
    """Encoder de proyeccion sintetica de hashes a tensores de 50 dimensiones."""

    def encode(self, texto: str) -> Any:
        h = hashlib.sha256(texto.encode("utf-8")).digest()
        try:
            import numpy as np
            raw = np.frombuffer(h * 2, dtype=np.uint8)[:50]
            return (raw.astype(np.float32) / 255.0) - 0.5
        except Exception:
            return [((b / 255.0) - 0.5) for b in (h * 2)[:50]]


class ConversorRespuestaPesos:
    """Conversor local de 50 neuronas (5 capas x 10)."""

    def __init__(self) -> None:
        self.neuronas: List[Dict[str, Any]] = [
            {"id": f"{capa}{i}", "peso": 0.0}
            for capa in ("ENRN", "RF_EN", "RF_SL", "RNP", "SLRN")
            for i in range(1, 11)
        ]
        self.deriva_acumulada: float = 0.0
        self.pasos_sesion: int = 0
        self.encoder = SimpleEncoder()

    def _propagar_todas_las_neuronas(self, v: Any) -> Tuple[Any, float]:
        try:
            import numpy as np
            arr = np.asarray(v, dtype=np.float32)
            act = np.tanh(arr)
            return act, float(np.mean(np.abs(act)))
        except Exception:
            import math
            act = [math.tanh(x) for x in v]
            return act, sum(abs(x) for x in act) / max(1, len(act))

    def _actualizar_pesos_en_todas_las_neuronas(self, v: Any, act: Any, factor: float = 1.0) -> Tuple[Any, float, Any]:
        try:
            import numpy as np
            deltas = np.asarray(act, dtype=np.float32) * factor * 0.01
            for i in range(min(len(self.neuronas), len(deltas))):
                self.neuronas[i]["peso"] = round(float(self.neuronas[i]["peso"] + deltas[i]), 5)
            norma = float(np.linalg.norm(deltas))
            self.deriva_acumulada = round(self.deriva_acumulada + norma * 0.001, 6)
            return None, round(norma, 5), None
        except Exception:
            norma = 0.01
            return None, norma, None

    def asimilar_respuestas_y_calcular_sintesis(self, prompt: str, respuesta: str,
                                                     modelo: str = "") -> Dict[str, Any]:
        info = self.procesar_consulta_a_pesos(f"{prompt} || {respuesta}")
        info["modelo"] = modelo
        info["sintesis"] = f"Turno asimilado en {len(self.neuronas)} neuronas."
        info["pasos_sesion"] = self.pasos_sesion
        return info

    def persistir_pesos_en_psnrl(self, etiqueta: str = "checkpoint"):
        import json
        from pathlib import Path
        try:
            from STM_CH.rutas import PSNRL_DIR
        except ImportError:
            PSNRL_DIR = Path("STM_CH") / "PSNRL"
        PSNRL_DIR.mkdir(parents=True, exist_ok=True)
        pesos = [n["peso"] for n in self.neuronas]
        npz_p = PSNRL_DIR / f"{etiqueta}.npz"
        js_p = PSNRL_DIR / f"{etiqueta}.json"
        try:
            import numpy as np
            np.savez_compressed(str(npz_p), pesos=np.array(pesos, dtype=np.float32))
        except Exception:
            npz_p.write_bytes(repr(pesos).encode("utf-8", "replace"))
        js_p.write_text(json.dumps({"etiqueta": etiqueta, "deriva": self.deriva_acumulada,
                                    "neuronas": len(self.neuronas)}, ensure_ascii=False), encoding="utf-8")
        return (npz_p, js_p)

    def procesar_consulta_a_pesos(self, prompt: str) -> Dict[str, Any]:
        h = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
        tonos = ("reflexivo", "analitico", "creativo", "pragmatico")
        tono_cog = tonos[h % len(tonos)]
        try:
            import numpy as np
            # Tensor de 5x10 (5 capas x 10 neuronas)
            semilla = (np.arange(50, dtype=np.float32).reshape(5, 10) + (h % 1000)) / 1000.0
            # Ortogonalizacion espectral grado-5 estilo Muon 2026
            norm_fro = float(np.linalg.norm(semilla, ord="fro")) + 1e-12
            x = semilla / norm_fro
            for _ in range(3):
                x = 1.5 * x - 0.5 * x @ (x.T @ x)
            val = round(float(np.clip(np.mean(x) * 2.0, -1.0, 1.0)), 3)
            norma = round(float(np.mean(np.abs(x))), 5)
            # Actualizar pesos de las 50 neuronas
            planos = x.flatten()
            for i, p in enumerate(planos[:len(self.neuronas)]):
                self.neuronas[i]["peso"] = round(float(p), 5)
        except Exception:
            val = round(((h % 2000) / 1000.0) - 1.0, 3)
            norma = round((h % 100000) / 100000.0, 5)

        self.deriva_acumulada = round(self.deriva_acumulada + norma * 0.001, 6)
        self.pasos_sesion += 1
        return {
            "tono_cognitivo": tono_cog,
            "estado_emocional": val,
            "norma_delta_aplicada": norma,
        }


_conversor_inst: Optional[ConversorRespuestaPesos] = None


def get_conversor_pesos() -> ConversorRespuestaPesos:
    global _conversor_inst
    if _conversor_inst is None:
        _conversor_inst = ConversorRespuestaPesos()
    return _conversor_inst


class IPFSManager:
    """Shim IPFS sin daemon.  NUNCA borra archivos locales (H1, P0-1).

    - ``almacenar_pesos``: genera un CID sintético ``QmLocal*`` para que el
      flujo de registro no se rompa, pero señala que no hay persistencia real.
    - ``subir_y_limpiar_psnrl``: devuelve error visible; no borra nada.
    - ``recuperar_pesos``: devuelve error visible; los datos están vacíos.
    - ``ejecutar_gc``: no-op, siempre ok.

    El llamador DEBE comprobar ``ok`` y ``error`` antes de anunciar éxito.
    Consulta la constante ``IPFS_DISPONIBLE`` para saber si hay daemon real.
    """

    def almacenar_pesos(self, datos: Any = None, origen: Any = None,
                          nombre_modelo: str = "", eliminar_local: bool = False,
                          **kw: Any) -> Dict[str, Any]:
        """CID sintético local; nunca borra el origen (H1)."""
        base = datos if datos is not None else origen
        sello = hashlib.sha256(repr((str(base)[:200], time.time())).encode()).hexdigest()[:16]
        cid = f"QmLocal{sello}"
        # H1: el shim nunca borra aunque eliminar_local=True
        return {
            "cid": cid,
            "ipfs_cid": cid,
            "ok": False,           # sin daemon real no hay persistencia
            "borrado_local": False,
            "error": "IPFS no disponible: shim local sin daemon. Datos NO persistidos en red.",
            "simulado": True,
        }

    def subir_y_limpiar_psnrl(self, forzar_borrado_sin_daemon: bool = False) -> Dict[str, Any]:
        """H1: no borra nada.  Devuelve error visible para que el llamador no anuncie éxito."""
        # NUNCA se borran archivos en el shim, con o sin forzar_borrado_sin_daemon
        return {
            "ok": False,
            "modo": "shim-sin-daemon",
            "cids": [],
            "borrados": [],
            "error": (
                "IPFS no disponible: shim local. "
                "Los archivos PSNRL NO se subieron ni borraron. "
                "Persistencia real requiere daemon Kubo activo."
            ),
        }

    def recuperar_pesos(self, cid: str, destino: Any = None) -> Dict[str, Any]:
        """H1: señala que no hay datos recuperables desde el shim."""
        return {
            "cid": str(cid),
            "ok": False,
            "datos": {},
            "recuperado": False,
            "error": "IPFS no disponible: shim local. No se puede recuperar desde CID sintético.",
        }

    def ejecutar_gc(self) -> Dict[str, Any]:
        """No-op siempre seguro."""
        return {"ok": True, "bloques_liberados": 0}


_ipfs_inst: Optional[IPFSManager] = None


def get_ipfs_manager() -> IPFSManager:
    global _ipfs_inst
    if _ipfs_inst is None:
        _ipfs_inst = IPFSManager()
    return _ipfs_inst
