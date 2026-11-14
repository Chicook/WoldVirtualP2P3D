"""U5 · Version unica: src/VERSION.json manda sobre los cuatro proyectos C#.

El plan §1.6 midio cinco fuentes de version que se desmentian (los dos .csproj, RutasLinux.cs, el
AssemblyInfo generado en obj/ y el SBSTM). Desde U5.1 el numero esta en un fichero,
`VSC#/Directory.Build.props` lo traduce a propiedades de ensamblado y
`VSC#/Directory.Build.targets` lo materializa en `WoldInfoVersion`, del que salen
`RutasLinux.Version` y el nombre del motor. Este gate es lo que evita la recaida: si alguien vuelve
a escribir `<Version>2.7.8</Version>` en un csproj o un `"2.7.5"` en RutasLinux.cs, CI lo para.

El ancla cruzada de verdad es la ultima prueba: pregunta a MSBuild que valor saca del JSON. Ahi es
donde se cortaria la incoherencia entre «lo que compila» y «lo que anuncia el portal» (DT-08).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))

from STM_HRTS.utils.add_utils import version_unica  # noqa: E402

VSC_DIR = SRC_DIR / "VSC#"
PROPS = VSC_DIR / "Directory.Build.props"
TARGETS = VSC_DIR / "Directory.Build.targets"
RUTAS_LINUX = VSC_DIR / "VisorLinux" / "Linux" / "RutasLinux.cs"


def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def test_version_json_existe_y_es_semver():
    datos = version_unica.leer()
    assert re.match(r"^\d+\.\d+\.\d+$", str(datos["version"])), datos["version"]
    assert datos["motor"], "el campo «motor» no puede estar vacio"


@pytest.mark.parametrize("rel", version_unica.CSPROJ)
def test_cada_csproj_hereda_el_numero_sin_cablearlo(rel: str):
    quejas = version_unica._csproj_sin_literal(rel)
    assert not quejas, "; ".join(quejas)


def test_los_cuatro_csproj_existen_y_declaran_version():
    for rel in version_unica.CSPROJ:
        texto = _leer(VSC_DIR / rel)
        assert "$(WoldVersion)" in texto, f"{rel} no consume la version unica"


def test_rutaslinux_no_vuelve_a_tener_su_propio_numero():
    texto = _leer(RUTAS_LINUX)
    assert "WoldInfoVersion.Version" in texto, "RutasLinux.Version debe derivar de la tabla"
    assert "WoldInfoVersion.Motor" in texto, "RutasLinux.NombreMotor debe derivar de la tabla"
    assert not re.search(r"[\"']\d+\.\d+\.\d+[\"']", texto), (
        "RutasLinux.cs lleva un literal de version: era 2.7.5 mientras los csproj decian 2.7.7"
    )


def test_ningun_cs_vuelve_a_escribir_el_nombre_del_motor():
    """El nombre del exe de Godot se compone desde VERSION.json; estaba literal en tres ficheros."""
    culpables = []
    for fuente in sorted(VSC_DIR.rglob("*.cs")):
        texto_rel = str(fuente.relative_to(VSC_DIR)).replace("\\", "/")
        if texto_rel.startswith(("obj/", "bin/")):
            continue
        for numero, linea in enumerate(_leer(fuente).splitlines(), start=1):
            if re.search(r"Godot_v\d+\.\d+\.\d+", linea) and not linea.strip().startswith("//"):
                culpables.append(f"{texto_rel}:{numero}")
    assert not culpables, "nombre del motor hardcodeado en " + ", ".join(culpables)


def test_props_y_targets_son_el_unico_puente_con_msbuild():
    props = _leer(PROPS)
    assert "VERSION.json" in props, "Directory.Build.props debe leer la tabla"
    assert "ReadAllText" in props
    assert props.count("<Error") >= 2, (
        "sin guardas el build cae en un numero por defecto y revive el desfase binario/anuncio (DT-08)"
    )
    targets = _leer(TARGETS)
    assert "$(IntermediateOutputPath)" in targets, "el fichero generado no debe caer en el arbol fuente"
    assert "WoldInfoVersion" in targets


def test_el_pck_queda_ancorado_en_la_tabla():
    if not version_unica.PCK.is_file():
        pytest.skip("no hay PCK en la zona; el ancla se verifica tras el reexport (RU5)")
    digest, bytes_reales = version_unica._digestos(version_unica.PCK)
    datos = version_unica.leer()
    assert digest == datos["pck_sha256"], "el PCK en disco no es el que declara VERSION.json"
    assert bytes_reales == datos["pck_bytes"]


def _arbol_aislado(tmp_path: Path, monkeypatch) -> Path:
    """Copia VERSION.json a un tmp y engancha el modulo alli: `fijar` escribe de verdad."""
    gemelo = tmp_path / "VERSION.json"
    gemelo.write_text(version_unica.VERSION_JSON.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(version_unica, "VERSION_JSON", gemelo)
    return gemelo


def test_fijar_toca_un_solo_fichero(tmp_path, monkeypatch):
    from datetime import date

    gemelo = _arbol_aislado(tmp_path, monkeypatch)
    antes = version_unica.leer()
    datos = version_unica.fijar("99.0.0")
    assert datos["version"] == "99.0.0"
    assert datos["motor"] == antes["motor"], "el motor no cambia si no se pide"
    assert datos["pck_sha256"] == antes["pck_sha256"], "subir de version no reancla el PCK"
    assert datos["fecha"] == date.today().isoformat()
    assert json.loads(gemelo.read_text(encoding="utf-8"))["version"] == "99.0.0"


def test_fijar_no_rebaja_ni_repite_el_numero(tmp_path, monkeypatch):
    """La Version publicada es un tag inmutable (R4); bajarla hace que el OTA baje su propio exe."""
    _arbol_aislado(tmp_path, monkeypatch)
    actual = version_unica.leer()["version"]
    for peor in (actual, "1.0.0", "0.0.1"):
        with pytest.raises(ValueError, match="no sube la version"):
            version_unica.fijar(peor)


def test_fijar_exige_x_y_z(tmp_path, monkeypatch):
    _arbol_aislado(tmp_path, monkeypatch)
    for invento in ("2.8", "v2.8.0", "2.8.0-beta", "2.8.0.1", ""):
        with pytest.raises(ValueError, match="x.y.z"):
            version_unica.fijar(invento)


def test_fijar_valida_el_motor(tmp_path, monkeypatch):
    """`--motor` es el campo del que sale `Godot_v<motor>`; un literal aqui revive DT-08."""
    _arbol_aislado(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="motor sin formato"):
        version_unica.fijar("99.0.0", motor="4.7")
    assert version_unica.fijar("99.0.0", motor="4.7.3")["motor"] == "4.7.3"


def test_la_tabla_es_la_unica_fuente_del_numero():
    """Despues de `--fijar` no puede quedar ni un literal suelto que lo contradiga."""
    problemas = version_unica.comprobar()
    assert not problemas, "\n".join(problemas)


@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet no disponible")
def test_msbuild_extrae_la_misma_version_que_python():
    """La prueba cruzada: lo que ve MSBuild tiene que ser lo que ve `version_unica.leer()`."""
    proc = subprocess.run(
        [sys.executable, str(SRC_DIR / "STM_HRTS" / "utils" / "add_utils" / "version_unica.py"), "--leer"],
        capture_output=True, text=True, cwd=str(SRC_DIR), timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    version_python = proc.stdout.strip()

    salida = subprocess.run(
        ["dotnet", "msbuild", "Visor3D.csproj", "-nologo", "-getProperty:WoldVersion"],
        capture_output=True, text=True, cwd=str(VSC_DIR), timeout=300,
    )
    assert salida.returncode == 0, salida.stderr
    # Con una sola propiedad MSBuild imprime el valor pelado; con varias, JSON.
    crudo = salida.stdout.strip()
    version_msbuild = re.search(r'"WoldVersion":\s*"([^"]+)"', crudo)
    valor = version_msbuild.group(1) if version_msbuild else crudo.splitlines()[-1].strip('"')
    assert valor == version_python, f"MSBuild saca {valor} y Python {version_python} del mismo fichero"
