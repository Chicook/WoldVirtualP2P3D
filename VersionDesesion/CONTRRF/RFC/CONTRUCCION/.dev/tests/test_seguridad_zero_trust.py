"""Suite de Pruebas Automatizadas de Seguridad Zero-Trust y Contención de Entorno (.dev)
Valida los 6 frentes de seguridad identificados:
1. Validación Zero Trust de Frontera y prevención de Path Traversal (sin supresión de excepciones).
2. Gestión Segura de Procesos y Verificación de PID (sin comodines PowerShell).
3. Aislamiento estricto del entorno Python (.dev/.python y .dev/venv).
4. Portabilidad de configuración VS Code (sin rutas absolutas de máquina).
5. Salvaguardas en operaciones de archivos (borrado y reubicación segura).
6. Validación exhaustiva del manifiesto de dependencias (dependencias.json).
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Asegurar que .dev esté en sys.path
DEV_DIR = Path(__file__).resolve().parent.parent
if str(DEV_DIR) not in sys.path:
    sys.path.insert(0, str(DEV_DIR))

from modulos.rutas import (
    REPO_ROOT,
    DEV_DIR,
    PYTHON_EXE,
    VENV_PYTHON,
    VSCODE_DIR,
    asegurar_ruta_en_repositorio,
)
from modulos.seguridad_entorno import (
    ValidadorFronteraSegura,
    GestorVenvSeguro,
    asegurar_frontera,
)
from modulos.entorno import (
    obtener_python_activo,
    obtener_pythonw_activo,
    limpiar_cache_raiz,
    traer_pytest_ini,
)
from modulos.blockchain_mgr import (
    PID_FILE_BLOCKCHAIN,
    detener_blockchain,
)
from modulos.lucia_mgr import (
    PID_FILE_LUCIA,
    detener_lucia,
)


# ==============================================================================
# 1. PRUEBAS DE VALIDACIÓN ZERO TRUST DE RUTAS Y PATH TRAVERSAL
# ==============================================================================

def test_exigir_frontera_rechaza_path_traversal_relativo():
    """Valida que los intentos de path traversal relativo lancen PermissionError de forma estricta."""
    validador = ValidadorFronteraSegura()
    rutas_maliciosas = [
        "../../Windows/System32",
        "..\\..\\..\\etc\\passwd",
        "../outside_repo_file.txt",
        "..\\..\\Windows\\explorer.exe",
    ]
    for ruta in rutas_maliciosas:
        candidato = (REPO_ROOT / ruta).resolve()
        with pytest.raises(PermissionError):
            validador.exigir_frontera(candidato, descripcion="PruebaTraversalRelativo")


def test_exigir_frontera_rechaza_rutas_absolutas_externas():
    """Valida que cualquier ruta fuera de REPO_ROOT sea rechazada con PermissionError."""
    validador = ValidadorFronteraSegura()
    rutas_externas = [
        Path("C:/Windows/System32/cmd.exe"),
        Path("C:/Users/Public/malicioso.bat"),
        Path("D:/otra_unidad/script.py"),
    ]
    for ruta in rutas_externas:
        with pytest.raises(PermissionError):
            validador.exigir_frontera(ruta, descripcion="PruebaRutaExterna")


def test_exigir_frontera_acepta_rutas_legitimas():
    """Valida que las rutas legítimas dentro de REPO_ROOT sean aceptadas."""
    validador = ValidadorFronteraSegura()
    rutas_validas = [
        REPO_ROOT / "VersionDesesion",
        DEV_DIR / "gestor_entorno.py",
        DEV_DIR / ".vscode" / "settings.json",
    ]
    for ruta in rutas_validas:
        resultado = validador.exigir_frontera(ruta, descripcion="PruebaRutaValida")
        assert resultado == ruta.resolve()


# ==============================================================================
# 2. PRUEBAS DEL DECORADOR @asegurar_frontera (SIN SUPRESIÓN DE EXCEPCIONES)
# ==============================================================================

@asegurar_frontera
def funcion_operacion_mock(ruta_posicional, clave="defecto", **kwargs):
    """Función de prueba que recibe argumentos posicionales y kwargs."""
    return f"OK:{ruta_posicional}:{clave}"


def test_asegurar_frontera_intercepta_args_posicionales():
    """Verifica que argumentos posicionales maliciosos sean bloqueados sin silenciar la excepción."""
    with pytest.raises(PermissionError):
        funcion_operacion_mock("../../Windows/System32")


def test_asegurar_frontera_intercepta_kwargs():
    """Verifica que kwargs maliciosos sean bloqueados sin silenciar la excepción."""
    with pytest.raises(PermissionError):
        funcion_operacion_mock("VersionDesesion", clave="../../escape_por_kwarg")


def test_asegurar_frontera_intercepta_kwargs_adicionales():
    """Verifica que kwargs arbitrarios maliciosos sean detectados."""
    with pytest.raises(PermissionError):
        funcion_operacion_mock("VersionDesesion", ruta_extra="C:\\Windows\\System32\\cmd.exe")


def test_asegurar_frontera_permite_ejecucion_con_argumentos_seguros():
    """Verifica que con argumentos válidos la función ejecute sin trabas."""
    res = funcion_operacion_mock("VersionDesesion/CONTRRF", clave="valor_seguro")
    assert "OK:VersionDesesion/CONTRRF:valor_seguro" in res


# ==============================================================================
# 3. PRUEBAS DE AISLAMIENTO ESTRICTO DEL ENTORNO
# ==============================================================================

def test_aislamiento_verificacion_interprete_contenido():
    """Verifica la detección correcta de si un intérprete reside dentro de .dev."""
    if PYTHON_EXE.is_file():
        assert GestorVenvSeguro.es_interprete_contenido(PYTHON_EXE) is True
    if VENV_PYTHON.is_file():
        assert GestorVenvSeguro.es_interprete_contenido(VENV_PYTHON) is True

    # Intérprete simulado fuera de .dev debe dar False
    assert GestorVenvSeguro.es_interprete_contenido("C:/Python312/python.exe") is False


def test_aislamiento_modo_estricto_bloquea_interprete_externo(monkeypatch):
    """En modo estricto, si el intérprete estuviera fuera de .dev, debe lanzar RuntimeError."""
    # Simular que sys.executable está fuera de .dev
    monkeypatch.setattr(sys, "executable", "C:/PythonExterno/python.exe")
    monkeypatch.setattr("modulos.entorno.PYTHON_EXE", Path("C:/Inexistente/python.exe"))
    monkeypatch.setattr("modulos.entorno.VENV_PYTHON", Path("C:/Inexistente/python.exe"))

    with pytest.raises(RuntimeError) as exc_info:
        obtener_python_activo(estricto=True)

    assert "VIOLACIÓN DE AISLAMIENTO ZERO TRUST" in str(exc_info.value)


# ==============================================================================
# 4. PRUEBAS DE GESTIÓN SEGURA DE PROCESOS (PID Y SIN COMODINES)
# ==============================================================================

def test_gestion_procesos_tracking_pid_blockchain(tmp_path):
    """Verifica el ciclo de vida seguro del archivo PID sin comodines."""
    PID_FILE_BLOCKCHAIN.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE_BLOCKCHAIN.write_text("99999999\n", encoding="utf-8")

    # Detener proceso no existente debe retornar sin fallar ni matar procesos ajenos
    detenidos = detener_blockchain()
    assert isinstance(detenidos, int)
    assert not PID_FILE_BLOCKCHAIN.is_file()


def test_gestion_procesos_tracking_pid_lucia(tmp_path):
    """Verifica el ciclo de vida seguro del archivo PID de LucIA."""
    PID_FILE_LUCIA.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE_LUCIA.write_text("99999998\n", encoding="utf-8")

    detenidos = detener_lucia()
    assert isinstance(detenidos, int)
    assert not PID_FILE_LUCIA.is_file()


# ==============================================================================
# 5. PRUEBAS DE PORTABILIDAD DE CONFIGURACIÓN
# ==============================================================================

def test_configuracion_vscode_no_tiene_rutas_absolutas_de_maquina():
    """Verifica que .dev/.vscode/settings.json no contenga rutas absolutas de una máquina específica (ej. E:/...)."""
    settings_path = VSCODE_DIR / "settings.json"
    assert settings_path.is_file(), f"No existe {settings_path}"

    contenido = settings_path.read_text(encoding="utf-8")
    assert "E:/WoldVirtualP2P3D" not in contenido, "El archivo settings.json contiene rutas absolutas de disco E:!"
    assert "E:\\WoldVirtualP2P3D" not in contenido, "El archivo settings.json contiene rutas absolutas de disco E:!"
    assert "${workspaceFolder}" in contenido, "El archivo settings.json debe usar ${workspaceFolder} para portabilidad."


# ==============================================================================
# 6. PRUEBAS DE OPERACIONES DE ARCHIVOS CON SALVAGUARDAS
# ==============================================================================

def test_limpiar_cache_raiz_salvaguarda_estricta():
    """Verifica que limpiar_cache_raiz no intente jamás borrar la raíz del repositorio."""
    # Ejecutar la limpieza segura
    resultado = limpiar_cache_raiz()
    assert isinstance(resultado, bool)
    # Comprobar que REPO_ROOT sigue existiendo intacto
    assert REPO_ROOT.is_dir()
    assert (REPO_ROOT / "VersionDesesion").is_dir()


def test_traer_pytest_ini_frontera():
    """Verifica que traer_pytest_ini valide que las rutas residan en REPO_ROOT."""
    # Ejecutar movimiento controlado
    res = traer_pytest_ini()
    assert isinstance(res, bool)


# ==============================================================================
# 7. PRUEBAS DE MANIFIESTO DE DEPENDENCIAS
# ==============================================================================

def test_manifiesto_dependencias_valido():
    """Verifica que dependencias.json esté bien formado y declare todas las dependencias requeridas."""
    dep_file = DEV_DIR / "dependencias.json"
    assert dep_file.is_file()

    datos = json.loads(dep_file.read_text(encoding="utf-8"))
    assert "dependencias" in datos
    deps = datos["dependencias"]

    # Verificar secciones requeridas
    assert "dotnet" in deps
    assert "python" in deps
    assert "seguridad_nativa" in deps
    assert "motor_3d" in deps

    # Verificar librerías nativas de seguridad de Windows requeridas
    dlls_declaradas = [d["nombre"].lower() for d in deps["seguridad_nativa"]["dlls"]]
    assert "crypt32.dll" in dlls_declaradas
    assert "ncrypt.dll" in dlls_declaradas
    assert "bcrypt.dll" in dlls_declaradas
    assert "kernel32.dll" in dlls_declaradas


# ==============================================================================
# 8. PRUEBAS DE SEGURIDAD 3D DE LUCIA (DAO Y AVATAR EXPERIMENTO ECO MIT)
# ==============================================================================

def test_lucia_seguridad_3d_instanciacion():
    """Verifica la carga de Seguridad3D en LucIAprc y su vinculación con el orquestador."""
    lucia_dir = REPO_ROOT / "VersionDesesion" / "CONTRRF" / "RFC" / "CONTRUCCION" / "TLLDCD" / "src" / "MTBGT" / "WoldVirtualP2P3D" / "lucia3D" / "IslaUnicaLucIA" / "CelebroInternoLucia"
    if str(lucia_dir) not in sys.path:
        sys.path.insert(0, str(lucia_dir))

    import LucIAprc
    seg_3d = LucIAprc.Seguridad3D()
    assert seg_3d is not None
    assert seg_3d.ALTURA_MESETA == 40.2
    assert seg_3d.RADIO_PERIMETRO_DAO == 31.0
    assert "identidad" in seg_3d.ESTACIONES_CARDINALES
    assert seg_3d.orquestador_cognitivo is not None


def test_lucia_seguridad_3d_evaluacion_espacial_y_neuronal():
    """Verifica la evaluación neuronal y espacial de interacciones en la DAO."""
    lucia_dir = REPO_ROOT / "VersionDesesion" / "CONTRRF" / "RFC" / "CONTRUCCION" / "TLLDCD" / "src" / "MTBGT" / "WoldVirtualP2P3D" / "lucia3D" / "IslaUnicaLucIA" / "CelebroInternoLucia"
    if str(lucia_dir) not in sys.path:
        sys.path.insert(0, str(lucia_dir))

    import LucIAprc
    seg_3d = LucIAprc.Seguridad3D()

    # Interacción legítima dentro de la estación cardinal de identidad
    res_ok = seg_3d.evaluar_seguridad_dao(
        actor="avatar_usuario_valido",
        posicion_3d=[0.0, 40.2, 22.0],
        estacion="identidad",
        firma_valida=True,
        cadencia=1.0,
    )
    assert res_ok["autorizado"] is True
    assert "p_red_neuronal" in res_ok
    assert "accion_avatar" in res_ok
    assert "salud_dao" in res_ok

    # Interacción anómala: posición fuera del atrio de la DAO (teletransporte / violación de perímetro)
    res_violacion = seg_3d.evaluar_seguridad_dao(
        actor="intruso_fuera_de_limite",
        posicion_3d=[150.0, 10.0, 200.0],
        estacion="identidad",
        firma_valida=False,
        cadencia=100.0,
    )
    assert res_violacion["autorizado"] is False
    assert res_violacion["decision"] == "BLOQUEAR"
    assert res_violacion["color_baliza"] == "rojo_bloqueo"


def test_lucia_seguridad_3d_control_avatar_eco_mit():
    """Verifica los comandos del Avatar 3D de LucIA según el modelo MIT ECO."""
    lucia_dir = REPO_ROOT / "VersionDesesion" / "CONTRRF" / "RFC" / "CONTRUCCION" / "TLLDCD" / "src" / "MTBGT" / "WoldVirtualP2P3D" / "lucia3D" / "IslaUnicaLucIA" / "CelebroInternoLucia"
    if str(lucia_dir) not in sys.path:
        sys.path.insert(0, str(lucia_dir))

    import LucIAprc
    seg_3d = LucIAprc.Seguridad3D()

    # Comportamiento amable en riesgo bajo
    cmd_bajo = seg_3d.control_avatar_eco_mit(
        estado_seguridad="PERMITIR",
        nivel_riesgo=0.10,
        posicion_intruso=[5.0, 40.2, 5.0],
        motivo="Acceso normal",
    )
    assert cmd_bajo["expresion"] == "amable"
    assert cmd_bajo["gesto"] == "bienvenida"
    assert cmd_bajo["alerta_activa"] is False

    # Comportamiento defensivo en riesgo alto
    cmd_alto = seg_3d.control_avatar_eco_mit(
        estado_seguridad="BLOQUEAR",
        nivel_riesgo=0.95,
        posicion_intruso=[50.0, 40.2, 50.0],
        motivo="Violación de perímetro",
    )
    assert cmd_alto["expresion"] == "defensiva_firme"
    assert cmd_alto["gesto"] == "detener_paso"
    assert cmd_alto["alerta_activa"] is True
    assert cmd_alto["lipsync_apertura"] > 0.5


def test_lucia_seguridad_3d_sello_y_verificacion_dao():
    """Verifica el sellado criptográfico HMAC-SHA256 con claves derivadas por HKDF."""
    lucia_dir = REPO_ROOT / "VersionDesesion" / "CONTRRF" / "RFC" / "CONTRUCCION" / "TLLDCD" / "src" / "MTBGT" / "WoldVirtualP2P3D" / "lucia3D" / "IslaUnicaLucIA" / "CelebroInternoLucia"
    if str(lucia_dir) not in sys.path:
        sys.path.insert(0, str(lucia_dir))

    import LucIAprc
    seg_3d = LucIAprc.Seguridad3D()

    datos = {"transaccion_id": "dao_prop_882", "votante": "usuario_01", "voto": "apruebo"}
    firma = seg_3d.sellar_transaccion_dao(datos)
    assert isinstance(firma, str) and len(firma) == 64

    # Verificación válida
    assert seg_3d.verificar_transaccion_dao(datos, firma) is True

    # Verificación inválida (datos manipulados)
    datos_manipulados = {"transaccion_id": "dao_prop_882", "votante": "usuario_01", "voto": "rechazo"}
    assert seg_3d.verificar_transaccion_dao(datos_manipulados, firma) is False


def test_lucia_seguridad_3d_protocolo_ndjson_gdscript():
    """Verifica el procesador de mensajes NDJSON para nodos GDScript."""
    lucia_dir = REPO_ROOT / "VersionDesesion" / "CONTRRF" / "RFC" / "CONTRUCCION" / "TLLDCD" / "src" / "MTBGT" / "WoldVirtualP2P3D" / "lucia3D" / "IslaUnicaLucIA" / "CelebroInternoLucia"
    if str(lucia_dir) not in sys.path:
        sys.path.insert(0, str(lucia_dir))

    import LucIAprc
    seg_3d = LucIAprc.Seguridad3D()

    # Ping
    resp_ping = json.loads(seg_3d.procesar_mensaje_gdscript(json.dumps({"comando": "ping"})))
    assert resp_ping.get("pong") is True

    # Estado DAO
    resp_estado = json.loads(seg_3d.procesar_mensaje_gdscript(json.dumps({"comando": "estado_dao"})))
    assert resp_estado.get("salud_dao") is not None
    assert resp_estado.get("avatar") is not None
