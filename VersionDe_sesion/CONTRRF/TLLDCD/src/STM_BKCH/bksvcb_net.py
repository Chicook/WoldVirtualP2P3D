"""
Servidor HTTP y daemon BKSVCB con medidas de seguridad anti-creación de múltiples cuentas.
===============================================================================================
Endpoints implementados:
  - POST /alta-cuenta: Crea una cuenta nueva con validaciones anti-duplicación
  - POST /migrar-cuenta: Migra cuenta antigua al hash único
  - GET /descargar-cuenta-zip: Descarga el .zip con el hash único de cuenta

Medidas de seguridad:
  - Una cuenta por huella de máquina (UUID)
  - Una cuenta por ubicación física (ubicacion_hash)
  - Rate limiting por IP
  - Registro de intentos de creación
  - Validación de huella duplicada
"""
from __future__ import annotations
import atexit
import hashlib
import json
import logging
import threading
import time
from collections import defaultdict
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional, Tuple
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BKSVCB_HTTP")

__server_name__ = "CelebroBlockchainServer-BKSVCB-Seguro"

# ─── CONFIGURACIÓN DE SEGURIDAD ───────────────────────────────────────────────
MAX_CUENTAS_POR_HUELLA = 1  # Máximo 1 cuenta por UUID de máquina
MAX_CUENTAS_POR_UBICACION = 1  # Máximo 1 cuenta por ubicación física
RATE_LIMIT_REQUESTS = 10  # Máximo 10 requests por IP por minuto
RATE_LIMIT_WINDOW = 60  # Ventana de 60 segundos

# ─── REGISTRO DE RATE LIMITING ─────────────────────────────────────────────────
_rate_limit_store: Dict[str, list] = defaultdict(list)
_cuentas_por_huella: Dict[str, int] = defaultdict(int)
_cuentas_por_ubicacion: Dict[str, int] = defaultdict(int)
_registro_intentos: list = []
_lock = threading.Lock()


def _clase_blockchain():
    from STM_BKCH.BKSVCB import CelebroBlockchain
    return CelebroBlockchain


def _verificar_rate_limit(ip: str) -> bool:
    """Verifica si la IP ha excedido el límite de requests."""
    with _lock:
        ahora = time.time()
        # Limpiar requests antiguos fuera de la ventana
        _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if ahora - t < RATE_LIMIT_WINDOW]
        if len(_rate_limit_store[ip]) >= RATE_LIMIT_REQUESTS:
            logger.warning(f"Rate limit excedido para IP: {ip}")
            return False
        _rate_limit_store[ip].append(ahora)
        return True


def _registrar_intento(tipo: str, ip: str, huella: str, exito: bool, motivo: str = "") -> None:
    """Registra intentos de creación de cuenta para auditoría."""
    with _lock:
        _registro_intentos.append({
            "timestamp": time.time(),
            "tipo": tipo,
            "ip": ip,
            "huella": huella[:16] + "..." if len(huella) > 16 else huella,
            "exito": exito,
            "motivo": motivo
        })
        # Mantener solo los últimos 1000 intentos
        if len(_registro_intentos) > 1000:
            _registro_intentos.pop(0)


def _validar_huella_no_duplicada(huella: str, ip: str) -> Tuple[bool, str]:
    """Valida que no exista una cuenta con la misma huella de máquina."""
    with _lock:
        if _cuentas_por_huella[huella] >= MAX_CUENTAS_POR_HUELLA:
            return False, f"Ya existe una cuenta para esta huella de máquina ({MAX_CUENTAS_POR_HUELLA} máximo)"
    return True, ""


def _validar_ubicacion_no_duplicada(ubicacion_hash: str, ip: str) -> Tuple[bool, str]:
    """Valida que no exista una cuenta con la misma ubicación física."""
    if not ubicacion_hash:
        return True, ""  # Si no hay ubicación, no validar
    with _lock:
        if _cuentas_por_ubicacion[ubicacion_hash] >= MAX_CUENTAS_POR_UBICACION:
            return False, f"Ya existe una cuenta para esta ubicación física ({MAX_CUENTAS_POR_UBICACION} máximo)"
    return True, ""


