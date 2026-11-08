"""Máquina de estados del comando ``ds ialocal`` (issue #80).

Un único ``ejecutar()`` orquesta las fases [1/5]…[5/5] con estas garantías:

- **Cortes válidos**: los fragmentos de un ``.py`` se calculan sobre fronteras
  de sentencias de nivel superior (AST), así que ninguno rompe un ``def``,
  un ``class`` ni un bloque ``try/except``.
- **Solape real**: cada fragmento recibe como contexto la cola del fragmento
  *original* anterior y el ensamblado elimina la repetición.
- **Sin truncamiento silencioso**: si el resultado excede el tope se rechaza
  con ``ErrorProyecto`` y el original queda intacto.
- **Rotación y validación**: los modelos fallidos se excluyen (sin borrarlos
  salvo ``--consumir-modelos``) y LucIA valida el candidato con su red.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from .stm_base import (
    E, informar, exito, advertir, reportar_error, pedir_confirmacion,
    ErrorProyecto, __version__, _caja, _panel, _imprimir_seguro,
)
from .stm_fs import escribir_texto_atomico
from .stm_fragmentos import calcular_rangos, quitar_solape
from .stm_lucia import (
    evaluar_y_aprender, guardar_expediente, preparar as preparar_expediente,
)
from .stm_gestion import (
    comando_crear_carpeta, comando_crear_archivo, comando_refactorizar,
    actualizar, comando_enviar,
)
from .stm_analisis import (
    AnalisisArchivo, analizar_archivo_local, crear_plan_refactorizacion,
    consultar_ia_local, ConsultorIA, comando_ia_local,
    _cargar_configuracion_ia_local,
)
from .stm_modelos import (
    LIMITE_LINEAS_REFACTOR, LINEAS_POR_FRAGMENTO, _asegurar_modelo_codigo,
    _liberar_ollama, _borrar_modelo_ollama, _borrar_peso_local,
)
from .stm_refactor import (
    comando_ds_ialocal, _generar_fragmento, _validar_refactor,
    _registrar_refactor_md, _pedir_extra_o_diagnostico, _fallback_openrouter,
)
from .stm_creacion import comando_crear_codigo
from .stm_logica import comando_crear_logica
from .stm_comentarios import comando_comentar_archivo
from .stm_descartes import retirar_modelo
from .test import comando_test
from .stm_rutas import comando_configurar_rutas, comando_rutas
from .stm_calidad import solo_documenta, validar_fragmento
#: Valores de ``RFPRMN_CONSUMIR_MODELOS`` que activan el borrado de modelos.
_AFIRMATIVOS = frozenset({"1", "si", "sí", "s", "yes", "y", "true"})


def consumir_modelos_por_entorno() -> bool:
    """True si ``RFPRMN_CONSUMIR_MODELOS`` pide borrar los modelos usados."""
    return os.environ.get("RFPRMN_CONSUMIR_MODELOS", "").strip().lower() in _AFIRMATIVOS


class FlujoRefactorLucIA:
    """Pipeline "ds ialocal": plan, IA local por fragmentos, validación y registro.

    Ante fallo de validación se borra el modelo con ``ollama rm`` y se rota a
    otra IA; agotadas ``MAX_IAS`` se cae al respaldo de OpenRouter.
    """

    MAX_IAS = 3
    MAX_REINTENTOS_FRAG = 2
    SOLAPE_LINEAS = 10

    def __init__(self, ruta: Path, contenido: str,
                 consultor: Optional[ConsultorIA] = None,
                 consumir_modelos: Optional[bool] = None) -> None:
        self.ruta = Path(ruta)
        self.contenido = contenido
        try:
            self.analisis: AnalisisArchivo = analizar_archivo_local(self.ruta)
        except OSError as error:
            raise ErrorProyecto(f"No se pudo analizar {self.ruta}: {error}")
        self.generador: ConsultorIA = consultor or consultar_ia_local
        #: Por defecto los modelos se CONSERVAN (R3); se borran con --consumir-modelos.
        self.consumir_modelos = (
            consumir_modelos_por_entorno() if consumir_modelos is None
            else bool(consumir_modelos))
        self.modelo = ""
        self.endpoint = ""
        self.fallidas: set[str] = set()
        self.errores: list[str] = []      # líneas "### Errores" para el .md
        self.rotaciones: list[str] = []   # líneas "### Rotación" para el .md
        self.fragmentos: list[dict] = []
        self.nota_lucia = ""
        #: Última descripción funcional que LucIA hizo del archivo.
        self.descripcion_lucia = ""
        #: Expediente (código + descripción + README + deuda) del archivo.
        self.expediente = None
        #: Si quedan fragmentos irreparables, pedir confirmación antes de escribir.
        self.confirmar_parcial = True
        self.fallo_filtro = False  # True si el modelo actual falló los filtros

    # -- fase PLAN ---------------------------------------------------------
    def _presentar_plan(self, titulo: str, pregunta: str) -> bool:
        """Muestra diagnóstico y plan de LucIA y pide confirmación."""
        plan_lucia = self.generador(self.contenido, self.analisis)
        self.descripcion_lucia = str(plan_lucia).strip()
        _imprimir_seguro(_panel(titulo, str(plan_lucia).strip()))
        plan = crear_plan_refactorizacion(self.analisis)
        print(f"\n{E.negrita}Plan de refactorización{E.reset}")
        for indice, paso in enumerate(plan, start=1):
            print(f"  {E.cian}{indice}.{E.reset} {paso}")
        if not pedir_confirmacion(pregunta):
            _pedir_extra_o_diagnostico(self.contenido, self.analisis)
            return False
        return True

    def plan_y_confirmacion(self) -> bool:
        """Muestra diagnóstico+plan de LucIA y pide s/n (con opciones 1/2)."""
        return self._presentar_plan("LucIA · Plan de refactorización",
                                    "¿Se aplica el plan?")

    def nuevo_diagnostico(self) -> bool:
        """Tras rotar de IA: nuevo diagnóstico+plan de LucIA y confirmación."""
        _imprimir_seguro("[VIGILANTE] Reiniciando flujo con otra IA local...")
        return self._presentar_plan("LucIA · Nuevo diagnóstico",
                                    "¿Se aplica el plan con la nueva IA?")

    # -- fase IA -----------------------------------------------------------
    def asegurar_ia(self) -> None:
        """Descarga/elige IA local no usada y libera la CPU para ella."""
        try:
            self.endpoint, _ = _cargar_configuracion_ia_local()
        except (OSError, ValueError) as error:
            raise ErrorProyecto(
                f"Configuración de IA local no disponible ({error}). "
                "Revisa STM_JSON/IAlocal.json y que Ollama escuche en el endpoint.")
        self.modelo = _asegurar_modelo_codigo(excluir=self.fallidas)
        if not self.modelo:
            raise ErrorProyecto("No hay ningún modelo de código disponible.")
        self.fallo_filtro = False
        _liberar_ollama(excepto=self.modelo)
        _imprimir_seguro(f"[1/5] OK, modelo listo: {self.modelo}")

    def rotar_ia(self, motivo: str) -> None:
        """Aparta la IA actual; la **borra** si falló los filtros o se pidió.

        Un modelo que devuelve código inválido, vacío o solo documentación no
        sirve: se elimina con ``ollama rm`` y queda apuntado para que el
        siguiente flujo descargue otro distinto. Un timeout solo la excluye.
        """
        self.fallidas.add(self.modelo)
        if not (self.fallo_filtro or self.consumir_modelos):
            advertir(f"{self.modelo} queda excluido de esta sesión y no se borra "
                     "(solo se elimina si no pasa los filtros o con --consumir-modelos).")
            self.rotaciones.append(f"- {self.modelo} excluida sin borrar (motivo: {motivo})")
            return
        razon = "no pasó los filtros" if self.fallo_filtro else "consumo pedido"
        _imprimir_seguro(f"[VIGILANTE] Borrando {self.modelo} ({razon}).")
        borrado = retirar_modelo(self.endpoint, self.modelo, motivo, self.fallo_filtro)
        self.rotaciones.append(f"- {self.modelo} " + (
            f"borrada ({razon})" if borrado else f"NO se pudo borrar ({razon})."))
        if not borrado:
            advertir(f"No se pudo borrar {self.modelo}; queda excluido igualmente.")

    # -- fase FRAGMENTOS ---------------------------------------------------
    def generar_fragmentos(self) -> None:
        """Corta en fronteras seguras, sin romper estructuras del lenguaje."""
        lineas = self.contenido.splitlines()
        rangos = calcular_rangos(self.contenido, self.ruta.suffix.lower(),
                                 LINEAS_POR_FRAGMENTO)
        if not rangos:
            raise ErrorProyecto(f"{self.ruta.name} está vacío: no hay nada que refactorizar.")
        self.fragmentos = []
        for numero, (inicio, fin) in enumerate(rangos, start=1):
            self.fragmentos.append({
                "num": numero, "inicio": inicio, "fin": fin,
                "original": "\n".join(lineas[inicio - 1:fin]),
                "salida": "", "irreparable": False, "intentos": 0,
            })
        _imprimir_seguro(f"[REFACTOR] {len(lineas)} líneas en "
                         f"{len(self.fragmentos)} fragmentos con {self.modelo}.")

    def _validar_salida_frag(self, texto: str, original: str = "",
                             estricto: bool = True) -> None:
        """Valida sintaxis y que haya transformación real (no solo comentarios)."""
        validar_fragmento(texto, original, self.ruta, estricto)

    def _contexto_solape(self, numero: int) -> str:
        """Cola del fragmento ORIGINAL anterior (contexto estable y no duplicado)."""
        if numero <= 1:
            return ""
        anterior = self.fragmentos[numero - 2]["original"].splitlines()
        if not anterior:
            return ""
        cola = "\n".join(anterior[-self.SOLAPE_LINEAS:])
        return ("\n[CONTEXTO — así termina el fragmento anterior, que YA está en el "
                "archivo; NO lo repitas ni lo incluyas en tu salida:]\n" + cola)

    def refactorizar_fragmento(self, frag: dict, total: int) -> bool:
        """Genera un fragmento con solape+validación; True si quedó usable.

        Hasta ``MAX_REINTENTOS_FRAG`` re-peticiones con el error adjunto; si
        sigue roto se marca irreparable y al ensamblar se conserva el original.
        """
        numero = frag["num"]
        contexto = self._contexto_solape(numero)
        for intento in range(1, self.MAX_REINTENTOS_FRAG + 1):
            frag["intentos"] = intento
            try:
                salida = _generar_fragmento(self.endpoint, self.modelo,
                                            self.ruta.name,
                                            frag["original"] + contexto,
                                            numero, total, 60,
                                            contexto=self.expediente.contexto
                                            if self.expediente else "")
                if not salida.strip():
                    raise ErrorProyecto("devolvió una salida vacía")
                ultimo = intento >= self.MAX_REINTENTOS_FRAG
                self._validar_salida_frag(salida, frag["original"], not ultimo)
                if ultimo and solo_documenta(frag["original"], salida,
                                             self.ruta.suffix.lower() == ".py"):
                    frag["solo_documentacion"] = True
                frag["salida"] = salida
                _imprimir_seguro(f"[REFACTOR {numero}/{total}] OK (intento {intento})")
                return True
            except ErrorProyecto as error:
                self.errores.append(
                    f"- [frag {numero}/{total}, intento {intento}] {error}")
                advertir(f"[REFACTOR {numero}/{total}] {error}; "
                         "reintento con el error adjunto.")
                contexto += f"\n[CORRIJE: tu salida anterior falló con: {error}]"
        frag["irreparable"] = True
        self.fallo_filtro = True  # el modelo no pasó los filtros: se borrará
        self.errores.append(f"- [frag {numero}/{total}] IRREPARABLE tras "
                            f"{self.MAX_REINTENTOS_FRAG} intentos; se conserva el original.")
        return False

    def ensamblar(self) -> str:
        """Une salidas OK + originales de irreparables y valida el conjunto.

        Elimina el solape repetido y **rechaza** (sin truncar) los resultados
        que excedan ``LIMITE_LINEAS_REFACTOR``.
        """
        partes: list[str] = []
        previo = ""
        for frag in self.fragmentos:
            texto = frag["salida"] if frag.get("salida") else frag["original"]
            if frag.get("salida") and previo:
                texto = quitar_solape(previo, texto)
            partes.append(texto)
            previo = partes[-1]
        texto = "\n".join(partes).strip()
        lineas = len(texto.splitlines())
        if lineas > LIMITE_LINEAS_REFACTOR:
            raise ErrorProyecto(
                f"El refactor ocupa {lineas} líneas (tope {LIMITE_LINEAS_REFACTOR}): "
                "se rechaza para no truncar código y se conserva el original.")
        return _validar_refactor(self.contenido, texto, self.ruta)

    # -- registro ----------------------------------------------------------
    def registrar(self, modelo: str, descripcion: str) -> None:
        """Guarda en el .md la nota de LucIA más los bloques de errores/rotación."""
        extra = ""
        if self.errores:
            extra += "\n### Errores\n" + "\n".join(self.errores)
        if self.rotaciones:
            extra += "\n### Rotación\n" + "\n".join(self.rotaciones)
        _registrar_refactor_md(self.ruta, modelo, descripcion.strip() + extra)

    # -- orquestación ------------------------------------------------------
    def ejecutar(self) -> bool:
        """Ejecuta el flujo y GARANTIZA limpiar el peso local (única definición)."""
        try:
            return self._ejecutar_fases()
        finally:
            _borrar_peso_local()

    def _aplicar(self, nuevo: str) -> bool:
        """Pide confirmación si hubo fragmentos irrecuperables y escribe atómico."""
        irreparables = [f["num"] for f in self.fragmentos if f.get("irreparable")]
        if irreparables and self.confirmar_parcial:
            advertir(f"{len(irreparables)} fragmento(s) sin refactorizar "
                     f"({irreparables}); se conserva su código original.")
            if not pedir_confirmacion("¿Se aplica el resultado parcial?"):
                informar("Refactor cancelado; el archivo no se ha modificado.")
                return False
        escribir_texto_atomico(self.ruta, nuevo)
        exito(f"[2/5] Refactorizado ({len(nuevo.splitlines())} líneas): {self.ruta}")
        return True

    def _ejecutar_fases(self) -> bool:
        """Fases [1/5]…[5/5] con rotación de IAs y anotación de errores."""
        if not self.plan_y_confirmacion():
            return False
        # Expediente: código + descripción de LucIA + README con la deuda del archivo.
        self.expediente = preparar_expediente(self.ruta, self.contenido,
                                              self.analisis, self.descripcion_lucia)
        for intento in range(1, self.MAX_IAS + 1):
            _imprimir_seguro(f"[1/5] Preparando IA local "
                             f"(intento {intento}/{self.MAX_IAS})...")
            try:
                self.asegurar_ia()
            except (ErrorProyecto, ValueError, OSError) as error:
                reportar_error(str(error))
                return False
            _imprimir_seguro("[2/5] Refactorizando por fragmentos...")
            self.fragmentos = []
            self.generar_fragmentos()
            total = len(self.fragmentos)
            abortado = False
            for frag in self.fragmentos:
                try:
                    self.refactorizar_fragmento(frag, total)
                except ErrorProyecto as error:  # timeout del vigilante: rota de IA
                    reportar_error(f"El modelo local falló: {error}")
                    self.rotar_ia(str(error))
                    self.registrar(self.modelo, f"FALLO: {error}")
                    abortado = True
                    break
            if abortado:
                if intento >= self.MAX_IAS:
                    return self._cierre_openrouter("3 IAs locales fallaron")
                if not self.nuevo_diagnostico():
                    return False
                continue
            try:
                nuevo = self.ensamblar()
            except ErrorProyecto as error:
                reportar_error(str(error))
                self.fallo_filtro = True  # no pasó los filtros: se borrará
                self.rotar_ia(f"validación global: {error}")
                self.registrar(self.modelo, f"FALLO validación: {error}")
                if intento >= self.MAX_IAS:
                    return self._cierre_openrouter(f"validación: {error}")
                if not self.nuevo_diagnostico():
                    return False
                continue
            # Si la IA devuelve el mismo código, no es un fallo: se pregunta.
            if nuevo.strip() == self.contenido.strip():
                advertir("La IA devolvió el código sin cambios; no se modifica nada.")
                return pedir_confirmacion("¿Se da el archivo por terminado igual?")
            # LucIA puntúa con su red (aprende del par expediente → calidad).
            if self.expediente is not None:
                veredicto = evaluar_y_aprender(self.expediente, nuevo, self.contenido)
                _imprimir_seguro(f"[LUCIA] {veredicto['motivo']}")
                if veredicto["disponible"] and not veredicto["aceptado"]:
                    advertir("LucIA no valida el resultado con su red neuronal.")
                    if self.confirmar_parcial and not pedir_confirmacion(
                            "¿Se aplica igualmente?"):
                        return False
            # Éxito: escritura atómica, nota de LucIA, registro y limpieza final.
            if not self._aplicar(nuevo):
                return False
            if self.expediente is not None:
                informar("README del expediente: "
                         f"{guardar_expediente(self.expediente)}")
            _imprimir_seguro("[3/5] Pidiendo a LucIA su nota interna...")
            self.nota_lucia = self.generador(nuevo, analizar_archivo_local(self.ruta))
            _imprimir_seguro("[4/5] Registrando en el .md...")
            self.registrar(self.modelo, self.nota_lucia)
            if self.consumir_modelos:
                _imprimir_seguro("[5/5] Borrando modelo local...")
                if not _borrar_modelo_ollama(self.endpoint, self.modelo):
                    advertir(f"El modelo {self.modelo} no se pudo borrar; "
                             "revisa `ollama ps` antes de cerrar.")
            else:
                informar(f"[5/5] Modelo conservado: {self.modelo} "
                         "(usa --consumir-modelos para borrarlo).")
            exito("Flujo ds ialocal completado.")
            return True
        return False

    def _cierre_openrouter(self, motivo: str) -> bool:
        """Agotadas las IAs locales: usa free de OpenRouter (borra solo si se pidió)."""
        return _fallback_openrouter(self.ruta, self.contenido, self.analisis,
                                    self.modelo or "local", motivo,
                                    borrar_modelo=self.consumir_modelos)


def cerrar() -> None:
    """Finaliza la sesión interactiva y limpia restos de modelos descargados."""
    _borrar_peso_local()
    informar("Cerrando el sistema...")


def mostrar_menu() -> None:
    """Imprime la lista de comandos disponibles dentro de una caja con bordes."""
    filas = [
        ("crear carpeta", "Crear una carpeta nueva"),
        ("crear archivo", "Crear un archivo nuevo"),
        ("refactorizar", "Copiar el contenido actual de PRY a RFC"),
        ("actualizar", "Reemplazar PRY con la versión de RFC"),
        ("enviar", "Enviar una carpeta con su contenido a CONTRRF/RFC"),
        ("ia local", "Analizar un archivo con LucIA y crear un plan"),
        ("ds ialocal", "Plan de LucIA + refactor con modelo local y registro .md"),
        ("crear codigo", "Crear un archivo nuevo a partir de un diagnóstico de LucIA"),
        ("crear logica", "Escribir una función a partir de lo que le pidas"),
        ("comentar archivo", "Documentar las funciones de un archivo con LucIA"),
        ("test", "Probar un archivo y diagnosticar su deuda técnica"),
        ("rutas", "Ver las rutas activas de RFC/PRY y su origen"),
        ("configurar rutas", "Elegir los directorios de RFC y PRY"),
        ("cerrar", "Cerrar el sistema"),
    ]
    _imprimir_seguro(_caja(f"WoldVirtualP2P3D · Gestor de Proyecto  v{__version__}",
                           filas))
    print()


def ejecutar_comandos() -> None:
    """Bucle principal de la shell interactiva."""
    despachador: dict[str, Callable[[], None]] = {
        "crear carpeta": comando_crear_carpeta,
        "crear archivo": comando_crear_archivo,
        "refactorizar": comando_refactorizar,
        "actualizar": actualizar,
        "enviar": comando_enviar,
        "ia local": comando_ia_local,
        "ds ialocal": comando_ds_ialocal,
        "crear codigo": comando_crear_codigo,
        "crear logica": comando_crear_logica,
        "comentar archivo": comando_comentar_archivo,
        "test": comando_test,
        "rutas": comando_rutas,
        "configurar rutas": comando_configurar_rutas,
    }

    mostrar_menu()
    try:
        while True:
            entrada = input("> ").strip().lower()
            if entrada == "cerrar":
                cerrar()
                break
            accion = despachador.get(entrada)
            if accion is None:
                reportar_error(f"Comando no reconocido: '{entrada}'")
                continue
            try:
                accion()
            except (ErrorProyecto, OSError) as error:
                # La shell sobrevive a cualquier fallo de un comando.
                reportar_error(f"El comando falló: {error}")
    except (KeyboardInterrupt, EOFError):
        _borrar_peso_local()
        informar("Sesión interrumpida; se limpiaron los modelos descargados.")


if __name__ == "__main__":
    ejecutar_comandos()
