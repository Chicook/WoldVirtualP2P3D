"""Suite de tests minima para RFC/src — 7 tests."""
from __future__ import annotations

import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))


def test_gestor_errores_singleton():
    from SBSTM.gestor_errores import obtener_gestor_errores

    g1 = obtener_gestor_errores()
    g2 = obtener_gestor_errores()
    assert g1 is g2
    g1.limpiar()
    assert g1.resumen_errores()["total"] == 0


def test_gestor_errores_captura():
    from SBSTM.gestor_errores import obtener_gestor_errores

    g = obtener_gestor_errores()
    g.limpiar()
    try:
        raise ValueError("test error")
    except ValueError as e:
        entrada = g.capturar(e, contexto="test")
    assert entrada["tipo"] == "ValueError"
    assert entrada["mensaje"] == "test error"
    assert g.resumen_errores()["total"] == 1
    g.limpiar()


def test_blockchain_servidor():
    from STM_BKCH.BKSVCB import CelebroBlockchain

    bks = CelebroBlockchain()
    valida, err = bks.validar_cadena()
    assert valida is True
    assert err is None
    assert len(bks.cadena) >= 1


def test_vault_openrouter():
    from STM_SGR.vault_openrouter import cifrar_key, descifrar_blob, enmascarar

    key = "sk-test-12345-abcdef"
    blob = cifrar_key(key)
    assert blob != key
    assert descifrar_blob(blob) == key
    assert enmascarar(key) != key
    assert enmascarar("") == "****"


def test_ipfs_manager():
    from STM_BKCH.compat_local import get_ipfs_manager

    mgr = get_ipfs_manager()
    res = mgr.almacenar_pesos(datos={"test": True})
    assert res["ok"] is True
    assert res["cid"].startswith("QmLocal")
    rec = mgr.recuperar_pesos(res["cid"])
    assert rec["ok"] is True
    gc = mgr.ejecutar_gc()
    assert gc["ok"] is True


def test_ipfs_deteccion_resiliente():
    from STMIPFS.SBSTMPYIPFS import get_ipfs_bin, get_ipfs_repo, verificar_instalacion
    from STMIPFS.SBSTMPYIPFS.ipfs_launcher import verificar_repositorio, ejecutar_repo_gc

    bin_path = get_ipfs_bin()
    repo_path = get_ipfs_repo()
    assert bin_path is not None
    assert repo_path is not None
    assert repo_path.exists()
    assert verificar_repositorio() is True
    # GC cuando el daemon no está corriendo debe retornar sin error fatal
    gc_res = ejecutar_repo_gc()
    assert isinstance(gc_res, dict)
    assert "ok" in gc_res
    info = verificar_instalacion()
    assert "repo_inicializado" in info
    assert info["repo_inicializado"] is True


def test_compat_local_conversor():
    from STM_BKCH.compat_local import get_conversor_pesos

    conv = get_conversor_pesos()
    assert len(conv.neuronas) == 50
    info = conv.procesar_consulta_a_pesos("test prompt")
    assert "tono_cognitivo" in info
    assert "estado_emocional" in info
    assert "norma_delta_aplicada" in info


def test_snsbstnprb_importar_nucleo():
    from SBSTM.SNSBSTNPRB import _importar_nucleo

    get_bks, iniciar_daemon, get_conv, get_gpv = _importar_nucleo()
    assert callable(get_bks)
    assert callable(iniciar_daemon)
    assert callable(get_conv)


def test_autodiagnostico():
    from SBSTM.autodiagnostico import AutodiagnosticoLucIA, es_peticion_diagnostico, ejecutar_diagnostico

    assert es_peticion_diagnostico("puedes hacer otro diagnostico profundo sobre tu propio sistema?")
    assert es_peticion_diagnostico("revisa tu sistema para ver que funciona y que no")
    assert not es_peticion_diagnostico("cuanto es dos mas dos?")

    diag = AutodiagnosticoLucIA().ejecutar_diagnostico_completo()
    assert diag["blockchain"]["estado"] == "OPERATIVO"
    assert diag["red_neuronal"]["estado"] == "OPERATIVO"
    assert diag["integridad_codigo"]["limite_respetado"] is True
    assert "presion_memoria" in diag
    resumen = ejecutar_diagnostico()
    assert "REPORTE DE AUTODIAGNÓSTICO" in resumen
    assert "TELEMETRÍA DE RECURSOS" in resumen


