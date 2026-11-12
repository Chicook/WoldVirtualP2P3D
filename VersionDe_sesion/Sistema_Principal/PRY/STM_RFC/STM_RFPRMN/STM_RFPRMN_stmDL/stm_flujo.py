"""Máquina de estados del comando ``ds ialocal`` (issue #80).

La implementación de ``FlujoRefactorLucIA`` vive ahora en
``sbstm_mdl/sbstm_flj.py`` para mantener pequeño este módulo. Aquí se conserva
la **API pública histórica**: la clase, ``consumir_modelos_por_entorno`` y las
funciones de la shell interactiva (delegadas en ``stm_shell``).
"""
from __future__ import annotations

import sys
from pathlib import Path

#: Directorio que contiene el paquete (``.../STM_RFPRMN``). Se añade al path
#: para que los imports absolutos resuelvan también en ejecución directa.
_RAIZ_PAQUETE = Path(__file__).resolve().parents[1]
if str(_RAIZ_PAQUETE) not in sys.path:
    sys.path.insert(0, str(_RAIZ_PAQUETE))

from STM_RFPRMN_stmDL.sbstm_mdl.sbstm_flj import (  # noqa: E402,F401  (API histórica)
    FlujoRefactorLucIA,
    consumir_modelos_por_entorno,
)

# ── Shell interactiva delegada a ShellInteractiva (stm_shell) ─────────────────
from STM_RFPRMN_stmDL.stm_shell import (  # noqa: E402,F401
    ShellInteractiva,
    cerrar,
    ejecutar_comandos,
    mostrar_menu,
)

if __name__ == "__main__":
    ejecutar_comandos()
