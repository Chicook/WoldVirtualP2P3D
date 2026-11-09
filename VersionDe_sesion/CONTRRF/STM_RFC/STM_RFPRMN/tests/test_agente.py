"""Pruebas del agente que permite a LucIA usar los comandos sin humano."""
from __future__ import annotations

import pytest

from STM_RFPRMN_stmDL import stm_agente, stm_base
from STM_RFPRMN_stmDL.stm_agente import AgenteRFPRMN


@pytest.fixture(autouse=True)
def _integridad(monkeypatch):
    """El autoanálisis en verde salvo que la prueba diga lo contrario."""
    monkeypatch.setattr(AgenteRFPRMN, "autoanalisis",
                        lambda self: {"ok": True, "problemas": []})
    yield


# --- Matemática de la decisión ----------------------------------------------

def test_un_archivo_sano_no_merece_accion():
    agente = AgenteRFPRMN()
    valor, senales = agente.utilidad("informe", {"puntuacion": 100, "lineas": 10})
    assert valor < 0.55
    assert senales["deficit"] == 0.0 and senales["urgencia"] == 0.0


def test_un_archivo_con_deuda_y_largo_si_la_merece():
    agente = AgenteRFPRMN()
    valor, senales = agente.utilidad("informe", {"puntuacion": 40, "lineas": 500})
    assert valor >= 0.55
    assert senales["deficit"] == 0.6 and senales["urgencia"] == 1.0


def test_la_urgencia_escalona_por_tamano():
    agente = AgenteRFPRMN(limite=450)
    assert agente.urgencia({"lineas": 100}) == 0.0
    assert agente.urgencia({"lineas": 320}) == 0.5
    assert agente.urgencia({"lineas": 500}) == 1.0


def test_el_exito_previo_empieza_en_medio_y_se_actualiza():
    agente = AgenteRFPRMN()
    assert agente.exito_previo("informe") == 0.5
    agente._anotar("informe", True, 0.7)
    agente._anotar("informe", True, 0.7)
    assert agente.exito_previo("informe") == 1.0
    agente._anotar("informe", False, 0.7)
    assert agente.exito_previo("informe") == pytest.approx(2 / 3)


def test_una_accion_cara_necesita_mas_motivo_que_una_barata():
    agente = AgenteRFPRMN()
    contexto = {"puntuacion": 70, "lineas": 100}
    barata, _ = agente.utilidad("probar", contexto)
    cara, _ = agente.utilidad("refactorizar", contexto)
    assert barata > cara


# --- Decisión ----------------------------------------------------------------

def test_decidir_respeta_el_umbral():
    agente = AgenteRFPRMN(umbral=0.60)
    si, valor, motivo = agente.decidir("informe", {"puntuacion": 20, "lineas": 480})
    assert si is True and valor >= 0.60 and "suficiente" in motivo
    no, valor, motivo = agente.decidir("informe", {"puntuacion": 100, "lineas": 5})
    assert no is False and "umbral" in motivo


def test_si_el_autoanalisis_falla_no_se_actua(monkeypatch):
    monkeypatch.setattr(AgenteRFPRMN, "autoanalisis",
                        lambda self: {"ok": False, "problemas": ["presupuesto en rojo"]})
    agente = AgenteRFPRMN()
    si, _valor, motivo = agente.decidir("refactorizar", {"puntuacion": 10, "lineas": 900})
    assert si is False and "autoanálisis" in motivo


def test_desea_cerrar_sin_trabajo():
    agente = AgenteRFPRMN()
    cerrar, valor, motivo = agente.desea_cerrar()
    assert cerrar is True and valor == 1.0 and "pendiente" in motivo


def test_no_cierra_con_un_flujo_abierto():
    agente = AgenteRFPRMN()
    agente._en_flujo = True
    assert agente.desea_cerrar()[0] is False


def test_no_cierra_si_queda_trabajo(tmp_path):
    agente = AgenteRFPRMN(umbral_cierre=0.20)
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(agente, "analizar",
                            lambda _ruta: {"puntuacion": 10, "lineas": 900})
        agente.pendientes = [str(tmp_path / "pendiente.py")]
        cerrar, _valor, motivo = agente.desea_cerrar()
        assert cerrar is False and "queda trabajo" in motivo
    finally:
        monkeypatch.undo()


