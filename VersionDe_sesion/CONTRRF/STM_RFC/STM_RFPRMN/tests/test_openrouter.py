"""Pruebas del respaldo OpenRouter (queda desactivado por defecto)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from STM_RFPRMN_stmDL import stm_openrouter, stm_refactor


def _sin_entorno(monkeypatch):
    monkeypatch.delenv("RFPRMN_OPENROUTER", raising=False)


def _opciones(monkeypatch, tmp_path, datos=None):
    archivo = tmp_path / ".config" / "opciones.json"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    if datos is not None:
        archivo.write_text(json.dumps(datos), encoding="utf-8")
    monkeypatch.setattr(stm_openrouter, "ARCHIVO_OPCIONES", archivo)
    return archivo


def test_desactivado_por_defecto(monkeypatch, tmp_path):
    _sin_entorno(monkeypatch)
    _opciones(monkeypatch, tmp_path)
    assert stm_openrouter.habilitado() is False


def test_se_activa_por_entorno(monkeypatch, tmp_path):
    _opciones(monkeypatch, tmp_path)
    monkeypatch.setenv("RFPRMN_OPENROUTER", "1")
    assert stm_openrouter.habilitado() is True


def test_el_entorno_manda_sobre_el_archivo(monkeypatch, tmp_path):
    _opciones(monkeypatch, tmp_path, {"openrouter": True})
    monkeypatch.setenv("RFPRMN_OPENROUTER", "0")
    assert stm_openrouter.habilitado() is False


def test_se_activa_por_archivo(monkeypatch, tmp_path):
    _sin_entorno(monkeypatch)
    _opciones(monkeypatch, tmp_path, {"openrouter": True})
    assert stm_openrouter.habilitado() is True


def test_archivo_con_texto_falso_no_activa(monkeypatch, tmp_path):
    _sin_entorno(monkeypatch)
    _opciones(monkeypatch, tmp_path, {"openrouter": "false"})
    assert stm_openrouter.habilitado() is False


def test_archivo_corrupto_no_activa(monkeypatch, tmp_path):
    _sin_entorno(monkeypatch)
    archivo = tmp_path / ".config" / "opciones.json"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text("{no es json", encoding="utf-8")
    monkeypatch.setattr(stm_openrouter, "ARCHIVO_OPCIONES", archivo)
    assert stm_openrouter.habilitado() is False


def test_describir_estado_indica_como_activarlo(monkeypatch, tmp_path):
    _sin_entorno(monkeypatch)
    _opciones(monkeypatch, tmp_path)
    texto = stm_openrouter.describir_estado()
    assert "desactivado" in texto
    assert "RFPRMN_OPENROUTER" in texto


def test_el_fallback_no_hace_nada_si_esta_desactivado(monkeypatch):
    monkeypatch.setattr(stm_refactor, "openrouter_habilitado", lambda: False)

    def _no_debe_llamarse(*_args, **_kwargs):
        raise AssertionError("no debe pedirse la clave si está desactivado")

    monkeypatch.setattr(stm_refactor, "_leer_openrouter_key", _no_debe_llamarse)
    resultado = stm_refactor._fallback_openrouter(
        Path("ejemplo.py"), "x = 1\n", None, "qwen2.5-coder:7b", "timeout")
    assert resultado is False


def test_el_fallback_sigue_disponible_si_se_activa(monkeypatch, tmp_path):
    monkeypatch.setattr(stm_refactor, "openrouter_habilitado", lambda: True)
    monkeypatch.setattr(stm_refactor, "_leer_openrouter_key", lambda: "")
    monkeypatch.setattr(stm_refactor, "_borrar_modelo_ollama", lambda *_a: True)
    monkeypatch.setattr(stm_refactor, "_cargar_configuracion_ia_local",
                        lambda: ("http://localhost:11434", "x"))
    resultado = stm_refactor._fallback_openrouter(
        Path("ejemplo.py"), "x = 1\n", None, "qwen2.5-coder:7b", "timeout")
    assert resultado is False  # sin clave no hay refactor, pero sin excepción
