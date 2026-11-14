"""
_imports.py - Módulo mediador de importaciones condicionales y resolución de dependencias
========================================================================================
Centraliza todas las importaciones dinámicas y defensivas de STMGNRL para evitar
bloques try/except frágiles dispersos en el orquestador principal.
"""
from __future__ import annotations
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional, Tuple, Type, Union

logger = logging.getLogger("WoldVirtualP2P3D.STMGNRL._imports")

# 1. Inicialización de rutas STM_CH
def init_stmch_rutas() -> bool:
    try:
        from STM_CH.STM_herramientas.rutas import inicializar as _stmch_init
        _stmch_init()
        return True
    except Exception as err:
        logger.debug("STM_CH.rutas.inicializar no disponible: %s", err)
        return False


# 2. RFPRMN (Gestión de comandos y archivos)
# La herramienta vive en CONTRRF/STM_RFC/STM_RFPRMN (cuatro niveles por encima
# de STMGNRL), no en TLLDCD/STM_RFC; sin esta ruta el import fallaba siempre.
try:
    from STM_CH.STM_herramientas.rutas_json import obtener as _obtener_ruta_json
except Exception:  # pragma: no cover
    _obtener_ruta_json = None

if _obtener_ruta_json is not None:
    try:
        _RFPRMN_DIR: Final[Path] = _obtener_ruta_json("runtime.rfprmn_dir")
    except Exception:
        _RFPRMN_DIR: Final[Path] = (Path(__file__).resolve().parents[4]
                                    / "STM_RFC" / "STM_RFPRMN")
else:
    _RFPRMN_DIR: Final[Path] = (Path(__file__).resolve().parents[4]
                                / "STM_RFC" / "STM_RFPRMN")
if _RFPRMN_DIR.is_dir() and str(_RFPRMN_DIR) not in sys.path:
    sys.path.insert(0, str(_RFPRMN_DIR))
try:
    import RFPRMN as _RFPRMN  # pyrefly: ignore[missing-import]
    RFPRMN_DISPONIBLE: bool = True
    modulo_rfprmn: Any = _RFPRMN
except Exception as _err_rfprmn:
    RFPRMN_DISPONIBLE = False
    modulo_rfprmn = None
    logger.debug("RFPRMN no disponible en %s: %s", _RFPRMN_DIR, _err_rfprmn)


# 3. IAFREE (OpenRouter Free Tier)
try:
    from SBSTM.SistemasLC.STM_SBTM_1.IAFREE import ClienteIAFree, get_cliente_iafree
except Exception:
    try:
        from LC.celebro.CMFG.SBSTM.IAFREE import ClienteIAFree, get_cliente_iafree  # pyrefly: ignore[missing-import]
    except Exception:
        ClienteIAFree = None  # type: ignore
        get_cliente_iafree = None  # type: ignore


# 4. STYLOS (Interfaz de terminal y renderizado ANSI)
try:
    from SBSTM.SistemasLC.STM_SBTM_3.STYLOS import (
        ColoresLucIA,
        EstiloTerminalLucIA,
        Glifos,
        badge_turno,
        banner_bienvenida,
        formatear_respuesta_lucia,
        panel_ayuda_comandos,
    )
except Exception:
    try:
        from LC.celebro.CMFG.SBSTM.STYLOS import (  # pyrefly: ignore[missing-import]
            ColoresLucIA,
            EstiloTerminalLucIA,
            Glifos,
            badge_turno,
            banner_bienvenida,
            formatear_respuesta_lucia,
            panel_ayuda_comandos,
        )
    except Exception:
        ColoresLucIA = None  # type: ignore
        EstiloTerminalLucIA = None  # type: ignore
        Glifos = None  # type: ignore
        badge_turno = None  # type: ignore
        banner_bienvenida = None  # type: ignore
        formatear_respuesta_lucia = None  # type: ignore
        panel_ayuda_comandos = None  # type: ignore


# 5. RPLC (Reprocesador Lingüístico-Cognitivo)
try:
    from SBSTM.SistemasLC.STM_SBTM_2.RPLC import get_procesador_rplc, reprocesar_con_metricas
    RPLC_DISPONIBLE: bool = True
