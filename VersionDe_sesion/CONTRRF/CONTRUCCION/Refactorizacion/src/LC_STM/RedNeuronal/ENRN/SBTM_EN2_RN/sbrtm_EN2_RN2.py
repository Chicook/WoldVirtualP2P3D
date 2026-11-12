"""Modulo autocontenido de creacion de estructura de codigo (SBTM_EN2_RN).

Unifica la subrutina NeuronaCreativa en una sola clase importable con clases
anidadas:
- Matematica: codificacion Xavier, proyeccion forward, afinidad por coseno,
  impulso creativo (balance de varianza) y entropia de Shannon.
- Maquina: carga perezosa de la maquina de comandos RFPRMN y orquestacion de
  analizar / planificar / crear / elegir / entrenar estructuras de codigo.

La clase envuelve una neurona Xavier (NeuronaEntradaXavier) y delega toda la
matematica en su arquitectura (input_size, forward, varianza) en tiempo de
ejecucion, sin importar RFPRMN hasta que se invoca un metodo.
"""

import math
from functools import lru_cache
from typing import Any, Dict, List, Optional

import numpy as np

_PAQUETE_RFPRMN: Optional[Any] = None


def _localizar_rfprmn() -> str:
    """Directorio de RFPRMN (contiene RFPRMN.py y STM_RFPRMN_stmDL/)."""
    import os as _os
    d = _os.path.dirname(_os.path.abspath(__file__))
    while True:
        for rel in ("", "STM_RFPRMN", "STM_RFC/STM_RFPRMN"):
            cand = d if not rel else _os.path.join(d, rel)
            if _os.path.isfile(_os.path.join(cand, "RFPRMN.py")) and \
                    _os.path.isdir(_os.path.join(cand, "STM_RFPRMN_stmDL")):
                return cand
        padre = _os.path.dirname(d)
        if padre == d:
            return ""
        d = padre


def _maquina():
    """Importa una sola vez el paquete STM_RFPRMN_stmDL (cache de modulo)."""
    global _PAQUETE_RFPRMN
    if _PAQUETE_RFPRMN is None:
        import importlib
        import sys as _sys
        try:
            _PAQUETE_RFPRMN = importlib.import_module("STM_RFPRMN_stmDL")
        except ImportError:
            raiz = _localizar_rfprmn()
            if raiz and raiz not in _sys.path:
                _sys.path.insert(0, raiz)
            _PAQUETE_RFPRMN = importlib.import_module("STM_RFPRMN_stmDL")
        importlib.import_module("STM_RFPRMN_stmDL.stm_creacion")
        importlib.import_module("STM_RFPRMN_stmDL.stm_analisis")
        importlib.import_module("STM_RFPRMN_stmDL.stm_mn")
    return _PAQUETE_RFPRMN


