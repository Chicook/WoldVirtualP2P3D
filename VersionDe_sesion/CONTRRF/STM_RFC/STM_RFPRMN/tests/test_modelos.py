"""Pruebas de la política de modelos (R3/R4/R6 de la discusión #84)."""
from __future__ import annotations

import json

import pytest

from STM_RFPRMN_stmDL import stm_modelos


# --- Registro de modelos usados ---------------------------------------------

def test_lee_las_cabeceras_del_registro(tmp_path, monkeypatch):
    registro = tmp_path / "registro_refactor.md"
    registro.write_text(
        "## a.py — qwen2.5-coder:7b\n"
        "Fecha: 2026-11-08T12:50:52\n"
        "Descripción del modelo: usé qwen2.5-coder:7b a las 12:50.\n",
        encoding="utf-8")
    monkeypatch.setattr(stm_modelos, "REGISTRO_REFACTOR_MD", registro)
    assert stm_modelos._modelos_usados_registro() == {"qwen2.5-coder:7b"}


def test_ignora_marcas_de_tiempo_sueltas(tmp_path, monkeypatch):
    registro = tmp_path / "registro_refactor.md"
    registro.write_text("Fecha: 2026-11-08T12:50:52\nsin cabeceras\n",
                        encoding="utf-8")
    monkeypatch.setattr(stm_modelos, "REGISTRO_REFACTOR_MD", registro)
    assert stm_modelos._modelos_usados_registro() == set()


def test_sin_registro_no_hay_modelos_usados(tmp_path, monkeypatch):
    monkeypatch.setattr(stm_modelos, "REGISTRO_REFACTOR_MD",
                        tmp_path / "no-existe.md")
    monkeypatch.setattr(stm_modelos, "SRC_DIR", tmp_path / "src")
    assert stm_modelos._modelos_usados_registro() == set()


def test_el_registro_heredado_sigue_leyendose(tmp_path, monkeypatch):
    heredado = tmp_path / "src" / "STM_IA" / "modelosIAlocal" / "registro_refactor.md"
    heredado.parent.mkdir(parents=True)
    heredado.write_text("## b.py — starcoder2:7b\n", encoding="utf-8")
    monkeypatch.setattr(stm_modelos, "REGISTRO_REFACTOR_MD",
                        tmp_path / "nuevo.md")
    monkeypatch.setattr(stm_modelos, "SRC_DIR", tmp_path / "src")
    assert stm_modelos._ruta_registro_refactor() == heredado
    assert stm_modelos._modelos_usados_registro() == {"starcoder2:7b"}


def test_los_pesos_se_borran_solo_de_su_carpeta(tmp_path, monkeypatch):
    monkeypatch.setattr(stm_modelos, "DIR_MODELOS_LOCAL", tmp_path / "pesos")
    (tmp_path / "pesos").mkdir()
    (tmp_path / "pesos" / "modelo.gguf").write_bytes(b"GGUF")
    stm_modelos._borrar_peso_local()
    assert not (tmp_path / "pesos").exists()


def test_no_borra_pesos_si_la_ruta_apunta_a_rfc(monkeypatch):
    """R1/R2: aunque alguien configure la ruta mal, no se borra dentro de RFC."""
    from STM_RFPRMN_stmDL import stm_rutas
    monkeypatch.setattr(stm_modelos, "DIR_MODELOS_LOCAL",
                        stm_rutas.RFC_DIR / "src" / "modelos")
    stm_modelos._borrar_peso_local()  # no debe lanzar ni borrar nada


# --- Política por defecto ----------------------------------------------------

def test_consumir_modelos_es_falso_por_defecto(monkeypatch):
    monkeypatch.delenv("RFPRMN_CONSUMIR_MODELOS", raising=False)
    from STM_RFPRMN_stmDL.stm_flujo import consumir_modelos_por_entorno
    assert consumir_modelos_por_entorno() is False


