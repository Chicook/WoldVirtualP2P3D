"""Pruebas del paquete ``STMIPFS.nodo`` (IPFS activado por código).

No necesita daemon: lo que se prueba es la lógica de rutas, empaquetado,
verificación y las respuestas honestas cuando falta el nodo.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "TLLDCD" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from STMIPFS.nodo import ErrorIPFS, NodoIPFS  # noqa: E402
from STMIPFS.nodo import binario, cliente, daemon, pesos, repositorio, rutas  # noqa: E402


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Aísla binario, repositorio y datos, y simula un nodo apagado.

    Sin este parche las pruebas dependerían de si hay un daemon real en el
    5001 de la máquina, que es justo lo que no se quiere.
    """
    monkeypatch.setenv("WOLD_IPFS_BIN", str(tmp_path / "ipfs.exe"))
    monkeypatch.setenv("IPFS_PATH", str(tmp_path / "repo"))
    monkeypatch.setenv("WOLD_IPFS_DATOS", str(tmp_path / "datos"))
    monkeypatch.setattr(cliente, "disponible", lambda *_a, **_k: False)
    monkeypatch.setattr(binario, "descargar",
                        lambda *_a, **_k: {"ok": False,
                                           "motivo": "descarga desactivada en pruebas"})
    return tmp_path


# --- Rutas -------------------------------------------------------------------

def test_las_rutas_salen_del_entorno(entorno):
    assert rutas.ruta_binario() == entorno / "ipfs.exe"
    assert rutas.dir_repo() == entorno / "repo"
    assert rutas.dir_datos() == entorno / "datos"


def test_describir_dice_si_existe(entorno):
    datos = rutas.describir()
    assert datos["binario_existe"] is False
    assert datos["repo_existe"] is False


# --- Cliente -----------------------------------------------------------------

def test_la_url_del_api_se_puede_cambiar(monkeypatch):
    monkeypatch.setenv("WOLD_IPFS_API", "http://127.0.0.1:9999/")
    assert cliente.api_url() == "http://127.0.0.1:9999"


def test_un_cid_invalido_se_rechaza():
    with pytest.raises(ErrorIPFS):
        cliente.leer("../etc/passwd")


# --- Repositorio -------------------------------------------------------------

def test_repositorio_sin_config_no_esta_inicializado(entorno):
    assert repositorio.inicializado() is False
    assert repositorio.estado()["inicializado"] is False


def test_repositorio_con_config_se_detecta(entorno):
    (entorno / "repo").mkdir()
    (entorno / "repo" / "config").write_text("{}", encoding="utf-8")
    (entorno / "repo" / "version").write_text("16", encoding="utf-8")
    assert repositorio.inicializado() is True
    assert repositorio.estado()["version"] == "16"


def test_inicializar_sin_binario_falla_con_motivo(entorno):
    resultado = repositorio.inicializar()
    assert resultado["ok"] is False and "binario" in resultado["motivo"]


def test_no_se_limpia_un_bloqueo_recien_creado(entorno):
    (entorno / "repo").mkdir()
    (entorno / "repo" / "repo.lock").write_text("x", encoding="utf-8")
    assert repositorio.limpiar_bloqueos()["limpiado"] is False


# --- Binario y daemon --------------------------------------------------------

def test_sin_binario_el_estado_lo_dice(entorno):
    assert binario.estado()["existe"] is False
    assert binario.version_instalada() == "Desconocida"


def test_el_daemon_no_arranca_sin_binario(entorno):
    resultado = daemon.arrancar(esperar=1)
    assert resultado["ok"] is False and "binario" in resultado["motivo"]


def test_el_nodo_sin_binario_falla_en_el_primer_paso(entorno):
    resultado = NodoIPFS(descargar=False).asegurar()
    assert resultado["ok"] is False and resultado["paso"] == "binario"


# --- Pesos -------------------------------------------------------------------

def _archivos(tmp_path: Path) -> list[Path]:
    carpeta = tmp_path / "pesos"
    carpeta.mkdir(exist_ok=True)
    (carpeta / "lucia_rn_31x1.pkl").write_bytes(b"\x80\x04binario")
    (carpeta / "agente.json").write_text('{"informe": [0.9, 2]}', encoding="utf-8")
    return sorted(carpeta.glob("*"))


def test_empaquetar_mete_los_archivos_y_el_indice(tmp_path):
    datos, nombres = pesos.empaquetar(_archivos(tmp_path))
    assert nombres == ["agente.json", "lucia_rn_31x1.pkl"]
    with zipfile.ZipFile(io.BytesIO(datos)) as paquete:
        assert paquete.read("lucia_rn_31x1.pkl") == b"\x80\x04binario"
        indice = json.loads(paquete.read(pesos.INDICE))
        assert indice["sha256"]["agente.json"]


def test_sin_daemon_publicar_no_inventa_cid(entorno, tmp_path):
    resultado = pesos.publicar(_archivos(tmp_path))
    assert resultado["ok"] is False and "no está activo" in resultado["motivo"]
    assert "cid" not in resultado
    assert Path(resultado["paquete"]).is_file()


def test_publicar_guarda_el_puntero_con_cid(entorno, tmp_path, monkeypatch):
    monkeypatch.setattr(cliente, "disponible", lambda *_a, **_k: True)
    monkeypatch.setattr(cliente, "agregar", lambda *_a, **_k: "QmPrueba")
    resultado = pesos.publicar(_archivos(tmp_path), nombre="p.zip")
    assert resultado["ok"] is True and resultado["cid"] == "QmPrueba"
    puntero = json.loads(rutas.ruta_puntero().read_text(encoding="utf-8"))
    assert puntero["cid"] == "QmPrueba"
    assert len(puntero["sha256"]) == 64


def test_recuperar_sin_cid_no_hace_nada(entorno):
    assert pesos.recuperar()["ok"] is False


def test_recuperar_verifica_y_restaura(entorno, tmp_path, monkeypatch):
    datos, _nombres = pesos.empaquetar(_archivos(tmp_path))
    puntero = {"cid": "QmPrueba", "sha256": hashlib.sha256(datos).hexdigest()}
    rutas.ruta_puntero().parent.mkdir(parents=True, exist_ok=True)
    rutas.ruta_puntero().write_text(json.dumps(puntero), encoding="utf-8")
    monkeypatch.setattr(cliente, "disponible", lambda *_a, **_k: True)
    monkeypatch.setattr(cliente, "leer", lambda *_a, **_k: datos)
    destino = tmp_path / "restaurado"
    resultado = pesos.recuperar(destino=destino)
    assert resultado["ok"] is True
    assert (destino / "lucia_rn_31x1.pkl").read_bytes() == b"\x80\x04binario"


def test_recuperar_rechaza_si_el_sha_no_coincide(entorno, tmp_path, monkeypatch):
    rutas.ruta_puntero().parent.mkdir(parents=True, exist_ok=True)
    rutas.ruta_puntero().write_text(
        json.dumps({"cid": "QmPrueba", "sha256": "0" * 64}), encoding="utf-8")
    monkeypatch.setattr(cliente, "disponible", lambda *_a, **_k: True)
    monkeypatch.setattr(cliente, "leer", lambda *_a, **_k: b"otra cosa")
    resultado = pesos.recuperar()
    assert resultado["ok"] is False and "SHA-256" in resultado["motivo"]


def test_estado_del_nodo_incluye_las_piezas(entorno):
    datos = NodoIPFS().estado()
    assert set(datos) == {"rutas", "binario", "repositorio", "daemon", "pesos", "listo"}
    assert datos["listo"] is False
