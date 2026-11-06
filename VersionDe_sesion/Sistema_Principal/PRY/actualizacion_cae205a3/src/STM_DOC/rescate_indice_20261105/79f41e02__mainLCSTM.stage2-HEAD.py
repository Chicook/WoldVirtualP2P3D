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
            self.procesar_turno_dialogo(entrada)
        self.activa = False

    def cerrar_sistema(self) -> None:
        """Cierre ordenado: minado de bloques pendientes y persistencia a IPFS."""
        with self.lock:
            if not self.servidor_bks:
                return
            print("\n\033[38;5;51m" + "=" * 76 + "\033[0m\n  \033[1;37mCONSOLIDANDO ESTADO COGNITIVO Y PERSISTENCIA FINAL...\033[0m")
            try:
                blk = self.servidor_bks.minar_transacciones_pendientes()
                if blk:
                    print(f"  Bloque final consolidado: \033[38;5;220m{blk.hash_bloque[:28]}...\033[0m")
            except Exception:
                pass
            try:
                self.servidor_bks.cerrar_sesion_y_subir_ipfs()
                print("  \033[38;5;48mSincronizacion IPFS de bloques y pesos completada exitosamente.\033[0m")
            except Exception as e_close:
                print(f"  \033[38;5;214mCierre IPFS: {e_close}\033[0m")
            print("\033[38;5;51m" + "=" * 76 + "\033[0m\n")
            self.servidor_bks = None
            res = limpiar_rutas_stmch()
            print(f"  STM_CH limpiado: {res.get('borrados', 0)} artefactos.")
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
