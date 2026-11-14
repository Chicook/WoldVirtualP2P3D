r"""LC_constructor — primer comando automático de LucIA (``crear carpeta``).

Recibe de la máquina de comandos una orden como::

    Ruta donde crear: E:\...\LCtrabajando
    Nombre de la carpeta: src

y la ejecuta pasando por la red neuronal completa de ``LCBS_NEURONAL``
(ENRN -> RF_EN y salud de las familias) y por la fachada ``RFPRMN.py``.
Acepta texto etiquetado (una o varias líneas), dict o JSON; la CLI responde
en texto legible, no en JSON.

Acciones disponibles:
- ``crear todo``          : ejecuta las tres siguientes en secuencia (explícito).
- ``crear carpeta``       : ``LCtrabajando/src`` con **toda** la jerarquía de
  carpetas detectada en ``TLLDCD/src`` (solo carpetas, sin archivos).  Es la
  acción por defecto de la CLI cuando no se pasan argumentos.
- ``crear red neuronal``  : ``LCtrabajando/src/LC_STM/RedNeuronal`` y sus
  6 familias.  Se invoca con ``python LC_constructor.py red``.
- ``crear mtbgt``         : ``LCtrabajando/src/MTBGT`` con sus carpetas;
  los archivos quedan para una fase posterior.  Se invoca con
  ``python LC_constructor.py mtbgt``.
"""
from __future__ import annotations

import contextlib
import importlib
import importlib.util
import json
import logging
import os
import re
import shlex
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

__version__ = "0.9.1"

_DIR_MODULO = Path(__file__).resolve().parent
if str(_DIR_MODULO) not in sys.path:
    sys.path.insert(0, str(_DIR_MODULO))

import RFPRMN as _RFPRMN  # noqa: E402

RFPRMN = _RFPRMN.RFPRMN

#: Ruta y nombre que usa el comando cuando no se indican.
RUTA_PREDETERMINADA = (
    r"E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\CONTRUCCION\LCtrabajando"
)
NOMBRE_PREDETERMINADO = "src"

#: Segunda acción: ``LCtrabajando/src/LC_STM/RedNeuronal`` y sus familias.
RUTA_RED_PREDETERMINADA = (
    r"E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\CONTRUCCION"
    r"\LCtrabajando\src\LC_STM"
)
NOMBRE_RED_PREDETERMINADO = "RedNeuronal"
SUBCARPETAS_RED: tuple[str, ...] = (
    "CELEBRO", "ENRN", "RF_EN", "RF_SL", "RNP", "SLRN",
)

COMANDO_CARPETA = "crear carpeta"
COMANDO_RED = "crear red neuronal"
COMANDO_MTBGT = "crear mtbgt"
COMANDO_TODO = "crear todo"

#: Tercera acción: ``LCtrabajando/src/MTBGT`` solo con carpetas por ahora.
RUTA_MTBGT_PREDETERMINADA = (
    r"E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\CONTRUCCION"
    r"\LCtrabajando\src\MTBGT"
)
NOMBRE_MTBGT_PREDETERMINADO = "MTBGT"
SUBCARPETAS_MTBGT: tuple[str, ...] = (
    ".godot", "addons", "AreaDeTrabajo", "gdscrip", "gdshader", "scene",
)
#: Sin archivos de momento: el ``project.godot`` queda para una fase posterior.
ARCHIVOS_MTBGT: tuple[str, ...] = ()

#: Modo limpio: crea solo carpetas, pero conserva el cálculo de LCBS_NEURONAL.
#: Poner False solo si se quiere evitar por completo la carga de la red.
USAR_RED_NEURONAL = True

#: Fuente oficial de la estructura de carpetas.
RUTA_FUENTE_PREDETERMINADA = (
    r"E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src"
)

#: Jerarquía base de respaldo si la fuente no está disponible.
SUBCARPETAS_SRC_BASE: tuple[str, ...] = (
    "LC_STM", "MTBGT", "SBSTM", "STMGNRL", "STMIPFS", "STM_BKCH",
    "STM_CH", "STM_DOC", "STM_HRTS", "STM_IA", "STM_JSON", "STM_SGR",
    "tests", "VSC#",
)


#: Carpetas generadas que no forman parte de la jerarquía fuente.
_EXCLUIR_CARPETAS = {
    "__pycache__", "pycache", ".git", ".godot", ".ruff_cache",
    ".pytest_cache", ".mypy_cache", "node_modules",
}