except Exception:
    try:
        from LC.celebro.CMFG.SBSTM.RPLC import get_procesador_rplc, reprocesar_con_metricas  # pyrefly: ignore[missing-import]
        RPLC_DISPONIBLE = True
    except Exception:
        RPLC_DISPONIBLE = False
        get_procesador_rplc = None  # type: ignore
        reprocesar_con_metricas = None  # type: ignore


# 6. Voice Engine (Voz juvenil de LucIA)
VOZ_MOTIVO: str = ""
try:
    from SBSTM.SistemasLC.STM_SBTM_3.voice_engine import (
        cancel_speech as cancelar_voz,
        configurar_prosodia_juvenil as prosodia_voz,
        speak as hablar_voz,
    )
    VOZ_DISPONIBLE: bool = True
except Exception as err_local:
    try:
        from LC.celebro.CMFG.SBSTM.voice_engine import (  # pyrefly: ignore[missing-import]
            cancel_speech as cancelar_voz,
            configurar_prosodia_juvenil as prosodia_voz,
            speak as hablar_voz,
        )
        VOZ_DISPONIBLE = True
        VOZ_MOTIVO = f"usando copia LC.celebro ({err_local})"
    except Exception as err_remoto:
        VOZ_DISPONIBLE = False
        VOZ_MOTIVO = f"local: {err_local} | remoto: {err_remoto}"
        hablar_voz = None  # type: ignore
        cancelar_voz = None  # type: ignore
        prosodia_voz = None  # type: ignore


# 7. SelectorModelos (Clase base de orquestación)
try:
    from SBSTM.SistemasLC.STM_SBTM_2.selector_modelos import SelectorModelos
except ImportError:
    try:
        from SBSTM.SistemasLC.STM_SBTM_2.selector_modelos import SelectorModelos  # type: ignore
    except ImportError:
        class SelectorModelos:  # type: ignore
            pass


# 8. Accesores STM_JSON y STM_HRTS
try:
    from SBSTM.SistemasLC.STM_SBTM_1.accesores import GestorHRTLucIA, GestorJSONLucIA
except ImportError:
    GestorJSONLucIA = None  # type: ignore
    GestorHRTLucIA = None  # type: ignore


# 9. Gestor IA Local
try:
    from STM_IA.STM_Informacion.modelosIAlocal.IALOCAL import get_gestor_ialocal
except ImportError:
    get_gestor_ialocal = None  # type: ignore


# 10. Watchdog adaptativo
try:
    from SBSTM.SistemasLC.STM_SBTM_3.watchdog import arrancar_watchdog
    WATCHDOG_DISPONIBLE: bool = True
except Exception:
    WATCHDOG_DISPONIBLE = False
    arrancar_watchdog = None  # type: ignore


# 11. Memoria de Sesión
try:
    from SBSTM.SistemasLC.STM_SBTM_2.memoria_sesion import MemoriaSesion, get_memoria
    MEMORIA_DISPONIBLE: bool = True
except Exception:
    MEMORIA_DISPONIBLE = False
    MemoriaSesion = None  # type: ignore
    get_memoria = None  # type: ignore


# 12. Helpers funcionales para subsistemas bajo demanda
def get_openrouter_vault_key() -> str:
    try:
        from STM_SGR.STM_CNX.vault_openrouter import obtener_key
        k = obtener_key()
        return k or ""
    except Exception:
        return ""


def confirmar_vault_openrouter() -> None:
    try:
        from STM_SGR.STM_CNX.vault_openrouter import confirmar_conexion
        confirmar_conexion()
    except Exception:
        pass


def registrar_key_vault_openrouter() -> None:
    from STM_SGR.STM_CNX.vault_openrouter import registrar_key_usuario
    registrar_key_usuario()


def obtener_componentes_blockchain() -> Tuple[Any, Any]:
    from STM_BKCH.stm_bkch1.BKSVCB import get_blockchain_server, iniciar_servidor_blockchain
    return get_blockchain_server, iniciar_servidor_blockchain


def importar_agente() -> Any:
    """Clase AgenteRFPRMN para que LucIA use los comandos sin humano.

    Devuelve ``None`` si RFPRMN no está disponible o si el agente no importa:
    LucIA debe poder seguir funcionando sin su máquina de comandos.
    """
    if not RFPRMN_DISPONIBLE:
        return None
    try:
        from STM_RFPRMN_stmDL.stm_agente import AgenteRFPRMN

        return AgenteRFPRMN
    except Exception as err:  # noqa: BLE001 - dependencia opcional
        logger.debug("Agente RFPRMN no importable: %s", err)
        return None


