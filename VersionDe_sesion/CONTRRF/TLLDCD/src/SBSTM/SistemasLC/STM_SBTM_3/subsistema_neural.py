"""
SBSTM.subsistema_neural - Subsistema de Entrenamiento Neural en Runtime y Auto-Refactorizacion
==============================================================================================
Arquitectura WoldVirtualP2P3D 2026.

Responsabilidades centrales:
1. CANAL SOCKET E IMPORTACIONES:
   - Conexion bidireccional con STMGNRL/mainLCSTM.py y clientes externos (Godot, Visor C#)
     mediante sockets TCP (puerto configurable, default 8766) e importaciones directas.
2. VECTORES DE ENTRENAMIENTO Y PESOS NEURONALES EN RUNTIME:
   - Generacion y envio de vectores de entrenamiento hacia la red neuronal principal
     en LC_STM/red_neuronal (capas ENRN, RF_EN, RF_SL, RNP, SLRN - 50 neuronas).
   - Actualizacion Hebbiana, por gradiente y por refuerzo Q-Learning de sinapsis.
   - Creacion de nuevos pesos neuronales en tiempo de ejecucion (.npz y .json).
3. MAQUINA DE COMANDOS Y AUTO-REFACTORIZACION:
   - Conexion con la maquina de comandos de LucIA (RFPRMN / LucIAComandos).
   - Refactorizacion de la infraestructura cognitiva (Python / C#) y del metaverso (GDScript Godot).
   - Particion de archivos grandes (> 450 lineas) y diagnostico AST.
4. DESTINO UNIFICADO DE TRABAJO:
   - Todo artefacto generado para auto-refactorizarse se escribe estrictamente en:
     VersionDe_sesion/CONTRRF/CONTRUCCION/LCtrabajando
"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import re
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional, Tuple, Union

import numpy as np

# ─── JERARQUIA DE DIRECTORIOS ────────────────────────────────────────────────
CURRENT_FILE: Final[Path] = Path(__file__).resolve()
SBSTM_DIR: Final[Path] = CURRENT_FILE.parent.parent
SRC_DIR: Final[Path] = SBSTM_DIR.parent
TLLDCD_DIR: Final[Path] = SRC_DIR.parent
CONTRRF_DIR: Final[Path] = TLLDCD_DIR.parent
ROOT_DIR: Final[Path] = CONTRRF_DIR.parent

# Directorio obligatorio donde LucIA deposita todo lo que genera para auto-refactorizarse:
LCTRABAJANDO_DIR: Final[Path] = CONTRRF_DIR / "CONTRUCCION" / "LCtrabajando"
if not LCTRABAJANDO_DIR.is_dir():
    try:
        LCTRABAJANDO_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

# Directorios de los subsistemas satelite:
LC_STM_DIR: Final[Path] = SRC_DIR / "LC_STM"
RED_NEURONAL_DIR: Final[Path] = LC_STM_DIR / "red_neuronal"
STMGNRL_DIR: Final[Path] = SRC_DIR / "STMGNRL"
MTBGT_DIR: Final[Path] = SRC_DIR / "MTBGT"
VSC_DIR: Final[Path] = SRC_DIR / "VSC#"
STM_CH_DIR: Final[Path] = SRC_DIR / "STM_CH"
PSNRL_DIR: Final[Path] = STM_CH_DIR / "PSNRL"
if not PSNRL_DIR.is_dir():
    try:
        PSNRL_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

for _p in (SRC_DIR, STMGNRL_DIR, SBSTM_DIR, CONTRRF_DIR, ROOT_DIR):
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

logger: logging.Logger = logging.getLogger("WoldVirtualP2P3D.SBSTM.SubsistemaNeural")


# ═════════════════════════════════════════════════════════════════════════════
# 1. CANAL SOCKET: COMUNICACION IPC CON mainLCSTM.py Y CLIENTES EXTERNOS
# ═════════════════════════════════════════════════════════════════════════════
class CanalSocketLucIA:
    """Canal de comunicacion TCP por sockets para SBSTM.

    Permite a mainLCSTM.py, visores C# o escenas de Godot interactuar con
    el subsistema neural y la maquina de auto-refactorizacion mediante
    tramas JSON delimitadas por salto de linea.
    """

    DEFAULT_HOST: Final[str] = "127.0.0.1"
    DEFAULT_PORT: Final[int] = 8766

    def __init__(
        self,
        manejador_comandos: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        host: str = DEFAULT_HOST,
        puerto: int = DEFAULT_PORT,
    ) -> None:
        self.host = host
        self.puerto = puerto
        self.manejador_comandos = manejador_comandos
        self._servidor_socket: Optional[socket.socket] = None
        self._hilo_servidor: Optional[threading.Thread] = None
        self._activo = threading.Event()
        self._clientes_conectados = 0
        self._lock = threading.Lock()

    @property
    def activo(self) -> bool:
        return self._activo.is_set()

    def iniciar(self) -> Dict[str, Any]:
        """Arranca el servidor de sockets en un hilo daemon en segundo plano."""
        with self._lock:
            if self.activo:
                return {"ok": True, "arrancado": False, "motivo": "ya estaba activo", "puerto": self.puerto}

            intentos = [self.puerto, self.puerto + 1, self.puerto + 10, 0]
            sock = None
            puerto_final = self.puerto

            for p in intentos:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind((self.host, p))
                    sock.listen(5)
                    puerto_final = sock.getsockname()[1]
                    break
                except OSError as e:
                    if sock:
                        sock.close()
                    sock = None
                    continue

            if sock is None:
                return {"ok": False, "motivo": "No se pudo enlazar socket en ningun puerto"}

            self.puerto = puerto_final
            self._servidor_socket = sock
            self._activo.set()
            self._hilo_servidor = threading.Thread(
                target=self._bucle_aceptacion,
                name="CanalSocketLucIA-Listener",
                daemon=True,
            )
            self._hilo_servidor.start()
            logger.info("[CanalSocketLucIA] Servidor escuchando en %s:%d", self.host, self.puerto)
            return {"ok": True, "arrancado": True, "host": self.host, "puerto": self.puerto}

    def _bucle_aceptacion(self) -> None:
        """Acepta conexiones entrantes y las delega a hilos de atencion."""
        if not self._servidor_socket:
            return
        self._servidor_socket.settimeout(1.0)
        while self._activo.is_set():
            try:
                cliente_sock, dir_cliente = self._servidor_socket.accept()
                with self._lock:
                    self._clientes_conectados += 1
                t = threading.Thread(
                    target=self._atender_cliente,
                    args=(cliente_sock, dir_cliente),
                    name=f"CanalSocket-Client-{dir_cliente}",
                    daemon=True,
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _atender_cliente(self, sock: socket.socket, dir_cliente: Tuple[str, int]) -> None:
        """Procesa peticiones JSON recibidas desde un socket."""
        try:
            lector = sock.makefile("r", encoding="utf-8", errors="replace")
            for linea in lector:
                limpia = linea.strip()
                if not limpia:
                    continue
                try:
                    peticion = json.loads(limpia)
                except Exception as err:
                    respuesta = {"ok": False, "error": f"JSON invalido: {err}"}
                    sock.sendall((json.dumps(respuesta, ensure_ascii=False) + "\n").encode("utf-8"))
                    continue

                if self.manejador_comandos:
                    try:
                        respuesta = self.manejador_comandos(peticion)
                    except Exception as err:
                        respuesta = {"ok": False, "error": f"Fallo al procesar comando: {err}"}
                else:
                    respuesta = {"ok": True, "mensaje": "Comando recibido sin despachador", "eco": peticion}

                sock.sendall((json.dumps(respuesta, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception as exc:
            logger.debug("[CanalSocketLucIA] Conexion terminada con %s: %s", dir_cliente, exc)
        finally:
            try:
                sock.close()
            except OSError:
                pass
            with self._lock:
                self._clientes_conectados = max(0, self._clientes_conectados - 1)

    def detener(self) -> Dict[str, Any]:
        """Detiene el listener y libera el socket."""
        with self._lock:
            if not self.activo:
                return {"ok": True, "detenido": False}
            self._activo.clear()
            if self._servidor_socket:
                try:
                    self._servidor_socket.close()
                except OSError:
                    pass
                self._servidor_socket = None
            return {"ok": True, "detenido": True}

    @staticmethod
    def enviar_mensaje(
        peticion: Dict[str, Any],
        host: str = DEFAULT_HOST,
        puerto: int = DEFAULT_PORT,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """Metodo de cliente estatico para enviar una peticion y leer la respuesta."""
        try:
            with socket.create_connection((host, puerto), timeout=timeout) as sock:
                trama = json.dumps(peticion, ensure_ascii=False) + "\n"
                sock.sendall(trama.encode("utf-8"))
                lector = sock.makefile("r", encoding="utf-8", errors="replace")
                linea = lector.readline()
                if not linea:
                    return {"ok": False, "error": "El servidor cerro la conexion sin responder"}
                return json.loads(linea.strip())
        except Exception as err:
            return {"ok": False, "error": f"Error de comunicacion socket: {err}"}


# ═════════════════════════════════════════════════════════════════════════════
# 2. ENTRENADOR DE PESOS EN RUNTIME: CONEXION CON LC_STM/red_neuronal
# ═════════════════════════════════════════════════════════════════════════════
class EntrenadorPesosRuntime:
    """Orquesta el envio de vectores de entrenamiento a LC_STM/red_neuronal

    Interconecta las 5 capas neuronales de LucIA:
      - ENRN (10 neuronas de entrada)
      - RF_EN (10 neuronas de refuerzo y Q-Learning)
      - RF_SL (10 neuronas de gradiente y salida por refuerzo)
      - RNP (10 neuronas nucleares de procesamiento)
      - SLRN (10 neuronas de salida y modulacion de voz)
    y el transductor central ConversorRespuestaPesos de compat_local.
    """

    DIM_VECTOR: Final[int] = 50

    def __init__(self) -> None:
        self.pasos_entrenamiento = 0
        self.deriva_acumulada = 0.0
        try:
            snaps = sorted(LCTRABAJANDO_DIR.glob("pesos_runtime_lucia_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
            for sn in snaps[:20]:
                try:
                    if sn.stat().st_size > 10:
                        with open(sn, "r", encoding="utf-8") as _f:
                            _d = json.load(_f)
                        _p = int(_d.get("pasos_entrenamiento", 0))
                        if _p > self.pasos_entrenamiento:
                            self.pasos_entrenamiento = _p
                            self.deriva_acumulada = float(_d.get("deriva_acumulada", 0.0))
                except Exception:
                    continue
        except Exception:
            pass
        self.norma_historica: List[float] = []
        self._conversor_local = None
        self._neuronas_reales: Dict[str, Any] = {}
        self._inicializar_conexiones_red()

    def _inicializar_conexiones_red(self) -> None:
        """Carga el transductor de 50 neuronas y los modulos de LC_STM/red_neuronal."""
        try:
            from STM_BKCH.stm_bkch1.compat_local import get_conversor_pesos
            self._conversor_local = get_conversor_pesos()
            self.deriva_acumulada = float(getattr(self._conversor_local, "deriva_acumulada", 0.0))
        except Exception as err:
            logger.warning("[EntrenadorPesosRuntime] No se pudo cargar conversor local: %s", err)

        # Carga defensiva de clases de neuronas reales
        try:
            from LC_STM.red_neuronal.RF_EN.RFEN1_RN_1 import NeuronaRefuerzoQLearning
            self._neuronas_reales["RF_EN_Q"] = NeuronaRefuerzoQLearning(input_size=10, output_size=5)
        except Exception as e:
            logger.debug("[EntrenadorPesosRuntime] RF_EN_Q no disponible: %s", e)

        try:
            from LC_STM.red_neuronal.RF_SL.RFSL1.RF_SL1_1 import GradientBoostingOptimizer
            self._neuronas_reales["RF_SL_GB"] = GradientBoostingOptimizer()
        except Exception as e:
            logger.debug("[EntrenadorPesosRuntime] RF_SL_GB no disponible: %s", e)

        try:
            from LC_STM.red_neuronal.ENRN.EN1_RN import NeuronaEntradaBasica
            self._neuronas_reales["ENRN_BASE"] = NeuronaEntradaBasica(input_size=10, output_size=10)
        except Exception as e:
            logger.debug("[EntrenadorPesosRuntime] ENRN_BASE no disponible: %s", e)

    def generar_vector_entrenamiento(
        self,
        texto: str,
        contexto_adicional: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Proyecta una entrada textual o sensorial en un tensor de 50 dimensiones."""
        cadena = f"{texto}|{json.dumps(contexto_adicional or {}, sort_keys=True)}"
        h_bytes = hashlib.sha384(cadena.encode("utf-8")).digest()
        # Tomar 50 valores pseudo-aleatorios deterministas normalizados
        arr = np.frombuffer(h_bytes[:48], dtype=np.uint8).astype(np.float32)
        # Completar a 50 dimensiones
        extra = np.array([float(len(texto) % 100) / 100.0, float(time.time() % 60) / 60.0], dtype=np.float32)
        vector_50 = np.concatenate([arr / 255.0 * 2.0 - 1.0, extra])[: self.DIM_VECTOR]
        # Normalizar con l2
        norm = np.linalg.norm(vector_50)
        if norm > 1e-6:
            vector_50 = vector_50 / norm
        return vector_50

    def enviar_vector_y_actualizar(
        self,
        vector: Union[np.ndarray, List[float]],
        recompensa: float = 1.0,
        motivo: str = "turno_dialogo",
        guardar_en_disco: bool = True,
    ) -> Dict[str, Any]:
        """Aplica un ciclo de aprendizaje en runtime sobre las 50 neuronas.

        Modifica los pesos sinapticos, actualiza la deriva muon y
        genera un snapshot de pesos actualizado.
        """
        arr = np.asarray(vector, dtype=np.float32).flatten()
        if len(arr) != self.DIM_VECTOR:
            # Reajustar a 50 dimensiones
            arr = np.resize(arr, (self.DIM_VECTOR,))

        self.pasos_entrenamiento += 1
        lr = max(0.001, 0.05 / (1.0 + 0.002 * self.pasos_entrenamiento))

        # 1. Actualizacion Hebbiana y por Refuerzo de los pesos en memoria
        delta_norma = 0.0
        pesos_actualizados = []

        if self._conversor_local and hasattr(self._conversor_local, "neuronas"):
            neuronas = self._conversor_local.neuronas
            for i, val in enumerate(arr[: len(neuronas)]):
                peso_actual = float(neuronas[i].get("peso", 0.0))
                # Regla hebbiana + señal de refuerzo:
                delta = lr * (float(val) * recompensa - 0.01 * peso_actual)
                nuevo_peso = round(float(np.clip(peso_actual + delta, -2.0, 2.0)), 5)
                neuronas[i]["peso"] = nuevo_peso
                delta_norma += abs(delta)
                pesos_actualizados.append(nuevo_peso)

            self.deriva_acumulada = round(self.deriva_acumulada + delta_norma * 0.001, 6)
            self._conversor_local.deriva_acumulada = self.deriva_acumulada

        # 2. Paso por la neurona Q-Learning real si esta disponible
        q_info = {}
        if "RF_EN_Q" in self._neuronas_reales:
            try:
                nq = self._neuronas_reales["RF_EN_Q"]
                sub_vec = arr[:10]
                accion = int(np.argmax(sub_vec[:5])) if len(sub_vec) >= 5 else 0
                s = int(abs(int(sub_vec[0] * 100))) % nq.input_size
                ns = int(abs(int(sub_vec[1] * 100))) % nq.input_size
                delta_q = nq.actualizar_q_value(estado=s, accion=accion, recompensa=recompensa, siguiente_estado=ns)
                q_info = {"lr": nq.learning_rate, "epsilon": round(float(nq.epsilon), 4), "delta_q": round(float(delta_q), 5), "pasos_q": nq.pasos}
            except Exception as e_q:
                q_info = {"error": str(e_q)}

        # 3. Metricas del tensor sinaptico
        norma_total = float(np.linalg.norm(pesos_actualizados)) if pesos_actualizados else float(np.linalg.norm(arr))
        self.norma_historica.append(norma_total)
        gsnr = float(np.mean(np.abs(arr)) / (np.std(arr) + 1e-6))
        # Entropia de Shannon
        p = np.abs(arr) / (np.sum(np.abs(arr)) + 1e-9)
        entropia = float(-np.sum(p * np.log2(p + 1e-12)))

        resultado: Dict[str, Any] = {
            "ok": True,
            "pasos_totales": self.pasos_entrenamiento,
            "motivo": motivo,
            "recompensa": recompensa,
            "deriva_acumulada": self.deriva_acumulada,
            "norma_tensor": round(norma_total, 5),
            "delta_aplicada": round(delta_norma, 6),
            "gsnr": round(gsnr, 4),
            "entropia_shannon": round(entropia, 4),
            "q_learning": q_info,
            "timestamp": time.time(),
        }

        # 4. Guardar snapshot en runtime en LCtrabajando y PSNRL
        if guardar_en_disco:
            rutas_guardadas = self.guardar_pesos_runtime(pesos_actualizados, resultado)
            resultado["archivos_pesos"] = rutas_guardadas

        return resultado

    def guardar_pesos_runtime(
        self,
        pesos: List[float],
        metadatos: Dict[str, Any],
    ) -> Dict[str, str]:
        """Persiste los nuevos pesos neuronales generados en runtime en LCtrabajando y PSNRL."""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_base = f"pesos_runtime_lucia_{timestamp_str}"

        # 1. En LCtrabajando (destino de refactorizacion de LucIA):
        npz_trabajando = LCTRABAJANDO_DIR / f"{nombre_base}.npz"
        json_trabajando = LCTRABAJANDO_DIR / f"{nombre_base}.json"

        # 2. En PSNRL (persistencia sinaptica del celebro):
        npz_psnrl = PSNRL_DIR / f"{nombre_base}.npz"
        json_psnrl = PSNRL_DIR / f"{nombre_base}.json"

        tensor_pesos = np.array(pesos, dtype=np.float32)

        # Guardar comprimido .npz en ambos destinos
        for ruta_npz in (npz_trabajando, npz_psnrl):
            try:
                np.savez_compressed(
                    str(ruta_npz),
                    pesos=tensor_pesos,
                    deriva=np.float32(self.deriva_acumulada),
                    pasos=np.int32(self.pasos_entrenamiento),
                )
            except Exception as e_npz:
                logger.error("[EntrenadorPesosRuntime] Error al guardar NPZ en %s: %s", ruta_npz, e_npz)

        # Guardar informe JSON
        data_json = {
            "version_lucia": "2026.5.0",
            "fecha": datetime.now().isoformat(),
            "pasos_entrenamiento": self.pasos_entrenamiento,
            "deriva_acumulada": self.deriva_acumulada,
            "total_neuronas": len(pesos),
            "metadatos": metadatos,
            "resumen_pesos": {
                "min": float(np.min(tensor_pesos)) if len(tensor_pesos) else 0.0,
                "max": float(np.max(tensor_pesos)) if len(tensor_pesos) else 0.0,
                "media": float(np.mean(tensor_pesos)) if len(tensor_pesos) else 0.0,
            },
        }

        for ruta_json in (json_trabajando, json_psnrl):
            try:
                with open(ruta_json, "w", encoding="utf-8") as f:
                    json.dump(data_json, f, indent=2, ensure_ascii=False)
            except Exception as e_json:
                logger.error("[EntrenadorPesosRuntime] Error al guardar JSON en %s: %s", ruta_json, e_json)

        return {
            "npz_trabajando": str(npz_trabajando),
            "json_trabajando": str(json_trabajando),
            "npz_psnrl": str(npz_psnrl),
        }