def descubrir_subcarpetas_src(
    ruta_fuente: str | Path | None = None,
) -> tuple[str, ...]:
    """Devuelve **toda** la jerarquía de carpetas de ``TLLDCD/src``.

    Solo carpetas: se ignoran los archivos. Se excluyen cachés y metadatos
    (``__pycache__``, ``pycache``, ``.git``, ``.godot``, etc.). Las rutas son
    relativas a ``TLLDCD/src`` y conservan sus niveles:
    ``SBSTM/SistemasLC/STM_SBTM_1``.
    """
    base = Path(ruta_fuente or RUTA_FUENTE_PREDETERMINADA)
    try:
        if base.is_dir():
            rutas: list[str] = []
            for actual, dirs, _ficheros in os.walk(base):
                dirs[:] = sorted(
                    d for d in dirs if d not in _EXCLUIR_CARPETAS)
                relativa = Path(actual).relative_to(base)
                if relativa.parts:
                    rutas.append(relativa.as_posix())
            return tuple(rutas)
    except OSError:
        pass
    return SUBCARPETAS_SRC_BASE


#: Alias explícito para quien prefiera el nombre "jerarquía".
descubrir_jerarquia_src = descubrir_subcarpetas_src

#: Jerarquía completa de ``LCtrabajando/src`` (solo carpetas de la fuente).
SUBCARPETAS_SRC: tuple[str, ...] = descubrir_subcarpetas_src()

#: Dimensión de la neurona Xavier usada para medir las órdenes.
DIM_ENTRADA = 64
DIM_SALIDA = 32

_RUTA_RED_RELATIVA = (
    Path("CONTRUCCION") / "Refactorizacion" / "src" / "LC_STM" / "RedNeuronal"
)

_MODULO_RED: ModuleType | None = None
_CLASE_CONSTRUCTIVA: type | None = None
_LCBS: ModuleType | None = None
_NULO = open(os.devnull, "w", encoding="utf-8")


@contextlib.contextmanager
def _silencio():
    """Silencia prints y logs internos de LCBS_NEURONAL durante el cálculo."""
    nivel = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(_NULO), contextlib.redirect_stderr(_NULO):
            yield
    finally:
        logging.disable(nivel)


def localizar_red_neuronal() -> Path:
    """Devuelve el directorio ``RedNeuronal`` o lanza ``FileNotFoundError``.

    Se puede forzar con la variable de entorno ``LC_RED_NEURONAL``.
    """
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
    """Importa EN2_RN desde ``RedNeuronal`` (con caché de módulo).

    Se carga por archivo para no chocar con otros paquetes ``LC_STM``.
    """
    global _MODULO_RED
    if _MODULO_RED is not None:
        return _MODULO_RED
    red = Path(ruta_red).expanduser() if ruta_red else localizar_red_neuronal()
    try:
        _MODULO_RED = _importar_por_archivo(red / "ENRN" / "EN2_RN.py")
    except (ImportError, OSError):
        src = red.parents[1]
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        _MODULO_RED = importlib.import_module("LC_STM.RedNeuronal.ENRN.EN2_RN")
    return _MODULO_RED


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
    if _LCBS is not None:
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
    _LCBS = modulo
    return _LCBS


def _obtener_clase_constructiva() -> type:
    """Especializa la NeuronaConstructiva con la orden de la máquina."""
    global _CLASE_CONSTRUCTIVA
    if _CLASE_CONSTRUCTIVA is not None:
        return _CLASE_CONSTRUCTIVA
    modulo = cargar_modulo_red()
    creativa_cls = modulo.NeuronaEntradaXavier.NeuronaCreativa
    base = creativa_cls.NeuronaConstructiva

    class NeuronaConstructivaLucIA(base):
        """Crea la jerarquía indicada, paso a paso y en orden."""

        def __init__(self, creativa: Any, maquina: Any, ruta_base: str,
                     nombre: str = NOMBRE_PREDETERMINADO,
                     subcarpetas: Iterable[str] | None = None) -> None:
            super().__init__(creativa)
            self._maquina = maquina
            self.ruta_base = str(ruta_base)
            self.nombre = str(nombre)
            self.subcarpetas = tuple(str(s) for s in (subcarpetas or ()))

        def vector(self, texto: str) -> Any:
            """Vector Xavier de la orden para alimentar la red general."""
            return self._creativa.vector(texto)

        def _crear_si_falta(self, base: str, nombre: str) -> str:
            """Devuelve la carpeta existente o la crea validando el nombre."""
            limpio = str(nombre).strip()
            if not limpio or limpio in {".", ".."} or Path(limpio).name != limpio:
                return self._maquina.crear_carpeta_en(base, nombre)
            objetivo = Path(base) / limpio
            try:
                if (objetivo.is_dir()
                        and objetivo.parent.resolve() == Path(base).resolve()):
                    return str(objetivo)
            except OSError:
                pass
            return self._maquina.crear_carpeta_en(base, nombre)

        def crear_carpetas(self) -> dict[str, Any]:
            """Crea la raíz y cada subcarpeta; devuelve la traza de pasos."""
            raiz = ""
            creadas: list[str] = []
            pasos: list[dict[str, Any]] = []
            try:
                raiz = self._crear_si_falta(self.ruta_base, self.nombre)
                pasos.append({"paso": 1, "carpeta": Path(raiz).name, "ruta": raiz})
                for numero, subcarpeta in enumerate(self.subcarpetas, start=2):
                    ruta_sub = self._crear_si_falta(raiz, subcarpeta)
                    creadas.append(ruta_sub)
                    pasos.append({"paso": numero, "carpeta": subcarpeta,
                                  "ruta": ruta_sub})
            except Exception as error:  # noqa: BLE001 - resultado degradado
                return {"ok": False,
                        "error": f"{type(error).__name__}: {error}",
                        "raiz": raiz, "carpetas": creadas, "pasos": pasos,
                        "total": (1 if raiz else 0) + len(creadas)}
            return {"ok": True, "raiz": raiz, "carpetas": creadas,
                    "total": 1 + len(creadas), "pasos": pasos}

    _CLASE_CONSTRUCTIVA = NeuronaConstructivaLucIA
    return _CLASE_CONSTRUCTIVA


