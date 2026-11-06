"""STM_HRTS como registro unico de rutas y catalogo de herramientas."""
from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from STM_HRTS.utils.add_utils import __main__ as consola
import pytest  # noqa: E402

from STM_HRTS.utils.add_utils import herramientas  # noqa: E402
from STM_HRTS.utils.add_utils import rutas  # noqa: E402


def test_rutas_clave_existen():
    informe = rutas.verificar()
    faltan = rutas.faltantes(informe)
    assert not faltan, "Rutas clave ausentes:\n  " + "\n  ".join(
        f"{f['nombre']}: {f['ruta']}" for f in faltan
    )


def test_rutas_son_absolutas_y_bajo_src_lo_que_debe():
    for nombre, ruta in rutas.RUTAS_CLAVE:
        assert ruta.is_absolute(), f"{nombre} no es absoluta: {ruta}"
    bajo_src = (
        rutas.GODOT_DIR, rutas.GODOT_SCRIPTS, rutas.GODOT_SHADERS, rutas.GODOT_SCENES,
        rutas.CSPROJ, rutas.DOCS_DIR, rutas.HERRAMIENTAS_DIR, rutas.TESTS_DIR,
        rutas.PYTEST_INI, rutas.CONOCIMIENTO_DIR, rutas.STM_CH_DIR,
    )
    for ruta in bajo_src:
        assert ruta == SRC_DIR or SRC_DIR in ruta.parents, f"Fuera de src/: {ruta}"


def test_raices_coherentes():
    assert rutas.STM_HRTS_DIR == SRC_DIR / "STM_HRTS"
    assert rutas.TLLDCD_DIR == SRC_DIR.parent
    assert rutas.CONTRRF_DIR == rutas.TLLDCD_DIR.parent
    assert rutas.RAICES["src"] == SRC_DIR
    # Entre src/ y el repo no hay un numero de niveles fijo: lo pone la
    # promocion RFPRMN (VersionDe_sesion/Sistema_Principal/PRY/actualizacion_x/src).
    # Las raices superiores se buscan por su marca, no por posicion.
    assert rutas.REPO_DIR in SRC_DIR.parents
    assert (rutas.REPO_DIR / ".git").exists() or (rutas.SRC_DIR / ".git").exists()
    assert rutas.VERSION_DIR.name == "VersionDe_sesion"
    assert rutas.VERSION_DIR in SRC_DIR.parents


def test_stm_ch_delega_en_stm_hrts():
    from STM_CH import rutas as ch

    for nombre in (
        "SRC_DIR", "TLLDCD_DIR", "CONTRRF_DIR", "STM_CH_DIR", "PYCACHE_DIR",
        "PSNRL_DIR", "LEDGER_PATH", "CACHE_IAFREE", "RUFF_CACHE_CANON",
    ):
        assert getattr(ch, nombre) == getattr(rutas, nombre), (
            f"STM_CH.rutas.{nombre} no coincide con STM_HRTS.rutas.{nombre}"
        )
    assert ch.__all__, "STM_CH.rutas debe declarar su API publica"


def test_catalogo_integro():
    lista = herramientas.catalogo()
    assert lista, f"No se encontraron herramientas en {rutas.HERRAMIENTAS_DIR}"
    nombres = [h.nombre for h in lista]
    assert len(nombres) == len(set(nombres)), f"Herramientas duplicadas: {nombres}"
    for h in lista:
        assert h.archivo.is_file(), f"Herramienta inexistente: {h.archivo}"
        assert rutas.HERRAMIENTAS_DIR in h.archivo.parents, (
            f"{h.nombre} vive fuera de STM_HRTS/utils: {h.archivo}"
        )
        assert h.tipo in set(herramientas.TIPO_POR_SUFIJO.values())
        assert h.relativa.startswith("STM_HRTS/utils/")


def test_catalogo_clasifica_modo_grafico():
    """La clasificacion sale del contenido del script, no de su nombre."""
    for h in herramientas.catalogo():
        assert h.headless is not herramientas.necesita_ventana(h.archivo), (
            f"{h.nombre}: el catalogo y la regla de contenido discrepan"
        )


def test_capturas_sin_autoguarda_no_corren_headless():
    # Medido 2026-11-05: estos tres se llamaban "probar_" y salian con 0 tras
    # volcar "Cannot call method 'save_png' on a null value". Un verde que no
    # comprueba nada.
    for nombre in ("probar_cara", "probar_cuerpo", "probar_personalizacion",
                   "capturar_carrusel", "render_avatares"):
        assert herramientas.buscar(nombre).headless is False, f"{nombre} necesita ventana"
    # Y el caso contrario: captura, pero se autoguarda, asi que si es headless.
    assert herramientas.buscar("probar_registro").headless is True


def test_el_modo_pck_sale_de_la_medicion():
    # Ocho guiones fallan o se cuelgan desde el arbol porque aqui no existe
    # `.godot/imported` (esta en .gitignore), y probar_red_puerto sale 1 con el
    # PCK porque el paquete trae el gdscrip/ de la 2.7.6: el modo no se deduce
    # del contenido, se mide.
    for nombre in ("probar_ganchos", "probar_registro", "validar_avatares",
                   "validar_ch3d", "validar_shapekeys_reales"):
        assert herramientas.buscar(nombre).montar_pck is True, f"{nombre} necesita el PCK"
        assert herramientas.buscar(nombre).modo == herramientas.MODO_PCK
    for nombre in ("probar_red_puerto", "probar_turnos", "probar_red_invitacion"):
        assert herramientas.buscar(nombre).montar_pck is False, f"{nombre} prueba el arbol"
        assert herramientas.buscar(nombre).modo == herramientas.MODO_ARBOL


