"""Puente para que LucIA use los comandos de RFPRMN **sin humano**.

LucIA no puede quedarse esperando un ``s/n``: este agente sustituye la
confirmación interactiva por una **decisión matemática** y ejecuta los comandos
en orden lógico. La decisión combina cinco señales normalizadas:

- **déficit**: ``(100 - puntuación_deuda) / 100`` del archivo.
- **urgencia**: 1.0 si supera el tope de 450 líneas, 0.5 si pasa de 300.
- **éxito previo**: calidad media de esa acción en esta sesión (0.5 al empezar).
- **coste**: lo que tarda y lo que toca (partir < probar < comentar < informe < refactorizar).
- **red**: predicción de LucIA según lo aprendido (``seq2seq``/pasos).

``utilidad = 0.35·déficit + 0.25·urgencia + 0.10·éxito + 0.10·(1 - coste) +
0.20·red`` y se actúa si ``utilidad >= umbral``.

La implementación vive ahora en ``sbstm_mdl/sbstm_agnt.py``, que compone la
base de ``sbstm_mdl/sbrtstm/snrtstm_sbstm_agnt.py`` con ``Ejecucion`` y
``Ciclo``. Aquí se re-exporta para conservar la API pública.
"""
from __future__ import annotations

import sys
from pathlib import Path

#: Directorio que contiene el paquete (``.../STM_RFPRMN``). Se añade al path
#: para que los imports absolutos resuelvan también en ejecución directa (F5).
_RAIZ_PAQUETE = Path(__file__).resolve().parents[1]
if str(_RAIZ_PAQUETE) not in sys.path:
    sys.path.insert(0, str(_RAIZ_PAQUETE))

from STM_RFPRMN_stmDL.sbstm_mdl.sbstm_agnt import (  # noqa: E402,F401
    ACCIONES, COSTES, PESOS, TIEMPOS, AgenteRFPRMN,
)

if __name__ == "__main__":
    # Ejecución directa (F5 / python stm_agente.py): confirma que carga.
    print(f"stm_agente OK · {AgenteRFPRMN.__name__} · "
          f"{len(ACCIONES)} acciones")
