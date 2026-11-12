"""
stm_shell.py - Shell Interactiva de RFPRMN
===========================================
Encapsula toda la lógica del menú, el bucle de comandos y el cierre de sesión
en la clase ``ShellInteractiva``, separándola del pipeline de refactorización
(``FlujoRefactorLucIA``) que vive en ``sbstm_mdl/sbstm_flj.py``.

Exporta también las funciones de compatibilidad ``mostrar_menu`` y
``ejecutar_comandos`` para que ``stm_flujo.py`` pueda delegarlas sin cambios
en la interfaz pública.
"""
from __future__ import annotations

from typing import Callable, Dict

from .stm_base import (
    ErrorProyecto,
    __version__,
    _caja,
    _imprimir_seguro,
    informar,
    reportar_error,
)
from .stm_modelos import _borrar_peso_local


class ShellInteractiva:
    """Menú, bucle de comandos y cierre de la sesión de RFPRMN.

    Atributos
    ---------
    version : str
        Versión del sistema (tomada de ``stm_base.__version__``).

    Métodos principales
    -------------------
    mostrar_menu()       Dibuja la caja con todos los comandos disponibles.
    ejecutar_comandos()  Bucle interactivo hasta que el usuario escribe "cerrar".
    cerrar()             Finaliza la sesión, reparte y limpia modelos.
    """

    # ── Tabla de entradas del menú (nombre, descripción) ──────────────────────
    _ENTRADAS_MENU: tuple = (
        ("crear carpeta",      "Crear una carpeta nueva"),
        ("crear archivo",      "Crear un archivo nuevo"),
        ("copiar codigo",      "Copiar líneas de un archivo fuente a otro vacío"),
        ("refactorizar",       "Copiar el contenido actual de PRY a RFC"),
        ("actualizar",         "Reemplazar PRY con la versión de RFC"),
        ("enviar",             "Enviar una carpeta con su contenido a CONTRRF/RFC"),
        ("ia local",           "Analizar un archivo con LucIA y crear un plan"),
        ("ds ialocal",         "Plan de LucIA + refactor con modelo local y registro .md"),
        ("crear codigo",       "Crear un archivo nuevo a partir de un diagnóstico de LucIA"),
        ("crear logica",       "Escribir una función a partir de lo que le pidas"),
        ("comentar archivo",   "Documentar las funciones de un archivo con LucIA"),
        ("informacion codigo", "Informe .md con deuda tecnica y hoja de ruta"),
        ("test",               "Probar un archivo y diagnosticar su deuda técnica"),
        ("rutas",              "Ver las rutas activas de RFC/PRY y su origen"),
        ("configurar rutas",   "Elegir los directorios de RFC y PRY"),
        ("lc entrenar",        "Entrenar red neuronal con código o .md"),
        ("lc adjuntar",        "Seleccionar archivo/carpeta y entrenar red neuronal"),
        ("lc evolucion",       "Ciclo 4 fases: propiocepción y autodiagnóstico"),
        ("cerrar",             "Cerrar el sistema"),
    )

    def __init__(self) -> None:
        self.version: str = __version__

    # ── Helpers de despacho LC ────────────────────────────────────────────────

    @staticmethod
    def _lc_entrenar(ruta: str = "") -> None:
        from .stm_cli import comando_lc_entrenar
        comando_lc_entrenar(ruta)

    @staticmethod
    def _lc_adjuntar() -> None:
        from .stm_adjuntar import comando_lc_entrenar_adjuntar
        comando_lc_entrenar_adjuntar()

    @staticmethod
    def _lc_evolucion() -> None:
        try:
            from SBSTM.subsistema_evolutivo import get_subsistema_evolutivo
            sub_evo = get_subsistema_evolutivo()
            res = sub_evo.ejecutar_ciclo_completo(auto_reparar=False)
            print()
            print(sub_evo.generar_reporte_texto(res))
            print()
        except Exception as err:
            reportar_error(f"Error en ciclo evolutivo: {err}")

    # ── Interfaz pública ──────────────────────────────────────────────────────

    def mostrar_menu(self) -> None:
        """Dibuja el panel de bienvenida con todos los comandos disponibles."""
        filas = list(self._ENTRADAS_MENU)
        titulo = f"WoldVirtualP2P3D · Gestor de Proyecto  v{self.version}"
        _imprimir_seguro(_caja(titulo, filas))
        print()

    def cerrar(self) -> None:
        """Finaliza la sesión: reparte lo que sobra y limpia modelos descargados."""
        from .stm_particion import repartir_carpeta
        repartir_carpeta()
        _borrar_peso_local()
        informar("Cerrando el sistema...")

    def _construir_despachador(self) -> Dict[str, Callable[[], None]]:
        """Crea el diccionario nombre → función de cada comando del menú."""
        from .stm_gestion import (
            comando_crear_carpeta, comando_crear_archivo,
            comando_refactorizar, actualizar, comando_enviar,
        )
        from .stm_analisis import comando_ia_local
        from .stm_refactor import comando_ds_ialocal
        from .stm_creacion import comando_crear_codigo, comando_copiar_codigo
        from .stm_logica import comando_crear_logica
        from .stm_comentarios import comando_comentar_archivo
        from .stm_informe import comando_informacion_codigo
        from .test import comando_test
        from .stm_rutas import comando_rutas, comando_configurar_rutas

        return {
            "crear carpeta":      comando_crear_carpeta,
            "crear archivo":      comando_crear_archivo,
            "copiar codigo":      comando_copiar_codigo,
            "copiar código":      comando_copiar_codigo,
            "refactorizar":       comando_refactorizar,
            "actualizar":         actualizar,
            "enviar":             comando_enviar,
            "ia local":           comando_ia_local,
            "ds ialocal":         comando_ds_ialocal,
            "crear codigo":       comando_crear_codigo,
            "crear logica":       comando_crear_logica,
            "comentar archivo":   comando_comentar_archivo,
            "informacion codigo": comando_informacion_codigo,
            "test":               comando_test,
            "rutas":              comando_rutas,
            "configurar rutas":   comando_configurar_rutas,
            "lc entrenar":        lambda: self._lc_entrenar(""),
            "lc adjuntar":        self._lc_adjuntar,
            "lc evolucion":       self._lc_evolucion,
        }

    def ejecutar_comandos(self) -> None:
        """Bucle principal de la shell interactiva hasta que el usuario cierra."""
        despachador = self._construir_despachador()
        self.mostrar_menu()
        try:
            while True:
                entrada = input("> ").strip().lower()
                if entrada == "cerrar":
                    self.cerrar()
                    break
                # lc entrenar acepta ruta inline: "lc entrenar ruta/al/archivo.py"
                if entrada.startswith(("lc entrenar", "lc_entrenar")):
                    partes = entrada.split(None, 2)
                    self._lc_entrenar(partes[2] if len(partes) > 2 else "")
                    continue
                accion = despachador.get(entrada)
                if accion is None:
                    reportar_error(f"Comando no reconocido: '{entrada}'")
                    continue
                try:
                    accion()
                except (ErrorProyecto, OSError) as error:
                    reportar_error(f"El comando falló: {error}")
        except (KeyboardInterrupt, EOFError):
            _borrar_peso_local()
            informar("Sesión interrumpida; se limpiaron los modelos descargados.")


# ── Funciones de compatibilidad (API pública de stm_flujo) ───────────────────

def mostrar_menu() -> None:
    """Delegador de compatibilidad → ``ShellInteractiva.mostrar_menu``."""
    ShellInteractiva().mostrar_menu()


def ejecutar_comandos() -> None:
    """Delegador de compatibilidad → ``ShellInteractiva.ejecutar_comandos``."""
    ShellInteractiva().ejecutar_comandos()


def cerrar() -> None:
    """Delegador de compatibilidad → ``ShellInteractiva.cerrar``."""
    ShellInteractiva().cerrar()


if __name__ == "__main__":
    ejecutar_comandos()