def test_consumir_modelos_por_entorno(monkeypatch):
    from STM_RFPRMN_stmDL.stm_flujo import consumir_modelos_por_entorno
    monkeypatch.setenv("RFPRMN_CONSUMIR_MODELOS", "1")
    assert consumir_modelos_por_entorno() is True
    monkeypatch.setenv("RFPRMN_CONSUMIR_MODELOS", "0")
    assert consumir_modelos_por_entorno() is False


def test_el_flujo_no_borra_nada_por_defecto(tmp_path, monkeypatch):
    from STM_RFPRMN_stmDL.stm_flujo import FlujoRefactorLucIA
    monkeypatch.delenv("RFPRMN_CONSUMIR_MODELOS", raising=False)
    archivo = tmp_path / "ejemplo.py"
    archivo.write_text("def a():\n    return 1\n", encoding="utf-8")
    flujo = FlujoRefactorLucIA(archivo, archivo.read_text(encoding="utf-8"))
    assert flujo.consumir_modelos is False


# --- Siempre el modelo más ligero (R6) ---------------------------------------

def test_tamano_modelo_lee_los_parametros():
    assert stm_modelos.tamano_modelo("qwen2.5-coder:1.5b") == 1.5
    assert stm_modelos.tamano_modelo("qwen2.5-coder:7b") == 7.0
    assert stm_modelos.tamano_modelo("modelo-desconocido") > 7.0


def test_ordenar_por_tamano_es_ascendente():
    orden = stm_modelos.ordenar_por_tamano(
        ["qwen2.5-coder:7b", "qwen2.5-coder:1.5b", "qwen2.5-coder:3b"])
    assert orden == ["qwen2.5-coder:1.5b", "qwen2.5-coder:3b", "qwen2.5-coder:7b"]


def test_los_candidatos_quedan_el_mas_ligero_por_familia(tmp_path, monkeypatch):
    config = tmp_path / "IAlocal.json"
    config.write_text(json.dumps({"models_available": [
        "qwen2.5-coder:7b", "qwen2.5-coder:3b", "qwen2.5-coder:latest"]}),
        encoding="utf-8")
    monkeypatch.setattr(stm_modelos, "ruta_config_ia_local", lambda: config)
    candidatos = stm_modelos._leer_candidatos_codigo()
    assert candidatos[0] == "qwen2.5-coder:3b"
    assert "qwen2.5-coder:7b" not in candidatos


def test_se_reutiliza_la_etiqueta_instalada_de_la_familia(monkeypatch):
    monkeypatch.setattr(stm_modelos, "_candidatos_disponibles",
                        lambda: ["qwen2.5-coder:3b"])
    monkeypatch.setattr(stm_modelos, "_modelos_ollama_instalados",
                        lambda: {"qwen2.5-coder:7b", "qwen2.5-coder"})
    monkeypatch.setattr(stm_modelos, "_cargar_configuracion_ia_local",
                        lambda: ("http://localhost:11434", "x"))
    monkeypatch.setattr(stm_modelos, "_modelos_usados_registro", lambda: set())
    assert stm_modelos._asegurar_modelo_codigo() == "qwen2.5-coder:7b"


def test_se_descarga_el_mas_ligero_si_no_hay_instalado(monkeypatch):
    monkeypatch.setattr(stm_modelos, "_candidatos_disponibles",
                        lambda: ["qwen2.5-coder:7b", "qwen2.5-coder:1.5b"])
    monkeypatch.setattr(stm_modelos, "_modelos_ollama_instalados", lambda: set())
    monkeypatch.setattr(stm_modelos, "_cargar_configuracion_ia_local",
                        lambda: ("http://localhost:11434", "x"))
    monkeypatch.setattr(stm_modelos, "_modelos_usados_registro", lambda: set())
    monkeypatch.setattr(stm_modelos, "_ram_gb", lambda: 16.0)
    descargados: list[str] = []

    def _descargar(_endpoint, modelo):
        descargados.append(modelo)
        return True

    monkeypatch.setattr(stm_modelos, "_descargar_modelo_ollama", _descargar)
    assert stm_modelos._asegurar_modelo_codigo() == "qwen2.5-coder:1.5b"
    assert descargados == ["qwen2.5-coder:1.5b"]