def test_watchdog_sistema():
    from SBSTM.watchdog import WatchdogSistema, estado_watchdog

    wd = WatchdogSistema(intervalo_s=10.0)
    assert wd.intervalo_s == 10.0
    st_ini = wd.estado()
    assert st_ini["activo"] is False
    assert st_ini["ciclos"] == 0
    # Comprobar un ciclo de inspección puntual directamente
    wd._ciclo_inspeccion()
    st_post = wd.estado()
    assert st_post["ciclos"] == 1
    assert "ultimo_estado" in st_post
    assert st_post["ultimo_estado"]["neural_ok"] is True
    assert st_post["ultimo_estado"]["bkch_ok"] is True


def test_memoria_sesion():
    import time
    from SBSTM.memoria_sesion import MemoriaSesion

    sid = f"TEST_FASE7_{int(time.time() * 1000)}"
    mem = MemoriaSesion(sesion_id=sid, ventana=3)
    mem.registrar_turno("Hola LucIA", "Hola, explorador", tono="reflexivo", valencia=0.5)
    mem.registrar_turno("Como estas?", "Todo operativo", tono="entusiasta", valencia=0.8)
    resumen = mem.resumen_contexto()
    assert len(mem._turnos) == 2
    assert "Hola LucIA" in resumen or "Todo operativo" in resumen
    if mem._ruta.exists():
        mem._ruta.unlink(missing_ok=True)


def test_orquestador_contexto_y_memoria():
    from STMGNRL.mainLCSTM import OrquestadorSistemaLucIA
    from STM_BKCH.compat_local import get_conversor_pesos

    orq = OrquestadorSistemaLucIA()
    assert orq.memoria is not None
    assert orq.sesion_id.startswith("LUCIA_")
    conv = get_conversor_pesos()
    st = conv.procesar_consulta_a_pesos("hola prueba de turno")
    ref = orq._generar_reflejo_interno("hola prueba de turno", st)
    assert "Estimulo cognitivo" in ref
    t = orq.memoria.registrar_turno("hola prueba de turno", ref, tono=st.get("tono_cognitivo", ""), valencia=st.get("estado_emocional", 0.0))
    assert t["n"] >= 1
    assert orq.memoria.total() >= 1
    ultimos = orq.memoria.ultimos(1)
    assert len(ultimos) == 1
    assert "hola prueba de turno" in ultimos[0]["prompt"]
    orq.memoria.limpiar()


def test_ollama_cache_y_fast_failover():
    import time
    from STM_IA.modelosIAlocal.IALOCAL.gestor import ollama_disponible as _ialocal_ollama
    from SBSTM.SNSBSTNPRB import _ollama_disponible as _sns_ollama
    from SBSTM.IAFREE import ClienteIAFree

    # Primera llamada registra estado y timestamp
    r1 = _ialocal_ollama(timeout=0.8)
    t0 = time.perf_counter()
    # Segunda llamada debe resolver desde cache TTL en < 10 ms
    r2 = _ialocal_ollama(timeout=0.8)
    delta_ms = (time.perf_counter() - t0) * 1000.0
    assert r1 == r2
    assert delta_ms < 15.0, f"Cache TTL demasiado lenta: {delta_ms:.2f} ms"

    s1 = _sns_ollama(timeout=0.8)
    t1 = time.perf_counter()
    s2 = _sns_ollama(timeout=0.8)
    delta_sns = (time.perf_counter() - t1) * 1000.0
    assert s1 == s2
    assert delta_sns < 15.0


