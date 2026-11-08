"""Pruebas de la política de modelos (R3 de la discusión #84)."""
from __future__ import annotations

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