_PATRONES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ruta", re.compile(
        r"(?i)(?:^|[\s,;])(?:ruta)\s*"
        r"(?:donde\s+crear|de\s+creaci[oó]n)?\s*[:=]\s*")),
    ("nombre", re.compile(
        r"(?i)(?:^|[\s,;])(?:nombre)\s*"
        r"(?:de\s+la\s+carpeta|de\s+carpeta)?\s*[:=]\s*")),
    ("subcarpetas", re.compile(
        r"(?i)(?:^|[\s,;])(?:subcarpetas?|jerarqu[ií]a)\s*[:=]\s*")),
)


def _dividir_subcarpetas(valor: str) -> tuple[str, ...]:
    """Separa una lista de nombres por comas, punto y coma, barras o saltos."""
    partes = re.split(r"[,;|\n]+", valor)
    return tuple(parte.strip().strip("\"'") for parte in partes if parte.strip())


def _normalizar_subcarpetas(valor: Any) -> tuple[str, ...] | None:
    """Convierte el campo ``subcarpetas`` a una tupla de nombres limpios."""
    if valor is None:
        return None
    if isinstance(valor, str):
        return _dividir_subcarpetas(valor)
    if isinstance(valor, Iterable):
        return tuple(str(item).strip().strip("\"'")
                     for item in valor if str(item).strip())
    return None


def _campos_de_texto(texto: str) -> dict[str, str]:
    """Extrae los campos etiquetados aunque la orden venga en una sola línea."""
    marcas: list[tuple[int, int, str]] = []
    for campo, patron in _PATRONES:
        for coincidencia in patron.finditer(texto):
            marcas.append((coincidencia.start(), coincidencia.end(), campo))
    marcas.sort(key=lambda marca: marca[0])
    campos: dict[str, str] = {}
    for indice, (_inicio, fin, campo) in enumerate(marcas):
        siguiente = len(texto)
        for inicio_siguiente, _fin, _campo in marcas[indice + 1:]:
            if inicio_siguiente >= fin:
                siguiente = inicio_siguiente
                break
        valor = texto[fin:siguiente].strip().strip("\"'").strip()
        if valor and campo not in campos:
            campos[campo] = valor
    return campos


_PREFIJO_COMANDO = re.compile(
    r"(?is)^\s*(?:comando\s+)?"
    r"(crear\s+mtbgt|mtbgt|crear\s+godot|godot"
    r"|crear\s+todo|todo|crear\s+secuencia|secuencia"
    r"|crear\s+red\s+neuronal|red\s+neuronal|red_neuronal|red"
    r"|crear\s+carpeta|crear_carpeta)\b"
)


def _normalizar_comando(comando: Any) -> str:
    """Unifica los alias (``red``, ``red_neuronal``, ...) a los dos comandos."""
    limpio = re.sub(r"(?i)^\s*comando\s+", "", str(comando).strip().lower())
    limpio = re.sub(r"\s+", " ", limpio.replace("_", " ")).strip()
    if limpio in ("red", "red neuronal", "crear red", COMANDO_RED):
        return COMANDO_RED
    if limpio in ("mtbgt", "crear mtbgt", "godot", "crear godot",
                  COMANDO_MTBGT):
        return COMANDO_MTBGT
    if limpio in ("todo", "crear todo", "secuencia", "crear secuencia",
                  COMANDO_TODO):
        return COMANDO_TODO
    if limpio in ("src", "crear src", COMANDO_CARPETA):
        return COMANDO_CARPETA
    return limpio


