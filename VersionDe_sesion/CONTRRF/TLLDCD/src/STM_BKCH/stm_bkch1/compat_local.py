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

# Cableado de neuronas reales (RF_EN/RF_SL). Se fija al instanciar el conversor;
# el llamador debe consultarlo antes de anunciar aprendizaje por refuerzo real.
NEURONAS_REALES_DISPONIBLE: bool = False
_MOTIVO_NEURONAS: str = ""


def _importar_neuronas_reales():
    """Importa las neuronas reales del sistema principal (LC_STM.red_neuronal).

    Devuelve (clase_rf_en, clase_rf_sl, motivo). Si numpy o el paquete no están
    disponibles, devuelve (None, None, motivo) sin lanzar excepción.
    """
    try:
        import numpy  # noqa: F401
    except Exception as error:
        return None, None, f"numpy no disponible: {error}"
    try:
        from LC_STM.red_neuronal.RF_EN.RFEN1_RN_1 import NeuronaRefuerzoQLearning
        from LC_STM.red_neuronal.RF_SL.RFSL1.RF_SL1_1 import GradientBoostingOptimizer
        return NeuronaRefuerzoQLearning, GradientBoostingOptimizer, ""
    except Exception as error:
        return None, None, f"LC_STM.red_neuronal no importable: {error}"



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
        self.neurona_rf_en: Any = None
        self.neurona_rf_sl: Any = None
        self._reales_cargadas: bool = False
        self._asegurar_src_en_path()

    @staticmethod
    def _asegurar_src_en_path() -> None:
        """Garantiza que el src principal esté en sys.path para importar LC_STM."""
        import sys
        from pathlib import Path
        src = Path(__file__).resolve().parent.parent
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))

    def _cargar_neuronas_reales(self) -> bool:
        """Instancia perezosamente las neuronas reales RF_EN y RF_SL (una vez)."""
        global NEURONAS_REALES_DISPONIBLE, _MOTIVO_NEURONAS
        if self._reales_cargadas:
            return self.neurona_rf_en is not None
        self._reales_cargadas = True
        cls_en, cls_sl, motivo = _importar_neuronas_reales()
        if cls_en is None or cls_sl is None:
            _MOTIVO_NEURONAS = motivo
            NEURONAS_REALES_DISPONIBLE = False
            return False
        try:
            self.neurona_rf_en = cls_en(input_size=16, output_size=4, nombre="RF_EN_refuerzo")
            self.neurona_rf_en.inicializar_pesos()
            self.neurona_rf_sl = cls_sl(input_size=4, output_size=1, nombre="RF_SL_refuerzo")
            NEURONAS_REALES_DISPONIBLE = True
            _MOTIVO_NEURONAS = ""
            return True
        except Exception as error:
            self.neurona_rf_en = None
            self.neurona_rf_sl = None
            _MOTIVO_NEURONAS = f"fallo al instanciar neuronas reales: {error}"
            NEURONAS_REALES_DISPONIBLE = False
            return False

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

    def persistir_pesos_en_psnrl(self, etiqueta: str = "checkpoint", psnrl_dir: Any = None):
        import json
        from pathlib import Path
        if psnrl_dir is None:
            try:
                from STM_CH.STM_herramientas.rutas import PSNRL_DIR
            except ImportError:
                PSNRL_DIR = Path("STM_CH") / "PSNRL"
        else:
            PSNRL_DIR = Path(psnrl_dir)
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
        if self._reales_cargadas and self.neurona_rf_en is not None:
            try:
                self.neurona_rf_en.guardar(str(PSNRL_DIR / f"{etiqueta}_rf_en.json"))
            except Exception:
                pass
        if self._reales_cargadas and self.neurona_rf_sl is not None:
            try:
                self.neurona_rf_sl.save(str(PSNRL_DIR / f"{etiqueta}_rf_sl.pkl"))
            except Exception:
                pass
        return (npz_p, js_p)

    def aplicar_recompensa(self, recompensa: float, estado: int, accion: int,
                           siguiente_estado: int, terminado: bool = False,
                           features: Optional[List[float]] = None) -> Dict[str, Any]:
        """Aprendizaje por recompensa con las neuronas reales RF_EN y RF_SL.

        RF_EN (Q-Learning) actualiza su tabla Q con la transición; RF_SL
        (Gradient Boosting) aprende a predecir la recompensa desde el estado.
        El delta aprendido se pliega en el ledger de 50 neuronas y la deriva.
        Nunca lanza excepción: si las neuronas reales no están disponibles,
        devuelve ``reales=False`` para que el llamador no anuncie éxito falso.
        """
        resumen: Dict[str, Any] = {"reales": False, "delta_q": 0.0, "loss_sl": 0.0, "norma": 0.0}
        if not self._cargar_neuronas_reales():
            resumen["motivo"] = _MOTIVO_NEURONAS
            return resumen
        try:
            import numpy as np
            r = float(recompensa)
            s = int(estado) % self.neurona_rf_en.input_size
            a = int(accion) % self.neurona_rf_en.output_size
            ns = int(siguiente_estado) % self.neurona_rf_en.input_size
            delta = self.neurona_rf_en.actualizar_q_value(s, a, r, ns, terminado)
            resumen["delta_q"] = float(delta)
            if features is None:
                features = [s / 15.0, r, a / 3.0, 0.0]
            feat = [float(x) for x in features][:self.neurona_rf_sl.input_size]
            feat += [0.0] * (self.neurona_rf_sl.input_size - len(feat))
            entrada = np.asarray([feat], dtype=np.float32)
            objetivo = np.asarray([[r]], dtype=np.float32)
            paso = self.neurona_rf_sl.train_step(entrada, objetivo)
            resumen["loss_sl"] = float(paso.get("loss_after", 0.0))
            resumen["norma"] = self._plegar_en_ledger(float(delta), r)
            resumen["reales"] = True
            self.pasos_sesion += 1
            return resumen
        except Exception as error:
            resumen["motivo"] = f"fallo en aplicar_recompensa: {error}"
            return resumen

    def _plegar_en_ledger(self, delta_q: float, recompensa: float) -> float:
        """Pliega la señal aprendida en las familias RF_EN (10-19) y RF_SL (20-29)."""
        try:
            import numpy as np
            senal_en = float(np.tanh(delta_q)) * 0.01
        except Exception:
            senal_en = math.tanh(delta_q) * 0.01
        senal_sl = float(recompensa) * 0.005
        for i in range(10, 20):
            self.neuronas[i]["peso"] = round(float(self.neuronas[i]["peso"] + senal_en), 5)
        for i in range(20, 30):
            self.neuronas[i]["peso"] = round(float(self.neuronas[i]["peso"] + senal_sl), 5)
        norma = abs(senal_en) * 10.0 + abs(senal_sl) * 10.0
        self.deriva_acumulada = round(self.deriva_acumulada + norma * 0.001, 6)
        return round(norma, 5)

    def cargar_pesos(self, etiqueta: str = "refuerzo_lucia", psnrl_dir: Any = None) -> bool:
        """Recupera el ledger y el estado de las neuronas reales del PSNRL principal."""
        from pathlib import Path
        if psnrl_dir is None:
            try:
                from STM_CH.STM_herramientas.rutas import PSNRL_DIR
            except ImportError:
                PSNRL_DIR = Path(__file__).resolve().parent.parent / "STM_CH" / "PSNRL"
        else:
            PSNRL_DIR = Path(psnrl_dir)
        npz_p = PSNRL_DIR / f"{etiqueta}.npz"
        js_p = PSNRL_DIR / f"{etiqueta}.json"
        if not npz_p.exists():
            return False
        try:
            import json
            import numpy as np
            with np.load(str(npz_p)) as datos:
                pesos = datos["pesos"].tolist()
            for neurona, peso in zip(self.neuronas, pesos):
                neurona["peso"] = round(float(peso), 5)
            if js_p.exists():
                meta = json.loads(js_p.read_text(encoding="utf-8"))
                self.deriva_acumulada = float(meta.get("deriva", 0.0))
            self._cargar_estado_reales(PSNRL_DIR, etiqueta)
            return True
        except Exception:
            return False

    def _cargar_estado_reales(self, psnrl_dir: Any, etiqueta: str) -> None:
        rf_en_p = psnrl_dir / f"{etiqueta}_rf_en.json"
        rf_sl_p = psnrl_dir / f"{etiqueta}_rf_sl.pkl"
        if not (rf_en_p.exists() or rf_sl_p.exists()):
            return
        if not self._cargar_neuronas_reales():
            return
        if rf_en_p.exists() and self.neurona_rf_en is not None:
            try:
                self.neurona_rf_en = type(self.neurona_rf_en).cargar(str(rf_en_p))
            except Exception:
                pass
        if rf_sl_p.exists() and self.neurona_rf_sl is not None:
            try:
                self.neurona_rf_sl.load(str(rf_sl_p))
            except Exception:
                pass

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
