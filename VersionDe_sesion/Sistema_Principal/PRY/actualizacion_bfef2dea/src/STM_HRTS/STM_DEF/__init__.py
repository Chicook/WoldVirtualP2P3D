"""STM_DEF — subsistema defensivo del taller WoldVirtualP2P3D.

Hace exactamente lo contrario que el dropper "EtherHiding" hallado en la zona
``PRY`` (evidencia: ``actualizacion_aeef1149`` y ``actualizacion_cae205a3``).
Aquel loader:

  1. consultaba ``api.ethplorer.io`` para localizar una transaccion de su
     cartera C2,
  2. recuperaba el campo ``input`` de la transaccion por JSON-RPC
     (``ethereum.publicnode.com``),
  3. lo decodificaba de hex a JavaScript,
  4. lo ejecutaba con ``node`` en un fichero temporal,
  5. todo en silencio y sin dejar rastro.

STM_DEF invierte cada paso:

  1. **bloquea** los canales C2 (sinkhole DNS en ``hosts`` + reglas de
     firewall de salida) para que el payload no se pueda descargar;
  2. **vigila** las conexiones salientes reales y avisa de cualquier intento;
  3. **detecta** estaticamente el patron del dropper antes de que se ejecute;
  4. **sella** la integridad del arbol para delatar modificaciones silenciosas;
  5. **conserva** la evidencia (nunca borra) y falla de forma visible.

El paquete vive en ``STM_HRTS/STM_DEF`` y reutiliza el registro canonico de
rutas (``STM_HRTS/utils/add_utils/rutas.py``) para no rellenar rutas a mano.
"""
from __future__ import annotations

import sys
from pathlib import Path

#: Marca que identifica la raiz ``src/`` subiendo directorios.
MARCA_RAIZ: tuple[str, ...] = ("STM_HRTS", "utils", "add_utils")


def anclar_src() -> Path:
    """Devuelve la raiz ``src/`` y la deja disponible en ``sys.path``.

    Permite que el paquete funcione igual ejecutado suelto, con ``-m`` o
    importado desde otro sitio, sin depender de imports relativos rotos.
    """
    raiz: Path | None = None
    for padre in Path(__file__).resolve().parents:
        if padre.joinpath(*MARCA_RAIZ).is_dir():
            raiz = padre
            break
    if raiz is None:
        # Respaldo: STM_DEF -> STM_HRTS -> src
        raiz = Path(__file__).resolve().parents[1]
    if str(raiz) not in sys.path:
        sys.path.insert(0, str(raiz))
    return raiz


#: Raiz ``src/`` del taller (donde vive STM_HRTS, VSC#, MTBGT...).
SRC_DIR: Path = anclar_src()
#: Directorio de este subsistema.
STM_DEF_DIR: Path = Path(__file__).resolve().parent
#: Directorio de estado persistente (clave, sello, politica de blindaje).
ESTADO_DIR: Path = STM_DEF_DIR / "estado"

__all__ = ["SRC_DIR", "STM_DEF_DIR", "ESTADO_DIR", "anclar_src", "MARCA_RAIZ"]
