"""Gestor del Entorno de Desarrollo y Sistema General de Rutas (.dev)
WoldVirtualP2P3D · Versión canónica modular

Centraliza y orquesta:
- Python base (.dev/.python) y venv (.dev/venv)
- Configuración de VS Code (.dev/.vscode) y Pytest (.dev/pytest.ini)
- Servidor Oficial Blockchain y Cuentas (STM_BKCH puerto 8545)
- Servidor Cerebro de LucIA 3D (puerto 8765)
- Reconstrucción y ciclo de vida del Visor 3D C# WPF (Visor3D.csproj)
- Jerarquía general de rutas canónicas
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Añadir el propio directorio .dev a sys.path para resolución de módulos
DEV_DIR_ROOT = Path(__file__).resolve().parent
if str(DEV_DIR_ROOT) not in sys.path:
    sys.path.insert(0, str(DEV_DIR_ROOT))

# Todo bytecode del ecosistema se compila dentro de .dev/pycache: nunca se
# crean carpetas __pycache__ en el árbol de fuentes.
sys.pycache_prefix = str(DEV_DIR_ROOT / "pycache")

# Importar desde el paquete modular de .dev
from modulos import (  # noqa: E402
    BLOCKCHAIN_DIR,
    BLOCKCHAIN_SCRIPT,
    CONTRRF_DIR,
    CONTRUCCION_DIR,
    DEV_DIR,
    DEV_PYTEST_INI,
    GODOT_PROJECT_FILE,
    GODOT_PROY_DIR,
    IPFS_DIR,
    LEDGER_PATH,
    LUCIA_BAT_VISOR,
    LUCIA_DIR,
    LUCIA_PS1_VISOR,
    LUCIA_SCRIPT,
    PRY_ARCHIVOS_DIR,
    PRY_DIR,
    PSNRL_DIR,
    PYTEST_CACHE_DIR,
    PYTHON_DIR,
    PYTHON_EXE,
    PYTHONW_EXE,
    REPO_ROOT,
    RFC_DIR,
    RUFF_CACHE_DIR,
    STM_RFC_DIR,
    TLLDCD_DIR,
    TLLDCD_SRC,
    VENV_DIR,
    VENV_PYTHON,
    VENV_PYTHONW,
    VERSION_DIR,
    VISOR_BASE_DIR,
    VISOR_CSPROJ,
    VISOR_HERRAMIENTAS_DIR,
    VISOR_OUTPUT_DLL,
    VISOR_OUTPUT_EXE,
    SEGURIDAD_DIR,
    SEGURIDAD_SESION_UNICA_DIR,
    SMTPLC_DIR,
    VSCODE_DIR,
    actualizar_vscode_config,
    comprobar_dotnet,
    configurar_variables_entorno,
    detener_blockchain,
    detener_lucia,
    ejecutar_pytest,
    estado_blockchain,
    estado_lucia,
    estado_visor,
    iniciar_blockchain,
    iniciar_lucia,
    lanzar_visor,
    limpiar_cache_raiz,
    obtener_python_activo,
    obtener_pythonw_activo,
    reconstruir_visor,
    reiniciar_blockchain,
    reiniciar_lucia,
    traer_pytest_ini,
    validar_ledger_en_disco,
    validar_frontera_carpetas,
    asegurar_ruta_en_repositorio,
    formatear_informe_dependencias,
    ValidadorFronteraSegura,
    GestorVenvSeguro,
    asegurar_frontera,
    requiere_venv_activo,
    auditar_operacion_entorno,
    ARCHIVO_AUDITORIA_ENTORNO,
    carpeta_temporal,
    listar_temporales,
    limpiar_temporales,
    entorno_bundle_visor,
    lanzar_vista_previa,
    formatear_informe_temporales,
)


@auditar_operacion_entorno("informe_general")
def mostrar_informe() -> None:
    """Muestra el estado completo y unificado de rutas, servicios y visor."""
    print("=" * 76)
    print("  SISTEMA GENERAL DE RUTAS Y SERVICIOS WOLDVIRTUALP2P3D (.dev)")
    print("=" * 76)

    # 0. Aislamiento y Contención de Fronteras
    validador = ValidadorFronteraSegura()
    frontera_ok, violaciones = validador.auditar_todo_el_arbol()
    st_frontera = "[OK] AISLADO" if frontera_ok else "[FALLO] ESCAPE"
    print(f"\n--- [0] CONTENCIÓN DE FRONTERAS Y ZERO TRUST ({st_frontera}) ---")
    print(f"  Raíz autorizada: {REPO_ROOT}")
    diag_venv = GestorVenvSeguro.verificar_integridad_entorno()
    st_venv = "[OK] AISLADO EN .DEV" if diag_venv["es_contenido_en_dev"] else "[EXTERNO / SISTEMA]"
    print(f"  Intérprete Python: {diag_venv['interprete_activo']} ({st_venv})")
    if not frontera_ok:
        for v in violaciones:
            print(f"  [ALERTA] {v}")
    else:
        print("  [OK] Todas las rutas del ecosistema residen estrictamente dentro de la jerarquía.")

    # 1. Rutas del Entorno
    print("\n--- [1] JERARQUÍA DE DIRECTORIOS Y CONFIGURACIÓN (.dev) ---")
    rutas_info = [
        ("Raíz Repositorio", REPO_ROOT, REPO_ROOT.is_dir()),
        ("Versión de Sesión", VERSION_DIR, VERSION_DIR.is_dir()),
        ("CONTRRF", CONTRRF_DIR, CONTRRF_DIR.is_dir()),
        ("RFC", RFC_DIR, RFC_DIR.is_dir()),
        ("CONTRUCCION", CONTRUCCION_DIR, CONTRUCCION_DIR.is_dir()),
        ("Carpeta .dev", DEV_DIR, DEV_DIR.is_dir()),
        ("Python base (.python)", PYTHON_DIR, PYTHON_DIR.is_dir()),
        ("Python ejecutable", PYTHON_EXE, PYTHON_EXE.is_file()),
        ("Pythonw ejecutable", PYTHONW_EXE, PYTHONW_EXE.is_file()),
        ("Entorno venv", VENV_DIR, VENV_DIR.is_dir()),
        ("Config VS Code (.vscode)", VSCODE_DIR, (VSCODE_DIR / "settings.json").is_file()),
        ("Config Pytest (.dev/pytest.ini)", DEV_PYTEST_INI, DEV_PYTEST_INI.is_file()),
        ("Caché Pytest (.pytest_cache)", PYTEST_CACHE_DIR, PYTEST_CACHE_DIR.is_dir()),
        ("Taller TLLDCD src", TLLDCD_SRC, TLLDCD_SRC.is_dir()),
        ("STM_RFC STM_RFPRMN", STM_RFC_DIR, STM_RFC_DIR.is_dir()),
        ("Sistema Principal PRY", PRY_DIR, PRY_DIR.is_dir()),
    ]
    for nombre, ruta, existe in rutas_info:
        estado = "[OK]" if existe else "[FALTA]"
        print(f"  {estado:<8} {nombre:<32} -> {ruta}")

    # 2. Servidor Blockchain Oficial
    print("\n--- [2] SERVIDOR BLOCKCHAIN OFICIAL (STM_BKCH · Puerto 8545) ---")
    st_bkch = estado_blockchain()
    puerto_bkch = "[ONLINE]" if st_bkch["abierto"] else "[OFFLINE]"
    print(f"  {puerto_bkch:<10} Puerto TCP 8545: {'Escuchando' if st_bkch['abierto'] else 'Cerrado/Inactivo'}")
    print(f"  {'[OK]' if st_bkch['script_existe'] else '[FALTA]':<10} Script: {st_bkch['ruta_script']}")
    print(f"  {'[OK]' if st_bkch['ledger_ok'] else '[FALTA]':<10} Ledger oficial: {st_bkch['detalle_ledger']}")
    if st_bkch["responde_http"]:
        info = st_bkch["info_http"]
        print(f"  [INFO]     Bloques en memoria: {info.get('total_bloques', '?')} | Estado: {info.get('estado', 'OK')}")

    # 3. Servidor LucIA 3D
    print("\n--- [3] SERVIDOR CEREBRO LUCIA 3D (Puente TCP · Puerto 8765) ---")
    st_lucia = estado_lucia()
    puerto_lucia = "[ONLINE]" if st_lucia["abierto"] else "[OFFLINE]"
    print(f"  {puerto_lucia:<10} Puerto TCP 8765: {'Escuchando' if st_lucia['abierto'] else 'Cerrado/Inactivo'}")
    print(f"  {'[OK]' if st_lucia['script_existe'] else '[FALTA]':<10} Script: {st_lucia['ruta_script']}")
    ollama_str = "Activo" if st_lucia["ollama_activo"] else "Desconectado"
    print(f"  {'[OK]' if st_lucia['ollama_activo'] else '[AVISO]':<10} Ollama (127.0.0.1:11434): {ollama_str}")
    if st_lucia["modelos_ollama"]:
        print(f"  [INFO]     Modelos Ollama disponibles: {', '.join(st_lucia['modelos_ollama'][:5])}")

    # 4. Visor 3D (.NET 8 WPF)
    print("\n--- [4] VISOR 3D (LCDMWoldVirtualP2P3Dv2.8.4 · .NET 8 WPF) ---")
    st_visor = estado_visor()
    print(f"  {'[OK]' if st_visor['dotnet_disponible'] else '[FALTA]':<10} Compilador .NET: {st_visor['dotnet_version']}")
    print(f"  {'[OK]' if st_visor['csproj_existe'] else '[FALTA]':<10} Proyecto C#: {st_visor['ruta_csproj']}")
    dll_status = "[OK]" if st_visor["dll_compilada"] else "[NO COMPILADO]"
    print(f"  {dll_status:<10} Ensamblado DLL: {st_visor['ruta_dll']}")
    if st_visor["dll_fecha_mod"]:
        print(f"  [INFO]     Última modificación: {st_visor['dll_fecha_mod']}")
    print(f"  {'[OK]' if st_visor['godot_proy_existe'] else '[FALTA]':<10} Proyecto Godot 3D: {st_visor['ruta_godot_proy']}")
    modulos_sesion = list(SEGURIDAD_SESION_UNICA_DIR.glob("*.cs")) if SEGURIDAD_SESION_UNICA_DIR.is_dir() else []
    print(f"  {'[OK]' if SEGURIDAD_SESION_UNICA_DIR.is_dir() else '[FALTA]':<10} Seguridad Sesión Única: {SEGURIDAD_SESION_UNICA_DIR} ({len(modulos_sesion)} módulos CS)")

    print("\n" + "=" * 76)
    print("  COMANDOS DISPONIBLES:")
    print("    python gestor_entorno.py sincronizar          (Aplica variables y config VSCode)")
    print("    python gestor_entorno.py reconstruir-visor    (Compila Visor3D con dotnet)")
    print("    python gestor_entorno.py dependencias         (Verifica .NET, DLLs nativas, Python y Godot)")
    print("    python gestor_entorno.py validar-frontera     (Comprueba que nada salga de E:\\WoldVirtualP2P3D)")
    print("    python gestor_entorno.py temporales [listar|crear <nombre>|limpiar]")
    print("    python gestor_entorno.py vista-previa <exe> [args]  (Extracción del paquete en .dev)")
    print("    python gestor_entorno.py blockchain [iniciar|detener|reiniciar|estado]")
    print("    python gestor_entorno.py lucia [iniciar|detener|reiniciar|estado]")
    print("    python gestor_entorno.py todo                 (Sincroniza, inicia servicios y compila)")
    print("    python gestor_entorno.py pytest               (Ejecuta suite de pruebas)")
    print("=" * 76)


@asegurar_frontera
@auditar_operacion_entorno("comando_todo")
def comando_todo() -> int:
    """Orquesta la sincronización completa, arranque de servicios y compilación del visor."""
    print(">>> 0/5 Comprobando contención de fronteras del repositorio...")
    f_ok, f_errs = validar_frontera_carpetas()
    if not f_ok:
        print("  [ERROR FATAL] Se detectaron violaciones en la jerarquía de directorios:")
        for e in f_errs:
            print(f"    - {e}")
        return 1
    print("  [OK] Todas las rutas se mantienen confinadas dentro del repositorio.")

    print("\n>>> 1/5 Sincronizando entorno y variables...")
    configurar_variables_entorno()
    traer_pytest_ini()
    actualizar_vscode_config()
    limpiar_cache_raiz()

    print("\n>>> 2/5 Verificando/Iniciando Servidor Blockchain (8545)...")
    st_b = estado_blockchain()
    if not st_b["abierto"]:
        ok_b, msg_b = iniciar_blockchain(segundo_plano=True)
        print(f"  {msg_b}")
    else:
        print("  Servidor Blockchain ya se encuentra activo en el puerto 8545.")

    print("\n>>> 3/5 Verificando/Iniciando Servidor LucIA 3D (8765)...")
    st_l = estado_lucia()
    if not st_l["abierto"]:
        ok_l, msg_l = iniciar_lucia(segundo_plano=True)
        print(f"  {msg_l}")
    else:
        print("  Servidor LucIA ya se encuentra activo en el puerto 8765.")

    print("\n>>> 4/5 Reconstruyendo Visor 3D...")
    ok_v, msg_v = reconstruir_visor()
    print(f"  {msg_v}")

    print("\n[FIN] Todo el entorno y los servicios han sido preparados.")
    return 0 if ok_v else 1


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    configurar_variables_entorno()

    if not argv or argv[0] in ("informe", "status", "--help", "-h"):
        mostrar_informe()
        return 0

    sub = argv[0].lower()

    if sub == "sincronizar":
        configurar_variables_entorno()
        traer_pytest_ini()
        actualizar_vscode_config()
        limpiar_cache_raiz()
        print("[OK] Entorno sincronizado y variables aplicadas.")
        mostrar_informe()
        return 0

    elif sub in ("reconstruir-visor", "reconstruir_visor", "reconstruir", "build"):
        limpiar = "--limpiar" in argv or "-l" in argv
        publicar = "--publicar" in argv or "-p" in argv
        ok, msg = reconstruir_visor(limpiar=limpiar, publicar_single_file=publicar)
        print(msg)
        return 0 if ok else 1

    elif sub in ("lanzar-visor", "lanzar_visor", "run"):
        return lanzar_visor(argv[1:])

    elif sub == "blockchain":
        accion = argv[1].lower() if len(argv) > 1 else "estado"
        if accion == "iniciar":
            ok, msg = iniciar_blockchain()
            print(msg)
            return 0 if ok else 1
        elif accion == "detener":
            detener_blockchain()
            print("[OK] Servidor Blockchain detenido.")
            return 0
        elif accion == "reiniciar":
            ok, msg = reiniciar_blockchain()
            print(msg)
            return 0 if ok else 1
        elif accion in ("estado", "status"):
            st = estado_blockchain()
            print(f"Puerto 8545 abierto: {st['abierto']}")
            print(f"Ledger: {st['detalle_ledger']}")
            if st["responde_http"]:
                print(f"Info HTTP: {st['info_http']}")
            return 0
        elif accion == "validar":
            ok, tot, msg = validar_ledger_en_disco()
            print(msg)
            return 0 if ok else 1
        else:
            print(f"Acción desconocida para blockchain: {accion}")
            return 1

    elif sub in ("lucia", "lucia3d"):
        accion = argv[1].lower() if len(argv) > 1 else "estado"
        if accion == "iniciar":
            ok, msg = iniciar_lucia()
            print(msg)
            return 0 if ok else 1
        elif accion == "detener":
            detener_lucia()
            print("[OK] Servidor LucIA detenido.")
            return 0
        elif accion == "reiniciar":
            ok, msg = reiniciar_lucia()
            print(msg)
            return 0 if ok else 1
        elif accion in ("estado", "status"):
            st = estado_lucia()
            print(f"Puerto 8765 abierto: {st['abierto']}")
            print(f"LucIA listo: {st['listo']}")
            print(f"Ollama activo: {st['ollama_activo']}")
            if st["modelos_ollama"]:
                print(f"Modelos Ollama: {st['modelos_ollama']}")
            return 0
        else:
            print(f"Acción desconocida para lucia: {accion}")
            return 1

    elif sub in ("temporales", "temps", "tmp"):
        accion = argv[1].lower() if len(argv) > 1 else "listar"
        if accion in ("listar", "ls", "estado"):
            print(formatear_informe_temporales())
            return 0
        elif accion in ("crear", "nuevo"):
            if len(argv) < 3:
                print("Uso: python gestor_entorno.py temporales crear <nombre> [--limpiar]")
                return 1
            try:
                ruta = carpeta_temporal(argv[2], limpiar="--limpiar" in argv)
            except (ValueError, PermissionError) as err:
                print(f"[ERROR] {err}")
                return 1
            print(f"[OK] Espacio temporal listo: {ruta}")
            return 0
        elif accion in ("limpiar", "clean"):
            conservar: List[str] = []
            if "--conservar" in argv:
                idx = argv.index("--conservar")
                conservar = [a for a in argv[idx + 1:] if not a.startswith("-")]
            borradas = limpiar_temporales(conservar)
            if borradas:
                for ruta in borradas:
                    print(f"[OK] Eliminada: {ruta}")
            else:
                print("[OK] No había espacios temporales que eliminar.")
            return 0
        elif accion in ("bundle", "extraccion"):
            env = entorno_bundle_visor()
            print(f"[OK] Base de extracción single-file: {env['DOTNET_BUNDLE_EXTRACT_BASE_DIR']}")
            return 0
        else:
            print(f"Acción desconocida para temporales: {accion}")
            print("  Opciones: listar | crear <nombre> | limpiar [--conservar <n1> <n2>] | bundle")
            return 1

    elif sub in ("vista-previa", "vista_previa", "previsualizar"):
        if len(argv) < 2:
            print("Uso: python gestor_entorno.py vista-previa <ruta-exe> [args...]")
            return 1
        return lanzar_vista_previa(argv[1], argv[2:])

    elif sub == "todo":
        return comando_todo()

    elif sub == "pytest":
        return ejecutar_pytest(argv[1:])

    elif sub in ("traer-pytest", "traer_pytest"):
        traer_pytest_ini()
        return 0

    elif sub == "vscode":
        actualizar_vscode_config()
        return 0

    elif sub in ("dependencias", "deps"):
        print(formatear_informe_dependencias())
        return 0

    elif sub in ("validar-frontera", "validar_frontera", "frontera", "aislamiento"):
        ok, errs = validar_frontera_carpetas()
        print("=" * 76)
        print("  VALIDACIÓN DE AISLAMIENTO Y FRONTERAS DEL REPOSITORIO (.dev)")
        print("=" * 76)
        print(f"Raíz permitida: {REPO_ROOT}")
        if ok:
            print("[OK] Aislamiento íntegro: Ningún módulo ni proceso escapa del repositorio.")
            return 0
        else:
            print("[FALLO] Se detectaron rutas fuera del repositorio:")
            for e in errs:
                print(f"  - {e}")
            return 1

    elif sub in ("auditoria", "audit"):
        if ARCHIVO_AUDITORIA_ENTORNO.is_file():
            print("=" * 76)
            print(f"  REGISTRO DE AUDITORÍA DE ENTORNO ({ARCHIVO_AUDITORIA_ENTORNO.name})")
            print("=" * 76)
            lineas = ARCHIVO_AUDITORIA_ENTORNO.read_text(encoding="utf-8").strip().splitlines()
            ultimas = lineas[-20:] if len(lineas) > 20 else lineas
            for l in ultimas:
                print(f"  {l}")
            print(f"\nTotal registros: {len(lineas)}")
        else:
            print("No hay eventos de auditoría registrados todavía.")
        return 0

    elif sub == "limpiar":
        borrado = limpiar_cache_raiz()
        traer_pytest_ini()
        print(f"Limpieza en raíz: {'Borrados rastros' if borrado else 'Sin archivos sueltos'}")
        return 0

    else:
        print(f"Comando desconocido: {sub}")
        mostrar_informe()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
