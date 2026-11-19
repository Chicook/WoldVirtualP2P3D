"""CLI del ciclo de vida del código de WoldVirtualP2P3D (fachada).

La lógica vive en ``STM_RFPRMN_stmDL/``; aquí se re-exporta y se expone la CLI.


Purpose: this module acts as a compatibility facade for the project’s refactor lifecycle.
It exposes the same public symbols and commands as the original RFPRMN.py while routing the actual implementation to the submodules under STM_RFPRMN_stmDL.
It provides a command-line interface for operations such as:
creating folders/files,
copying or updating project content between PRY and RFC,
sending code to the target location,
running local AI analysis and refactoring workflows,
checking module status and budget limits,
managing model downloads and cleanup.
It also preserves the legacy usage pattern by exposing a class named RFPRMN with methods that mirror the old commands.


"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional

__version__ = "2.25.0"

# ─── Rutas de arranque: Nuevo sistema general de rutas ───────────────────────
_MODULO_DIR = Path(__file__).resolve().parent
_PAQUETE_DIR = _MODULO_DIR / "STM_RFPRMN_stmDL"
_STM_RFC_DIR = _MODULO_DIR.parent
_CONTRUCCION_DIR = _STM_RFC_DIR.parent
_DEV_DIR = _CONTRUCCION_DIR / ".dev"
_VENV_DIR = _DEV_DIR / "venv"
_PYTHON_DIR = _DEV_DIR / ".python"
_RFC_DIR = _CONTRUCCION_DIR.parent
_CONTRRF_DIR = _RFC_DIR.parent
_VERSION_DIR = _CONTRRF_DIR.parent
_PRY_DIR = _VERSION_DIR / "SistemaPrincipal" / "PRY"
_TLLDCD_SRC = _CONTRUCCION_DIR / "TLLDCD" / "src"
_PYTEST_CACHE = _DEV_DIR / ".pytest_cache"
_RUFF_CACHE = _DEV_DIR / ".ruff_cache"


def _raiz_repositorio() -> Path:
    """Raíz que debe estar en ``sys.path`` para importar ``VersionDesesion.*``.

    Se deduce subiendo desde este archivo hasta el directorio que contiene
    ``VersionDesesion``; si el árbol se movió, cae en la carpeta del módulo.
    """
    for candidato in _MODULO_DIR.parents:
        if (candidato / "VersionDesesion").is_dir():
            return candidato
    return _MODULO_DIR


_RAIZ_REPO = _raiz_repositorio()

_PYTHON_VENV_EXE = _VENV_DIR / "Scripts" / "python.exe"
_PYTHON_STANDALONE_EXE = _PYTHON_DIR / "python.exe"
_PYTHON_EJECUTABLE = (
    _PYTHON_VENV_EXE if _PYTHON_VENV_EXE.is_file()
    else (_PYTHON_STANDALONE_EXE if _PYTHON_STANDALONE_EXE.is_file() else Path(sys.executable))
)


def _configurar_entorno_arranque() -> None:
    """Configura las variables de entorno oficiales del nuevo sistema general de rutas."""
    if _VENV_DIR.is_dir():
        os.environ.setdefault("VIRTUAL_ENV", str(_VENV_DIR))
    if _PYTHON_DIR.is_dir():
        os.environ.setdefault("PYTHONHOME", str(_PYTHON_DIR))
    if _PYTHON_EJECUTABLE.is_file():
        os.environ.setdefault("WVP_PYTHON", str(_PYTHON_EJECUTABLE))
    if _RFC_DIR.is_dir():
        os.environ.setdefault("RFPRMN_RFC_DIR", str(_RFC_DIR))
    if _PRY_DIR.is_dir():
        os.environ.setdefault("RFPRMN_PRY_DIR", str(_PRY_DIR))
    if _DEV_DIR.is_dir():
        os.environ.setdefault("PYTEST_CACHE_DIR", str(_PYTEST_CACHE))
        os.environ.setdefault("RUFF_CACHE_DIR", str(_RUFF_CACHE))


_configurar_entorno_arranque()

# Todo bytecode compilado por la herramienta vive en .dev/pycache; el árbol de
# fuentes no genera __pycache__.
if _DEV_DIR.is_dir():
    sys.pycache_prefix = str(_DEV_DIR / "pycache")

for _ruta in (str(_MODULO_DIR), str(_PAQUETE_DIR), str(_RAIZ_REPO), str(_TLLDCD_SRC), str(_DEV_DIR)):
    if _ruta and _ruta not in sys.path:
        sys.path.insert(0, _ruta)

try:
    from STM_RFPRMN_stmDL import RegistroRFPRMN as _Registro  # noqa: E402
    from STM_RFPRMN_stmDL.stm_base import (  # noqa: E402,F401
        Estilo, E, ANCHO_TERMINAL, _caja, _panel, RESPUESTAS_AFIRMATIVAS,
        LIMITE_TAMANO_ANALISIS, EXTENSIONES_POR_LENGUAJE, PATRON_MARCADOR_PENDIENTE,
        ErrorProyecto, RaizProyectoNoEncontrada, _imprimir_seguro, informar, exito,
        advertir, reportar_error, pedir_confirmacion, MODULO_DIR, TLLDCD_DIR,
        CONTRRF_DIR, SRC_DIR, encontrar_raiz, RAIZ, ORIGEN, DESTINO,
        CONFIG_IA_LOCAL, RFC_DIR, PRY_DIR, carpetas_creadas,
    )
    from STM_RFPRMN_stmDL.stm_gestion import (  # noqa: E402,F401
        hacer_escribible, _forzar_borrado, eliminar_ruta, borrar_contenido,
        copiar_contenido, encontrar_contenido_actual, _ultima_actualizacion_pry,
        _es_layout_actual, comando_refactorizar, _refactorizar_layout_actual,
        crear_carpeta, crear_archivo, comando_crear_carpeta, comando_crear_archivo,
        copiar_codigo, comando_copiar_codigo,
        REGISTRO_ENVIOS, DIR_REGISTRO_JSON, _contar_ficheros, _registrar_envio, comando_enviar,
        actualizar, _actualizar_layout_actual,
    )
    from STM_RFPRMN_stmDL.stm_analisis import (  # noqa: E402,F401
        AnalisisArchivo, analizar_archivo_local, crear_plan_refactorizacion,
        _crear_diagnostico_respaldo, _cargar_configuracion_ia_local,
        consultar_ia_local, ConsultorIA, comando_ia_local,
    )
    from STM_RFPRMN_stmDL.stm_modelos import (  # noqa: E402,F401
        DIR_MODELOS_LOCAL, HF_REPO_CODIGO, HF_ARCHIVO_CODIGO,
        MODELOS_CODIGO_LIGEROS, LIMITE_LINEAS_REFACTOR, LINEAS_POR_FRAGMENTO, REGISTRO_REFACTOR_MD,
        MODELOS_OR_CODIGO, ENDPOINT_OPENROUTER, _leer_openrouter_key,
        _chat_openrouter, _refactorizar_con_openrouter, _descargar_peso_hf,
        _modelos_ollama_instalados, _es_modelo_codigo, _leer_candidatos_codigo,
        _borrar_peso_local, _descargar_modelo_ollama, _modelos_usados_registro,
        _asegurar_modelo_codigo, _borrar_modelo_ollama, _liberar_ollama,
    )
    from STM_RFPRMN_stmDL.stm_refactor import (  # noqa: E402,F401
        _generar_fragmento, _refactorizar_con_modelo,
        _validar_refactor, _registrar_refactor_md, _pedir_extra_o_diagnostico,
        comando_ds_ialocal, _fallback_openrouter,
    )
    from STM_RFPRMN_stmDL.stm_flujo import (  # noqa: E402,F401
        FlujoRefactorLucIA,
        cerrar as _cerrar_flujo, mostrar_menu as _mostrar_menu,
        ejecutar_comandos as _ejecutar_comandos,
    )
    from STM_RFPRMN_stmDL.stm_registro import (  # noqa: E402,F401
        DIR_REGISTRO, RUTA_MD, RUTA_PESOS, publicar_registro_actualizar,
        limpiar_registro, verificar_pesos, vista_previa, similitud_coseno,
    )
    from STM_RFPRMN_stmDL.stm_rutas import (  # noqa: E402,F401
        comando_configurar_rutas, comando_rutas, estado_rutas, guardar_rutas,
        actualizar_rutas_finales, leer_rutas_finales,
    )
    from STM_RFPRMN_stmDL.stm_lucia import describir as describir_lucia  # noqa: E402
    from STM_RFPRMN_stmDL.stm_corpus import sembrar_corpus  # noqa: E402
    from STM_RFPRMN_stmDL.stm_seq2seq import describir as describir_seq2seq  # noqa: E402
    from STM_RFPRMN_stmDL.stm_creacion import comando_crear_codigo  # noqa: E402
    from STM_RFPRMN_stmDL.stm_mn import (  # noqa: E402,F401
        RFPRMN, _COMANDOS_AYUDA, cerrar, ejecutar_comandos, mostrar_menu,
    )
except ImportError:
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL import RegistroRFPRMN as _Registro  # noqa: E402
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_base import (  # noqa: E402,F401
        Estilo, E, ANCHO_TERMINAL, _caja, _panel, RESPUESTAS_AFIRMATIVAS,
        LIMITE_TAMANO_ANALISIS, EXTENSIONES_POR_LENGUAJE, PATRON_MARCADOR_PENDIENTE,
        ErrorProyecto, RaizProyectoNoEncontrada, _imprimir_seguro, informar, exito,
        advertir, reportar_error, pedir_confirmacion, MODULO_DIR, TLLDCD_DIR,
        CONTRRF_DIR, SRC_DIR, encontrar_raiz, RAIZ, ORIGEN, DESTINO,
        CONFIG_IA_LOCAL, RFC_DIR, PRY_DIR, carpetas_creadas,
    )
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_gestion import (  # noqa: E402,F401
        hacer_escribible, _forzar_borrado, eliminar_ruta, borrar_contenido,
        copiar_contenido, encontrar_contenido_actual, _ultima_actualizacion_pry,
        _es_layout_actual, comando_refactorizar, _refactorizar_layout_actual,
        crear_carpeta, crear_archivo, comando_crear_carpeta, comando_crear_archivo,
        copiar_codigo, comando_copiar_codigo,
        REGISTRO_ENVIOS, DIR_REGISTRO_JSON, _contar_ficheros, _registrar_envio, comando_enviar,
        actualizar, _actualizar_layout_actual,
    )
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_analisis import (  # noqa: E402,F401
        AnalisisArchivo, analizar_archivo_local, crear_plan_refactorizacion,
        _crear_diagnostico_respaldo, _cargar_configuracion_ia_local,
        consultar_ia_local, ConsultorIA, comando_ia_local,
    )
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_modelos import (  # noqa: E402,F401
        DIR_MODELOS_LOCAL, HF_REPO_CODIGO, HF_ARCHIVO_CODIGO,
        MODELOS_CODIGO_LIGEROS, LIMITE_LINEAS_REFACTOR, LINEAS_POR_FRAGMENTO, REGISTRO_REFACTOR_MD,
        MODELOS_OR_CODIGO, ENDPOINT_OPENROUTER, _leer_openrouter_key,
        _chat_openrouter, _refactorizar_con_openrouter, _descargar_peso_hf,
        _modelos_ollama_instalados, _es_modelo_codigo, _leer_candidatos_codigo,
        _borrar_peso_local, _descargar_modelo_ollama, _modelos_usados_registro,
        _asegurar_modelo_codigo, _borrar_modelo_ollama, _liberar_ollama,
    )
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_refactor import (  # noqa: E402,F401
        _generar_fragmento, _refactorizar_con_modelo,
        _validar_refactor, _registrar_refactor_md, _pedir_extra_o_diagnostico,
        comando_ds_ialocal, _fallback_openrouter,
    )
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_flujo import (  # noqa: E402,F401
        FlujoRefactorLucIA,
        cerrar as _cerrar_flujo, mostrar_menu as _mostrar_menu,
        ejecutar_comandos as _ejecutar_comandos,
    )
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_registro import (  # noqa: E402,F401
        DIR_REGISTRO, RUTA_MD, RUTA_PESOS, publicar_registro_actualizar,
        limpiar_registro, verificar_pesos, vista_previa, similitud_coseno,
    )
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_rutas import (  # noqa: E402,F401
        comando_configurar_rutas, comando_rutas, estado_rutas, guardar_rutas,
        actualizar_rutas_finales, leer_rutas_finales,
    )
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_lucia import describir as describir_lucia  # noqa: E402
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_corpus import sembrar_corpus  # noqa: E402
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_seq2seq import describir as describir_seq2seq  # noqa: E402
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_creacion import comando_crear_codigo  # noqa: E402
    from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_mn import (  # noqa: E402,F401
        RFPRMN, _COMANDOS_AYUDA, cerrar, ejecutar_comandos, mostrar_menu,
    )

__all__ = sorted(set(_Registro.nombres()) | {"RFPRMN", "cerrar", "mostrar_menu",
    "ejecutar_comandos", "__version__", "rutas_arranque"})


def rutas_arranque() -> dict[str, str]:
    """Mapeo de rutas de arranque calculadas en tiempo de ejecución."""
    return {
        "modulo": str(_MODULO_DIR),
        "paquete": str(_PAQUETE_DIR),
        "construccion": str(_CONTRUCCION_DIR),
        "dev": str(_DEV_DIR),
        "venv": str(_VENV_DIR),
        "python": str(_PYTHON_DIR),
        "python_exe": str(_PYTHON_EJECUTABLE),
        "rfc": str(_RFC_DIR),
        "pry": str(_PRY_DIR),
        "raiz_repo": str(_RAIZ_REPO),
        "tlldcd_src": str(_TLLDCD_SRC),
        "pytest_cache": str(_PYTEST_CACHE),
    }


def listar_comandos() -> list[str]:
    """Nombres de comandos aceptados por la shell interactiva."""
    return sorted(_COMANDOS_AYUDA.keys())


def ayuda_comando(comando: str) -> str:
    """Texto de ayuda para ``comando`` (cadena vacía si no existe)."""
    return _COMANDOS_AYUDA.get(comando.strip().lower(), "")


def imprimir_ayuda() -> None:
    """Imprime la ayuda de todos los comandos en una caja."""
    filas = [(nombre, _COMANDOS_AYUDA[nombre]) for nombre in sorted(_COMANDOS_AYUDA)]
    _imprimir_seguro(_caja(f"WoldVirtualP2P3D · Ayuda  v{__version__}", filas, color="verde"))
    print()


def version_info() -> dict:
    """Versión de la fachada y nº de símbolos públicos re-exportados."""
    try:
        from STM_RFPRMN_stmDL import modulos_estado
    except ImportError:
        from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL import modulos_estado
    return {
        "version": __version__,
        "simbolos": len(__all__),
        "modulos": list(modulos_estado()),
        "arranque": rutas_arranque(),
    }


def estado_sistema() -> dict:
    """Estado de import + líneas de cada submódulo (delega en el paquete)."""
    try:
        from STM_RFPRMN_stmDL import modulos_estado
    except ImportError:
        from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL import modulos_estado
    estado = modulos_estado()
    filas = [(m, f"{v['import']} · {v['lineas']} líneas") for m, v in estado.items()]
    _imprimir_seguro(_caja("Estado de submódulos", filas, color="azul"))
    return estado


def verificar_sistema(max_lineas: int = 450) -> dict:
    """Verifica el presupuesto de líneas e informa del resultado.

    Muestra un aviso por cada módulo excedido; devuelve el dict crudo
    de STM_RFPRMN_stmDL.verificar_presupuesto().
    """
    try:
        from STM_RFPRMN_stmDL import verificar_presupuesto
    except ImportError:
        from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL import verificar_presupuesto
    resultado = verificar_presupuesto(max_lineas)
    if resultado["ok"]:
        exito(f"Presupuesto OK: ningún módulo supera {max_lineas} líneas.")
    else:
        for modulo, n in resultado["excedidos"].items():
            reportar_error(f"{modulo}: {n} líneas (tope {max_lineas}).")
    return resultado


def _ejecutar_extra(entrada: str) -> bool:
    """Ejecuta los comandos extra de la fachada (estado/presupuesto/rutas/ayuda).

    Devuelve True si ``entrada`` era un comando extra (ya ejecutado).
    """
    if entrada in ("arranque", "ruta arranque", "rutas arranque"):
        filas = [(k, v) for k, v in rutas_arranque().items()]
        _imprimir_seguro(_caja("Rutas de arranque (RFPRMN)", filas, color="verde"))
        return True
    if entrada == "estado":
        estado_sistema()
        return True
    if entrada == "presupuesto":
        verificar_sistema()
        return True
    if entrada == "rutas":
        comando_rutas()
        return True
    if entrada == "configurar rutas":
        comando_configurar_rutas()
        return True
    if entrada == "lucia":
        _imprimir_seguro(describir_lucia())
        return True
    if entrada in ("ayuda", "help", "?"):
        imprimir_ayuda()
        return True
    if entrada.startswith("copiar codigo") or entrada.startswith("copiar código"):
        partes = entrada.split(None, 2)
        if len(partes) >= 3:
            comando_copiar_codigo(partes[1], partes[2])
        else:
            comando_copiar_codigo()
        return True
    if entrada.startswith("lc entrenar") or entrada.startswith("lc_entrenar"):
        try:
            from STM_RFPRMN_stmDL.stm_cli import comando_lc_entrenar
        except ImportError:
            from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_cli import comando_lc_entrenar
        partes = entrada.split(None, 2)
        ruta = partes[2] if len(partes) > 2 else ""
        comando_lc_entrenar(ruta)
        return True
    return False


def ejecutar_interactiva() -> None:
    """Shell interactiva: despacha comandos clásicos + extras de la fachada."""
    try:
        from STM_RFPRMN_stmDL.stm_cli import comando_lc_entrenar
    except ImportError:
        from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_cli import comando_lc_entrenar
    despachador: dict[str, Callable[[], None]] = {
        "crear carpeta": comando_crear_carpeta,
        "crear archivo": comando_crear_archivo,
        "copiar codigo": comando_copiar_codigo,
        "copiar código": comando_copiar_codigo,
        "refactorizar": comando_refactorizar,
        "actualizar": actualizar,
        "enviar": comando_enviar,
        "ia local": comando_ia_local,
        "ds ialocal": comando_ds_ialocal,
        "lc entrenar": lambda: comando_lc_entrenar(""),
    }
    mostrar_menu()
    try:
        while True:
            entrada = input("> ").strip().lower()
            if entrada == "cerrar":
                cerrar()
                break
            if _ejecutar_extra(entrada):
                continue
            accion = despachador.get(entrada)
            if accion is None:
                reportar_error(f"Comando no reconocido: '{entrada}' (prueba 'ayuda')")
                continue
            accion()
    except (KeyboardInterrupt, EOFError):
        _borrar_peso_local()
        informar("Sesión interrumpida; se limpiaron los modelos descargados.")


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI no interactivo (delega en EjecutorCLI)."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--arranque" in args:
        filas = [(k, v) for k, v in rutas_arranque().items()]
        _imprimir_seguro(_caja("Rutas de arranque (RFPRMN)", filas, color="verde"))
        return 0
    try:
        from STM_RFPRMN_stmDL.stm_cli import EjecutorCLI
    except ImportError:
        from VersionDesesion.CONTRRF.RFC.CONTRUCCION.STM_RFC.STM_RFPRMN.STM_RFPRMN_stmDL.stm_cli import EjecutorCLI
    return EjecutorCLI().ejecutar(args)


if __name__ == "__main__":
    raise SystemExit(main())
