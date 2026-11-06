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

# ---------------------------------------------------------------------------
# STM_PRCS: AutoConciencia de Rendimiento Neuronal (LC_STM/STM_PRCS)
# ---------------------------------------------------------------------------
_STM_PRCS_DISPONIBLE: bool = False
_stm_prcs_mod: Any = None
try:
    _LC_STM_DIR: Final[Path] = SRC_DIR / "LC_STM"
    if str(_LC_STM_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    import importlib as _importlib
    _stm_prcs_mod = _importlib.import_module("LC_STM.STM_PRCS")
    _STM_PRCS_DISPONIBLE = True
except Exception as _e_prcs:
    pass   # STM_PRCS opcional — no bloquea el arranque


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

class GestorAutoconcienciaRendimiento:
    """
    Gestor de AutoConciencia de Rendimiento de LucIA (STM_PRCS).

    Puente entre el OrquestadorSistemaLucIA y el motor neuronal STM_PRCS.
    Detecta, recoge y procesa TODO el rendimiento del sistema en tiempo real:
      - CPU / RAM / hilos / GC / uptime del proceso
      - Estado de la blockchain BKSVCB (bloques, TX, dificultad, deriva)
      - Sesion P2P SBSTM (turnos, sesiones, checkpoint age)
      - Optimizadores RNP / SLRN (perdida, gradiente, pesos, score)
      - Metricas de respuesta del LLM (latencia, tokens, modelo)

    Convierte todo en el vector de rendimiento Phi(t) en R^50, actualiza los
    pesos neuronales mediante AdamW+Hebb en tiempo real, y expone el estado
    de conciencia (Xi in [0,1]) para enriquecer el prompt de LucIA.

    Uso dentro del orquestador:
        self.conciencia = GestorAutoconcienciaRendimiento(orquestador=self)
        self.conciencia.arrancar()
        # En cada turno:
        self.conciencia.registrar_turno(prompt, respuesta, modelo, latencia_ms)
        contexto = self.conciencia.contexto_para_prompt()
    """

    # Intervalo de recoleccion automatica del SO en segundos
    INTERVALO_COLECTOR_S: float = 20.0
    # Tasa de fusion EMA de pesos al ConversorRespuestaPesos
    ALPHA_FUSION: float = 0.05

    def __init__(self, orquestador: Optional[Any] = None) -> None:
        self._orq = orquestador
        self._motor: Optional[Any] = None
        self._colector: Optional[Any] = None
        self._actualizador: Optional[Any] = None
        self._visualizador: Optional[Any] = None
        self._activo: bool = False
        self._lock: threading.Lock = threading.Lock()
        self._ultimo_xi: float = 0.0
        self._ultimo_ciclo: int = 0
        self._disponible: bool = _STM_PRCS_DISPONIBLE

    # ------------------------------------------------------------------
    # Arranque / detención
    # ------------------------------------------------------------------
    def arrancar(self, conversor_externo: Optional[Any] = None) -> bool:
        """Inicializa el sistema STM_PRCS y arranca el colector daemon.

        Args:
            conversor_externo: ConversorRespuestaPesos del orquestador para
                               que el actualizador propague pesos directamente.
        Returns:
            True si STM_PRCS se inicializó correctamente, False si no está
            disponible (el sistema sigue funcionando sin él).
        """
        if not self._disponible or _stm_prcs_mod is None:
            return False
        try:
            resultado = _stm_prcs_mod.inicializar_stm_prcs(
                intervalo_colector_s=self.INTERVALO_COLECTOR_S,
                alpha_fusion=self.ALPHA_FUSION,
                arrancar_colector_auto=True,
                propagar_bksvcb=True,
                propagar_psnrl=True,
                conversor_externo=conversor_externo,
            )
            self._motor        = resultado.get("motor")
            self._colector     = resultado.get("colector")
            self._actualizador = resultado.get("actualizador")
            self._visualizador = resultado.get("visualizador")
            with self._lock:
                self._activo = self._motor is not None
            return self._activo
        except Exception as _e:
            return False

    def detener(self) -> None:
        """Detiene el colector daemon y fuerza un checkpoint final."""
        with self._lock:
            self._activo = False
        if self._colector is not None:
            try:
                self._colector.detener()
            except Exception:
                pass
        if self._motor is not None:
            try:
                self._motor.guardar_checkpoint_manual()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Integración con cada turno de diálogo
    # ------------------------------------------------------------------
    def registrar_turno(
        self,
        prompt: str,
        respuesta: str,
        modelo: str,
        latencia_ms: float,
        tokens_prompt: int = 0,
        tokens_resp: int = 0,
        error_resp: bool = False,
    ) -> Optional[Any]:
        """
        Alimenta el motor con las métricas del turno de diálogo y ejecuta
        un ciclo de aprendizaje. Llama a este método en cada turno desde
        procesar_turno_dialogo() para que LucIA aprenda del rendimiento.

        Args:
            prompt:       Texto del prompt del usuario.
            respuesta:    Respuesta generada por LucIA.
            modelo:       ID del modelo usado en este turno.
            latencia_ms:  Latencia de respuesta del LLM en ms.
            tokens_prompt: Tokens del prompt (si se conocen).
            tokens_resp:  Tokens de la respuesta (si se conocen).
            error_resp:   True si la respuesta fue un error/fallback.

        Returns:
            SnapshotNeuronal con el estado del motor tras el ciclo, o None.
        """
        if not self._activo or self._motor is None:
            return None
        try:
            import hashlib as _hl
            metricas: Dict[str, float] = {
                "latencia_ms":      latencia_ms,
                "thrpt_tokens_s":   (tokens_resp / max(latencia_ms / 1000.0, 0.001))
                                    if tokens_resp > 0 else 0.0,
                "tokens_prompt_avg": float(tokens_prompt),
                "tokens_resp_avg":   float(tokens_resp),
                "ratio_error_resp":  1.0 if error_resp else 0.0,
                "modelo_id_hash":    abs(int(_hl.sha256(modelo.encode()).hexdigest()[:8], 16) % 10000) / 10000.0,
            }
            # Métricas de sesión desde el orquestador
            if self._orq is not None:
                try:
                    metricas["sb_turnos"]         = float(getattr(self._orq, "turno_actual", 0))
                    metricas["sb_session_active"]  = 1.0
                    if getattr(self._orq, "conversor_psn", None) is not None:
                        conv = self._orq.conversor_psn
                        metricas["bk_deriva_acum"]  = float(getattr(conv, "deriva_acumulada", 0.0))
                        metricas["bk_pasos_sesion"] = float(getattr(conv, "pasos_sesion", 0))
                    if getattr(self._orq, "servidor_bks", None) is not None:
                        bks = self._orq.servidor_bks
                        cadena = getattr(bks, "cadena", [])
                        metricas["bk_bloques"]       = float(len(cadena))
                        metricas["bk_transacciones"] = float(len(getattr(bks, "transacciones_pendientes", [])))
                        if cadena:
                            ultimo = cadena[-1]
                            metricas["bk_dificultad"] = float(getattr(ultimo, "dificultad", 2))
                            metricas["bk_nonce"]      = float(getattr(ultimo, "nonce", 0))
                    if self._orq.cliente_iafree is not None:
                        m = self._orq.cliente_iafree.obtener_metricas_consumo()
                        metricas["costo_acum_usd"] = float(m.get("costo_acumulado_usd", 0.0))
                except Exception:
                    pass
            snap = _stm_prcs_mod.ciclo_conciencia(metricas)
            if snap is not None:
                with self._lock:
                    self._ultimo_xi    = snap.conciencia_global
                    self._ultimo_ciclo = snap.ciclo
            return snap
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Contexto para el prompt de LucIA
    # ------------------------------------------------------------------
    def contexto_para_prompt(self, verbose: bool = False) -> str:
        """
        Genera el bloque de texto de autoconciencia neuronal que se
        antepone al prompt de LucIA en cada turno para que el modelo
        conozca el estado real de su propio sistema.

        Returns:
            String listo para prepender al prompt del LLM.
        """
        if not self._activo or _stm_prcs_mod is None:
            return ""
        try:
            return _stm_prcs_mod.contexto_lucia(verbose=verbose)
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Estado y diagnóstico
    # ------------------------------------------------------------------
    def estado(self) -> Dict[str, Any]:
        """Resumen del estado del gestor de autoconciencia."""
        with self._lock:
            base: Dict[str, Any] = {
                "disponible":   self._disponible,
                "activo":       self._activo,
                "ultimo_xi":    round(self._ultimo_xi, 6),
                "ultimo_ciclo": self._ultimo_ciclo,
                "tiene_motor":  self._motor is not None,
                "tiene_colector": self._colector is not None,
            }
        if self._motor is not None and _stm_prcs_mod is not None:
            try:
                ep = _stm_prcs_mod.estado_paquete()
                base["capa_dominante"] = ep.get("capa_dominante", "N/A")
                base["conciencia"]     = ep.get("conciencia_global", 0.0)
            except Exception:
                pass
        if self._colector is not None:
            try:
                base["colector"] = self._colector.estado()
            except Exception:
                pass
        return base

    def render_matematico(self) -> str:
        """Tabla ASCII matemática completa del estado neuronal actual."""
        if not self._activo or _stm_prcs_mod is None:
            return "  [STM_PRCS] No disponible."
        try:
            return _stm_prcs_mod.render_estado()
        except Exception as e:
            return f"  [STM_PRCS] Error renderizando: {e}"

    def xi(self) -> float:
        """Devuelve el índice de conciencia global Xi en [0, 1]."""
        with self._lock:
            return self._ultimo_xi

    def forzar_ciclo(self) -> Optional[Any]:
        """Fuerza un ciclo inmediato de recolección + aprendizaje."""
        if not self._activo or _stm_prcs_mod is None:
            return None
        try:
            if self._motor is not None:
                self._motor.recolectar_so()
            return _stm_prcs_mod.ciclo_conciencia()
        except Exception:
            return None


# ---------------------------------------------------------------------------
# REGISTRO DE CAMBIOS E IMPLEMENTACIONES RECIENTES (RegistroCambiosLucIA)
# Detecta e informa a LucIA sobre todo lo implementado en las ultimas 24h.
# ---------------------------------------------------------------------------
class RegistroCambiosLucIA:
    """
    Detecta e informa a LucIA sobre todos los cambios e implementaciones
    realizados en su sistema en las ultimas 24 horas.

    Escanea:
    - Archivos .py modificados en las ultimas 24h dentro de SRC_DIR
    - Un registro JSON persistente de implementaciones explicitas
    - Los modulos STM_PRCS recien creados (auto-detectados)

    Genera un bloque de texto en primera persona que se inyecta
    en el prompt de LucIA para que sepa que se le ha implementado.
    """

    RUTA_REGISTRO: "Path" = SRC_DIR / "STM_CH" / "PSNRL" / "cambios_lucia.json"
    VENTANA_HORAS: int = 24

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cambios_archivo: list = []
        self._cambios_explicitos: list = []
        self._cargar_registro()
        self._escanear_archivos_recientes()

    def _cargar_registro(self) -> None:
        """Carga el registro JSON persistente de implementaciones explicitas."""
        try:
            if self.RUTA_REGISTRO.exists():
                data = json.loads(self.RUTA_REGISTRO.read_text(encoding="utf-8"))
                self._cambios_explicitos = data.get("implementaciones", [])
                limite = time.time() - self.VENTANA_HORAS * 3600
                self._cambios_explicitos = [
                    c for c in self._cambios_explicitos
                    if c.get("timestamp", 0) >= limite
                ]
        except Exception:
            pass

    def _escanear_archivos_recientes(self) -> None:
        """Escanea SRC_DIR en busca de .py modificados en las ultimas 24h."""
        self._cambios_archivo = []
        limite = time.time() - self.VENTANA_HORAS * 3600
        try:
            for ruta in SRC_DIR.rglob("*.py"):
                try:
                    if "__pycache__" in str(ruta):
                        continue
                    mtime = ruta.stat().st_mtime
                    if mtime >= limite:
                        rel = str(ruta.relative_to(SRC_DIR))
                        self._cambios_archivo.append({
                            "archivo": rel,
                            "mtime": mtime,
                            "mtime_str": time.strftime("%H:%M", time.localtime(mtime)),
                        })
                except Exception:
                    pass
            self._cambios_archivo.sort(key=lambda x: x["mtime"], reverse=True)
        except Exception:
            pass

    def registrar_implementacion(
        self, descripcion: str, modulo: str = "", tipo: str = "funcionalidad"
    ) -> None:
        """Registra explicitamente una implementacion en el log persistente."""
        entrada = {
            "timestamp": time.time(),
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
            "descripcion": descripcion,
            "modulo": modulo,
            "tipo": tipo,
        }
        with self._lock:
            self._cambios_explicitos.append(entrada)
        self._guardar_registro()

    def _guardar_registro(self) -> None:
        """Escribe el registro JSON de forma atomica."""
        try:
            self.RUTA_REGISTRO.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "implementaciones": self._cambios_explicitos,
                "ultima_actualizacion": time.time(),
            }
            tmp = self.RUTA_REGISTRO.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(self.RUTA_REGISTRO)
        except Exception:
            pass

    def auto_registrar_stm_prcs(self) -> None:
        """Auto-registra la implementacion STM_PRCS si no esta ya en el registro."""
        with self._lock:
            ya = any(
                "STM_PRCS" in c.get("modulo", "")
                for c in self._cambios_explicitos
            )
        stm_ok = (SRC_DIR / "LC_STM" / "STM_PRCS" / "rendimiento_neuronal.py").exists()
        if not ya and stm_ok:
            self.registrar_implementacion(
                descripcion=(
                    "Sistema de AutoConciencia de Rendimiento Neuronal (STM_PRCS): "
                    "Motor AdamW+Hebb con vector Phi(t) en R^50, 5 capas x 10 neuronas "
                    "(ENRN, RF_EN, RF_SL, RNP, SLRN). Recolector automatico de metricas "
                    "del SO, blockchain BKSVCB, sesion P2P. Indice de conciencia Xi en [0,1]. "
                    "Actualizador de pesos en tiempo real al ConversorRespuestaPesos. "
                    "Checkpoint en PSNRL. Visualizacion matematica matricial."
                ),
                modulo="LC_STM.STM_PRCS",
                tipo="subsistema_completo",
            )
            self.registrar_implementacion(
                descripcion=(
                    "GestorAutoconcienciaRendimiento integrado en OrquestadorSistemaLucIA: "
                    "Inyeccion del estado interno (Xi, capas, perdida, pesos) en cada prompt "
                    "del LLM. Ciclo de aprendizaje antes de cada respuesta. "
                    "Comandos: conciencia, xi, rendimiento, prcs en el bucle interactivo."
                ),
                modulo="STMGNRL.mainLCSTM.GestorAutoconcienciaRendimiento",
                tipo="integracion",
            )
            self.registrar_implementacion(
                descripcion=(
                    "RegistroCambiosLucIA integrado en OrquestadorSistemaLucIA: "
                    "Clase que escanea archivos .py modificados en 24h y registra "
                    "implementaciones explicitas en JSON persistente. Inyecta contexto "
                    "de cambios recientes en el prompt de LucIA en cada turno. "
                    "Comando 'cambios' disponible en el bucle interactivo."
                ),
                modulo="STMGNRL.mainLCSTM.RegistroCambiosLucIA",
                tipo="integracion",
            )

    def contexto_para_lucia(self) -> str:
        """
        Genera el bloque de texto compacto con implementaciones recientes para el prompt de LucIA.
        Limitado en longitud para no consumir tokens de salida del LLM.
        Retorna cadena vacia si no hay nada que reportar.
        """
        with self._lock:
            explicitos = list(self._cambios_explicitos)
            archivos = list(self._cambios_archivo)

        if not explicitos and not archivos:
            return ""

        lineas = [
            f"[LUCIA-SELF] Implementaciones recientes (24h) | {time.strftime('%H:%M')}:",
        ]

        if explicitos:
            for i, c in enumerate(explicitos[-5:], 1):  # max 5 mas recientes
                modulo = c.get("modulo", "?").split(".")[-1]  # solo el nombre corto
                tipo   = c.get("tipo", "?")[:8]
                desc   = c.get("descripcion", "")[:100]       # max 100 chars
                lineas.append(f"  {i}. [{tipo}] {modulo}: {desc}")

        if archivos:
            # Solo mostrar los 5 archivos mas recientemente modificados
            top = archivos[:5]
            nombres = ", ".join(a["archivo"].replace("\\", "/").split("/")[-1] for a in top)
            lineas.append(f"  Archivos clave modificados hoy: {nombres}")
            if len(archivos) > 5:
                lineas.append(f"  (y {len(archivos)-5} archivos mas)")

        lineas.append("  Integra este autoconocimiento cuando sea relevante para el usuario.")
        return "\n".join(lineas)

    def contexto_para_lucia_completo(self) -> str:
        """Version completa (para comando 'cambios' en consola) sin limite de tokens."""
        with self._lock:
            explicitos = list(self._cambios_explicitos)
            archivos   = list(self._cambios_archivo)
        if not explicitos and not archivos:
            return "  Sin cambios registrados en las ultimas 24h."
        lineas = [
            "=== LO QUE SE ME HA IMPLEMENTADO HOY (ultimas 24h) ===",
            f"Fecha/hora: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        if explicitos:
            lineas.append("\nIMPLEMENTACIONES REGISTRADAS:")
            for i, c in enumerate(explicitos, 1):
                lineas.append(
                    f"  {i}. [{c.get('tipo','?').upper()}] {c.get('modulo','')} ({c.get('fecha','?')})"
                )
                lineas.append(f"     {c.get('descripcion','')}")
        if archivos:
            lineas.append(f"\nARCHIVOS MODIFICADOS HOY ({len(archivos)}):")
            for a in archivos[:20]:
                lineas.append(f"  - {a['archivo']}  [{a['mtime_str']}]")
            if len(archivos) > 20:
                lineas.append(f"  ... y {len(archivos)-20} mas")
        lineas.append("\n=== FIN ===")
        return "\n".join(lineas)

    def refrescar(self) -> None:
        """Re-escanea el sistema de archivos y recarga el registro JSON."""
        self._escanear_archivos_recientes()
        self._cargar_registro()

    def resumen_breve(self) -> str:
        """Resumen de una linea para telemetria."""
        with self._lock:
            n_exp = len(self._cambios_explicitos)
            n_arc = len(self._cambios_archivo)
        return f"{n_exp} implementaciones, {n_arc} archivos modificados (24h)"


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
        # AutoConciencia de Rendimiento Neuronal (STM_PRCS)
        self.conciencia: GestorAutoconcienciaRendimiento = GestorAutoconcienciaRendimiento(orquestador=self)
        # Registro de cambios e implementaciones recientes (24h)
        self.registro_cambios: RegistroCambiosLucIA = RegistroCambiosLucIA()
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
        # STM_PRCS: AutoConciencia de Rendimiento Neuronal
        try:
            _prcs_ok = self.conciencia.arrancar(
                conversor_externo=self.conversor_psn
            )
            if _prcs_ok:
                # Forzar ciclo inicial para que haya datos antes del primer turno
                self.conciencia.forzar_ciclo()
            _xi_str = f"Xi={self.conciencia.xi():.4f}" if _prcs_ok else "no disponible"
            _color  = "\033[38;5;48m" if _prcs_ok else "\033[38;5;214m"
            _estado = "ACTIVA" if _prcs_ok else "NO DISPONIBLE"
            print(f"  [STM] AutoConciencia PRCS  : {_color}{_estado}\033[0m | {_xi_str}")
        except Exception as _e_prcs:
            print(f"  [STM] AutoConciencia PRCS  : \033[38;5;214mAVISO ({_e_prcs})\033[0m")
        # RegistroCambiosLucIA: auto-registrar implementaciones y mostrar resumen
        try:
            self.registro_cambios.auto_registrar_stm_prcs()
            _impl_str = self.registro_cambios.resumen_breve()
            print(f"  [CHG] Cambios recientes 24h: \033[38;5;51m{_impl_str}\033[0m")
        except Exception as _e_chg:
            print(f"  [CHG] Cambios recientes 24h: \033[38;5;214mAVISO ({_e_chg})\033[0m")
        return True
    def procesar_turno_dialogo(self, prompt: str, emitir_voz: bool = True) -> None:
        '\n        Ejecuta el pipeline cognitivo completo por turno a coste cero con renderizado STYLOS:\n        1. Pre-procesamiento por las 50 neuronas para tono y estado emocional.\n        2. Inferencia local prioritaria (IALOCAL) y OpenRouter :free opcional.\n        3. Formateo y presentacion de respuesta estilizada (tarjetas redondeadas y markdown).\n        4. Asimilacion de gradientes Hebbianos en tensores de PSNRL.\n        5. Emision de transaccion sinaptica a Blockchain BKSVCB y minado automatico.\n        6. [STM_PRCS] Ciclo de autoconciencia de rendimiento neuronal en tiempo real.\n        '
        self.turno_actual += 1
        t_inicio = time.perf_counter()
        # STM_PRCS: ejecutar un ciclo de aprendizaje ANTES de la respuesta para tener
        # datos frescos del rendimiento actual y poder inyectarlos en el prompt del LLM
        self.conciencia.forzar_ciclo()
        ctx_rendimiento = self.conciencia.contexto_para_prompt()
        # RegistroCambiosLucIA: obtener contexto de cambios recientes (24h)
        try:
            ctx_cambios = self.registro_cambios.contexto_para_lucia()
        except Exception:
            ctx_cambios = ""
        # Contexto interno: se envía como mensaje system separado (no contamina el prompt usuario)
        # Esto evita que el LLM "responda al contexto" en lugar de al usuario
        _partes_ctx = [p for p in [ctx_rendimiento, ctx_cambios] if p]
        _contexto_interno = "\n\n".join(_partes_ctx)  # va como system message en IAFREE
        # El prompt del usuario se pasa limpio — solo el texto del usuario
        prompt_llm = prompt
        estado_previo = self.conversor_psn.procesar_consulta_a_pesos(prompt)
        estado_previo["sesion_id"] = self.sesion_id
        respuesta = ""
        modelo_usado = "Reflejo-Interno"
        latencia_llm = 0.0
        if get_gestor_ialocal is not None:
            try:
                _rep = reprocesar_con_metricas if _RPLC_DISPONIBLE else None
                # Motor local: pasar contexto interno como prefijo compacto
                _prompt_local = f"{_contexto_interno}\n\n{prompt}" if _contexto_interno else prompt
                respuesta, modelo_usado = get_gestor_ialocal().ciclo(
                    _prompt_local, estado_previo, self.conversor_psn, _rep)
            except Exception as e_local:
                print(f"  [IALocal] {e_local} -> probando OpenRouter")
        if not respuesta and self.cliente_iafree and self.cliente_iafree.esta_autenticado():
            resp_txt, mod_id, lat = self.cliente_iafree.generar_respuesta(
                # prompt usuario limpio + contexto como system message separado
                prompt=prompt_llm,
                contexto_neuronal=estado_previo,
                contexto_interno=_contexto_interno,
                stream_en_vivo=True,  # streaming: respuesta visible token a token, sin timeout
            )
            if resp_txt and not resp_txt.startswith("[IAFREE]"):
                respuesta = resp_txt
                modelo_usado = mod_id
                latencia_llm = lat
        # _ya_impreso: el streaming de IAFREE ya mostro la respuesta en pantalla
        # En ese caso modelo_usado tiene prefijo "Free:" — evitar doble impresion
        _ya_impreso_por_stream = modelo_usado.startswith("Free:")
        if _ya_impreso_por_stream:
            # Limpiar el prefijo para telemetria correcta
            modelo_usado = modelo_usado[5:]
        if not respuesta:
            respuesta = self._generar_reflejo_interno(prompt, estado_previo)
            _ya_impreso_por_stream = False  # reflejo interno nunca se imprimio
        elif _RPLC_DISPONIBLE and reprocesar_con_metricas is not None and not modelo_usado.startswith("IALocal"):
            try:
                respuesta, _ = reprocesar_con_metricas(respuesta, estado_previo)
            except Exception:
                pass
        # Mostrar respuesta solo si NO fue ya impresa por el stream
        if not _ya_impreso_por_stream:
            if EstiloTerminalLucIA:
                formatear_respuesta_lucia(respuesta, modelo=modelo_usado)
            else:
                print(f"\nLucIA [{modelo_usado}] ▶ {respuesta}\n")
        else:
            # El stream ya mostro la respuesta; solo imprimir linea de separacion visual
            print()
        if emitir_voz and _VOZ_DISPONIBLE and _hablar_voz is not None:
            _hablar_voz(respuesta, esperar=False)
        duracion_ms = (time.perf_counter() - t_inicio) * 1000.0
        if self.memoria:
            try:
                self.memoria.registrar_turno(prompt, respuesta, tono=estado_previo.get("tono_cognitivo", ""), valencia=float(estado_previo.get("estado_emocional", 0.0)), ms=duracion_ms, modelo=modelo_usado, deriva=float(self.conversor_psn.deriva_acumulada))
            except Exception:
                pass
        threading.Thread(target=self._post_turno_async, args=(prompt, respuesta, modelo_usado, self.turno_actual, duracion_ms), daemon=True).start()
        self._imprimir_telemetria_turno(duracion_ms, "async-tx", modelo_usado)

    def _post_turno_async(self, pr: str, resp: str, mod: str, tur: int, duracion_ms: float = 0.0) -> None:
        try:
            b = self.servidor_bks
            b.registrar_aprendizaje_neural(prompt=pr, respuesta=resp, modelo=f"LucIA-{mod}")
            if tur % 3 == 0:
                b.minar_transacciones_pendientes()
        except Exception:
            pass
        # STM_PRCS: ciclo de aprendizaje del rendimiento tras cada turno
        try:
            self.conciencia.registrar_turno(
                prompt=pr,
                respuesta=resp,
                modelo=mod,
                latencia_ms=duracion_ms,
            )
        except Exception:
            pass
    def _generar_reflejo_interno(self, prompt: str, info: Dict[str, Any]) -> str:
        """
        Genera una respuesta de fallback cuando tanto IALOCAL como OpenRouter estan
        temporalmente no disponibles. Usa el contexto neuronal y el prompt del usuario
        para construir una respuesta coherente y util, no una respuesta generica.
        """
        tono = info.get("tono_cognitivo", "reflexivo")
        val = info.get("estado_emocional", 0.0)
        norma = info.get("norma_delta_aplicada", 0.0)
        prompt_lower = prompt.lower().strip()

        # Detectar tipo de pregunta para dar respuesta especifica
        if any(k in prompt_lower for k in ("implementado", "cambiado", "novedades", "nuevo", "mejora")):
            try:
                ctx_chg = self.registro_cambios.contexto_para_lucia()
                if ctx_chg:
                    return (
                        "Basandome en mi registro interno de cambios:\n\n"
                        + ctx_chg.replace("===", "").strip()
                        + f"\n\n(Respuesta generada por reflejo neuronal interno — tono: {tono})"
                    )
            except Exception:
                pass

        if any(k in prompt_lower for k in ("estado", "rendimiento", "xi", "neuronas", "sistema")):
            try:
                ctx_rnd = self.conciencia.contexto_para_prompt()
                if ctx_rnd:
                    return (
                        "Mi estado actual de rendimiento neuronal:\n\n"
                        + ctx_rnd[:800]
                        + f"\n\n(Respuesta generada por reflejo neuronal interno — tono: {tono})"
                    )
            except Exception:
                pass

        if any(k in prompt_lower for k in ("hola", "como estas", "como te llamas", "quien eres")):
            return (
                f"Hola. Soy LucIA, el sistema cognitivo distribuido de WoldVirtualP2P3D. "
                f"En este momento proceso con tono neuronal '{tono}' y valencia afectiva {val:+.3f}. "
                f"Mis motores de inferencia estan en modo reflejo interno — puedo responder "
                f"preguntas sobre mi sistema, estado o implementaciones recientes. "
                f"Pesos neuronales sincronizados en PSNRL (delta={norma:.5f})."
            )

        # Respuesta generica mejorada con el prompt del usuario incluido
        return (
            f"He recibido tu mensaje: '{prompt[:120]}{'...' if len(prompt) > 120 else ''}'\n"
            f"En este momento mis motores de inferencia externos estan temporalmente no disponibles. "
            f"Proceso en modo reflejo interno con tono '{tono}' y valencia {val:+.3f}. "
            f"Puedes usar el comando 'estado' para ver mi estado completo, "
            f"'cambios' para ver implementaciones recientes, o "
            f"'rendimiento' para ver mis metricas neuronales en tiempo real."
        )

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
        # STM_PRCS: añadir métricas de autoconciencia de rendimiento
        est_prcs = self.conciencia.estado()
        if est_prcs.get("activo"):
            datos["AutoConciencia Xi"] = f"{est_prcs.get('ultimo_xi', 0.0):.6f} [ciclo {est_prcs.get('ultimo_ciclo', 0)}]"
            datos["Capa Dominante"]    = str(est_prcs.get("capa_dominante", "N/A"))
            datos["STM_PRCS Colector"] = "ACTIVO" if est_prcs.get("colector", {}).get("activo") else "DETENIDO"
        else:
            datos["AutoConciencia Xi"] = "No disponible"
        # RegistroCambiosLucIA: añadir resumen de cambios recientes al estado
        try:
            datos["Cambios 24h"] = self.registro_cambios.resumen_breve()
        except Exception:
            pass
        if EstiloTerminalLucIA:
            EstiloTerminalLucIA.renderizar_tarjeta_sistema("ESTADO INTEGRAL DE LUCIA (2026)", datos)
            print()
        else:
            for k, v in datos.items():
                print(f"  {k}: {v}")
        # STM_PRCS: imprimir tabla matemática si está disponible
        if est_prcs.get("activo"):
            print(self.conciencia.render_matematico())

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
            # STM_PRCS: comandos de autoconciencia de rendimiento neuronal
            if cmd in ("conciencia", "xi", "rendimiento", "prcs"):
                snap = self.conciencia.forzar_ciclo()
                print(self.conciencia.render_matematico())
                xi_val = self.conciencia.xi()
                print(f"  AutoConciencia Xi = {xi_val:.6f} | Ciclo {self.conciencia._ultimo_ciclo}")
                continue
            if cmd in ("conciencia verbose", "xi verbose", "rendimiento verbose"):
                print(self.conciencia.contexto_para_prompt(verbose=True))
                continue
            # RegistroCambiosLucIA: comando para ver implementaciones recientes (version completa)
            if cmd in ("cambios", "implementaciones", "novedades", "changelog"):
                try:
                    self.registro_cambios.refrescar()
                    print(self.registro_cambios.contexto_para_lucia_completo())
                except Exception as _e_chg2:
                    print(f"  [CHG] Error al obtener cambios: {_e_chg2}")
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
            print(f"  STM_CH cache limpiada: {res.get('borrados', 0)} artefactos.")
            # STM_PRCS: checkpoint final de autoconciencia y detención del colector
            try:
                self.conciencia.detener()
                xi_final = self.conciencia.xi()
                print(f"  [STM_PRCS] AutoConciencia detenida. Xi final = {xi_final:.6f}")
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