def _ruta_canonica_constructor() -> Optional[Path]:
    """Ruta de ``LC_constructor.py`` declarada en ``Rutas.json``.

    Se prefiere la clave ``archivos.LC_constructor`` para que el sistema
    principal ejecute siempre el modulo canonico, sin depender del ``cwd`` ni
    de otro ``LC_constructor`` que aparezca antes en ``sys.path``.
    """
    if _obtener_ruta_json is not None:
        try:
            ruta = Path(_obtener_ruta_json("archivos.LC_constructor"))
            if ruta.is_file():
                return ruta
        except Exception:
            pass
    candidata = _RFPRMN_DIR / "LC_constructor.py"
    return candidata if candidata.is_file() else None


def importar_constructor() -> Any:
    """Módulo ``LC_constructor`` para que LucIA cree jerarquías sola.

    Se carga desde la ruta canonica de ``Rutas.json`` y su salida se fija en
    ``runtime.lc_trabajando`` (``CONTRRF/CONTRUCCION/LCtrabajando``). Si no
    importa, LucIA sigue conversando y el resto de comandos sigue disponible.
    """
    if not RFPRMN_DISPONIBLE:
        return None
    ruta = _ruta_canonica_constructor()
    try:
        if ruta is not None:
            existente = sys.modules.get("LC_constructor")
            if (existente is not None
                    and Path(str(getattr(existente, "__file__", ""))).resolve()
                    == ruta.resolve()):
                return existente
            especificacion = importlib.util.spec_from_file_location(
                "LC_constructor", ruta)
            if especificacion is None or especificacion.loader is None:
                raise ImportError(f"No se puede cargar {ruta}")
            modulo = importlib.util.module_from_spec(especificacion)
            sys.modules["LC_constructor"] = modulo
            especificacion.loader.exec_module(modulo)
        else:
            import LC_constructor  # pyrefly: ignore[missing-import]
            modulo = LC_constructor
        _aplicar_ruta_trabajo(modulo)
        return modulo
    except Exception as err:  # noqa: BLE001 - constructor opcional
        logger.debug("LC_constructor no importable (%s): %s", ruta, err)
        return None


def _aplicar_ruta_trabajo(modulo: Any) -> None:
    """Alinea la salida de ``LC_constructor`` con ``runtime.lc_trabajando``."""
    if _obtener_ruta_json is None:
        return
    try:
        trabajo = Path(_obtener_ruta_json("runtime.lc_trabajando"))
    except Exception:
        return
    if not trabajo.is_absolute():
        trabajo = trabajo.resolve()
    modulo.RUTA_PREDETERMINADA = str(trabajo)
    modulo.RUTA_RED_PREDETERMINADA = str(trabajo / "src" / "LC_STM")
    modulo.RUTA_MTBGT_PREDETERMINADA = str(trabajo / "src" / "MTBGT")


def obtener_conversor_pesos_blockchain() -> Any:
    from STM_BKCH.stm_bkch1.compat_local import get_conversor_pesos
    return get_conversor_pesos()


def instanciar_sesion_p2p() -> Any:
    from SBSTM.SistemasLC.STM_SBTM_1 import obtener_clase_sesion
    cls_sesion = obtener_clase_sesion()
    return cls_sesion()


def limpiar_rutas_stmch() -> Dict[str, Any]:
    try:
        from STM_CH.STM_herramientas.rutas import limpiar as _stmch_limpiar
        return _stmch_limpiar()
    except Exception as err:
        logger.debug("Error limpiando STM_CH: %s", err)
        return {"borrados": 0}


def obtener_subsistema_neural() -> Any:
    try:
        from SBSTM.SistemasLC.STM_SBTM_3.subsistema_neural import get_subsistema_neural
        return get_subsistema_neural()
    except Exception as err:
        logger.debug("Subsistema neural no disponible: %s", err)
        return None


def obtener_subsistema_evolutivo() -> Any:
    try:
        from SBSTM.SistemasLC.STM_SBTM_3.subsistema_evolutivo import get_subsistema_evolutivo
        return get_subsistema_evolutivo()
    except Exception as err:
        logger.debug("Subsistema evolutivo no disponible: %s", err)
        return None


