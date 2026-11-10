"""
_imports.py - Módulo mediador de importaciones condicionales y resolución de dependencias
========================================================================================
Centraliza todas las importaciones dinámicas y defensivas de STMGNRL para evitar
bloques try/except frágiles dispersos en el orquestador principal.
"""
from __future__ import annotations
import logging
from typing import Any, Callable, Dict, Final, List, Optional, Tuple, Type, Union

logger = logging.getLogger("WoldVirtualP2P3D.STMGNRL._imports")

# 1. Inicialización de rutas STM_CH
def init_stmch_rutas() -> bool:
    try:
        from STM_CH.rutas import inicializar as _stmch_init
        _stmch_init()
        return True
    except Exception as err:
        logger.debug("STM_CH.rutas.inicializar no disponible: %s", err)
        return False


# 2. RFPRMN (Gestión de comandos y archivos)
try:
    import RFPRMN as _RFPRMN  # pyrefly: ignore[missing-import]
    RFPRMN_DISPONIBLE: bool = True
    modulo_rfprmn: Any = _RFPRMN
except Exception:
    RFPRMN_DISPONIBLE = False
    modulo_rfprmn = None


# 3. IAFREE (OpenRouter Free Tier)
try:
    from SBSTM.IAFREE import ClienteIAFree, get_cliente_iafree
except Exception:
    try:
        from LC.celebro.CMFG.SBSTM.IAFREE import ClienteIAFree, get_cliente_iafree  # pyrefly: ignore[missing-import]
    except Exception:
        ClienteIAFree = None  # type: ignore
        get_cliente_iafree = None  # type: ignore


# 4. STYLOS (Interfaz de terminal y renderizado ANSI)
try:
    from SBSTM.STYLOS import (
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
    from SBSTM.RPLC import get_procesador_rplc, reprocesar_con_metricas
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
    from SBSTM.voice_engine import (
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
    from SBSTM.selector_modelos import SelectorModelos
except ImportError:
    try:
        from src.SBSTM.selector_modelos import SelectorModelos  # type: ignore
    except ImportError:
        class SelectorModelos:  # type: ignore
            pass


# 8. Accesores STM_JSON y STM_HRTS
try:
    from SBSTM.accesores import GestorHRTLucIA, GestorJSONLucIA
except ImportError:
    GestorJSONLucIA = None  # type: ignore
    GestorHRTLucIA = None  # type: ignore


# 9. Gestor IA Local
try:
    from STM_IA.modelosIAlocal.IALOCAL import get_gestor_ialocal
except ImportError:
    get_gestor_ialocal = None  # type: ignore


# 10. Watchdog adaptativo
try:
    from SBSTM.watchdog import arrancar_watchdog
    WATCHDOG_DISPONIBLE: bool = True
except Exception:
    WATCHDOG_DISPONIBLE = False
    arrancar_watchdog = None  # type: ignore


# 11. Memoria de Sesión
try:
    from SBSTM.memoria_sesion import MemoriaSesion, get_memoria
    MEMORIA_DISPONIBLE: bool = True
except Exception:
    MEMORIA_DISPONIBLE = False
    MemoriaSesion = None  # type: ignore
    get_memoria = None  # type: ignore


# 12. Helpers funcionales para subsistemas bajo demanda
def get_openrouter_vault_key() -> str:
    try:
        from STM_SGR.vault_openrouter import obtener_key
        k = obtener_key()
        return k or ""
    except Exception:
        return ""


def confirmar_vault_openrouter() -> None:
    try:
        from STM_SGR.vault_openrouter import confirmar_conexion
        confirmar_conexion()
    except Exception:
        pass


def registrar_key_vault_openrouter() -> None:
    from STM_SGR.vault_openrouter import registrar_key_usuario
    registrar_key_usuario()


def obtener_componentes_blockchain() -> Tuple[Any, Any]:
    from STM_BKCH.BKSVCB import get_blockchain_server, iniciar_servidor_blockchain
    return get_blockchain_server, iniciar_servidor_blockchain


def obtener_conversor_pesos_blockchain() -> Any:
    from STM_BKCH.compat_local import get_conversor_pesos
    return get_conversor_pesos()


def instanciar_sesion_p2p() -> Any:
    from SBSTM import obtener_clase_sesion
    cls_sesion = obtener_clase_sesion()
    return cls_sesion()


def limpiar_rutas_stmch() -> Dict[str, Any]:
    try:
        from STM_CH.rutas import limpiar as _stmch_limpiar
        return _stmch_limpiar()
    except Exception as err:
        logger.debug("Error limpiando STM_CH: %s", err)
        return {"borrados": 0}
