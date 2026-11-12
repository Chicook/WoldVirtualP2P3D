"""Base del agente autónomo: tiempo, red, señales y decisión.

Primera mitad de ``AgenteRFPRMN`` (líneas 51–241 de ``sbstm_agnt.py``),
extraída a este submódulo para aligerar la fachada. ``sbstm_agnt`` importa esta
clase base y añade ``Ejecucion``, ``Ciclo`` y el constructor.

Incluye micro-optimizaciones sin cambiar el comportamiento: reloj importado una
vez, cálculo único del tiempo restante en ``decidir`` y pesos leídos una sola
vez por evaluación en ``utilidad``.

Usa imports absolutos al paquete y bootstrap de ``sys.path`` para funcionar
también en ejecución directa (F5).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

#: Directorio que contiene el paquete (``.../STM_RFPRMN``).
_RAIZ_PAQUETE = Path(__file__).resolve().parents[3]
if str(_RAIZ_PAQUETE) not in sys.path:
    sys.path.insert(0, str(_RAIZ_PAQUETE))

from STM_RFPRMN_stmDL.stm_base import ErrorProyecto, advertir  # noqa: E402
from STM_RFPRMN_stmDL.test import diagnostico_deuda  # noqa: E402

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

__all__ = ["ACCIONES", "COSTES", "PESOS", "TIEMPOS", "AgenteRFPRMN"]


class AgenteRFPRMN:
    """Ejecuta comandos de RFPRMN decidiendo por utilidad, no por ``input()``.

    Esta clase base agrupa las clases anidadas de análisis y decisión; la parte
    de ejecución y el ciclo completo los añade ``sbstm_agnt``.
    """

    class Tiempo:
        """Presupuesto temporal de la sesión."""

        @staticmethod
        def restante(agente) -> float:
            """Segundos que quedan del presupuesto de esta sesión."""
            if not agente._inicio:
                return agente.presupuesto_tiempo
            return max(0.0, agente.presupuesto_tiempo
                       - (time.monotonic() - agente._inicio))

        @staticmethod
        def estimar_tiempo(agente, accion: str,
                           analisis: dict | None = None) -> float:
            """Segundos estimados de la acción (el refactor crece por fragmentos)."""
            lineas = int((analisis or {}).get("lineas", 0) or 0)
            if accion == "refactorizar":
                return max(30.0, float(max(1, -(-lineas // 60))) * 40.0)
            if accion == "comentar":
                return max(10.0, float(lineas) * 0.4)
            return float(TIEMPOS.get(accion, 10))

    class Red:
        """Quinta señal: predicción de LucIA a partir de lo aprendido."""

        @staticmethod
        def senal_red(agente, contenido: str = "",
                      pasos: int | None = None) -> float:
            """Predicción de LucIA (0-1): probabilidad de que el refactor valga.

            Si el ``seq2seq`` tiene un refactor memorizado para un código
            equivalente, sube; si no, se queda en 0.5. La señal se **encoge**
            hacia 0.5 según lo que haya aprendido la red, porque con pocas
            muestras su opinión no debe pesar como una certeza.
            """
            valor = 0.5
            try:
                from STM_RFPRMN_stmDL import stm_seq2seq
                if contenido and stm_seq2seq.generar(contenido):
                    valor = 0.9
                elif stm_seq2seq.estado().get("pares", 0):
                    valor = 0.6
            except Exception:  # noqa: BLE001 - sin memoria, señal neutra
                valor = 0.5
            if pasos is None:
                try:
                    from STM_RFPRMN_stmDL.stm_lucia import pasos_aprendidos
                    pasos = pasos_aprendidos()
                except Exception:  # noqa: BLE001
                    pasos = 0
            confianza = min(1.0, max(0.0, float(pasos or 0) / 8.0))
            return round(0.5 + (valor - 0.5) * confianza, 4)

    class Senales:
        """Diagnóstico, integridad y señales que alimentan la utilidad."""

        @staticmethod
        def analizar(agente, ruta: str | Path) -> dict:
            """Diagnóstico de deuda del archivo (0-100, métricas y contenido)."""
            try:
                informe = diagnostico_deuda(ruta)
            except ErrorProyecto as error:
                return {"puntuacion": 100, "lineas": 0, "motivos": [],
                        "error": str(error)}
            try:
                informe["contenido"] = Path(str(ruta)).read_text(encoding="utf-8-sig")
            except OSError:
                informe["contenido"] = ""
            return informe

        @staticmethod
        def autoanalisis(agente) -> dict:
            """Comprobación de integridad antes de tocar nada."""
            problemas: list[str] = []
            try:
                from STM_RFPRMN_stmDL import verificar_presupuesto
                if not verificar_presupuesto().get("ok", False):
                    problemas.append("presupuesto de módulos en rojo")
            except Exception as error:  # noqa: BLE001 - el autoanálisis no rompe
                problemas.append(f"no se pudo verificar el presupuesto ({error})")
            try:
                import numpy  # noqa: F401
            except ImportError:
                problemas.append("numpy no disponible")
            return {"ok": not problemas, "problemas": problemas}

        @staticmethod
        def exito_previo(agente, accion: str) -> float:
            """**Calidad media** conseguida por esa acción (0.5 si no hay datos)."""
            suma, intentos = agente.historial.get(accion, [0.0, 0])
            if not intentos:
                return 0.5
            return round(min(1.0, max(0.0, suma / intentos)), 4)

        @staticmethod
        def urgencia(agente, analisis: dict) -> float:
            """Cuánto corre prisa tocar ese archivo."""
            lineas = int(analisis.get("lineas", 0) or 0)
            if lineas > agente.limite:
                return 1.0
            if lineas > agente.limite * 2 // 3:
                return 0.5
            return 0.0

        @staticmethod
        def utilidad(agente, accion: str, analisis: dict | None = None,
                     red: float | None = None) -> tuple[float, dict]:
            """Utilidad de una acción (0-1) y las señales que la componen."""
            analisis = analisis or {}
            puntuacion = float(analisis.get("puntuacion", 100))
            if red is None:
                red = agente.senal_red(str(analisis.get("contenido", "")))
            senales = {
                "deficit": max(0.0, min(1.0, (100.0 - puntuacion) / 100.0)),
                "urgencia": agente.urgencia(analisis),
                "exito": agente.exito_previo(accion),
                "coste": COSTES.get(accion, 0.5),
                "red": max(0.0, min(1.0, float(red))),
            }
            w = PESOS
            valor = (w["deficit"] * senales["deficit"]
                     + w["urgencia"] * senales["urgencia"]
                     + w["exito"] * senales["exito"]
                     + w["coste"] * (1.0 - senales["coste"])
                     + w["red"] * senales["red"])
            return round(min(1.0, max(0.0, valor)), 4), senales

    class Decision:
        """Decisión matemática: umbral, presupuesto y cierre de sesión."""

        @staticmethod
        def decidir(agente, accion: str,
                    ruta: str | Path | None = None) -> tuple[bool, float, str]:
            """¿Se lanza la acción? Devuelve (sí/no, utilidad, motivo)."""
            integridad = agente.autoanalisis()
            if not integridad["ok"]:
                return False, 0.0, ("autoanálisis: "
                                    + "; ".join(integridad["problemas"]))
            analisis = ruta if isinstance(ruta, dict) else (
                agente.analizar(ruta) if ruta is not None else {})
            valor, _ = agente.utilidad(accion, analisis)
            umbral = agente.umbral
            if valor < umbral:
                return False, valor, f"utilidad {valor} < umbral {umbral}"
            restante = agente.restante()
            tiempo = agente.estimar_tiempo(accion, analisis)
            if tiempo > restante:
                return False, valor, (f"no cabe en el presupuesto: {int(tiempo)}s "
                                      f"> {int(restante)}s")
            return True, valor, "utilidad suficiente"

        @staticmethod
        def desea_cerrar(agente) -> tuple[bool, float, str]:
            """¿Puede LucIA cerrar su máquina de comandos? (y con qué puntuación)."""
            if agente._en_flujo:
                return False, 0.0, "hay un flujo abierto"
            integridad = agente.autoanalisis()
            if not integridad["ok"]:
                return False, 0.0, ("autoanálisis: "
                                    + "; ".join(integridad["problemas"]))
            pendientes = list(agente.pendientes)
            if pendientes:
                carga = max((agente.utilidad("refactorizar",
                                             agente.analizar(ruta))[0]
                             for ruta in pendientes), default=0.0)
                if carga >= agente.umbral_cierre:
                    return False, round(1.0 - carga, 3), f"queda trabajo (carga {carga})"
                return True, round(1.0 - carga, 3), "trabajo por debajo del umbral"
            return True, 1.0, "sin trabajo pendiente"

        @staticmethod
        def cerrar_si_procede(agente) -> bool:
            """Cierra si ``desea_cerrar`` lo autoriza; no pasa por el umbral normal."""
            autorizado, valor, motivo = agente.desea_cerrar()
            if not autorizado:
                return False
            agente._en_flujo = True
            try:
                resultado = bool(agente._lanzar("cerrar", None, valor))
            except Exception as error:  # noqa: BLE001 - cerrar no debe romper nada
                advertir(f"cerrar falló: {error}")
                resultado = False
            finally:
                agente._en_flujo = False
            agente._anotar("cerrar", resultado, valor, motivo)
            return resultado

    # API de esta mitad: alias directos, sin capa extra de llamada.
    restante = Tiempo.restante
    estimar_tiempo = Tiempo.estimar_tiempo
    senal_red = Red.senal_red
    analizar = Senales.analizar
    autoanalisis = Senales.autoanalisis
    exito_previo = Senales.exito_previo
    urgencia = Senales.urgencia
    utilidad = Senales.utilidad
    decidir = Decision.decidir
    desea_cerrar = Decision.desea_cerrar
    cerrar_si_procede = Decision.cerrar_si_procede


if __name__ == "__main__":
    # Ejecución directa (F5 / python snrtstm_sbstm_agnt.py): confirma que carga.
    print(f"snrtstm_sbstm_agnt OK · {AgenteRFPRMN.__name__} base · "
          f"{len(ACCIONES)} acciones")
