"""Paquete STM_RFPRMN_stmDL: nucleo modularizado de RFPRMN.

Expone un registro perezoso (PEP 562) y la clase RegistroRFPRMN para
resolver los ~75 simbolos publicos sin cargar todos los backends
(Ollama/HF/OpenRouter) al arrancar.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Callable, Optional

__version__ = "2.0.0"

_MODULOS = ("stm_base", "stm_gestion", "stm_analisis", "stm_modelos", "stm_refactor", "stm_flujo", "stm_registro")

# Mapa simbolo -> modulo que lo define (resolucion perezosa).
_REGISTRO: dict[str, str] = {}
_BASE_SYMS = ["Estilo", "E", "ANCHO_TERMINAL", "_caja", "_panel", "RESPUESTAS_AFIRMATIVAS",
    "LIMITE_TAMANO_ANALISIS", "EXTENSIONES_POR_LENGUAJE", "PATRON_MARCADOR_PENDIENTE",
    "ErrorProyecto", "RaizProyectoNoEncontrada", "_imprimir_seguro", "informar", "exito",
    "advertir", "reportar_error", "pedir_confirmacion", "MODULO_DIR", "TLLDCD_DIR",
    "CONTRRF_DIR", "SRC_DIR", "encontrar_raiz", "RAIZ", "ORIGEN", "DESTINO",
    "CONFIG_IA_LOCAL", "RFC_DIR", "PRY_DIR", "carpetas_creadas"]
for _s in _BASE_SYMS:
    _REGISTRO[_s] = "stm_base"
_GESTION_SYMS = ["hacer_escribible", "_forzar_borrado", "eliminar_ruta", "borrar_contenido",
    "copiar_contenido", "encontrar_contenido_actual", "_ultima_actualizacion_pry",
    "_es_layout_actual", "comando_refactorizar", "_refactorizar_layout_actual",
    "crear_carpeta", "comando_crear_carpeta", "comando_crear_archivo", "DIR_REGISTRO_JSON",
    "REGISTRO_ENVIOS",
    "DIR_REGISTRO_JSON",
    "_contar_ficheros", "_registrar_envio", "comando_enviar", "actualizar",
    "_actualizar_layout_actual"]
for _s in _GESTION_SYMS:
    _REGISTRO[_s] = "stm_gestion"
_ANALISIS_SYMS = ["AnalisisArchivo", "analizar_archivo_local", "crear_plan_refactorizacion",
    "_crear_diagnostico_respaldo", "_cargar_configuracion_ia_local", "consultar_ia_local",
    "ConsultorIA", "comando_ia_local"]
for _s in _ANALISIS_SYMS:
    _REGISTRO[_s] = "stm_analisis"
_MODELOS_SYMS = ["DIR_MODELOS_LOCAL", "HF_REPO_CODIGO", "HF_ARCHIVO_CODIGO",
    "MODELOS_CODIGO_LIGEROS", "LIMITE_LINEAS_REFACTOR", "REGISTRO_REFACTOR_MD",
    "MODELOS_OR_CODIGO", "ENDPOINT_OPENROUTER", "_leer_openrouter_key", "_chat_openrouter",
    "_refactorizar_con_openrouter", "_descargar_peso_hf", "_modelos_ollama_instalados",
    "_es_modelo_codigo", "_leer_candidatos_codigo", "_borrar_peso_local",
    "_descargar_modelo_ollama", "_modelos_usados_registro", "_asegurar_modelo_codigo",
    "_borrar_modelo_ollama", "_liberar_ollama"]
for _s in _MODELOS_SYMS:
    _REGISTRO[_s] = "stm_modelos"
_REFACTOR_SYMS = ["_generar_fragmento", "_refactorizar_con_modelo",
    "_validar_refactor", "_registrar_refactor_md", "_pedir_extra_o_diagnostico",
    "comando_ds_ialocal", "_fallback_openrouter"]
for _s in _REFACTOR_SYMS:
    _REGISTRO[_s] = "stm_refactor"
_FLUJO_SYMS = ["FlujoRefactorLucIA", "cerrar", "mostrar_menu", "ejecutar_comandos"]
for _s in _FLUJO_SYMS:
    _REGISTRO[_s] = "stm_flujo"
_REGISTRO_SYMS = ["DIR_REGISTRO", "RUTA_JSON", "RUTA_MD", "RUTA_PESOS",
    "DIM_VECTOR", "IPFS_API_URL", "IPFS_GATEWAY_URL", "NOMBRE_PESOS",
    "leer_eventos", "construir_texto", "texto_a_vector",
    "norma", "seccionar_md", "cuantizar", "desnormalizar",
    "similitud_coseno", "md_a_pesos", "verificar_pesos", "vista_previa",
    "url_pasarela", "subir_a_ipfs", "limpiar_registro", "limpiar_caches",
    "publicar_registro_actualizar"]
for _s in _REGISTRO_SYMS:
    _REGISTRO[_s] = "stm_registro"
_REGISTRO["LINEAS_POR_FRAGMENTO"] = "stm_modelos"

__all__ = sorted(_REGISTRO.keys()) + ["RegistroRFPRMN", "crear_instancia", "version_info",
    "modulos_estado", "verificar_presupuesto", "resolver", "nombres", "__version__"]


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
    """Lista ordenada de símbolos públicos registrados."""
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

    Evita importar los backends pesados (Ollama/HF) hasta su primer uso
    y ofrece introspección y verificación de presupuesto de líneas.
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
        for n in nombres_sel:
            try:
                out[n] = cls.obtener(n)
            except Exception as e:
                cls._fallos[n] = str(e)
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
        por_mod: dict[str, int] = {m: 0 for m in _MODULOS}
        for _n, _m in _REGISTRO.items():
            por_mod[_m] = por_mod.get(_m, 0) + 1
        return {"version": __version__, "modulos": list(_MODULOS),
                "simbolos_totales": len(_REGISTRO), "por_modulo": por_mod,
                "cacheados": len(cls._cache), "fallos": len(cls._fallos)}

    @classmethod
    def verificar_imports(cls) -> dict[str, str]:
        """Intenta importar cada submódulo; devuelve {modulo: 'OK'|'error'}."""
        estado: dict[str, str] = {}
        for m in _MODULOS:
            try:
                cls.cargar_modulo(m)
                estado[m] = "OK"
            except Exception as e:
                estado[m] = f"ERROR: {e}"
        return estado

    @classmethod
    def buscar(cls, patron: str) -> list[str]:
        """Busca símbolos por subcadena (insensible a mayúsculas)."""
        p = patron.lower()
        return sorted(n for n in _REGISTRO if p in n.lower())

    @classmethod
    def es_comando(cls, nombre: str) -> bool:
        """True si el símbolo es un comando interactivo conocido."""
        return nombre in {"comando_refactorizar", "comando_crear_carpeta",
                          "comando_crear_archivo", "comando_enviar", "actualizar",
                          "comando_ia_local", "comando_ds_ialocal"}

    @classmethod
    def comandos(cls) -> list[str]:
        """Lista de comandos interactivos disponibles."""
        return sorted(n for n in _REGISTRO if cls.es_comando(n))


def crear_instancia(raiz: str | Path | None = None):
    """Crea una instancia de la fachada RFPRMN (import diferido)."""
    from .stm_flujo import ejecutar_comandos as _ej  # noqa: F401 (calienta import)
    mod = importlib.import_module("RFPRMN")
    cls = getattr(mod, "RFPRMN")
    return cls(raiz=raiz) if raiz is not None else cls()


def version_info() -> dict[str, Any]:
    """Versión del paquete y nº de símbolos registrados."""
    return {"version": __version__, "simbolos": len(_REGISTRO), "modulos": list(_MODULOS)}


def modulos_estado() -> dict[str, Any]:
    """Estado de cada submódulo: import OK/ERROR + nº de líneas físicas."""
    base = Path(__file__).resolve().parent
    estado: dict[str, Any] = {}
    for m in _MODULOS:
        f = base / f"{m}.py"
        try:
            n = len(f.read_text(encoding="utf-8").splitlines()) if f.exists() else -1
        except OSError:
            n = -1
        try:
            _importar(m)
            estado[m] = {"import": "OK", "lineas": n}
        except Exception as e:
            estado[m] = {"import": f"ERROR: {e}", "lineas": n}
    return estado


def verificar_presupuesto(max_lineas: int = 450) -> dict[str, Any]:
    """Verifica que ningún módulo supere ``max_lineas`` (anti-regresión)."""
    base = Path(__file__).resolve().parent
    detalle: dict[str, int] = {}
    for m in _MODULOS:
        f = base / f"{m}.py"
        try:
            detalle[m] = len(f.read_text(encoding="utf-8").splitlines())
        except OSError:
            detalle[m] = -1
    # Incluye la fachada RFPRMN.py y este __init__ en el control.
    for extra in [base.parent / "RFPRMN.py", base / "__init__.py"]:
        try:
            detalle[extra.name if extra.name != "__init__.py" else "STM_RFPRMN_stmDL/__init__.py"] = len(
                extra.read_text(encoding="utf-8").splitlines())
        except OSError:
            pass
    excedidos = {k: v for k, v in detalle.items() if v > max_lineas}
    return {"max": max_lineas, "detalle": detalle, "excedidos": excedidos,
            "ok": not excedidos}


def tabla_comandos() -> list[tuple[str, str]]:
    """Pares (comando, módulo) de los comandos interactivos registrados."""
    return [(n, _REGISTRO[n]) for n in sorted(_REGISTRO) if RegistroRFPRMN.es_comando(n)]


def ayuda_comando(nombre: str) -> str:
    """Una línea de ayuda para un comando (vacía si no es comando)."""
    if not RegistroRFPRMN.es_comando(nombre.strip().lower()):
        return ""
    return f"{nombre.strip().lower()} (módulo {RegistroRFPRMN.modulo_de(nombre.strip().lower())})"


def diagnostico_imports() -> dict[str, Any]:
    """Diagnóstico de imports: estado por módulo + fallos de precarga."""
    return {"imports": RegistroRFPRMN.verificar_imports(),
            "fallos_precarga": RegistroRFPRMN.fallos(),
            "cacheados": len(RegistroRFPRMN._cache)}


def contar_lineas() -> dict[str, int]:
    """Nº de líneas físicas por submódulo (sin importar nada)."""
    base = Path(__file__).resolve().parent
    out: dict[str, int] = {}
    for m in _MODULOS:
        f = base / f"{m}.py"
        try:
            out[m] = len(f.read_text(encoding="utf-8").splitlines()) if f.exists() else -1
        except OSError:
            out[m] = -1
    out["__init__"] = len(Path(__file__).read_text(encoding="utf-8").splitlines())
    return out


def informe_salud(max_lineas: int = 450) -> dict[str, Any]:
    """Informe combinado: imports + líneas + presupuesto en un solo dict."""
    salud_imports = RegistroRFPRMN.verificar_imports()
    lineas = contar_lineas()
    presup = verificar_presupuesto(max_lineas)
    ok_imports = all(v == "OK" for v in salud_imports.values())
    return {"imports_ok": ok_imports, "imports": salud_imports,
            "lineas": lineas, "presupuesto": presup,
            "saludable": ok_imports and bool(presup["ok"])}


def simbolos_por_modulo(modulo: str) -> list[str]:
    """Símbolos públicos definidos en ``modulo`` (KeyError si no existe)."""
    if modulo not in _MODULOS:
        raise KeyError(f"Módulo desconocido: {modulo}")
    return sorted(n for n, m in _REGISTRO.items() if m == modulo)


def documentar_registro() -> str:
    """Resumen en texto del registro (nº símbolos por módulo)."""
    lineas_out = [f"STM_RFPRMN_stmDL v{__version__}: {len(_REGISTRO)} símbolos"]
    for m in _MODULOS:
        n = sum(1 for _m in _REGISTRO.values() if _m == m)
        lineas_out.append(f"  - {m}: {n} símbolos")
    return "\n".join(lineas_out)


# --- Re-exports directos (compatibilidad: from paquete import X) --------------
# Se cargan de forma tolerante para no romper si un backend pesado falla.
try:
    from .stm_base import (  # noqa: F401,E402
        Estilo, E, ANCHO_TERMINAL, _caja, _panel, RESPUESTAS_AFIRMATIVAS,
        LIMITE_TAMANO_ANALISIS, EXTENSIONES_POR_LENGUAJE, PATRON_MARCADOR_PENDIENTE,
        ErrorProyecto, RaizProyectoNoEncontrada, _imprimir_seguro, informar, exito,
        advertir, reportar_error, pedir_confirmacion, MODULO_DIR, TLLDCD_DIR,
        CONTRRF_DIR, SRC_DIR, encontrar_raiz, RAIZ, ORIGEN, DESTINO,
        CONFIG_IA_LOCAL, RFC_DIR, PRY_DIR, carpetas_creadas,
    )
except Exception:
    pass
try:
    from .stm_gestion import (  # noqa: F401,E402
        hacer_escribible, eliminar_ruta, borrar_contenido, copiar_contenido,
        encontrar_contenido_actual, comando_refactorizar, crear_carpeta,
        comando_crear_carpeta, comando_crear_archivo, _contar_ficheros,
        DIR_REGISTRO_JSON, REGISTRO_ENVIOS,
        _registrar_envio, comando_enviar, actualizar,
    )
except Exception:
    pass
try:
    from .stm_analisis import (  # noqa: F401,E402
        AnalisisArchivo, analizar_archivo_local, crear_plan_refactorizacion,
        consultar_ia_local, ConsultorIA, comando_ia_local,
    )
except Exception:
    pass
try:
    from .stm_modelos import (  # noqa: F401,E402
        DIR_MODELOS_LOCAL, LIMITE_LINEAS_REFACTOR, LINEAS_POR_FRAGMENTO,
        REGISTRO_REFACTOR_MD, _borrar_peso_local,
    )
except Exception:
    pass
try:
    from .stm_refactor import (  # noqa: F401,E402
        comando_ds_ialocal,
    )
except Exception:
    pass
try:
    from .stm_flujo import (  # noqa: F401,E402
        FlujoRefactorLucIA, cerrar, mostrar_menu, ejecutar_comandos,
    )
except Exception:
    pass
try:
    from .stm_registro import (  # noqa: F401,E402
        DIR_REGISTRO, RUTA_MD, RUTA_PESOS, DIM_VECTOR, leer_eventos,
        construir_texto, texto_a_vector, md_a_pesos, subir_a_ipfs,
        limpiar_registro, limpiar_caches, publicar_registro_actualizar, verificar_pesos,
        similitud_coseno, vista_previa, url_pasarela,
    )
except Exception:
    pass
