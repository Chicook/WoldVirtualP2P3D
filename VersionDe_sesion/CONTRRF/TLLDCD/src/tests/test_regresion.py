"""Cobertura de regresion: todo modulo del paquete debe importar sin traceback."""
from __future__ import annotations

import ast
import pathlib
import sys

SRC_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

PAQUETES = [
    "SBSTM",
    "SBSTM.accesores",
    "STM_BKCH",
    "STM_BKCH.BKSVCB",
    "STM_BKCH.bksvcb_net",
    "STM_BKCH.compat_local",
    "STM_CH.rutas",
    "STM_SGR.vault_openrouter",
    "STM_JSON.registro_json",
    "STM_HRTS.registro_hrts",
    "STMGNRL.mainLCSTM",
]


def test_todos_los_paquetes_importan():
    fallos = []
    for mod in PAQUETES:
        try:
            __import__(mod)
        except Exception as exc:
            fallos.append(f"{mod}: {type(exc).__name__}: {exc}")
    assert not fallos, "Paquetes que no importan:\n  " + "\n  ".join(fallos)


def test_accesores_exporta_todo_lo_declarado():
    import SBSTM.accesores as A

    faltantes = [n for n in A.__all__ if not hasattr(A, n)]
    assert not faltantes, f"accesores.__all__ declara simbolos inexistentes: {faltantes}"


def test_sbstm_reexporta_accesores():
    import SBSTM as S

    for nombre in (
        "obtener_procesador_rplc",
        "reprocesar_respuesta_lucia",
        "obtener_motor_voz",
        "reproducir_voz_lucia",
        "cancelar_voz_lucia",
        "obtener_servicio_iafree",
        "obtener_motor_stylos",
    ):
        assert hasattr(S, nombre), f"SBSTM no reexporta {nombre}"


def test_sin_sintaxis_rota_en_todo_el_src():
    rotos = []
    for p in SRC_DIR.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            rotos.append(f"{p.relative_to(SRC_DIR)} L{exc.lineno}: {exc.msg}")
    assert not rotos, "Archivos con error de sintaxis:\n  " + "\n  ".join(rotos)


def test_sesion_neuronal_api_completa():
    """La clase de sesion debe exponer la API que SBSTM/__init__.py invoca."""
    from SBSTM.SNSBSTNPRB import SesionNeuronalP2P

    for metodo in (
        "arrancar",
        "bucle_conversacion",
        "iniciar_consola_interactiva",
        "cerrar",
        "obtener_telemetria",
        "guardar_checkpoint_psnrl",
    ):
        assert hasattr(SesionNeuronalP2P, metodo), (
            f"SesionNeuronalP2P no expone '{metodo}', requerido por SBSTM/__init__.py"
        )


def test_vault_pbkdf2_determinista_opcional():
    from STM_SGR.vault_openrouter import cifrar_key, descifrar_blob

    key = "sk-test-12345-abcdef"
    assert descifrar_blob(cifrar_key(key)) == key
    salt = b"0123456789abcdef"
    assert cifrar_key(key, salt=salt) == cifrar_key(key, salt=salt)


def test_config_pytest_unica_en_raiz():
    """pytest.ini vive en STM_HRTS/ (movido de src/ por peticion del usuario)."""
    from STM_HRTS.rutas import PYTEST_INI, STM_HRTS_DIR
    # La config esta ahora en STM_HRTS/, no en la raiz de src/
    assert PYTEST_INI.exists(), f"Debe existir pytest.ini en STM_HRTS/: {PYTEST_INI}"
    assert PYTEST_INI.parent == STM_HRTS_DIR, (
        f"pytest.ini debe estar en STM_HRTS/, no en {PYTEST_INI.parent}"
    )
    assert not (SRC_DIR / "pytest.ini").exists(), (
        "No debe haber pytest.ini en la raiz de src/ (se mueve a STM_HRTS/)"
    )
    assert "STM_HRTS" in PYTEST_INI.read_text(encoding="utf-8"), (
        "pytest.ini debe redirigir la cache a STM_HRTS/"
    )



def test_slrn_no_importa_init_como_modulo():
    """Los optimizadores SLRN deben usar import relativo, no 'from __init__ import'."""
    import re

    rotos = []
    for i in range(1, 11):
        p = SRC_DIR / "LC_STM" / "red_neuronal" / "SLRN" / f"SL{i}.py"
        src = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"from\s+__init__\s+import", src):
            rotos.append(f"SL{i}.py")
    assert not rotos, f"Usan 'from __init__ import': {rotos}"


def test_slrn_diez_optimizadores_importan():
    import importlib

    for i in range(1, 11):
        importlib.import_module(f"LC_STM.red_neuronal.SLRN.SL{i}")


def test_familias_neuronales_importan():
    import importlib

    familias = ["ENRN", "RF_EN", "RF_SL", "RNP", "SLRN"]
    for fam in familias:
        importlib.import_module(f"LC_STM.red_neuronal.{fam}")