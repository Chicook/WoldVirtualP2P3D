"""Submodulo de RFPRMN (refactor: tope 400/450 lineas)."""
from __future__ import annotations
import ast, json, os, re, shutil, stat, subprocess, sys, textwrap, urllib.error, urllib.parse, urllib.request, uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional
try:
    from .stm_base import (E, informar, exito, advertir, reportar_error, pedir_confirmacion, ErrorProyecto, __version__, _caja, _panel, _imprimir_seguro)
    from .stm_gestion import comando_crear_carpeta, comando_crear_archivo, comando_refactorizar, actualizar, comando_enviar
    from .stm_analisis import comando_ia_local
    from .stm_refactor import comando_ds_ialocal, _borrar_peso_local
except ImportError:
    pass

class FlujoRefactorLucIA:
    """Máquina de estados del flujo ds ialocal para un archivo.

    Decisiones aplicadas: ante fallo de validación se borra la IA local con
    ``ollama rm``; el fragmento irreparable (2 reintentos) se escala a otra IA
    y todos los errores se anotan en ``registro_refactor.md``.
    """

    MAX_IAS = 3
    MAX_REINTENTOS_FRAG = 2
    SOLAPE_LINEAS = 10

    def __init__(self, ruta: Path, contenido: str, consultor: Optional[ConsultorIA] = None) -> None:
        self.ruta = ruta
        self.contenido = contenido
        self.analisis = analizar_archivo_local(ruta)
        self.generador = consultor or consultar_ia_local
        self.modelo = ""
        self.endpoint = ""
        self.fallidas: set[str] = set()
        self.errores: list[str] = []      # líneas "### Errores" para el .md
        self.rotaciones: list[str] = []   # líneas "### Rotación" para el .md
        self.fragmentos: list[dict] = []  # {num, original, salida, irreparable}
        self.nota_lucia = ""

    # -- fase PLAN ---------------------------------------------------------
    def plan_y_confirmacion(self) -> bool:
        """Muestra diagnóstico+plan de LucIA y pide s/n (con opciones 1/2)."""
        plan_lucia = self.generador(self.contenido, self.analisis)
        _imprimir_seguro(_panel("LucIA · Plan de refactorización", plan_lucia.strip()))
        plan = crear_plan_refactorizacion(self.analisis)
        print(f"\n{E.negrita}Plan de refactorización{E.reset}")
        for indice, paso in enumerate(plan, start=1):
            print(f"  {E.cian}{indice}.{E.reset} {paso}")
        if not pedir_confirmacion("¿Se aplica el plan?"):
            _pedir_extra_o_diagnostico(self.contenido, self.analisis)
            return False
        return True

    def nuevo_diagnostico(self) -> bool:
        """Tras rotar de IA: nuevo diagnóstico+plan de LucIA y confirmación."""
        _imprimir_seguro("[VIGILANTE] Reiniciando flujo con otra IA local...")
        plan_lucia = self.generador(self.contenido, self.analisis)
        _imprimir_seguro(_panel("LucIA · Nuevo diagnóstico", plan_lucia.strip()))
        plan = crear_plan_refactorizacion(self.analisis)
        print(f"\n{E.negrita}Plan de refactorización{E.reset}")
        for indice, paso in enumerate(plan, start=1):
            print(f"  {E.cian}{indice}.{E.reset} {paso}")
        if not pedir_confirmacion("¿Se aplica el plan con la nueva IA?"):
            _pedir_extra_o_diagnostico(self.contenido, self.analisis)
            return False
        return True

    # -- fase IA -----------------------------------------------------------
    def asegurar_ia(self) -> None:
        """Descarga/elige IA local no usada y libera la CPU para ella."""
        self.endpoint, _ = _cargar_configuracion_ia_local()
        self.modelo = _asegurar_modelo_codigo(excluir=self.fallidas)
        _liberar_ollama(excepto=self.modelo)
        _imprimir_seguro(f"[1/5] OK, modelo listo: {self.modelo}")

    def rotar_ia(self, motivo: str) -> None:
        """Borra la IA actual con `ollama rm`, la anota y marca como fallida."""
        _imprimir_seguro(f"[VIGILANTE] Borrando {self.modelo} ({motivo}).")
        _borrar_modelo_ollama(self.endpoint, self.modelo)
        self.rotaciones.append(f"- {self.modelo} borrada con `ollama rm` (motivo: {motivo})")
        self.fallidas.add(self.modelo)

    # -- fase FRAGMENTOS ---------------------------------------------------
    def generar_fragmentos(self) -> None:
        """Corte en fronteras seguras con solape de contexto entre fragmentos."""
        lineas = self.contenido.splitlines()
        actual: list[str] = []
        for ln in lineas:
            actual.append(ln)
            if len(actual) >= LINEAS_POR_FRAGMENTO and (
                    not ln.strip() or re.match(r"\s*(def |class |if |for |while |try:|else:|elif )", ln)):
                self.fragmentos.append({"original": "\n".join(actual), "salida": "",
                                        "irreparable": False})
                actual = []
        if actual:
            self.fragmentos.append({"original": "\n".join(actual), "salida": "",
                                    "irreparable": False})
        for i, f in enumerate(self.fragmentos, start=1):
            f["num"] = i
        _imprimir_seguro(f"[REFACTOR] {len(lineas)} líneas en {len(self.fragmentos)} "
                         f"fragmentos con {self.modelo}.")

    def _validar_salida_frag(self, texto: str) -> None:
        """Valida un fragmento .py con ast (detecta cortes a mitad de string)."""
        if self.ruta.suffix.lower() == ".py":
            try:
                ast.parse(texto, filename=str(self.ruta))
            except SyntaxError as error:
                raise ErrorProyecto(f"frag inválido (línea {error.lineno}: {error.msg})")

    def refactorizar_fragmento(self, frag: dict, total: int) -> bool:
        """Genera un fragmento con solape+validación; True si quedó usable.

        Hasta MAX_REINTENTOS_FRAG re-pidiendo con el error adjunto; si sigue
        roto se marca irreparable (se conserva el original al ensamblar).
        """
        num = frag["num"]
        contexto = ""
        if num > 1 and self.fragmentos[num - 2].get("salida"):
            prev = self.fragmentos[num - 2]["salida"].splitlines()
            contexto = ("\n[CONTEXTO: el fragmento anterior termina así, continúa "
                        "con coherencia sin repetirlo:]\n" + "\n".join(prev[-self.SOLAPE_LINEAS:]))
        for intento in range(1, self.MAX_REINTENTOS_FRAG + 1):
            try:
                salida = _generar_fragmento(self.endpoint, self.modelo,
                                            self.ruta.name, frag["original"] + contexto,
                                            num, total, 60)
                self._validar_salida_frag(salida)
                frag["salida"] = salida
                _imprimir_seguro(f"[REFACTOR {num}/{total}] OK (intento {intento})")
                return True
            except ErrorProyecto as error:
                self.errores.append(f"- [frag {num}/{total}, intento {intento}] {error}")
                advertir(f"[REFACTOR {num}/{total}] {error}; reintento con el error adjunto.")
                # El siguiente intento lleva el error en el contexto del prompt.
                contexto += f"\n[CORRIJE: tu salida anterior falló con: {error}]"
        frag["irreparable"] = True
        self.errores.append(f"- [frag {num}/{total}] IRREPARABLE tras "
                            f"{self.MAX_REINTENTOS_FRAG} intentos; se conserva el original.")
        return False

    def ensamblar(self) -> str:
        """Une salidas OK + originales de irreparables y valida el conjunto."""
        partes = [f["salida"] if f.get("salida") else f["original"] for f in self.fragmentos]
        texto = "\n".join(partes).strip()
        if len(texto.splitlines()) > LIMITE_LINEAS_REFACTOR:
            texto = "\n".join(texto.splitlines()[:LIMITE_LINEAS_REFACTOR])
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
        """Ejecuta las fases [1/5]…[5/5]; devuelve True si el archivo quedó."""
    def ejecutar(self) -> bool:
        """Ejecuta el flujo completo y GARANTIZA borrar el GGUF local al terminar.

        Envuelve ``_ejecutar_fases`` con try/finally: el peso descargado de
        HuggingFace se elimina en éxito, error, cancelación o fallback, para no
        dejar residuos de ~1 GB en ``modelosIAlocal/IAlocalDESCARGADA``.
        """
        try:
            return self._ejecutar_fases()
        finally:
            _borrar_peso_local()

    def _ejecutar_fases(self) -> bool:
        """Fases [1/5]…[5/5] con rotación de IAs y anotación de errores."""
        if not self.plan_y_confirmacion():
            return False
        for intento in range(1, self.MAX_IAS + 1):
            _imprimir_seguro(f"[1/5] Descargando modelo de IA (intento {intento}/{self.MAX_IAS})...")
            try:
                self.asegurar_ia()
            except (ErrorProyecto, ValueError) as error:
                reportar_error(str(error))
                return False
            _imprimir_seguro("[2/5] Refactorizando por fragmentos...")
            self.fragmentos = []
            self.generar_fragmentos()
            total = len(self.fragmentos)
            for frag in self.fragmentos:
                try:
                    self.refactorizar_fragmento(frag, total)
                except ErrorProyecto as error:  # timeout del vigilante: rota de IA
                    reportar_error(f"El modelo local falló: {error}")
                    self.rotar_ia(str(error))
                    self.registrar(self.modelo, f"FALLO: {error}")
                    break
            else:
                try:
                    nuevo = self.ensamblar()
                except ErrorProyecto as error:
                    reportar_error(str(error))
                    self.rotar_ia(f"validación global: {error}")
                    self.registrar(self.modelo, f"FALLO validación: {error}")
                    if intento >= self.MAX_IAS:
                        return self._cierre_openrouter(f"validación: {error}")
                    if not self.nuevo_diagnostico():
                        return False
                    continue
                # Detecta refactor no-op (IA que devuelve el input sin tocarlo).
                if nuevo.strip() == self.contenido.strip():
                    self.errores.append("- [global] el modelo devolvió el código sin cambios")
                    reportar_error("La IA no cambió nada (refactor no-op); se rota de modelo.")
                    self.rotar_ia("refactor no-op")
                    self.registrar(self.modelo, "FALLO: refactor no-op (código idéntico).")
                    if intento >= self.MAX_IAS:
                        return self._cierre_openrouter("refactor no-op")
                    if not self.nuevo_diagnostico():
                        return False
                    continue
                # Éxito: nota de LucIA, registro y limpieza final.
                self.ruta.write_text(nuevo, encoding="utf-8")
                exito(f"[2/5] Refactorizado ({len(nuevo.splitlines())} líneas): {self.ruta}")
                _imprimir_seguro("[3/5] Pidiendo a LucIA su nota interna...")
                self.nota_lucia = self.generador(nuevo, analizar_archivo_local(self.ruta))
                _imprimir_seguro("[4/5] Registrando en el .md...")
                self.registrar(self.modelo, self.nota_lucia)
                _imprimir_seguro("[5/5] Borrando modelo local...")
                _borrar_modelo_ollama(self.endpoint, self.modelo)
                exito("Flujo ds ialocal completado.")
                return True
            if intento >= self.MAX_IAS:
                return self._cierre_openrouter("3 IAs locales fallaron")
            if not self.nuevo_diagnostico():
                return False
        return False

    def _cierre_openrouter(self, motivo: str) -> bool:
        """Agotadas las IAs locales: borra restos y usa free de OpenRouter."""
        return _fallback_openrouter(self.ruta, self.contenido, self.analisis,
                                    self.modelo or "local", motivo)


# --- Menú interactivo --------------------------------------------------------

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
        ("cerrar", "Cerrar el sistema"),
    ]
    _imprimir_seguro(_caja(f"WoldVirtualP2P3D · Gestor de Proyecto  v{__version__}", filas))
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
            accion()
    except (KeyboardInterrupt, EOFError):
        _borrar_peso_local()
        informar("Sesión interrumpida; se limpiaron los modelos descargados.")


if __name__ == "__main__":
    ejecutar_comandos()
