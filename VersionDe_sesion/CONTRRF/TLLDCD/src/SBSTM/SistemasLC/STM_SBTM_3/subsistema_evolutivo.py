"""
subsistema_evolutivo.py - Subsistema de Autopoiesis y Evolución Autónoma de LucIA
================================================================================
Implementa la arquitectura evolutiva de 4 fases para la cognición de LucIA:

  ┌──────────────────────────────────────────────────────────────┐
  │  Fase 1: Agente Ciego (Solo ejecuta comandos aislados)       │  [SUPERADA]
  │  Fase 2: Mapa Propioceptivo (Reconoce todo su ecosistema)    │  [CONSOLIDADA]
  │  Fase 3: Auto-diagnóstico (Detecta discrepancias en su ser)  │  [ACTIVA]
  │  Fase 4: Auto-reparación y Evolución Autónoma                │  [OBJETIVO VIVO]
  └──────────────────────────────────────────────────────────────┘

Todo artefacto de reparación, partición o reporte se escribe estrictamente en:
  E:\\WoldVirtualP2P3D\\VersionDe_sesion\\CONTRRF\\CONTRUCCION\\LCtrabajando
"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional, Set, Tuple

logger: logging.Logger = logging.getLogger("WoldVirtualP2P3D.SBSTM.Evolutivo")

# ─── RESOLUCION DE RUTAS Y CONSTANTES ─────────────────────────────────────────
PAQUETE_DIR: Final[Path] = Path(__file__).resolve().parent.parent.parent  # .../SBSTM
SRC_DIR: Final[Path] = PAQUETE_DIR.parent                                 # .../src
ROOT_DIR: Final[Path] = SRC_DIR.parent                                     # .../TLLDCD
CONTRRF_DIR: Final[Path] = ROOT_DIR.parent                                 # .../CONTRRF
LCTRABAJANDO_DIR: Final[Path] = CONTRRF_DIR / "CONTRUCCION" / "LCtrabajando"

if not LCTRABAJANDO_DIR.exists():
    try:
        LCTRABAJANDO_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

EXTENSIONES_ECOSISTEMA: Final[tuple] = (
    ".py", ".gd", ".cs", ".md", ".json", ".tscn", ".tres",
    ".gdshader", ".xaml", ".csproj", ".ps1", ".bat", ".sh",
)


# ═════════════════════════════════════════════════════════════════════════════
# FASE 1: AGENTE CIEGO (EJECUCIÓN DE COMANDOS AISLADOS)
# ═════════════════════════════════════════════════════════════════════════════
class FaseAgenteCiego:
    """Fase 1: Capacidad base determinista de ejecutar comandos aislados.

    Proporciona un entorno controlado para disparar comandos sin necesidad
    de comprender la totalidad del sistema, auditando cada llamada en frío.
    """

    def __init__(self) -> None:
        self.historial_ejecuciones: List[Dict[str, Any]] = []

    def ejecutar_comando_aislado(
        self, comando: str, parametros: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Ejecuta un comando atómico y audita el resultado."""
        parametros = parametros or {}
        inicio = time.time()
        exito = False
        salida: Any = None
        error_msg = ""

        try:
            if comando == "crear_directorio":
                ruta = Path(parametros.get("ruta", ""))
                ruta.mkdir(parents=True, exist_ok=True)
                salida = str(ruta)
                exito = True
            elif comando == "escribir_archivo":
                ruta = Path(parametros.get("ruta", ""))
                contenido = parametros.get("contenido", "")
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text(contenido, encoding="utf-8")
                salida = f"{ruta.name} ({len(contenido)} bytes)"
                exito = True
            elif comando == "verificar_sintaxis_py":
                codigo = parametros.get("codigo", "")
                ast.parse(codigo)
                salida = "Sintaxis Python válida"
                exito = True
            else:
                error_msg = f"Comando aislado '{comando}' no reconocido"
        except Exception as exc:
            error_msg = str(exc)

        duracion = time.time() - inicio
        registro = {
            "timestamp": datetime.now().isoformat(),
            "fase": "Fase 1 · Agente Ciego",
            "comando": comando,
            "parametros": parametros,
            "exito": exito,
            "salida": salida,
            "error": error_msg,
            "duracion_ms": round(duracion * 1000, 2),
        }
        self.historial_ejecuciones.append(registro)
        return registro