def _defaults_comando(comando: str) -> tuple[str, str, tuple[str, ...] | None]:
    """Ruta, nombre y subcarpetas predeterminadas de cada acción."""
    if comando == COMANDO_RED:
        return RUTA_RED_PREDETERMINADA, NOMBRE_RED_PREDETERMINADO, SUBCARPETAS_RED
    if comando == COMANDO_MTBGT:
        return RUTA_MTBGT_PREDETERMINADA, NOMBRE_MTBGT_PREDETERMINADO, SUBCARPETAS_MTBGT
    return RUTA_PREDETERMINADA, NOMBRE_PREDETERMINADO, None


def _comando_de_texto(texto: str) -> str:
    """Comando indicado al principio del texto (por defecto ``crear carpeta``)."""
    coincidencia = _PREFIJO_COMANDO.match(texto)
    if coincidencia is None:
        return COMANDO_CARPETA
    return _normalizar_comando(coincidencia.group(1))


def _normalizar_orden(datos: Mapping[str, Any]) -> dict[str, Any]:
    """Normaliza una orden recibida como diccionario."""
    comando = _normalizar_comando(
        datos.get("comando") or datos.get("accion")
        or datos.get("orden") or COMANDO_CARPETA)
    ruta_def, nombre_def, sub_def = _defaults_comando(comando)
    ruta = (datos.get("ruta") or datos.get("ruta_donde_crear")
            or datos.get("ruta_crear") or datos.get("path") or ruta_def)
    nombre = (datos.get("nombre") or datos.get("nombre_carpeta")
              or datos.get("nombre_de_la_carpeta") or datos.get("carpeta")
              or nombre_def)
    subcarpetas = _normalizar_subcarpetas(
        datos.get("subcarpetas") or datos.get("jerarquia")
        or datos.get("carpetas"))
    if subcarpetas is None and sub_def is not None:
        subcarpetas = sub_def
    return {
        "comando": comando,
        "ruta": str(ruta).strip().strip("\"'"),
        "nombre": str(nombre).strip().strip("\"'"),
        "subcarpetas": subcarpetas,
    }


def _error_orden(mensaje: str) -> dict[str, Any]:
    """Estructura de error común al interpretar una orden."""
    return {"comando": "crear carpeta", "ruta": "", "nombre": "",
            "subcarpetas": None, "error": mensaje}


def interpretar_orden(orden: str | Mapping[str, Any]) -> dict[str, Any]:
    """Convierte texto, JSON o dict de la máquina en una orden normalizada.

    Acepta ``Ruta donde crear:`` y ``Nombre de la carpeta:`` en una o varias
    líneas, además de la forma corta ``crear carpeta <ruta> [nombre]``.
    """
    if isinstance(orden, Mapping):
        return _normalizar_orden(orden)
    texto = str(orden or "").strip()
    if not texto:
        return _error_orden("Orden vacía: no hay comando que ejecutar.")
    if texto.startswith("{"):
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as error:
            return _error_orden(f"JSON no válido: {error}")
        if not isinstance(datos, Mapping):
            return _error_orden("El JSON de la orden debe ser un objeto.")
        return _normalizar_orden(datos)

    comando = _comando_de_texto(texto)
    ruta_def, nombre_def, sub_def = _defaults_comando(comando)
    campos = _campos_de_texto(texto)
    if campos:
        if (comando == COMANDO_CARPETA
                and _PREFIJO_COMANDO.match(texto) is None):
            nombre_clave = str(campos.get("nombre", "")).strip().lower()
            ruta_clave = Path(str(campos.get("ruta", ""))).name.lower()
            if nombre_clave == NOMBRE_RED_PREDETERMINADO.lower():
                comando = COMANDO_RED
            elif (nombre_clave == NOMBRE_MTBGT_PREDETERMINADO.lower()
                  or ruta_clave == NOMBRE_MTBGT_PREDETERMINADO.lower()):
                comando = COMANDO_MTBGT
            if comando != COMANDO_CARPETA:
                ruta_def, nombre_def, sub_def = _defaults_comando(comando)
        return {
            "comando": comando,
            "ruta": (campos.get("ruta") or ruta_def).strip().strip("\"'"),
            "nombre": (campos.get("nombre")
                       or nombre_def).strip().strip("\"'"),
            "subcarpetas": (_normalizar_subcarpetas(campos.get("subcarpetas"))
                            or sub_def),
        }

    coincidencia = _PREFIJO_COMANDO.match(texto)
    if coincidencia is None:
        return _error_orden(
            "No reconozco la orden. Usa 'crear carpeta' o "
            "'crear red neuronal' con 'Ruta donde crear:' y "
            "'Nombre de la carpeta:'.")
    resto = texto[coincidencia.end():].strip()
    if not resto:
        return {"comando": comando, "ruta": ruta_def,
                "nombre": nombre_def, "subcarpetas": sub_def}
    try:
        partes = shlex.split(resto, posix=False)
    except ValueError:
        partes = resto.split()
    ruta = partes[0].strip().strip("\"'") if partes else ruta_def
    nombre = (partes[1].strip().strip("\"'")
              if len(partes) > 1 else nombre_def)
    return {"comando": comando, "ruta": ruta, "nombre": nombre,
            "subcarpetas": sub_def}


