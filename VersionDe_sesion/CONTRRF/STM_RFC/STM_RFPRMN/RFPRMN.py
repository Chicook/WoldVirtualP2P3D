"""CLI del ciclo de vida del código de WoldVirtualP2P3D (fachada).

La lógica vive en ``STM_RFPRMN_stmDL/``; aquí se re-exporta y se expone la CLI.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional

__version__ = "2.24.0"

_MODULO_DIR = Path(__file__).resolve().parent
_PAQUETE_DIR = _MODULO_DIR / "STM_RFPRMN_stmDL"
if str(_MODULO_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULO_DIR))

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

__all__ = sorted(set(_Registro.nombres()) | {"RFPRMN", "cerrar", "mostrar_menu",
    "ejecutar_comandos", "__version__"})

from STM_RFPRMN_stmDL.stm_mn import (  # noqa: E402,F401
    RFPRMN, _COMANDOS_AYUDA, cerrar, ejecutar_comandos, mostrar_menu,
)

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
    from STM_RFPRMN_stmDL import modulos_estado
    return {"version": __version__, "simbolos": len(__all__), "modulos": list(modulos_estado())}


def estado_sistema() -> dict:
    """Estado de import + líneas de cada submódulo (delega en el paquete)."""
    from STM_RFPRMN_stmDL import modulos_estado
    estado = modulos_estado()
    filas = [(m, f"{v['import']} · {v['lineas']} líneas") for m, v in estado.items()]
    _imprimir_seguro(_caja("Estado de submódulos", filas, color="azul"))
    return estado

def verificar_sistema(max_lineas: int = 450) -> dict:
    """Verifica el presupuesto de líneas e informa del resultado.

    Muestra un aviso por cada módulo excedido; devuelve el dict crudo
    de STM_RFPRMN_stmDL.verificar_presupuesto().
    """
    from STM_RFPRMN_stmDL import verificar_presupuesto
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
        from STM_RFPRMN_stmDL.stm_cli import comando_lc_entrenar
        partes = entrada.split(None, 2)
        ruta = partes[2] if len(partes) > 2 else ""
        comando_lc_entrenar(ruta)
        return True
    return False

def ejecutar_interactiva() -> None:
    """Shell interactiva: despacha comandos clásicos + extras de la fachada."""
    from STM_RFPRMN_stmDL.stm_cli import comando_lc_entrenar
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
    from STM_RFPRMN_stmDL.stm_cli import EjecutorCLI
    return EjecutorCLI().ejecutar(argv)

if __name__ == "__main__":
    raise SystemExit(main())