def test_con_poca_ram_no_se_baja_un_7b(monkeypatch):
    monkeypatch.setattr(stm_modelos, "_ram_gb", lambda: 4.0)
    assert stm_modelos._elegir_para_descargar(
        ["qwen2.5-coder:7b", "qwen2.5-coder:3b"]) == "qwen2.5-coder:3b"


# --- R6: el GGUF se registra en Ollama ---------------------------------------

class _Proceso:
    def __init__(self, returncode: int, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = ""
        self.stderr = stderr


def test_registrar_gguf_invoca_ollama_create(tmp_path, monkeypatch):
    gguf = tmp_path / "modelo.gguf"
    gguf.write_bytes(b"GGUF")
    comandos: list[list[str]] = []

    def _run(comando, **_kwargs):
        comandos.append(list(comando))
        return _Proceso(0)

    monkeypatch.setattr(stm_modelos.subprocess, "run", _run)
    monkeypatch.setattr(stm_modelos, "_modelos_ollama_instalados",
                        lambda: {"wvp-coder-1.5b"})
    assert stm_modelos._registrar_gguf_en_ollama(
        "http://localhost:11434", gguf) is True
    assert comandos and comandos[0][:3] == ["ollama", "create", "wvp-coder-1.5b"]
    assert not list(tmp_path.glob("Modelfile.*")), "el Modelfile se borra al terminar"


def test_registrar_gguf_falla_si_ollama_create_falla(tmp_path, monkeypatch):
    gguf = tmp_path / "modelo.gguf"
    gguf.write_bytes(b"GGUF")
    monkeypatch.setattr(stm_modelos.subprocess, "run",
                        lambda *_a, **_k: _Proceso(1, "error de prueba"))
    assert stm_modelos._registrar_gguf_en_ollama(
        "http://localhost:11434", gguf) is False


def test_registrar_gguf_falla_si_no_aparece_en_ollama(tmp_path, monkeypatch):
    gguf = tmp_path / "modelo.gguf"
    gguf.write_bytes(b"GGUF")
    monkeypatch.setattr(stm_modelos.subprocess, "run",
                        lambda *_a, **_k: _Proceso(0))
    monkeypatch.setattr(stm_modelos, "_modelos_ollama_instalados", lambda: set())
    assert stm_modelos._registrar_gguf_en_ollama(
        "http://localhost:11434", gguf) is False


def test_el_respaldo_gguf_devuelve_el_modelo_registrado(tmp_path, monkeypatch):
    monkeypatch.setattr(stm_modelos, "_candidatos_disponibles",
                        lambda: ["qwen2.5-coder:3b"])
    monkeypatch.setattr(stm_modelos, "_modelos_ollama_instalados", lambda: set())
    monkeypatch.setattr(stm_modelos, "_cargar_configuracion_ia_local",
                        lambda: ("http://localhost:11434", "x"))
    monkeypatch.setattr(stm_modelos, "_modelos_usados_registro", lambda: set())
    monkeypatch.setattr(stm_modelos, "_ram_gb", lambda: 16.0)
    monkeypatch.setattr(stm_modelos, "_descargar_modelo_ollama",
                        lambda *_a: False)
    monkeypatch.setattr(stm_modelos, "_descargar_peso_hf",
                        lambda: tmp_path / "modelo.gguf")
    monkeypatch.setattr(stm_modelos, "_registrar_gguf_en_ollama",
                        lambda *_a: True)
    assert stm_modelos._asegurar_modelo_codigo() == stm_modelos.NOMBRE_MODELO_GGUF
