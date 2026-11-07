"""Orquestador del subsistema defensivo STM_DEF.

Reune las cuatro capacidades (detecta, vigila, sella y blinda) en una sola
pasada y produce un informe homogeneo. Es el punto de entrada que usan la
consola ``__main__`` y las pruebas.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

from . import SRC_DIR, blindaje, cuarentena, deteccion, historial, integridad, iocs, monitor
from .modelos import ALTA, PESO_SEVERIDAD, Alerta, Informe, clasificar


class MotorDefensa:
    """Coordina deteccion estatica, monitor de red, sello y blindaje."""

    def __init__(self, raices: Optional[Iterable[Path]] = None) -> None:
        self.raices: List[Path] = [Path(r) for r in (raices if raices is not None else [SRC_DIR])]

    # ------------------------------------------------------------ capacidades
    def escanear(self, raices: Optional[Iterable[Path]] = None) -> Informe:
        """Barrido estatico del arbol buscando el patron del dropper."""
        objetivo = [Path(r) for r in raices] if raices is not None else self.raices
        hallazgos = deteccion.escanear_arbol(objetivo)
        resumen = deteccion.resumen(hallazgos)
        return Informe(hallazgos=hallazgos, resumen={"deteccion": resumen})

    def escanear_historial(self, limite: int = 200) -> Informe:
        """Busca en el historial Git las introducciones del dropper (commit pasado)."""
        hallazgos = historial.escanear_historial(limite=limite)
        return Informe(hallazgos=hallazgos, resumen={"historial": historial.resumen(hallazgos)})

    def vigilar(self, resolver: bool = False, ciclos: int = 1, intervalo: float = 60.0) -> Informe:
        """Pasada del monitor de red: conexiones salientes y procesos."""
        alertas = monitor.vigilar(ciclos=ciclos, intervalo=intervalo, resolver=resolver)
        puntos = sum(PESO_SEVERIDAD.get(alerta.severidad, 0) for alerta in alertas)
        return Informe(alertas=alertas, resumen={"red": {"alertas": len(alertas), "veredicto": clasificar(puntos)}})

    def sellar(self) -> Dict[str, object]:
        """Calcula y guarda el sello de integridad firmado."""
        sello = integridad.construir_sello()
        ruta = integridad.guardar_sello(sello)
        return {"ruta": str(ruta), "ficheros": len(sello.get("ficheros", {})), "fecha": sello.get("fecha")}

    def verificar_integridad(self) -> Dict[str, object]:
        """Comprueba el sello guardado contra el arbol real."""
        return integridad.verificar_sello()

    def blindar(self, aplicar: bool = False) -> Dict[str, object]:
        """Sinkhole DNS + firewall de salida (simulado salvo ``aplicar=True``)."""
        return blindaje.blindar(aplicar)

    def poner_en_cuarentena(self, ruta: Path, motivo: str = "") -> Dict[str, object]:
        """Copia una muestra a la cuarentena firmada (nunca borra el original)."""
        return cuarentena.poner_en_cuarentena(ruta, motivo=motivo)

    def listar_cuarentena(self) -> List[Dict[str, object]]:
        """Registros del manifiesto de cuarentena."""
        return cuarentena.listar()

    def verificar_cuarentena(self) -> Dict[str, object]:
        """Integridad de las copias frente a su SHA-256 registrado."""
        return cuarentena.verificar()

    # ------------------------------------------------------- puerta de seguridad
    def puerta_seguridad(self, raices: Optional[Iterable[Path]] = None) -> Dict[str, object]:
        """Puerta bloqueante para CI: escaneo + integridad + cuarentena.

        Devuelve ``bloquea=True`` (y el motivo) si el arbol no es de fiar. Es el
        unico punto que un paso de CI necesita invocar; su criterio de salida es
        *fail-closed* para lo verificable: un hallazgo ALTA, un sello de
        integridad manipulado o una cuarentena alterada bloquean el paso.
        """
        objetivo = [Path(r) for r in raices] if raices is not None else self.raices
        bloqueos: List[str] = []
        detalle: Dict[str, object] = {}

        hallazgos = deteccion.escanear_arbol(objetivo)
        por_severidad: Dict[str, int] = {}
        for hallazgo in hallazgos:
            por_severidad[hallazgo.severidad] = por_severidad.get(hallazgo.severidad, 0) + 1
        resumen_escaneo = deteccion.resumen(hallazgos)
        detalle["escanear"] = {
            "hallazgos": len(hallazgos),
            "por_severidad": por_severidad,
            "veredicto": resumen_escaneo["veredicto"],
        }
        if por_severidad.get(ALTA):
            bloqueos.append(f"{por_severidad[ALTA]} hallazgo(s) ALTA en el escaneo")

        bloqueos_integridad, detalle_integridad = integridad.bloqueos_sello(integridad.SELLO_PATH)
        detalle["integridad"] = detalle_integridad
        bloqueos.extend(bloqueos_integridad)

        estado_cuarentena = cuarentena.verificar()
        detalle["cuarentena"] = estado_cuarentena
        if not estado_cuarentena.get("intacto"):
            bloqueos.append("cuarentena alterada o con copias ausentes")

        return {"bloquea": bool(bloqueos), "bloqueos": bloqueos, "detalle": detalle}

    def estado(self) -> Dict[str, object]:
        """Estado combinado del blindaje y de los indicadores."""
        return {"blindaje": blindaje.estado(), "iocs": _resumen_iocs()}

    # --------------------------------------------------------- informe global
    def informe(self, escanear: bool = True, vigilar: bool = True, resolver: bool = False) -> Informe:
        """Pasada completa: detecta, vigila, verifica integridad y resume."""
        informe = Informe()
        if escanear:
            informe.extension(self.escanear())
        if vigilar:
            informe.extension(self.vigilar(resolver=resolver))
        estado_integridad = self.verificar_integridad()
        informe.resumen.update({
            "integridad": estado_integridad,
            "blindaje_activo": bool(blindaje.estado().get("sinkhole_dns_activo")),
            "veredicto": informe.veredicto(),
            "puntos": informe.puntos(),
            "hallazgos": len(informe.hallazgos),
            "alertas": len(informe.alertas),
        })
        return informe


def _resumen_iocs() -> Dict[str, object]:
    """Recuento de la base de indicadores cargada."""
    return {
        "patrones": len(iocs.PATRONES),
        "patrones_comando": len(iocs.PATRONES_COMANDO),
        "dominios_c2": len(iocs.DOMINIOS_C2),
        "sufijos_rpc": len(iocs.SUFIJOS_RPC),
        "carteras": len(iocs.DIRECCIONES_C2),
        "dominios_extra": len(iocs.DOMINIOS_EXTRA),
    }


def alerta_a_diccionario(alerta: Alerta) -> Dict[str, object]:
    """Vista serializable de una alerta de red (para ``--json``)."""
    return {
        "severidad": alerta.severidad, "motivo": alerta.motivo, "detalle": alerta.detalle,
        "destino": alerta.conexion.destino() if alerta.conexion else "",
        "proceso": alerta.conexion.proceso if alerta.conexion else "",
        "pid": alerta.conexion.pid if alerta.conexion else 0,
    }


def informe_a_diccionario(informe: Informe) -> Dict[str, object]:
    """Vista serializable de un informe (para ``--json``)."""
    return {
        "resumen": informe.resumen,
        "hallazgos": [
            {"id": h.id, "severidad": h.severidad, "origen": h.origen, "linea": h.linea,
             "repeticiones": h.repeticiones, "descripcion": h.descripcion, "fragmento": h.fragmento}
            for h in informe.hallazgos
        ],
        "alertas": [alerta_a_diccionario(a) for a in informe.alertas],
        "veredicto": informe.veredicto(),
        "puntos": informe.puntos(),
    }


__all__ = ["MotorDefensa", "informe_a_diccionario", "alerta_a_diccionario"]
