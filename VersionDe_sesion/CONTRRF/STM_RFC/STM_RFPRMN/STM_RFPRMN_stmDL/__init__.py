"""Paquete STM_RFPRMN_stmDL: núcleo modularizado de RFPRMN.

El registro de símbolos ya **no se mantiene a mano** (D4): se descubre leyendo
el árbol sintáctico de cada submódulo con ``ast``. Así no hay deriva entre lo
que el código define y lo que el registro publica.

Reglas del descubrimiento:

- funciones y clases de nivel superior: siempre (públicas y privadas),
- constantes y variables de nivel superior: solo si no empiezan por ``_``,
- los nombres importados **no** se registran (evita duplicados y ruido),
- si un nombre aparece en dos módulos, gana el primero en ``_MODULOS``.

La carga sigue siendo perezosa (PEP 562): ``from paquete import X`` resuelve
``X`` en su módulo solo cuando se usa.
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any

__version__ = "2.6.0"

_MODULOS = ("stm_base", "stm_rutas", "stm_fs", "stm_fragmentos", "stm_gestion",
            "stm_analisis", "stm_lucia", "stm_embeddings", "stm_calidad",
            "stm_corpus", "stm_modelos", "stm_descarga", "stm_openrouter",
            "stm_refactor", "stm_flujo", "stm_registro", "stm_pesos", "stm_ipfs")


def _simbolos_del_modulo(modulo: str) -> list[str]:
    """Símbolos de nivel superior definidos en ``modulo`` (vía AST)."""
    ruta = Path(__file__).with_name(f"{modulo}.py")
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    nombres: list[str] = []
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not nodo.name.startswith("__"):
                nombres.append(nodo.name)
        elif isinstance(nodo, ast.Assign):
            for objetivo in nodo.targets:
                if isinstance(objetivo, ast.Name) and not objetivo.id.startswith("_"):
                    nombres.append(objetivo.id)
        elif isinstance(nodo, ast.AnnAssign):
            objetivo = nodo.target
            if isinstance(objetivo, ast.Name) and not objetivo.id.startswith("_"):
                nombres.append(objetivo.id)
    return nombres


#: Mapa símbolo -> módulo que lo define (resolución perezosa).
_REGISTRO: dict[str, str] = {}
for _modulo in _MODULOS:
    for _simbolo in _simbolos_del_modulo(_modulo):
        _REGISTRO.setdefault(_simbolo, _modulo)
del _modulo, _simbolo

__all__ = sorted(_REGISTRO.keys()) + ["RegistroRFPRMN", "crear_instancia",
    "version_info", "modulos_estado", "verificar_presupuesto", "resolver",
    "nombres", "__version__"]


def _importar(modulo: str):
    """Importa un submódulo por nombre corto."""
    return importlib.import_module(f"{__name__}.{modulo}")


def resolver(nombre: str) -> Any:
    """Devuelve el objeto público ``nombre`` cargando su módulo si hace falta."""
    modulo = _REGISTRO.get(nombre)
    if modulo is None:
        raise AttributeError(f"Símbolo desconocido: {nombre}")
    return getattr(_importar(modulo), nombre)


def nombres() -> list[str]:
    """Lista ordenada de símbolos registrados."""
    return sorted(_REGISTRO.keys())


def __getattr__(nombre: str) -> Any:
    """PEP 562: permite ``from paquete import simbolo`` sin cargarlo todo."""
    if nombre in _REGISTRO:
        return resolver(nombre)
    raise AttributeError(f"módulo {__name__!r} no tiene atributo {nombre!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_REGISTRO.keys()))


class RegistroRFPRMN:
    """Registro central: mapa nombre -> (módulo, objeto) con carga perezosa.

    Evita importar los backends pesados (Ollama/HF/red neuronal) hasta su
    primer uso y ofrece introspección y verificación de presupuesto de líneas.
    """

    _cache: dict[str, Any] = {}
    _fallos: dict[str, str] = {}

    @classmethod
    def nombres(cls) -> list[str]:
        """Nombres públicos registrados."""
        return nombres()

    @classmethod
    def modulo_de(cls, nombre: str) -> str:
        """Módulo que define ``nombre`` (KeyError si no existe)."""
        if nombre not in _REGISTRO:
            raise KeyError(f"Símbolo no registrado: {nombre}")
        return _REGISTRO[nombre]

    @classmethod
    def obtener(cls, nombre: str) -> Any:
        """Obtiene (y cachea) el objeto ``nombre``."""
        if nombre in cls._cache:
            return cls._cache[nombre]
        obj = resolver(nombre)
        cls._cache[nombre] = obj
        return obj

    @classmethod
    def cargar_modulo(cls, modulo: str) -> Any:
        """Importa un submódulo completo por nombre corto."""
        if modulo not in _MODULOS:
            raise KeyError(f"Módulo desconocido: {modulo}")
        return _importar(modulo)

    @classmethod
    def precargar(cls, *nombres_sel: str) -> dict[str, Any]:
        """Carga anticipada de una lista de símbolos; devuelve los resueltos."""
        out: dict[str, Any] = {}
        for nombre in nombres_sel:
            try:
                out[nombre] = cls.obtener(nombre)
            except Exception as error:  # noqa: BLE001 - se acumula el fallo
                cls._fallos[nombre] = str(error)
        return out

    @classmethod
    def fallos(cls) -> dict[str, str]:
        """Fallos acumulados de precargas."""
        return dict(cls._fallos)

    @classmethod
    def limpiar_cache(cls) -> None:
        """Vacía la caché de objetos resueltos."""
        cls._cache.clear()
        cls._fallos.clear()

    @classmethod
    def resumen(cls) -> dict[str, Any]:
        """Resumen del registro: módulos, nº símbolos y estado de caché."""
        por_mod: dict[str, int] = {modulo: 0 for modulo in _MODULOS}
        for modulo in _REGISTRO.values():
            por_mod[modulo] = por_mod.get(modulo, 0) + 1
        return {"version": __version__, "modulos": list(_MODULOS),
                "simbolos_totales": len(_REGISTRO), "por_modulo": por_mod,
                "cacheados": len(cls._cache), "fallos": len(cls._fallos)}

    @classmethod
    def verificar_imports(cls) -> dict[str, str]:
        """Intenta importar cada submódulo; devuelve {modulo: 'OK'|'error'}."""
        estado: dict[str, str] = {}
        for modulo in _MODULOS:
            try:
                cls.cargar_modulo(modulo)
                estado[modulo] = "OK"
            except Exception as error:  # noqa: BLE001 - se informa del fallo
                estado[modulo] = f"ERROR: {error}"
        return estado

    @classmethod
    def buscar(cls, patron: str) -> list[str]:
        """Busca símbolos por subcadena (insensible a mayúsculas)."""
        objetivo = patron.lower()
        return sorted(nombre for nombre in _REGISTRO if objetivo in nombre.lower())

    @classmethod
    def es_comando(cls, nombre: str) -> bool:
        """True si el símbolo es un comando interactivo conocido."""
        return nombre in {"comando_refactorizar", "comando_crear_carpeta",
                          "comando_crear_archivo", "comando_enviar", "actualizar",
                          "comando_ia_local", "comando_ds_ialocal"}

    @classmethod
    def comandos(cls) -> list[str]:
        """Lista de comandos interactivos disponibles."""
        return sorted(nombre for nombre in _REGISTRO if cls.es_comando(nombre))


def crear_instancia(raiz: str | Path | None = None):
    """Crea una instancia de la fachada RFPRMN (import diferido)."""
    modulo = importlib.import_module("RFPRMN")
    clase = getattr(modulo, "RFPRMN")
    return clase(raiz=raiz) if raiz is not None else clase()


def version_info() -> dict[str, Any]:
    """Versión del paquete y nº de símbolos registrados."""
    return {"version": __version__, "simbolos": len(_REGISTRO),
            "modulos": list(_MODULOS)}


def modulos_estado() -> dict[str, Any]:
    """Estado de cada submódulo: import OK/ERROR + nº de líneas físicas."""
    base = Path(__file__).resolve().parent
    estado: dict[str, Any] = {}
    for modulo in _MODULOS:
        archivo = base / f"{modulo}.py"
        try:
            lineas = len(archivo.read_text(encoding="utf-8").splitlines()) if archivo.exists() else -1
        except OSError:
            lineas = -1
        try:
            _importar(modulo)
            estado[modulo] = {"import": "OK", "lineas": lineas}
        except Exception as error:  # noqa: BLE001 - se informa del fallo
            estado[modulo] = {"import": f"ERROR: {error}", "lineas": lineas}
    return estado


def verificar_presupuesto(max_lineas: int = 450) -> dict[str, Any]:
    """Verifica que ningún módulo supere ``max_lineas`` (anti-regresión)."""
    base = Path(__file__).resolve().parent
    detalle: dict[str, int] = {}
    for modulo in _MODULOS:
        archivo = base / f"{modulo}.py"
        try:
            detalle[modulo] = len(archivo.read_text(encoding="utf-8").splitlines())
        except OSError:
            detalle[modulo] = -1
    for extra in (base.parent / "RFPRMN.py", base / "__init__.py"):
        try:
            etiqueta = extra.name if extra.name != "__init__.py" else "STM_RFPRMN_stmDL/__init__.py"
            detalle[etiqueta] = len(extra.read_text(encoding="utf-8").splitlines())
        except OSError:
            pass
    excedidos = {nombre: lineas for nombre, lineas in detalle.items()
                 if lineas > max_lineas}
    return {"max": max_lineas, "detalle": detalle, "excedidos": excedidos,
            "ok": not excedidos}


def tabla_comandos() -> list[tuple[str, str]]:
    """Pares (comando, módulo) de los comandos interactivos registrados."""
    return [(nombre, _REGISTRO[nombre]) for nombre in sorted(_REGISTRO)
            if RegistroRFPRMN.es_comando(nombre)]


def ayuda_comando(nombre: str) -> str:
    """Una línea de ayuda para un comando (vacía si no es comando)."""
    limpio = nombre.strip().lower()
    if not RegistroRFPRMN.es_comando(limpio):
        return ""
    return f"{limpio} (módulo {RegistroRFPRMN.modulo_de(limpio)})"


def diagnostico_imports() -> dict[str, Any]:
    """Diagnóstico de imports: estado por módulo + fallos de precarga."""
    return {"imports": RegistroRFPRMN.verificar_imports(),
            "fallos_precarga": RegistroRFPRMN.fallos(),
            "cacheados": len(RegistroRFPRMN._cache)}


def contar_lineas() -> dict[str, int]:
    """Nº de líneas físicas por submódulo (sin importar nada)."""
    base = Path(__file__).resolve().parent
    salida: dict[str, int] = {}
    for modulo in _MODULOS:
        archivo = base / f"{modulo}.py"
        try:
            salida[modulo] = len(archivo.read_text(encoding="utf-8").splitlines()) if archivo.exists() else -1
        except OSError:
            salida[modulo] = -1
    salida["__init__"] = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    return salida


def informe_salud(max_lineas: int = 450) -> dict[str, Any]:
    """Informe combinado: imports + líneas + presupuesto en un solo dict."""
    salud_imports = RegistroRFPRMN.verificar_imports()
    lineas = contar_lineas()
    presupuesto = verificar_presupuesto(max_lineas)
    ok_imports = all(valor == "OK" for valor in salud_imports.values())
    return {"imports_ok": ok_imports, "imports": salud_imports,
            "lineas": lineas, "presupuesto": presupuesto,
            "saludable": ok_imports and bool(presupuesto["ok"])}


def simbolos_por_modulo(modulo: str) -> list[str]:
    """Símbolos registrados que define ``modulo`` (KeyError si no existe)."""
    if modulo not in _MODULOS:
        raise KeyError(f"Módulo desconocido: {modulo}")
    return sorted(nombre for nombre, origen in _REGISTRO.items() if origen == modulo)


def documentar_registro() -> str:
    """Resumen en texto del registro (nº símbolos por módulo)."""
    lineas_out = [f"STM_RFPRMN_stmDL v{__version__}: {len(_REGISTRO)} símbolos"]
    for modulo in _MODULOS:
        cantidad = sum(1 for origen in _REGISTRO.values() if origen == modulo)
        lineas_out.append(f"  - {modulo}: {cantidad} símbolos")
    return "\n".join(lineas_out)