def _registrar_cuenta_creada(huella: str, ubicacion_hash: str = "") -> None:
    """Registra que se creó una cuenta para actualizar los contadores."""
    with _lock:
        _cuentas_por_huella[huella] += 1
        if ubicacion_hash:
            _cuentas_por_ubicacion[ubicacion_hash] += 1


class BlockchainHTTPHandler(BaseHTTPRequestHandler):
    """Manejador HTTP REST y JSON-RPC para el servidor blockchain con seguridad."""
    timeout = 10.0

    def _enviar_json(self, status: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _obtener_ip_cliente(self) -> str:
        """Obtiene la IP del cliente (considerando proxies)."""
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def do_GET(self) -> None:
        ip = self._obtener_ip_cliente()
        if not _verificar_rate_limit(ip):
            self._enviar_json(429, {"error": "Too Many Requests", "mensaje": "Límite de requests excedido"})
            return

        bks = get_blockchain_server()
        if self.path in ("/", "/status"):
            valida, err = bks.validar_cadena()
            self._enviar_json(200, {
                "servidor": __server_name__,
                "total_bloques": len(bks.cadena),
                "cadena_valida": valida,
                "error_validacion": err,
                "ultimo_bloque": bks.obtener_ultimo_bloque().to_dict(),
                "cuentas_por_huella": dict(_cuentas_por_huella),
                "cuentas_por_ubicacion": dict(_cuentas_por_ubicacion),
            })
        elif self.path == "/blocks":
            self._enviar_json(200, {"bloques": [b.to_dict() for b in bks.cadena]})
        elif self.path == "/transform":
            self._enviar_json(200, bks.transformar_ledger_a_pesos_neuronales())
        elif self.path == "/mine":
            bloque = bks.minar_transacciones_pendientes()
            if bloque:
                self._enviar_json(200, {"mensaje": "Bloque minado", "bloque": bloque.to_dict()})
            else:
                self._enviar_json(200, {"mensaje": "Sin transacciones pendientes para minar"})
        elif self.path == "/intentos":
            # Endpoint de auditoría para ver intentos de creación
            with _lock:
                self._enviar_json(200, {"intentos": _registro_intentos[-100:]})
        elif self.path.startswith("/descargar-cuenta-zip"):
            # Descargar el .zip con el hash único de cuenta
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            cuenta_hash = params.get("cuenta_hash", [None])[0]
            if not cuenta_hash:
                self._enviar_json(400, {"error": "Falta parámetro cuenta_hash"})
                return
            self._descargar_zip_cuenta(cuenta_hash)
        else:
            self._enviar_json(404, {"error": "Ruta no encontrada"})

    def do_POST(self) -> None:
        ip = self._obtener_ip_cliente()
        if not _verificar_rate_limit(ip):
            self._enviar_json(429, {"error": "Too Many Requests", "mensaje": "Límite de requests excedido"})
            return

        bks = get_blockchain_server()
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else "{}"
        try:
            params = json.loads(body)
        except Exception:
            params = {}

        if self.path == "/alta-cuenta":
            self._procesar_alta_cuenta(params, ip)
        elif self.path == "/migrar-cuenta":
            self._procesar_migrar_cuenta(params, ip)
        elif self.path == "/transaction":
            idx = bks.agregar_transaccion(
                tipo=params.get("tipo", "TRANSFERENCIA_COGNITIVA"),
                emisor=params.get("emisor", "EXTERNO"),
                receptor=params.get("receptor", "CELEBRO"),
                datos=params.get("datos", {}),
                cid_ipfs=params.get("cid_ipfs"),
            )
            self._enviar_json(201, {"mensaje": "Transaccion encolada", "bloque_objetivo": idx})
        elif self.path == "/learn":
            res = bks.registrar_aprendizaje_neural(
                prompt=params.get("prompt", ""),
                respuesta=params.get("respuesta", ""),
                modelo=params.get("modelo", "qwen2.5:7b"),
            )
            self._enviar_json(200, res)
        else:
            self._enviar_json(404, {"error": "Endpoint POST no reconocido"})

    def _procesar_alta_cuenta(self, params: Dict[str, Any], ip: str) -> None:
        """Procesa la solicitud de alta de cuenta con validaciones de seguridad."""
        nick = params.get("nick", "").strip()
        huella = params.get("huella", "").strip()
        ubicacion_hash = params.get("ubicacion_hash", "").strip()

        # Validaciones básicas
        if not nick or len(nick) < 3:
            _registrar_intento("alta", ip, huella, False, "Nick inválido")
            self._enviar_json(400, {"error": "Nick inválido", "mensaje": "El nick debe tener al menos 3 caracteres"})
            return

        if not huella or len(huella) != 32 or not huella.is_valid_hex_number():
            _registrar_intento("alta", ip, huella, False, "Huella inválida")
            self._enviar_json(400, {"error": "Huella inválida", "mensaje": "La huella debe ser un UUID de 32 caracteres hexadecimales"})
            return

        # Validar que no exista una cuenta con la misma huella
        huella_ok, huella_msg = _validar_huella_no_duplicada(huella, ip)
        if not huella_ok:
            _registrar_intento("alta", ip, huella, False, huella_msg)
            self._enviar_json(409, {"error": "Cuenta duplicada", "mensaje": huella_msg})
            return

        # Validar ubicación si se proporciona
        if ubicacion_hash:
            ubicacion_ok, ubicacion_msg = _validar_ubicacion_no_duplicada(ubicacion_hash, ip)
            if not ubicacion_ok:
                _registrar_intento("alta", ip, huella, False, ubicacion_msg)
                self._enviar_json(409, {"error": "Ubicación duplicada", "mensaje": ubicacion_msg})
                return

        # Generar hash único de cuenta
        cuenta_hash = _generar_hash_cuenta(nick, huella, ubicacion_hash)

        # Registrar la cuenta creada
        _registrar_cuenta_creada(huella, ubicacion_hash)
        _registrar_intento("alta", ip, huella, True, "")

        # Emitir transacción en la blockchain
        bks = get_blockchain_server()
        datos_tx = {
            "tipo": "ALTA_CUENTA",
            "nick": nick,
            "huella": huella[:16] + "...",
            "cuenta_hash": cuenta_hash,
            "ubicacion_hash": ubicacion_hash[:16] + "..." if ubicacion_hash else "no_verificada",
        }
        bks.agregar_transaccion(
            tipo="ALTA_CUENTA",
            emisor="REGISTRO_PC",
            receptor="BLOCKCHAIN_CELEBRO",
            datos=datos_tx,
        )

        # Minar el bloque inmediatamente
        bloque = bks.minar_transacciones_pendientes()

        self._enviar_json(201, {
            "mensaje": "Cuenta creada exitosamente",
            "cuenta_hash": cuenta_hash,
            "nick": nick,
            "bloque": bloque.to_dict() if bloque else None,
        })

    def _procesar_migrar_cuenta(self, params: Dict[str, Any], ip: str) -> None:
        """Procesa la solicitud de migración de cuenta antigua."""
        nick = params.get("nick", "").strip()
        huella = params.get("huella", "").strip()
        ubicacion_hash = params.get("ubicacion_hash", "").strip()

        # Validaciones básicas
        if not nick or len(nick) < 3:
            _registrar_intento("migracion", ip, huella, False, "Nick inválido")
            self._enviar_json(400, {"error": "Nick inválido", "mensaje": "El nick debe tener al menos 3 caracteres"})
            return

        if not huella or len(huella) != 32 or not huella.is_valid_hex_number():
            _registrar_intento("migracion", ip, huella, False, "Huella inválida")
            self._enviar_json(400, {"error": "Huella inválida", "mensaje": "La huella debe ser un UUID de 32 caracteres hexadecimales"})
            return

        # Validar que no exista una cuenta con la misma huella
        huella_ok, huella_msg = _validar_huella_no_duplicada(huella, ip)
        if not huella_ok:
            _registrar_intento("migracion", ip, huella, False, huella_msg)
            self._enviar_json(409, {"error": "Cuenta duplicada", "mensaje": huella_msg})
            return

        # Generar hash único de cuenta para migración
        cuenta_hash = _generar_hash_cuenta(nick, huella, ubicacion_hash, es_migracion=True)

        # Registrar la cuenta migrada
        _registrar_cuenta_creada(huella, ubicacion_hash)
        _registrar_intento("migracion", ip, huella, True, "")

        # Emitir transacción en la blockchain
        bks = get_blockchain_server()
        datos_tx = {
            "tipo": "MIGRACION_CUENTA",
            "nick": nick,
            "huella": huella[:16] + "...",
            "cuenta_hash": cuenta_hash,
            "ubicacion_hash": ubicacion_hash[:16] + "..." if ubicacion_hash else "no_verificada",
        }
        bks.agregar_transaccion(
            tipo="MIGRACION_CUENTA",
            emisor="MIGRACION_PC",
            receptor="BLOCKCHAIN_CELEBRO",
            datos=datos_tx,
        )

        # Minar el bloque inmediatamente
        bloque = bks.minar_transacciones_pendientes()

        self._enviar_json(200, {
            "mensaje": "Cuenta migrada exitosamente",
            "cuenta_hash": cuenta_hash,
            "nick": nick,
            "bloque": bloque.to_dict() if bloque else None,
        })

    def _descargar_zip_cuenta(self, cuenta_hash: str) -> None:
        """Genera y descarga el .zip con el hash único de cuenta."""
        # Validar que el hash sea válido
        if len(cuenta_hash) != 64 or not cuenta_hash.is_valid_hex_number():
            self._enviar_json(400, {"error": "Hash inválido", "mensaje": "El hash debe ser SHA-256 de 64 caracteres"})
            return

        # Generar el contenido del archivo JSON
        contenido = {
            "cuenta_hash": cuenta_hash,
            "fecha_generacion": time.time(),
            "red": "WoldVirtualP2P3D",
            "version": "2026.3.1",
        }

        # Convertir a JSON bytes
        json_bytes = json.dumps(contenido, indent=2, ensure_ascii=False).encode("utf-8")

        # Enviar como archivo .zip (simulado, en producción sería un ZIP real)
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="cuenta_{cuenta_hash[:16]}.zip"')
        self.send_header("Content-Length", str(len(json_bytes)))
        self.end_headers()
        self.wfile.write(json_bytes)

    def log_message(self, format: str, *args: Any) -> None:
        """Sobrescribir para evitar logs innecesarios."""
        pass


def _generar_hash_cuenta(nick: str, huella: str, ubicacion_hash: str, es_migracion: bool = False) -> str:
    """Genera el hash único de cuenta usando SHA-256."""
    timestamp = str(time.time())
    tipo = "MIGRACION" if es_migracion else "ALTA"
    raw = f"{nick}:{huella}:{ubicacion_hash}:{tipo}:{timestamp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class BlockchainServerDaemon:
    """Contenedor de ejecución asíncrona para el servicio HTTP Blockchain."""

    def __init__(self, host: str = "127.0.0.1", puerto: int = 8545) -> None:
        self.host, self.puerto = host, puerto
        self.servidor: Optional[ThreadingHTTPServer] = None
        self.hilo: Optional[threading.Thread] = None

    def iniciar(self) -> bool:
        """Arranca el servidor HTTP en un hilo demonio desacoplado."""
        try:
            self.servidor = ThreadingHTTPServer((self.host, self.puerto), BlockchainHTTPHandler)
            self.servidor.daemon_threads = True
            self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
            self.hilo.start()
            logger.info(f"Servidor blockchain iniciado en {self.host}:{self.puerto}")
            return True
        except Exception as e:
            logger.error(f"Error iniciando servidor blockchain: {e}")
            return False

    def detener(self) -> None:
        """Detiene ordenadamente el servidor HTTP."""
        if self.servidor:
            self.servidor.shutdown()
            self.servidor.server_close()
            self.servidor = None
            logger.info("Servidor blockchain detenido")


_blockchain_instancia: Optional[CelebroBlockchain] = None
_daemon_http_instancia: Optional[BlockchainServerDaemon] = None


def get_blockchain_server():
    """Acceso singleton al motor de la blockchain neuronal."""
    global _blockchain_instancia
    if _blockchain_instancia is None:
        _blockchain_instancia = _clase_blockchain()()
    return _blockchain_instancia


def iniciar_servidor_blockchain(puerto: int = 8545) -> BlockchainServerDaemon:
    """Arranca el servicio de API HTTP del servidor de bloques."""
    global _daemon_http_instancia
    if _daemon_http_instancia is None:
        _daemon_http_instancia = BlockchainServerDaemon(puerto=puerto)
        _daemon_http_instancia.iniciar()
    return _daemon_http_instancia


def _hook_salida_sistema() -> None:
    """Ejecutado al cerrar la sesión de terminal: sube ledger y pesos a IPFS."""
    if _blockchain_instancia:
        _blockchain_instancia.cerrar_sesion_y_subir_ipfs()
    if _daemon_http_instancia:
        _daemon_http_instancia.detener()


atexit.register(_hook_salida_sistema)


if __name__ == "__main__":
    bks = get_blockchain_server()
    print("\n\033[1;36m" + "=" * 74 + "\033[0m")
    print(f"  \033[1;32mBLOCKCHAIN SERVER & CONSENSO NEURAL: {__server_name__}\033[0m")
    print(f"  Neuronas Activas: \033[1;35m{len(bks.conversor.neuronas)}\033[0m | Dificultad: \033[1;37m{bks.dificultad}\033[0m | Bloques: \033[1;37m{len(bks.cadena)}\033[0m")
    print(f"  Seguridad: \033[1;33mAnti-duplicación activa\033[0m | Max cuentas/huella: \033[1;37m{MAX_CUENTAS_POR_HUELLA}\033[0m")
    print("\033[1;36m" + "=" * 74 + "\033[0m")

    # Muestra los hashes únicos inmediatamente
    bks.mostrar_cadena_hashes_terminal()

    # 1. Transformación del ledger en pesos neuronales
    print("[+] Transformando blockchain_ledger.json en pesos neuronales (50 neuronas)...")
    res_t = bks.transformar_ledger_a_pesos_neuronales()
    print(f"    Bloques convertidos : \033[1;33m{res_t['total_bloques']}\033[0m")
    print(f"    Pesos en PSNRL      : \033[1;32m{res_t['npz_pesos']}\033[0m (Norma: {res_t['norma_acumulada']})")

    # 2. Arranque del actualizador continuo de la red neuronal durante la sesión
    bks.arrancar_actualizador_red()
    print("    Actualizador neuronal: \033[1;32mACTIVO EN SEGUNDO PLANO DURANTE LA SESIÓN\033[0m")

    # 3. Transacción y minado en vivo
    print("\n[+] Nueva transacción cognitiva en blockchain...")
    res = bks.registrar_aprendizaje_neural(
        prompt="¿Cual es el rol de las 50 neuronas en la blockchain de Celebro?",
        respuesta="Registrar cada gradiente Hebbiano y estado emocional en bloques inmutables con hashes unicos.",
        modelo="qwen2.5:7b",
    )
    print(f"    CID IPFS vinculado   : \033[1;36m{res['ipfs_cid']}\033[0m")

    bloque = bks.minar_transacciones_pendientes()
    if bloque:
        print(f"    \033[1;32mBloque #{bloque.indice} consolidado con éxito!\033[0m")
        print(f"    Hash único del bloque: \033[1;33m{bloque.hash_bloque}\033[0m")
        print(f"    Raíz de Merkle       : \033[1;35m{bloque.merkle_root}\033[0m")

    valida, err = bks.validar_cadena()
    estado_str = "\033[1;32mINTEGRA Y VÁLIDA\033[0m" if valida else f"\033[1;31mERROR: {err}\033[0m"
    print(f"\n[+] Estado de la cadena: {estado_str}")
    print("    Persistencia IPFS al cierre: \033[1;36mREGISTRADA (atexit hook activo)\033[0m")
    print("\033[1;36m" + "=" * 74 + "\033[0m\n")