class ConstructorLucIA:
    """Ejecuta las órdenes de construcción de LucIA.

    ``maquina`` permite inyectar una fachada RFPRMN ya construida (pruebas).
    """

    COMANDOS = (COMANDO_CARPETA, COMANDO_RED, COMANDO_MTBGT, COMANDO_TODO)

    def __init__(self, ruta_red: str | Path | None = None,
                 maquina: Any | None = None) -> None:
        self.ruta_red = ruta_red
        self.rfprmn = maquina if maquina is not None else RFPRMN()
        self._red: Any | None = None

    # -- neuronas ---------------------------------------------------------
    def _crear_constructiva(self, ruta: Path, nombre: str,
                            subcarpetas: tuple[str, ...]) -> Any:
        """Instancia la neurona constructiva con la orden ya normalizada."""
        modulo = cargar_modulo_red(self.ruta_red)
        clase = _obtener_clase_constructiva()
        neurona = modulo.NeuronaEntradaXavier(DIM_ENTRADA, DIM_SALIDA)
        creativa = modulo.NeuronaEntradaXavier.NeuronaCreativa(neurona)
        return clase(creativa, self.rfprmn, str(ruta), nombre, subcarpetas)

    def _metricas_red(self, constructiva: Any, texto: str, nombre: str,
                      subcarpetas: tuple[str, ...]) -> dict[str, Any]:
        """Calcula impulso, entropía y afinidades de la orden."""
        datos: dict[str, Any] = {
            "familia": "ENRN.EN2_RN", "neurona": "NeuronaEntradaXavier",
            "dim_entrada": DIM_ENTRADA, "dim_salida": DIM_SALIDA,
        }
        try:
            datos["impulso"] = round(float(constructiva.impulso_creativo()), 6)
            datos["entropia"] = round(float(constructiva.entropia(texto)), 6)
            similitudes = {
                sub: round(float(constructiva.similitud(nombre, sub)), 6)
                for sub in subcarpetas
            }
            datos["similitudes"] = similitudes
            if similitudes:
                datos["afinidad_maxima"] = max(similitudes.values())
        except Exception as error:  # noqa: BLE001 - métrica diagnóstica
            datos["error"] = f"{type(error).__name__}: {error}"
        return datos

    def _calcular_red_general(self, constructiva: Any,
                              texto: str) -> dict[str, Any]:
        """Pasa la orden por LCBS_NEURONAL: ENRN -> RF_EN + salud global."""
        vector = constructiva.vector(texto)
        datos: dict[str, Any] = {"modulo": "LCBS_NEURONAL"}
        try:
            modulo = cargar_lcbs_neuronal()
            with _silencio():
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

    def _crear_si_falta(self, base: str, nombre: str) -> str:
        """Devuelve la carpeta existente o la crea validando el nombre."""
        limpio = str(nombre).strip()
        if not limpio or limpio in {".", ".."} or Path(limpio).name != limpio:
            return self.rfprmn.crear_carpeta_en(base, nombre)
        objetivo = Path(base) / limpio
        try:
            if (objetivo.is_dir()
                    and objetivo.parent.resolve() == Path(base).resolve()):
                return str(objetivo)
        except OSError:
            pass
        return self.rfprmn.crear_carpeta_en(base, nombre)

    def _crear_solo_carpetas(self, base: Path, nombre: str,
                             subcarpetas: tuple[str, ...]) -> dict[str, Any]:
        """Crea la jerarquía sin red neuronal: solo carpetas."""
        raiz = ""
        creadas: list[str] = []
        pasos: list[dict[str, Any]] = []
        try:
            raiz = self._crear_si_falta(str(base), nombre)
            pasos.append({"paso": 1, "carpeta": Path(raiz).name, "ruta": raiz})
            top_level: list[str] = []
            for subcarpeta in subcarpetas:
                partes = Path(subcarpeta).parts
                if not partes:
                    continue
                if partes[0] not in top_level:
                    top_level.append(partes[0])
                actual = raiz
                for parte in partes:
                    actual = self._crear_si_falta(actual, parte)
                creadas.append(actual)
            for numero, nombre_top in enumerate(top_level, start=2):
                pasos.append({"paso": numero, "carpeta": nombre_top,
                              "ruta": str(Path(raiz) / nombre_top)})
        except Exception as error:  # noqa: BLE001 - resultado degradado
            return {"ok": False, "error": f"{type(error).__name__}: {error}",
                    "raiz": raiz, "carpetas": creadas, "pasos": pasos,
                    "total": (1 if raiz else 0) + len(creadas)}
        return {"ok": True, "raiz": raiz, "carpetas": creadas,
                "total": 1 + len(creadas), "pasos": pasos}

    # -- API pública ------------------------------------------------------
    def crear_carpeta(self, ruta: str | Path = "",
                      nombre: str = NOMBRE_PREDETERMINADO,
                      subcarpetas: Iterable[str] | None = None,
                      archivos: Iterable[str] | None = None) -> dict[str, Any]:
        """Crea ``ruta/nombre`` y, si es ``src``, su jerarquía completa.

        Sin ``ruta`` usa ``RUTA_PREDETERMINADA`` y sin ``nombre`` usa
        ``NOMBRE_PREDETERMINADO``.  Si ``subcarpetas`` es ``None`` y el nombre
        es ``src`` se usa ``SUBCARPETAS_SRC``, toda la jerarquía de carpetas de
        ``TLLDCD/src``; en otro caso sólo la raíz.
        ``archivos`` permite crear ficheros vacíos dentro de la raíz.
        """
        ruta_texto = str(ruta or "").strip().strip("\"'") or RUTA_PREDETERMINADA
        base = Path(os.path.expandvars(os.path.expanduser(ruta_texto))).resolve()
        nombre = str(nombre or NOMBRE_PREDETERMINADO).strip()
        if subcarpetas is None:
            subcarpetas = (descubrir_subcarpetas_src()
                           if nombre.lower() == NOMBRE_PREDETERMINADO else ())
        elif isinstance(subcarpetas, str):
            subcarpetas = _dividir_subcarpetas(subcarpetas)
        else:
            subcarpetas = tuple(str(s).strip() for s in subcarpetas
                                if str(s).strip())

        resultado = self._crear_solo_carpetas(base, nombre, subcarpetas)
        if USAR_RED_NEURONAL:
            try:
                # Para la red se usan los nombres de primer nivel: el cálculo
                # matemático no necesita recorrer 1200 rutas anidadas.
                subcarpetas_red = tuple(dict.fromkeys(
                    Path(s).parts[0] for s in subcarpetas if Path(s).parts))
                constructiva = self._crear_constructiva(
                    base, nombre, subcarpetas_red)
                texto_orden = " ".join((str(base), nombre, *subcarpetas_red))
                red_general = self._calcular_red_general(
                    constructiva, texto_orden)
                metricas = self._metricas_red(
                    constructiva, texto_orden, nombre, subcarpetas_red)
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
            "rfprmn": {"version": getattr(_RFPRMN, "__version__", "")},
        })
        archivos_creados: list[str] = []
        if archivos is not None and resultado.get("ok"):
            if isinstance(archivos, str):
                archivos = (archivos,)
            try:
                for nombre_archivo in archivos:
                    archivos_creados.append(
                        self.rfprmn.crear_archivo(resultado["raiz"],
                                                  str(nombre_archivo)))
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
            ruta or RUTA_RED_PREDETERMINADA,
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
        ruta_texto = str(ruta or RUTA_MTBGT_PREDETERMINADA).strip().strip("\"'")
        root = Path(os.path.expandvars(
            os.path.expanduser(ruta_texto))).resolve()
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
        src = self.crear_carpeta()
        red = self.crear_red_neuronal()
        mtbgt = self.crear_mtbgt()
        acciones = [src, red, mtbgt]
        return {
            "ok": all(accion.get("ok") for accion in acciones),
            "comando": COMANDO_TODO,
            "acciones": acciones,
            "total": sum(int(accion.get("total", 0)) for accion in acciones),
        }

    def comando_crear_todo(self) -> dict[str, Any]:
        """Alias de la secuencia completa."""
        return self.crear_todo()

    def comando_crear_carpeta(self, ruta: str | Path = "",
                              nombre: str = NOMBRE_PREDETERMINADO,
                              subcarpetas: Iterable[str] | None = None) -> dict[str, Any]:
        """Alias del comando con la ruta y el nombre predeterminados."""
        return self.crear_carpeta(ruta, nombre, subcarpetas)

    def ejecutar(self, orden: str | Mapping[str, Any]) -> dict[str, Any]:
        """Interpreta y ejecuta una orden completa de la máquina de comandos."""
        datos = interpretar_orden(orden)
        if datos.get("error"):
            return {"ok": False, "comando": datos.get("comando", "crear carpeta"),
                    "error": datos["error"]}
        comando = datos.get("comando", "crear carpeta")
        if comando not in self.COMANDOS:
            return {"ok": False, "comando": comando,
                    "error": f"Comando no soportado: {comando!r}. "
                             f"Disponibles: {', '.join(self.COMANDOS)}"}
        if comando == COMANDO_TODO:
            return self.crear_todo()
        if comando == COMANDO_MTBGT:
            return self.crear_mtbgt(
                datos.get("ruta") or RUTA_MTBGT_PREDETERMINADA,
                datos.get("subcarpetas"))
        if comando == COMANDO_RED:
            return self.crear_red_neuronal(
                datos.get("ruta") or RUTA_RED_PREDETERMINADA,
                datos.get("nombre") or NOMBRE_RED_PREDETERMINADO,
                datos.get("subcarpetas"))
        return self.crear_carpeta(datos.get("ruta") or RUTA_PREDETERMINADA,
                                  datos.get("nombre") or NOMBRE_PREDETERMINADO,
                                  datos.get("subcarpetas"))


