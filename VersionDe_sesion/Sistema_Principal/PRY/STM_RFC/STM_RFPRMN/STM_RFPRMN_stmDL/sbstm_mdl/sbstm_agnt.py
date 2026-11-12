"""Agente autónomo de RFPRMN: decide y ejecuta comandos sin intervención humana.

La base (``Tiempo``, ``Red``, ``Senales`` y ``Decision``) vive en
``sbrtstm/snrtstm_sbstm_agnt.py``. Este módulo la importa y completa la clase
``AgenteRFPRMN`` con ``Ejecucion``, ``Ciclo`` y el constructor, conservando
exactamente la misma API pública.

Usa imports absolutos al paquete y añade la raíz al ``sys.path`` para funcionar
también en ejecución directa (F5), igual que el resto de ``sbstm_mdl``.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

#: Directorio que contiene el paquete (``.../STM_RFPRMN``).
_RAIZ_PAQUETE = Path(__file__).resolve().parents[2]
if str(_RAIZ_PAQUETE) not in sys.path:
    sys.path.insert(0, str(_RAIZ_PAQUETE))

from STM_RFPRMN_stmDL import stm_base  # noqa: E402
from STM_RFPRMN_stmDL.stm_base import advertir, informar  # noqa: E402
from STM_RFPRMN_stmDL.stm_comentarios import comentar_archivo  # noqa: E402
from STM_RFPRMN_stmDL.stm_entrenamiento import convertir_si_existe  # noqa: E402
from STM_RFPRMN_stmDL.stm_informe import generar_informe  # noqa: E402
from STM_RFPRMN_stmDL.stm_particion import partir_archivo  # noqa: E402
from STM_RFPRMN_stmDL.stm_pesos_ipfs import (  # noqa: E402
    cargar_historial, guardar_historial, sincronizar_al_iniciar, subir,
)
from STM_RFPRMN_stmDL.sbstm_mdl.sbrtstm.snrtstm_sbstm_agnt import (  # noqa: E402
    ACCIONES, COSTES, PESOS, TIEMPOS, AgenteRFPRMN as AgenteRFPRMNBase,
)

__all__ = ["ACCIONES", "COSTES", "PESOS", "TIEMPOS", "AgenteRFPRMN"]


class AgenteRFPRMN(AgenteRFPRMNBase):
    """Ejecuta comandos de RFPRMN decidiendo por utilidad, no por ``input()``.

    Hereda el análisis y la decisión de ``AgenteRFPRMNBase`` y añade la
    ejecución de acciones y el ciclo completo de trabajo.
    """

    class Ejecucion:
        """Ejecución de acciones con confirmación forzada y anotación."""

        @staticmethod
        def _con_politica(agente, valor: bool, funcion, *args, **kwargs):
            """Ejecuta algo con la confirmación forzada a ``valor``."""
            original = stm_base.pedir_confirmacion
            stm_base.pedir_confirmacion = lambda *_a, **_k: valor
            try:
                return funcion(*args, **kwargs)
            finally:
                stm_base.pedir_confirmacion = original

        @staticmethod
        def _anotar(agente, accion: str, ok: bool, utilidad: float,
                    motivo: str = "", calidad: float | None = None) -> None:
            """Anota el intento con su **calidad** (no solo si salió bien)."""
            peso = float(calidad) if calidad is not None else (1.0 if ok else 0.0)
            suma, intentos = agente.historial.get(accion, [0.0, 0])
            agente.historial[accion] = [suma + peso, intentos + 1]
            agente.registro.append({"accion": accion, "ok": ok,
                                    "utilidad": utilidad, "motivo": motivo,
                                    "calidad": peso})

        @staticmethod
        def ejecutar(agente, accion: str,
                     ruta: str | Path | None = None) -> bool:
            """Lanza una acción si la decisión matemática lo permite."""
            if accion not in ACCIONES:
                advertir(f"Acción desconocida: {accion}")
                return False
            permite, valor, motivo = agente.decidir(accion, ruta)
            if not permite:
                agente._anotar(accion, False, valor, motivo)
                return False
            agente._en_flujo = True
            agente.ultima_calidad = None
            try:
                resultado = agente._lanzar(accion, ruta, valor)
            except Exception as error:  # noqa: BLE001 - LucIA no debe caerse
                advertir(f"{accion} falló: {error}")
                resultado = False
            finally:
                agente._en_flujo = False
            agente._anotar(accion, bool(resultado), valor, "ejecutada",
                           agente.ultima_calidad)
            return bool(resultado)

        @staticmethod
        def _lanzar(agente, accion: str, ruta, valor: float) -> bool:
            """Ejecuta la acción concreta con la política de confirmación."""
            if accion == "presupuesto":
                from STM_RFPRMN_stmDL import verificar_presupuesto
                return bool(verificar_presupuesto().get("ok", False))
            if accion == "estado":
                from STM_RFPRMN_stmDL import modulos_estado
                return bool(modulos_estado())
            if accion == "probar":
                informe = agente.analizar(ruta)
                informar(f"{Path(str(ruta)).name}: {informe.get('puntuacion')}/100")
                return "error" not in informe
            if accion == "partir":
                return bool(agente._con_politica(True, partir_archivo,
                                                 ruta).get("partido"))
            if accion == "comentar":
                return bool(agente._con_politica(True, comentar_archivo, ruta))
            if accion == "informe":
                return generar_informe(ruta, con_ia=False) is not None
            if accion == "refactorizar":
                return bool(agente._con_politica(True, agente._refactorizar, ruta))
            if accion == "cerrar":
                return bool(agente._con_politica(True, agente._cerrar))
            return False

        @staticmethod
        def _refactorizar(agente, ruta) -> bool:
            """Lanza el flujo de refactor y devuelve también la nota de LucIA."""
            from STM_RFPRMN_stmDL.stm_flujo import FlujoRefactorLucIA
            origen = Path(str(ruta))
            contenido = origen.read_text(encoding="utf-8-sig")
            flujo = FlujoRefactorLucIA(
                origen, contenido,
                lambda texto, _analisis: f"Refactor de {origen.name}")
            resultado = flujo.ejecutar()
            if resultado:
                agente.ultima_calidad = getattr(flujo, "nota_final", None)
            return resultado

        @staticmethod
        def _cerrar(agente) -> bool:
            """Cierra la máquina: guarda el historial, sube los pesos y reparte."""
            from STM_RFPRMN_stmDL import repartir_carpeta
            guardar_historial(agente.historial)
            recibo = subir()
            if recibo.get("ok"):
                informar(f"Pesos en IPFS: {recibo.get('cid')} "
                         f"({', '.join(recibo.get('archivos', []))}).")
            else:
                advertir(f"Los pesos no se subieron a IPFS ({recibo.get('motivo')}).")
            repartir_carpeta()
            informar("LucIA cierra su máquina de comandos.")
            return True

    class Ciclo:
        """Ciclo completo: salud → probar → actuar → informe."""

        @staticmethod
        def ciclo(agente, rutas: list[str | Path]) -> dict:
            """Orden lógico: salud → probar → partir/refactorizar/comentar → informe."""
            resultados: list[dict] = []
            agente._inicio = time.monotonic()
            agente.pendientes = [str(ruta) for ruta in rutas]
            if not agente.ejecutar("presupuesto"):
                return {"acciones": resultados, "cerrado": False,
                        "motivo": "presupuesto en rojo"}
            agotado = False
            for ruta in rutas:
                if agente.restante() <= 0:
                    agotado = True
                    break
                analisis = agente.analizar(ruta)
                objetivos = []
                if int(analisis.get("lineas", 0) or 0) > agente.limite:
                    objetivos.append("partir")
                if (analisis.get("motivos")
                        and float(analisis.get("puntuacion", 0)) < 60):
                    objetivos.append("refactorizar")
                if any("docstring" in str(motivo)
                       for motivo, _ in analisis.get("motivos", [])):
                    objetivos.append("comentar")
                objetivos.append("informe")
                for accion in objetivos:
                    ok = agente.ejecutar(accion, ruta)
                    resultados.append({"ruta": str(ruta), "accion": accion,
                                       "ok": ok})
                convertir_si_existe(
                    Path(str(ruta)).parent / f"informe_{Path(str(ruta)).stem}.md")
                if str(ruta) in agente.pendientes:
                    agente.pendientes.remove(str(ruta))
            cerrar, valor, motivo = agente.desea_cerrar()
            if cerrar:
                agente.cerrar_si_procede()
            return {"acciones": resultados, "cerrado": cerrar,
                    "puntuacion_cierre": valor, "motivo": motivo,
                    "agotado": agotado, "restante": round(agente.restante(), 1)}

    def __init__(self, umbral: float = 0.55, umbral_cierre: float = 0.20,
                 limite: int = 450, presupuesto_segundos: float = 300.0) -> None:
        self.umbral = float(umbral)
        self.umbral_cierre = float(umbral_cierre)
        self.limite = int(limite)
        self.presupuesto_tiempo = float(presupuesto_segundos)
        self._inicio = 0.0
        self.historial: dict[str, list[float]] = cargar_historial()
        self.ultima_calidad: float | None = None
        self.registro: list[dict] = []
        self.pendientes: list[str] = []
        self._en_flujo = False
        self._decision: bool = False
        # Al iniciar: si no hay pesos locales, se intentan traer de IPFS.
        sincronizar_al_iniciar()

    # API de esta mitad: alias directos, sin capa extra de llamada.
    _con_politica = Ejecucion._con_politica
    _anotar = Ejecucion._anotar
    ejecutar = Ejecucion.ejecutar
    _lanzar = Ejecucion._lanzar
    _refactorizar = Ejecucion._refactorizar
    _cerrar = Ejecucion._cerrar
    ciclo = Ciclo.ciclo


if __name__ == "__main__":
    # Ejecución directa (F5 / python sbstm_agnt.py): confirma que carga.
    print(f"sbstm_agnt OK · {AgenteRFPRMN.__name__} · "
          f"{len(ACCIONES)} acciones")