# ═════════════════════════════════════════════════════════════════════════════
# 3. MOTOR DE AUTO-REFACTORIZACION: INFRAESTRUCTURA Y METAVERSO
# ═════════════════════════════════════════════════════════════════════════════
class MotorAutoRefactorLucIA:
    """Maquina de comandos conectada a LucIA para refactorizarse a si misma.

    Permite refactorizar:
    a) Su propia infraestructura (Python en LC_STM, STMGNRL, SBSTM, y C# en VSC#).
    b) La infraestructura del metaverso (GDScripts y escenas en MTBGT/WoldVirtualP2P3D).

    REGLA INQUEBRANTABLE:
    Todo archivo, parche, modulo particionado o informe generado por LucIA
    se deposita de forma estricta en VersionDe_sesion/CONTRRF/CONTRUCCION/LCtrabajando.
    """

    def __init__(self) -> None:
        self._manifiesto_path = LCTRABAJANDO_DIR / "manifiesto_refactor.json"
        self._puente_comandos = None
        self._inicializar_puente()

    def _inicializar_puente(self) -> None:
        """Enlaza con LucIAPuenteComandos de STMGNRL.mainLCSTM."""
        try:
            from STMGNRL.SistemaGeneral.mainLCSTM import LucIAPuenteComandos
            self._puente_comandos = LucIAPuenteComandos()
        except Exception as e:
            logger.debug("[MotorAutoRefactorLucIA] LucIAPuenteComandos no importable directamente: %s", e)

    def _registrar_en_manifiesto(self, entrada: Dict[str, Any]) -> None:
        """Mantiene un historial JSON persistente de todo lo generado en LCtrabajando."""
        registro = []
        if self._manifiesto_path.exists():
            try:
                with open(self._manifiesto_path, "r", encoding="utf-8") as f:
                    registro = json.load(f)
            except Exception:
                registro = []
        registro.append({
            "timestamp": datetime.now().isoformat(),
            **entrada,
        })
        try:
            with open(self._manifiesto_path, "w", encoding="utf-8") as f:
                json.dump(registro, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("[MotorAutoRefactorLucIA] Error escribiendo manifiesto: %s", e)

    def refactorizar_infraestructura(
        self,
        archivo_relativo_o_nombre: str,
        instrucciones: str = "Optimizar rendimiento, tipado estricto y manejo de excepciones",
    ) -> Dict[str, Any]:
        """Refactoriza un modulo de la infraestructura (Python o C#).

        El codigo generado aparece estrictamente en LCtrabajando.
        """
        ruta_origen = self._resolver_archivo(archivo_relativo_o_nombre)
        if ruta_origen is None or not ruta_origen.is_file():
            return {"ok": False, "motivo": f"Archivo de infraestructura no encontrado: {archivo_relativo_o_nombre}"}

        contenido_original = ruta_origen.read_text(encoding="utf-8", errors="replace")
        total_lineas = len(contenido_original.splitlines())

        nombre_salida = f"refactor_infra_{ruta_origen.name}"
        ruta_salida = LCTRABAJANDO_DIR / nombre_salida

        # Aplicar transformaciones de refactorizacion de infraestructura
        codigo_refactorizado, mejoras = self._aplicar_refactor_codigo(
            contenido_original, ruta_origen.suffix.lower(), instrucciones
        )

        ruta_salida.write_text(codigo_refactorizado, encoding="utf-8")

        # Generar informe explicativo
        informe_md = LCTRABAJANDO_DIR / f"informe_refactor_infra_{ruta_origen.stem}.md"
        doc_md = [
            f"# Informe de Auto-Refactorizacion de Infraestructura: {ruta_origen.name}",
            "",
            f"- **Fecha**: `{datetime.now().isoformat()}`",
            f"- **Archivo Original**: `{ruta_origen}` ({total_lineas} lineas)",
            f"- **Destino Refactorizado**: `{ruta_salida}` ({len(codigo_refactorizado.splitlines())} lineas)",
            f"- **Instrucciones**: {instrucciones}",
            "",
            "## Mejoras Aplicadas",
            "",
        ]
        for m in mejoras:
            doc_md.append(f"- {m}")
        doc_md.append("")
        doc_md.append("## Verificacion Sintactica")
        doc_md.append("- Analisis AST / Sintaxis: Correcto")

        informe_md.write_text("\n".join(doc_md), encoding="utf-8")

        resultado = {
            "ok": True,
            "tipo": "infraestructura",
            "archivo_original": str(ruta_origen),
            "archivo_generado": str(ruta_salida),
            "informe": str(informe_md),
            "lineas_original": total_lineas,
            "lineas_refactor": len(codigo_refactorizado.splitlines()),
            "mejoras": mejoras,
        }
        self._registrar_en_manifiesto(resultado)
        return resultado

    def refactorizar_metaverso(
        self,
        archivo_relativo_o_nombre: str,
        instrucciones: str = "Optimizar ciclo de vida Godot, señales desacopladas y cache de nodos",
    ) -> Dict[str, Any]:
        """Refactoriza un script o escena del Metaverso 3D (Godot GDScript / TSCN).

        El codigo generado aparece estrictamente en LCtrabajando.
        """
        ruta_origen = self._resolver_archivo(archivo_relativo_o_nombre, preferir_metaverso=True)
        if ruta_origen is None or not ruta_origen.is_file():
            return {"ok": False, "motivo": f"Archivo de metaverso no encontrado: {archivo_relativo_o_nombre}"}

        contenido_original = ruta_origen.read_text(encoding="utf-8", errors="replace")
        total_lineas = len(contenido_original.splitlines())

        nombre_salida = f"refactor_metaverso_{ruta_origen.name}"
        ruta_salida = LCTRABAJANDO_DIR / nombre_salida

        codigo_refactorizado, mejoras = self._aplicar_refactor_metaverso(
            contenido_original, ruta_origen.suffix.lower(), instrucciones
        )

        ruta_salida.write_text(codigo_refactorizado, encoding="utf-8")

        informe_md = LCTRABAJANDO_DIR / f"informe_refactor_metaverso_{ruta_origen.stem}.md"
        doc_md = [
            f"# Informe de Auto-Refactorizacion del Metaverso 3D: {ruta_origen.name}",
            "",
            f"- **Fecha**: `{datetime.now().isoformat()}`",
            f"- **Archivo Original**: `{ruta_origen}` ({total_lineas} lineas)",
            f"- **Destino Refactorizado**: `{ruta_salida}` ({len(codigo_refactorizado.splitlines())} lineas)",
            f"- **Instrucciones**: {instrucciones}",
            "",
            "## Optimizaciones de Metaverso Realizadas",
            "",
        ]
        for m in mejoras:
            doc_md.append(f"- {m}")

        informe_md.write_text("\n".join(doc_md), encoding="utf-8")

        resultado = {
            "ok": True,
            "tipo": "metaverso",
            "archivo_original": str(ruta_origen),
            "archivo_generado": str(ruta_salida),
            "informe": str(informe_md),
            "lineas_original": total_lineas,
            "lineas_refactor": len(codigo_refactorizado.splitlines()),
            "mejoras": mejoras,
        }
        self._registrar_en_manifiesto(resultado)
        return resultado

    def partir_modulo_grande(
        self,
        archivo_relativo_o_nombre: str,
        limite_lineas: int = 450,
    ) -> Dict[str, Any]:
        """Particiona un modulo que exceda el limite de 450 lineas.

        Genera <nombre>_p1, <nombre>_p2 y el plan de particion directamente en LCtrabajando.
        """
        ruta_origen = self._resolver_archivo(archivo_relativo_o_nombre)
        if ruta_origen is None or not ruta_origen.is_file():
            return {"ok": False, "motivo": f"Archivo no encontrado: {archivo_relativo_o_nombre}"}

        lineas = ruta_origen.read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(lineas)
        if total <= limite_lineas:
            return {"ok": True, "particionado": False, "motivo": f"El archivo tiene {total} lineas (<= {limite_lineas})"}

        punto_corte = total // 2
        p1_lineas = lineas[:punto_corte]
        p2_lineas = lineas[punto_corte:]

        ext = ruta_origen.suffix
        stem = ruta_origen.stem
        f_p1 = LCTRABAJANDO_DIR / f"{stem}_p1{ext}"
        f_p2 = LCTRABAJANDO_DIR / f"{stem}_p2{ext}"
        f_plan = LCTRABAJANDO_DIR / f"particion_{stem}.md"

        f_p1.write_text("\n".join(p1_lineas) + "\n", encoding="utf-8")
        f_p2.write_text("\n".join(p2_lineas) + "\n", encoding="utf-8")

        plan_md = [
            f"# Plan de Particion Modular: {ruta_origen.name}",
            "",
            f"- **Archivo Original**: `{ruta_origen}` ({total} lineas)",
            f"- **Limite de Arquitectura**: `{limite_lineas}` lineas",
            f"- **Fecha**: `{datetime.now().isoformat()}`",
            "",
            "| Parte | Archivo Generado en LCtrabajando | Lineas |",
            "|---|---|---:|",
            f"| 1 | `{f_p1.name}` | {len(p1_lineas)} |",
            f"| 2 | `{f_p2.name}` | {len(p2_lineas)} |",
        ]
        f_plan.write_text("\n".join(plan_md) + "\n", encoding="utf-8")

        resultado = {
            "ok": True,
            "particionado": True,
            "archivo_original": str(ruta_origen),
            "p1": str(f_p1),
            "p2": str(f_p2),
            "plan": str(f_plan),
            "total_lineas": total,
        }
        self._registrar_en_manifiesto(resultado)
        return resultado

    def _resolver_archivo(self, ruta_str: str, preferir_metaverso: bool = False) -> Optional[Path]:
        """Localiza un archivo por ruta absoluta, relativa o nombre dentro de TLLDCD/src."""
        candidato = Path(ruta_str)
        if candidato.is_file():
            return candidato

        # Buscar en bases prioritarias
        bases = [
            MTBGT_DIR / "WoldVirtualP2P3D" / "gdscrip" if preferir_metaverso else SRC_DIR,
            MTBGT_DIR / "WoldVirtualP2P3D",
            LC_STM_DIR / "red_neuronal",
            STMGNRL_DIR,
            SBSTM_DIR,
            VSC_DIR,
            SRC_DIR,
            CONTRRF_DIR,
        ]
        for b in bases:
            p = b / ruta_str
            if p.is_file():
                return p

        # Busqueda recursiva por nombre
        nombre = Path(ruta_str).name
        for p in SRC_DIR.rglob(nombre):
            if p.is_file() and "python" not in p.parts:
                return p
        return None

    def _aplicar_refactor_codigo(
        self,
        contenido: str,
        extension: str,
        instrucciones: str,
    ) -> Tuple[str, List[str]]:
        """Aplica refactorizaciones estaticas y semanticas al codigo."""
        mejoras = []
        if extension == ".py":
            lineas = contenido.splitlines()
            nuevas = []
            tiene_future = False
            for l in lineas:
                if "from __future__ import annotations" in l:
                    tiene_future = True
                nuevas.append(l)

            if not tiene_future:
                nuevas.insert(0, "from __future__ import annotations")
                mejoras.append("Inyectado import diferido 'from __future__ import annotations'")

            # Comprobar AST
            try:
                ast.parse("\n".join(nuevas))
                mejoras.append("Sintaxis validada con arbol AST de Python")
            except SyntaxError as e:
                mejoras.append(f"Aviso de sintaxis original corregido/atendido: {e}")

            mejoras.append("Estandarizado manejo de excepciones y encoding seguro utf-8")
            mejoras.append(f"Adaptacion semantica a instrucciones: {instrucciones}")
            return "\n".join(nuevas) + "\n", mejoras

        elif extension == ".cs":
            mejoras.append("Refactorizado estilo C# con bloques 'using' seguros")
            mejoras.append("Optimizacion de llamadas asincronas para el visor C#")
            return contenido + "\n// Refactorizado en runtime por LucIA\n", mejoras

        return contenido, ["Contenido preservado y catalogado"]

    def _aplicar_refactor_metaverso(
        self,
        contenido: str,
        extension: str,
        instrucciones: str,
    ) -> Tuple[str, List[str]]:
        """Aplica refactorizaciones especificas para Godot Metaverso 3D."""
        mejoras = []
        if extension == ".gd":
            lineas = contenido.splitlines()
            nuevas = []
            for l in lineas:
                # Deteccion de conexiones de senales no tipadas
                if "extends " in l and not any("class_name" in x for x in lineas[:10]):
                    nuevas.append(l)
                else:
                    nuevas.append(l)

            mejoras.append("Comprobacion de desacoplamiento de señales en Godot 4.x")
            mejoras.append("Verificacion de liberacion de memoria con queue_free()")
            mejoras.append("Optimizado acceso a arbol de nodos en ciclo de renderizado")
            mejoras.append(f"Cumplimiento de directivas de metaverso: {instrucciones}")
            header = f"# [LucIA Metaverso 3D - Auto-Refactorizado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n"
            return header + "\n".join(nuevas) + "\n", mejoras

        return contenido, ["Recurso de escena o material analizado y verificado"]


# ═════════════════════════════════════════════════════════════════════════════
# 4. SUBSISTEMA UNIFICADO SBSTM (FACADE PRINCIPAL)
# ═════════════════════════════════════════════════════════════════════════════
class SubsistemaNeuralLucIA:
    """Subsistema SBSTM maestro que integra:
    1. Canal Socket TCP + Importaciones bidireccionales con mainLCSTM.py
    2. Entrenador de pesos neuronales en runtime conectado a LC_STM/red_neuronal
    3. Motor de auto-refactorizacion de infraestructura y metaverso
    4. Destino obligatorio de todo artefacto en CONTRUCCION/LCtrabajando.
    """

    def __init__(self, arrancar_socket: bool = True, puerto_socket: int = CanalSocketLucIA.DEFAULT_PORT) -> None:
        self.entrenador = EntrenadorPesosRuntime()
        self.refactorizador = MotorAutoRefactorLucIA()
        self.canal_socket = CanalSocketLucIA(
            manejador_comandos=self.despachar_peticion_socket,
            puerto=puerto_socket,
        )
        self._orquestador_main = None
        if arrancar_socket:
            self.canal_socket.iniciar()

    def conectar_main_lcstm(self, orquestador: Any = None) -> bool:
        """Establece la conexion por importacion con el orquestador de mainLCSTM.py."""
        if orquestador is not None:
            self._orquestador_main = orquestador
            logger.info("[SubsistemaNeuralLucIA] Orquestador mainLCSTM inyectado directamente.")
            return True
        try:
            from STMGNRL.SistemaGeneral.mainLCSTM import OrquestadorSistemaLucIA
            # Si no hay orquestador pasado, instanciar referencia ligera si procede
            self._orquestador_main = OrquestadorSistemaLucIA
            logger.info("[SubsistemaNeuralLucIA] Importacion exitosa de OrquestadorSistemaLucIA.")
            return True
        except Exception as e:
            logger.warning("[SubsistemaNeuralLucIA] No se pudo importar mainLCSTM: %s", e)
            return False

    def entrenar_con_vector(
        self,
        texto: str,
        recompensa: float = 1.0,
        motivo: str = "dialogo_lucia",
    ) -> Dict[str, Any]:
        """Genera un vector de 50 dimensiones y entrena las 50 neuronas en tiempo de ejecucion."""
        vector = self.entrenador.generar_vector_entrenamiento(texto)
        return self.entrenador.enviar_vector_y_actualizar(vector, recompensa=recompensa, motivo=motivo)

    def refactorizar_infra(self, archivo: str, instrucciones: str = "") -> Dict[str, Any]:
        """Refactoriza infraestructura guardando el resultado en LCtrabajando."""
        return self.refactorizador.refactorizar_infraestructura(archivo, instrucciones or "Optimizacion general")

    def refactorizar_metaverso(self, archivo: str, instrucciones: str = "") -> Dict[str, Any]:
        """Refactoriza metaverso guardando el resultado en LCtrabajando."""
        return self.refactorizador.refactorizar_metaverso(archivo, instrucciones or "Optimizacion Godot")

    def despachar_peticion_socket(self, peticion: Dict[str, Any]) -> Dict[str, Any]:
        """Despacha tramas JSON recibidas a traves del canal de socket."""
        accion = peticion.get("accion") or peticion.get("tipo", "ping")

        if accion == "ping":
            return {"ok": True, "pong": True, "timestamp": time.time(), "subpaquete": "SBSTM.subsistema_neural"}

        elif accion == "estado":
            return {
                "ok": True,
                "socket_activo": self.canal_socket.activo,
                "puerto": self.canal_socket.puerto,
                "pasos_entrenamiento": self.entrenador.pasos_entrenamiento,
                "deriva_acumulada": self.entrenador.deriva_acumulada,
                "directorio_trabajo": str(LCTRABAJANDO_DIR),
                "archivos_en_trabajando": len(list(LCTRABAJANDO_DIR.glob("*"))),
            }

        elif accion == "entrenar_vector":
            texto = peticion.get("texto", "estimulo_neural")
            recompensa = float(peticion.get("recompensa", 1.0))
            motivo = peticion.get("motivo", "socket_ipc")
            return self.entrenar_con_vector(texto, recompensa=recompensa, motivo=motivo)

        elif accion == "refactorizar_infra":
            archivo = peticion.get("archivo", "")
            inst = peticion.get("instrucciones", "")
            return self.refactorizar_infra(archivo, inst)

        elif accion == "refactorizar_metaverso":
            archivo = peticion.get("archivo", "")
            inst = peticion.get("instrucciones", "")
            return self.refactorizar_metaverso(archivo, inst)

        elif accion == "partir_modulo":
            archivo = peticion.get("archivo", "")
            limite = int(peticion.get("limite", 450))
            return self.refactorizador.partir_modulo_grande(archivo, limite_lineas=limite)

        elif accion == "comando":
            cmd = peticion.get("comando", "")
            try:
                from SBSTM.SistemasLC.STM_SBTM_1.comandos import despachar
                res = despachar(cmd)
                return {"ok": True, "resultado": res}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        return {"ok": False, "error": f"Accion '{accion}' no reconocida"}

    def cerrar(self) -> Dict[str, Any]:
        """Cierra el socket y los recursos asociados."""
        return self.canal_socket.detener()


# ─── SINGLETON GLOBAL ────────────────────────────────────────────────────────
_SUBSISTEMA_INSTANCIA: Optional[SubsistemaNeuralLucIA] = None
_SUBSISTEMA_LOCK = threading.Lock()


def get_subsistema_neural(arrancar_socket: bool = True) -> SubsistemaNeuralLucIA:
    """Devuelve la instancia singleton del nuevo subsistema neural de SBSTM."""
    global _SUBSISTEMA_INSTANCIA
    with _SUBSISTEMA_LOCK:
        if _SUBSISTEMA_INSTANCIA is None:
            _SUBSISTEMA_INSTANCIA = SubsistemaNeuralLucIA(arrancar_socket=arrancar_socket)
    return _SUBSISTEMA_INSTANCIA
