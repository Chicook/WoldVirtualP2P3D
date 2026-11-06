"""Version unica del producto: `src/VERSION.json`.

Desde U5.1 el numero vive en un solo fichero. Los cuatro proyectos C# lo leen a traves de
`VSC#/Directory.Build.props` (que fija Version/AssemblyVersion/FileVersion y el nombre del .exe) y
`VSC#/Directory.Build.targets` (que lo materializa en la clase `WoldInfoVersion`, de la que salen
`RutasLinux.Version` y el nombre del motor Godot). Antes havia cinco fuentes que se desmentian:
el plan §1.6 midio un arbol que declaraba 2.7.5 mientras el binario publicado era 2.7.6.

Modos:
  --leer           imprime la version (lo usan los guiones de publicacion)
  --comprobar      verifica los invariantes del arbol; sale 1 si alguno se rompe
  --fijar X.Y.Z    UNICO punto de cambio del numero: reescribe VERSION.json (y --motor si toca)
  --registrar-pck  recalcula digest y bytes del PCK en disco y los escribe en VERSION.json
                   (es el paso que hay que dar despues de reexportar, regla RU5)

`--fijar` existe porque antes cada release pedia editar cinco ficheros a mano y alguien siempre
olvidaba uno: el plan §1.6 midio un arbol que declaraba 2.7.5 con el 2.7.6 ya publicado. Se niega a
rebajar o repetir un numero (regla R4: las etiquetas publicadas no se reescriben).

No depende de `rutas.py` a proposito: este fichero es el ancla, si el registro de rutas se rompe la
version sigue siendo legible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Tuple

SRC_DIR: Path = Path(__file__).resolve().parents[3]
VERSION_JSON: Path = SRC_DIR / "VERSION.json"
VSC_DIR: Path = SRC_DIR / "VSC#"
PCK: Path = VSC_DIR / "wvp3d.pck"

CAMPOS_OBLIGATORIOS = ("version", "motor", "pck_sha256", "pck_bytes", "fecha")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
HEX_SHA = re.compile(r"^[0-9a-f]{64}$")
FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Los csproj que deben heredar el numero, no escribirlo.
CSPROJ = ("Visor3D.csproj", "Nucleo/Nucleo.csproj", "VisorLinux/VisorLinux.csproj", "Tests/Visor3DTests.csproj")
PROPIEDADES_VERSION = ("Version", "AssemblyVersion", "FileVersion")


def leer() -> Dict[str, Any]:
    """Diccionario de VERSION.json validado campo a campo."""
    if not VERSION_JSON.is_file():
        raise ValueError(f"no existe {VERSION_JSON}")
    datos = json.loads(VERSION_JSON.read_text(encoding="utf-8-sig"))
    for campo in CAMPOS_OBLIGATORIOS:
        if campo not in datos:
            raise ValueError(f"VERSION.json no tiene el campo {campo!r}")
    if not SEMVER.match(str(datos["version"])):
        raise ValueError(f"version sin formato x.y.z: {datos['version']!r}")
    if not str(datos["motor"]):
        raise ValueError("el campo 'motor' esta vacio")
    if not HEX_SHA.match(str(datos["pck_sha256"])):
        raise ValueError(f"pck_sha256 no es SHA-256 hex: {datos['pck_sha256']!r}")
    if not isinstance(datos["pck_bytes"], int) or datos["pck_bytes"] <= 0:
        raise ValueError(f"pck_bytes no es un entero positivo: {datos['pck_bytes']!r}")
    if not FECHA.match(str(datos["fecha"])):
        raise ValueError(f"fecha sin formato AAAA-MM-DD: {datos['fecha']!r}")
    return datos


def _digestos(pck: Path) -> tuple[str, int]:
    return hashlib.sha256(pck.read_bytes()).hexdigest(), pck.stat().st_size


def _csproj_sin_literal(rel: str) -> list[str]:
    """Razones por las que un .csproj vuelve a cablear el numero en vez de heredarlo."""
    ruta = VSC_DIR / rel
    if not ruta.is_file():
        return [f"falta {rel}"]
    texto = ruta.read_text(encoding="utf-8")
    quejas: list[str] = []
    for propiedad in PROPIEDADES_VERSION:
        for valor in re.findall(rf"<{propiedad}>([^<]*)</{propiedad}>", texto):
            if "$(" not in valor and re.search(r"\d+\.\d+", valor):
                quejas.append(f"{rel}: <{propiedad}>{valor}</{propiedad}> es un literal")
    for nombre in re.findall(r"<AssemblyName>([^<]*)</AssemblyName>", texto):
        if "DMWoldVirtualP2P3Dv" in nombre and "$(" not in nombre:
            quejas.append(f"{rel}: <AssemblyName>{nombre}</AssemblyName> cablea la version")
    return quejas


def _codigo_sin_literal(rel: str, patron: re.Pattern[str]) -> list[str]:
    ruta = VSC_DIR / rel
    if not ruta.is_file():
        return [f"falta {rel}"]
    lineas = [
        f"{rel}:{numero}: {texto.strip()}"
        for numero, texto in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1)
        if patron.search(texto) and not texto.strip().startswith("//")
    ]
    return lineas


def comprobar() -> list[str]:
    """Lista de problemas; vacia significa arbol coherente."""
    problemas: list[str] = []
    try:
        datos = leer()
    except (ValueError, json.JSONDecodeError) as error:
        return [f"VERSION.json invalido: {error}"]

    for rel in CSPROJ:
        problemas += _csproj_sin_literal(rel)

    # El visor de Linux no puede volver a tener su propio numero (estaba en 2.7.5).
    rutas_cs = _codigo_sin_literal("VisorLinux/Linux/RutasLinux.cs", re.compile(r"[\"']\d+\.\d+\.\d+[\"']"))
    if rutas_cs:
        problemas += [f"RutasLinux.cs hardcodea una version: {l}" for l in rutas_cs]
    motor_literal = _codigo_sin_literal("VisorLinux/Linux/RutasLinux.cs", re.compile(r"Godot_v\d"))
    if motor_literal:
        problemas += [f"RutasLinux.cs hardcodea el motor: {l}" for l in motor_literal]

    # Ningun .cs del visor debe volver a escribir el nombre del motor a mano.
    for fuente in sorted(VSC_DIR.rglob("*.cs")):
        if "/obj/" in str(fuente).replace("\\", "/") or "/bin/" in str(fuente).replace("\\", "/"):
            continue
        texto = fuente.read_text(encoding="utf-8", errors="ignore")
        for numero, linea in enumerate(texto.splitlines(), start=1):
            if re.search(r"Godot_v\d+\.\d+\.\d+", linea) and not linea.strip().startswith("//"):
                problemas.append(f"{fuente.relative_to(SRC_DIR)}:{numero} hardcodea el motor: {linea.strip()}")

    if PCK.is_file():
        digest, bytes_real = _digestos(PCK)
        if digest != datos["pck_sha256"]:
            problemas.append(
                f"el PCK en disco ({PCK.name}) no es el que declara VERSION.json: "
                f"digest real {digest[:12]}… frente a {str(datos['pck_sha256'])[:12]}…"
            )
        if bytes_real != datos["pck_bytes"]:
            problemas.append(f"el PCK pesa {bytes_real} B y VERSION.json declara {datos['pck_bytes']} B")
    else:
        problemas.append(f"no hay PCK en {PCK} (no se puede anclar el digest; DT-07)")

    return problemas


def registrar_pck() -> Dict[str, Any]:
    """Escribe en VERSION.json el digest y el peso reales del PCK en disco."""
    if not PCK.is_file():
        raise ValueError(f"no hay PCK en {PCK}")
    datos = leer()
    digest, bytes_real = _digestos(PCK)
    datos["pck_sha256"] = digest
    datos["pck_bytes"] = bytes_real
    VERSION_JSON.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return datos


def _clave(version: str) -> Tuple[int, int, int]:
    mayor, menor, parche = version.split(".")
    return int(mayor), int(menor), int(parche)


def fijar(nueva: str, motor: str = "") -> Dict[str, Any]:
    """Sube el numero en el unico sitio que lo guarda: `src/VERSION.json`.

    Rebajar esta prohibido: la version ya publicada es un tag inmutable (regla R4) y un arbol por
    debajo del binario en Releases hace que el OTA baje el propio instalador.
    """
    if not SEMVER.match(nueva):
        raise ValueError(f"version sin formato x.y.z: {nueva!r}")
    datos = leer()
    anterior = str(datos["version"])
    if _clave(nueva) <= _clave(anterior):
        raise ValueError(
            f"{nueva} no sube la version: el arbol ya declara {anterior}; "
            "los numeros publicados no se reescriben ni se rebajan (regla R4)"
        )
    if motor and not re.match(r"^\d+\.\d+\.\d+$", motor):
        raise ValueError(f"motor sin formato x.y.z: {motor!r}")
    datos["version"] = nueva
    if motor:
        datos["motor"] = motor
    datos["fecha"] = date.today().isoformat()
    VERSION_JSON.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return datos


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Version unica del producto (src/VERSION.json)")
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--leer", action="store_true", help="imprime la version")
    modo.add_argument("--comprobar", action="store_true", help="verifica los invariantes del arbol")
    modo.add_argument("--fijar", metavar="X.Y.Z", help="sube el numero en VERSION.json (unico punto)")
    modo.add_argument("--registrar-pck", action="store_true", help="refresca el digest del PCK en VERSION.json")
    parser.add_argument("--motor", default="", help="con --fijar, cambias tambien el motor de Godot")
    args = parser.parse_args(argv)

    if args.leer:
        print(leer()["version"])
        return 0

    if args.fijar:
        try:
            datos = fijar(args.fijar, args.motor)
        except ValueError as error:
            print(f"FALLO {error}")
            return 1
        print(f"VERSION.json: {datos['version']} (motor {datos['motor']}, {datos['fecha']})")
        print("siguientes pasos:")
        print("  1. python -m STM_HRTS.utils.add_utils.version_unica --comprobar")
        print("  2. dotnet build Visor3D.sln -c Debug   (los csproj heredan el numero)")
        if args.motor:
            print("  3. reexportar el PCK con ese motor y despues --registrar-pck (regla RU5)")
        else:
            print("  3. si has tocado gdscrip/ o ESCENAS/, reexportar el PCK y despues --registrar-pck (RU5)")
        return 0

    if args.registrar_pck:
        datos = registrar_pck()
        print(f"PCK anotado: {datos['pck_sha256'][:16]}… · {datos['pck_bytes']} B")
        return 0

    problemas = comprobar()
    datos = leer()
    print(f"VERSION.json: {datos['version']} (motor {datos['motor']}, {datos['fecha']})")
    if problemas:
        for problema in problemas:
            print(f"FALLO {problema}")
        return 1
    print(f"OK version unica: {len(CSPROJ)} csproj heredan el numero y el PCK esta anclado")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
