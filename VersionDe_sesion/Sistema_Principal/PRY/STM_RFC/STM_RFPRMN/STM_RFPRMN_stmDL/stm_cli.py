"""
stm_cli.py - Ejecutor CLI y Despachador de Comandos de STM_RFPRMN
================================================================
Núcleo modularizado para la interfaz de línea de comandos de RFPRMN.

Convierte la lógica CLI de main() en una clase estructurada (`EjecutorCLI`)
e incorpora el comando especializado `comando_lc_entrenar` para convertir
cualquier archivo de código o .md en vectores de entrenamiento en runtime
para la red neuronal principal de LucIA.
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional

from .stm_base import (
    _caja,
    _imprimir_seguro,
    exito,
    informar,
    reportar_error,
)
from .stm_corpus import sembrar_corpus
from .stm_creacion import comando_crear_codigo
from .stm_flujo import ejecutar_comandos
from .stm_gestion import (
    actualizar,
    comando_crear_archivo,
    comando_crear_carpeta,
    comando_enviar,
    comando_refactorizar,
)
from .stm_lucia import describir as describir_lucia
from .stm_rutas import comando_configurar_rutas, comando_rutas
from .stm_seq2seq import describir as describir_seq2seq

# ─── RESOLUCION DEL SUBSISTEMA NEURAL DE LUCIA ──────────────────────────────
from .stm_rutas import SRC_DIR, CONTRRF_DIR, TLLDCD_DIR, MODULO_DIR
LCTRABAJANDO_DIR: Final[Path] = CONTRRF_DIR / "CONTRUCCION" / "LCtrabajando"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))




def comando_lc_entrenar(ruta_o_texto: str = "") -> Dict[str, Any]:
    """Comando 'LC entrenar': vectoriza y entrena la red neuronal con un archivo o texto.

    Acepta cualquier archivo de código (.py, .gd, .cs, .tscn, .tres, etc.) o .md
    que adjunte LucIA, lo divide en fragmentos semánticos, genera tensores de 50 dimensiones
    y actualiza los pesos de las 50 neuronas en tiempo de ejecución.
    
    Todo artefacto resultante se escribe estrictamente en CONTRUCCION/LCtrabajando.
    """
    ruta_candidata = (ruta_o_texto or "").strip().strip("\"'")
    archivo_objetivo: Optional[Path] = None

    if ruta_candidata:
        p = Path(ruta_candidata)
        if p.is_file():
            archivo_objetivo = p
        else:
            # Buscar en LCtrabajando o en el árbol de fuentes
            for base in (LCTRABAJANDO_DIR, SRC_DIR, MODULO_DIR):
                cand = base / ruta_candidata
                if cand.is_file():
                    archivo_objetivo = cand
                    break

    if archivo_objetivo is None:
        # Si no se pasó ruta o no existe, buscar el último archivo generado en LCtrabajando
        if LCTRABAJANDO_DIR.exists():
            candidatos = [
                f for f in LCTRABAJANDO_DIR.glob("*")
                if f.is_file() and f.suffix.lower() in (
                    ".py", ".gd", ".cs", ".md", ".json", ".tscn", ".tres"
                ) and "pesos_runtime" not in f.name and "manifiesto" not in f.name
            ]
            if candidatos:
                candidatos.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                archivo_objetivo = candidatos[0]

    if archivo_objetivo is None:
        reportar_error("LC entrenar: no se encontró archivo de código o .md válido para entrenar.")
        return {"ok": False, "motivo": "Archivo no encontrado"}

    try:
        contenido = archivo_objetivo.read_text(encoding="utf-8", errors="replace")
    except Exception as err:
        reportar_error(f"Error al leer '{archivo_objetivo}': {err}")
        return {"ok": False, "motivo": str(err)}

    lineas = contenido.splitlines()
    total_lineas = len(lineas)
    informar(f"[LC entrenar] Procesando '{archivo_objetivo.name}' ({total_lineas} líneas)...")

    # Importar el subsistema neural
    try:
        from SBSTM.subsistema_neural import get_subsistema_neural
        sub = get_subsistema_neural(arrancar_socket=False)
    except Exception as err:
        reportar_error(f"No se pudo acceder al subsistema neural de SBSTM: {err}")
        reportar_error(f"SRC_DIR: {SRC_DIR}")
        reportar_error(f"sys.path: {sys.path}")
        return {"ok": False, "motivo": str(err)}

    # Fragmentar en bloques de entrenamiento
    bloques = []
    bloque_actual = []
    for l in lineas:
        bloque_actual.append(l)
        if len(bloque_actual) >= 25 or (l.strip().startswith(("def ", "func ", "class ", "##", "###")) and len(bloque_actual) >= 10):
            bloques.append("\n".join(bloque_actual))
            bloque_actual = []
    if bloque_actual:
        bloques.append("\n".join(bloque_actual))

    if not bloques:
        bloques = [contenido]

    resultados_pasos = []
    for idx, bloque in enumerate(bloques, start=1):
        res_paso = sub.entrenar_con_vector(
            texto=bloque,
            recompensa=1.2,
            motivo=f"LC_entrenar_{archivo_objetivo.stem}_b{idx}",
        )
        resultados_pasos.append(res_paso)

    ultimo = resultados_pasos[-1] if resultados_pasos else {}
    archivos_pesos = ultimo.get("archivos_pesos", {})

    # Registrar en manifiesto de LCtrabajando
    doc_resumen = [
        f"# Sesión de Entrenamiento Neuronal: {archivo_objetivo.name}",
        "",
        f"- **Fecha**: `{datetime.now().isoformat()}`",
        f"- **Archivo Origen**: `{archivo_objetivo}`",
        f"- **Líneas Procesadas**: `{total_lineas}`",
        f"- **Vectores de Entrenamiento**: `{len(bloques)}` fragmentos proyectados",
        f"- **Deriva Muon Acumulada**: `{ultimo.get('deriva_acumulada', 0.0)}`",
        f"- **Norma Tensor Final**: `{ultimo.get('norma_tensor', 0.0)}`",
        f"- **GSNR**: `{ultimo.get('gsnr', 0.0)}`",
        f"- **Entropía Shannon**: `{ultimo.get('entropia_shannon', 0.0)}`",
        "",
        "## Archivos de Pesos Generados en Runtime",
        f"- NPZ: `{archivos_pesos.get('npz_trabajando')}`",
        f"- JSON: `{archivos_pesos.get('json_trabajando')}`",
    ]
    reporte_md = LCTRABAJANDO_DIR / f"reporte_entrenamiento_{archivo_objetivo.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    reporte_md.write_text("\n".join(doc_resumen), encoding="utf-8")

    filas = [
        ("Archivo adjuntado", f"{archivo_objetivo.name} ({total_lineas} líneas)"),
        ("Vectores enviados", f"{len(bloques)} tensores de 50 dimensiones"),
        ("Deriva Muon", f"{ultimo.get('deriva_acumulada', 0.0):.6f}"),
        ("Q-Learning Delta", f"{ultimo.get('q_learning', {}).get('delta_q', 'OK')}"),
        ("Snapshot Pesos", f"{Path(archivos_pesos.get('json_trabajando', '')).name}"),
        ("Destino", "CONTRUCCION/LCtrabajando"),
    ]
    _imprimir_seguro(_caja("LC Entrenar · Red Neuronal Actualizada", filas, color="verde"))
    exito(f"Pesos actualizados en caliente. Reporte: {reporte_md.name}")

    return {
        "ok": True,
        "archivo": str(archivo_objetivo),
        "fragmentos": len(bloques),
        "metricas": ultimo,
        "reporte": str(reporte_md),
        "archivos_pesos": archivos_pesos,
    }


class EjecutorCLI:
    """Ejecutor de la CLI no interactiva e interactiva de STM_RFPRMN.

    Convierte el flujo principal en una máquina de ejecución modular y limpia,
    proporcionando soporte a flags de consola y a comandos del sistema.
    """

    def __init__(self, argv: Optional[List[str]] = None) -> None:
        self.argv = argv

    def ejecutar(self, argv: Optional[List[str]] = None) -> int:
        """Punto de entrada de ejecución CLI."""
        args = list(sys.argv[1:] if argv is None and self.argv is None else (argv if argv is not None else self.argv))

        if "--consumir-modelos" in args:
            os.environ["RFPRMN_CONSUMIR_MODELOS"] = "1"
            args = [a for a in args if a != "--consumir-modelos"]

        if "--openrouter" in args:
            os.environ["RFPRMN_OPENROUTER"] = "1"
            args = [a for a in args if a != "--openrouter"]

        if not args:
            ejecutar_comandos()
            return 0

        cmd = args[0].strip().lower()

        if cmd in ("--ayuda", "-h", "ayuda"):
            self.imprimir_ayuda()
            return 0

        if cmd in ("--version", "-v"):
            return self._mostrar_version()

        if cmd == "--estado":
            return self._mostrar_estado()

        if cmd == "--presupuesto":
            return self._verificar_presupuesto()

        if cmd in ("--rutas", "rutas"):
            comando_rutas()
            return 0

        if cmd in ("--configurar-rutas", "configurar rutas"):
            comando_configurar_rutas()
            return 0

        if cmd in ("--lucia", "lucia"):
            _imprimir_seguro(describir_lucia())
            _imprimir_seguro(describir_seq2seq())
            return 0

        if cmd in ("--seq2seq", "seq2seq"):
            _imprimir_seguro(describir_seq2seq())
            return 0

        if cmd in ("--sembrar-lucia", "sembrar lucia"):
            return self._sembrar(args)

        if cmd in ("--lc-entrenar", "lc entrenar", "lc_entrenar"):
            ruta = " ".join(args[1:]).strip() if len(args) > 1 else ""
            res = comando_lc_entrenar(ruta)
            return 0 if res.get("ok") else 1

        if cmd in ("--lc-adjuntar", "lc adjuntar", "lc_adjuntar"):
            from .stm_adjuntar import comando_lc_entrenar_adjuntar
            comando_lc_entrenar_adjuntar()
            return 0

        if cmd in ("--lc-evolucion", "lc evolucion", "lc_evolucion"):
            try:
                from SBSTM.subsistema_evolutivo import get_subsistema_evolutivo
                sub_evo = get_subsistema_evolutivo()
                res = sub_evo.ejecutar_ciclo_completo(auto_reparar=False)
                print()
                print(sub_evo.generar_reporte_texto(res))
                print()
                return 0
            except Exception as err:
                reportar_error(f"Error en ciclo evolutivo: {err}")
                reportar_error(f"SRC_DIR: {SRC_DIR}")
                return 1

        if cmd in ("--copiar-codigo", "copiar codigo", "copiar código"):
            from .stm_creacion import comando_copiar_codigo
            orig = args[1] if len(args) > 1 else ""
            dest = args[2] if len(args) > 2 else ""
            return 0 if comando_copiar_codigo(orig, dest) else 1

        if cmd == "--comando" and len(args) > 1:
            return self._despachar_comando(args[1:])

        reportar_error(f"Argumento no reconocido: {args[0]} (prueba --ayuda)")
        return 2

    def _mostrar_version(self) -> int:
        from . import modulos_estado, __version__
        mods = list(modulos_estado())
        print(f"RFPRMN v{__version__} · {len(mods)} submódulos activos")
        return 0

    def _mostrar_estado(self) -> int:
        from . import modulos_estado
        estado = modulos_estado()
        filas = [(m, f"{v['import']} · {v['lineas']} líneas") for m, v in estado.items()]
        _imprimir_seguro(_caja("Estado de submódulos", filas, color="azul"))
        return 0

    def _verificar_presupuesto(self, max_lineas: int = 450) -> int:
        from . import verificar_presupuesto
        res = verificar_presupuesto(max_lineas)
        if res.get("ok"):
            exito(f"Presupuesto OK: ningún módulo supera {max_lineas} líneas.")
            return 0
        for modulo, n in res.get("excedidos", {}).items():
            reportar_error(f"{modulo}: {n} líneas (tope {max_lineas}).")
        return 1

    def _sembrar(self, args: List[str]) -> int:
        from .stm_rutas import MODULO_DIR
        limite = int(args[1]) if len(args) > 1 and args[1].isdigit() else 12
        resultado = sembrar_corpus(MODULO_DIR / "STM_RFPRMN_stmDL", limite)
        if not resultado.get("disponible") or resultado.get("muestras") == 0:
            reportar_error(f"No se pudo sembrar: {resultado.get('motivo')}")
            return 1
        exito(f"Semilla: {resultado['muestras']} muestras de {resultado['archivos']} "
              f"archivos ({resultado['pasos']} pasadas).")
        return 0

    def _despachar_comando(self, argumentos_comando: List[str]) -> int:
        nombre = " ".join(argumentos_comando).strip().lower()

        # Atajo especial para 'lc entrenar'
        if nombre.startswith("lc entrenar") or nombre.startswith("lc_entrenar"):
            resto = nombre.replace("lc_entrenar", "").replace("lc entrenar", "").strip()
            res = comando_lc_entrenar(resto)
            return 0 if res.get("ok") else 1

        # Atajo especial para 'lc adjuntar'
        if nombre.startswith("lc adjuntar") or nombre.startswith("lc_adjuntar"):
            from .stm_adjuntar import comando_lc_entrenar_adjuntar
            comando_lc_entrenar_adjuntar()
            return 0

        # Atajo especial para 'lc evolucion'
        if nombre.startswith("lc evolucion") or nombre.startswith("lc_evolucion"):
            try:
                from SBSTM.subsistema_evolutivo import get_subsistema_evolutivo
                sub_evo = get_subsistema_evolutivo()
                res = sub_evo.ejecutar_ciclo_completo(auto_reparar=False)
                print()
                print(sub_evo.generar_reporte_texto(res))
                print()
                return 0
            except Exception as err:
                reportar_error(f"Error en ciclo evolutivo: {err}")
                reportar_error(f"SRC_DIR: {SRC_DIR}")
                return 1

        tabla: Dict[str, Callable[[], Any]] = {
            "refactorizar": comando_refactorizar,
            "actualizar": actualizar,
            "enviar": comando_enviar,
            "crear carpeta": comando_crear_carpeta,
            "crear archivo": comando_crear_archivo,
            "crear codigo": comando_crear_codigo,
            "copiar codigo": lambda: __import__(
                "STM_RFPRMN_stmDL.stm_creacion", fromlist=["comando_copiar_codigo"]
            ).comando_copiar_codigo(),
            "copiar código": lambda: __import__(
                "STM_RFPRMN_stmDL.stm_creacion", fromlist=["comando_copiar_codigo"]
            ).comando_copiar_codigo(),
            "rutas": comando_rutas,
            "configurar rutas": comando_configurar_rutas,
            "lc entrenar": comando_lc_entrenar,
            "lc adjuntar": lambda: __import__(
                "STM_RFPRMN_stmDL.stm_adjuntar", fromlist=["comando_lc_entrenar_adjuntar"]
            ).comando_lc_entrenar_adjuntar(),
            "lc evolucion": lambda: __import__(
                "SBSTM.subsistema_evolutivo", fromlist=["get_subsistema_evolutivo"]
            ).get_subsistema_evolutivo().ejecutar_ciclo_completo(auto_reparar=False),
        }

        accion = tabla.get(nombre)
        if accion is None:
            # Reintentar mediante coincidencia de prefijo
            for clave, fn in tabla.items():
                if nombre.startswith(clave):
                    accion = fn
                    break

        if accion is None:
            reportar_error(f"Comando no reconocido: '{nombre}' (prueba --ayuda)")
            return 2

        try:
            accion()
        except (KeyboardInterrupt, EOFError):
            informar("Entrada interrumpida (sin más datos); no se modificó nada.")
            return 1
        return 0

    def imprimir_ayuda(self) -> None:
        """Muestra el panel de ayuda CLI."""
        from . import __version__
        filas = [
            ("--ayuda / -h", "Muestra esta ayuda."),
            ("--version / -v", "Muestra la versión de RFPRMN."),
            ("--estado", "Estado de submódulos y conteo de líneas."),
            ("--presupuesto", "Verifica que ningún módulo supere 450 líneas."),
            ("--rutas", "Muestra las rutas activas de RFC y PRY."),
            ("--configurar-rutas", "Configuración interactiva de rutas."),
            ("--lucia", "Muestra estado de la red neuronal LucIA."),
            ("--seq2seq", "Estado de la memoria seq2seq."),
            ("--sembrar-lucia [N]", "Siembra el corpus de entrenamiento."),
            ("--lc-entrenar [RUTA]", "Entrena la red neuronal con archivo de código o .md."),
            ("--lc-adjuntar", "Selector interactivo de archivo/carpeta para entrenar."),
            ("--lc-evolucion", "Ciclo 4 fases: propiocepción y autodiagnóstico."),
            ("--comando NOMBRE", "Ejecuta un comando por nombre directo."),
        ]
        _imprimir_seguro(_caja(f"RFPRMN CLI · Ayuda v{__version__}", filas, color="verde"))


def main(argv: Optional[List[str]] = None) -> int:
    """Función de compatibilidad CLI estándar."""
    return EjecutorCLI().ejecutar(argv)
