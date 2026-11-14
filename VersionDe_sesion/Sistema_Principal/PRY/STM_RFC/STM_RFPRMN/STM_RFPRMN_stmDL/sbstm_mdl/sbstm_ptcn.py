"""Motor de partición de módulos que superan el tope de líneas.

Código extraído de ``stm_particion.py`` (líneas 40–158) y agrupado en la clase
``Particionador``. ``stm_particion`` re-exporta sus métodos para conservar la
API histórica (``separar_unidades``, ``plan_de_particion``, ``BOOTSTRAP``…).

Igual que el resto de ``sbstm_mdl``, usa imports absolutos al paquete y añade
la raíz al ``sys.path`` para funcionar también en ejecución directa (F5).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

#: Directorio que contiene el paquete (``.../STM_RFPRMN``).
_RAIZ_PAQUETE = Path(__file__).resolve().parents[2]
if str(_RAIZ_PAQUETE) not in sys.path:
    sys.path.insert(0, str(_RAIZ_PAQUETE))

from STM_RFPRMN_stmDL.stm_base import ErrorProyecto  # noqa: E402
from STM_RFPRMN_stmDL.stm_fragmentos import LIMITE_LINEAS_REFACTOR  # noqa: E402

__all__ = ["Particionador"]


class Particionador:
    """Analiza un módulo y calcula cómo repartirlo sin romper sus unidades.

    Agrupa en una sola clase los helpers que antes eran funciones sueltas.
    Todos los métodos son estáticos: no hay estado que instanciar y la llamada
    cuesta lo mismo que la de una función de módulo.
    """

    #: Líneas que ocupa el bloque de importación de subsistemas en la parte 1.
    BOOTSTRAP = 8

    @staticmethod
    def _texto(contenido: str, nodo) -> str:
        """Código fuente exacto de un nodo (sin líneas vacías en los extremos)."""
        return (ast.get_source_segment(contenido, nodo) or "").strip("\n")

    @staticmethod
    def _es_docstring(nodo) -> bool:
        """True si el nodo es el docstring del módulo."""
        return (isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Constant)
                and isinstance(nodo.value.value, str))

    @staticmethod
    def _es_import(nodo) -> bool:
        """True para ``import`` y ``from ... import ...``."""
        return isinstance(nodo, (ast.Import, ast.ImportFrom))

    @staticmethod
    def _es_cabecera(nodo) -> bool:
        """True si el nodo pertenece a la cabecera (docstring o import)."""
        return (Particionador._es_docstring(nodo)
                or Particionador._es_import(nodo))

    @staticmethod
    def _nombre(nodo) -> str:
        """Nombre legible de una unidad (o ``bloque_<línea>`` si es una asignación)."""
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return nodo.name
        return f"bloque_{getattr(nodo, 'lineno', 0)}"

    @staticmethod
    def _tipo(nodo) -> str:
        """Clase, función o bloque."""
        if isinstance(nodo, ast.ClassDef):
            return "clase"
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return "funcion"
        return "bloque"

    @staticmethod
    def separar_unidades(contenido: str) -> tuple[str, list[dict]]:
        """Devuelve ``(cabecera, unidades)``; lanza si no es Python válido."""
        try:
            arbol = ast.parse(contenido)
        except SyntaxError as error:
            raise ErrorProyecto(
                f"Sintaxis inválida (línea {error.lineno}: {error.msg}).")
        cabecera: list[str] = []
        unidades: list[dict] = []
        for nodo in arbol.body:
            if Particionador._es_cabecera(nodo):
                cabecera.append(Particionador._texto(contenido, nodo))
                continue
            texto = Particionador._texto(contenido, nodo)
            unidades.append({"nombre": Particionador._nombre(nodo),
                             "tipo": Particionador._tipo(nodo),
                             "lineas": len(texto.splitlines()), "texto": texto})
        return "\n".join(cabecera), unidades

    @staticmethod
    def _imports(cabecera: str) -> list[str]:
        """Líneas de import de una cabecera, sin duplicados."""
        vistas: list[str] = []
        for linea in cabecera.splitlines():
            limpia = linea.strip()
            if limpia.startswith(("import ", "from ")) and limpia not in vistas:
                vistas.append(limpia)
        return vistas

    @staticmethod
    def _empaquetar(cabecera: str, unidades: list[dict], limite: int,
                    reserva: int = 8) -> list[list[dict]]:
        """Reparte las unidades en partes que quepan en ``limite`` líneas."""
        coste = len(cabecera.splitlines()) + 4
        partes: list[list[dict]] = [[]]
        usadas = 0
        for unidad in unidades:
            tope = limite - coste - (reserva if len(partes) == 1 else 0)
            extra = unidad["lineas"] + 2
            if partes[-1] and usadas + extra > tope:
                partes.append([])
                usadas = 0
            partes[-1].append(unidad)
            usadas += extra
        return partes

    @staticmethod
    def plan_de_particion(contenido: str,
                          limite: int = LIMITE_LINEAS_REFACTOR) -> dict:
        """Calcula cómo quedaría el módulo sin escribir nada."""
        cabecera, unidades = Particionador.separar_unidades(contenido)
        if not unidades:
            raise ErrorProyecto("El archivo no tiene clases ni funciones que repartir.")
        total = len(contenido.splitlines())
        if total <= limite:
            return {"necesita": False, "total": total, "cabecera": cabecera,
                    "unidades": unidades, "partes": [unidades], "problemas": []}
        partes = Particionador._empaquetar(cabecera, unidades, limite)
        reserva = 7 + max(1, len(partes) - 1)
        if reserva != Particionador.BOOTSTRAP:
            partes = Particionador._empaquetar(cabecera, unidades, limite, reserva)
        coste = len(cabecera.splitlines()) + 4
        problemas = [u["nombre"] for parte in partes for u in parte
                     if u["lineas"] + coste > limite]
        return {"necesita": True, "total": total, "cabecera": cabecera,
                "unidades": unidades, "partes": partes, "problemas": problemas}

    @staticmethod
    def _bloque_imports(stem: str, indices: list[int],
                        carpeta_rel: str | None = None) -> str:
        """Re-exporta las partes; añade ``sys.path`` si están en otra carpeta."""
        lineas = ["", "# --- Partes/subsistemas extraídos automáticamente ---"]
        if carpeta_rel:
            lineas += ["import sys as _sys",
                       "from pathlib import Path as _Path",
                       f'_partes = _Path(__file__).resolve().parent / "{carpeta_rel}"',
                       "if _partes.is_dir() and str(_partes) not in _sys.path:",
                       "    _sys.path.insert(0, str(_partes))"]
        lineas += [f"from {stem}_p{indice} import *  # noqa: F401,F403"
                   for indice in indices]
        return "\n".join(lineas) + "\n"

    @staticmethod
    def _componente(cabecera: str, unidades: list[dict], stem: str,
                    indices: list[int], carpeta_rel: str | None = None) -> str:
        """Cabecera + unidades + re-export de las partes."""
        piezas = [cabecera] if cabecera else []
        piezas += [unidad["texto"] for unidad in unidades]
        texto = "\n\n\n".join(piezas).rstrip() + "\n"
        if indices:
            texto += Particionador._bloque_imports(stem, indices, carpeta_rel)
        return texto


if __name__ == "__main__":
    # Ejecución directa (F5 / python sbstm_ptcn.py): confirma que carga.
    print(f"sbstm_ptcn OK · {__all__[0]} · "
          f"tope {LIMITE_LINEAS_REFACTOR} líneas")