def test_manifiesto_hrts_y_registro():
    from STM_HRTS.registro_hrts import RegistroHRTS
    reg = RegistroHRTS()
    assert reg.existe() is True, "El archivo pyproject.toml de STM_HRTS no existe o no fue detectado"
    assert reg.nombre() == "lucia-woldvirtualp2p3d", f"Nombre inesperado: {reg.nombre()}"
    assert reg.version() == "2026.5.0", f"Version inesperada: {reg.version()}"
    deps = reg.dependencias()
    assert isinstance(deps, list)
    assert len(deps) >= 1
    assert any("numpy" in d for d in deps)
    scripts = reg.scripts()
    assert "lucia" in scripts
    assert scripts["lucia"] == "STMGNRL.mainLCSTM:main"


def test_minado_rapido_y_persistencia_atomica():
    import time
    from STM_BKCH.BKSVCB import CelebroBlockchain
    bks = CelebroBlockchain(dificultad=2)
    bks.agregar_transaccion("TEST_POW", "NODE_A", "NODE_B", {"valor": 42})
    t0 = time.perf_counter()
    blk = bks.minar_transacciones_pendientes()
    dt_ms = (time.perf_counter() - t0) * 1000.0
    assert blk is not None
    assert blk.hash_bloque.startswith("00")
    assert blk.calcular_hash() == blk.hash_bloque
    assert blk.calcular_merkle_root() == blk.merkle_root
    assert dt_ms < 100.0, f"Minado lento: {dt_ms:.2f} ms"
    valida, err = bks.validar_cadena()
    assert valida is True, f"Cadena invalida tras minado: {err}"


def test_rplc_cache_memoria_deque_y_vectorizacion():
    from SBSTM.RPLC import get_procesador_rplc, CacheMemoriaCognitiva
    cache = CacheMemoriaCognitiva(capacidad=10)
    for i in range(15):
        cache.registrar(f"texto {i}", 0.5, "neutro")
    assert cache.total_registros() == 10
    assert cache.es_repetitivo("texto 14") is True
    assert cache.es_repetitivo("texto 0") is False

    proc = get_procesador_rplc()
    vec = proc.analizador.vectorizar("arquitectura cognitiva de LucIA en 50 neuronas")
    assert len(vec) == 50
    assert max(vec) == 1.0


def test_transformar_ledger_y_checkpoint_npz():
    from STM_BKCH.BKSVCB import CelebroBlockchain
    bks = CelebroBlockchain()
    res = bks.transformar_ledger_a_pesos_neuronales()
    assert res["total_bloques"] >= 1
    assert res["norma_acumulada"] > 0.0, f"Norma acumulada deberia ser mayor que 0: {res['norma_acumulada']}"
    assert res["npz_pesos"].endswith(".npz")
    assert res["json_meta"].endswith(".json")


def test_rutas_limpieza_optimizada():
    import time
    from STM_CH.rutas import limpiar, inicializar
    inicializar()
    t0 = time.perf_counter()
    res = limpiar()
    dt_ms = (time.perf_counter() - t0) * 1000.0
    assert "borrados" in res
    assert isinstance(res["errores"], list)
    assert dt_ms < 50.0, f"Limpieza demasiado lenta: {dt_ms:.2f} ms"


if __name__ == "__main__":
    tests = [
        test_gestor_errores_singleton,
        test_gestor_errores_captura,
        test_blockchain_servidor,
        test_vault_openrouter,
        test_ipfs_manager,
        test_compat_local_conversor,
        test_snsbstnprb_importar_nucleo,
        test_autodiagnostico,
        test_watchdog_sistema,
        test_memoria_sesion,
        test_ipfs_deteccion_resiliente,
        test_orquestador_contexto_y_memoria,
        test_ollama_cache_y_fast_failover,
        test_manifiesto_hrts_y_registro,
        test_minado_rapido_y_persistencia_atomica,
        test_rplc_cache_memoria_deque_y_vectorizacion,
        test_transformar_ledger_y_checkpoint_npz,
        test_rutas_limpieza_optimizada,
    ]
    exitos = 0
    for t in tests:
        try:
            t()
            print(f"  [OK] {t.__name__}")
            exitos += 1
        except Exception as exc:
            print(f"  [FAIL] {t.__name__}: {exc}")
    print(f"\nResultado: {exitos}/{len(tests)} tests pasados con exito.")
    if exitos != len(tests):
        sys.exit(1)