_CONSTRUCTOR: ConstructorLucIA | None = None


def obtener_constructor() -> ConstructorLucIA:
    """Constructor compartido (carga perezosa de la red y de RFPRMN)."""
    global _CONSTRUCTOR
    if _CONSTRUCTOR is None:
        _CONSTRUCTOR = ConstructorLucIA()
    return _CONSTRUCTOR


def ejecutar_orden(orden: str | Mapping[str, Any]) -> dict[str, Any]:
    """Atajo: interpreta y ejecuta una orden con el constructor compartido."""
    return obtener_constructor().ejecutar(orden)


def crear_carpeta(ruta: str | Path = "",
                  nombre: str = NOMBRE_PREDETERMINADO,
                  subcarpetas: Iterable[str] | None = None) -> dict[str, Any]:
    """Atajo programático; sin ruta usa ``RUTA_PREDETERMINADA``."""
    return obtener_constructor().crear_carpeta(ruta, nombre, subcarpetas)


def comando_crear_carpeta(ruta: str | Path = "",
                          nombre: str = NOMBRE_PREDETERMINADO,
                          subcarpetas: Iterable[str] | None = None) -> dict[str, Any]:
    """Alias con la ruta y el nombre predeterminados."""
    return crear_carpeta(ruta, nombre, subcarpetas)


