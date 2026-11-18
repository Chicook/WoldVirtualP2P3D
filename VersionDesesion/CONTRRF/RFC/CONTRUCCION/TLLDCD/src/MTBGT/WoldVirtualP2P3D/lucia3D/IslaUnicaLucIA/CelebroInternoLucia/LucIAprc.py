# =============================================================================
# IMPORTACIÓN CANÓNICA DE mainLCSTM (Orquestador Central Cognitivo de LucIA)
# Conforme a la jerarquía modular de rutas de .dev y TLLDCD
# Permite a LucIA tener pleno control de su avatar 3D como en el experimento Eco del MIT.
# =============================================================================
import sys
from pathlib import Path

_DIR_ACTUAL = Path(__file__).resolve().parent
_SRC_DIR = _DIR_ACTUAL.parents[4]  # TLLDCD/src
_DEV_DIR = _DIR_ACTUAL.parents[6] / ".dev"

for _directorio_adicional in (str(_SRC_DIR), str(_DEV_DIR)):
    if _directorio_adicional not in sys.path:
        sys.path.insert(0, _directorio_adicional)

try:
    from STMGNRL.SistemaGeneral import mainLCSTM
except (ImportError, ValueError):
    mainLCSTM = None

"""
SeguridadNeuronal - Módulo de seguridad matemáticamente robusto para LucIA
===========================================================================
Implementa:
  - Entropía de Shannon para detección de anomalías
  - Red neuronal MLP (2 capas ocultas) para clasificación de amenazas
  - Aprendizaje online del MLP (retropropagación con recorte de gradiente)
  - Distancia de Mahalanobis diagonal para detectar vectores fuera de baseline
  - Umbral adaptativo bayesiano (Teorema de Bayes)
  - Control estadístico de proceso: EWMA + CUSUM bilateral
  - Hash de integridad SHA-256
  - Firma HMAC y derivación HKDF (RFC 5869) por módulo
  - Anti-replay con nonce aleatorio y ventana temporal (TTL)
  - Limitador de tasa por cubo de fichas (token bucket)
  - Sistema de cuarentena con puntuación de riesgo exponencial
  - Narración en español para el avatar 3D de LucIA
"""

import math
import hashlib
import hmac as _hmac
import json
import time
import random
import os
import socket
import threading as _threading
from collections import Counter, deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Intento de importar numpy; si no está disponible se usa modo fallback puro Python
try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False


# ---------------------------------------------------------------------------
# Utilidades matemáticas puras (fallback sin numpy)
# ---------------------------------------------------------------------------

def _dot(a, b):
    """Producto punto entre dos vectores (listas) de igual longitud."""
    return sum(x * y for x, y in zip(a, b))

def _mat_vec(M, v):
    """Multiplicación matriz × vector. M es lista de filas (listas)."""
    return [_dot(row, v) for row in M]

def _relu(x):
    """Función de activación ReLU: max(0, x)."""
    if isinstance(x, list):
        return [max(0.0, xi) for xi in x]
    return max(0.0, x)

def _sigmoid(x):
    """
    Función de activación Sigmoid: σ(x) = 1 / (1 + e^(-x))
    Clamp para evitar overflow numérico.
    """
    if isinstance(x, list):
        return [_sigmoid(xi) for xi in x]
    x = max(-500.0, min(500.0, x))
    return 1.0 / (1.0 + math.exp(-x))

def _add_bias(v, b):
    """Suma el vector de bias a un vector de activaciones."""
    return [vi + bi for vi, bi in zip(v, b)]


# ---------------------------------------------------------------------------
# Clase Principal de Seguridad 3D para la DAO y Avatar de LucIA
# ---------------------------------------------------------------------------

