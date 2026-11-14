'\nmainLCSTM.py - Orquestador Central del Sistema Cognitivo LucIA (WoldVirtualP2P3D 2026)\n=====================================================================================\nCoordinacion maestro: Blockchain BKSVCB, Sesion P2P, IAFREE ($0.00), STYLOS y RPLC.\n'

from __future__ import annotations
import atexit
import json
import logging
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional, Tuple, Union

CURRENT_FILE: Final[Path] = Path(__file__).resolve()
GNRL_DIR: Final[Path] = CURRENT_FILE.parent
SRC_DIR: Final[Path] = GNRL_DIR.parent
ROOT_DIR: Final[Path] = SRC_DIR.parent
CONTRRF_DIR: Final[Path] = CURRENT_FILE.parents[3]
ENV_FILE: Final[Path] = next((c for c in (GNRL_DIR / ".env", SRC_DIR / ".env", ROOT_DIR / ".env") if c.exists()), SRC_DIR / ".env")
CELEBRO_DIR: Final[Path] = SRC_DIR / "STM_CH"
PSNRL_DIR: Final[Path] = CELEBRO_DIR / "PSNRL"
CMFG_DIR: Final[Path] = SRC_DIR
SBSTM_DIR: Final[Path] = SRC_DIR / "SBSTM"
STM_RFC_DIR: Final[Path] = ROOT_DIR / "STM_RFC"
for _p in (GNRL_DIR, SRC_DIR, STM_RFC_DIR, ROOT_DIR, CONTRRF_DIR):
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from ._imports import (
        init_stmch_rutas,
        RFPRMN_DISPONIBLE as _RFPRMN_DISPONIBLE,
        modulo_rfprmn as _RFPRMN,
        ClienteIAFree,
        get_cliente_iafree,
        ColoresLucIA,
        EstiloTerminalLucIA,
        Glifos,
        badge_turno,
        banner_bienvenida,
        formatear_respuesta_lucia,
        panel_ayuda_comandos,
        RPLC_DISPONIBLE as _RPLC_DISPONIBLE,
        get_procesador_rplc,
        reprocesar_con_metricas,
        VOZ_DISPONIBLE as _VOZ_DISPONIBLE,
        VOZ_MOTIVO as _VOZ_MOTIVO,
        hablar_voz as _hablar_voz,
        cancelar_voz as _cancelar_voz,
        prosodia_voz as _prosodia_voz,
        SelectorModelos,
        GestorHRTLucIA,
        GestorJSONLucIA,
        get_gestor_ialocal,
        WATCHDOG_DISPONIBLE as _WATCHDOG_DISPONIBLE,
        arrancar_watchdog as _arrancar_watchdog,
        MEMORIA_DISPONIBLE as _MEMORIA_DISPONIBLE,
        MemoriaSesion,
        get_memoria,
        get_openrouter_vault_key,
        confirmar_vault_openrouter,
        registrar_key_vault_openrouter,
        obtener_componentes_blockchain,
        obtener_conversor_pesos_blockchain,
        instanciar_sesion_p2p,
        limpiar_rutas_stmch,
        importar_agente,
    )
except (ImportError, ValueError):
    from _imports import (
        init_stmch_rutas,
        RFPRMN_DISPONIBLE as _RFPRMN_DISPONIBLE,
        modulo_rfprmn as _RFPRMN,
        ClienteIAFree,
        get_cliente_iafree,
        ColoresLucIA,
        EstiloTerminalLucIA,
        Glifos,
        badge_turno,
        banner_bienvenida,
        formatear_respuesta_lucia,
        panel_ayuda_comandos,
        RPLC_DISPONIBLE as _RPLC_DISPONIBLE,
        get_procesador_rplc,
        reprocesar_con_metricas,
        VOZ_DISPONIBLE as _VOZ_DISPONIBLE,
        VOZ_MOTIVO as _VOZ_MOTIVO,
        hablar_voz as _hablar_voz,
        cancelar_voz as _cancelar_voz,
        prosodia_voz as _prosodia_voz,
        SelectorModelos,
        GestorHRTLucIA,
        GestorJSONLucIA,
        get_gestor_ialocal,
        WATCHDOG_DISPONIBLE as _WATCHDOG_DISPONIBLE,
        arrancar_watchdog as _arrancar_watchdog,
        MEMORIA_DISPONIBLE as _MEMORIA_DISPONIBLE,
        MemoriaSesion,
        get_memoria,
        get_openrouter_vault_key,
        confirmar_vault_openrouter,
        registrar_key_vault_openrouter,
        obtener_componentes_blockchain,
        obtener_conversor_pesos_blockchain,
        instanciar_sesion_p2p,
        limpiar_rutas_stmch,
        importar_agente,
    )

init_stmch_rutas()


_COMANDOS_RFPRMN: Final[Dict[str, str]] = {"crear carpeta": "comando_crear_carpeta", "crear archivo": "comando_crear_archivo", "refactorizar": "comando_refactorizar", "actualizar": "actualizar", "enviar": "comando_enviar", "ia local": "comando_ia_local", "cerrar": "cerrar"}

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

logging.basicConfig(level=logging.CRITICAL)
for _log_name in ("", "WoldVirtualP2P3D", "LC", "urllib3", "ENRN", "SLRN", "RNP", "httpx"):
    logging.getLogger(_log_name).setLevel(logging.CRITICAL)


class GestorEntornoSeguro:
    """Carga y gestiona de forma aislada credenciales y rutas desde .env."""

    @staticmethod
    def cargar_variables(ruta_env: Path = ENV_FILE) -> Dict[str, str]:
        variables: Dict[str, str] = {}
        if not ruta_env.exists():
            return variables
        try:
            for linea in ruta_env.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                limpia = linea.strip().lstrip("\ufeff")
                if limpia and not limpia.startswith("#") and "=" in limpia:
                    k, _, v = limpia.partition("=")
                    clave, valor = k.strip(), v.strip().strip("'\"")
                    variables[clave] = valor
                    os.environ[clave] = valor
        except Exception as err:
            sys.stderr.write(f"[mainLCSTM] Advertencia leyendo .env: {err}\n")
        return variables

    @classmethod
    def obtener_openrouter_key(cls) -> str:
        k = get_openrouter_vault_key()
        if k:
            return k
        return cls.cargar_variables().get("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY", "")).strip()

