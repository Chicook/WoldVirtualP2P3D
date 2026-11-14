"""Cobertura de regresion: todo modulo del paquete debe importar sin traceback."""
from __future__ import annotations

import ast
import pathlib
import sys

SRC_DIR = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))

PAQUETES = [
    "SBSTM.SistemasLC",
    "SBSTM.SistemasLC.STM_SBTM_1.accesores",
    "STM_BKCH.stm_bkch1",
    "STM_BKCH.stm_bkch1.BKSVCB",
    "STM_BKCH.stm_bkch1.bksvcb_net",
    "STM_BKCH.stm_bkch1.compat_local",
    "STM_CH.STM_herramientas.rutas",
    "STM_SGR.STM_CNX.vault_openrouter",
    "STM_JSON.STM_LC.registro_json",
    "STM_HRTS.utils.add_utils.rutas",
    "STM_HRTS.utils.add_utils.herramientas",
    "STM_HRTS.utils.add_utils.registro_hrts",
    "STMGNRL.SistemaGeneral.mainLCSTM",
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
    import SBSTM.SistemasLC.STM_SBTM_1.accesores as A

    faltantes = [n for n in A.__all__ if not hasattr(A, n)]
    assert not faltantes, f"accesores.__all__ declara simbolos inexistentes: {faltantes}"


def test_sbstm_reexporta_accesores():
    import SBSTM.SistemasLC.STM_SBTM_1 as S

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
    from SBSTM.SistemasLC.STM_SBTM_2.SNSBSTNPRB import SesionNeuronalP2P

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
    from STM_SGR.STM_CNX.vault_openrouter import cifrar_key, descifrar_blob

    key = "sk-test-12345-abcdef"
    assert descifrar_blob(cifrar_key(key)) == key
    salt = b"0123456789abcdef"
    assert cifrar_key(key, salt=salt) == cifrar_key(key, salt=salt)


def test_config_pytest_unica_en_raiz():
    """pytest.ini viaja con el paquete, en STM_HRTS/utils/add_utils/."""
    from STM_HRTS.utils.add_utils.rutas import (
        ADD_UTILS_DIR,
        PYTEST_CACHE,
        PYTEST_INI,
        STM_HRTS_DIR,
    )

    assert PYTEST_INI.exists(), f"Debe existir pytest.ini junto al paquete: {PYTEST_INI}"
    assert PYTEST_INI.parent == ADD_UTILS_DIR, (
        f"pytest.ini debe vivir con el paquete, no en {PYTEST_INI.parent}"
    )
    assert not (SRC_DIR / "pytest.ini").exists(), (
        "No debe haber pytest.ini en la raiz de src/"
    )
    assert not (STM_HRTS_DIR / "pytest.ini").exists(), (
        "No debe duplicarse pytest.ini en STM_HRTS/"
    )
    assert PYTEST_CACHE == ADD_UTILS_DIR / "STM_HRTS" / ".pytest_cache", (
        "La cache de pytest debe vivir junto al paquete (add_utils/STM_HRTS/)"
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