# --- Ejecución ---------------------------------------------------------------

def test_una_accion_desconocida_no_se_lanza():
    agente = AgenteRFPRMN()
    assert agente.ejecutar("borrar_todo") is False


def test_la_politica_fuerza_la_confirmacion_y_la_restaura():
    agente = AgenteRFPRMN()
    original = stm_base.pedir_confirmacion
    visto: list[bool] = []

    def _accion():
        visto.append(stm_base.pedir_confirmacion("¿sí?"))
        return True

    assert agente._con_politica(True, _accion) is True
    assert visto == [True]
    assert stm_base.pedir_confirmacion is original


def test_probar_usa_el_diagnostico(tmp_path):
    archivo = tmp_path / "x.py"
    archivo.write_text("def f():\n    return 1\n", encoding="utf-8")
    agente = AgenteRFPRMN(umbral=0.0)
    assert agente.ejecutar("probar", archivo) is True
    assert agente.registro[-1]["accion"] == "probar"


def test_si_una_accion_falla_no_rompe_al_agente(tmp_path, monkeypatch):
    def _explotar(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(stm_agente, "partir_archivo", _explotar)
    agente = AgenteRFPRMN()
    assert agente.ejecutar("partir", tmp_path / "x.py") is False
    assert agente.registro[-1]["ok"] is False


def test_cerrar_pasa_por_la_politica(tmp_path, monkeypatch):
    llamadas: list[str] = []
    monkeypatch.setattr(stm_agente, "partir_archivo", lambda *a, **k: {"partido": True})
    agente = AgenteRFPRMN(umbral=0.0)
    agente._cerrar = lambda: llamadas.append("cerrado") or True
    agente._lanzar = lambda accion, ruta, valor: agente._cerrar()
    assert agente.ejecutar("cerrar") is True
    assert llamadas == ["cerrado"]


def test_cerrar_si_procede_no_usa_el_umbral_normal(monkeypatch):
    agente = AgenteRFPRMN(umbral=0.99)  # inalcanzable para la utilidad
    monkeypatch.setattr(agente, "_lanzar", lambda *_a, **_k: True)
    assert agente.cerrar_si_procede() is True
    assert agente.registro[-1]["accion"] == "cerrar"


def test_cerrar_si_procede_respeta_el_trabajo_pendiente(tmp_path, monkeypatch):
    agente = AgenteRFPRMN(umbral_cierre=0.20)
    monkeypatch.setattr(agente, "_lanzar", lambda *_a, **_k: True)
    monkeypatch.setattr(agente, "analizar",
                        lambda _ruta: {"puntuacion": 5, "lineas": 900})
    agente.pendientes = [str(tmp_path / "x.py")]
    assert agente.cerrar_si_procede() is False


# --- Quinta señal: la predicción de la red -----------------------------------

def test_senal_red_sin_memoria_es_neutra(monkeypatch):
    from STM_RFPRMN_stmDL import stm_seq2seq

    monkeypatch.setattr(stm_seq2seq, "generar", lambda _texto: None)
    monkeypatch.setattr(stm_seq2seq, "estado", lambda: {"pares": 0})
    agente = AgenteRFPRMN()
    assert agente.senal_red("codigo", pasos=8) == 0.5


def test_senal_red_con_refactor_memorizado_sube(monkeypatch):
    from STM_RFPRMN_stmDL import stm_seq2seq

    monkeypatch.setattr(stm_seq2seq, "generar", lambda _texto: "def f(): pass")
    agente = AgenteRFPRMN()
    assert agente.senal_red("codigo", pasos=8) == pytest.approx(0.9)


def test_senal_red_se_encoge_con_pocos_pasos(monkeypatch):
    from STM_RFPRMN_stmDL import stm_seq2seq

    monkeypatch.setattr(stm_seq2seq, "generar", lambda _texto: "algo")
    agente = AgenteRFPRMN()
    assert agente.senal_red("codigo", pasos=0) == 0.5
    assert agente.senal_red("codigo", pasos=4) == pytest.approx(0.7)


def test_la_utilidad_incluye_la_red():
    agente = AgenteRFPRMN()
    sin_red, senales_neutras = agente.utilidad("informe", {"puntuacion": 60, "lineas": 100}, red=0.5)
    con_red, senales_altas = agente.utilidad("informe", {"puntuacion": 60, "lineas": 100}, red=1.0)
    assert senales_neutras["red"] == 0.5 and senales_altas["red"] == 1.0
    assert con_red > sin_red


# --- Presupuesto de tiempo ---------------------------------------------------

def test_el_tiempo_crece_con_el_tamano():
    agente = AgenteRFPRMN()
    assert agente.estimar_tiempo("refactorizar", {"lineas": 10}) == 40.0
    assert agente.estimar_tiempo("refactorizar", {"lineas": 600}) == 400.0
    assert agente.estimar_tiempo("comentar", {"lineas": 100}) == 40.0
    assert agente.estimar_tiempo("probar", {"lineas": 100}) == 2.0


def test_decidir_rechaza_lo_que_no_cabe_en_el_presupuesto(monkeypatch):
    monkeypatch.setattr(AgenteRFPRMN, "autoanalisis",
                        lambda self: {"ok": True, "problemas": []})
    agente = AgenteRFPRMN(umbral=0.0, presupuesto_segundos=10.0)
    si, _valor, motivo = agente.decidir("refactorizar", {"puntuacion": 10, "lineas": 600})
    assert si is False and "presupuesto" in motivo


def test_restante_descuenta_el_tiempo_corrido():
    import time as _time

    agente = AgenteRFPRMN(presupuesto_segundos=100.0)
    agente._inicio = _time.monotonic() - 40.0
    assert 55.0 <= agente.restante() <= 60.0


def test_el_ciclo_marca_agotado_sin_presupuesto(monkeypatch):
    agente = AgenteRFPRMN(presupuesto_segundos=0.0)
    monkeypatch.setattr(agente, "ejecutar", lambda accion, ruta=None: True)
    monkeypatch.setattr(agente, "decidir", lambda *_a, **_k: (True, 1.0, "ok"))
    monkeypatch.setattr(agente, "analizar",
                        lambda _ruta: {"puntuacion": 100, "lineas": 10, "motivos": []})
    resultado = agente.ciclo(["x.py"])
    assert resultado["agotado"] is True


# --- Ciclo -------------------------------------------------------------------

def test_el_ciclo_no_actua_si_el_presupuesto_esta_en_rojo(monkeypatch):
    monkeypatch.setattr(AgenteRFPRMN, "ejecutar",
                        lambda self, accion, ruta=None: accion != "presupuesto")
    agente = AgenteRFPRMN()
    resultado = agente.ciclo(["x.py"])
    assert resultado["cerrado"] is False
    assert "presupuesto" in resultado["motivo"]


def test_el_ciclo_decide_por_archivo(tmp_path, monkeypatch):
    lanzadas: list[tuple[str, str]] = []
    monkeypatch.setattr(stm_agente, "convertir_si_existe", lambda *_a: None)
    agente = AgenteRFPRMN()

    def _decidir(_accion, _ruta=None):
        return True, 0.9, "ok"

    def _ejecutar(accion, ruta=None):
        lanzadas.append((accion, str(ruta)))
        if accion == "presupuesto":
            return True
        agente._anotar(accion, True, 0.9)
        return True

    monkeypatch.setattr(agente, "decidir", _decidir)
    monkeypatch.setattr(agente, "ejecutar", _ejecutar)
    monkeypatch.setattr(agente, "analizar",
                        lambda _ruta: {"puntuacion": 40, "lineas": 500,
                                       "motivos": [("3 funciones sin docstring", 5)]})
    resultado = agente.ciclo([tmp_path / "x.py"])
    acciones = [accion for accion, _ in lanzadas]
    assert acciones[0] == "presupuesto"
    assert "partir" in acciones and "refactorizar" in acciones
    assert "comentar" in acciones and "informe" in acciones
    assert resultado["cerrado"] is True


def test_el_ciclo_cierra_cuando_no_queda_nada(monkeypatch):
    monkeypatch.setattr(AgenteRFPRMN, "autoanalisis",
                        lambda self: {"ok": True, "problemas": []})
    agente = AgenteRFPRMN()
    monkeypatch.setattr(agente, "ejecutar", lambda accion, ruta=None: True)
    monkeypatch.setattr(agente, "analizar",
                        lambda _ruta: {"puntuacion": 100, "lineas": 10, "motivos": []})
    resultado = agente.ciclo([])
    assert resultado["cerrado"] is True
