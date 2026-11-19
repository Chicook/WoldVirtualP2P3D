"""
SBSTM.comandos_refactor - Comandos de Consola para Auto-Refactorizacion y Red Neuronal
======================================================================================
Extiende el registro de comandos de consola de LucIA (SBSTM.comandos)
con capacidades directas para:
  - Refactorizar codigo de infraestructura (Python / C#)
  - Refactorizar scripts y escenas del metaverso 3D (Godot GDScript / TSCN)
  - Particionar archivos grandes (> 450 lineas)
  - Enviar vectores de entrenamiento y generar nuevos pesos en runtime
  - Consultar el estado del subsistema neural y archivos en LCtrabajando.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from SBSTM.SistemasLC.STM_SBTM_1.comandos import registrar_comando
from SBSTM.SistemasLC.STM_SBTM_3.subsistema_neural import LCTRABAJANDO_DIR, get_subsistema_neural


def _cmd_refactor_infra(args: str, contexto: Any = None) -> str:
    """Refactoriza un modulo de la infraestructura guardando el resultado en LCtrabajando."""
    archivo = (args or "").strip()
    if not archivo:
        return "[refactor_infra] Uso: /refactor_infra <nombre_o_ruta_de_archivo>"
    sub = get_subsistema_neural(arrancar_socket=False)
    res = sub.refactorizar_infra(archivo)
    if res.get("ok"):
        return (
            f"[refactor_infra] EXITO:\n"
            f"  - Original : {res.get('archivo_original')} ({res.get('lineas_original')} lineas)\n"
            f"  - Generado : {res.get('archivo_generado')} ({res.get('lineas_refactor')} lineas)\n"
            f"  - Informe  : {res.get('informe')}\n"
            f"  - Destino  : {LCTRABAJANDO_DIR}"
        )
    return f"[refactor_infra] FALLO: {res.get('motivo', 'Error desconocido')}"


def _cmd_refactor_metaverso(args: str, contexto: Any = None) -> str:
    """Refactoriza un script o escena del metaverso Godot hacia LCtrabajando."""
    archivo = (args or "").strip()
    if not archivo:
        return "[refactor_metaverso] Uso: /refactor_metaverso <nombre_script_gd_o_escena>"
    sub = get_subsistema_neural(arrancar_socket=False)
    res = sub.refactorizar_metaverso(archivo)
    if res.get("ok"):
        return (
            f"[refactor_metaverso] EXITO:\n"
            f"  - Original : {res.get('archivo_original')} ({res.get('lineas_original')} lineas)\n"
            f"  - Generado : {res.get('archivo_generado')} ({res.get('lineas_refactor')} lineas)\n"
            f"  - Informe  : {res.get('informe')}\n"
            f"  - Destino  : {LCTRABAJANDO_DIR}"
        )
    return f"[refactor_metaverso] FALLO: {res.get('motivo', 'Error desconocido')}"


def _cmd_partir(args: str, contexto: Any = None) -> str:
    """Particiona un archivo grande (> 450 lineas) en subpartes en LCtrabajando."""
    partes = (args or "").strip().split(None, 1)
    if not partes:
        return "[partir] Uso: /partir <archivo> [limite_lineas=450]"
    archivo = partes[0]
    limite = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 450
    sub = get_subsistema_neural(arrancar_socket=False)
    res = sub.refactorizador.partir_modulo_grande(archivo, limite_lineas=limite)
    if res.get("ok"):
        if not res.get("particionado"):
            return f"[partir] {res.get('motivo')}"
        return (
            f"[partir] EXITO:\n"
            f"  - Parte 1: {res.get('p1')}\n"
            f"  - Parte 2: {res.get('p2')}\n"
            f"  - Plan   : {res.get('plan')}\n"
            f"  - Destino: {LCTRABAJANDO_DIR}"
        )
    return f"[partir] FALLO: {res.get('motivo')}"


def _cmd_entrenar_vector(args: str, contexto: Any = None) -> str:
    """Envia un vector de entrenamiento y actualiza los pesos de las 50 neuronas en tiempo de ejecucion."""
    texto = (args or "").strip() or "estimulo_manual"
    sub = get_subsistema_neural(arrancar_socket=False)
    res = sub.entrenar_con_vector(texto, recompensa=1.0, motivo="comando_consola")
    if res.get("ok"):
        archivos = res.get("archivos_pesos", {})
        return (
            f"[entrenar_vector] SINAPSIS ACTUALIZADAS EN RUNTIME:\n"
            f"  - Paso total : {res.get('pasos_totales')}\n"
            f"  - Deriva Muon: {res.get('deriva_acumulada')}\n"
            f"  - Norma      : {res.get('norma_tensor')}\n"
            f"  - GSNR       : {res.get('gsnr')}\n"
            f"  - Entropia   : {res.get('entropia_shannon')}\n"
            f"  - Snapshot   : {archivos.get('json_trabajando')}\n"
            f"  - NPZ        : {archivos.get('npz_trabajando')}"
        )
    return f"[entrenar_vector] FALLO: {res.get('error', 'Error desconocido')}"


def _cmd_estado_neural(args: str, contexto: Any = None) -> str:
    """Muestra el estado completo del subsistema neural y de LCtrabajando."""
    sub = get_subsistema_neural(arrancar_socket=False)
    estado = sub.despachar_peticion_socket({"accion": "estado"})
    lineas = [
        "════════════ ESTADO DEL SUBSISTEMA NEURAL SBSTM ════════════",
        f"  Canal Socket Activo   : {estado.get('socket_activo')} (Puerto: {estado.get('puerto')})",
        f"  Pasos de Entrenamiento: {estado.get('pasos_entrenamiento')}",
        f"  Deriva Muon Acumulada : {estado.get('deriva_acumulada')}",
        f"  Destino LCtrabajando  : {estado.get('directorio_trabajo')}",
        f"  Artefactos en Destino : {estado.get('archivos_en_trabajando')} archivos",
        "════════════════════════════════════════════════════════════",
    ]
    return "\n".join(lineas)


def _cmd_evolucion(args: str, contexto: Any = None) -> str:
    """Ejecuta el ciclo de 4 fases de conciencia evolutiva y muestra el informe."""
    try:
        from SBSTM.SistemasLC.STM_SBTM_3.subsistema_evolutivo import get_subsistema_evolutivo
        sub_evo = get_subsistema_evolutivo()
        res = sub_evo.ejecutar_ciclo_completo(auto_reparar=False)
        return sub_evo.generar_reporte_texto(res)
    except Exception as err:
        return f"[evolucion] Error al ejecutar ciclo: {err}"


def _cmd_autoreparar(args: str, contexto: Any = None) -> str:
    """Ejecuta el ciclo completo de 4 fases con auto-reparación y registro en diario."""
    try:
        from SBSTM.SistemasLC.STM_SBTM_3.subsistema_evolutivo import get_subsistema_evolutivo
        sub_evo = get_subsistema_evolutivo()
        res = sub_evo.ejecutar_ciclo_completo(auto_reparar=True)
        return sub_evo.generar_reporte_texto(res)
    except Exception as err:
        return f"[autoreparar] Error al auto-reparar: {err}"


def registrar_comandos_subsistema_neural() -> None:
    """Registra todos los comandos de auto-refactorizacion y red neuronal."""
    registrar_comando(
        nombre="/refactor_infra",
        funcion=_cmd_refactor_infra,
        ayuda="Refactoriza infraestructura (Python/C#) depositando el codigo en LCtrabajando",
        alias=["refactor_infra", "/refactor_codigo"],
    )
    registrar_comando(
        nombre="/refactor_metaverso",
        funcion=_cmd_refactor_metaverso,
        ayuda="Refactoriza scripts del metaverso 3D (GDScript/Godot) en LCtrabajando",
        alias=["refactor_metaverso", "/refactor_godot"],
    )
    registrar_comando(
        nombre="/partir",
        funcion=_cmd_partir,
        ayuda="Particiona archivos > 450 lineas en partes modulares dentro de LCtrabajando",
        alias=["partir", "/partir_archivo"],
    )
    registrar_comando(
        nombre="/entrenar_vector",
        funcion=_cmd_entrenar_vector,
        ayuda="Envia vector de entrenamiento a las 50 neuronas y genera nuevos pesos en runtime",
        alias=["entrenar_vector", "/entrenar"],
    )
    registrar_comando(
        nombre="/estado_neural",
        funcion=_cmd_estado_neural,
        ayuda="Muestra estado del canal socket, pesos y directorio LCtrabajando",
        alias=["estado_neural", "/neural_status"],
    )
    registrar_comando(
        nombre="/evolucion",
        funcion=_cmd_evolucion,
        ayuda="Ejecuta el ciclo de 4 fases de conciencia evolutiva y auto-diagnostico",
        alias=["evolucion", "/lucia_evolucion", "/fases_lucia"],
    )
    registrar_comando(
        nombre="/autoreparar",
        funcion=_cmd_autoreparar,
        ayuda="Ejecuta auto-diagnostico y auto-reparacion en LCtrabajando",
        alias=["autoreparar", "/autopoiesis", "/reparar_sistema"],
    )


# Auto-registro al importar el modulo
registrar_comandos_subsistema_neural()
