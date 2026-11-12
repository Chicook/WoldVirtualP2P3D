"""Puerta headless de Godot (DT-05).

Ejecuta las pruebas `probar_*.gd` / `validar_*.gd` del taller con el motor real y
falla si el veredicto no es cero, si el motor tira un `SCRIPT ERROR` o si el
veredicto no trae evidencia. Las tres cosas se midieron necesarias el 2026-11-05:

- `probar_cara`, `probar_cuerpo` y `probar_personalizacion` salian con 0 tras
  volcar `Cannot call method 'save_png' on a null value`: verde silencioso.
- `probar_registro` y `probar_flujo_portal` salen con 0 con un
  `SCRIPT ERROR: Trying to assign value of type 'Nil' to a variable of type
  'PackedInt32Array'` dentro (Personalizacion.gd:952).
- `validar_anim_glb` sale con 0 habiendo visto `0 modelos`.

El modo (arbol o PCK) no se repite aqui: lo dicta `herramientas.PCK_OBLIGATORIO`
y su evidencia esta en `medicion_modos.py`. Sin motor ni PCK la puerta se omite,
no se falsea.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SRC_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SRC_DIR))

import pytest  # noqa: E402

from STM_HRTS.utils.add_utils import herramientas, rutas  # noqa: E402

# Una prueba de Godot no puede colgarse llevandose la suite por delante.
TIMEOUT = float(os.environ.get("WVP3D_GODOT_TIMEOUT", "120"))

# Cero o mas fallos, en las tres ortografias que usan los guiones:
# `fallos=2`, `24 con fallo`, `0 FALLOS`, `41 líneas, 0 fallos`.
CUENTAS_FALLOS = (
    re.compile(r"fallos\s*=\s*(\d+)"),
    re.compile(r"(\d+)\s+(?:FALLOS|con fallo)"),
    re.compile(r"(\d+)\s+[Ff]allos\b"),
)
# Lo que el guion miro de verdad: sin evidencia un `fallos=0` no dice nada.
CUENTAS_EVIDENCIA = (
    re.compile(r"(\d+)\s+OK\b"),
    re.compile(r"(\d+)\s+(?:avatares|escenas|modelos|l[íi]neas)"),
)
LINEA_VEREDICTO = re.compile(r"fallo", re.IGNORECASE)
# Falla de CODIGO, no de entorno. Los `Cannot open file` / `Failed loading
# resource` y los `Parse Error: [ext_resource] referenced non-existent resource`
# se dejan fuera a proposito: el arbol del taller no trae `.godot/imported`
# (esta en .gitignore), asi que en modo arbol son ruido esperado — y son
# precisamente la razon de los nueve modos PCK de la matriz.
ERROR_DE_MOTOR = re.compile(r"SCRIPT ERROR:|Parse Error:")
RUIDO_DE_CARGA = re.compile(r"\[ext_resource\] referenced non-existent resource")


class Veredicto:
    def __init__(self, codigo: int, salida: str, linea: Optional[str],
                 fallos: Optional[int], evidencia: Optional[int]) -> None:
        self.codigo = codigo
        self.salida = salida
        self.linea = linea
        self.fallos = fallos
        self.evidencia = evidencia

    @property
    def errores_de_motor(self) -> List[str]:
        return [
            l.strip() for l in self.salida.splitlines()
            if ERROR_DE_MOTOR.search(l) and not RUIDO_DE_CARGA.search(l)
        ]

    def __str__(self) -> str:
        detalle = self.linea or "(sin linea de veredicto)"
        return f"salida {self.codigo} · {detalle}"


def analizar(codigo: int, salida: str) -> Veredicto:
    """Veredicto de una prueba: ultima linea con «fallo», sus dos contadoras."""
    lineas = [l for l in salida.splitlines() if LINEA_VEREDICTO.search(l)]
    ultima = lineas[-1].strip() if lineas else None
    fallos: Optional[int] = None
    evidencia: Optional[int] = None
    if ultima:
        cuentas = [int(m) for patron in CUENTAS_FALLOS for m in patron.findall(ultima)]
        if cuentas:
            fallos = max(cuentas)
        vistas = [int(m) for patron in CUENTAS_EVIDENCIA for m in patron.findall(ultima)]
        if vistas:
            evidencia = max(vistas)
    return Veredicto(codigo, salida, ultima, fallos, evidencia)


def ejecutar(nombre: str, extra: Tuple[str, ...] = ()) -> Veredicto:
    plan = herramientas.comando(nombre, extra)
    with tempfile.TemporaryDirectory(prefix="wvp3d_godot_") as caja:
        archivo = Path(caja) / f"{nombre}.txt"
        with open(archivo, "wb") as destino:
            try:
                proceso = subprocess.run(plan["argv"], cwd=plan["cwd"], env=plan["env"],
                                         stdout=destino, stderr=subprocess.STDOUT,
                                         timeout=TIMEOUT)
                codigo = proceso.returncode
            except subprocess.TimeoutExpired:
                codigo = 124
        salida = archivo.read_text(encoding="utf-8", errors="replace")
    return analizar(codigo, salida)


# -- client --peer-url=... es el uso documentado en el encabezado del propio
# guion: sin argumentos `resolver_objetivo()` no tiene invitacion que leer y las
# dos ultimas comprobaciones fallan (medido: fallos=2).
ARGUMENTOS: Dict[str, Tuple[str, ...]] = {
    "probar_red_invitacion": (
        "--client",
        "--peer-url=https://demo.trycloudflare.com/?invitacion=0123456789abcdef0123456789abcdef",
    ),
}

# Las 22 pruebas de Godot que condicionan su salida al contador de fallos
# (`emite_veredicto`). Las otras once —capturas puras y sondas— no tienen nada
# que comprobar desde CI y quedan registradas en el README_DESARROLLO §17.6.
PRUEBAS = (
    "probar_cambio_avatar", "probar_carrusel", "probar_carrusel_ocupado",
    "probar_construccion", "probar_control_clic", "probar_flujo_portal",
    "probar_ganchos", "probar_islas_fantasma", "probar_red", "probar_red_invitacion",
    "probar_red_puerto", "probar_registro", "probar_registro_islas",
    "probar_reparar_avatar", "probar_selector", "probar_shapekeys", "probar_turnos",
    "validar_anim_glb", "validar_avatares", "validar_ch3d", "validar_personalizacion",
    "validar_shapekeys_reales",
)

# Verde sin evidencia o verde con el motor llorando: se marcan para que la puerta
# siga en verde mientras el defecto este a la vista. `strict=True` convierte el
# dia que se arreglen en un fallo que obliga a quitar la marca.
DEFECTOS_CONOCIDOS = {
    "probar_registro": (
        "SCRIPT ERROR en Personalizacion.gd:952 (_vertices_cabeza asigna Nil a "
        "PackedInt32Array) con el PCK montado; el guion sale 0 igualmente. Medido 2026-11-05."
    ),
    "probar_flujo_portal": (
        "Mismo SCRIPT ERROR de Personalizacion.gd:952 al pasar por el portal; sale 0. Medido 2026-11-05."
    ),
    "validar_anim_glb": (
        "Recorre res://avtrnCRS/GTLF_GODOT/... en busca de `*_anim.glb` y no hay ninguno en este "
        "arbol ni en el PCK: «== 0 modelos, 0 con fallo ==». Verde que no comprueba nada. Medido 2026-11-05."
    ),
    "validar_personalizacion": (
        "Recorre 0 `Ch3D.tscn` con el PCK montado (el recuento se anadio al guion "
        "para que el verde dejara de ser ciego); desde el arbol falla contra los imports "
        "ausentes. fixture fuera del PCK exportado. Medido 2026-11-05."
    ),
}


def _casos():
    for nombre in PRUEBAS:
        marks = []
        if nombre in DEFECTOS_CONOCIDOS:
            marks.append(pytest.mark.xfail(strict=True, reason=DEFECTOS_CONOCIDOS[nombre]))
        yield pytest.param(nombre, marks=marks, id=nombre)


def _motor_oxigeno() -> None:
    if rutas.binario_godot() is None:
        pytest.skip("Godot no disponible (define GODOT_BIN)")


def test_cobertura_de_la_puerta():
    """La puerta lista todas las pruebas headless que condicionan su salida.

    Si alguien anade un `probar_*.gd` con veredicto y se olvida de meterlo aqui,
    esta prueba lo echa de menos: la cobertura no se pierde sola.
    """
    esperadas = {
        h.nombre for h in herramientas.catalogo()
        if h.tipo == "godot" and h.headless and herramientas.emite_veredicto(h.archivo)
    }
    assert esperadas == set(PRUEBAS), (
        "la puerta y el catalogo discrepan; solo en el catalogo: "
        f"{sorted(esperadas - set(PRUEBAS))}; solo en la puerta: "
        f"{sorted(set(PRUEBAS) - esperadas)}"
    )


@pytest.mark.godot
@pytest.mark.parametrize("nombre", list(_casos()))
def test_prueba_godot_headless(nombre: str) -> None:
    _motor_oxigeno()
    herramienta = herramientas.buscar(nombre)
    if herramienta.montar_pck and not rutas.PCK_EMBEBIDO.is_file():
        pytest.skip(f"{nombre} necesita el PCK exportado y no hay uno en {rutas.PCK_EMBEBIDO}")
    veredicto = ejecutar(nombre, ARGUMENTOS.get(nombre, ()))
    assert veredicto.linea is not None, f"{nombre}: no imprime veredicto ({veredicto.salida[-400:]})"
    assert not veredicto.errores_de_motor, (
        f"{nombre}: el motor reporto {len(veredicto.errores_de_motor)} errores\n"
        + "\n".join(veredicto.errores_de_motor[:6])
    )
    assert veredicto.fallos == 0, f"{nombre}: {veredicto}"
    assert veredicto.evidencia is None or veredicto.evidencia > 0, (
        f"{nombre}: veredicto sin evidencia ({veredicto.linea})"
    )
    assert veredicto.codigo == 0, f"{nombre}: salida {veredicto.codigo} con {veredicto}"