class OrquestadorSistemaLucIA(SelectorModelos):
    '\n    Orquestador maestro que integra BKSVCB, SNSBSTNPRB, IAFREE, STYLOS y las 50 neuronas.\n    '
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.servidor_bks = None
        self.conversor_psn = None
        self.sesion_p2p = None
        self.cliente_iafree = None
        self.subsistema_neural = None
        self.subsistema_evolutivo = None
        self.activa = False
        self.turno_actual = 0
        self.sesion_id = f"LUCIA_{time.strftime('%Y%m%d_%H%M%S')}"
        self.memoria = get_memoria(self.sesion_id) if _MEMORIA_DISPONIBLE and get_memoria else None
        atexit.register(self.cerrar_sistema)
    def inicializar_subsistemas(self) -> bool:
        """Inicializa en secuencia la blockchain, transductor, IAFREE y credenciales."""
        GestorEntornoSeguro.cargar_variables()
        if hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            confirmar_vault_openrouter()
        if get_cliente_iafree is not None:
            self.cliente_iafree = get_cliente_iafree()
            modelo_ini = self.cliente_iafree.gestor.obtener_modelo_activo()["id"]
        else:
            modelo_ini = "openrouter/free"
        if EstiloTerminalLucIA:
            banner_bienvenida(self.sesion_id, modelo_ini)
        else:
            print(f"\n[+] WoldVirtualP2P3D -- LucIA Console 2026 | Mod: {modelo_ini}")
        try:
            get_bks, start_bks = obtener_componentes_blockchain()
            self.servidor_bks = get_bks()
            print(f"  [1/4] Blockchain BKSVCB    : \033[38;5;48mACTIVA\033[0m | Bloques: \033[38;5;220m{len(self.servidor_bks.cadena)}\033[0m")
            self.servidor_bks.mostrar_cadena_hashes_terminal()
            start_bks(puerto=8545)
        except Exception as e_bks:
            print(f"  [1/4] Blockchain BKSVCB    : \033[38;5;203mERROR ({e_bks})\033[0m")
            return False
        try:
            self.conversor_psn = obtener_conversor_pesos_blockchain()
            num_neu = len(self.conversor_psn.neuronas)
            print(f"  [2/4] Conversor PSNRCV     : \033[38;5;48mOK\033[0m | Sinapsis: \033[38;5;141m{num_neu} Activas\033[0m")
        except Exception as e_psn:
            print(f"  [2/4] Conversor PSNRCV     : \033[38;5;203mERROR ({e_psn})\033[0m")
            return False
        try:
            res_t = self.servidor_bks.transformar_ledger_a_pesos_neuronales()
            self.servidor_bks.arrancar_actualizador_red()
            print(f"  [3/4] Ledger -> Pesos PSNRL: \033[38;5;48m{res_t.get('total_bloques', 0)} bloques\033[0m | Norma: \033[38;5;214m{res_t.get('norma_acumulada', 0.0)}\033[0m")
        except Exception as e_led:
            print(f"  [3/4] Ledger -> Pesos      : \033[38;5;214mAVISO ({e_led})\033[0m")
        try:
            self.sesion_p2p = instanciar_sesion_p2p()
            print(f"  [4/4] Sesion SNSBSTNPRB    : \033[38;5;48mACOPLADA\033[0m | Motor STYLOS: \033[38;5;51mACTIVO\033[0m\n")
        except Exception as e_sbs:
            print(f"  [4/4] Sesion SNSBSTNPRB    : \033[38;5;214mAVISO ({e_sbs})\033[0m\n")

        self.gestor_json = GestorJSONLucIA() if GestorJSONLucIA else None
        if self.gestor_json:
            print(f"  [JSON] {self.gestor_json.linea_estado()}")
        self.gestor_hrts = GestorHRTLucIA() if GestorHRTLucIA else None
        if self.gestor_hrts:
            print(f"  [HRTS] {self.gestor_hrts.linea_estado()}")
        try:
            from SBSTM.voice_engine import estado_voz as _estado_voz
            print(f"  {_estado_voz()}")
        except Exception as _e_v:
            print(f"  [VOZ]  Voz Neuronal LucIA  : \033[38;5;203mNO DISPONIBLE ({_VOZ_MOTIVO or _e_v})\033[0m")
        self.activa = True
        if _WATCHDOG_DISPONIBLE and _arrancar_watchdog is not None:
            try:
                _arrancar_watchdog(intervalo_s=60.0)
                print("  [WDG] Watchdog subsistemas : \033[38;5;48mACTIVO\033[0m | Ciclo: 60 s")
            except Exception as _e_wdg:
                print(f"  [WDG] Watchdog             : \033[38;5;214mAVISO ({_e_wdg})\033[0m")
        try:
            from SBSTM.subsistema_neural import get_subsistema_neural
            self.subsistema_neural = get_subsistema_neural(arrancar_socket=True)
            self.subsistema_neural.conectar_main_lcstm(self)
            puerto_sck = self.subsistema_neural.canal_socket.puerto
            print(f"  [SBSTM] Subsistema Neural   : \033[38;5;48mACTIVO\033[0m | Socket Puerto: \033[38;5;141m{puerto_sck}\033[0m | Destino: \033[38;5;220mLCtrabajando\033[0m")
        except Exception as _e_sub:
            print(f"  [SBSTM] Subsistema Neural   : \033[38;5;214mAVISO ({_e_sub})\033[0m")
        try:
            from SBSTM.subsistema_evolutivo import get_subsistema_evolutivo
            self.subsistema_evolutivo = get_subsistema_evolutivo()
            print("  [SBSTM] Subsistema Evolutivo: \033[38;5;48mACTIVO\033[0m | 4 Fases: \033[38;5;141mAutopoiesis\033[0m")
        except Exception as _e_evo:
            print(f"  [SBSTM] Subsistema Evolutivo: \033[38;5;214mAVISO ({_e_evo})\033[0m")
        return True
    def procesar_turno_dialogo(self, prompt: str, emitir_voz: bool = True) -> None:
        '\n        Ejecuta el pipeline cognitivo completo por turno a coste cero con renderizado STYLOS:\n        1. Pre-procesamiento por las 50 neuronas para tono y estado emocional.\n        2. Inferencia local prioritaria (IALOCAL) y OpenRouter :free opcional.\n        3. Formateo y presentacion de respuesta estilizada (tarjetas redondeadas y markdown).\n        4. Asimilacion de gradientes Hebbianos en tensores de PSNRL.\n        5. Emision de transaccion sinaptica a Blockchain BKSVCB y minado automatico.\n        '
        self.turno_actual += 1
        t_inicio = time.perf_counter()
        estado_previo = self.conversor_psn.procesar_consulta_a_pesos(prompt)
        estado_previo["sesion_id"] = self.sesion_id
        respuesta = ""
        modelo_usado = "Reflejo-Interno"
        latencia_llm = 0.0
        if get_gestor_ialocal is not None:
            try:
                _rep = reprocesar_con_metricas if _RPLC_DISPONIBLE else None
                respuesta, modelo_usado = get_gestor_ialocal().ciclo(
                    prompt, estado_previo, self.conversor_psn, _rep)
            except Exception as e_local:
                print(f"  [IALocal] {e_local} -> probando OpenRouter")
        if not respuesta and self.cliente_iafree and self.cliente_iafree.esta_autenticado():
            resp_txt, mod_id, lat = self.cliente_iafree.generar_respuesta( prompt=prompt, contexto_neuronal=estado_previo, stream_en_vivo=False, )
            if resp_txt and not resp_txt.startswith("[IAFREE]"):
                respuesta = resp_txt
                modelo_usado = mod_id
                latencia_llm = lat
        if not respuesta:
            respuesta = self._generar_reflejo_interno(prompt, estado_previo)
        elif _RPLC_DISPONIBLE and reprocesar_con_metricas is not None and not modelo_usado.startswith("IALocal"):
            try:
                respuesta, _ = reprocesar_con_metricas(respuesta, estado_previo)
            except Exception:
                pass
        if EstiloTerminalLucIA:
            formatear_respuesta_lucia(respuesta, modelo=modelo_usado)
        else:
            print(f"\nLucIA [{modelo_usado}] ▶ {respuesta}\n")
        if emitir_voz and _VOZ_DISPONIBLE and _hablar_voz is not None:
            _hablar_voz(respuesta, esperar=False)
        duracion_ms = (time.perf_counter() - t_inicio) * 1000.0
        if self.memoria:
            try:
                self.memoria.registrar_turno(prompt, respuesta, tono=estado_previo.get("tono_cognitivo", ""), valencia=float(estado_previo.get("estado_emocional", 0.0)), ms=duracion_ms, modelo=modelo_usado, deriva=float(self.conversor_psn.deriva_acumulada))
            except Exception:
                pass
        threading.Thread(target=self._post_turno_async, args=(prompt, respuesta, modelo_usado, self.turno_actual), daemon=True).start()
        self._imprimir_telemetria_turno(duracion_ms, "async-tx", modelo_usado)

    def _post_turno_async(self, pr: str, resp: str, mod: str, tur: int) -> None:
        try:
            b = self.servidor_bks
            b.registrar_aprendizaje_neural(prompt=pr, respuesta=resp, modelo=f"LucIA-{mod}")
            if tur % 3 == 0:
                b.minar_transacciones_pendientes()
        except Exception:
            pass
        if getattr(self, "subsistema_neural", None):
            try:
                self.subsistema_neural.entrenar_con_vector(
                    f"{pr} -> {resp}",
                    recompensa=1.0,
                    motivo=f"turno_{tur}"
                )
            except Exception:
                pass
    def _generar_reflejo_interno(self, prompt: str, info: Dict[str, Any]) -> str:
        tono = info.get("tono_cognitivo", "reflexivo")
        val = info.get("estado_emocional", 0.0)
        norma = info.get("norma_delta_aplicada", 0.0)
        return (f"Estimulo cognitivo asimilado en red distribuida. Tono: **{tono}** | "
                f"Valencia afectiva: `{val:+.3f}` | Delta sinaptico: `{norma:.5f}`.\n"
                "Pesos neuronales sincronizados y activos en persistencia `PSNRL`.")

    def _imprimir_telemetria_turno(self, duracion_ms: float, cid: str, modelo_id: str) -> None:
        deriva = self.conversor_psn.deriva_acumulada
        neu = len(self.conversor_psn.neuronas)
        txs = len(self.servidor_bks.transacciones_pendientes)
        if EstiloTerminalLucIA:
            badge_turno(turno=self.turno_actual, dt=duracion_ms, mod=modelo_id, der=deriva, neu=neu, cid=cid, txs=txs)
        else:
            print(f"  Turno #{self.turno_actual} | {duracion_ms:.0f}ms | Mod: {modelo_id} | Deriva: {deriva:.4f} | CID: {cid[:16]}")

    def mostrar_estado_sistema(self) -> None:
        """Despliega en terminal un reporte detallado del estado de todos los componentes."""
        valida, err = self.servidor_bks.validar_cadena()
        cadena_str = "VALIDA E INMUTABLE" if valida else f"ERROR: {err}"
        mod_act = self.cliente_iafree.gestor.obtener_modelo_activo()["id"] if self.cliente_iafree else "N/A"
        metricas = self.cliente_iafree.obtener_metricas_consumo() if self.cliente_iafree else {}
        costo_usd = float(metricas.get("costo_acumulado_usd", 0.0))
        datos = {
            "Cadena de Bloques": f"{len(self.servidor_bks.cadena)} bloques [{cadena_str}]",
            "Txs en Espera": str(len(self.servidor_bks.transacciones_pendientes)),
            "Neuronas Activas": f"{len(self.conversor_psn.neuronas)} (ENRN, RF_EN, RF_SL, RNP, SLRN)",
            "Deriva Muon": f"{self.conversor_psn.deriva_acumulada:.6f}",
            "Turnos de Sesion": str(self.turno_actual),
            "Modelo Activo": mod_act,
            "Costo Acumulado": f"${costo_usd:.2f} USD (100% Free)",
        }
        if EstiloTerminalLucIA:
            EstiloTerminalLucIA.renderizar_tarjeta_sistema("ESTADO INTEGRAL DE LUCIA (2026)", datos)
            print()
        else:
            for k, v in datos.items():
                print(f"  {k}: {v}")

    def ejecutar_comando_rfprmn(self, comando: str) -> bool:
        if not _RFPRMN_DISPONIBLE or _RFPRMN is None:
            print(f"RFPRMN no esta disponible en: {STM_RFC_DIR / 'RFPRMN.py'}")
            return True
        if comando == "cerrar":
            _RFPRMN.cerrar()
            print("\n\033[38;5;214mIniciando protocolo de salida y sincronizacion...\033[0m")
            return False
        funcion = getattr(_RFPRMN, _COMANDOS_RFPRMN.get(comando, ""), None)
        if callable(funcion):
            try:
                funcion()
            except Exception as error:
                print(f"Error ejecutando '{comando}': {error}")
        else:
            print(f"El comando RFPRMN '{comando}' no esta disponible.")
        return True

    def ejecutar_bucle_interactivo(self) -> None:
        """Bucle principal de recepcion e interpretacion de comandos de consola."""
        while self.activa:
            try:
                entrada = input("\033[38;5;214mLucIA> Tu:\033[0m ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                break
            if not entrada:
                continue
            cmd = entrada.lower()
            if cmd in ("salir", "exit", "quit"):
                print("\n\033[38;5;214mIniciando protocolo de salida y sincronizacion...\033[0m")
                break
            if cmd in ("estado", "status"):
                self.mostrar_estado_sistema()
                continue
            if cmd in ("ayuda", "help"):
                if EstiloTerminalLucIA:
                    panel_ayuda_comandos()
                continue
            if cmd in ("modelos", "models", "free"):
                self.listar_modelos_gratuitos()
                continue
            if cmd in ("minar", "mine"):
                blk = self.servidor_bks.minar_transacciones_pendientes()
                if blk:
                    (EstiloTerminalLucIA.renderizar_notificacion_bloque(blk.indice, blk.hash_bloque)
                     if EstiloTerminalLucIA else print(f"Bloque #{blk.indice} minado: {blk.hash_bloque}"))
                else:
                    print("  No hay transacciones pendientes para minar.")
                continue
            if cmd in ("api", "apikey", "registrar api"):
                try:
                    registrar_key_vault_openrouter()
                except Exception as e_api:
                    print(f"  No se pudo registrar: {e_api}")
                continue
            if cmd.startswith("modelo "):
                nuevo_mod = entrada[7:].strip()
                ok = bool(self.cliente_iafree and self.cliente_iafree.gestor.seleccionar_por_id(nuevo_mod))
                col, msg = ("\033[38;5;48m", f"Modelo gratuito seleccionado: {nuevo_mod}") if ok else ("\033[38;5;214m", f"Modelo '{nuevo_mod}' no encontrado en catalogo :free.")
                print(f"  {col}{msg}\033[0m")
                continue
            if cmd in _COMANDOS_RFPRMN:
                if not self.ejecutar_comando_rfprmn(cmd):
                    break
                continue
            try:
                from SBSTM.comandos import es_comando, despachar
                if es_comando(entrada):
                    res_cmd = despachar(entrada)
                    if res_cmd:
                        print(f"\n{res_cmd}\n")
                    continue
            except Exception:
                pass
            self.procesar_turno_dialogo(entrada)
        self.activa = False

    def cerrar_sistema(self) -> None:
        """Cierre ordenado: minado de bloques pendientes y conservación de datos (H1)."""
        with self.lock:
            if not self.servidor_bks:
                return
            print("\n\033[38;5;51m" + "=" * 76 + "\033[0m\n  \033[1;37mCONSOLIDANDO ESTADO COGNITIVO...\033[0m")
            try:
                blk = self.servidor_bks.minar_transacciones_pendientes()
                if blk:
                    print(f"  Bloque final consolidado: \033[38;5;220m{blk.hash_bloque[:28]}...\033[0m")
            except Exception:
                pass
            try:
                res_cierre = self.servidor_bks.cerrar_sesion_y_subir_ipfs()
                # H1: informar honestamente sobre el estado de la persistencia
                if res_cierre.get("ipfs_ok", False):
                    print("  \033[38;5;48mSincronizacion IPFS completada. Ledger y pesos subidos.\033[0m")
                else:
                    # Estado honesto: los datos quedan en disco (no se borraron)
                    print("  \033[38;5;220m[H1] IPFS no disponible. "
                          "Ledger y PSNRL CONSERVADOS en disco (no borrados).\033[0m")
                    err = res_cierre.get("ipfs_error", "")
                    if err:
                        print(f"  \033[38;5;241m  Detalle: {err[:120]}\033[0m")
            except Exception as e_close:
                print(f"  \033[38;5;214mCierre: {e_close}\033[0m")
            print("\033[38;5;51m" + "=" * 76 + "\033[0m\n")
            self.servidor_bks = None
            # H1: limpiar solo cache (pycache/ruff_cache), nunca ledger ni PSNRL
            res = limpiar_rutas_stmch()
            print(f"  STM_CH cache limpiada: {res.get('borrados', 0)} artefactos.")
            if getattr(self, "subsistema_neural", None):
                try:
                    self.subsistema_neural.cerrar()
                except Exception:
                    pass
class ContextoOrquestadorLucIA:
    """Gestor de contexto para pruebas, evaluacion o invocacion programatica."""
    def __init__(self) -> None:
        self.orquestador = OrquestadorSistemaLucIA()
    def __enter__(self) -> OrquestadorSistemaLucIA:
        if not self.orquestador.inicializar_subsistemas():
            raise RuntimeError("Fallo durante la inicializacion de subsistemas en LucIA")
        return self.orquestador
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self.orquestador.cerrar_sistema()
        return False
logger = logging.getLogger("WoldVirtualP2P3D.STMGNRL.LucIAComandos")


class LucIAComandos:
    """LucIA usando su propia maquina de comandos (RFPRMN) sin humano.

    Cada comando se ejecuta solo si la decision matematica del agente lo
    autoriza (`utilidad >= umbral`), calculada con el deficit de deuda, la
    urgencia, el exito previo y el coste. El cierre tambien se decide asi: no
    se cierra mientras haya un flujo abierto o trabajo pendiente.
    """

    def __init__(self, umbral: float = 0.55) -> None:
        self._agente = None
        if not _RFPRMN_DISPONIBLE or _RFPRMN is None:
            logger.debug("RFPRMN no disponible: LucIA se queda sin comandos.")
            return
        clase = importar_agente() if importar_agente else None
        if clase is None:
            logger.debug("AgenteRFPRMN no importable.")
            return
        try:
            self._agente = clase(umbral=umbral)
        except Exception as err:  # noqa: BLE001 - nunca romper el arranque
            logger.debug("No se pudo crear el agente: %s", err)

    @property
    def disponible(self) -> bool:
        """True si LucIA puede lanzar comandos."""
        return self._agente is not None

    def __getattr__(self, nombre: str) -> Any:
        """Expone todos los comandos del agente como metodos."""
        agente = self.__dict__.get("_agente")
        if agente is None or not hasattr(agente, nombre):
            raise AttributeError(nombre)
        return getattr(agente, nombre)

    def comando(self, nombre: str, ruta: Optional[str] = None) -> bool:
        """Ejecuta un comando por nombre si la utilidad lo permite."""
        if not self._agente:
            return False
        return bool(self._agente.ejecutar(nombre, ruta))

    def utilidad(self, nombre: str, ruta: Optional[str] = None) -> float:
        """Utilidad calculada de un comando (0-1) sobre ese archivo."""
        if not self._agente:
            return 0.0
        return float(self._agente.utilidad(nombre, self._agente.analizar(ruta)
                                           if ruta else {})[0])

    def cerrar(self) -> bool:
        """Cierra la maquina de comandos solo si la decision lo autoriza."""
        if not self._agente:
            return False
        autorizado, valor, motivo = self._agente.desea_cerrar()
        logger.info("LucIA cierre: %s (%.3f, %s)",
                    "si" if autorizado else "no", valor, motivo)
        return bool(self._agente.cerrar_si_procede())

    def ciclo(self, rutas: List[str]) -> Dict[str, Any]:
        """Ciclo autonomo: salud, probar, partir/refactorizar/comentar, informe."""
        if not self._agente:
            return {"acciones": [], "cerrado": False, "motivo": "RFPRMN no disponible"}
        return dict(self._agente.ciclo(rutas))


class LucIAPlanificador:
    """Planifica los comandos con dos señales mas: su red y el tiempo.

    - **Prediccion de la red** (quinta senal de la utilidad): cuanto respalda
      LucIA una accion segun lo que ha aprendido (memoria del seq2seq y pasos de
      su red, encogida hacia 0.5 cuando aun sabe poco).
    - **Presupuesto de tiempo**: cada accion lleva un coste estimado en segundos
      y la sesion tiene un maximo; lo que no cabe se descarta y el ciclo se
      corta cuando se agota, en vez de quedarse minutos bloqueado.
    """

    def __init__(self, presupuesto_segundos: float = 300.0,
                 umbral: float = 0.55) -> None:
        self._agente = None
        clase = importar_agente() if importar_agente else None
        if clase is not None:
            try:
                self._agente = clase(umbral=umbral,
                                     presupuesto_segundos=presupuesto_segundos)
            except Exception as err:  # noqa: BLE001 - nunca romper el arranque
                logger.debug("No se pudo crear el planificador: %s", err)

    @property
    def disponible(self) -> bool:
        """True si hay agente con el que planificar."""
        return self._agente is not None

    def senal_red(self, ruta: str) -> float:
        """Prediccion de LucIA para ese archivo (0-1; 0.5 si no hay agente)."""
        if not self._agente:
            return 0.5
        try:
            contenido = Path(ruta).read_text(encoding="utf-8-sig")
        except OSError:
            contenido = ""
        return float(self._agente.senal_red(contenido))

    def estimar(self, comando: str, ruta: Optional[str] = None) -> float:
        """Segundos estimados del comando sobre ese archivo."""
        if not self._agente:
            return 0.0
        analisis = self._agente.analizar(ruta) if ruta else {}
        return float(self._agente.estimar_tiempo(comando, analisis))

    def restante(self) -> float:
        """Segundos que quedan del presupuesto de la sesion."""
        return float(self._agente.restante()) if self._agente else 0.0

    def exito(self, comando: str) -> float:
        """Calidad media conseguida por ese comando (0.5 si aun no hay datos).

        No cuenta aciertos: cada intento aporta la nota que dio la red de LucIA
        al aplicarlo, asi que una accion que sale a medias pesa menos.
        """
        return float(self._agente.exito_previo(comando)) if self._agente else 0.5

    def aprendizaje(self) -> Dict[str, Dict[str, float]]:
        """Lo aprendido por comando: calidad media e intentos de la sesion."""
        if not self._agente:
            return {}
        historial = getattr(self._agente, "historial", {})
        return {
            accion: {
                "calidad_media": round(self._agente.exito_previo(accion), 3),
                "intentos": int(historial.get(accion, [0.0, 0])[1]),
            }
            for accion in sorted(historial)
        }

    def plan(self, rutas: List[str],
             acciones: Tuple[str, ...] = ("partir", "refactorizar",
                                          "comentar", "informe")) -> List[Dict[str, Any]]:
        """Ordena las acciones por **utilidad por segundo** y marca las que caben."""
        if not self._agente:
            return []
        filas: List[Dict[str, Any]] = []
        for ruta in rutas:
            analisis = self._agente.analizar(ruta)
            for accion in acciones:
                valor, senales = self._agente.utilidad(accion, analisis)
                segundos = self._agente.estimar_tiempo(accion, analisis)
                filas.append({
                    "ruta": str(ruta), "accion": accion,
                    "utilidad": valor, "segundos": segundos,
                    "eficiencia": round(valor / max(segundos, 1.0), 4),
                    "red": senales["red"],
                    "cabe": segundos <= self._agente.restante(),
                })
        return sorted(filas, key=lambda fila: (not fila["cabe"],
                                               -fila["eficiencia"]))

    def ejecutar(self, rutas: List[str]) -> Dict[str, Any]:
        """Ciclo autonomo con presupuesto de tiempo."""
        if not self._agente:
            return {"acciones": [], "cerrado": False, "motivo": "sin agente"}
        return dict(self._agente.ciclo(rutas))

    def cerrar(self) -> bool:
        """Cierra solo si la decision matematica lo autoriza."""
        if not self._agente:
            return False
        return bool(self._agente.cerrar_si_procede())


class LucIAIPFS:
    """Conecta el nodo IPFS con los pesos de LucIA y su maquina de comandos.

    El nodo vive en ``STMIPFS/nodo`` (binario, repositorio, daemon, cliente y
    pesos). Esta clase pone encima lo que necesita LucIA:

    - ``asegurar()``: deja el nodo listo (descarga Kubo si falta, inicializa el
      repositorio y arranca el daemon) y, si no hay pesos locales, los recupera.
    - ``publicar()``: empaqueta los pesos (red, agente, seq2seq) y los sube.
    - ``recuperar()``: los baja, verifica el SHA-256 y los deja en ``.modelos``.
    - ``cerrar()``: publica y para el daemon.
    """

    #: Carpeta de pesos que produce STM_RFPRMN.
    DIR_PESOS: Final[Path] = (CONTRRF_DIR / "STM_RFC" / "STM_RFPRMN"
                              / ".modelos")
    #: Archivos de estado que viajan en el paquete.
    PATRONES: Final[Tuple[str, ...]] = ("lucia_rn_*.pkl", "agente.json",
                                        "seq2seq.json")

    def __init__(self, arrancar: bool = False) -> None:
        self._nodo = None
        try:
            from STMIPFS.nodo import NodoIPFS

            self._nodo = NodoIPFS(descargar=True)
        except Exception as err:  # noqa: BLE001 - IPFS es opcional
            logger.debug("Nodo IPFS no disponible: %s", err)
        if arrancar:
            self.asegurar()

    @property
    def disponible(self) -> bool:
        """True si el paquete del nodo se pudo cargar."""
        return self._nodo is not None

    def asegurar(self) -> Dict[str, Any]:
        """Deja el nodo listo y recupera los pesos si faltan localmente."""
        if not self._nodo:
            return {"ok": False, "motivo": "nodo IPFS no disponible"}
        resultado = dict(self._nodo.asegurar())
        if resultado.get("ok") and not self.archivos():
            recuperado = self.recuperar()
            resultado["pesos_recuperados"] = recuperado.get("archivos", [])
        return resultado

    def estado(self) -> Dict[str, Any]:
        """Estado del nodo más la carpeta de pesos de LucIA."""
        if not self._nodo:
            return {"disponible": False, "pesos": []}
        datos = dict(self._nodo.estado())
        datos["disponible"] = True
        datos["pesos"] = [archivo.name for archivo in self.archivos()]
        return datos

    def archivos(self) -> List[Path]:
        """Archivos de pesos que existen ahora mismo."""
        if not self.DIR_PESOS.is_dir():
            return []
        encontrados: List[Path] = []
        for patron in self.PATRONES:
            encontrados += sorted(self.DIR_PESOS.glob(patron))
        return encontrados

    def publicar(self) -> Dict[str, Any]:
        """Sube el paquete de pesos al nodo."""
        if not self._nodo:
            return {"ok": False, "motivo": "nodo IPFS no disponible"}
        archivos = self.archivos()
        if not archivos:
            return {"ok": False, "motivo": "no hay pesos en .modelos"}
        datos = dict(self._nodo.publicar(archivos))
        if datos.get("ok"):
            logger.info("Pesos publicados en IPFS: %s", datos.get("cid"))
        return datos

    def recuperar(self) -> Dict[str, Any]:
        """Baja el paquete y lo restaura en la carpeta de pesos de LucIA."""
        if not self._nodo:
            return {"ok": False, "motivo": "nodo IPFS no disponible"}
        return dict(self._nodo.recuperar(destino=self.DIR_PESOS))

    def cerrar(self) -> Dict[str, Any]:
        """Publica los pesos y para el daemon."""
        if not self._nodo:
            return {"ok": False, "motivo": "nodo IPFS no disponible"}
        publicacion = self.publicar()
        parada = self._nodo.parar()
        return {"ok": bool(publicacion.get("ok")), "publicacion": publicacion,
                "daemon": parada}


class LucIAServidor3D:
    """Levanta y conecta el puente TCP de LucIA 3D: Godot <-> nucleo <-> Ollama.

    El servidor real vive en el proyecto Godot, en
    ``lucia3D/GLTF_lucIA/celebro_3D/puente_3D/servidor_lucia.py``. Esta clase lo
    arranca **como proceso** (no bloquea el orquestador), comprueba el puerto y
    habla su protocolo NDJSON: ``consulta`` entra, ``token``/``voz``/``fin``
    salen.

    Con ``ipfs`` y ``comandos`` conecta la arquitectura entera en un sitio:
    servidor + pesos + maquina de comandos.
    """

    #: Ruta del servidor, relativa a la raiz del proyecto Godot.
    RUTA_RELATIVA: Final[Path] = (Path("lucia3D") / "GLTF_lucIA" / "celebro_3D"
                                  / "puente_3D" / "servidor_lucia.py")
    HOST: Final[str] = "127.0.0.1"

    def __init__(self, raiz_godot: Optional[Path] = None, puerto: int = 8765,
                 modelo: str = "", voz: bool = True, ipfs: Any = None,
                 comandos: Any = None) -> None:
        self.raiz_godot = (Path(raiz_godot) if raiz_godot
                           else SRC_DIR / "MTBGT" / "WoldVirtualP2P3D")
        self.ruta_servidor = self.raiz_godot / self.RUTA_RELATIVA
        self.puerto = int(puerto)
        self.modelo = modelo
        self.voz = voz
        self.ipfs = ipfs
        self.comandos = comandos
        self._proceso: Any = None
        self._log = self.ruta_servidor.parent / "servidor.log"

    @property
    def disponible(self) -> bool:
        """True si el archivo del servidor existe."""
        return self.ruta_servidor.is_file()

    def activo(self, timeout: float = 0.6) -> bool:
        """True si el puerto del servidor acepta conexiones."""
        import socket

        try:
            with socket.create_connection((self.HOST, self.puerto), timeout=timeout):
                return True
        except OSError:
            return False

    def arrancar(self, esperar: float = 25.0) -> Dict[str, Any]:
        """Lanza el servidor y espera a que abra el puerto."""
        import subprocess

        if not self.disponible:
            return {"ok": False, "motivo": f"no existe {self.ruta_servidor}"}
        if self.activo():
            return {"ok": True, "arrancado": False, "motivo": "ya estaba escuchando"}
        argumentos = [sys.executable, str(self.ruta_servidor),
                      "--puerto", str(self.puerto)]
        if self.modelo:
            argumentos += ["--modelo", self.modelo]
        if not self.voz:
            argumentos += ["--sin-voz"]
        try:
            with open(self._log, "ab") as salida:
                self._proceso = subprocess.Popen(
                    argumentos, cwd=str(self.ruta_servidor.parent.parent),
                    stdout=salida, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL)
        except OSError as error:
            return {"ok": False, "motivo": f"no se pudo lanzar: {error}"}
        limite = time.monotonic() + max(1.0, esperar)
        while time.monotonic() < limite:
            if self.activo():
                return {"ok": True, "arrancado": True, "pid": self._proceso.pid,
                        "log": str(self._log)}
            if self._proceso.poll() is not None:
                return {"ok": False, "motivo": "el servidor terminó al arrancar",
                        "log": str(self._log)}
            time.sleep(0.4)
        return {"ok": False, "motivo": f"el puerto {self.puerto} no abrió en "
                                       f"{esperar:.0f}s", "log": str(self._log)}

    def consultar(self, texto: str, timeout: float = 180.0) -> Dict[str, Any]:
        """Un turno completo: envía la consulta y devuelve el evento ``fin``."""
        import socket

        if not self.activo():
            return {"ok": False, "motivo": "el servidor no está escuchando"}
        peticion = json.dumps({"tipo": "consulta", "texto": texto},
                              ensure_ascii=False) + "\n"
        try:
            with socket.create_connection((self.HOST, self.puerto),
                                          timeout=timeout) as conexion:
                conexion.sendall(peticion.encode("utf-8"))
                lector = conexion.makefile("r", encoding="utf-8", errors="replace")
                for linea in lector:
                    limpia = linea.strip()
                    if not limpia:
                        continue
                    try:
                        evento = json.loads(limpia)
                    except ValueError:
                        continue
                    if evento.get("tipo") == "error":
                        return {"ok": False, "motivo": evento.get("mensaje", "")}
                    if evento.get("tipo") == "fin":
                        return {"ok": True, **evento}
        except (OSError, ValueError) as error:
            return {"ok": False, "motivo": str(error)}
        return {"ok": False, "motivo": "el servidor cerró sin enviar 'fin'"}

    def parar(self) -> Dict[str, Any]:
        """Termina el proceso del servidor (si lo lanzamos nosotros)."""
        import subprocess

        proceso = self._proceso
        if proceso is None:
            return {"ok": not self.activo(), "detenido": False}
        try:
            proceso.terminate()
            proceso.wait(timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            try:
                proceso.kill()
            except OSError:
                pass
        self._proceso = None
        return {"ok": not self.activo(), "detenido": True}

    def nucleo(self) -> Dict[str, Any]:
        """Estado del núcleo neuronal de LucIA 3D (50 sinapsis, deriva, sesión)."""
        if not self.disponible:
            return {"ok": False, "motivo": "sin servidor"}
        try:
            import importlib

            base = self.ruta_servidor.parent.parent  # celebro_3D
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
            modulo = importlib.import_module("nucleo.orquestador_lucia")
            return {"ok": True, **modulo.NucleoLucia().estado()}
        except Exception as error:  # noqa: BLE001 - el nucleo es opcional
            return {"ok": False, "motivo": str(error)}

    def estado(self) -> Dict[str, Any]:
        """Servidor + IPFS + comandos: la arquitectura entera en un dict."""
        datos: Dict[str, Any] = {
            "disponible": self.disponible, "activo": self.activo(),
            "puerto": self.puerto, "ruta": str(self.ruta_servidor),
            "modelo": self.modelo or "(automático)", "log": str(self._log),
        }
        if self.ipfs is not None:
            datos["ipfs"] = self.ipfs.estado()
        if self.comandos is not None:
            datos["comandos"] = self.comandos.aprendizaje()
        return datos

    def cerrar(self) -> Dict[str, Any]:
        """Para el servidor y, si hay nodo IPFS, publica los pesos."""
        datos: Dict[str, Any] = {"servidor": self.parar()}
        if self.ipfs is not None:
            datos["ipfs"] = self.ipfs.cerrar()
        return datos


class LucIAPuenteComandos:
    """Puente entre la conversación y la máquina de comandos RFPRMN.

    El chat 3D solo hablaba con Ollama, así que LucIA contestaba «no puedo
    refactorizarme» aunque el agente sí sabe hacerlo. Esta clase:

    - ``capacidades()``: texto con lo que **de verdad** puede hacer, para el
      prompt del sistema.
    - ``detectar(texto)``: convierte una petición en (acción, ruta).
    - ``atender(texto)``: detecta y ejecuta; devuelve el resultado para que el
      modelo responda con datos reales.

    Todo es opcional: si RFPRMN no está, ``disponible`` es False y el servidor
    sigue funcionando como antes.
    """

    #: Palabras que activan cada acción del agente.
    CLAVES: Final[Tuple[Tuple[str, Tuple[str, ...]], ...]] = (
        ("refactorizar", ("refactoriza", "refactorizar", "refactor",
                          "reescribe", "mejora el codigo")),
        ("comentar", ("comenta", "comentar", "documenta", "documentar")),
        ("probar", ("haz test", "pasa test", "prueba el archivo", "probar",
                    "diagnostica")),
        ("informe", ("informe", "informacion", "deuda", "analiza")),
        ("partir", ("parte ", "partir", "divide", "dividir")),
        ("presupuesto", ("presupuesto", "450")),
        ("estado", ("estado", "como estas", "que tal")),
    )

    def __init__(self) -> None:
        self._agente = None
        self._error = ""
        try:
            from ._imports import importar_agente

            clase = importar_agente()
            # importar_agente() devuelve la CLASE, no una instancia.
            self._agente = clase() if clase is not None else None
            if self._agente is None:
                self._error = "RFPRMN no disponible"
        except Exception as error:  # noqa: BLE001 - RFPRMN es opcional
            self._error = str(error)

    @property
    def disponible(self) -> bool:
        """True si el agente RFPRMN se pudo cargar."""
        return self._agente is not None

    def capacidades(self) -> str:
        """Lo que LucIA puede hacer, en primera persona, para el prompt."""
        if not self.disponible:
            return ("No tienes la máquina de refactor cargada ahora mismo; "
                    "puedes conversar, pero no ejecutar cambios.")
        return (
            "Tienes una máquina de trabajo real (RFPRMN) y puedes usarla:\n"
            "- refactorizar código con calidad medida y veto si empeora;\n"
            "- comentar y documentar funciones;\n"
            "- probar y diagnosticar un archivo;\n"
            "- generar informes de deuda técnica;\n"
            "- partir archivos de más de 450 líneas en un subsistema.\n"
            "Decides con seis señales (déficit, urgencia, éxito previo, coste, "
            "red y candidato real) y solo aplicas por encima de 0.55 de nota. "
            "También puedes analizarte a ti misma y refactorizarte con "
            "`autoanalisis`. Nunca digas que no puedes refactorizar: puedes, "
            "y si falta el archivo, pide la ruta."
        )

    def detectar(self, texto: str) -> Optional[Dict[str, Any]]:
        """Acción y ruta a partir de una frase; None si no hay petición."""
        minuscula = texto.lower()
        accion = ""
        for nombre, claves in self.CLAVES:
            if any(clave in minuscula for clave in claves):
                accion = nombre
                break
        if not accion:
            return None
        return {"accion": accion, "ruta": self._ruta_en(texto)}

    def _ruta_en(self, texto: str) -> Optional[Path]:
        """Busca una ruta de archivo dentro del texto."""
        import re

        for trozo in re.findall(r"[A-Za-z]:\\[^\s\"']+|/[\w./-]+\.\w+", texto):
            candidato = Path(trozo.strip("\"'.,;:"))
            if candidato.is_file():
                return candidato
        for trozo in re.findall(r"[\w.-]+\.(?:py|gd|tscn|tres|md|json|cs)", texto):
            for base in (CONTRRF_DIR, SRC_DIR,
                         CONTRRF_DIR / "STM_RFC" / "STM_RFPRMN",
                         CONTRRF_DIR / "STM_RFC" / "STM_RFPRMN" / "STM_RFPRMN_stmDL",
                         SRC_DIR / "STMGNRL",
                         SRC_DIR / "MTBGT" / "WoldVirtualP2P3D"):
                candidato = base / trozo
                if candidato.is_file():
                    return candidato
        return None

    def atender(self, texto: str) -> Optional[Dict[str, Any]]:
        """Ejecuta lo que pide la frase y devuelve un resumen para el modelo."""
        deteccion = self.detectar(texto)
        if not deteccion:
            return None
        accion = str(deteccion["accion"])
        ruta = deteccion.get("ruta")
        if accion == "estado" and ruta is None:
            return None
        if accion in ("refactorizar", "comentar", "probar", "informe", "partir"):
            if ruta is None:
                if accion == "refactorizar":
                    # «refactorízate» sin archivo: que se analice a sí misma en
                    # vez de responder que no puede.
                    return self._autoanalisis()
                return {"ok": False, "accion": accion,
                        "motivo": "necesito la ruta del archivo"}
        try:
            aplicado, utilidad, motivo = self._agente.decidir(accion, ruta)
        except Exception as error:  # noqa: BLE001 - el agente no debe tumbar el chat
            return {"ok": False, "accion": accion, "motivo": str(error)}
        if not aplicado:
            return {"ok": False, "accion": accion, "utilidad": round(utilidad, 2),
                    "motivo": motivo}
        try:
            hecho = bool(self._agente.ejecutar(accion, ruta))
        except Exception as error:  # noqa: BLE001
            return {"ok": False, "accion": accion, "motivo": str(error)}
        return {"ok": hecho, "accion": accion, "ruta": str(ruta or ""),
                "utilidad": round(utilidad, 2), "motivo": motivo}

    def _autoanalisis(self) -> Dict[str, Any]:
        """Su propio estado interno, para cuando le piden refactorizarse."""
        try:
            datos = self._agente.autoanalisis()
        except Exception as error:  # noqa: BLE001
            return {"ok": False, "accion": "autoanalisis", "motivo": str(error)}
        return {"ok": True, "accion": "autoanalisis", "datos": datos}


def obtener_diagnostico_orquestador() -> Dict[str, Any]:
    """Genera un reporte estructural para validar la salud de todo el stack."""
    cf = get_cliente_iafree() if get_cliente_iafree else None
    return {
        "orquestador_version": "2026.5.0",
        "iafree_activo": cf.esta_autenticado() if cf else False,
        "modelos_gratuitos_total": len(cf.gestor.listar_modelos()) if cf else 0,
        "modelo_predeterminado": cf.gestor.obtener_modelo_activo()["id"] if cf else "N/A",
        "costo_acumulado": cf.obtener_metricas_consumo()["costo_acumulado_usd"] if cf else 0.0,
        "timestamp": time.time(),
    }
def main() -> int:
    """Punto de arranque del orquestador unificado mainLCSTM."""
    orquestador = OrquestadorSistemaLucIA()
    if not orquestador.inicializar_subsistemas():
        sys.stderr.write("[mainLCSTM] Fallo durante la inicializacion de subsistemas.\n")
        return 1
    try:
        orquestador.ejecutar_bucle_interactivo()
        limpiar_rutas_stmch()
        return 0

    except Exception as err:
        sys.stderr.write(f"[mainLCSTM] Error no controlado: {err}\n")
        return 1
if __name__ == "__main__":
    sys.exit(main())