def test_comando_godot_solo_monta_el_pck_lo_que_toca():
    _requiere_godot()
    arbol = herramientas.comando("probar_red_puerto")["argv"]
    assert "--main-pack" not in arbol, "montar el PCK probaria el codigo empaquetado, no el del arbol"
    if rutas.PCK_EMBEBIDO.is_file():
        assert herramientas.comando("probar_ganchos")["argv"].count("--main-pack") == 1


def test_comando_godot_aisla_el_user_de_godot():
    plan = herramientas.comando("probar_turnos")
    anclaje = str(rutas.GODOT_USER_DIR)
    assert plan["env"]["APPDATA"] == anclaje
    assert plan["env"]["LOCALAPPDATA"] == anclaje
    assert plan["env"]["XDG_DATA_HOME"] == anclaje
    # El aislamiento no puede escribir en el registro real del visor instalado.
    assert rutas.GODOT_USER_DIR.parent == rutas.USER_DATA_DIR
    assert "test_user_data" in rutas.USER_DATA_DIR.parts


def test_veredicto_identifica_a_los_que_no_comprueban_nada():
    con_veredicto = {
        h.nombre for h in herramientas.catalogo()
        if h.tipo == "godot" and herramientas.emite_veredicto(h.archivo)
    }
    assert "probar_turnos" in con_veredicto
    assert "validar_avatares" in con_veredicto
    # Capturas y sondas: `quit()` a secas, salen 0 pase lo que pase.
    for nombre in ("capturar_carrusel", "probar_cara", "render_avatares",
                   "inspeccionar_avatar", "probar_sonda_anfitrion"):
        assert nombre not in con_veredicto, f"{nombre} no condiciona su salida"
    assert herramientas.buscar("probar_turnos").headless is True


def test_busqueda_por_nombre_y_extension():
    assert herramientas.buscar("probar_construccion").tipo == "godot"
    assert herramientas.buscar("PROBAR_CONSTRUCCION.GD").nombre == "probar_construccion"
    assert herramientas.buscar("generar_ch3d").tipo == "python"
    with pytest.raises(herramientas.ErrorHerramienta):
        herramientas.buscar("no_existe_esta_herramienta")


def _requiere_godot():
    if rutas.binario_godot() is None:
        pytest.skip("Godot no disponible (define GODOT_BIN)")


def test_comando_godot_headless():
    _requiere_godot()
    plan = herramientas.comando("probar_construccion")
    argv = plan["argv"]
    assert Path(plan["cwd"]) == rutas.SRC_DIR
    assert "--path" in argv
    assert argv[argv.index("--path") + 1] == str(rutas.GODOT_DIR)
    assert "--headless" in argv
    assert argv[argv.index("--script") + 1] == str(
        herramientas.buscar("probar_construccion").archivo
    )


def test_comando_godot_con_ventana_y_argumentos():
    _requiere_godot()
    plan = herramientas.comando("capturar_construccion", ["--salida", "x.png"])
    argv = plan["argv"]
    assert "--headless" not in argv
    assert argv[-3:] == ["--", "--salida", "x.png"]


def test_comando_python_usa_el_interprete_actual():
    plan = herramientas.comando("generar_ch3d")
    assert plan["argv"][0] == str(rutas.python_actual())
    assert plan["argv"][1].endswith("generar_ch3d.py")


def test_comando_pytest_unico_en_raiz():
    plan = herramientas.comando_pytest(["-k", "rutas"])
    argv = plan["argv"]
    assert "-c" in argv and argv[argv.index("-c") + 1] == str(rutas.PYTEST_INI)
    assert Path(plan["cwd"]) == SRC_DIR
    assert not (rutas.HERRAMIENTAS_DIR / "pytest.ini").exists(), (
        "No debe haber un pytest.ini dentro de STM_HRTS/utils"
    )
    assert rutas.PYTEST_INI.read_text(encoding="utf-8").count("STM_HRTS") >= 1


def test_pytest_cache_vive_en_stm_hrts():
    assert rutas.PYTEST_CACHE == rutas.STM_HRTS_DIR / ".pytest_cache"
    assert not (SRC_DIR / ".pytest_cache").exists(), (
        "La cache de pytest no debe quedar en la raiz de src/"
    )
    texto = rutas.PYTEST_INI.read_text(encoding="utf-8")
    assert "cache_dir" in texto and "STM_HRTS" in texto


def test_consola_rutas_y_verificar(capsys):
    assert consola.main(["verificar", "--json"]) == 0
    salida = capsys.readouterr().out
    assert '"existe": true' in salida
    assert consola.main(["rutas"]) == 0
    assert "src" in capsys.readouterr().out


def test_consola_herramientas_json(capsys):
    import json

    assert consola.main(["herramientas", "--json"]) == 0
    datos = json.loads(capsys.readouterr().out)
    assert any(d["nombre"] == "probar_construccion" for d in datos)


def test_consola_herramienta_desconocida():
    assert consola.main(["ejecutar", "no_existe_esta_herramienta"]) == 2


def test_manifiesto_declara_la_consola():
    from STM_HRTS.utils.add_utils.registro_hrts import RegistroHRTS

    scripts = RegistroHRTS().scripts()
    assert scripts.get("hrts") == "STM_HRTS.__main__:main"


def test_entrypoint_declarado_resuelve_a_la_consola():
    """El script ``hrts`` apunta a un módulo que existe y reenvía al motor real."""
    import importlib

    modulo = importlib.import_module("STM_HRTS.__main__")
    assert callable(modulo.main)
    assert modulo.main is consola.main
