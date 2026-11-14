"""Ejecución de las órdenes de construcción de LucIA (STM_MD3).

Ejecuta ``crear carpeta``, ``crear red neuronal``, ``crear mtbgt`` y
``crear todo``: normaliza la orden con ``STM_MD2``, crea la jerarquía con
``STM_MD1`` y la pasa por la red ``LCBS_NEURONAL``.

Las rutas predeterminadas se inyectan desde ``LC_constructor`` para respetar
``runtime.lc_trabajando``. Sin inyección quedan vacías y el destino lo decide
quien ejecuta.

La clase anidada ``ConstructorLucIA.Operaciones`` fusiona las funciones puras
(normalizar rutas y subcarpetas, calcular niveles, escribir archivos) para
reutilizarlas sin repetir trabajo.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from .STM_MD1 import (
    DIM_ENTRADA,
    DIM_SALIDA,
    RUTA_FUENTE_PREDETERMINADA,
    cargar_lcbs_neuronal,
    cargar_modulo_red,
    crear_jerarquia,
    descubrir_subcarpetas_src,
    obtener_clase_constructiva,
    silencio,
)
from .STM_MD2 import (
    COMANDO_CARPETA,
    COMANDO_MTBGT,
    COMANDO_RED,
    COMANDO_TODO,
    COMANDOS,
    NOMBRE_PREDETERMINADO,
    NOMBRE_RED_PREDETERMINADO,
    SUBCARPETAS_MTBGT,
    SUBCARPETAS_RED,
    InterpreteOrden,
)

#: Tercera acción: sin archivos de momento; ``project.godot`` queda para
#: una fase posterior.
ARCHIVOS_MTBGT: tuple[str, ...] = ()

#: Modo limpio: crea solo carpetas, pero conserva el cálculo de la red.
USAR_RED_NEURONAL = True

_RFPRMN: ModuleType | None = None


def _importar_rfprmn() -> ModuleType:
    """Importa la fachada ``RFPRMN`` desde el directorio del proyecto.

    Se hace de forma perezosa para que importar este módulo no dependa de que
    ``STM_RFPRMN`` esté ya en ``sys.path``.
    """
    global _RFPRMN
    if _RFPRMN is not None:
        return _RFPRMN
    try:
        import RFPRMN as modulo
    except ImportError:
        raiz = Path(__file__).resolve().parents[1]
        if str(raiz) not in sys.path:
            sys.path.insert(0, str(raiz))
        import RFPRMN as modulo
    _RFPRMN = modulo
    return _RFPRMN


class ConstructorLucIA:
    """Ejecuta las órdenes de construcción de LucIA.

    Parameters
    ----------
    ruta_red : str | Path, opcional
        Directorio de ``RedNeuronal``; por defecto se autolocaliza.
    maquina : Any, opcional
        Fachada RFPRMN ya construida (útil en pruebas).
    rutas : Mapping[str, str] | Callable[[], Mapping[str, str]], opcional
        Rutas de cada comando. Si es invocable se consulta en cada ejecución,
        de modo que ``runtime.lc_trabajando`` se aplica sin recrear la clase.
    usar_red : bool
        Si es ``False`` crea solo carpetas y omite la red neuronal.
    """

    class Operaciones:
        """Funciones puras compartidas de rutas, jerarquía y archivos."""

        @staticmethod
        def normalizar_ruta(ruta: str | Path, predeterminada: str = "") -> Path:
            """Limpia, expande y resuelve la ruta de trabajo."""
            texto = str(ruta or "").strip().strip("\"'") or str(predeterminada)
            return Path(os.path.expandvars(
                os.path.expanduser(texto))).resolve()

        @staticmethod
        @lru_cache(maxsize=8)
        def subcarpetas_fuente(fuente: str) -> tuple[str, ...]:
            """Jerarquía de la fuente, descubierta una vez por proceso."""
            return descubrir_subcarpetas_src(fuente)

        @classmethod
        def normalizar_subcarpetas(
            cls, subcarpetas: Iterable[str] | str | None,
            nombre: str, fuente: str | Path,
        ) -> tuple[str, ...]:
            """Convierte ``subcarpetas`` en una tupla de nombres."""
            if subcarpetas is None:
                if str(nombre).lower() == NOMBRE_PREDETERMINADO.lower():
                    return cls.subcarpetas_fuente(str(fuente))
                return ()
            if isinstance(subcarpetas, str):
                return InterpreteOrden.Campos.dividir_subcarpetas(subcarpetas)
            return tuple(str(item).strip() for item in subcarpetas
                         if str(item).strip())

        @staticmethod
        def primer_nivel(subcarpetas: Iterable[str]) -> tuple[str, ...]:
            """Nombres de primer nivel, sin repetir y en orden."""
            return tuple(dict.fromkeys(
                partes[0] for partes in (Path(sub).parts for sub in subcarpetas)
                if partes))

        @staticmethod
        def texto_orden(base: Path, nombre: str,
                        niveles: Iterable[str]) -> str:
            """Texto que alimenta la red: ruta, nombre y niveles."""
            return " ".join((str(base), str(nombre), *niveles))

        @classmethod
        def resumir_pasos(cls, raiz: str,
                          niveles: Iterable[str]) -> list[dict[str, Any]]:
            """Traza de pasos por nivel (no por cada ruta anidada)."""
            return [
                {"paso": 1, "carpeta": Path(raiz).name, "ruta": raiz},
                *({"paso": numero, "carpeta": nivel,
                   "ruta": str(Path(raiz) / nivel)}
                  for numero, nivel in enumerate(niveles, start=2)),
            ]

        @staticmethod
        def crear_archivos(maquina: Any, raiz: str,
                           archivos: Iterable[str] | str) -> list[str]:
            """Crea los archivos vacíos indicados dentro de la raíz."""
            if isinstance(archivos, str):
                archivos = (archivos,)
            return [maquina.crear_archivo(raiz, str(nombre))
                    for nombre in archivos]

    COMANDOS = COMANDOS

    def __init__(
        self,
        ruta_red: str | Path | None = None,
        maquina: Any | None = None,
        rutas: Mapping[str, str] | Any | None = None,
        usar_red: bool = USAR_RED_NEURONAL,
    ) -> None:
        self.ruta_red = ruta_red
        self.rfprmn = (maquina if maquina is not None
                       else _importar_rfprmn().RFPRMN())
        self._rutas = rutas if rutas is not None else {}
        self.usar_red = usar_red
        self._red: Any | None = None

    @property
    def rutas(self) -> dict[str, str]:
        """Rutas actuales de cada comando (consulta el proveedor si existe)."""
        fuente = self._rutas
        return dict(fuente() if callable(fuente) else fuente)

    def _ruta(self, comando: str) -> str:
        """Ruta predeterminada del comando."""
        return self.rutas.get(comando, "")

    # -- red neuronal ------------------------------------------------------
    def _evaluar_orden(self, base: Path, nombre: str,
                       niveles: tuple[str, ...]) -> tuple[dict[str, Any],
                                                          dict[str, Any]]:
        """Crea la neurona constructiva y devuelve (red general, métricas)."""
        modulo = cargar_modulo_red(self.ruta_red)
        neurona = modulo.NeuronaEntradaXavier(DIM_ENTRADA, DIM_SALIDA)
        creativa = modulo.NeuronaEntradaXavier.NeuronaCreativa(neurona)
        clase = obtener_clase_constructiva()
        constructiva = clase(creativa, self.rfprmn, str(base), nombre, niveles)
        texto = self.Operaciones.texto_orden(base, nombre, niveles)

        metricas: dict[str, Any] = {
            "familia": "ENRN.EN2_RN", "neurona": "NeuronaEntradaXavier",
            "dim_entrada": DIM_ENTRADA, "dim_salida": DIM_SALIDA,
        }
        try:
            metricas["impulso"] = round(float(constructiva.impulso_creativo()), 6)
            metricas["entropia"] = round(float(constructiva.entropia(texto)), 6)
            similitudes = {
                nivel: round(float(constructiva.similitud(nombre, nivel)), 6)
                for nivel in niveles
            }
            metricas["similitudes"] = similitudes
            if similitudes:
                metricas["afinidad_maxima"] = max(similitudes.values())
        except Exception as error:  # noqa: BLE001 - métrica diagnóstica
            metricas["error"] = f"{type(error).__name__}: {error}"

        return self._red_general(constructiva, texto), metricas

    def _red_general(self, constructiva: Any,
                     texto: str) -> dict[str, Any]:
        """Pasa la orden por LCBS_NEURONAL: ENRN -> RF_EN + salud global."""
        vector = constructiva.vector(texto)
        datos: dict[str, Any] = {"modulo": "LCBS_NEURONAL"}
        try:
            modulo = cargar_lcbs_neuronal()
            with silencio():
                if self._red is None:
                    self._red = modulo.RedNeuronal(
                        input_size=int(vector.size), output_size=4,
                        latente_size=16, seed=2026)
                accion, diagnostico = self._red.procesar(vector, modo="xavier")
                salud = self._red.salud()
        except Exception as error:  # noqa: BLE001 - se reporta sin romper
            datos.update({"ok": False,
                          "error": f"{type(error).__name__}: {error}"})
            return datos
        datos.update({
            "ok": True,
            "version": getattr(modulo, "__version__", ""),
            "familias": list(getattr(modulo.RedNeuronal, "FAMILIAS", ())),
            "salud": {familia: bool(info.get("ok"))
                      for familia, info in salud.items()},
            "accion": [round(float(valor), 6) for valor in accion],
            "diagnostico": {clave: valor for clave, valor in diagnostico.items()
                            if isinstance(valor, (int, float, str, bool))},
        })
        return datos

    # -- carpetas ----------------------------------------------------------
    def _crear_solo_carpetas(
        self, base: Path, nombre: str, subcarpetas: tuple[str, ...],
        niveles: tuple[str, ...],
    ) -> dict[str, Any]:
        """Crea la jerarquía sin red neuronal y resume los pasos por nivel."""
        resultado = crear_jerarquia(str(base), nombre, subcarpetas, self.rfprmn)
        if resultado.get("ok"):
            resultado["pasos"] = self.Operaciones.resumir_pasos(
                resultado["raiz"], niveles)
        return resultado

    # -- API pública -------------------------------------------------------
    def crear_carpeta(self, ruta: str | Path = "",
                      nombre: str = NOMBRE_PREDETERMINADO,
                      subcarpetas: Iterable[str] | None = None,
                      archivos: Iterable[str] | None = None) -> dict[str, Any]:
        """Crea ``ruta/nombre`` y, si es ``src``, su jerarquía completa.

        Sin ``ruta`` usa la ruta inyectada y sin ``nombre`` usa
        ``NOMBRE_PREDETERMINADO``. Si ``subcarpetas`` es ``None`` y el nombre
        es ``src`` se descubre la jerarquía de ``TLLDCD/src``; en otro caso
        solo la raíz. ``archivos`` crea ficheros vacíos dentro de la raíz.
        """
        base = self.Operaciones.normalizar_ruta(
            ruta, self._ruta(COMANDO_CARPETA))
        nombre = str(nombre or NOMBRE_PREDETERMINADO).strip()
        subcarpetas = self.Operaciones.normalizar_subcarpetas(
            subcarpetas, nombre, RUTA_FUENTE_PREDETERMINADA)
        niveles = self.Operaciones.primer_nivel(subcarpetas)

        resultado = self._crear_solo_carpetas(
            base, nombre, subcarpetas, niveles)
        if self.usar_red:
            try:
                red_general, metricas = self._evaluar_orden(
                    base, nombre, niveles)
            except Exception as error:  # noqa: BLE001 - la creación ya ocurrió
                red_general = {"ok": False,
                               "error": f"{type(error).__name__}: {error}"}
                metricas = {}
        else:
            red_general = {"ok": True, "omitida": True,
                           "motivo": "modo solo carpetas (red desactivada)"}
            metricas = {}
        resultado.update({
            "comando": COMANDO_CARPETA,
            "ruta": str(base),
            "nombre": nombre,
            "subcarpetas": list(subcarpetas),
            "red_general": red_general,
            "neurona_entrada": metricas,
            "rfprmn": {"version": getattr(_importar_rfprmn(),
                                          "__version__", "")},
        })
        archivos_creados: list[str] = []
        if archivos is not None and resultado.get("ok"):
            try:
                archivos_creados = self.Operaciones.crear_archivos(
                    self.rfprmn, resultado["raiz"], archivos)
            except Exception as error:  # noqa: BLE001 - resultado degradado
                resultado["ok"] = False
                resultado["error"] = f"{type(error).__name__}: {error}"
        resultado["archivos"] = archivos_creados
        if not red_general.get("ok"):
            resultado["advertencia"] = (
                "La red general no pudo calcular; la jerarquía se creó igualmente.")
        return resultado

    def crear_red_neuronal(
        self, ruta: str | Path = "",
        nombre: str = NOMBRE_RED_PREDETERMINADO,
        subcarpetas: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Segunda acción: crea ``LC_STM/RedNeuronal`` con sus seis familias."""
        resultado = self.crear_carpeta(
            ruta or self._ruta(COMANDO_RED),
            nombre or NOMBRE_RED_PREDETERMINADO,
            SUBCARPETAS_RED if subcarpetas is None else subcarpetas)
        resultado["comando"] = COMANDO_RED
        return resultado

    def comando_crear_red_neuronal(
        self, ruta: str | Path = "",
        nombre: str = NOMBRE_RED_PREDETERMINADO,
        subcarpetas: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Alias de la segunda acción con sus valores predeterminados."""
        return self.crear_red_neuronal(ruta, nombre, subcarpetas)

    def crear_mtbgt(
        self, ruta: str | Path = "",
        subcarpetas: Iterable[str] | None = None,
        archivos: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Tercera acción: ``MTBGT`` con sus carpetas (sin archivos por ahora)."""
        root = self.Operaciones.normalizar_ruta(
            ruta, self._ruta(COMANDO_MTBGT))
        resultado = self.crear_carpeta(
            root.parent, root.name,
            SUBCARPETAS_MTBGT if subcarpetas is None else subcarpetas,
            ARCHIVOS_MTBGT if archivos is None else archivos)
        resultado["comando"] = COMANDO_MTBGT
        resultado["ruta_mtbgt"] = str(root)
        return resultado

    def comando_crear_mtbgt(
        self, ruta: str | Path = "",
        subcarpetas: Iterable[str] | None = None,
        archivos: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Alias de la tercera acción con sus valores predeterminados."""
        return self.crear_mtbgt(ruta, subcarpetas, archivos)

    def crear_todo(self) -> dict[str, Any]:
        """Secuencia completa: ``src``, ``RedNeuronal`` y ``MTBGT``."""
        acciones = [self.crear_carpeta(),
                    self.crear_red_neuronal(),
                    self.crear_mtbgt()]
        return {
            "ok": all(accion.get("ok") for accion in acciones),
            "comando": COMANDO_TODO,
            "acciones": acciones,
            "total": sum(int(accion.get("total", 0)) for accion in acciones),
        }

    def comando_crear_todo(self) -> dict[str, Any]:
        """Alias de la secuencia completa."""
        return self.crear_todo()

    def comando_crear_carpeta(
        self, ruta: str | Path = "", nombre: str = NOMBRE_PREDETERMINADO,
        subcarpetas: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Alias del comando con la ruta y el nombre predeterminados."""
        return self.crear_carpeta(ruta, nombre, subcarpetas)

    def ejecutar(self, orden: str | Mapping[str, Any]) -> dict[str, Any]:
        """Interpreta y ejecuta una orden completa de la máquina de comandos."""
        datos = InterpreteOrden(self.rutas).interpretar(orden)
        if datos.get("error"):
            return {"ok": False,
                    "comando": datos.get("comando", COMANDO_CARPETA),
                    "error": datos["error"]}
        comando = datos.get("comando", COMANDO_CARPETA)
        if comando not in self.COMANDOS:
            return {"ok": False, "comando": comando,
                    "error": f"Comando no soportado: {comando!r}. "
                             f"Disponibles: {', '.join(self.COMANDOS)}"}
        if comando == COMANDO_TODO:
            return self.crear_todo()
        if comando == COMANDO_MTBGT:
            return self.crear_mtbgt(
                datos.get("ruta") or self._ruta(COMANDO_MTBGT),
                datos.get("subcarpetas"))
        if comando == COMANDO_RED:
            return self.crear_red_neuronal(
                datos.get("ruta") or self._ruta(COMANDO_RED),
                datos.get("nombre") or NOMBRE_RED_PREDETERMINADO,
                datos.get("subcarpetas"))
        return self.crear_carpeta(
            datos.get("ruta") or self._ruta(COMANDO_CARPETA),
            datos.get("nombre") or NOMBRE_PREDETERMINADO,
            datos.get("subcarpetas"))


_CONSTRUCTOR: ConstructorLucIA | None = None


def obtener_constructor(
    rutas: Mapping[str, str] | Any | None = None,
    usar_red: bool = USAR_RED_NEURONAL,
) -> ConstructorLucIA:
    """Constructor compartido (carga perezosa de la red y de RFPRMN)."""
    global _CONSTRUCTOR
    if _CONSTRUCTOR is None:
        _CONSTRUCTOR = ConstructorLucIA(rutas=rutas, usar_red=usar_red)
    return _CONSTRUCTOR


def ejecutar_orden(orden: str | Mapping[str, Any]) -> dict[str, Any]:
    """Atajo: interpreta y ejecuta una orden con el constructor compartido."""
    return obtener_constructor().ejecutar(orden)


def crear_carpeta(ruta: str | Path = "",
                  nombre: str = NOMBRE_PREDETERMINADO,
                  subcarpetas: Iterable[str] | None = None) -> dict[str, Any]:
    """Atajo programático; sin ruta usa la ruta inyectada."""
    return obtener_constructor().crear_carpeta(ruta, nombre, subcarpetas)


def comando_crear_carpeta(
    ruta: str | Path = "", nombre: str = NOMBRE_PREDETERMINADO,
    subcarpetas: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Alias con la ruta y el nombre predeterminados."""
    return crear_carpeta(ruta, nombre, subcarpetas)


def crear_red_neuronal(
    ruta: str | Path = "", nombre: str = NOMBRE_RED_PREDETERMINADO,
    subcarpetas: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Atajo de la segunda acción."""
    return obtener_constructor().crear_red_neuronal(ruta, nombre, subcarpetas)


def comando_crear_red_neuronal(
    ruta: str | Path = "", nombre: str = NOMBRE_RED_PREDETERMINADO,
    subcarpetas: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Alias de la segunda acción con sus valores predeterminados."""
    return crear_red_neuronal(ruta, nombre, subcarpetas)


def crear_mtbgt(
    ruta: str | Path = "", subcarpetas: Iterable[str] | None = None,
    archivos: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Atajo de la tercera acción; crea ``MTBGT`` solo con carpetas."""
    return obtener_constructor().crear_mtbgt(ruta, subcarpetas, archivos)


def comando_crear_mtbgt(
    ruta: str | Path = "", subcarpetas: Iterable[str] | None = None,
    archivos: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Alias de la tercera acción con sus valores predeterminados."""
    return crear_mtbgt(ruta, subcarpetas, archivos)


def crear_todo() -> dict[str, Any]:
    """Ejecuta la secuencia completa: ``src``, ``RedNeuronal`` y ``MTBGT``."""
    return obtener_constructor().crear_todo()


def comando_crear_todo() -> dict[str, Any]:
    """Alias de la secuencia completa."""
    return crear_todo()


__all__ = [
    "ARCHIVOS_MTBGT",
    "COMANDOS",
    "USAR_RED_NEURONAL",
    "ConstructorLucIA",
    "comando_crear_carpeta",
    "comando_crear_mtbgt",
    "comando_crear_red_neuronal",
    "comando_crear_todo",
    "crear_carpeta",
    "crear_mtbgt",
    "crear_red_neuronal",
    "crear_todo",
    "ejecutar_orden",
    "obtener_constructor",
]