class Seguridad3D:
    """
    Clase principal de seguridad neuronal para LucIA en 3D y protección de la DAO.

    Combina técnicas de teoría de la información, aprendizaje automático
    ligero y criptografía para proteger la integridad del cerebro interno
    de LucIA y detectar amenazas en tiempo real. Además de cálculo neuronal 
    que mediante sockets conecta a un GDScript concreto para proteger la DAO,
    orquestando el control del avatar 3D de LucIA conforme al Experimento Eco del MIT.
    """

    ALTURA_MESETA: float = 40.2
    RADIO_PERIMETRO_DAO: float = 31.0
    RADIO_OFICINA_CENTRAL: float = 7.2
    PUERTO_SOCKET_DEFECTO: int = 9099

    ESTACIONES_CARDINALES: dict = {
        "identidad": (0.0, 40.2, 22.0),       # Norte (PlazaRegistroDAO: RegistroNorte)
        "cuenta_unica": (22.0, 40.2, 0.0),    # Este (PlazaRegistroDAO: RegistroEste)
        "huella_equipo": (-22.0, 40.2, 0.0),  # Oeste (PlazaRegistroDAO: RegistroOeste)
        "firma_sesion": (0.0, 40.2, -22.0),   # Sur (PlazaRegistroDAO: RegistroSur)
    }

    def __init__(
        self,
        host: str = "127.0.0.1",
        puerto_socket: int = PUERTO_SOCKET_DEFECTO,
        clave_maestra: str = "LucIA_DAO_Security_3D_MIT_ECO",
        autoiniciar_socket: bool = False
    ):
        self.host: str = host
        self.puerto: int = puerto_socket
        self.clave_maestra: str = clave_maestra
        self.clave_bytes: bytes = clave_maestra.encode("utf-8")
        self.timestamp_inicio: float = time.time()

        # Vinculación al Orquestador Central Cognitivo de LucIA
        self.orquestador_cognitivo = mainLCSTM

        # Referencia perezosa al subsistema de SeguridadNeuronal primitivo
        self._seguridad_neuronal: Optional["SeguridadNeuronal"] = None

        # Red neuronal especializada en la DAO (MLP: entrada 8 -> oculta1 12 -> oculta2 6 -> salida 1)
        self._pesos_dao = self._inicializar_red_dao()

        # Estado del Avatar 3D de LucIA (Modelo de Agente Sintético · Experimento Eco del MIT)
        self.estado_avatar: dict = {
            "expresion": "amable",
            "gesto": "reposo",
            "postura": "de_pie",
            "apertura_boca": 0.0,
            "alerta_activa": False,
            "orientacion_objetivo": [0.0, 40.2, 0.0],
            "ultima_frase": "Sistemas de la DAO del metaverso operativos y protegidos.",
        }

        # Estado de seguridad de la DAO
        self.nivel_salud_dao: float = 100.0  # 0.0 a 100.0
        self.cuarentena_dao: dict = {}
        self.historial_eventos_dao: deque = deque(maxlen=512)

        # Servidor de Sockets TCP NDJSON para conexión bidireccional con GDScript
        self._servidor_socket: Optional[socket.socket] = None
        self._hilo_socket: Optional[_threading.Thread] = None
        self._activo: bool = False
        self._bloqueo = _threading.Lock()

        if autoiniciar_socket:
            self.iniciar_servidor_socket()

    @property
    def subsistema_neuronal(self) -> "SeguridadNeuronal":
        """Obtiene o inicializa de forma segura la instancia de SeguridadNeuronal."""
        if self._seguridad_neuronal is None:
            self._seguridad_neuronal = SeguridadNeuronal(self.clave_maestra)
        return self._seguridad_neuronal

    def _inicializar_red_dao(self) -> dict:
        """Inicializa los pesos de la red neuronal de la DAO usando Xavier y semilla criptográfica."""
        semilla_hex = hashlib.sha256(self.clave_bytes + b"::dao_neural_weights_v3").hexdigest()
        semilla_int = int(semilla_hex[:8], 16)
        rng = random.Random(semilla_int)

        def _xavier(fan_in: int, fan_out: int) -> list:
            limite = math.sqrt(6.0 / (fan_in + fan_out))
            return [[rng.uniform(-limite, limite) for _ in range(fan_in)] for _ in range(fan_out)]

        return {
            "W1": _xavier(8, 12),
            "b1": [0.0] * 12,
            "W2": _xavier(12, 6),
            "b2": [0.0] * 6,
            "W3": _xavier(6, 1),
            "b3": [-0.35],  # sesgo inicial
        }

    def _forward_dao(self, vector_8d: list) -> float:
        """Propagación hacia adelante por el MLP de seguridad de la DAO (8 -> 12 -> 6 -> 1)."""
        z1 = _add_bias(_mat_vec(self._pesos_dao["W1"], vector_8d), self._pesos_dao["b1"])
        a1 = _relu(z1)
        z2 = _add_bias(_mat_vec(self._pesos_dao["W2"], a1), self._pesos_dao["b2"])
        a2 = _relu(z2)
        z3 = _add_bias(_mat_vec(self._pesos_dao["W3"], a2), self._pesos_dao["b3"])
        return _sigmoid(z3[0])

    def construir_vector_dao(
        self,
        actor: str,
        posicion_3d: list,
        estacion: str = "",
        cadencia_req_s: float = 1.0,
        firma_valida: bool = True
    ) -> list:
        """
        Construye un vector normalizado de 8 dimensiones para inferencia neuronal:
        [0] Distancia radial normalizada en plano XZ (0.0 = centro, >1.0 = fuera del atrio)
        [1] Desviación vertical Y normalizada respecto a la meseta (40.2m)
        [2] Distancia euclidiana a la estación cardinal declarada
        [3] Cadencia de peticiones normalizada (token bucket)
        [4] Coherencia de firma criptográfica (0.0 = válida, 1.0 = inválida)
        [5] Entropía de interacción del actor
        [6] Nivel de historial de incidentes
        [7] Deriva acumulada CUSUM / baseline
        """
        x = float(posicion_3d[0]) if len(posicion_3d) > 0 else 0.0
        y = float(posicion_3d[1]) if len(posicion_3d) > 1 else self.ALTURA_MESETA
        z = float(posicion_3d[2]) if len(posicion_3d) > 2 else 0.0

        dist_radial = math.sqrt(x * x + z * z)
        d_norm = min(2.0, dist_radial / self.RADIO_PERIMETRO_DAO)
        desv_y = min(2.0, abs(y - self.ALTURA_MESETA) / 4.0)

        d_estacion = 0.0
        if estacion in self.ESTACIONES_CARDINALES:
            ex, ey, ez = self.ESTACIONES_CARDINALES[estacion]
            d_est = math.sqrt((x - ex)**2 + (y - ey)**2 + (z - ez)**2)
            d_estacion = min(2.0, d_est / 15.0)

        cad_norm = min(2.0, cadencia_req_s / 5.0)
        sig_penalidad = 0.0 if firma_valida else 1.0

        self.subsistema_neuronal.registrar_evento(f"dao_actor:{actor[:16]}")
        entropia = self.subsistema_neuronal.detectar_anomalia_entropia()["entropia"]
        ent_norm = min(1.0, entropia / 4.0)

        incidentes = self.cuarentena_dao.get(actor, {}).get("incidentes", 0)
        inc_norm = min(2.0, incidentes / 5.0)

        cusum_val = min(1.0, max(0.0, self.subsistema_neuronal._cusum_pos / 5.0))

        return [d_norm, desv_y, d_estacion, cad_norm, sig_penalidad, ent_norm, inc_norm, cusum_val]

    def evaluar_seguridad_dao(
        self,
        actor: str,
        posicion_3d: list,
        estacion: str = "",
        firma_valida: bool = True,
        cadencia: float = 1.0
    ) -> dict:
        """
        Evalúa de forma integral la interacción dentro de la DAO usando:
        - Inferencia neuronal con MLP especializado en espacio 3D
        - Distancia de Mahalanobis y CUSUM bilateral
        - Detección de teletransporte o violación de perímetro 3D
        - Generación de comandos para el avatar 3D según el Experimento Eco del MIT
        """
        with self._bloqueo:
            ahora = time.time()
            if actor in self.cuarentena_dao:
                info_q = self.cuarentena_dao[actor]
                if ahora < info_q.get("expira", 0):
                    reaccion = self.control_avatar_eco_mit(
                        estado_seguridad="CUARENTENA",
                        nivel_riesgo=1.0,
                        posicion_intruso=posicion_3d,
                        motivo=f"Entidad en cuarentena activa: {info_q.get('razon')}"
                    )
                    return {
                        "autorizado": False,
                        "riesgo": 1.0,
                        "decision": "CUARENTENA",
                        "motivo": f"Actor en cuarentena hasta {datetime.fromtimestamp(info_q['expira']).isoformat()}",
                        "accion_avatar": reaccion,
                        "color_baliza": "rojo_bloqueo",
                        "halo_estacion": "inactiva"
                    }

            vector_8d = self.construir_vector_dao(actor, posicion_3d, estacion, cadencia, firma_valida)
            p_red = self._forward_dao(vector_8d)

            self.subsistema_neuronal.actualizar_ewma(p_red)
            cusum_res = self.subsistema_neuronal.actualizar_cusum(p_red)

            self.subsistema_neuronal.calibrar_baseline(vector_8d[:6])
            mahal = self.subsistema_neuronal.detectar_anomalia_mahalanobis(vector_8d[:6])

            prob_bayes = self.subsistema_neuronal.actualizar_bayesiano(
                p_red > 0.5 or mahal.get("probabilidad", 0.0) >= 0.5
            )
            riesgo_final = max(p_red, prob_bayes, mahal["probabilidad"])

            if riesgo_final >= 0.70 or not firma_valida:
                decision = "BLOQUEAR"
                autorizado = False
                self.nivel_salud_dao = max(0.0, self.nivel_salud_dao - 15.0)
                self.cuarentena_dao[actor] = {
                    "incidentes": self.cuarentena_dao.get(actor, {}).get("incidentes", 0) + 1,
                    "expira": ahora + 120.0,
                    "razon": f"Riesgo crítico detectado ({riesgo_final:.2f})"
                }
                halo_estacion = "inactiva"
                color_baliza = "rojo_bloqueo"
            elif riesgo_final >= 0.35:
                decision = "ADVERTIR"
                autorizado = True
                self.nivel_salud_dao = max(0.0, self.nivel_salud_dao - 3.0)
                halo_estacion = "activa"
                color_baliza = "oro_advertencia"
            else:
                decision = "PERMITIR"
                autorizado = True
                self.nivel_salud_dao = min(100.0, self.nivel_salud_dao + 1.0)
                halo_estacion = "completa" if estacion else "activa"
                color_baliza = "cian_normal"

            reaccion_avatar = self.control_avatar_eco_mit(
                estado_seguridad=decision,
                nivel_riesgo=riesgo_final,
                posicion_intruso=posicion_3d,
                motivo=f"Estación {estacion or 'atrio central'}"
            )

            resultado = {
                "autorizado": autorizado,
                "riesgo": round(riesgo_final, 4),
                "p_red_neuronal": round(p_red, 4),
                "p_bayes": round(prob_bayes, 4),
                "mahalanobis_d": round(mahal["distancia"], 4),
                "decision": decision,
                "salud_dao": round(self.nivel_salud_dao, 2),
                "accion_avatar": reaccion_avatar,
                "color_baliza": color_baliza,
                "halo_estacion": halo_estacion,
                "timestamp": ahora,
            }
            self.historial_eventos_dao.append(resultado)
            return resultado

    def control_avatar_eco_mit(
        self,
        estado_seguridad: str,
        nivel_riesgo: float,
        posicion_intruso: list = None,
        motivo: str = ""
    ) -> dict:
        """
        Modelo de Comportamiento Autónomo del Avatar 3D basado en el Experimento Eco del MIT.
        Controla dinámicamente la expresión facial, gestualidad de los 65 huesos Mixamo,
        rotación de cabeza/mirada hacia el objetivo y lipsync vocal para interactuar
        con los scripts de Godot (lucia_personaje.gd, InteriorDAO.gd y PlazaRegistroDAO.gd).
        """
        pos = posicion_intruso or [0.0, self.ALTURA_MESETA, 0.0]

        if nivel_riesgo < 0.30:
            expresion = "amable"
            gesto = "bienvenida"
            postura = "de_pie"
            lipsync = 0.0
            frase = "Bienvenido al atrio de la DAO del metaverso. La estación se encuentra operativa y segura."
            alerta = False
        elif nivel_riesgo < 0.70:
            expresion = "curiosa_cautelosa"
            gesto = "atencion"
            postura = "orientar_cabeza"
            lipsync = 0.45
            frase = f"Precaución en la isla. Detecto inconsistencias en la interacción: {motivo}."
            alerta = True
        else:
            expresion = "defensiva_firme"
            gesto = "detener_paso"
            postura = "alerta_defensiva"
            lipsync = 0.85
            frase = f"Acceso suspendido por protocolo de seguridad neuronal. {motivo}."
            alerta = True

        comando = {
            "expresion": expresion,
            "gesto": gesto,
            "postura": postura,
            "lipsync_apertura": lipsync,
            "rotar_hacia": [pos[0], pos[1], pos[2]],
            "alerta_activa": alerta,
            "narracion_voz": frase,
            "timestamp": time.time(),
        }
        self.estado_avatar.update(comando)
        return comando

    def sellar_transaccion_dao(self, datos_transaccion: dict) -> str:
        """Sella criptográficamente una transacción de la DAO usando HKDF y HMAC-SHA256."""
        clave_dao = self.subsistema_neuronal.derivar_clave("modulo:dao_metaverso_governance")
        datos_str = json.dumps(datos_transaccion, sort_keys=True, ensure_ascii=False)
        h = _hmac.new(clave_dao, datos_str.encode("utf-8"), hashlib.sha256)
        return h.hexdigest()

    def verificar_transaccion_dao(self, datos_transaccion: dict, firma: str) -> bool:
        """Verifica la firma HMAC-SHA256 de una transacción de la DAO."""
        esperada = self.sellar_transaccion_dao(datos_transaccion)
        return _hmac.compare_digest(esperada, firma)

    def iniciar_servidor_socket(self) -> bool:
        """Inicia el servidor socket TCP NDJSON en segundo plano para comunicarse con Godot (GDScript)."""
        with self._bloqueo:
            if self._activo:
                return True
            try:
                self._servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._servidor_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._servidor_socket.bind((self.host, self.puerto))
                self._servidor_socket.listen(5)
                self._servidor_socket.settimeout(1.0)
                self._activo = True

                self._hilo_socket = _threading.Thread(
                    target=self._bucle_servidor_socket,
                    name="LucIA_Seguridad3D_Socket",
                    daemon=True
                )
                self._hilo_socket.start()
                return True
            except Exception:
                self._activo = False
                return False

    def detener_servidor_socket(self) -> None:
        """Detiene el servidor socket y cierra conexiones."""
        with self._bloqueo:
            self._activo = False
            if self._servidor_socket:
                try:
                    self._servidor_socket.close()
                except Exception:
                    pass
                self._servidor_socket = None

    def _bucle_servidor_socket(self) -> None:
        """Bucle en segundo plano para aceptar conexiones de nodos GDScript."""
        while self._activo and self._servidor_socket:
            try:
                cliente, _ = self._servidor_socket.accept()
                _threading.Thread(
                    target=self._atender_cliente_gdscript,
                    args=(cliente,),
                    daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception:
                break

    def _atender_cliente_gdscript(self, cliente: socket.socket) -> None:
        """Atiende la conexión NDJSON con un nodo GDScript de Godot."""
        cliente.settimeout(5.0)
        buffer = ""
        try:
            with cliente:
                while self._activo:
                    datos = cliente.recv(4096)
                    if not datos:
                        break
                    buffer += datos.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        linea, buffer = buffer.split("\n", 1)
                        linea = linea.strip()
                        if not linea:
                            continue
                        respuesta = self.procesar_mensaje_gdscript(linea)
                        cliente.sendall((respuesta + "\n").encode("utf-8"))
        except Exception:
            pass

    def procesar_mensaje_gdscript(self, linea_json: str) -> str:
        """
        Procesa una línea JSON recibida desde GDScript y devuelve la respuesta NDJSON:
        Comandos admitidos:
        - 'evaluar_interaccion': Evalúa un actor en una estación cardinal de la DAO.
        - 'sellar_transaccion': Sella criptográficamente una transacción de la DAO.
        - 'verificar_transaccion': Valida la integridad de un registro.
        - 'estado_dao': Devuelve la telemetría de salud y estado del avatar.
        """
        try:
            solicitud = json.loads(linea_json)
        except Exception as e:
            return json.dumps({"error": f"JSON inválido: {e}"}, ensure_ascii=False)

        cmd = solicitud.get("comando") or solicitud.get("tipo") or "evaluar_interaccion"

        if cmd in ("ping", "echo"):
            return json.dumps({"pong": True, "timestamp": time.time()}, ensure_ascii=False)

        elif cmd in ("evaluar_interaccion", "evaluar_acceso"):
            actor = str(solicitud.get("actor", "anonimo_dao"))
            pos = solicitud.get("posicion", [0.0, self.ALTURA_MESETA, 0.0])
            estacion = str(solicitud.get("estacion", ""))
            firma_ok = bool(solicitud.get("firma_valida", True))
            cadencia = float(solicitud.get("cadencia", 1.0))
            res = self.evaluar_seguridad_dao(actor, pos, estacion, firma_ok, cadencia)
            return json.dumps(res, ensure_ascii=False)

        elif cmd == "sellar_transaccion":
            datos_tx = solicitud.get("datos") or solicitud.get("transaccion") or {}
            firma = self.sellar_transaccion_dao(datos_tx)
            return json.dumps({"ok": True, "firma": firma, "timestamp": time.time()}, ensure_ascii=False)

        elif cmd == "verificar_transaccion":
            datos_tx = solicitud.get("datos") or solicitud.get("transaccion") or {}
            firma = str(solicitud.get("firma", ""))
            valido = self.verificar_transaccion_dao(datos_tx, firma)
            return json.dumps({"ok": True, "valida": valido, "valido": valido}, ensure_ascii=False)

        elif cmd in ("estado_dao", "obtener_estado_avatar"):
            return json.dumps({
                "ok": True,
                "salud_dao": self.nivel_salud_dao,
                "estado": self.estado_avatar,
                "avatar": self.estado_avatar,
                "cuarentenas_activas": len(self.cuarentena_dao),
                "total_eventos": len(self.historial_eventos_dao),
                "orquestador_cognitivo": bool(self.orquestador_cognitivo is not None),
                "tiempo_activo": round(time.time() - self.timestamp_inicio, 2),
            }, ensure_ascii=False)

        else:
            return json.dumps({"error": f"Comando '{cmd}' no reconocido por Seguridad3D"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class SeguridadNeuronal:
    """
    Sistema de seguridad neuronal de LucIA.

    Combina técnicas de teoría de la información, aprendizaje automático
    ligero y criptografía para proteger la integridad del cerebro interno
    de LucIA y detectar amenazas en tiempo real.
    """

    # ------------------------------------------------------------------
    # 1. INICIALIZACIÓN
    # ------------------------------------------------------------------

    def __init__(self, clave_maestra: str = "LucIA_SecretKey_MIT_ECO"):
        """
        Inicializa todos los subsistemas de seguridad.

        Parámetros
        ----------
        clave_maestra : str
            Clave usada para HMAC y derivación de semillas de red neuronal.
        """
        # --- Estado básico ---
        self.estado_seguridad: str = "activo"
        self.nivel_seguridad: float = 100.0        # 0-100
        self.timestamp_inicio: float = time.time()

        # --- Clave maestra (nunca sale de este objeto) ---
        self._clave_bytes: bytes = clave_maestra.encode("utf-8")

        # --- Historial de eventos para entropía ---
        # Ventana deslizante de los últimos 256 eventos
        self._historial_eventos: deque = deque(maxlen=256)
        self._entropia_actual: float = 0.0

        # --- Red neuronal de detección de amenazas ---
        # Arquitectura: entrada(6) → oculta1(8) → oculta2(4) → salida(1)
        # Pesos inicializados con Xavier usando semilla determinista derivada de la clave
        self._pesos_nn = self._inicializar_red_neuronal()

        # --- Umbral adaptativo bayesiano ---
        # P(amenaza) prior inicial conservador
        self._prob_amenaza_prior: float = 0.05        # P(A)
        self._prob_evidencia_dado_amenaza: float = 0.90   # P(B|A)
        self._prob_evidencia_dado_seguro: float = 0.10    # P(B|¬A)
        self._prob_amenaza_posterior: float = self._prob_amenaza_prior

        # --- Registro de hashes de integridad ---
        # módulo → hash SHA-256 en el momento del registro
        self._hashes_modulos: dict = {}

        # --- Sistema de cuarentena ---
        # módulo → {"riesgo": float, "timestamp": float, "razon": str}
        self._cuarentena: dict = {}
        self._umbral_cuarentena: float = 0.75   # riesgo > 0.75 → cuarentena

        # --- Anti-replay: nonce → instante de expiración ---
        self._nonces_vistos: dict = {}
        self._ttl_nonce: float = 30.0
        self._cerrojo = _threading.Lock()

        # --- Limitador de tasa por cubo de fichas ---
        # clave → [fichas_disponibles, ultimo_instante]
        self._cubos: dict = {}

        # --- Control estadístico: EWMA y CUSUM ---
        self._ewma_riesgo: float = 0.0
        self._cusum_pos: float = 0.0
        self._cusum_neg: float = 0.0
        self._cusum_objetivo: float = 0.20
        self._cusum_deriva: float = 0.10
        self._cusum_umbral: float = 2.50

        # --- Baseline del vector de amenaza (media y M2 de Welford) ---
        self._baseline_media: list = [0.0] * 6
        self._baseline_m2: list = [0.0] * 6
        self._baseline_n: int = 0
        self._ultima_p_mahalanobis: float = 0.0

        # --- Log de auditoría ---
        self._log: list = []
        self._log_max: int = 1000

        self._registrar_log("INIT", "SeguridadNeuronal inicializada correctamente.")

    # ------------------------------------------------------------------
    # 2. RED NEURONAL (MLP) — DETECCIÓN DE AMENAZAS
    # ------------------------------------------------------------------

    def _inicializar_red_neuronal(self) -> dict:
        """
        Inicializa los pesos del MLP con Xavier initialization.

        Xavier: W ~ U[-sqrt(6/(fan_in+fan_out)), +sqrt(6/(fan_in+fan_out))]

        Usa una semilla derivada HMAC de la clave maestra para reproducibilidad
        determinista sin necesidad de numpy.
        """
        # Semilla determinista a partir de la clave
        seed_bytes = _hmac.new(self._clave_bytes, b"nn_seed", hashlib.sha256).digest()
        seed_int = int.from_bytes(seed_bytes[:8], "big")
        rng = random.Random(seed_int)

        def xavier_matrix(fan_in, fan_out):
            limit = math.sqrt(6.0 / (fan_in + fan_out))
            return [[rng.uniform(-limit, limit) for _ in range(fan_in)]
                    for _ in range(fan_out)]

        def zero_bias(n):
            return [0.0] * n

        # Dimensiones: 6 → 8 → 4 → 1
        return {
            "W1": xavier_matrix(6, 8),   # (8×6)
            "b1": zero_bias(8),
            "W2": xavier_matrix(8, 4),   # (4×8)
            "b2": zero_bias(4),
            "W3": xavier_matrix(4, 1),   # (1×4)
            "b3": zero_bias(1),
        }

    def _forward_nn(self, vector_amenaza: list) -> float:
        """
        Propagación hacia adelante del MLP.

        Arquitectura:
            capa1: ReLU(W1·x + b1)
            capa2: ReLU(W2·h1 + b2)
            salida: Sigmoid(W3·h2 + b3)

        Parámetros
        ----------
        vector_amenaza : list[float]
            Vector de 6 características en [0, 1]:
            [tasa_anomalia, entropia_norm, intentos_fallidos_norm,
             actividad_red_norm, cambios_modulo_norm, tiempo_sesion_norm]

        Retorna
        -------
        float : probabilidad de amenaza en [0, 1]
        """
        if len(vector_amenaza) != 6:
            raise ValueError("El vector de amenaza debe tener exactamente 6 características.")

        nn = self._pesos_nn
        # Capa 1
        z1 = _add_bias(_mat_vec(nn["W1"], vector_amenaza), nn["b1"])
        h1 = _relu(z1)
        # Capa 2
        z2 = _add_bias(_mat_vec(nn["W2"], h1), nn["b2"])
        h2 = _relu(z2)
        # Capa de salida
        z3 = _add_bias(_mat_vec(nn["W3"], h2), nn["b3"])
        prob = _sigmoid(z3[0])
        return prob

    def clasificar_amenaza(self, vector_amenaza: list) -> dict:
        """
        Clasifica un vector de amenaza usando la red neuronal.

        Retorna un dict con:
            - "probabilidad": float en [0,1]
            - "clasificacion": "SEGURO" | "AMENAZA"
            - "confianza": float en [0,1]
        """
        prob = self._forward_nn(vector_amenaza)
        self.actualizar_ewma(prob)
        cusum = self.actualizar_cusum(prob)
        mahal = self.detectar_anomalia_mahalanobis(vector_amenaza)

        # Fusión de detectores: la red neuronal y la distancia al baseline
        # votan con el máximo (OR), de modo que un vector claramente fuera
        # de distribución no pase desapercibido aunque el MLP lo subestime.
        fusion = prob
        if mahal["suficiente"]:
            fusion = max(prob, float(mahal["probabilidad"]))
        clasificacion = "AMENAZA" if fusion >= 0.5 else "SEGURO"
        confianza = fusion if fusion >= 0.5 else (1.0 - fusion)

        self._registrar_log("NN", f"Vector clasificado como {clasificacion} (p={fusion:.4f})")
        return {
            "probabilidad": fusion,
            "probabilidad_mlp": prob,
            "clasificacion": clasificacion,
            "confianza": confianza,
            "mahalanobis": mahal,
            "cusum": cusum,
            "ewma": round(self._ewma_riesgo, 4),
        }

    # ------------------------------------------------------------------
    # 3. ENTROPÍA DE SHANNON
    # ------------------------------------------------------------------

    def registrar_evento(self, tipo_evento: str):
        """
        Registra un evento en el historial y recalcula la entropía.

        Parámetros
        ----------
        tipo_evento : str
            Etiqueta del evento (p.ej. "LOGIN_OK", "LOGIN_FAIL", "ACCESO_MODULO").
        """
        self._historial_eventos.append(tipo_evento)
        self._entropia_actual = self._calcular_entropia_shannon(list(self._historial_eventos))

    def _calcular_entropia_shannon(self, eventos: list) -> float:
        """
        Calcula la entropía de Shannon H = -Σ p_i · log2(p_i)
        sobre la distribución de tipos de evento.

        Una entropía alta indica diversidad (posible exploración aleatoria
        o ataque de enumeración); una entropía muy baja indica repetición
        (posible bucle de fuerza bruta en un punto específico).

        Parámetros
        ----------
        eventos : list[str]
            Secuencia de tipos de evento.

        Retorna
        -------
        float : entropía en bits (0 si lista vacía)
        """
        if not eventos:
            return 0.0

        conteo = Counter(eventos)
        total = len(eventos)
        H = 0.0
        for count in conteo.values():
            p_i = count / total
            # Evitar log(0)
            if p_i > 0:
                H -= p_i * math.log2(p_i)
        return H

    def detectar_anomalia_entropia(self, umbral_bajo: float = 0.3,
                                    umbral_alto: float = 3.5) -> dict:
        """
        Detecta anomalías basadas en la entropía actual.

        - Entropía < umbral_bajo → repetición sospechosa (fuerza bruta)
        - Entropía > umbral_alto → diversidad excesiva (escaneo / fuzzing)

        Retorna
        -------
        dict con "entropia", "estado_entropia", "alerta"
        """
        H = self._entropia_actual
        if len(self._historial_eventos) < 5:
            estado = "insuficiente_datos"
            alerta = False
        elif H < umbral_bajo:
            estado = "repeticion_sospechosa"
            alerta = True
        elif H > umbral_alto:
            estado = "diversidad_anomala"
            alerta = True
        else:
            estado = "normal"
            alerta = False

        if alerta:
            self._registrar_log("ENTROPIA", f"Anomalía detectada: {estado} H={H:.4f}")
        return {"entropia": H, "estado_entropia": estado, "alerta": alerta}

    # ------------------------------------------------------------------
    # 4. UMBRAL ADAPTATIVO BAYESIANO
    # ------------------------------------------------------------------

    def actualizar_bayesiano(self, evidencia_presente: bool) -> float:
        """
        Actualiza la probabilidad posterior de amenaza con el Teorema de Bayes.

        Fórmula:
            P(A|B) = P(B|A) · P(A) / P(B)

        donde:
            P(B) = P(B|A)·P(A) + P(B|¬A)·(1-P(A))

        Parámetros
        ----------
        evidencia_presente : bool
            True si se observó evidencia de amenaza en este ciclo.

        Retorna
        -------
        float : nueva probabilidad posterior P(A|B)
        """
        P_A  = self._prob_amenaza_posterior         # Prior (actualizado en cada paso)
        P_BA = self._prob_evidencia_dado_amenaza if evidencia_presente \
               else (1.0 - self._prob_evidencia_dado_amenaza)
        P_Bn = self._prob_evidencia_dado_seguro if evidencia_presente \
               else (1.0 - self._prob_evidencia_dado_seguro)

        # Probabilidad marginal de la evidencia: ley de la probabilidad total
        P_B = P_BA * P_A + P_Bn * (1.0 - P_A)

        if P_B == 0.0:
            # Caso degenerado: no se actualiza
            return self._prob_amenaza_posterior

        # Actualización bayesiana
        P_AB = (P_BA * P_A) / P_B
        self._prob_amenaza_posterior = P_AB

        self._registrar_log(
            "BAYES",
            f"P(amenaza) actualizada: {P_A:.4f} → {P_AB:.4f} "
            f"(evidencia={'SÍ' if evidencia_presente else 'NO'})"
        )
        return P_AB

    def obtener_probabilidad_amenaza(self) -> float:
        """Retorna la probabilidad actual de amenaza según el modelo bayesiano."""
        return self._prob_amenaza_posterior

    # ------------------------------------------------------------------
    # 5. HASH DE INTEGRIDAD SHA-256
    # ------------------------------------------------------------------

    def sellar_modulo(self, nombre_modulo: str, contenido: str) -> str:
        """
        Calcula y almacena el hash SHA-256 del contenido de un módulo.

        El hash actúa como sello de integridad: cualquier modificación
        posterior del módulo producirá un hash diferente.

        Parámetros
        ----------
        nombre_modulo : str
            Identificador del módulo (p.ej. "CerebroInternoLucia").
        contenido : str
            Contenido textual o serialización del módulo.

        Retorna
        -------
        str : hash hexadecimal SHA-256
        """
        digest = hashlib.sha256(contenido.encode("utf-8")).hexdigest()
        self._hashes_modulos[nombre_modulo] = {
            "hash": digest,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._registrar_log("SHA256", f"Módulo '{nombre_modulo}' sellado: {digest[:16]}…")
        return digest

    def verificar_integridad(self, nombre_modulo: str, contenido_actual: str) -> dict:
        """
        Verifica que el contenido actual de un módulo coincide con su sello.

        Parámetros
        ----------
        nombre_modulo : str
            Módulo a verificar.
        contenido_actual : str
            Contenido actual del módulo.

        Retorna
        -------
        dict con "integro": bool, "hash_esperado": str, "hash_actual": str
        """
        if nombre_modulo not in self._hashes_modulos:
            return {"integro": False, "error": "Módulo no registrado"}

        hash_esperado = self._hashes_modulos[nombre_modulo]["hash"]
        hash_actual = hashlib.sha256(contenido_actual.encode("utf-8")).hexdigest()
        integro = hash_esperado == hash_actual

        if not integro:
            self._registrar_log("SHA256", f"¡VIOLACIÓN DE INTEGRIDAD en '{nombre_modulo}'!")
            # Penalizar nivel de seguridad
            self.nivel_seguridad = max(0.0, self.nivel_seguridad - 20.0)
            self.evaluar_seguridad()

        return {
            "integro": integro,
            "hash_esperado": hash_esperado,
            "hash_actual": hash_actual,
        }

    # ------------------------------------------------------------------
    # 6. FIRMA HMAC
    # ------------------------------------------------------------------

    def firmar_mensaje(self, mensaje: str) -> str:
        """
        Genera una firma HMAC-SHA256 para autenticar un mensaje entre módulos.

        HMAC(K, m) = H((K ⊕ opad) || H((K ⊕ ipad) || m))

        Parámetros
        ----------
        mensaje : str
            Mensaje a firmar.

        Retorna
        -------
        str : firma hexadecimal HMAC-SHA256
        """
        firma = _hmac.new(
            self._clave_bytes,
            mensaje.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        self._registrar_log("HMAC", f"Mensaje firmado (firma={firma[:16]}…)")
        return firma

    def verificar_firma(self, mensaje: str, firma_recibida: str) -> bool:
        """
        Verifica la autenticidad de un mensaje mediante su firma HMAC.

        Usa comparación en tiempo constante para evitar ataques de timing.

        Parámetros
        ----------
        mensaje : str
            Mensaje cuya firma se verifica.
        firma_recibida : str
            Firma hexadecimal recibida junto al mensaje.

        Retorna
        -------
        bool : True si la firma es válida
        """
        firma_esperada = _hmac.new(
            self._clave_bytes,
            mensaje.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Comparación en tiempo constante (hmac.compare_digest previene timing attacks)
        valida = _hmac.compare_digest(firma_esperada, firma_recibida)
        self._registrar_log("HMAC", f"Verificación de firma: {'VÁLIDA' if valida else 'INVÁLIDA'}")
        return valida

    # ------------------------------------------------------------------
    # 7. SISTEMA DE CUARENTENA
    # ------------------------------------------------------------------

    def calcular_riesgo_exponencial(self, num_incidentes: int,
                                    tasa_base: float = 0.15) -> float:
        """
        Calcula una puntuación de riesgo exponencial:

            riesgo(n) = 1 - e^(-tasa_base · n)

        La función crece rápidamente con los incidentes y satura en 1.0,
        lo que modela el hecho de que múltiples incidentes escalan
        el peligro de forma no lineal.

        Parámetros
        ----------
        num_incidentes : int
            Número de incidentes registrados para el módulo.
        tasa_base : float
            Tasa de decaimiento (default 0.15).

        Retorna
        -------
        float : puntuación de riesgo en [0, 1)
        """
        return 1.0 - math.exp(-tasa_base * num_incidentes)

    def poner_en_cuarentena(self, nombre_modulo: str, num_incidentes: int,
                             razon: str = "") -> dict:
        """
        Evalúa si un módulo debe ir a cuarentena y lo aísla si supera el umbral.

        Parámetros
        ----------
        nombre_modulo : str
            Módulo a evaluar.
        num_incidentes : int
            Incidentes acumulados para ese módulo.
        razon : str
            Descripción de la causa.

        Retorna
        -------
        dict con "en_cuarentena": bool, "riesgo": float, "mensaje": str
        """
        riesgo = self.calcular_riesgo_exponencial(num_incidentes)
        en_cuarentena = riesgo >= self._umbral_cuarentena

        if en_cuarentena:
            self._cuarentena[nombre_modulo] = {
                "riesgo": riesgo,
                "timestamp": time.time(),
                "razon": razon or "umbral de riesgo superado",
            }
            self._registrar_log(
                "CUARENTENA",
                f"Módulo '{nombre_modulo}' AISLADO. Riesgo={riesgo:.4f} Incidentes={num_incidentes}"
            )
            self.nivel_seguridad = max(0.0, self.nivel_seguridad - riesgo * 30)
            self.evaluar_seguridad()
            mensaje = (f"⚠️ MÓDULO '{nombre_modulo}' EN CUARENTENA "
                       f"(riesgo={riesgo:.2%}, incidentes={num_incidentes})")
        else:
            mensaje = (f"Módulo '{nombre_modulo}' en observación "
                       f"(riesgo={riesgo:.2%}, incidentes={num_incidentes})")

        return {"en_cuarentena": en_cuarentena, "riesgo": riesgo, "mensaje": mensaje}

    def liberar_cuarentena(self, nombre_modulo: str) -> bool:
        """Libera un módulo de la cuarentena si está en ella."""
        if nombre_modulo in self._cuarentena:
            del self._cuarentena[nombre_modulo]
            self._registrar_log("CUARENTENA", f"Módulo '{nombre_modulo}' liberado de cuarentena.")
            return True
        return False

    def listar_cuarentena(self) -> dict:
        """Retorna el diccionario de módulos en cuarentena."""
        return dict(self._cuarentena)

    # ------------------------------------------------------------------
    # 7b. REFUERZO MATEMÁTICO (ampliación de la clase)
    # ------------------------------------------------------------------

    def derivar_clave(self, info: str, sal: bytes = b"", longitud: int = 32) -> bytes:
        """
        Deriva una subclave con HKDF-SHA256 (RFC 5869).

        Cada módulo recibe su propia clave, de modo que comprometer un módulo
        no permite forjar mensajes de otro (separación de claves).

        Parámetros
        ----------
        info : str
            Etiqueta de contexto (p. ej. el nombre del módulo).
        sal : bytes
            Sal opcional; si falta se usa una sal nula de 32 bytes.
        longitud : int
            Bytes de clave a derivar (máximo 255·32).

        Retorna
        -------
        bytes : clave derivada
        """
        if longitud < 1 or longitud > 255 * 32:
            raise ValueError("Longitud HKDF fuera de rango (1..8160 bytes).")
        prk = _hmac.new(sal or b"\x00" * 32, self._clave_bytes, hashlib.sha256).digest()
        okm = b""
        bloque = b""
        contador = 1
        while len(okm) < longitud:
            bloque = _hmac.new(
                prk,
                bloque + info.encode("utf-8") + bytes([contador]),
                hashlib.sha256,
            ).digest()
            okm += bloque
            contador += 1
        return okm[:longitud]

    def firmar_con_clave_modulo(self, nombre_modulo: str, mensaje: str) -> str:
        """Firma un mensaje con la subclave HKDF exclusiva de ese módulo."""
        clave = self.derivar_clave("modulo:" + nombre_modulo)
        return _hmac.new(clave, mensaje.encode("utf-8"), hashlib.sha256).hexdigest()

    def verificar_firma_modulo(self, nombre_modulo: str, mensaje: str,
                               firma_recibida: str) -> bool:
        """Verifica una firma usando solo la subclave del módulo indicado."""
        esperada = self.firmar_con_clave_modulo(nombre_modulo, mensaje)
        return _hmac.compare_digest(esperada, firma_recibida)

    def firmar_mensaje_con_nonce(self, mensaje: str, ttl: float = 0.0) -> dict:
        """
        Envuelve un mensaje en un sobre firmado con nonce aleatorio y caducidad.

        El nonce de 128 bits impide que dos mensajes idénticos compartan firma;
        el instante y el TTL permiten rechazar sobres viejos o reinyectados.
        """
        ttl = ttl or self._ttl_nonce
        nonce = os.urandom(16).hex()
        instante = time.time()
        cuerpo = f"{nonce}|{instante:.6f}|{mensaje}"
        firma = _hmac.new(
            self._clave_bytes, cuerpo.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return {
            "mensaje": mensaje,
            "nonce": nonce,
            "instante": instante,
            "ttl": ttl,
            "firma": firma,
        }

    def _purgar_nonces(self, ahora: float) -> None:
        """Elimina nonces caducados para que el registro no crezca sin límite."""
        caducados = [n for n, expira in self._nonces_vistos.items() if expira <= ahora]
        for nonce in caducados:
            del self._nonces_vistos[nonce]

    def verificar_mensaje_con_nonce(self, sobre: dict, ttl: float = 0.0) -> dict:
        """
        Verifica firma, ventana temporal y unicidad del nonce (anti-replay).

        Retorna dict con "valida" y "motivo" ("ok", "firma", "caducado",
        "repetido", "formato").
        """
        try:
            mensaje = str(sobre["mensaje"])
            nonce = str(sobre["nonce"])
            instante = float(sobre["instante"])
            firma = str(sobre["firma"])
        except (KeyError, TypeError, ValueError):
            return {"valida": False, "motivo": "formato"}

        esperada = _hmac.new(
            self._clave_bytes,
            f"{nonce}|{instante:.6f}|{mensaje}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not _hmac.compare_digest(esperada, firma):
            return {"valida": False, "motivo": "firma"}

        ttl = ttl or float(sobre.get("ttl", self._ttl_nonce))
        ahora = time.time()
        if abs(ahora - instante) > ttl:
            return {"valida": False, "motivo": "caducado"}

        with self._cerrojo:
            self._purgar_nonces(ahora)
            if nonce in self._nonces_vistos:
                return {"valida": False, "motivo": "repetido"}
            self._nonces_vistos[nonce] = instante + ttl

        self._registrar_log("ANTI_REPLAY", "Sobre con nonce aceptado una sola vez.")
        return {"valida": True, "motivo": "ok"}

    def consumir_permiso(self, clave: str, capacidad: float = 5.0,
                         recarga_por_s: float = 1.0, costo: float = 1.0) -> dict:
        """
        Limitador de tasa por cubo de fichas (token bucket).

        Las fichas se recargan de forma continua a ``recarga_por_s`` por
        segundo hasta ``capacidad``. Una ráfaga agota el cubo y las peticiones
        siguientes se rechazan hasta que se recupere al menos ``costo``.
        """
        ahora = time.time()
        with self._cerrojo:
            fichas, ultimo = self._cubos.get(clave, (capacidad, ahora))
            fichas = min(capacidad, fichas + (ahora - ultimo) * recarga_por_s)
            permitido = fichas >= costo
            if permitido:
                fichas -= costo
            self._cubos[clave] = (fichas, ahora)
        if not permitido:
            self._registrar_log("RATE_LIMIT", f"Ráfaga bloqueada para '{clave}'.")
        return {
            "permitido": permitido,
            "fichas": round(fichas, 3),
            "capacidad": capacidad,
        }

    def calibrar_baseline(self, vector: list) -> int:
        """
        Alimenta la media y la varianza del baseline con una muestra confiable.

        Usa el algoritmo de Welford (actualización numéricamente estable):
            media ← media + (x − media)/n
            M2    ← M2 + (x − media_vieja)·(x − media_nueva)

        Retorna el número de muestras acumuladas.
        """
        if len(vector) != 6:
            raise ValueError("El vector de amenaza debe tener 6 características.")
        self._baseline_n += 1
        n = self._baseline_n
        for i, valor in enumerate(vector):
            delta = float(valor) - self._baseline_media[i]
            self._baseline_media[i] += delta / n
            self._baseline_m2[i] += delta * (float(valor) - self._baseline_media[i])
        return self._baseline_n

    def _varianzas_baseline(self) -> list:
        """Varianza insesgada por característica con suelo para evitar división por 0."""
        if self._baseline_n < 2:
            return [1.0] * 6
        return [max(m2 / (self._baseline_n - 1), 1e-4) for m2 in self._baseline_m2]

    def distancia_mahalanobis(self, vector: list) -> float:
        """
        Distancia de Mahalanobis con covarianza diagonal:

            d(x) = sqrt( Σ ((x_i − μ_i)² / σ_i²) )

        Es la métrica natural para detectar un vector que se aleja del
        comportamiento aprendido, corrigiendo la escala de cada característica.
        """
        if len(vector) != 6:
            raise ValueError("El vector de amenaza debe tener 6 características.")
        if self._baseline_n < 2:
            return 0.0
        varianzas = self._varianzas_baseline()
        suma = 0.0
        for i, valor in enumerate(vector):
            suma += ((float(valor) - self._baseline_media[i]) ** 2) / varianzas[i]
        return math.sqrt(suma)

    def detectar_anomalia_mahalanobis(self, vector: list,
                                      minimo_muestras: int = 8) -> dict:
        """
        Convierte la distancia de Mahalanobis en probabilidad de anomalía.

        Con 6 dimensiones, d² sigue aproximadamente una chi-cuadrado con 6
        grados de libertad; se usa P = 1 − exp(−d²/(2·6)) como aproximación
        monótona y acotada en [0, 1).
        """
        if self._baseline_n < minimo_muestras:
            return {"suficiente": False, "distancia": 0.0, "probabilidad": 0.0}
        d = self.distancia_mahalanobis(vector)
        probabilidad = 1.0 - math.exp(-(d * d) / 12.0)
        self._ultima_p_mahalanobis = probabilidad
        if probabilidad >= 0.95:
            self._registrar_log(
                "MAHALANOBIS",
                f"Vector fuera de baseline: d={d:.3f}, P(anomalía)={probabilidad:.3f}",
            )
        return {
            "suficiente": True,
            "distancia": round(d, 4),
            "probabilidad": round(probabilidad, 4),
        }

    def actualizar_ewma(self, valor: float, alpha: float = 0.2) -> float:
        """Media móvil exponencial: EWMA ← α·x + (1−α)·EWMA."""
        alpha = max(0.0, min(1.0, alpha))
        self._ewma_riesgo = alpha * float(valor) + (1.0 - alpha) * self._ewma_riesgo
        return self._ewma_riesgo

    def actualizar_cusum(self, valor: float) -> dict:
        """
        CUSUM unilateral para detectar deriva sostenida al alza:

            S⁺ ← max(0, S⁺ + x − μ₀ − k)

        donde μ₀ es el objetivo y k la tolerancia. Se alerta cuando S⁺
        supera h. A diferencia de un umbral fijo, el CUSUM acumula evidencias
        pequeñas y detecta un ataque lento que nunca dispara un pico aislado.
        """
        x = max(0.0, min(1.0, float(valor)))
        self._cusum_pos = max(
            0.0, self._cusum_pos + x - self._cusum_objetivo - self._cusum_deriva
        )
        alerta = self._cusum_pos > self._cusum_umbral
        if alerta:
            self._registrar_log(
                "CUSUM",
                f"Deriva sostenida detectada: S⁺={self._cusum_pos:.3f} "
                f"(h={self._cusum_umbral}).",
            )
        return {
            "cusum": round(self._cusum_pos, 4),
            "alerta": alerta,
            "estado": "deriva" if alerta else "estable",
        }

    def entrenar_online(self, vector: list, etiqueta: float,
                        tasa: float = 0.05) -> dict:
        """
        Un paso de retropropagación sobre el MLP 6-8-4-1.

        Pérdida: entropía cruzada binaria. Los gradientes se recortan a
        [−1, 1] y los pesos se mantienen en [−8, 8] para que una muestra
        atípica no desestabilice la red (defensa contra envenenamiento).
        """
        if len(vector) != 6:
            raise ValueError("El vector de amenaza debe tener 6 características.")
        y = 1.0 if etiqueta >= 0.5 else 0.0
        nn = self._pesos_nn

        z1 = _add_bias(_mat_vec(nn["W1"], vector), nn["b1"])
        h1 = _relu(z1)
        z2 = _add_bias(_mat_vec(nn["W2"], h1), nn["b2"])
        h2 = _relu(z2)
        z3 = _add_bias(_mat_vec(nn["W3"], h2), nn["b3"])
        p = _sigmoid(z3[0])

        def recortar(v: float) -> float:
            return max(-1.0, min(1.0, v))

        def limitar(v: float) -> float:
            return max(-8.0, min(8.0, v))

        eps = 1e-9
        perdida = -(y * math.log(p + eps) + (1.0 - y) * math.log(1.0 - p + eps))

        d3 = p - y
        grad_w3 = [[recortar(d3 * h2[j]) for j in range(4)]]
        grad_b3 = [recortar(d3)]
        d2 = [recortar(nn["W3"][0][j] * d3) if z2[j] > 0.0 else 0.0 for j in range(4)]
        grad_w2 = [[recortar(d2[i] * h1[j]) for j in range(8)] for i in range(4)]
        grad_b2 = [recortar(v) for v in d2]
        d1 = []
        for j in range(8):
            suma = sum(nn["W2"][i][j] * d2[i] for i in range(4))
            d1.append(recortar(suma) if z1[j] > 0.0 else 0.0)
        grad_w1 = [[recortar(d1[i] * vector[j]) for j in range(6)] for i in range(8)]
        grad_b1 = [recortar(v) for v in d1]

        lr = max(0.0, min(0.5, float(tasa)))
        for i in range(8):
            for j in range(6):
                nn["W1"][i][j] = limitar(nn["W1"][i][j] - lr * grad_w1[i][j])
            nn["b1"][i] = limitar(nn["b1"][i] - lr * grad_b1[i])
        for i in range(4):
            for j in range(8):
                nn["W2"][i][j] = limitar(nn["W2"][i][j] - lr * grad_w2[i][j])
            nn["b2"][i] = limitar(nn["b2"][i] - lr * grad_b2[i])
        for j in range(4):
            nn["W3"][0][j] = limitar(nn["W3"][0][j] - lr * grad_w3[0][j])
        nn["b3"][0] = limitar(nn["b3"][0] - lr * grad_b3[0])

        return {
            "entrenado": True,
            "perdida": round(perdida, 6),
            "probabilidad_previa": round(p, 4),
            "etiqueta": y,
        }

    # ------------------------------------------------------------------
    # 8. MÉTODOS ORIGINALES (expandidos con lógica matemática real)
    # ------------------------------------------------------------------

    def evaluar_seguridad(self):
        """
        Evalúa el estado de seguridad del sistema usando múltiples métricas:
          - nivel_seguridad (0-100)
          - probabilidad bayesiana de amenaza
          - número de módulos en cuarentena
          - anomalías de entropía

        El estado resultante es:
          "activo"      → sistema operando con normalidad
          "alerta"      → indicadores elevados, monitoreo intensivo
          "vulnerable"  → degradación significativa, respuesta requerida
          "crítico"     → sistema comprometido, acción inmediata
        """
        # Factor combinado: 0 = perfecto, 1 = comprometido
        factor_nivel    = 1.0 - (self.nivel_seguridad / 100.0)
        factor_bayes    = self._prob_amenaza_posterior
        factor_cuarente = min(1.0, len(self._cuarentena) / 5.0)
        anomalia_H      = self.detectar_anomalia_entropia()["alerta"]
        factor_entropia = 0.3 if anomalia_H else 0.0
        factor_mahal    = self._ultima_p_mahalanobis
        factor_cusum    = min(1.0, self._cusum_pos / self._cusum_umbral)

        # Ponderación: nivel 40%, bayes 15%, cuarentena 10%, entropía 5%,
        # Mahalanobis 15%, CUSUM 15%. Suma exactamente 1.0.
        riesgo_global = (
            0.40 * factor_nivel +
            0.15 * factor_bayes +
            0.10 * factor_cuarente +
            0.05 * factor_entropia +
            0.15 * factor_mahal +
            0.15 * factor_cusum
        )

        if riesgo_global < 0.20:
            self.estado_seguridad = "activo"
        elif riesgo_global < 0.45:
            self.estado_seguridad = "alerta"
        elif riesgo_global < 0.70:
            self.estado_seguridad = "vulnerable"
        else:
            self.estado_seguridad = "crítico"

        return self.estado_seguridad

    def actualizar_nivel_seguridad(self, cambio: float,
                                    evento: str = "evento_externo"):
        """
        Actualiza el nivel de seguridad (clampado a [0, 100]) y registra el evento.

        Parámetros
        ----------
        cambio : float
            Variación del nivel (negativa = degradación, positiva = mejora).
        evento : str
            Tipo de evento que provoca el cambio.
        """
        self.nivel_seguridad = max(0.0, min(100.0, self.nivel_seguridad + cambio))
        self.registrar_evento(evento)
        self.evaluar_seguridad()
        self._registrar_log(
            "NIVEL",
            f"Nivel de seguridad → {self.nivel_seguridad:.1f} (cambio={cambio:+.1f}, evento={evento})"
        )

    def obtener_estado(self) -> dict:
        """
        Retorna un snapshot completo del estado de seguridad del sistema.

        Retorna
        -------
        dict con todas las métricas activas.
        """
        self.evaluar_seguridad()
        return {
            "estado_seguridad":       self.estado_seguridad,
            "nivel_seguridad":        round(self.nivel_seguridad, 2),
            "entropia_shannon":       round(self._entropia_actual, 4),
            "prob_amenaza_bayesiana": round(self._prob_amenaza_posterior, 4),
            "ewma_riesgo":            round(self._ewma_riesgo, 4),
            "cusum":                  round(self._cusum_pos, 4),
            "mahalanobis_prob":       round(self._ultima_p_mahalanobis, 4),
            "baseline_muestras":      self._baseline_n,
            "nonces_activos":         len(self._nonces_vistos),
            "modulos_sellados":       list(self._hashes_modulos.keys()),
            "modulos_en_cuarentena":  list(self._cuarentena.keys()),
            "total_eventos":          len(self._historial_eventos),
            "timestamp":              datetime.utcnow().isoformat(),
            "numpy_disponible":       _NUMPY,
        }

    # ------------------------------------------------------------------
    # 9. VOZ DE LUCIA
    # ------------------------------------------------------------------

    def narrar_estado(self) -> str:
        """
        Genera una narración en español del estado actual del sistema
        para ser leída en voz alta por el avatar 3D de LucIA.

        Retorna
        -------
        str : narración completa lista para TTS.
        """
        estado = self.obtener_estado()
        frases = {
            "activo":     "Mi sistema de seguridad funciona con total normalidad. Estoy protegida.",
            "alerta":     "Detecto señales que requieren mi atención. Incrementando la vigilancia.",
            "vulnerable": "Mi integridad está comprometida parcialmente. Iniciando protocolos de defensa.",
            "crítico":    "¡Alerta máxima! Mi núcleo neuronal está bajo amenaza. Activando cuarentena de emergencia.",
        }
        narracion = (
            f"Soy LucIA. {frases.get(estado['estado_seguridad'], 'Estado desconocido.')} "
            f"Mi nivel de seguridad es de {estado['nivel_seguridad']} sobre cien. "
            f"La entropía de los eventos actuales es {estado['entropia_shannon']:.2f} bits. "
            f"La probabilidad bayesiana de amenaza es del {estado['prob_amenaza_bayesiana']*100:.1f} por ciento. "
        )
        if estado["modulos_en_cuarentena"]:
            narracion += (
                f"Tengo {len(estado['modulos_en_cuarentena'])} módulo(s) en cuarentena: "
                f"{', '.join(estado['modulos_en_cuarentena'])}. "
            )
        else:
            narracion += "No hay módulos en cuarentena. "
        if estado["cusum"] > self._cusum_umbral:
            narracion += (
                "Mi control de deriva CUSUM detecta una acumulación anómala de "
                "señales: el riesgo no viene de un pico aislado, sino de una "
                "tendencia sostenida. "
            )
        narracion += f"Llevo {len(estado['modulos_sellados'])} módulo(s) con sello de integridad registrado."
        return narracion

    def lucia_voz_seguridad(self) -> dict:
        """
        Retorna un diccionario con las frases que LucIA diría en voz alta
        para explicar cada subsistema de seguridad.

        Formato: {"subsistema": "frase en español para TTS"}
        """
        return {
            "entropia": (
                "Estoy analizando la entropía de Shannon de los eventos para detectar "
                "patrones anómalos. Una entropía demasiado baja me indica que alguien "
                "repite la misma acción, como un ataque de fuerza bruta. Una entropía "
                "demasiado alta me alerta de un barrido o exploración masiva del sistema."
            ),
            "red_neuronal": (
                "Mi red neuronal de detección de amenazas evalúa seis características del "
                "entorno y las procesa en dos capas ocultas con activación ReLU. La capa "
                "de salida utiliza una función sigmoide para darme una probabilidad de "
                "amenaza entre cero y uno. Si supera el cincuenta por ciento, activo mis "
                "defensas automáticamente."
            ),
            "bayes": (
                "Aplico el teorema de Bayes para actualizar en tiempo real mi creencia "
                "sobre la probabilidad de estar bajo ataque. Cada nueva evidencia modifica "
                "mi estimación anterior de forma matemáticamente rigurosa, combinando lo que "
                "ya sabía con lo que acabo de observar."
            ),
            "sha256": (
                "Genero un sello criptográfico SHA-256 para cada módulo de mi cerebro interno. "
                "Si alguien modifica un módulo, el hash cambiará y yo lo detectaré al instante, "
                "como una huella digital inalterable que protege mi integridad."
            ),
            "hmac": (
                "Firmo todos los mensajes entre mis módulos internos con HMAC-SHA256. "
                "Esto garantiza que nadie puede falsificar una instrucción y hacerse pasar "
                "por una parte legítima de mi sistema. La clave maestra es solo mía."
            ),
            "cuarentena": (
                "Cuando un módulo acumula incidentes, calculo su riesgo con una función "
                "exponencial creciente. Si supera el umbral de setenta y cinco por ciento, "
                "lo aíslo en cuarentena para que no contamine el resto de mi cerebro, "
                "igual que el sistema inmunitario aísla un agente patógeno."
            ),
            "nivel_seguridad": (
                "Mantengo un nivel de seguridad global entre cero y cien. Los eventos negativos "
                "lo reducen y las acciones correctivas lo restauran. Combino este valor con las "
                "métricas bayesianas, de entropía y de cuarentena para determinar mi estado "
                "general: activo, alerta, vulnerable o crítico."
            ),
            "mahalanobis": (
                "Comparo cada vector de amenaza con mi huella de comportamiento normal usando "
                "la distancia de Mahalanobis. Esta métrica corrige la escala de cada variable y "
                "me dice cuántas desviaciones me alejo de mi baseline. Si la distancia crece, "
                "la probabilidad de anomalía sube automáticamente."
            ),
            "cusum": (
                "Aplico un control estadístico CUSUM que acumula desviaciones pequeñas. Así "
                "detecto un ataque lento que nunca produce un pico único: si la suma de señales "
                "supera mi umbral, sé que la amenaza es sostenida y no ruido."
            ),
            "anti_replay": (
                "Cada mensaje que sale de mí lleva un nonce aleatorio de ciento veintiocho bits "
                "y una fecha de caducidad. Si alguien captura un mensaje y lo reenvía, el nonce "
                "ya estará usado y la firma será rechazada. Es mi defensa contra la repetición."
            ),
            "limitador": (
                "Mis cubos de fichas limitan cuántas peticiones admite cada canal. Una ráfaga "
                "agota el cubo y las siguientes peticiones esperan a que se recargue, igual que "
                "una presa regula el caudal de un río."
            ),
        }

    # ------------------------------------------------------------------
    # 10. UTILIDADES INTERNAS
    # ------------------------------------------------------------------

    def _registrar_log(self, categoria: str, mensaje: str):
        """Registra una entrada de auditoría interna con timestamp."""
        entrada = {
            "timestamp": datetime.utcnow().isoformat(),
            "categoria": categoria,
            "mensaje":   mensaje,
        }
        self._log.append(entrada)
        # Rotación del log
        if len(self._log) > self._log_max:
            self._log = self._log[-self._log_max:]

    def obtener_log(self, n_ultimos: int = 20) -> list:
        """Retorna las últimas n_ultimos entradas del log de auditoría."""
        return self._log[-n_ultimos:]

    def exportar_estado_json(self) -> str:
        """Serializa el estado completo a JSON (sin incluir pesos de la red ni clave)."""
        estado = self.obtener_estado()
        return json.dumps(estado, ensure_ascii=False, indent=2)


# ===========================================================================
# DEMOSTRACIÓN PRINCIPAL
# ===========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  LucIA — SeguridadNeuronal: Demostración matemática completa")
    print("=" * 70)

    seg = SeguridadNeuronal(clave_maestra="LucIA_MIT_ECO_2025")

    # --- 1. Registrar eventos y calcular entropía ---
    print("\n[1] ENTROPÍA DE SHANNON")
    eventos_simulados = (
        ["LOGIN_OK"] * 10 +
        ["LOGIN_FAIL"] * 5 +
        ["ACCESO_MODULO"] * 8 +
        ["ALERTA_FIREWALL"] * 3
    )
    for ev in eventos_simulados:
        seg.registrar_evento(ev)
    resultado_H = seg.detectar_anomalia_entropia()
    print(f"    H = {resultado_H['entropia']:.4f} bits | Estado: {resultado_H['estado_entropia']}")

    # --- 2. Red neuronal ---
    print("\n[2] RED NEURONAL — DETECCIÓN DE AMENAZAS")
    vectores = {
        "tráfico_normal":  [0.1, 0.4, 0.05, 0.2, 0.0, 0.3],
        "ataque_potencial":[0.9, 0.8, 0.95, 0.85, 0.7, 0.6],
        "caso_borde":      [0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
    }
    for nombre, vec in vectores.items():
        res = seg.clasificar_amenaza(vec)
        print(f"    {nombre:20s} → {res['clasificacion']:7s}  p={res['probabilidad']:.4f}  confianza={res['confianza']:.4f}")

    # --- 3. Bayesiano ---
    print("\n[3] UMBRAL ADAPTATIVO BAYESIANO")
    secuencia_evidencias = [True, True, False, True, False, False, True]
    for i, ev in enumerate(secuencia_evidencias):
        p = seg.actualizar_bayesiano(ev)
        print(f"    Paso {i+1}: evidencia={'SÍ' if ev else 'NO '} → P(amenaza)={p:.4f}")

    # --- 4. Hash SHA-256 ---
    print("\n[4] INTEGRIDAD SHA-256")
    contenido_original = '{"modulo": "CerebroInternoLucia", "version": "1.0"}'
    h = seg.sellar_modulo("CerebroInternoLucia", contenido_original)
    print(f"    Hash original  : {h[:32]}…")

    res_ok = seg.verificar_integridad("CerebroInternoLucia", contenido_original)
    print(f"    Verificación OK: {res_ok['integro']}")

    contenido_alterado = contenido_original.replace("1.0", "1.1_HACK")
    res_ko = seg.verificar_integridad("CerebroInternoLucia", contenido_alterado)
    print(f"    Verificación KO: {res_ko['integro']} (contenido alterado)")

    # --- 5. HMAC ---
    print("\n[5] FIRMA HMAC-SHA256")
    msg = "Lucia→Avatar3D: activar expresion_felicidad"
    firma = seg.firmar_mensaje(msg)
    print(f"    Firma          : {firma[:32]}…")
    print(f"    Verificación OK: {seg.verificar_firma(msg, firma)}")
    print(f"    Verificación KO: {seg.verificar_firma(msg + 'TAMPER', firma)}")

    # --- 6. Cuarentena ---
    print("\n[6] SISTEMA DE CUARENTENA (riesgo exponencial)")
    for n_inc in [1, 3, 7, 10, 15]:
        res_q = seg.poner_en_cuarentena("ModuloX", n_inc, f"prueba con {n_inc} incidentes")
        print(f"    Incidentes={n_inc:2d} → riesgo={res_q['riesgo']:.4f} | cuarentena={res_q['en_cuarentena']}")

    # --- 7. Estado general y narración ---
    print("\n[7] ESTADO GENERAL")
    seg.actualizar_nivel_seguridad(-30, "ATAQUE_DETECTADO")
    estado = seg.obtener_estado()
    print(f"    Estado: {estado['estado_seguridad']} | Nivel: {estado['nivel_seguridad']} | "
          f"P(amenaza): {estado['prob_amenaza_bayesiana']}")

    print("\n[8] VOZ DE LUCIA — narrar_estado()")
    print(f"    {seg.narrar_estado()}")

    print("\n[9] FRASES DE VOZ POR SUBSISTEMA")
    voces = seg.lucia_voz_seguridad()
    for clave, frase in voces.items():
        print(f"\n    [{clave.upper()}]")
        print(f"    {frase[:100]}…")

    # --- 10. HKDF, anti-replay y limitador ---
    print("\n[10] HKDF · ANTI-REPLAY · TOKEN BUCKET")
    k_avatar = seg.derivar_clave("modulo:avatar")
    print(f"    HKDF determinista: {k_avatar == seg.derivar_clave('modulo:avatar')} "
          f"| longitud={len(k_avatar) * 8} bits")
    print(f"    Claves separadas por módulo: "
          f"{k_avatar != seg.derivar_clave('modulo:cerebro')}")
    firma_mod = seg.firmar_con_clave_modulo("avatar", "mover_brazo")
    print(f"    Firma con clave de módulo válida: "
          f"{seg.verificar_firma_modulo('avatar', 'mover_brazo', firma_mod)}")
    sobre = seg.firmar_mensaje_con_nonce("activar_expresion_felicidad")
    print(f"    1er uso del sobre : {seg.verificar_mensaje_con_nonce(sobre)}")
    print(f"    Reenvío (replay)  : {seg.verificar_mensaje_con_nonce(sobre)}")
    rafaga = [seg.consumir_permiso("chat", capacidad=3, recarga_por_s=0.5)["permitido"]
              for _ in range(5)]
    print(f"    Ráfaga de 5 con capacidad 3: {rafaga}")

    # --- 11. Mahalanobis ---
    print("\n[11] DISTANCIA DE MAHALANOBIS")
    vector_normal = [0.1, 0.4, 0.05, 0.2, 0.0, 0.3]
    for _ in range(20):
        seg.calibrar_baseline(
            [v + random.uniform(-0.02, 0.02) for v in vector_normal]
        )
    r_normal = seg.detectar_anomalia_mahalanobis(vector_normal)
    r_anomalo = seg.detectar_anomalia_mahalanobis([0.95, 0.9, 0.9, 0.9, 0.8, 0.7])
    print(f"    Normal  → d={r_normal['distancia']:.3f} P={r_normal['probabilidad']:.4f}")
    print(f"    Anómalo → d={r_anomalo['distancia']:.3f} P={r_anomalo['probabilidad']:.4f}")

    # --- 12. EWMA + CUSUM ---
    print("\n[12] EWMA + CUSUM (deriva sostenida)")
    ewma = 0.0
    for _ in range(8):
        ewma = seg.actualizar_ewma(0.6)
    for _ in range(10):
        deriva = seg.actualizar_cusum(0.6)
    print(f"    EWMA tras 8 pasos a 0.6: {ewma:.4f}")
    print(f"    CUSUM S⁺={deriva['cusum']:.3f} → {deriva['estado']} (alerta={deriva['alerta']})")

    # --- 13. Aprendizaje online ---
    print("\n[13] APRENDIZAJE ONLINE DEL MLP")
    vector_ataque = [0.95, 0.9, 0.9, 0.9, 0.8, 0.7]
    antes = seg.clasificar_amenaza(vector_ataque)["probabilidad_mlp"]
    for _ in range(40):
        seg.entrenar_online(vector_ataque, 1.0, tasa=0.10)
    despues = seg.clasificar_amenaza(vector_ataque)["probabilidad_mlp"]
    print(f"    P(amenaza) MLP antes={antes:.4f} → después={despues:.4f}")

    print("\n" + "=" * 70)
    print("  Demostración completada. LucIA operativa y protegida.")
    print("=" * 70)