def crear_red_neuronal(ruta: str | Path = "",
                       nombre: str = NOMBRE_RED_PREDETERMINADO,
                       subcarpetas: Iterable[str] | None = None) -> dict[str, Any]:
    """Atajo de la segunda acción; sin ruta usa ``RUTA_RED_PREDETERMINADA``."""
    return obtener_constructor().crear_red_neuronal(ruta, nombre, subcarpetas)


def comando_crear_red_neuronal(
    ruta: str | Path = "", nombre: str = NOMBRE_RED_PREDETERMINADO,
    subcarpetas: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Alias de la segunda acción con sus valores predeterminados."""
    return crear_red_neuronal(ruta, nombre, subcarpetas)


def crear_mtbgt(ruta: str | Path = "",
                subcarpetas: Iterable[str] | None = None,
                archivos: Iterable[str] | None = None) -> dict[str, Any]:
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


def formatear_resultado(resultado: Mapping[str, Any]) -> str:
    """Devuelve el informe de terminal (texto legible, sin JSON)."""
    acciones = resultado.get("acciones")
    if acciones:
        partes = [formatear_resultado(accion) for accion in acciones]
        estado = "OK" if resultado.get("ok") else "CON ERRORES"
        partes.append(
            f"Resultado global: {estado} · {resultado.get('total', 0)} carpetas")
        return "\n".join(partes)
    ancho = 74
    comando = resultado.get("comando", COMANDO_CARPETA)
    lineas = ["=" * ancho, f" LC_constructor · comando {comando}", "=" * ancho]
    if not resultado.get("ok"):
        lineas.append(f"ERROR: {resultado.get('error', 'desconocido')}")
        if resultado.get("ruta"):
            lineas.append(f"Ruta: {resultado['ruta']}")
        if resultado.get("nombre"):
            lineas.append(f"Carpeta: {resultado['nombre']}")
        lineas.append("=" * ancho)
        return "\n".join(lineas)
    red = resultado.get("red_general") or {}
    entrada = resultado.get("neurona_entrada") or {}
    diagnostico = red.get("diagnostico") or {}
    lineas.extend([
        f"Ruta           : {resultado.get('ruta_mtbgt') or resultado.get('ruta', '')}",
        f"Carpeta        : {resultado.get('nombre', '')}",
    ])
    if not red.get("omitida"):
        lineas.append(
            f"Red general    : LCBS_NEURONAL v{red.get('version', '?')}")
        salud = red.get("salud") or {}
        if salud:
            estados = " | ".join(
                f"{familia}={'OK' if ok else 'ERR'}"
                for familia, ok in salud.items())
            lineas.append(f"Familias       : {estados}")
        if red.get("ok"):
            lineas.extend([
                f"Modo           : {diagnostico.get('modo', '?')} "
                f"({diagnostico.get('neurona_enrn', '?')} -> "
                f"{diagnostico.get('neurona_rfen', '?')})",
                f"Accion         : {red.get('accion', [])}",
                f"Latencia       : {diagnostico.get('latencia_ms', 0):.3f} ms",
                f"Normas         : estado={diagnostico.get('norma_estado', 0):.4f} "
                f"latente={diagnostico.get('norma_latente', 0):.4f} "
                f"accion={diagnostico.get('norma_accion', 0):.4f}",
            ])
        else:
            lineas.append(f"Red general    : ERROR {red.get('error', '')}")
        if entrada:
            lineas.append(
                f"Neurona entrada: impulso={entrada.get('impulso', '?')} "
                f"entropia={entrada.get('entropia', '?')}")
    lineas.append(f"Jerarquia      : {resultado.get('total', 0)} carpetas")
    archivos = resultado.get("archivos") or []
    if archivos:
        lineas.append(
            "Archivos       : " + ", ".join(Path(a).name for a in archivos))
    for paso in resultado.get("pasos", []):
        lineas.append(f"  {paso.get('paso', '?'):>2}. {paso.get('carpeta', '')}")
    if resultado.get("advertencia"):
        lineas.append(f"AVISO          : {resultado['advertencia']}")
    estado = "OK" if red.get("ok") else "OK (creación; red general con error)"
    lineas.extend([f"Estado         : {estado}", "=" * ancho])
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI: por argumentos o con los valores predeterminados."""
    argumentos = list(sys.argv[1:] if argv is None else argv)
    pausa = "--pausa" in argumentos
    argumentos = [argumento for argumento in argumentos if argumento != "--pausa"]
    if argumentos:
        resultado = ejecutar_orden(" ".join(argumentos))
    else:
        resultado = crear_carpeta()
    print(formatear_resultado(resultado))
    if pausa or (not argumentos and sys.stdin.isatty()):
        try:
            input("\nPulsa Enter para cerrar...")
        except EOFError:
            pass
    return 0 if resultado.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ConstructorLucIA", "interpretar_orden", "localizar_red_neuronal",
    "cargar_modulo_red", "localizar_lcbs_neuronal", "cargar_lcbs_neuronal",
    "formatear_resultado", "obtener_constructor", "ejecutar_orden",
    "crear_carpeta", "comando_crear_carpeta",
    "crear_red_neuronal", "comando_crear_red_neuronal",
    "crear_mtbgt", "comando_crear_mtbgt",
    "crear_todo", "comando_crear_todo",
    "SUBCARPETAS_SRC", "SUBCARPETAS_RED", "SUBCARPETAS_MTBGT",
    "SUBCARPETAS_SRC_BASE", "descubrir_subcarpetas_src",
    "descubrir_jerarquia_src",
    "RUTA_PREDETERMINADA", "NOMBRE_PREDETERMINADO",
    "RUTA_FUENTE_PREDETERMINADA",
    "RUTA_RED_PREDETERMINADA", "NOMBRE_RED_PREDETERMINADO",
    "RUTA_MTBGT_PREDETERMINADA", "NOMBRE_MTBGT_PREDETERMINADO",
    "ARCHIVOS_MTBGT", "USAR_RED_NEURONAL",
    "COMANDO_CARPETA", "COMANDO_RED", "COMANDO_MTBGT", "COMANDO_TODO",
    "RFPRMN", "main", "__version__",
]
