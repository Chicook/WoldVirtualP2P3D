"""Pruebas del comando «informacion codigo» y de su informe."""
from __future__ import annotations

import builtins

import pytest

from STM_RFPRMN_stmDL import stm_informe
from STM_RFPRMN_stmDL.stm_base import ErrorProyecto

LIMPIO = '''"""Módulo limpio."""


def sumar(a: int, b: int) -> int:
    """Suma dos enteros."""
    return a + b
'''

SUCIO = '''def f(a=[]):
    try:
        return a[0]
    except:
        return None
'''


def _grande() -> str:
    """Módulo de 600 líneas para probar el aviso de partición."""
    piezas = ['"""Grande."""']
    for indice in range(24):
        cuerpo = "\n".join(f"    x{i} = {i}" for i in range(24))
        piezas.append(f"def funcion_{indice}():\n{cuerpo}\n    return x0\n")
    return "\n\n".join(piezas)


@pytest.fixture
def destino(tmp_path, monkeypatch):
    """Aísla STM_DOC en el directorio temporal de la prueba."""
    carpeta = tmp_path / "STM_DOC"
    carpeta.mkdir()
    monkeypatch.setattr(stm_informe, "DIR_DOCS", carpeta)
    return carpeta


# --- Construcción ------------------------------------------------------------

def test_el_informe_trae_informacion_del_codigo(tmp_path):
    archivo = tmp_path / "limpio.py"
    archivo.write_text(LIMPIO, encoding="utf-8")
    texto = stm_informe.construir_informe(archivo)
    assert "# Informe de código · limpio.py" in texto
    assert "limpio.py" in texto and "`.py`" in texto
    assert "1 funciones" in texto and "Sintaxis**: válida" in texto


def test_la_estructura_lista_clases_y_funciones(tmp_path):
    archivo = tmp_path / "limpio.py"
    archivo.write_text(LIMPIO, encoding="utf-8")
    texto = stm_informe.construir_informe(archivo)
    assert "| funcion | `sumar` |" in texto


def test_la_deuda_aparece_con_sus_descuentos(tmp_path):
    archivo = tmp_path / "sucio.py"
    archivo.write_text(SUCIO, encoding="utf-8")
    texto = stm_informe.construir_informe(archivo)
    assert "## Deuda técnica" in texto
    assert "funciones sin docstring" in texto
    assert "capturas genéricas" in texto


def test_un_archivo_sano_dice_que_lo_es(tmp_path):
    archivo = tmp_path / "limpio.py"
    archivo.write_text(LIMPIO, encoding="utf-8")
    assert "está sano" in stm_informe.construir_informe(archivo)


def test_la_hoja_de_ruta_incluye_documentar(tmp_path):
    archivo = tmp_path / "sucio.py"
    archivo.write_text(SUCIO, encoding="utf-8")
    texto = stm_informe.construir_informe(archivo)
    assert "## Hoja de ruta" in texto
    assert "comentar archivo" in texto


def test_la_hoja_de_ruta_incluye_partir_si_es_grande(tmp_path):
    archivo = tmp_path / "grande.py"
    archivo.write_text(_grande(), encoding="utf-8")
    texto = stm_informe.construir_informe(archivo)
    assert "Partir el archivo" in texto
    assert "CONTRUCCION" in texto


def test_la_hoja_de_ruta_incluye_lint(tmp_path):
    archivo = tmp_path / "sucio.py"
    archivo.write_text(SUCIO, encoding="utf-8")
    texto = stm_informe.construir_informe(archivo)
    assert "lint" in texto.lower()


def test_incluye_el_diagnostico_de_lucia_si_hay_consultor(tmp_path):
    archivo = tmp_path / "limpio.py"
    archivo.write_text(LIMPIO, encoding="utf-8")

    def _consultor(_contenido, _analisis):
        return "LucIA: el archivo está claro."

    texto = stm_informe.construir_informe(archivo, consultor=_consultor)
    assert "## Diagnóstico de LucIA" in texto
    assert "el archivo está claro" in texto


def test_sin_consultor_no_hay_seccion_de_lucia(tmp_path):
    archivo = tmp_path / "limpio.py"
    archivo.write_text(LIMPIO, encoding="utf-8")
    assert "Diagnóstico de LucIA" not in stm_informe.construir_informe(archivo)


def test_si_lucia_falla_el_informe_sigue(tmp_path):
    archivo = tmp_path / "limpio.py"
    archivo.write_text(LIMPIO, encoding="utf-8")

    def _rompe(_contenido, _analisis):
        raise RuntimeError("sin modelo")

    texto = stm_informe.construir_informe(archivo, consultor=_rompe)
    assert "no respondió" in texto


# --- Escritura ---------------------------------------------------------------

def test_escribe_el_md_en_stm_doc(tmp_path, destino):
    archivo = tmp_path / "sucio.py"
    archivo.write_text(SUCIO, encoding="utf-8")
    salida = stm_informe.generar_informe(archivo)
    assert salida == destino / "informe_sucio.md"
    assert "## Hoja de ruta" in salida.read_text(encoding="utf-8")


def test_archivo_inexistente_no_escribe(tmp_path, destino):
    assert stm_informe.generar_informe(tmp_path / "nada.py") is None
    assert not list(destino.iterdir())


def test_un_archivo_sin_python_no_rompe(tmp_path, destino):
    archivo = tmp_path / "x.cs"
    archivo.write_text("class A { void M() { } }\n", encoding="utf-8")
    salida = stm_informe.generar_informe(archivo)
    assert salida is not None and salida.is_file()


