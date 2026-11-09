"""Puente para que LucIA use los comandos de RFPRMN **sin humano**.

LucIA no puede quedarse esperando un ``s/n``: este agente sustituye la
confirmación interactiva por una **decisión matemática** y ejecuta los comandos
en orden lógico. La decisión combina cuatro señales normalizadas:

- **déficit**: ``(100 - puntuación_deuda) / 100`` del archivo.
- **urgencia**: 1.0 si supera el tope de 450 líneas, 0.5 si pasa de 300.
- **éxito previo**: aciertos/intentos de esa acción en esta sesión (0.5 al empezar).
- **coste**: lo que tarda y lo que toca (partir < probar < comentar < informe < refactorizar).

``utilidad = 0.45·déficit + 0.30·urgencia + 0.15·éxito + 0.10·(1 - coste)``
y se actúa si ``utilidad >= umbral``.

Para no romperse a sí misma, antes de actuar hace un **autoanálisis**: que el
presupuesto de módulos esté en verde, que las rutas existan y que numpy esté.
Si algo falla, solo permite las acciones de diagnóstico. ``cerrar`` nunca se
lanza a mano: se decide con ``desea_cerrar`` y solo si no hay flujo abierto ni
trabajo pendiente.
"""
from __future__ import annotations

from pathlib import Path

from .stm_base import ErrorProyecto, advertir, informar
from .stm_entrenamiento import convertir_si_existe
from .stm_informe import generar_informe
from .stm_particion import partir_archivo
from .stm_comentarios import comentar_archivo
from .test import diagnostico_deuda

#: Acciones que el agente sabe lanzar.
ACCIONES = ("presupuesto", "estado", "probar", "partir", "comentar",
            "refactorizar", "informe", "cerrar")

#: Coste relativo de cada acción (0 = gratis, 1 = lo más caro).
COSTES = {"presupuesto": 0.05, "estado": 0.1, "probar": 0.2, "partir": 0.35,
          "comentar": 0.5, "informe": 0.6, "refactorizar": 1.0, "cerrar": 0.05}

#: Segundos típicos de cada acción (medidos en CPU con un 7B).
TIEMPOS = {"presupuesto": 1, "estado": 1, "probar": 2, "partir": 5,
           "informe": 3, "comentar": 30, "refactorizar": 90, "cerrar": 2}

#: Pesos de la utilidad (suman 1). ``red`` es la predicción de LucIA.
PESOS = {"deficit": 0.35, "urgencia": 0.25, "exito": 0.10, "coste": 0.10,
         "red": 0.20}


