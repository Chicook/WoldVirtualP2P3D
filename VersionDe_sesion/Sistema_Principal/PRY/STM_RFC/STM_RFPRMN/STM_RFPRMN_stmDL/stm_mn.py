"""Fachada de RFPRMN: clase principal, ayuda y ciclo de vida de la shell.

Este módulo vive dentro de ``STM_RFPRMN_stmDL`` y usa **imports absolutos** al
paquete, igual que ``RFPRMN.py``. Antes de importar nada añade al ``sys.path``
el directorio que contiene ``STM_RFPRMN_stmDL``, de modo que funciona tanto si
se importa como paquete::

    from STM_RFPRMN_stmDL.stm_mn import RFPRMN, cerrar, mostrar_menu

como si se ejecuta directamente (F5 / ``python stm_mn.py``), donde ``__package__``
es ``None`` y los imports relativos fallarían con ``ImportError``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

#: Directorio que contiene el paquete (``.../STM_RFPRMN``). Se añade al path
#: para que los imports absolutos resuelvan también en ejecución directa.
_RAIZ_PAQUETE = Path(__file__).resolve().parent.parent
if str(_RAIZ_PAQUETE) not in sys.path:
    sys.path.insert(0, str(_RAIZ_PAQUETE))

from STM_RFPRMN_stmDL import RegistroRFPRMN as _Registro  # noqa: E402
from STM_RFPRMN_stmDL.stm_analisis import (  # noqa: E402
    AnalisisArchivo, ConsultorIA, analizar_archivo_local, comando_ia_local,
    consultar_ia_local, crear_plan_refactorizacion,
)
from STM_RFPRMN_stmDL.stm_base import (  # noqa: E402
    CONFIG_IA_LOCAL, DESTINO, ORIGEN, PRY_DIR, RAIZ, RFC_DIR, __version__,
)
from STM_RFPRMN_stmDL.stm_flujo import (  # noqa: E402
    FlujoRefactorLucIA,
    cerrar as _cerrar_flujo,
    ejecutar_comandos as _ejecutar_comandos,
    mostrar_menu as _mostrar_menu,
)
from STM_RFPRMN_stmDL.stm_gestion import (  # noqa: E402
    actualizar, borrar_contenido, comando_copiar_codigo, comando_crear_archivo,
    comando_crear_carpeta, comando_enviar, comando_refactorizar, copiar_codigo,
    copiar_contenido, crear_archivo, crear_carpeta, eliminar_ruta,
    encontrar_contenido_actual, hacer_escribible,
)
from STM_RFPRMN_stmDL.stm_modelos import (  # noqa: E402
    _asegurar_modelo_codigo, _borrar_peso_local, _liberar_ollama,
    _modelos_ollama_instalados,
)
from STM_RFPRMN_stmDL.stm_refactor import (  # noqa: E402
    _validar_refactor, comando_ds_ialocal,
)
from STM_RFPRMN_stmDL.stm_registro import (  # noqa: E402
    limpiar_registro, publicar_registro_actualizar, verificar_pesos, vista_previa,
)

__all__ = [
    "RFPRMN", "cerrar", "mostrar_menu", "ejecutar_comandos",
    "crear_archivo", "crear_carpeta", "copiar_codigo", "comando_copiar_codigo",
]


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

    def crear_archivo(self, ruta: str, nombre: str, lenguaje: str = "") -> str:
        """Crea un archivo vacio en ``ruta/nombre`` sin interaccion (API programatica).

        Equivalente no interactivo de ``crear_archivo_cmd``.  Es el metodo que
        invocan las neuronas en tiempo de ejecucion (NeuronaCodigo, etc.).

        Parameters
        ----------
        ruta : str
            Directorio donde se creara el archivo.
        nombre : str
            Nombre del archivo con o sin extension.
        lenguaje : str, opcional
            Lenguaje para resolver la extension (ej: ``'python'``, ``'csharp'``).

        Returns
        -------
        str
            Ruta absoluta del archivo creado.
        """
        return crear_archivo(ruta, nombre, lenguaje)

    def copiar_codigo(self, origen: str | Path, destino: str | Path) -> dict:
        """Copia todas las líneas de un archivo de código fuente al archivo destino."""
        return copiar_codigo(origen, destino)

    def copiar_codigo_cmd(self, origen: str = "", destino: str = "") -> bool:
        """Comando interactivo 'copiar codigo'."""
        return comando_copiar_codigo(origen, destino)

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

    def lc_entrenar(self, ruta_o_texto: str = "") -> dict:
        """Comando 'lc entrenar': envía archivo o texto a la red neuronal en vectores."""
        from STM_RFPRMN_stmDL.stm_cli import comando_lc_entrenar
        return comando_lc_entrenar(ruta_o_texto)


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
    "copiar codigo": "Copia las líneas de un archivo fuente a un archivo destino vacío.",
    "refactorizar": "Copia el contenido actual de PRY hacia RFC.",
    "actualizar": "Reemplaza PRY con la versión refactorizada de RFC.",
    "enviar": "Envía una carpeta con su contenido a CONTRRF/RFC.",
    "ia local": "Analiza un archivo con LucIA y crea un plan de refactorización.",
    "lc entrenar": "Envía archivo de código o .md a la red neuronal en vectores.",
    "ds ialocal": "Plan de LucIA + refactor local (registro .md; --openrouter lo activa).",
    "crear codigo": "Crea un archivo nuevo a partir de un diagnóstico de LucIA.",
    "crear logica": "Escribe una función a partir de lo que le pidas en lenguaje natural.",
    "comentar archivo": "Documenta con LucIA las funciones de un archivo existente.",
    "informacion codigo": "Informe .md con la deuda técnica y la hoja de ruta.",
    "test": "Prueba un archivo y diagnostica su deuda técnica.",
    "cerrar": "Cierra el sistema limpiando modelos descargados.",
    "estado": "Muestra el estado de los submódulos y su nº de líneas.",
    "presupuesto": "Verifica que ningún módulo supere el tope de 450 líneas.",
    "rutas": "Muestra las rutas activas de RFC/PRY y de qué fuente salen.",
    "configurar rutas": "Elige los directorios de RFC y PRY (se guardan en .config).",
    "lucia": "Estado de la red neuronal de LucIA (muestras aprendidas y pesos).",
    "seq2seq": "Estado del subsistema seq2seq (pares memorizados).",
    "ayuda": "Muestra esta ayuda.",
}


if __name__ == "__main__":
    # Ejecución directa (F5 / python stm_mn.py): confirma que el módulo carga.
    print(f"stm_mn OK · RFPRMN v{__version__} · {len(_COMANDOS_AYUDA)} comandos")
    print(f"raíz del proyecto: {RAIZ}")
    print("importa la fachada con: from STM_RFPRMN_stmDL.stm_mn import RFPRMN")
