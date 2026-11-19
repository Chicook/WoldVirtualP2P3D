"""Empaqueta el runtime privado de LucIA y su manifiesto SHA-256."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile


CONSTRUCCION = Path(__file__).resolve().parents[2]
PYTHON_BASE = CONSTRUCCION / ".dev" / ".python"
CEREBRO_BASE = (
    CONSTRUCCION / "TLLDCD" / "src" / "MTBGT" / "WoldVirtualP2P3D"
    / "lucia3D" / "GLTF_lucIA" / "celebro_3D"
)
SALIDA = Path(__file__).resolve().with_name("lucia_runtime.zip")
VERSION = "2.9.2"
ABI = "cp315-win_amd64"

PYTHON_RAIZ = (
    "python.exe", "pythonw.exe", "python315.dll", "python3.dll", "LICENSE.txt",
)
# Únicamente estos directorios, módulos y extensiones de site-packages.
SITE_DIRECTORIOS = (
    "numpy", "numpy.libs", "scipy", "scipy.libs", "_soundfile_data",
    "cffi", "pycparser", "pedalboard", "pedalboard_native", "gtts",
    "comtypes", "requests", "click", "colorama", "charset_normalizer",
    "idna", "urllib3", "certifi",
)
SITE_MODULOS = ("soundfile.py", "_soundfile.py", "typing_extensions.py")
SITE_BINARIOS = ("_cffi_backend*.pyd", "pedalboard_native*.pyd")
DISTRIBUCIONES = (
    "numpy", "scipy", "soundfile", "cffi", "pycparser", "pedalboard",
    "gtts", "comtypes", "requests", "click", "colorama",
    "charset_normalizer", "idna", "urllib3", "certifi", "typing_extensions",
)
CEREBRO_ARCHIVOS = (
    "puente_3D/servidor_lucia.py",
    "puente_3D/voz_lucia.py",
    "nucleo/__init__.py",
    "nucleo/orquestador_lucia.py",
    "STM_BKCH/__init__.py",
    "STM_BKCH/compat_local.py",
    "STM_CH/__init__.py",
    "STM_CH/rutas.py",
    "sub_sistemas/__init__.py",
    "sub_sistemas/accesores.py",
    "sub_sistemas/RPLC.py",
    "sub_sistemas/memoria_sesion.py",
    "sub_sistemas/rubrica.py",
    "sub_sistemas/voice_helpers.py",
)

OMITIR_DIRECTORIOS = {
    "test", "tests", "__pycache__", "cache", "caches", ".cache",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git",
    "idlelib", "tkinter", "ensurepip", "site-packages", "turtledemo",
    "benchmarks", "examples", "_examples", "models", "modelos",
    "user_data", "userdata", "profiles", "logs",
}
# Se conservan los helpers de runtime numpy.testing y scipy._lib._testutils:
# no son las suites tests/ y algunos módulos los importan al arrancar.
EXTENSIONES_RUNTIME = {".py", ".pyi", ".pyd", ".dll"}
RECURSOS_SITE = {
    "certifi/cacert.pem",
    "scipy/stats/_sobol_direction_numbers.npz",  # tabla numérica, no modelo
    "urllib3/contrib/emscripten/emscripten_fetch_worker.js",
}
EXTENSIONES_STDLIB = {".py", ".pyi", ".js", ".css", ".html", ".png", ".rst"}
VENV_RECURSOS = {
    "venv/scripts/common/activate", "venv/scripts/common/activate.fish",
    "venv/scripts/common/Activate.ps1", "venv/scripts/posix/activate.csh",
    "venv/scripts/nt/activate.bat", "venv/scripts/nt/deactivate.bat",
    "venv/scripts/nt/venvlauncher.exe", "venv/scripts/nt/venvwlauncher.exe",
}


def licencia(ruta: Path) -> bool:
    return any(
        parte.lower().startswith(("license", "licence", "copying", "copyright", "notice"))
        for parte in ruta.parts
    )


def release(ruta: Path) -> bool:
    nombre = ruta.name.lower()
    modulo = nombre.split(".", 1)[0]
    if modulo.endswith("_d") or ruta.suffix.lower() in {".pdb", ".pyc", ".pyo"}:
        return False
    etiqueta = re.search(r"\.(cp[^.]+)\.", nombre)
    if etiqueta and etiqueta.group(1) != ABI:
        return False
    if ruta.suffix.lower() in {".pyd", ".dll", ".exe"}:
        if modulo.startswith(("_test", "test_")) or modulo.endswith(("_test", "_tests")):
            return False
    return not (nombre.startswith("test_") or nombre == "conftest.py")


def comprobar_ruta(ruta: Path, base: Path) -> None:
    """No seguir symlinks/junctions ni empaquetar contenido fuera de la fuente."""
    relativa = ruta.relative_to(base)
    actual = base
    for parte in ("", *relativa.parts):
        actual = actual / parte if parte else actual
        if actual.is_symlink() or actual.is_junction():
            raise ValueError(f"Enlace no permitido: {actual}")
    if not ruta.resolve().is_relative_to(base.resolve()):
        raise ValueError(f"Ruta fuera de la fuente: {ruta}")


def recorrer(directorio: Path, base: Path):
    comprobar_ruta(directorio, base)
    if not directorio.is_dir():
        raise FileNotFoundError(f"Falta directorio requerido: {directorio}")
    for ruta in sorted(directorio.iterdir(), key=lambda p: p.name.casefold()):
        if ruta.name.lower() in OMITIR_DIRECTORIOS:
            continue
        comprobar_ruta(ruta, base)
        if ruta.is_dir():
            yield from recorrer(ruta, base)
        elif ruta.is_file() and release(ruta):
            yield ruta


def seleccionar() -> dict[str, Path]:
    archivos: dict[str, Path] = {}
    nombres: set[str] = set()

    def agregar(ruta: Path, base: Path, prefijo: str) -> None:
        comprobar_ruta(ruta, base)
        if not ruta.is_file():
            raise FileNotFoundError(f"Falta archivo requerido: {ruta}")
        nombre = prefijo + "/" + ruta.relative_to(base).as_posix()
        if nombre.casefold() in nombres:
            raise ValueError(f"Entrada ZIP duplicada: {nombre}")
        nombres.add(nombre.casefold())
        archivos[nombre] = ruta

    for nombre in PYTHON_RAIZ:
        agregar(PYTHON_BASE / nombre, PYTHON_BASE, "python")
    runtimes = sorted(p for p in PYTHON_BASE.glob("vcruntime*.dll") if release(p))
    if not runtimes:
        raise FileNotFoundError("No hay vcruntime*.dll release en el Python base")
    for ruta in runtimes:
        agregar(ruta, PYTHON_BASE, "python")

    for ruta in recorrer(PYTHON_BASE / "DLLs", PYTHON_BASE):
        if ruta.suffix.lower() not in {".dll", ".pyd"}:
            continue
        if ruta.name.lower().startswith(("_tkinter", "tcl", "tk", "libtommath")):
            continue
        agregar(ruta, PYTHON_BASE, "python")

    lib = PYTHON_BASE / "Lib"
    for ruta in recorrer(lib, PYTHON_BASE):
        relativa = ruta.relative_to(lib)
        if ruta.name.lower() in {"sitecustomize.py", "usercustomize.py"}:
            continue
        if (ruta.suffix.lower() in EXTENSIONES_STDLIB
                or relativa.as_posix() in VENV_RECURSOS or licencia(relativa)):
            agregar(ruta, PYTHON_BASE, "python")

    site = lib / "site-packages"
    for nombre in SITE_DIRECTORIOS:
        seleccionados = 0
        for ruta in recorrer(site / nombre, PYTHON_BASE):
            relativa = ruta.relative_to(site)
            # comtypes/gen contiene wrappers generados en esta máquina. Mantener
            # solo el inicializador para regenerarlos en el equipo de destino.
            if relativa.parts[:2] == ("comtypes", "gen") and relativa.as_posix() != "comtypes/gen/__init__.py":
                continue
            if (ruta.suffix.lower() in EXTENSIONES_RUNTIME or ruta.name == "py.typed"
                    or relativa.as_posix() in RECURSOS_SITE or licencia(relativa)):
                agregar(ruta, PYTHON_BASE, "python")
                seleccionados += 1
        if not seleccionados:
            raise ValueError(f"Paquete permitido sin archivos de runtime: {nombre}")
    for nombre in SITE_MODULOS:
        agregar(site / nombre, PYTHON_BASE, "python")
    for patron in SITE_BINARIOS:
        coincidencias = sorted(p for p in site.glob(patron) if release(p))
        if not coincidencias:
            raise FileNotFoundError(f"Falta extensión release {ABI}: {patron}")
        for ruta in coincidencias:
            agregar(ruta, PYTHON_BASE, "python")

    # Nombre de distribución normalizado, no un prefijo abierto (numpy != numpy_extra).
    for nombre in DISTRIBUCIONES:
        coincidencias = [
            p for p in site.glob("*.dist-info")
            if re.sub(r"[-_.]+", "_", p.name.split("-", 1)[0].lower()) == nombre
        ]
        if len(coincidencias) != 1:
            raise ValueError(f"Se esperaba un único dist-info de {nombre}: {coincidencias}")
        for ruta in recorrer(coincidencias[0], PYTHON_BASE):
            # direct_url puede revelar rutas locales o credenciales de instalación.
            if ruta.name.lower() != "direct_url.json":
                agregar(ruta, PYTHON_BASE, "python")

    for nombre in CEREBRO_ARCHIVOS:
        agregar(CEREBRO_BASE / nombre, CEREBRO_BASE, "celebro_3D")
    # Fallar antes de escribir si faltan piezas básicas para arrancar el runtime.
    for nombre in (
        "python/Lib/os.py", "python/Lib/encodings/__init__.py",
        "python/Lib/site.py", "python/DLLs/_socket.pyd", "python/DLLs/_ssl.pyd",
        "python/DLLs/_ctypes.pyd", "python/DLLs/libssl-3.dll",
        "python/DLLs/libcrypto-3.dll", "python/DLLs/libffi-8.dll",
        "python/Lib/site-packages/certifi/cacert.pem",
    ):
        if nombre not in archivos:
            raise FileNotFoundError(f"Runtime incompleto: {nombre}")
    return dict(sorted(archivos.items()))


def escribir(zip_salida: zipfile.ZipFile, nombre: str, contenido: bytes) -> None:
    # Orden y fecha fijos: las mismas fuentes producen el mismo ZIP.
    entrada = zipfile.ZipInfo(nombre, date_time=(1980, 1, 1, 0, 0, 0))
    entrada.create_system = 3
    entrada.external_attr = 0o100644 << 16
    zip_salida.writestr(
        entrada, contenido, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9,
    )


def main() -> None:
    archivos = seleccionar()
    manifiesto = {
        "schema_version": 1,
        "version": VERSION,
        "python_abi": ABI,
        "hash_algorithm": "SHA256",
        "files": [],
    }
    temporal: Path | None = None
    try:
        # Publicación atómica: un fallo no sustituye el ZIP anterior.
        with tempfile.NamedTemporaryFile(
            dir=SALIDA.parent, prefix="lucia_runtime_", suffix=".tmp", delete=False,
        ) as fichero:
            temporal = Path(fichero.name)
        with zipfile.ZipFile(temporal, "w", allowZip64=True) as paquete:
            for nombre, fuente in archivos.items():
                contenido = fuente.read_bytes()
                escribir(paquete, nombre, contenido)
                manifiesto["files"].append({
                    "path": nombre,
                    "size": len(contenido),
                    "sha256": hashlib.sha256(contenido).hexdigest(),
                })
            escribir(paquete, "manifest.json", (
                json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8"))
        with zipfile.ZipFile(temporal, "r") as paquete:
            if paquete.namelist() != [*archivos, "manifest.json"]:
                raise ValueError("El ZIP no coincide con la allowlist seleccionada")
            for entrada in manifiesto["files"]:
                contenido = paquete.read(entrada["path"])
                if (len(contenido) != entrada["size"]
                        or hashlib.sha256(contenido).hexdigest() != entrada["sha256"]):
                    raise ValueError(f"Verificación SHA256 fallida: {entrada['path']}")
        os.replace(temporal, SALIDA)
        temporal = None
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)

    total = sum(entrada["size"] for entrada in manifiesto["files"])
    print(f"Creado: {SALIDA}")
    print(f"v{VERSION} / {ABI}: {len(archivos)} archivos + manifest.json")
    print(f"Sin comprimir: {total / 1024**2:.2f} MiB; ZIP: {SALIDA.stat().st_size / 1024**2:.2f} MiB")
    print("Site-packages: " + ", ".join(sorted({
        nombre.split("/")[3] for nombre in archivos
        if nombre.startswith("python/Lib/site-packages/")
    })))
    print(f"Cerebro canónico: {len(CEREBRO_ARCHIVOS)} archivos .py; sin modelos ni datos de usuario")


if __name__ == "__main__":
    main()