class AgenteRFPRMN:
    """Ejecuta comandos de RFPRMN decidiendo por utilidad, no por ``input()``."""

    def __init__(self, umbral: float = 0.55, umbral_cierre: float = 0.20,
                 limite: int = 450, presupuesto_segundos: float = 300.0) -> None:
        self.umbral = float(umbral)
        self.umbral_cierre = float(umbral_cierre)
        self.limite = int(limite)
        self.presupuesto_tiempo = float(presupuesto_segundos)
        self._inicio = 0.0
        self.historial: dict[str, list[float]] = {}
        self.ultima_calidad: float | None = None
        self.registro: list[dict] = []
        self.pendientes: list[str] = []
        self._en_flujo = False
        self._decision: bool = False

    # -- tiempo -----------------------------------------------------------
    def restante(self) -> float:
        """Segundos que quedan del presupuesto de esta sesión."""
        if not self._inicio:
            return self.presupuesto_tiempo
        import time as _time

        return max(0.0, self.presupuesto_tiempo - (_time.monotonic() - self._inicio))

    def estimar_tiempo(self, accion: str, analisis: dict | None = None) -> float:
        """Segundos estimados de la acción (el refactor crece por fragmentos)."""
        lineas = int((analisis or {}).get("lineas", 0) or 0)
        if accion == "refactorizar":
            fragmentos = max(1, -(-lineas // 60))
            return max(30.0, float(fragmentos) * 40.0)
        if accion == "comentar":
            return max(10.0, float(lineas) * 0.4)
        return float(TIEMPOS.get(accion, 10))

    # -- señal de la red (quinta) -----------------------------------------
    def senal_red(self, contenido: str = "", pasos: int | None = None) -> float:
        """Predicción de LucIA (0-1): probabilidad de que el refactor valga.

        Se apoya en lo que ya aprendió: si el ``seq2seq`` tiene un refactor
        memorizado para un código equivalente, sube; si no, se queda en 0.5. La
        señal se **encoge** hacia 0.5 según lo que haya aprendido la red, porque
        con pocas muestras su opinión no debe pesar como una certeza.
        """
        valor = 0.5
        try:
            from . import stm_seq2seq

            if contenido and stm_seq2seq.generar(contenido):
                valor = 0.9
            elif stm_seq2seq.estado().get("pares", 0):
                valor = 0.6
        except Exception:  # noqa: BLE001 - sin memoria, señal neutra
            valor = 0.5
        if pasos is None:
            try:
                from .stm_lucia import pasos_aprendidos

                pasos = pasos_aprendidos()
            except Exception:  # noqa: BLE001
                pasos = 0
        confianza = min(1.0, max(0.0, float(pasos or 0) / 8.0))
        return round(0.5 + (valor - 0.5) * confianza, 4)

    # -- señales ----------------------------------------------------------
    def analizar(self, ruta: str | Path) -> dict:
        """Diagnóstico de deuda del archivo (0-100, métricas y contenido)."""
        try:
            informe = diagnostico_deuda(ruta)
        except ErrorProyecto as error:
            return {"puntuacion": 100, "lineas": 0, "motivos": [], "error": str(error)}
        try:
            informe["contenido"] = Path(str(ruta)).read_text(encoding="utf-8-sig")
        except OSError:
            informe["contenido"] = ""
        return informe

    def autoanalisis(self) -> dict:
        """Comprobación de integridad antes de tocar nada."""
        problemas: list[str] = []
        try:
            from . import verificar_presupuesto

            informe = verificar_presupuesto()
            if not informe.get("ok", False):
                problemas.append("presupuesto de módulos en rojo")
        except Exception as error:  # noqa: BLE001 - el autoanálisis no debe romper
            problemas.append(f"no se pudo verificar el presupuesto ({error})")
        try:
            import numpy  # noqa: F401
        except ImportError:
            problemas.append("numpy no disponible")
        return {"ok": not problemas, "problemas": problemas}

    def exito_previo(self, accion: str) -> float:
        """**Calidad media** conseguida por esa acción (0.5 si aún no hay datos).

        No es un contador de aciertos: cada intento aporta su nota (la que dio
        la red de LucIA al aplicarlo), así que una acción que funciona a medias
        pesa menos que una que sale bien.
        """
        suma, intentos = self.historial.get(accion, [0.0, 0])
        if not intentos:
            return 0.5
        return round(min(1.0, max(0.0, suma / intentos)), 4)

    def urgencia(self, analisis: dict) -> float:
        """Cuánto corre prisa tocar ese archivo."""
        lineas = int(analisis.get("lineas", 0) or 0)
        if lineas > self.limite:
            return 1.0
        if lineas > self.limite * 2 // 3:
            return 0.5
        return 0.0

    def utilidad(self, accion: str, analisis: dict | None = None,
                 red: float | None = None) -> tuple[float, dict]:
        """Utilidad de una acción (0-1) y las señales que la componen.

        La quinta señal (``red``) es la predicción de LucIA: cuánto respaldo
        tiene la acción según lo aprendido. Se puede pasar ya calculada.
        """
        analisis = analisis or {}
        puntuacion = float(analisis.get("puntuacion", 100))
        if red is None:
            red = self.senal_red(str(analisis.get("contenido", "")))
        senales = {
            "deficit": max(0.0, min(1.0, (100.0 - puntuacion) / 100.0)),
            "urgencia": self.urgencia(analisis),
            "exito": self.exito_previo(accion),
            "coste": COSTES.get(accion, 0.5),
            "red": max(0.0, min(1.0, float(red))),
        }
        valor = (PESOS["deficit"] * senales["deficit"]
                 + PESOS["urgencia"] * senales["urgencia"]
                 + PESOS["exito"] * senales["exito"]
                 + PESOS["coste"] * (1.0 - senales["coste"])
                 + PESOS["red"] * senales["red"])
        return round(min(1.0, max(0.0, valor)), 4), senales

    # -- decisión ---------------------------------------------------------
    def decidir(self, accion: str, ruta: str | Path | None = None) -> tuple[bool, float, str]:
        """¿Se lanza la acción? Devuelve (sí/no, utilidad, motivo)."""
        integridad = self.autoanalisis()
        if not integridad["ok"]:
            return False, 0.0, "autoanálisis: " + "; ".join(integridad["problemas"])
        analisis = ruta if isinstance(ruta, dict) else (
            self.analizar(ruta) if ruta is not None else {})
        valor, _ = self.utilidad(accion, analisis)
        if valor < self.umbral:
            return False, valor, f"utilidad {valor} < umbral {self.umbral}"
        tiempo = self.estimar_tiempo(accion, analisis)
        if tiempo > self.restante():
            return False, valor, (f"no cabe en el presupuesto: {int(tiempo)}s "
                                  f"> {int(self.restante())}s")
        return True, valor, "utilidad suficiente"

    def desea_cerrar(self) -> tuple[bool, float, str]:
        """¿Puede LucIA cerrar su máquina de comandos? (y con qué puntuación)."""
        if self._en_flujo:
            return False, 0.0, "hay un flujo abierto"
        integridad = self.autoanalisis()
        if not integridad["ok"]:
            return False, 0.0, "autoanálisis: " + "; ".join(integridad["problemas"])
        pendientes = [r for r in self.pendientes]
        if pendientes:
            carga = max((self.utilidad("refactorizar", self.analizar(ruta))[0]
                         for ruta in pendientes), default=0.0)
            if carga >= self.umbral_cierre:
                return False, round(1.0 - carga, 3), f"queda trabajo (carga {carga})"
            return True, round(1.0 - carga, 3), "trabajo por debajo del umbral"
        return True, 1.0, "sin trabajo pendiente"

    def cerrar_si_procede(self) -> bool:
        """Cierra si ``desea_cerrar`` lo autoriza; no pasa por el umbral normal.

        Cerrar no compite con las demás acciones: la decisión ya la tomó
        ``desea_cerrar`` con la carga de trabajo y la integridad del sistema.
        """
        autorizado, valor, motivo = self.desea_cerrar()
        if not autorizado:
            return False
        self._en_flujo = True
        try:
            resultado = bool(self._lanzar("cerrar", None, valor))
        except Exception as error:  # noqa: BLE001 - cerrar no debe romper nada
            advertir(f"cerrar falló: {error}")
            resultado = False
        finally:
            self._en_flujo = False
        self._anotar("cerrar", resultado, valor, motivo)
        return resultado

    # -- ejecución --------------------------------------------------------
    def _con_politica(self, valor: bool, funcion, *args, **kwargs):
        """Ejecuta algo con la confirmación forzada a ``valor``."""
        from . import stm_base

        original = stm_base.pedir_confirmacion
        stm_base.pedir_confirmacion = lambda *_a, **_k: valor
        try:
            return funcion(*args, **kwargs)
        finally:
            stm_base.pedir_confirmacion = original

    def _anotar(self, accion: str, ok: bool, utilidad: float, motivo: str = "",
                calidad: float | None = None) -> None:
        """Anota el intento con su **calidad** (no solo si salió bien)."""
        peso = float(calidad) if calidad is not None else (1.0 if ok else 0.0)
        suma, intentos = self.historial.get(accion, [0.0, 0])
        self.historial[accion] = [suma + peso, intentos + 1]
        self.registro.append({"accion": accion, "ok": ok, "utilidad": utilidad,
                              "motivo": motivo, "calidad": peso})

    def ejecutar(self, accion: str, ruta: str | Path | None = None) -> bool:
        """Lanza una acción si la decisión matemática lo permite."""
        if accion not in ACCIONES:
            advertir(f"Acción desconocida: {accion}")
            return False
        permite, valor, motivo = self.decidir(accion, ruta)
        if not permite:
            self._anotar(accion, False, valor, motivo)
            return False
        self._en_flujo = True
        self.ultima_calidad = None
        try:
            resultado = self._lanzar(accion, ruta, valor)
        except Exception as error:  # noqa: BLE001 - LucIA no debe caerse
            advertir(f"{accion} falló: {error}")
            resultado = False
        finally:
            self._en_flujo = False
        self._anotar(accion, bool(resultado), valor, "ejecutada", self.ultima_calidad)
        return bool(resultado)

    def _lanzar(self, accion: str, ruta, valor: float) -> bool:
        """Ejecuta la acción concreta con la política de confirmación."""
        if accion == "presupuesto":
            from . import verificar_presupuesto

            return bool(verificar_presupuesto().get("ok", False))
        if accion == "estado":
            from . import modulos_estado

            return bool(modulos_estado())
        if accion == "probar":
            informe = self.analizar(ruta)
            informar(f"{Path(str(ruta)).name}: {informe.get('puntuacion')}/100")
            return "error" not in informe
        if accion == "partir":
            return bool(self._con_politica(True, partir_archivo, ruta).get("partido"))
        if accion == "comentar":
            return bool(self._con_politica(True, comentar_archivo, ruta))
        if accion == "informe":
            return generar_informe(ruta, con_ia=False) is not None
        if accion == "refactorizar":
            return bool(self._con_politica(True, self._refactorizar, ruta))
        if accion == "cerrar":
            return bool(self._con_politica(True, self._cerrar))
        return False

    def _refactorizar(self, ruta) -> bool:
        """Lanza el flujo de refactor y devuelve también la nota de LucIA."""
        from .stm_flujo import FlujoRefactorLucIA

        origen = Path(str(ruta))
        contenido = origen.read_text(encoding="utf-8-sig")
        flujo = FlujoRefactorLucIA(origen, contenido,
                                   lambda texto, _analisis: f"Refactor de {origen.name}")
        resultado = flujo.ejecutar()
        if resultado:
            self.ultima_calidad = getattr(flujo, "nota_final", None)
        return resultado

    def _cerrar(self) -> bool:
        """Cierra la máquina de comandos (y reparte lo que sobre en CONTRUCCION)."""
        from . import repartir_carpeta

        repartir_carpeta()
        informar("LucIA cierra su máquina de comandos.")
        return True

    # -- ciclo completo ---------------------------------------------------
    def ciclo(self, rutas: list[str | Path]) -> dict:
        """Orden lógico: salud → probar → partir/refactorizar/comentar → informe."""
        resultados: list[dict] = []
        import time as _time

        self._inicio = _time.monotonic()
        self.pendientes = [str(ruta) for ruta in rutas]
        if not self.ejecutar("presupuesto"):
            return {"acciones": resultados, "cerrado": False,
                    "motivo": "presupuesto en rojo"}
        agotado = False
        for ruta in rutas:
            if self.restante() <= 0:
                agotado = True
                break
            analisis = self.analizar(ruta)
            objetivos = []
            if int(analisis.get("lineas", 0) or 0) > self.limite:
                objetivos.append("partir")
            if analisis.get("motivos") and float(analisis.get("puntuacion", 0)) < 60:
                objetivos.append("refactorizar")
            if any("docstring" in str(motivo) for motivo, _ in analisis.get("motivos", [])):
                objetivos.append("comentar")
            objetivos.append("informe")
            for accion in objetivos:
                ok = self.ejecutar(accion, ruta)
                resultados.append({"ruta": str(ruta), "accion": accion, "ok": ok})
            convertir_si_existe(Path(str(ruta)).parent / f"informe_{Path(str(ruta)).stem}.md")
            if str(ruta) in self.pendientes:
                self.pendientes.remove(str(ruta))
        cerrar, valor, motivo = self.desea_cerrar()
        if cerrar:
            self.cerrar_si_procede()
        return {"acciones": resultados, "cerrado": cerrar,
                "puntuacion_cierre": valor, "motivo": motivo,
                "agotado": agotado, "restante": round(self.restante(), 1)}
