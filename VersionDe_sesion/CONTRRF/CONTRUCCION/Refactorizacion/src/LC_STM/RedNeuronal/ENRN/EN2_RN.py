import numpy as np
import math
import time
import json
from typing import Tuple, Optional, Dict, Any, List, Callable
try:
    from . import NeuronaEntradaBase, LUCIA_CONFIG
except ImportError:
    import numpy as _np_alias  # noqa: F401
    from typing import Tuple as _Tuple, Dict as _Dict, Any as _Any

    LUCIA_CONFIG = {
        "precision": "float32",
        "random_seed": 42,
        "default_learning_rate": 0.001,
    }

try:
    from .SBTM_EN2_RN.sbrtm_EN2_RN1 import (
        NeuronaEntradaBase,
        NeuronaEntradaXavier as _NeuronaEntradaXavierBase,
        LUCIA_CONFIG,
        _dtype,
        _now,
    )
except ImportError:
    import importlib.util as _ilu
    import os as _os
    _base = _os.path.dirname(_os.path.abspath(__file__))
    _spec = _ilu.spec_from_file_location(
        'sbrtm_EN2_RN1', _os.path.join(_base, 'SBTM_EN2_RN', 'sbrtm_EN2_RN1.py'))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    NeuronaEntradaBase = _mod.NeuronaEntradaBase
    _NeuronaEntradaXavierBase = _mod.NeuronaEntradaXavier
    LUCIA_CONFIG = _mod.LUCIA_CONFIG
    _dtype = _mod._dtype
    _now = _mod._now

try:
    from .SBTM_EN2_RN.sbrtm_EN2_RN2 import NeuronaCreativa as _NeuronaCreativa
except ImportError:
    import importlib.util as _ilu2
    import os as _os2
    _base2 = _os2.path.dirname(_os2.path.abspath(__file__))
    _spec2 = _ilu2.spec_from_file_location(
        'sbrtm_EN2_RN2', _os2.path.join(_base2, 'SBTM_EN2_RN', 'sbrtm_EN2_RN2.py'))
    _mod2 = _ilu2.module_from_spec(_spec2)
    _spec2.loader.exec_module(_mod2)
    _NeuronaCreativa = _mod2.NeuronaCreativa


class NeuronaEntradaXavier(_NeuronaEntradaXavierBase):
    """Neurona Xavier: API completa heredada de SBTM_EN2_RN.sbrtm_EN2_RN1."""

    class NeuronaCreativa(_NeuronaCreativa):
        """Neurona creativa: API completa heredada de SBTM_EN2_RN.sbrtm_EN2_RN2."""

        # Creacion de carpetas y adjuncion a la red
        class NeuronaConstructiva:
            """Crea la estructura de carpetas de LCtrabajando y la adjunta a la red.

            Bajo la arquitectura de la neurona, orquesta el comando 'crear carpeta'
            (LCtrabajando/src y sus subcarpetas) y ejecuta el equivalente no
            interactivo del comando 'lc adjuntar' sobre esa ruta.

            Matematica expuesta (delega en NeuronaCreativa sin reimportar nada):
              - similitud(a, b)    : afinidad coseno entre dos rutas/descripciones.
              - impulso_creativo() : temperatura Xavier que guia la construccion.
              - entropia(texto)    : entropia de Shannon de la proyeccion Xavier.
            """

            RUTA_BASE = r"E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\CONTRUCCION\LCtrabajando"
            CARPETAS = [
                "LC_STM", "MTBGT", "SBSTM", "STM_BKCH", "STM_CH",
                "STM_DOC", "STM_JSON", "STM_SGR",
                "STMGNRL", "STMIPFS", "tests", "VSC#",
            ]

            def __init__(self, creativa: "NeuronaCreativa") -> None:
                self._creativa = creativa

            # ----------------------------------------------------------
            # Matematica Xavier delegada (sin reimportar nada del modulo)
            # ----------------------------------------------------------
            def similitud(self, a: str, b: str) -> float:
                """Afinidad coseno entre dos textos/rutas proyectados por Xavier."""
                return self._creativa.similitud(a, b)

            def impulso_creativo(self) -> float:
                """Temperatura Xavier en [0.2, 0.9]: guia si construir de forma
                determinista (ratio~1) o exploratoria (varianza desequilibrada)."""
                return self._creativa.impulso_creativo()

            def entropia(self, texto: str) -> float:
                """Entropia de Shannon normalizada de la proyeccion Xavier."""
                return self._creativa.entropia(texto)

            # ----------------------------------------------------------
            # Orquestacion de carpetas y adjuncion
            # ----------------------------------------------------------
            def crear_carpetas(self) -> Dict[str, Any]:
                """Crea 'src' y las subcarpetas con el comando 'crear carpeta'."""
                try:
                    pkg = self._creativa.maquina
                    src = pkg.stm_mn.crear_carpeta(self.RUTA_BASE, "src")
                    creadas = [pkg.stm_mn.crear_carpeta(src, nombre)
                               for nombre in self.CARPETAS]
                    return {"ok": True, "src": src, "carpetas": creadas,
                            "total": len(creadas) + 1}
                except Exception as error:  # noqa: BLE001 - resultado degradado
                    return {"ok": False, "error": f"{type(error).__name__}: {error}"}

            def adjuntar(self, ruta: str) -> Dict[str, Any]:
                """Ejecuta el equivalente no interactivo de 'lc adjuntar' sobre ``ruta``."""
                import importlib
                from pathlib import Path
                try:
                    pkg = self._creativa.maquina
                    adjuntar = importlib.import_module("STM_RFPRMN_stmDL.stm_adjuntar")
                    archivos = adjuntar.archivos_de_ruta(Path(ruta))
                    entrenados = []
                    for archivo in archivos:
                        res = pkg.stm_mn.RFPRMN().lc_entrenar(str(archivo))
                        entrenados.append({"archivo": archivo.name,
                                           "ok": bool(res.get("ok"))})
                    return {"ok": True, "ruta": ruta, "archivos": len(archivos),
                            "entrenados": entrenados}
                except Exception as error:  # noqa: BLE001
                    return {"ok": False, "error": f"{type(error).__name__}: {error}"}

            def construir(self) -> Dict[str, Any]:
                """Pipeline completo: crea la estructura y adjunta la ruta a la red."""
                paso1 = self.crear_carpetas()
                if not paso1.get("ok"):
                    return paso1
                paso2 = self.adjuntar(paso1["src"])
                return {"ok": bool(paso1.get("ok") and paso2.get("ok")),
                        "src": paso1["src"],
                        "carpetas_creadas": paso1["total"],
                        "lc_adjuntar": paso2}