def test_el_comando_pide_el_archivo(tmp_path, destino, monkeypatch):
    archivo = tmp_path / "limpio.py"
    archivo.write_text(LIMPIO, encoding="utf-8")
    entradas = iter([str(archivo), "n"])  # sin diagnóstico de LucIA
    monkeypatch.setattr(builtins, "input", lambda *_a: next(entradas))
    monkeypatch.setattr(stm_informe, "pedir_confirmacion", lambda *_a: False)
    stm_informe.comando_informacion_codigo()
    assert (destino / "informe_limpio.md").is_file()


def test_el_comando_avisa_si_no_hay_ruta(monkeypatch):
    errores: list[str] = []
    monkeypatch.setattr(builtins, "input", lambda *_a: "")
    monkeypatch.setattr(stm_informe, "reportar_error", errores.append)
    stm_informe.comando_informacion_codigo()
    assert errores and "archivo" in errores[0]


def test_construir_falla_si_no_se_puede_leer(tmp_path):
    with pytest.raises(ErrorProyecto):
        stm_informe.construir_informe(tmp_path / "no-existe.py")


# --- Envío a la IA de código, sin cortar -------------------------------------

def test_trocear_codigo_no_parte_unidades(tmp_path):
    codigo = _grande()
    bloques = stm_informe.trocear_codigo(codigo, maximo=1500)
    assert len(bloques) > 1
    for bloque in bloques:
        assert len(bloque) <= 1500 + 200
    # ninguna función se queda partida entre bloques
    enteras = sum(bloque.count("def funcion_") for bloque in bloques)
    assert enteras == 24


def test_trocear_codigo_conserva_todo(tmp_path):
    codigo = _grande()
    bloques = stm_informe.trocear_codigo(codigo, maximo=1500)
    for indice in range(24):
        assert any(f"def funcion_{indice}(" in bloque for bloque in bloques)


def test_analizar_con_ia_une_los_bloques(tmp_path, monkeypatch):
    archivo = tmp_path / "grande.py"
    archivo.write_text(_grande(), encoding="utf-8")
    monkeypatch.setattr(stm_informe, "_endpoint", lambda: "http://x")
    llamadas: list[str] = []

    def _pedir(_sistema, contenido, _modelo, _endpoint, num_predict=900):
        llamadas.append(contenido)
        return f"Analisis del bloque {len(llamadas)}"

    monkeypatch.setattr(stm_informe, "_pedir", _pedir)
    texto = stm_informe.analizar_con_ia(_grande(), archivo, "fake")
    assert texto.count("Analisis del bloque") == len(llamadas)
    assert all("def funcion_" in contenido for contenido in llamadas)


def test_faltantes_detecta_lo_que_falta():
    original = "La clase `Neurona` tiene 390 líneas y 35 funciones."
    assert stm_informe.faltantes(original, "La clase tiene líneas.") != []
    assert stm_informe.faltantes(original, original) == []


def test_reescribir_reintenta_si_faltan_detalles(monkeypatch):
    monkeypatch.setattr(stm_informe, "_endpoint", lambda: "http://x")
    original = "La clase `Neurona` tiene 390 líneas."
    respuestas = iter(["La clase tiene líneas.", "La clase `Neurona` tiene 390 líneas."])
    monkeypatch.setattr(stm_informe, "_pedir",
                        lambda *_a, **_k: next(respuestas))
    resultado = stm_informe.reescribir_con_lucia(original, "fake")
    assert resultado["completo"] is True
    assert "390" in resultado["texto"]


def test_reescribir_anota_lo_que_sigue_faltando(monkeypatch):
    monkeypatch.setattr(stm_informe, "_endpoint", lambda: "http://x")
    monkeypatch.setattr(stm_informe, "_pedir",
                        lambda *_a, **_k: "texto sin datos")
    resultado = stm_informe.reescribir_con_lucia(
        "La clase `Neurona` tiene 390 líneas.", "fake")
    assert resultado["completo"] is False
    assert resultado["faltantes"]


def test_el_informe_con_ia_lleva_la_redaccion_y_los_datos(tmp_path, destino, monkeypatch):
    archivo = tmp_path / "limpio.py"
    archivo.write_text(LIMPIO, encoding="utf-8")
    monkeypatch.setattr(stm_informe, "_modelo_codigo", lambda: "fake")
    monkeypatch.setattr(stm_informe, "_endpoint", lambda: "http://x")
    monkeypatch.setattr(stm_informe, "_pedir",
                        lambda *_a, **_k: "Lucia: el modulo esta claro y sano.")
    salida = stm_informe.generar_informe(archivo, con_ia=True)
    texto = salida.read_text(encoding="utf-8")
    assert "Redactado por LucIA" in texto
    assert "el modulo esta claro" in texto
    assert "## Datos objetivos" in texto


def test_sin_ia_el_informe_sale_completo_igual(tmp_path, destino, monkeypatch):
    archivo = tmp_path / "limpio.py"
    archivo.write_text(LIMPIO, encoding="utf-8")
    monkeypatch.setattr(stm_informe, "_modelo_codigo", lambda: "")
    salida = stm_informe.generar_informe(archivo, con_ia=True)
    texto = salida.read_text(encoding="utf-8")
    assert "## Hoja de ruta" in texto and "## Deuda técnica" in texto
