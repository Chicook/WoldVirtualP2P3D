"""Hook de arranque *fail-closed* de STM_DEF.

Antes de que arranque el visor (``VSC#``) o el punto de entrada de ``STM_HRTS``
se ejecuta aqui un escaneo estatico del arbol + la verificacion del sello de
integridad. El criterio es *fail-closed*: si aparece un hallazgo ALTA, si el
sello tiene la firma manipulada o si el arbol cambio respecto al sello, el
arranque se **DETIENE** y se avisa.

Es el mismo paso del dropper, invertido: aquel no comprobaba nada antes de
ejecutar; aqui no se arranca nada sin comprobarlo antes. El modulo solo lee y
decide: nunca modifica, descarga ni ejecuta nada.

Integracion (sin tocar el visor ni ``STM_HRTS``), desde otro punto de entrada:

    from STM_HRTS.STM_DEF.arranque import arranque_seguro

    resultado = arranque_seguro()
    if not resultado["permite"]:
        raise SystemExit("STM_DEF detuvo el arranque: " + "; ".join(resultado["bloqueos"]))

y desde la consola:

    python -m STM_HRTS.STM_DEF arranque     (exit 0 si arranca, 1 si lo detiene)
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

from . import SRC_DIR, deteccion, integridad
from .modelos import ALTA


def arranque_seguro(raices: Optional[Iterable[Path]] = None) -> Dict[str, object]:
    """Comprueba escaneo + integridad y decide si el arranque puede continuar.

    Devuelve ``permite=True`` solo si no hay ningun bloqueo. El detalle incluye
    el resumen del escaneo (hallazgos por severidad y veredicto) y el estado del
    sello, para que el aviso sea accionable. La ausencia de sello no bloquea:
    no puede exigirse una linea base que aun no existe.
    """
    objetivo = [Path(r) for r in raices] if raices is not None else [SRC_DIR]
    hallazgos = deteccion.escanear_arbol(objetivo)
    por_severidad: Dict[str, int] = {}
    for hallazgo in hallazgos:
        por_severidad[hallazgo.severidad] = por_severidad.get(hallazgo.severidad, 0) + 1
    resumen_escaneo = deteccion.resumen(hallazgos)

    bloqueos: List[str] = []
    detalle: Dict[str, object] = {
        "escanear": {
            "hallazgos": len(hallazgos),
            "por_severidad": por_severidad,
            "veredicto": resumen_escaneo["veredicto"],
        }
    }
    if por_severidad.get(ALTA):
        bloqueos.append(f"{por_severidad[ALTA]} hallazgo(s) ALTA en el escaneo")

    bloqueos_integridad, detalle_integridad = integridad.bloqueos_sello(integridad.SELLO_PATH)
    detalle["integridad"] = detalle_integridad
    bloqueos.extend(bloqueos_integridad)

    return {
        "permite": not bloqueos,
        "bloqueos": bloqueos,
        "veredicto": resumen_escaneo["veredicto"],
        "detalle": detalle,
    }


def bloquea(raices: Optional[Iterable[Path]] = None) -> bool:
    """Atajo booleano del hook: ``True`` si el arranque debe detenerse."""
    return not arranque_seguro(raices)["permite"]


__all__ = ["arranque_seguro", "bloquea"]
