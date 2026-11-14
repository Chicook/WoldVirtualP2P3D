"""Constructor de jerarquías de carpetas para LucIA (STM_MD1).

Descubre la jerarquía de ``TLLDCD/src``, carga la red neuronal (EN2_RN /
LCBS_NEURONAL) y crea carpetas paso a paso usando una neurona constructiva.

El módulo se puede importar sin que exista la red: las funciones de
localización lanzan ``FileNotFoundError`` y la clase de alto nivel degrada a un
constructor de carpetas puro.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import logging
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType
from typing import Any

# ---------------------------------------------------------------------------
# Constantes y rutas
# ---------------------------------------------------------------------------

_DIR_MODULO: Path = Path(__file__).resolve().parent

_EXCLUIR_CARPETAS: frozenset[str] = frozenset({
    "__pycache__", "pycache", ".git", ".godot", ".venv", "venv",
    "node_modules", ".pytest_cache", ".ruff_cache",
})

_NOMBRE_PREDETERMINADO: str = "LC"
DIM_ENTRADA: int = 64
DIM_SALIDA: int = 32

_RUTA_RED_RELATIVA: Path = (
    Path("CONTRUCCION") / "Refactorizacion" / "src" / "LC_STM" / "RedNeuronal"
)


def _resolver_fuente_predeterminada() -> Path:
    """Localiza ``TLLDCD/src`` a partir del módulo o del entorno."""
    entorno = os.environ.get("LC_SRC", "").strip()
    if entorno:
        candidata = Path(entorno).expanduser()
        if candidata.is_dir():
            return candidata
    for base in (_DIR_MODULO, *_DIR_MODULO.parents):
        candidata = base / "TLLDCD" / "src"
        if candidata.is_dir():
            return candidata
        candidata = base / "CONTRRF" / "TLLDCD" / "src"
        if candidata.is_dir():
            return candidata
    return _DIR_MODULO


RUTA_FUENTE_PREDETERMINADA: Path = _resolver_fuente_predeterminada()

#: Alias histórico.
NOMBRE_PREDETERMINADO: str = _NOMBRE_PREDETERMINADO

#: Jerarquía base de respaldo si la fuente no está disponible.
SUBCARPETAS_SRC_BASE: tuple[str, ...] = (
    "LC_STM", "MTBGT", "SBSTM", "STMGNRL", "STMIPFS", "STM_BKCH",
    "STM_CH", "STM_DOC", "STM_HRTS", "STM_IA", "STM_JSON", "STM_SGR",
    "tests", "VSC#",
)

_MODULO_RED: ModuleType | None = None
_CLASE_CONSTRUCTIVA: type | None = None
_LCBS: ModuleType | None = None


@contextlib.contextmanager
def _silencio():
    """Silencia prints y logs internos de LCBS_NEURONAL durante el cálculo."""
    nivel = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with open(os.devnull, "w", encoding="utf-8") as nulo, \
                contextlib.redirect_stdout(nulo), \
                contextlib.redirect_stderr(nulo):
            yield
    finally:
        logging.disable(nivel)


# ---------------------------------------------------------------------------
# Descubrimiento de carpetas
# ---------------------------------------------------------------------------

def descubrir_subcarpetas_src(
    ruta_fuente: str | Path | None = None,
) -> tuple[str, ...]:
    """Devuelve **toda** la jerarquía de carpetas de ``TLLDCD/src``.

    Solo carpetas: se ignoran los archivos. Se excluyen cachés y metadatos.
    Las rutas son relativas a la fuente y conservan sus niveles.
    """
    base = Path(ruta_fuente or RUTA_FUENTE_PREDETERMINADA)
    try:
        if base.is_dir():
            rutas: list[str] = []
            for actual, dirs, _ficheros in os.walk(base):
                dirs[:] = sorted(d for d in dirs if d not in _EXCLUIR_CARPETAS)
                relativa = Path(actual).relative_to(base)
                if relativa.parts:
                    rutas.append(relativa.as_posix())
            return tuple(rutas)
    except OSError:
        pass
    return SUBCARPETAS_SRC_BASE


#: Alias explícito para quien prefiera el nombre "jerarquía".
descubrir_jerarquia_src = descubrir_subcarpetas_src

#: Jerarquía completa de la fuente (calculada una sola vez).
SUBCARPETAS_SRC: tuple[str, ...] = descubrir_subcarpetas_src()


# ---------------------------------------------------------------------------
# Localización y carga de la red neuronal
# ---------------------------------------------------------------------------

def localizar_red_neuronal() -> Path:
    """Devuelve el directorio ``RedNeuronal`` o lanza ``FileNotFoundError``."""
    candidatos: list[Path] = []
    entorno = os.environ.get("LC_RED_NEURONAL", "").strip()
    if entorno:
        candidatos.append(Path(entorno).expanduser())
    for base in (_DIR_MODULO, *_DIR_MODULO.parents):
        candidatos.extend((
            base / _RUTA_RED_RELATIVA,
            base / "CONTRRF" / _RUTA_RED_RELATIVA,
            base / "VersionDe_sesion" / "CONTRRF" / _RUTA_RED_RELATIVA,
        ))
    vistos: set[Path] = set()
    for candidato in candidatos:
        try:
            resuelto = candidato.resolve()
        except OSError:
            continue
        if resuelto in vistos:
            continue
        vistos.add(resuelto)
        if (resuelto / "ENRN" / "EN2_RN.py").is_file():
            return resuelto
    raise FileNotFoundError(
        "No encuentro RedNeuronal/ENRN/EN2_RN.py. Define LC_RED_NEURONAL "
        f"o revisa la ruta de {_DIR_MODULO}"
    )


def _importar_por_archivo(ruta: Path) -> ModuleType:
    """Carga un módulo de la red por ruta, sin depender del paquete ``LC_STM``."""
    nombre = f"_lc_constructor_{ruta.stem.lower()}"
    if nombre in sys.modules:
        return sys.modules[nombre]
    especificacion = importlib.util.spec_from_file_location(nombre, ruta)
    if especificacion is None or especificacion.loader is None:
        raise ImportError(f"No se puede cargar {ruta.name} desde {ruta}")
    modulo = importlib.util.module_from_spec(especificacion)
    sys.modules[nombre] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


def cargar_modulo_red(ruta_red: str | Path | None = None) -> ModuleType:
    """Importa EN2_RN desde ``RedNeuronal`` (con caché de módulo)."""
    global _MODULO_RED
    if _MODULO_RED is not None and ruta_red is None:
        return _MODULO_RED
    red = Path(ruta_red).expanduser() if ruta_red else localizar_red_neuronal()
    try:
        modulo = _importar_por_archivo(red / "ENRN" / "EN2_RN.py")
    except (ImportError, OSError):
        src = red.parents[1]
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        modulo = importlib.import_module("LC_STM.RedNeuronal.ENRN.EN2_RN")
    if ruta_red is None:
        _MODULO_RED = modulo
    return modulo


def localizar_lcbs_neuronal() -> Path:
    """Devuelve la ruta de ``LCBS_NEURONAL.py`` (módulo general de la red)."""
    entorno = os.environ.get("LC_LCBS_NEURONAL", "").strip()
    if entorno and Path(entorno).is_file():
        return Path(entorno).expanduser().resolve()
    ruta = localizar_red_neuronal().parent / "LCBS_NEURONAL.py"
    if ruta.is_file():
        return ruta
    raise FileNotFoundError(f"No encuentro el módulo general de la red: {ruta}")


def cargar_lcbs_neuronal(ruta: str | Path | None = None) -> ModuleType:
    """Importa la fachada general ``LCBS_NEURONAL`` (cacheada y en silencio)."""
    global _LCBS
    if _LCBS is not None and ruta is None:
        return _LCBS
    archivo = (Path(ruta).expanduser() if ruta
               else localizar_lcbs_neuronal()).resolve()
    src = archivo.parent.parent
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    with _silencio():
        try:
            modulo = importlib.import_module("LC_STM.LCBS_NEURONAL")
            ruta_modulo = Path(str(getattr(modulo, "__file__", ""))).resolve()
            if ruta_modulo != archivo:
                raise ImportError("LC_STM.LCBS_NEURONAL resolvió a otro archivo")
        except ImportError:
            modulo = _importar_por_archivo(archivo)
    if ruta is None:
        _LCBS = modulo
    return modulo


def _asegurar_carpeta(base: str, nombre: str, maquina: Any) -> str:
    """Devuelve ``base/nombre`` creándolo si falta.

    Admite rutas anidadas (``STMGNRL/sub``) creando cada nivel con
    ``maquina.crear_carpeta_en``, que valida los nombres y aplica el fallback
    de PowerShell cuando el intérprete no puede crear la carpeta.
    """
    limpio = str(nombre).strip()
    if not limpio:
        return maquina.crear_carpeta_en(base, nombre)
    partes = Path(limpio.replace("\\", "/")).parts
    if (Path(limpio).is_absolute() or not partes
            or any(parte in {".", ".."} for parte in partes)):
        return maquina.crear_carpeta_en(base, nombre)
    actual = str(base)
    for parte in partes:
        objetivo = Path(actual) / parte
        try:
            if (objetivo.is_dir()
                    and objetivo.parent.resolve() == Path(actual).resolve()):
                actual = str(objetivo)
                continue
        except OSError:
            pass
        actual = maquina.crear_carpeta_en(actual, parte)
    return actual


def crear_jerarquia(base: str | Path, nombre: str,
                    subcarpetas: Iterable[str], maquina: Any) -> dict[str, Any]:
    """Crea la raíz y cada subcarpeta; devuelve la traza de pasos.

    ``maquina`` solo necesita el método ``crear_carpeta_en(base, nombre)``.
    No carga la red neuronal: sirve para el modo de solo carpetas.
    """
    raiz = ""
    creadas: list[str] = []
    pasos: list[dict[str, Any]] = []
    try:
        raiz = _asegurar_carpeta(str(base), nombre, maquina)
        pasos.append({"paso": 1, "carpeta": Path(raiz).name, "ruta": raiz})
        for numero, subcarpeta in enumerate(subcarpetas, start=2):
            if not str(subcarpeta).strip():
                continue
            ruta_sub = _asegurar_carpeta(raiz, subcarpeta, maquina)
            creadas.append(ruta_sub)
            pasos.append({"paso": numero, "carpeta": subcarpeta,
                          "ruta": ruta_sub})
    except Exception as error:  # noqa: BLE001 - resultado degradado
        return {"ok": False, "error": f"{type(error).__name__}: {error}",
                "raiz": raiz, "carpetas": creadas, "pasos": pasos,
                "total": (1 if raiz else 0) + len(creadas)}
    return {"ok": True, "raiz": raiz, "carpetas": creadas,
            "total": 1 + len(creadas), "pasos": pasos}


def _obtener_clase_constructiva() -> type:
    """Especializa la NeuronaConstructiva con la orden de la máquina."""
    global _CLASE_CONSTRUCTIVA
    if _CLASE_CONSTRUCTIVA is not None:
        return _CLASE_CONSTRUCTIVA

    try:
        modulo = cargar_modulo_red()
        base = modulo.NeuronaEntradaXavier.NeuronaCreativa.NeuronaConstructiva
    except Exception:  # red no disponible: constructor de carpetas puro
        base = object

    class NeuronaConstructivaLucIA(base):
        """Crea la jerarquía indicada, paso a paso y en orden."""

        def __init__(self, creativa: Any, maquina: Any, ruta_base: str,
                     nombre: str = _NOMBRE_PREDETERMINADO,
                     subcarpetas: Iterable[str] | None = None) -> None:
            if base is not object:
                super().__init__(creativa)
            self._creativa = creativa
            self._maquina = maquina
            self.ruta_base = str(ruta_base)
            self.nombre = str(nombre)
            self.subcarpetas = tuple(str(s) for s in (subcarpetas or ()))

        def vector(self, texto: str) -> Any:
            """Vector Xavier de la orden para alimentar la red general."""
            creativa = self._creativa
            if creativa is not None and hasattr(creativa, "vector"):
                return creativa.vector(texto)
            return texto

        def _crear_si_falta(self, base: str, nombre: str) -> str:
            """Devuelve la carpeta existente o la crea (admite anidamiento)."""
            return _asegurar_carpeta(base, nombre, self._maquina)

        def crear_carpetas(self) -> dict[str, Any]:
            """Crea la raíz y cada subcarpeta; devuelve la traza de pasos."""
            return crear_jerarquia(self.ruta_base, self.nombre,
                                   self.subcarpetas, self._maquina)

    _CLASE_CONSTRUCTIVA = NeuronaConstructivaLucIA
    return _CLASE_CONSTRUCTIVA


#: Alias publico para consumidores externos (``LC_constructor``).
silencio = _silencio
obtener_clase_constructiva = _obtener_clase_constructiva


# ---------------------------------------------------------------------------
# Clase principal y clase anidada unificadora
# ---------------------------------------------------------------------------

class ConstructorJerarquia:
    """Mejora los objetivos principales del módulo de forma unificada.

    - Descubre la jerarquía de carpetas de la fuente.
    - Carga (opcional) la red neuronal y LCBS.
    - Crea la jerarquía en disco usando la neurona constructiva.
    """

    class Operaciones:
        """Clase anidada que unifica funciones auxiliares de carpetas."""

        @staticmethod
        def validar_nombre(nombre: str) -> bool:
            limpio = str(nombre).strip()
            return bool(limpio) and limpio not in {".", ".."} and Path(limpio).name == limpio

        @staticmethod
        def crear_carpeta_en(base: str, nombre: str) -> str:
            """Crea (si falta) y devuelve la ruta de la carpeta."""
            objetivo = Path(base) / str(nombre).strip()
            objetivo.mkdir(parents=True, exist_ok=True)
            return str(objetivo)

        @staticmethod
        def asegurar_jerarquia(base: str, nombre: str,
                               subcarpetas: Iterable[str]) -> dict[str, Any]:
            """Crea raíz + subcarpetas y devuelve traza."""
            raiz = str(Path(base) / str(nombre).strip())
            Path(raiz).mkdir(parents=True, exist_ok=True)
            creadas = []
            for sub in subcarpetas:
                ruta_sub = str(Path(raiz) / str(sub).strip())
                Path(ruta_sub).mkdir(parents=True, exist_ok=True)
                creadas.append(ruta_sub)
            return {"ok": True, "raiz": raiz, "carpetas": creadas,
                    "total": 1 + len(creadas)}

    def __init__(
        self,
        ruta_fuente: str | Path | None = None,
        nombre: str = _NOMBRE_PREDETERMINADO,
        subcarpetas: Iterable[str] | None = None,
        ruta_red: str | Path | None = None,
        usar_red: bool = True,
    ) -> None:
        self.ruta_fuente = Path(ruta_fuente) if ruta_fuente else RUTA_FUENTE_PREDETERMINADA
        self.nombre = str(nombre)
        self._subcarpetas = (tuple(str(s) for s in subcarpetas)
                             if subcarpetas is not None else None)
        self.ruta_red = ruta_red
        self.usar_red = usar_red
        self._cache_descubiertas: tuple[str, ...] | None = None

    # --- propiedades eficientes (caché) ---

    @property
    def subcarpetas(self) -> tuple[str, ...]:
        if self._subcarpetas is not None:
            return self._subcarpetas
        if self._cache_descubiertas is None:
            self._cache_descubiertas = descubrir_subcarpetas_src(self.ruta_fuente)
        return self._cache_descubiertas

    # --- operaciones ---

    def descubrir(self) -> tuple[str, ...]:
        return self.subcarpetas

    def cargar_red(self) -> ModuleType | None:
        if not self.usar_red:
            return None
        try:
            return cargar_modulo_red(self.ruta_red)
        except Exception:  # noqa: BLE001 - degradación controlada
            return None

    def cargar_lcbs(self) -> ModuleType | None:
        if not self.usar_red:
            return None
        try:
            return cargar_lcbs_neuronal(None)
        except Exception:  # noqa: BLE001 - degradación controlada
            return None

    def crear(self, ruta_base: str | Path | None = None) -> dict[str, Any]:
        base = str(ruta_base) if ruta_base is not None else str(self.ruta_fuente)
        clase = _obtener_clase_constructiva()
        maquina = self.Operaciones()
        try:
            neurona = clase(
                creativa=None,
                maquina=maquina,
                ruta_base=base,
                nombre=self.nombre,
                subcarpetas=self.subcarpetas,
            )
            return neurona.crear_carpetas()
        except Exception as error:  # noqa: BLE001 - resultado degradado
            return self.Operaciones.asegurar_jerarquia(
                base, self.nombre, self.subcarpetas)

    def __repr__(self) -> str:
        return (f"ConstructorJerarquia(nombre={self.nombre!r}, "
                f"fuente={str(self.ruta_fuente)!r})")


__all__ = [
    "ConstructorJerarquia",
    "descubrir_subcarpetas_src",
    "descubrir_jerarquia_src",
    "cargar_modulo_red",
    "cargar_lcbs_neuronal",
    "localizar_red_neuronal",
    "localizar_lcbs_neuronal",
    "obtener_clase_constructiva",
    "silencio",
    "crear_jerarquia",
    "SUBCARPETAS_SRC",
    "SUBCARPETAS_SRC_BASE",
    "RUTA_FUENTE_PREDETERMINADA",
    "NOMBRE_PREDETERMINADO",
    "DIM_ENTRADA",
    "DIM_SALIDA",
]