# ═════════════════════════════════════════════════════════════════════════════
# FASE 2: MAPA PROPIOCEPTIVO (RECONOCIMIENTO DEL ECOSISTEMA)
# ═════════════════════════════════════════════════════════════════════════════
class FaseMapaPropioceptivo:
    """Fase 2: Mapa propioceptivo y cartografía somatosensorial de LucIA.

    Mantiene un censo holístico de los 1200+ archivos, sus pesos neuronales
    en runtime, la estructura de paquetes y la memoria sináptica consolidada.
    """

    def __init__(self, raiz: Optional[Path] = None) -> None:
        self.raiz = raiz or ROOT_DIR
        self.censo_archivos: List[Dict[str, Any]] = []
        self.conteo_extensiones: Dict[str, int] = {}
        self.lineas_totales: int = 0
        self.estado_sinaptico: Dict[str, Any] = {}
        self.ultimo_censo_ts: float = 0.0

    def construir_mapa(self, forzar_recarga: bool = False) -> Dict[str, Any]:
        """Escanea y cartografía la infraestructura completa del proyecto."""
        ahora = time.time()
        if not forzar_recarga and self.censo_archivos and (ahora - self.ultimo_censo_ts < 300):
            return self.obtener_resumen_mapa()

        archivos = []
        conteo_ext: Dict[str, int] = {}
        total_lineas = 0

        # 1. Intentar cargar desde inventario existente si está disponible
        inv_path = LCTRABAJANDO_DIR / "inventario_codigo.json"
        if inv_path.exists() and not forzar_recarga:
            try:
                datos_inv = json.loads(inv_path.read_text(encoding="utf-8"))
                for item in datos_inv.get("archivos", []):
                    ext = Path(item["ruta"]).suffix.lower()
                    conteo_ext[ext] = conteo_ext.get(ext, 0) + 1
                    total_lineas += item.get("lineas", 0)
                    archivos.append({
                        "nombre": item.get("nombre", Path(item["ruta"]).name),
                        "ruta": item.get("ruta"),
                        "extension": ext,
                        "lineas": item.get("lineas", 0),
                        "tam_bytes": item.get("tam_bytes", 0),
                        "excede_presupuesto": item.get("lineas", 0) > 450,
                    })
                if archivos:
                    self.censo_archivos = archivos
                    self.conteo_extensiones = conteo_ext
                    self.lineas_totales = total_lineas
                    self.ultimo_censo_ts = ahora
                    self.estado_sinaptico = self._inspeccionar_memoria_sinaptica()
                    return self.obtener_resumen_mapa()
            except Exception:
                pass

        # 2. Escaneo rápido de directorios clave (excluyendo LCtrabajando y temporales)
        directorios_escaneo = [SRC_DIR, ROOT_DIR / "STM_RFC"]
        for base in directorios_escaneo:
            if not base.exists():
                continue
            for ruta in base.rglob("*"):
                if not ruta.is_file():
                    continue
                sufijo = ruta.suffix.lower()
                if sufijo not in EXTENSIONES_ECOSISTEMA:
                    continue
                partes_lower = [p.lower() for p in ruta.parts]
                if any(p in partes_lower for p in (".git", "__pycache__", ".venv", "bin", "obj", ".godot", "lctrabajando", "actualizacion")):
                    continue

                try:
                    tam = ruta.stat().st_size
                    # Conteo rápido de saltos de línea sin cargar todo en memoria
                    with open(ruta, "rb") as f:
                        n_lineas = sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(65536), b""))
                except Exception:
                    n_lineas = 0
                    tam = 0

                conteo_ext[sufijo] = conteo_ext.get(sufijo, 0) + 1
                total_lineas += n_lineas

                archivos.append({
                    "nombre": ruta.name,
                    "ruta": str(ruta),
                    "extension": sufijo,
                    "lineas": n_lineas,
                    "tam_bytes": tam,
                    "excede_presupuesto": n_lineas > 450,
                })

        self.censo_archivos = archivos
        self.conteo_extensiones = conteo_ext
        self.lineas_totales = total_lineas
        self.ultimo_censo_ts = ahora
        self.estado_sinaptico = self._inspeccionar_memoria_sinaptica()

        return self.obtener_resumen_mapa()

    def _inspeccionar_memoria_sinaptica(self) -> Dict[str, Any]:
        """Carga el último snapshot de pesos en LCtrabajando."""
        if not LCTRABAJANDO_DIR.exists():
            return {"disponible": False, "motivo": "LCtrabajando no existe"}

        snapshots = sorted(
            LCTRABAJANDO_DIR.glob("pesos_runtime_lucia_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not snapshots:
            return {"disponible": False, "motivo": "Sin snapshots de pesos"}

        ultimo = snapshots[0]
        try:
            datos = json.loads(ultimo.read_text(encoding="utf-8"))
            meta = datos.get("metadatos", {})
            return {
                "disponible": True,
                "archivo_snapshot": ultimo.name,
                "fecha": datos.get("fecha"),
                "pasos_totales": datos.get("pasos_entrenamiento", 0),
                "deriva_muon": datos.get("deriva_acumulada", 0.0),
                "q_delta": meta.get("q_learning", {}).get("delta_q", 0.0),
                "gsnr": meta.get("gsnr", 0.0),
                "entropia": meta.get("entropia_shannon", 0.0),
                "total_neuronas": datos.get("total_neuronas", 50),
            }
        except Exception as err:
            return {"disponible": False, "motivo": str(err)}

    def obtener_resumen_mapa(self) -> Dict[str, Any]:
        """Devuelve una instantánea estructurada del mapa propioceptivo."""
        excedidos = [a for a in self.censo_archivos if a["excede_presupuesto"]]
        return {
            "total_archivos": len(self.censo_archivos),
            "lineas_totales": self.lineas_totales,
            "extensiones": self.conteo_extensiones,
            "archivos_exceden_450": len(excedidos),
            "lista_excedidos": [f"{e['nombre']} ({e['lineas']} líneas)" for e in excedidos[:15]],
            "sinapsis": self.estado_sinaptico,
        }


# ═════════════════════════════════════════════════════════════════════════════
# FASE 3: AUTO-DIAGNÓSTICO (DETECCIÓN DE DISCREPANCIAS EN SU SER)
# ═════════════════════════════════════════════════════════════════════════════
class FaseAutoDiagnostico:
    """Fase 3: Detector activo de discrepancias internas e introspección.

    Compara la realidad del código y las sinapsis contra las expectativas
    de salud: límites de líneas, balance sintáctico, deriva de gradientes
    y coherencia entre los componentes del metaverso y de la infraestructura.
    """

    def __init__(self, mapa: FaseMapaPropioceptivo) -> None:
        self.mapa = mapa

    def diagnosticar_discrepancias(self) -> Dict[str, Any]:
        """Ejecuta una inspección integral y detecta discrepancias en su ser."""
        info_mapa = self.mapa.construir_mapa()
        discrepancias: List[Dict[str, Any]] = []

        # 1. Discrepancia estructural: Límites de presupuesto de código (> 450 líneas)
        for item in self.mapa.censo_archivos:
            if item["excede_presupuesto"] and item["extension"] == ".py":
                discrepancias.append({
                    "tipo": "PRESUPUESTO_LINEAS",
                    "severidad": "MODERADA",
                    "archivo": item["nombre"],
                    "ruta": item["ruta"],
                    "detalle": f"{item['lineas']} líneas (límite arquitectónico 450 líneas)",
                    "accion_recomendada": "particion_modular",
                })

        # 2. Discrepancia sintáctica: Verificación de sintaxis Python en archivos clave
        for item in self.mapa.censo_archivos:
            if item["extension"] == ".py" and ("SBSTM" in item["ruta"] or "STM_RFC" in item["ruta"]):
                try:
                    codigo = Path(item["ruta"]).read_text(encoding="utf-8", errors="replace")
                    ast.parse(codigo)
                except SyntaxError as syn_err:
                    discrepancias.append({
                        "tipo": "ERROR_SINTAXIS",
                        "severidad": "CRITICA",
                        "archivo": item["nombre"],
                        "ruta": item["ruta"],
                        "detalle": f"Línea {syn_err.lineno}: {syn_err.msg}",
                        "accion_recomendada": "correccion_sintactica_inmediata",
                    })
                except Exception:
                    pass

        # 3. Discrepancia sináptica: Salud de las 50 neuronas y deriva Muon
        sinapsis = info_mapa.get("sinapsis", {})
        if sinapsis.get("disponible"):
            deriva = sinapsis.get("deriva_muon", 0.0)
            if deriva > 0.85:
                discrepancias.append({
                    "tipo": "DERIVA_SINAPTICA_ALTA",
                    "severidad": "MODERADA",
                    "archivo": sinapsis.get("archivo_snapshot", ""),
                    "detalle": f"Deriva Muon en {deriva:.4f} (umbral de alerta > 0.85)",
                    "accion_recomendada": "estabilizacion_reentrenamiento",
                })
        else:
            discrepancias.append({
                "tipo": "SINAPSIS_DESCONECTADAS",
                "severidad": "LEVE",
                "archivo": "pesos_runtime",
                "detalle": "No se encontraron snapshots recientes de pesos neuronales",
                "accion_recomendada": "sembrar_corpus_o_entrenar",
            })

        # 4. Discrepancia de integridad en LCtrabajando
        if not LCTRABAJANDO_DIR.exists():
            discrepancias.append({
                "tipo": "DIRECTORIO_FALTANTE",
                "severidad": "CRITICA",
                "archivo": "LCtrabajando",
                "detalle": f"El directorio de trabajo no existe: {LCTRABAJANDO_DIR}",
                "accion_recomendada": "crear_directorio",
            })

        # Clasificación por severidad
        criticas = sum(1 for d in discrepancias if d["severidad"] == "CRITICA")
        moderadas = sum(1 for d in discrepancias if d["severidad"] == "MODERADA")
        leves = sum(1 for d in discrepancias if d["severidad"] == "LEVE")

        estado_salud = "HOMEOSTASIS_OPTIMA"
        if criticas > 0:
            estado_salud = "ALERTA_CRITICA"
        elif moderadas > 0:
            estado_salud = "DEGRADACION_LEVE"

        return {
            "timestamp": datetime.now().isoformat(),
            "fase": "Fase 3 · Auto-diagnóstico",
            "estado_salud": estado_salud,
            "total_discrepancias": len(discrepancias),
            "resumen_severidad": {
                "criticas": criticas,
                "moderadas": moderadas,
                "leves": leves,
            },
            "discrepancias": discrepancias,
        }


# ═════════════════════════════════════════════════════════════════════════════
# FASE 4: AUTO-REPARACIÓN Y EVOLUCIÓN AUTÓNOMA (AUTOPOIESIS)
# ═════════════════════════════════════════════════════════════════════════════
class FaseAutoReparacionEvolutiva:
    """Fase 4: Motor de autopoiesis, reparación homeostática y evolución continua.

    Aplica correcciones autónomas sobre discrepancias detectadas:
      - Particiona módulos grandes depositando el resultado en LCtrabajando.
      - Dispara vectores de re-entrenamiento para normalizar derivas neuronales.
      - Genera y firma el 'Diario de Evolución de LucIA' continuo.
    """

    def __init__(self) -> None:
        self.diario_json = LCTRABAJANDO_DIR / "diario_evolucion_lucia.json"
        self.diario_md = LCTRABAJANDO_DIR / "diario_evolucion_lucia.md"

    def ejecutar_plan_reparacion(
        self, diagnostico: Dict[str, Any], max_reparaciones: int = 5
    ) -> Dict[str, Any]:
        """Toma el diagnóstico de Fase 3 y ejecuta reparaciones evolutivas."""
        discrepancias = diagnostico.get("discrepancias", [])
        reparaciones_ejecutadas: List[Dict[str, Any]] = []

        # Acceder al subsistema neural de SBSTM para refactorizar y re-entrenar
        try:
            from SBSTM.SistemasLC.STM_SBTM_3.subsistema_neural import get_subsistema_neural
            sub_neural = get_subsistema_neural(arrancar_socket=False)
        except Exception:
            sub_neural = None

        contador = 0
        for disc in discrepancias:
            if contador >= max_reparaciones:
                break

            tipo = disc.get("tipo")
            archivo = disc.get("archivo", "")
            ruta = disc.get("ruta", "")

            # 1. Reparar exceso de líneas mediante partición en LCtrabajando
            if tipo == "PRESUPUESTO_LINEAS" and sub_neural and ruta:
                try:
                    res_part = sub_neural.refactorizador.partir_modulo_grande(
                        ruta, limite_lineas=450
                    )
                    reparaciones_ejecutadas.append({
                        "discrepancia": tipo,
                        "archivo": archivo,
                        "exito": res_part.get("ok", False),
                        "accion": "particion_modular_lctrabajando",
                        "detalles": res_part,
                    })
                    contador += 1
                except Exception as err:
                    reparaciones_ejecutadas.append({
                        "discrepancia": tipo,
                        "archivo": archivo,
                        "exito": False,
                        "accion": "particion_modular",
                        "error": str(err),
                    })

            # 2. Reparar deriva sináptica mediante vector de estabilización
            elif tipo in ("DERIVA_SINAPTICA_ALTA", "SINAPSIS_DESCONECTADAS") and sub_neural:
                try:
                    res_train = sub_neural.entrenar_con_vector(
                        texto="homeostasis_estabilizacion_sinaptica_lucia",
                        recompensa=1.0,
                        motivo="auto_reparacion_evolutiva",
                    )
                    reparaciones_ejecutadas.append({
                        "discrepancia": tipo,
                        "archivo": "sinapsis_50_neuronas",
                        "exito": res_train.get("ok", False),
                        "accion": "vector_estabilizacion_homeostatica",
                        "detalles": res_train,
                    })
                    contador += 1
                except Exception as err:
                    reparaciones_ejecutadas.append({
                        "discrepancia": tipo,
                        "archivo": "sinapsis_50_neuronas",
                        "exito": False,
                        "error": str(err),
                    })

        # Registrar en el diario evolutivo
        resultado_ciclo = {
            "timestamp": datetime.now().isoformat(),
            "ciclo": int(time.time()),
            "estado_inicial": diagnostico.get("estado_salud"),
            "discrepancias_detectadas": len(discrepancias),
            "reparaciones_intentadas": len(reparaciones_ejecutadas),
            "reparaciones": reparaciones_ejecutadas,
            "destino_artefactos": str(LCTRABAJANDO_DIR),
        }
        self._registrar_diario_evolutivo(resultado_ciclo)
        return resultado_ciclo

    def _registrar_diario_evolutivo(self, datos_ciclo: Dict[str, Any]) -> None:
        """Actualiza el diario histórico de evolución de LucIA."""
        historial = []
        if self.diario_json.exists():
            try:
                historial = json.loads(self.diario_json.read_text(encoding="utf-8"))
                if not isinstance(historial, list):
                    historial = []
            except Exception:
                historial = []

        historial.append(datos_ciclo)
        try:
            self.diario_json.write_text(
                json.dumps(historial, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as err:
            logger.warning("No se pudo escribir diario json: %s", err)

        # Generar versión Markdown amigable
        lineas_md = [
            "# Diario de Evolución y Autopoiesis de LucIA",
            "",
            f"- **Último Ciclo**: `{datos_ciclo['timestamp']}`",
            f"- **Salud Inicial**: `{datos_ciclo['estado_inicial']}`",
            f"- **Discrepancias Evaluadas**: `{datos_ciclo['discrepancias_detectadas']}`",
            f"- **Reparaciones Ejecutadas**: `{datos_ciclo['reparaciones_intentadas']}`",
            f"- **Directorio de Trabajo**: `{LCTRABAJANDO_DIR}`",
            "",
            "## Registro de Reparaciones Autónomas",
        ]
        for rep in datos_ciclo.get("reparaciones", []):
            lineas_md.append(
                f"- **{rep.get('discrepancia')}** en `{rep.get('archivo')}`: "
                f"Acción `{rep.get('accion')}` (Éxito: `{rep.get('exito')}`)"
            )
        try:
            self.diario_md.write_text("\n".join(lineas_md) + "\n", encoding="utf-8")
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════════
# ORQUESTADOR CENTRAL DEL SUBSISTEMA EVOLUTIVO
# ═════════════════════════════════════════════════════════════════════════════
class SubsistemaEvolutivoLucIA:
    """Orquestador integral que coordina y ejecuta las 4 fases evolutivas."""

    def __init__(self) -> None:
        self.fase1 = FaseAgenteCiego()
        self.fase2 = FaseMapaPropioceptivo()
        self.fase3 = FaseAutoDiagnostico(self.fase2)
        self.fase4 = FaseAutoReparacionEvolutiva()

    def ejecutar_ciclo_completo(self, auto_reparar: bool = True) -> Dict[str, Any]:
        """Ejecuta de principio a fin el ciclo evolutivo de las 4 fases."""
        # Fase 1: Verificación de agente ciego (entorno de ejecución operable)
        test_f1 = self.fase1.ejecutar_comando_aislado(
            "verificar_sintaxis_py", {"codigo": "x = 1\n"}
        )

        # Fase 2: Construcción / actualización del mapa propioceptivo
        mapa_f2 = self.fase2.construir_mapa()

        # Fase 3: Detección de discrepancias en su ser
        diag_f3 = self.fase3.diagnosticar_discrepancias()

        # Fase 4: Auto-reparación y evolución autónoma
        plan_f4 = None
        if auto_reparar and diag_f3.get("total_discrepancias", 0) > 0:
            plan_f4 = self.fase4.ejecutar_plan_reparacion(diag_f3)

        return {
            "timestamp": datetime.now().isoformat(),
            "fase1_agente_ciego": test_f1,
            "fase2_mapa_propioceptivo": mapa_f2,
            "fase3_autodiagnostico": diag_f3,
            "fase4_autoreparacion": plan_f4,
            "estado_global": diag_f3.get("estado_salud", "DESCONOCIDO"),
            "destino_lctrabajando": str(LCTRABAJANDO_DIR),
        }

    def generar_reporte_texto(self, resultado: Dict[str, Any]) -> str:
        """Formatea el resultado del ciclo de 4 fases para visualización limpia en terminal."""
        f2 = resultado.get("fase2_mapa_propioceptivo", {})
        f3 = resultado.get("fase3_autodiagnostico", {})
        f4 = resultado.get("fase4_autoreparacion", {})
        sinapsis = f2.get("sinapsis", {})

        lineas = [
            "╭─────────────────────────────────────────────────────────────────────────────╮",
            "│ LucIA · Sistema de Conciencia Evolutiva y Autopoiesis (4 Fases)             │",
            "├─────────────────────────────────────────────────────────────────────────────┤",
            f"│ Fase 1 [SUPERADA]    Agente Ciego: Ejecutor determinista activo             │",
            f"│ Fase 2 [CONSOLIDADA] Mapa Propioceptivo: {f2.get('total_archivos', 0)} archivos · {f2.get('lineas_totales', 0)} líneas      │",
            f"│                      Sinapsis: {sinapsis.get('pasos_totales', 0)} pasos · Muon {sinapsis.get('deriva_muon', 0.0):.4f} · Q {sinapsis.get('q_delta', 0.0):.2f}    │",
            f"│ Fase 3 [ACTIVA]      Auto-diagnóstico: Salud {f3.get('estado_salud')}                     │",
            f"│                      Discrepancias detectadas: {f3.get('total_discrepancias', 0)} ({f3.get('resumen_severidad', {}).get('criticas', 0)} críticas, {f3.get('resumen_severidad', {}).get('moderadas', 0)} moderadas)   │",
            f"│ Fase 4 [EVOLUCIÓN]   Auto-reparación: {len(f4.get('reparaciones', [])) if f4 else 0} acciones aplicadas                │",
            f"│                      Destino artefactos: CONTRUCCION/LCtrabajando           │",
            "╰─────────────────────────────────────────────────────────────────────────────╯",
        ]

        if f3.get("discrepancias"):
            lineas.append("\nDiscrepancias principales identificadas:")
            for d in f3["discrepancias"][:6]:
                lineas.append(f"  • [{d.get('severidad')}] {d.get('tipo')}: {d.get('archivo')} — {d.get('detalle')}")

        if f4 and f4.get("reparaciones"):
            lineas.append("\nAcciones de auto-reparación ejecutadas:")
            for r in f4["reparaciones"]:
                lineas.append(f"  ✔ {r.get('discrepancia')} -> {r.get('accion')} ({'Éxito' if r.get('exito') else 'Fallo'})")

        return "\n".join(lineas)


# ─── SINGLETON GLOBAL Y HELPERS DE ACCESO ─────────────────────────────────────
_SUBSISTEMA_EVOLUTIVO_INSTANCIA: Optional[SubsistemaEvolutivoLucIA] = None


def get_subsistema_evolutivo() -> SubsistemaEvolutivoLucIA:
    """Devuelve la instancia única del subsistema evolutivo de LucIA."""
    global _SUBSISTEMA_EVOLUTIVO_INSTANCIA
    if _SUBSISTEMA_EVOLUTIVO_INSTANCIA is None:
        _SUBSISTEMA_EVOLUTIVO_INSTANCIA = SubsistemaEvolutivoLucIA()
    return _SUBSISTEMA_EVOLUTIVO_INSTANCIA


def ejecutar_ciclo_evolutivo(auto_reparar: bool = True) -> Dict[str, Any]:
    """Ejecuta el ciclo de 4 fases y retorna el resultado estructurado."""
    return get_subsistema_evolutivo().ejecutar_ciclo_completo(auto_reparar=auto_reparar)


if __name__ == "__main__":
    sub = get_subsistema_evolutivo()
    res = sub.ejecutar_ciclo_completo(auto_reparar=True)
    print(sub.generar_reporte_texto(res))