class NeuronaCreativa:
    """Subrutina anidada que crea estructura de codigo con la maquina RFPRMN.

    Uso:
        creativa = NeuronaCreativa(neurona_xavier)
        creativa.crear_estructura("un modulo de cache LRU", "cache.py")
    """

    def __init__(self, neurona: Any) -> None:
        self._neurona = neurona

    # ----------------------------------------------------------
    # Matematica Xavier
    # ----------------------------------------------------------
    class Matematica:
        """Codificacion y proyeccion Xavier de texto en vectores."""

        @staticmethod
        @lru_cache(maxsize=4096)
        def hash_token(token: str) -> int:
            """Hash FNV-1a determinista de un token (32 bits)."""
            h = 2166136261
            for c in str(token):
                h = ((h ^ ord(c)) * 16777619) & 0xFFFFFFFF
            return h

        @classmethod
        def vector(cls, neurona: Any, texto: str) -> np.ndarray:
            """Vector determinista de input_size (bolsa de tokens normalizada)."""
            n = max(1, int(neurona.input_size))
            v = np.zeros(n, dtype=np.float64)
            for token in str(texto).split():
                h = cls.hash_token(token)
                v[h % n] += 1.0 if h >= 0 else -1.0
            norma = float(np.linalg.norm(v))
            if norma > 0.0:
                v /= norma
            return v

        @classmethod
        def proyectar(cls, neurona: Any, texto: str) -> np.ndarray:
            """Proyeccion Xavier del texto (forward de la neurona)."""
            return np.asarray(neurona.forward(cls.vector(neurona, texto))).reshape(-1)

        @classmethod
        def similitud(cls, neurona: Any, a: str, b: str) -> float:
            """Coseno entre las proyecciones de dos textos (afinidad estructural)."""
            va = cls.proyectar(neurona, a).astype(np.float64)
            vb = cls.proyectar(neurona, b).astype(np.float64)
            den = float(np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-12
            return float(np.dot(va, vb) / den)

        @classmethod
        def impulso_creativo(cls, neurona: Any) -> float:
            """Temperatura en [0.2, 0.9] derivada del balance Xavier.

            ratio~1 (varianza equilibrada) -> determinista; lejos -> creativo.
            """
            if neurona.pesos is None:
                neurona.inicializar_pesos()
            ratio = neurona._ratio_varianza()
            desvio = abs(math.log(max(ratio, 1e-6)))
            return float(np.clip(0.2 + 0.7 * min(desvio, 1.0), 0.2, 0.9))

        @classmethod
        def entropia(cls, neurona: Any, texto: str) -> float:
            """Entropia de Shannon normalizada de la proyeccion (en [0, 1])."""
            z = cls.proyectar(neurona, texto).astype(np.float64)
            e = np.exp(z - np.max(z))
            p = e / (e.sum() + 1e-12)
            p = p[p > 1e-12]
            if p.size == 0:
                return 0.0
            return float(-(p * np.log(p)).sum() / max(math.log(p.size), 1e-12))

    # ----------------------------------------------------------
    # Maquina de comandos RFPRMN
    # ----------------------------------------------------------
    class Maquina:
        """Orquestacion de RFPRMN para crear estructura de codigo."""

        @staticmethod
        def analizar_estructura(ruta: str) -> Dict[str, Any]:
            """Analisis estatico + plan de refactor de un archivo existente."""
            import os as _os
            from pathlib import Path
            pkg = _maquina()
            objetivo = Path(_os.path.expanduser(str(ruta))).resolve()
            analisis = pkg.stm_analisis.analizar_archivo_local(objetivo)
            return {"ruta": str(objetivo),
                    "analisis": analisis.a_dict(),
                    "plan": pkg.stm_analisis.crear_plan_refactorizacion(analisis)}

        @staticmethod
        def plan_estructura(descripcion: str, ruta: str,
                            lenguaje: str = "python") -> str:
            """Diagnostico/plan que propone la estructura del codigo a crear."""
            return _maquina().stm_creacion.diagnosticar(descripcion, ruta, lenguaje)

        @staticmethod
        def crear_estructura(neurona: Any, descripcion: str, ruta: str,
                             lenguaje: str = "python") -> Dict[str, Any]:
            """Crea ``ruta`` desde ``descripcion`` sin prompts interactivos."""
            import os as _os
            from pathlib import Path
            try:
                pkg = _maquina()
                destino = Path(_os.path.expandvars(_os.path.expanduser(str(ruta)))).resolve()
                impulso = NeuronaCreativa.Matematica.impulso_creativo(neurona)
                diagnostico = pkg.stm_creacion.diagnosticar(descripcion, destino, lenguaje)
                codigo = pkg.stm_creacion.generar_codigo(descripcion, diagnostico, destino, lenguaje)
                codigo = pkg.stm_creacion.validar_codigo(codigo, destino)
                pkg.stm_creacion.escribir_texto_atomico(destino, codigo)
                return {"ok": True, "ruta": str(destino),
                        "lineas": len(codigo.splitlines()), "impulso": impulso}
            except Exception as error:  # noqa: BLE001 - resultado degradado
                return {"ok": False, "error": f"{type(error).__name__}: {error}"}

        @staticmethod
        def elegir_estructura(neurona: Any, descripcion: str,
                              candidatos: List[str]) -> Dict[str, Any]:
            """Elige el candidato mas afin por coseno proyectado."""
            puntajes = [(c, NeuronaCreativa.Matematica.similitud(neurona, descripcion, c))
                        for c in candidatos]
            mejor = max(puntajes, key=lambda t: t[1]) if puntajes else ("", 0.0)
            return {"mejor": mejor[0], "puntajes": puntajes}

        @staticmethod
        def entrenar_estructura(ruta: str = "") -> Dict[str, Any]:
            """Envia la estructura creada a la red neuronal (comando lc entrenar)."""
            try:
                return _maquina().stm_mn.RFPRMN().lc_entrenar(ruta)
            except Exception as error:  # noqa: BLE001
                return {"ok": False, "error": f"{type(error).__name__}: {error}"}

    # ----------------------------------------------------------
    # Metodos de instancia que delegan en las clases anidadas
    # ----------------------------------------------------------
    @property
    def maquina(self) -> Any:
        """Paquete STM_RFPRMN_stmDL cargado de forma perezosa."""
        return _maquina()

    def vector(self, texto: str) -> np.ndarray:
        return self.Matematica.vector(self._neurona, texto)

    def proyectar(self, texto: str) -> np.ndarray:
        return self.Matematica.proyectar(self._neurona, texto)

    def similitud(self, a: str, b: str) -> float:
        return self.Matematica.similitud(self._neurona, a, b)

    @property
    def impulso(self) -> float:
        """Impulso creativo actual derivado del balance Xavier."""
        return self.Matematica.impulso_creativo(self._neurona)

    def impulso_creativo(self) -> float:
        return self.impulso

    def entropia(self, texto: str) -> float:
        return self.Matematica.entropia(self._neurona, texto)

    def analizar_estructura(self, ruta: str) -> Dict[str, Any]:
        return self.Maquina.analizar_estructura(ruta)

    def plan_estructura(self, descripcion: str, ruta: str,
                        lenguaje: str = "python") -> str:
        return self.Maquina.plan_estructura(descripcion, ruta, lenguaje)

    def crear_estructura(self, descripcion: str, ruta: str,
                         lenguaje: str = "python") -> Dict[str, Any]:
        return self.Maquina.crear_estructura(self._neurona, descripcion, ruta, lenguaje)

    def elegir_estructura(self, descripcion: str,
                          candidatos: List[str]) -> Dict[str, Any]:
        return self.Maquina.elegir_estructura(self._neurona, descripcion, candidatos)

    def entrenar_estructura(self, ruta: str = "") -> Dict[str, Any]:
        return self.Maquina.entrenar_estructura(ruta)


__all__ = ["NeuronaCreativa"]
