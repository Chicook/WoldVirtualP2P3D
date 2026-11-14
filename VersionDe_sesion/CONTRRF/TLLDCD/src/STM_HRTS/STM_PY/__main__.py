"""Consola del taller WoldVirtualP2P3D — punto de entrada unico.

TODO el trabajo de arranque se hace desde ESTE fichero:

  1. Localiza la raiz ``src/`` por la posicion real del fichero, sin imports
     relativos (que revientan con "attempted relative import with no known
     parent package" si el fichero se ejecuta suelto, sin paquete padre).
  2. Anade ``src/`` a ``sys.path`` y carga el motor de consola real
     (``STM_HRTS.utils.add_utils.__main__``), con las ordenes ``rutas``,
     ``verificar``, ``herramientas`` y ``ejecutar``.
  3. Antes de delegar en el motor, corre el hook *fail-closed* de STM_DEF
     (``STM_HRTS.STM_DEF.arranque``): escaneo + integridad; un hallazgo ALTA o
     un sello manipulado detienen el arranque.
  4. Si se lanza sin argumentos muestra la ayuda en vez de fallar.

Arranques soportados:

    python STM_HRTS/STM_PY/__main__.py verificar
    python STM_HRTS/STM_PY/__main__.py            (muestra la ayuda)
    python -m STM_HRTS.STM_PY verificar
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

#: Motor de consola real (implementa las ordenes).
MODULO_CLI: str = "STM_HRTS.utils.add_utils.__main__"
#: Marca que identifica la raiz del arbol (src/) subiendo directorios.
MARCA_RAIZ: tuple[str, ...] = ("STM_HRTS", "utils", "add_utils")
#: Ordenes que expone la consola (para ayuda y pruebas).
ORDENES: tuple[str, ...] = ("rutas", "verificar", "herramientas", "ejecutar")


class ConsolaHRTS:
    """Hace todo el trabajo: localiza el arbol, carga el motor y lo ejecuta.

    El motor vive anidado en ``STM_HRTS/utils/add_utils``; esta clase evita
    los imports relativos calculando la raiz ``src/`` desde la ubicacion real
    de este fichero, de modo que la consola funciona igual si se ejecuta
    directamente, con ``-m`` o importada desde otro sitio.
    """

    def __init__(self, modulo_cli: str = MODULO_CLI) -> None:
        self.modulo_cli = modulo_cli
        self._motor: ModuleType | None = None

    # ── localizacion del arbol ───────────────────────────────────────────
    @staticmethod
    def raiz_src() -> Path:
        """Raiz ``src/``: primer ancestro que contiene ``STM_HRTS/utils/add_utils``."""
        for padre in Path(__file__).resolve().parents:
            if padre.joinpath(*MARCA_RAIZ).is_dir():
                return padre
        # Respaldo: STM_PY/__main__.py -> STM_PY -> STM_HRTS -> src
        return Path(__file__).resolve().parents[2]

    def preparar(self) -> Path:
        """Anade ``src/`` a ``sys.path`` (si falta) y devuelve la raiz."""
        raiz = self.raiz_src()
        if str(raiz) not in sys.path:
            sys.path.insert(0, str(raiz))
        return raiz

    # ── carga del motor de consola ───────────────────────────────────────
    @property
    def motor(self) -> ModuleType:
        """Modulo CLI real, cargado una sola vez (cachea en ``_motor``)."""
        if self._motor is None:
            self.preparar()
            self._motor = importlib.import_module(self.modulo_cli)
        return self._motor

    def ordenes(self) -> list[str]:
        """Devuelve las ordenes disponibles."""
        return list(ORDENES)

    def ayuda(self) -> int:
        """Muestra la ayuda del motor de consola y devuelve 0."""
        self.motor.construir_parser().print_help()
        return 0

    # ── ejecucion ────────────────────────────────────────────────────────
    def ejecutar(self, argv: list[str] | None = None) -> int:
        """Ejecuta la consola; sin argumentos muestra la ayuda, no un error.

        Antes de delegar en el motor corre el hook *fail-closed* de STM_DEF
        (escaneo + integridad): si detecta un hallazgo **ALTA** o un sello
        manipulado, detiene el arranque y devuelve 1.
        """
        argumentos = list(sys.argv[1:] if argv is None else argv)
        if not argumentos:
            return self.ayuda()
        self.preparar()
        from STM_HRTS.STM_DEF.arranque import bloquea

        if bloquea():
            print("[STM_PY] STM_DEF detuvo el arranque: hallazgo ALTA o sello manipulado.",
                  file=sys.stderr)
            return 1
        return int(self.motor.main(argumentos))


def main(argv: list[str] | None = None) -> int:
    """Atajo funcional: ``ConsolaHRTS().ejecutar(argv)``."""
    return ConsolaHRTS().ejecutar(argv)


if __name__ == "__main__":
    raise SystemExit(main())