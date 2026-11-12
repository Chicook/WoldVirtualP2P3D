"""Pruebas del troceado de código (issue #80, puntos 2 y 3)."""
from __future__ import annotations

import ast

from STM_RFPRMN_stmDL.stm_fragmentos import (
    MAX_SOLAPE, calcular_rangos, quitar_solape,
)

MINIMO = 60


def _modulo_sintetico(funciones: int = 12, cuerpo: int = 20) -> str:
    """Módulo Python de tamaño realista con funciones independientes."""
    lineas = ["import os", "", ""]
    for indice in range(funciones):
        lineas.append(f"def funcion_{indice}(x):")
        lineas.append(f'    """Documenta la función {indice}."""')
        for paso in range(cuerpo):
            lineas.append(f"    paso_{paso} = x + {paso}")
        lineas.append(f"    return paso_{cuerpo - 1}")
        lineas.append("")
        lineas.append("")
    return "\n".join(lineas)


def test_cada_fragmento_python_es_valido_por_si_mismo():
    contenido = _modulo_sintetico()
    lineas = contenido.splitlines()
    rangos = calcular_rangos(contenido, ".py", MINIMO)
    assert len(rangos) > 1, "un módulo largo debería dividirse"
    for inicio, fin in rangos:
        trozo = "\n".join(lineas[inicio - 1:fin])
        ast.parse(trozo)  # no debe lanzar


def test_los_rangos_cubren_todo_el_archivo_sin_huecos():
    contenido = _modulo_sintetico()
    rangos = calcular_rangos(contenido, ".py", MINIMO)
    assert rangos[0][0] == 1
    assert rangos[-1][1] == len(contenido.splitlines())
    for (_, fin), (siguiente, _) in zip(rangos, rangos[1:]):
        assert siguiente == fin + 1


def test_no_se_corta_entre_try_y_except():
    cuerpo = ["def procesar(datos):", "    try:", "        valor = datos[0]",
              "    except IndexError:", "        return None",
              "    finally:", "        datos.clear()", "    return valor", ""]
    relleno = [f"x_{i} = {i}" for i in range(70)]
    contenido = "\n".join(relleno + cuerpo)
    lineas = contenido.splitlines()
    for inicio, fin in calcular_rangos(contenido, ".py", MINIMO):
        ast.parse("\n".join(lineas[inicio - 1:fin]))


def test_sin_contenido_no_hay_fragmentos():
    assert calcular_rangos("   \n\n", ".py", MINIMO) == []


def test_fichero_corto_es_un_unico_fragmento():
    contenido = "def a():\n    return 1\n"
    assert calcular_rangos(contenido, ".py", MINIMO) == [(1, 2)]


def test_python_roto_usa_la_heuristica():
    contenido = "def roto(:\n    pass\n" + "\n".join(f"y{i} = {i}" for i in range(80))
    rangos = calcular_rangos(contenido, ".py", MINIMO)
    assert rangos and rangos[-1][1] == len(contenido.splitlines())


def test_quitar_solape_elimina_la_repeticion():
    previo = "def a():\n    x = 1\n    return x"
    actual = "    x = 1\n    return x\ndef b():\n    return 2"
    assert quitar_solape(previo, actual) == "def b():\n    return 2"


def test_quitar_solape_no_recorta_codigo_legitimo():
    previo = "def a():\n    return 1"
    actual = "def b():\n    return 1"
    assert quitar_solape(previo, actual) == actual


def test_quitar_solape_exige_dos_lineas():
    previo = "def a():\n    return 1"
    actual = "    return 1\ndef b():\n    return 2"
    assert quitar_solape(previo, actual) == actual


def test_maximo_de_solape_es_razonable():
    assert MAX_SOLAPE >= 5
