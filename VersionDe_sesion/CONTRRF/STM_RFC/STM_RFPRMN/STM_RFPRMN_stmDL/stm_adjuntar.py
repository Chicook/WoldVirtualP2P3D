"""
stm_adjuntar.py - Selector interactivo de archivos/directorios para LC Adjuntar
================================================================================
Proporciona un mini-navegador de terminal que permite seleccionar un archivo
individual o un directorio completo y enviar todos sus archivos de código válidos
a la red neuronal de LucIA mediante `comando_lc_entrenar`.

Comandos exportados:
  - selector_ruta_interactivo(directorio_base)  → Path | None
  - comando_lc_entrenar_adjuntar()              → None
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Final

from .stm_base import (
    MODULO_DIR,
    exito,
    informar,
    reportar_error,
)

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
SRC_DIR: Final[Path] = MODULO_DIR.parents[1] / "TLLDCD" / "src"
LCTRABAJANDO_DIR: Final[Path] = MODULO_DIR.parents[1] / "CONTRUCCION" / "LCtrabajando"

EXTENSIONES_VALIDAS: Final[tuple] = (
    ".py", ".gd", ".cs", ".md", ".json", ".tscn", ".tres",
    ".gdshader", ".xaml", ".csproj", ".ps1", ".bat", ".txt",
    ".js", ".ts", ".cpp", ".c", ".h", ".hpp", ".rs", ".go",
    ".java", ".sh", ".toml", ".yaml", ".yml", ".sql", ".cfg",
)

_INICIOS_RAPIDOS: Dict[str, Path] = {
    "1": LCTRABAJANDO_DIR,
    "2": SRC_DIR,
    "3": MODULO_DIR,
    "4": Path.cwd(),
}

# ─── SELECTOR DE RUTA ────────────────────────────────────────────────────────

def selector_ruta_interactivo(directorio_base: Optional[Path] = None) -> Optional[Path]:
    """Mini-navegador de terminal: carpeta/archivo.

    Controles:
      - Si se pasa un archivo directo, lo selecciona inmediatamente.
      - Número → navegar al subdirectorio o seleccionar archivo.
      - ``0`` / ``..`` → subir un nivel.
      - ``A`` / ``aqui`` → seleccionar el directorio actual completo.
      - Ruta directa → ir a esa ruta o archivo.
      - ``cancelar`` / Enter vacío → abortar y devolver None.

    Returns:
        Path seleccionado (archivo o directorio) o None si se canceló.
    """
    base = Path(directorio_base or Path.cwd())
    if not base.exists():
        reportar_error(f"La ruta no existe: {base}")
        return None

    # Si es directamente un archivo, lo seleccionamos sin intentar iterar directorio
    if base.is_file():
        informar(f"✔ Archivo detectado directamente: {base.name}")
        return base

    while True:
        try:
            entradas = sorted(
                base.iterdir(),
                key=lambda p: (p.is_file(), p.name.lower()),
            )
        except (PermissionError, OSError) as err:
            reportar_error(f"Error al leer '{base}': {err}")
            return None

        # Cabecera
        print(f"\n📁  {base}")
        print("─" * min(80, len(str(base)) + 6))
        print("  [ 0]  ..  (subir un nivel)")
        print("  [ A]  ★   Seleccionar ESTE directorio completo")

        mostrar = entradas[:20]
        for idx, entrada in enumerate(mostrar, start=1):
            icono = "📄" if entrada.is_file() else "📂"
            print(f"  [{idx:2d}]  {icono}  {entrada.name}")
        if len(entradas) > 20:
            print(f"  … y {len(entradas) - 20} entradas más. Escribe el nombre exacto.")

        print()
        print("  Opciones: número, nombre/ruta directa, '..' , 'aqui', 'cancelar'")
        try:
            respuesta = input("› ").strip()
        except (KeyboardInterrupt, EOFError):
            informar("Selección cancelada.")
            return None

        if not respuesta or respuesta.lower() == "cancelar":
            informar("Selección cancelada.")
            return None

        resp_lower = respuesta.lower()

        if resp_lower in ("aqui", "aquí", "a"):
            informar(f"✔ Directorio seleccionado: {base}")
            return base

        if respuesta == "0" or resp_lower == "..":
            base = base.parent
            continue

        # Número de lista
        if respuesta.isdigit():
            n = int(respuesta)
            if 1 <= n <= len(mostrar):
                elegido = mostrar[n - 1]
                if elegido.is_file():
                    informar(f"✔ Archivo seleccionado: {elegido.name}")
                    return elegido
                base = elegido
                continue
            reportar_error(f"Número fuera de rango (1–{len(mostrar)}).")
            continue

        # Ruta directa o nombre de entrada
        candidato = Path(respuesta.strip("\"'"))
        if not candidato.is_absolute():
            candidato = base / candidato
        if candidato.exists():
            if candidato.is_file():
                informar(f"✔ Archivo seleccionado: {candidato.name}")
                return candidato
            else:
                informar(f"📂 Navegando a directorio: {candidato}")
                base = candidato
                continue
        reportar_error(f"No existe '{respuesta}'. Prueba de nuevo o escribe 'cancelar'.")


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def archivos_de_ruta(ruta: Path) -> List[Path]:
    """Devuelve lista de archivos válidos dado un archivo o directorio."""
    if ruta.is_file():
        return [ruta]
    return sorted(
        f for f in ruta.rglob("*")
        if f.is_file() and f.suffix.lower() in EXTENSIONES_VALIDAS
    )


def _mostrar_inicios() -> None:
    print("  Directorios de inicio rápido:")
    for clave, ruta in _INICIOS_RAPIDOS.items():
        estado = ruta.name if ruta.exists() else "⚠ no existe"
        print(f"  [{clave}]  {ruta}  ({estado})")
    print("  [0]  Escribir ruta manualmente (archivo o carpeta)")
    print()


def _elegir_base() -> Optional[Path]:
    """Pide al usuario el directorio o archivo de inicio del selector."""
    _mostrar_inicios()
    try:
        opcion = input("› Inicio: ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not opcion:
        return None

    if opcion in _INICIOS_RAPIDOS:
        base = _INICIOS_RAPIDOS[opcion]
        return base if base.exists() else Path.cwd()

    if opcion == "0":
        try:
            ruta_manual = input("› Ruta: ").strip().strip("\"'")
        except (KeyboardInterrupt, EOFError):
            return None
        if not ruta_manual:
            return None
        p = Path(ruta_manual)
        if not p.exists():
            reportar_error(f"La ruta no existe: {p}")
            return None
        return p

    p = Path(opcion.strip("\"'"))
    if not p.exists():
        reportar_error(f"La ruta no existe: {p}")
        return None
    return p


# ─── COMANDO PÚBLICO ─────────────────────────────────────────────────────────

def comando_lc_entrenar_adjuntar() -> None:
    """Comando 'LC adjuntar': selector interactivo + entrenamiento de la red neuronal.

    Permite elegir un archivo suelto o un directorio completo; en caso de directorio
    escanea recursivamente todos los archivos de código válidos y lanza
    ``comando_lc_entrenar`` por cada uno de ellos.
    """
    from .stm_cli import comando_lc_entrenar  # import local para evitar ciclo

    print()
    informar("LC Adjuntar · Selector para entrenamiento neuronal de LucIA")
    print()

    base = _elegir_base()
    if base is None:
        return
    ruta_elegida = selector_ruta_interactivo(base)
    if ruta_elegida is None:
        return

    archivos = archivos_de_ruta(ruta_elegida)
    if not archivos:
        reportar_error(
            f"No se encontraron archivos de código válidos en: {ruta_elegida}"
        )
        return

    if len(archivos) == 1:
        comando_lc_entrenar(str(archivos[0]))
        return

    # Directorio: confirmación previa
    informar(
        f"Se entrenarán {len(archivos)} archivo(s) del directorio «{ruta_elegida.name}»:"
    )
    for f in archivos[:10]:
        print(f"    · {f.relative_to(ruta_elegida) if ruta_elegida.is_dir() else f.name}")
    if len(archivos) > 10:
        print(f"    … y {len(archivos) - 10} más.")

    try:
        confirm = input("› ¿Continuar con todos? (s/n) ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        informar("Cancelado.")
        return
    if confirm not in ("s", "si", "sí", "y", "yes"):
        informar("Cancelado.")
        return

    total_ok = 0
    for idx, archivo in enumerate(archivos, start=1):
        informar(f"[{idx}/{len(archivos)}] Entrenando: {archivo.name}")
        res = comando_lc_entrenar(str(archivo))
        if res.get("ok"):
            total_ok += 1

    exito(f"Entrenamiento completado: {total_ok}/{len(archivos)} archivos procesados correctamente.")
