"""CLI del ciclo de vida del código de WoldVirtualP2P3D (fachada).

La lógica vive en STM_RFPRMN_stmDL/ (6 módulos de <=450 líneas).
Este archivo mantiene compatibilidad total: todos los símbolos públicos
del RFPRMN.py original se re-exportan, y la clase RFPRMN expone cada
comando como método. Funcionalidad intacta.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

__version__ = "2.0.0"

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
    crear_carpeta, comando_crear_carpeta, comando_crear_archivo,
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

__all__ = sorted(set(_Registro.nombres()) | {"RFPRMN", "cerrar", "mostrar_menu",
    "ejecutar_comandos", "__version__"})

class RFPRMN:
    """Fachada del sistema: cada método delega al submódulo que lo implementa.

    Uso:
        RFPRMN().ejecutar()          # shell interactiva
        RFPRMN().enviar()            # comando 'enviar'
        RFPRMN(raiz=...).actualizar()  # con raíz explícita
    """

    version = __version__

    def __init__(self, raiz: str | Path | None = None) -> None:
        """Crea la fachada; ``raiz`` permite fijar la raíz del proyecto."""
        self.raiz = Path(raiz).resolve() if raiz is not None else RAIZ
        self.origen = ORIGEN
        self.destino = DESTINO
        self.rfc_dir = RFC_DIR
        self.pry_dir = PRY_DIR
        self.config_ia = CONFIG_IA_LOCAL

    # -- gestión PRY <-> RFC ---------------------------------------------
    def refactorizar(self) -> None:
        """Copia el contenido actual de PRY hacia RFC (previa confirmación)."""
        return comando_refactorizar()

    def actualizar(self) -> None:
        """Promueve el contenido de RFC a PRY como nueva versión histórica."""
        return actualizar()

    def enviar(self) -> None:
        """Envía una carpeta completa a su destino con verificación."""
        return comando_enviar()

    def crear_carpeta_cmd(self) -> None:
        """Comando interactivo 'crear carpeta'."""
        return comando_crear_carpeta()

    def crear_archivo_cmd(self) -> None:
        """Comando interactivo 'crear archivo'."""
        return comando_crear_archivo()

    def crear_carpeta_en(self, ruta: str, nombre: str) -> str:
        """Crea ``nombre`` dentro de ``ruta`` y devuelve la ruta final."""
        return crear_carpeta(ruta, nombre)

    # -- sistema de archivos ----------------------------------------------
    def hacer_escribible(self, ruta: str) -> None:
        """Otorga permiso de escritura a ``ruta`` de forma recursiva."""
        return hacer_escribible(ruta)

    def eliminar_ruta(self, ruta: str) -> None:
        """Elimina un archivo o árbol de directorios completo."""
        return eliminar_ruta(ruta)

    def borrar_contenido(self, carpeta: str) -> None:
        """Vacía ``carpeta`` reintentando tras corregir permisos."""
        return borrar_contenido(carpeta)

    def copiar_contenido(self, origen: str, destino: str) -> None:
        """Copia recursivamente ``origen`` dentro de ``destino``."""
        return copiar_contenido(origen, destino)

    def encontrar_contenido_actual(self, carpeta: str) -> str:
        """Desciende por actualizacion_* anidadas hasta el contenido real."""
        return encontrar_contenido_actual(carpeta)

    # -- análisis y LucIA ---------------------------------------------------
    def analizar_archivo(self, ruta: Path) -> AnalisisArchivo:
        """Analiza un archivo y devuelve sus métricas estáticas."""
        return analizar_archivo_local(ruta)

    def crear_plan(self, analisis: AnalisisArchivo) -> list[str]:
        """Deriva un plan de pasos concretos a partir del análisis."""
        return crear_plan_refactorizacion(analisis)

    def consultar_ia(self, contenido: str, analisis: AnalisisArchivo) -> str:
        """Pide un diagnóstico a LucIA (modelo local vía Ollama)."""
        return consultar_ia_local(contenido, analisis)

    def ia_local(self, consultor: Optional[ConsultorIA] = None) -> bool:
        """Comando 'ia local': analiza y muestra diagnóstico + plan."""
        return comando_ia_local(consultor)

    def ds_ialocal(self, consultor: Optional[ConsultorIA] = None) -> bool:
        """Comando 'ds ialocal': pipeline completo de refactor con IA local."""
        return comando_ds_ialocal(consultor)

    def flujo_para(self, ruta: Path, contenido: str,
                   consultor: Optional[ConsultorIA] = None) -> FlujoRefactorLucIA:
        """Construye el flujo de refactor para un archivo dado."""
        return FlujoRefactorLucIA(ruta, contenido, consultor)

    # -- modelos e infraestructura IA ---------------------------------------
    def asegurar_modelo_codigo(self, excluir: set[str] | None = None) -> str:
        """Descarga/elige un modelo de código no usado antes."""
        return _asegurar_modelo_codigo(excluir)

    def borrar_peso_local(self) -> None:
        """Borra lo descargado en IAlocalDESCARGADA."""
        return _borrar_peso_local()

    def liberar_ollama(self, excepto: str = "") -> None:
        """Descarga de CPU/RAM los modelos Ollama salvo ``excepto``."""
        return _liberar_ollama(excepto)

    def modelos_ollama(self) -> set[str]:
        """Modelos ya descargados en Ollama."""
        return _modelos_ollama_instalados()

    def validar_refactor(self, original: str, nuevo: str, ruta: Path) -> str:
        """Valida un refactor (sintaxis, tope 400/450, fidelidad mínima)."""
        return _validar_refactor(original, nuevo, ruta)

    def publicar_registro(self, info: dict) -> dict:
        """Publica el registro de actualizar: md -> pesos -> IPFS -> limpieza."""
        return publicar_registro_actualizar(info)

    def limpiar_registro(self) -> dict:
        """Borra json, md y pesos del registro (directorio limpio)."""
        return limpiar_registro()

    def vista_previa_registro(self, info: dict) -> str:
        """Muestra cómo quedaría registro.md sin escribir ni publicar."""
        return vista_previa(info)

    def verificar_pesos(self) -> bool:
        """Verifica la integridad de registro_pesos.json si existe."""
        return verificar_pesos()

    # -- UI y ciclo de vida ---------------------------------------------------
    def mostrar_menu(self) -> None:
        """Imprime la lista de comandos disponibles."""
        return _mostrar_menu()

    def cerrar(self) -> None:
        """Finaliza la sesión y limpia restos de modelos."""
        return _cerrar_flujo()

    def ejecutar(self) -> None:
        """Bucle principal de la shell interactiva."""
        return _ejecutar_comandos()

    def registro(self) -> _Registro:
        """Acceso al registro perezoso de símbolos del paquete."""
        return _Registro

    def estado_modulos(self) -> dict:
        """Estado de import + líneas de cada submódulo."""
        from STM_RFPRMN_stmDL import modulos_estado
        return modulos_estado()

    def verificar_presupuesto(self, max_lineas: int = 450) -> dict:
        """Verifica que ningún módulo supere el tope de líneas."""
        from STM_RFPRMN_stmDL import verificar_presupuesto
        return verificar_presupuesto(max_lineas)

def cerrar() -> None:
    """Finaliza la sesión interactiva y limpia restos de modelos."""
    return _cerrar_flujo()

def mostrar_menu() -> None:
    """Imprime la lista de comandos disponibles."""
    return _mostrar_menu()

def ejecutar_comandos() -> None:
    """Bucle principal de la shell interactiva."""
    return _ejecutar_comandos()

_COMANDOS_AYUDA: dict[str, str] = {
    "crear carpeta": "Crea una carpeta nueva (pide ruta y nombre).",
    "crear archivo": "Crea un archivo nuevo (pide ruta, nombre y lenguaje).",
    "refactorizar": "Copia el contenido actual de PRY hacia RFC.",
    "actualizar": "Reemplaza PRY con la versión refactorizada de RFC.",
    "enviar": "Envía una carpeta con su contenido a CONTRRF/RFC.",
    "ia local": "Analiza un archivo con LucIA y crea un plan de refactorización.",
    "ds ialocal": "Plan de LucIA + refactor con modelo local y registro .md.",
    "cerrar": "Cierra el sistema limpiando modelos descargados.",
    "estado": "Muestra el estado de los submódulos y su nº de líneas.",
    "presupuesto": "Verifica que ningún módulo supere el tope de 450 líneas.",
    "ayuda": "Muestra esta ayuda.",
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
    return {"version": __version__, "simbolos": len(__all__),
            "modulos": ["stm_base", "stm_gestion", "stm_analisis",
                        "stm_modelos", "stm_refactor", "stm_flujo",
                        "stm_registro"]}

def estado_sistema() -> dict:
    """Estado de import + líneas de cada submódulo del paquete.

    Delega en STM_RFPRMN_stmDL.modulos_estado() y lo muestra en caja.
    """
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
    """Ejecuta los comandos extra de la fachada (estado/presupuesto/ayuda).

    Devuelve True si ``entrada`` era un comando extra (ya ejecutado).
    """
    if entrada == "estado":
        estado_sistema()
        return True
    if entrada == "presupuesto":
        verificar_sistema()
        return True
    if entrada in ("ayuda", "help", "?"):
        imprimir_ayuda()
        return True
    return False

def ejecutar_interactiva() -> None:
    """Shell interactiva: despacha comandos clásicos + extras de la fachada."""
    despachador: dict[str, Callable[[], None]] = {
        "crear carpeta": comando_crear_carpeta,
        "crear archivo": comando_crear_archivo,
        "refactorizar": comando_refactorizar,
        "actualizar": actualizar,
        "enviar": comando_enviar,
        "ia local": comando_ia_local,
        "ds ialocal": comando_ds_ialocal,
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
    """Punto de entrada CLI no interactivo.

    Sin argumentos abre la shell interactiva clásica (compatibilidad).
    Acepta: --ayuda, --version, --estado, --presupuesto, --comando NOMBRE.
    Devuelve código de salida (0 = OK).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        ejecutar_comandos()
        return 0
    if args[0] in ("--ayuda", "-h", "ayuda"):
        imprimir_ayuda()
        return 0
    if args[0] in ("--version", "-v"):
        info = version_info()
        print(f"RFPRMN v{info['version']} · {info['simbolos']} símbolos · "
              f"{len(info['modulos'])} submódulos")
        return 0
    if args[0] == "--estado":
        estado_sistema()
        return 0
    if args[0] == "--presupuesto":
        return 0 if verificar_sistema()["ok"] else 1
    if args[0] == "--comando" and len(args) > 1:
        nombre = " ".join(args[1:]).strip().lower()
        fachada = RFPRMN()
        tabla: dict[str, Callable[[], None]] = {
            "refactorizar": fachada.refactorizar,
            "actualizar": fachada.actualizar,
            "enviar": fachada.enviar,
            "crear carpeta": fachada.crear_carpeta_cmd,
            "crear archivo": fachada.crear_archivo_cmd,
            "ia local": fachada.ia_local,
            "ds ialocal": fachada.ds_ialocal,
        }
        accion = tabla.get(nombre)
        if accion is None:
            reportar_error(f"Comando no reconocido: '{nombre}' (prueba --ayuda)")
            return 2
        accion()
        return 0
    reportar_error(f"Argumento no reconocido: {args[0]} (prueba --ayuda)")
    return 2

if __name__ == "__main__":
    raise SystemExit(main())