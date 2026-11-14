"""
BKSVCB.py - Blockchain Server & Consenso Neuronal de Celebro (Arquitectura 2026)
================================================================================
Servidor de bloques inmutable y libro mayor distribuido para WoldVirtualP2P3D:
  - Transforma blockchain_ledger.json en pesos neuronales nada mas arrancar.
  - Mantiene activa la sincronizacion y actualizacion neuronal durante la sesion.
  - Al cerrar sesion, sube atomicamente el estado y pesos de PSNRL a IPFS.
  - Estructura de bloques criptograficos con hashing doble SHA-256 y Merkle Root.
  - Visualizacion de hashes unicos de cada bloque en terminal en tiempo real.
  - Consenso PoNL (Proof of Neural Learning) y servidor HTTP REST/JSON-RPC.
"""
from __future__ import annotations
import os, sys, time, json, hashlib, logging, re, threading, atexit
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

logging.basicConfig(level=logging.CRITICAL)
for _lg in ("", "WoldVirtualP2P3D", "RFENRN1", "LC", "urllib3", "ENRN", "SLRN", "RNP"):
    logging.getLogger(_lg).setLevel(logging.CRITICAL)

__version__ = "2026.3.1"
__server_name__ = "CelebroBlockchainServer-BKSVCB"

# Solo para el servidor de demo: permite repetir alta y migración con la misma
# huella o el mismo nick, para poder probar los dos caminos en una misma
# sesión. En producción se queda en False (una cuenta por PC y nick único).
PERMITIR_REPETIR = False

CELEBRO_DIR: Path = Path(__file__).parent.resolve()
ROOT_DIR: Path = CELEBRO_DIR.parent.parent.resolve()
try:
    from STM_CH.rutas import PSNRL_DIR as PSNRL_DIR, LEDGER_PATH as LEDGER_PATH
except ImportError:
    try:
        from STM_CH.rutas import PSNRL_DIR, LEDGER_PATH
    except ImportError:
        PSNRL_DIR: Path = CELEBRO_DIR / "PSNRL"
        LEDGER_PATH: Path = CELEBRO_DIR / "blockchain_ledger.json"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from STM_BKCH.compat_local import get_conversor_pesos, ConversorRespuestaPesos, get_ipfs_manager, IPFSManager
from SBSTM.IALOCAL import (
    ejecutar_flujo_sesion_local as _ialocal_pre_sesion,
    cerrar_sesion_ialocal as _ialocal_cierre,
    MODELOS_DIR as _IALOCAL_MODELOS_DIR,
)
_IALOCAL_DISPONIBLE = True


class BloqueNeuronal:
    """Representa un bloque inmutable de la cadena de bloques de Celebro."""

    def __init__(
        self, indice: int, hash_previo: str, transacciones: List[Dict[str, Any]],
        estado_neuronal: Optional[Dict[str, Any]] = None, dificultad: int = 2,
        nonce: int = 0, hash_existente: Optional[str] = None,
        merkle_root_existente: Optional[str] = None,
    ) -> None:
        self.indice = indice
        self.hash_previo = hash_previo
        self.transacciones = transacciones
        self.estado_neuronal = estado_neuronal or {}
        self.dificultad = dificultad
        self.nonce = nonce
        self.merkle_root = merkle_root_existente or self.calcular_merkle_root()
        self.hash_bloque = hash_existente or self.calcular_hash()

    def calcular_merkle_root(self) -> str:
        """Calcula la raiz de Merkle de las transacciones incluidas en el bloque."""
        if not self.transacciones:
            return hashlib.sha256(b"empty_block_celebro_2026").hexdigest()
        hashes = [
            hashlib.sha256(json.dumps(tx, sort_keys=True).encode("utf-8")).hexdigest()
            for tx in self.transacciones
        ]
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256((h1 + h2).encode("utf-8")).hexdigest()
                for h1, h2 in zip(hashes[0::2], hashes[1::2])
            ]
        return hashes[0]

    def calcular_hash(self) -> str:
        """Calcula el doble hash SHA-256 inmutable de la cabecera."""
        cabecera = {
            "indice": self.indice, "hash_previo": self.hash_previo,
            "merkle_root": self.merkle_root, "dificultad": self.dificultad, "nonce": self.nonce,
        }
        serializado = json.dumps(cabecera, sort_keys=True).encode("utf-8")
        return hashlib.sha256(hashlib.sha256(serializado).digest()).hexdigest()

    def minar_bloque(self, max_iteraciones: int = 500000) -> bool:
        """Realiza el minado por prueba de trabajo/aprendizaje adaptativo con serializacion acelerada."""
        prefijo = "0" * self.dificultad
        self.merkle_root = self.calcular_merkle_root()
        prefix = f'{{"dificultad": {self.dificultad}, "hash_previo": "{self.hash_previo}", "indice": {self.indice}, "merkle_root": "{self.merkle_root}", "nonce": '.encode("ascii")
        for _ in range(max_iteraciones):
            ser = prefix + str(self.nonce).encode("ascii") + b"}"
            h = hashlib.sha256(hashlib.sha256(ser).digest()).hexdigest()
            if h.startswith(prefijo):
                self.hash_bloque = h
                return True
            self.nonce += 1
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Exporta el bloque completo a un diccionario serializable."""
        return {
            "indice": self.indice, "hash_bloque": self.hash_bloque,
            "hash_previo": self.hash_previo, "merkle_root": self.merkle_root,
            "dificultad": self.dificultad, "nonce": self.nonce,
            "total_transacciones": len(self.transacciones),
            "transacciones": self.transacciones, "estado_neuronal": self.estado_neuronal,
        }


class CelebroBlockchain:
    """Motor central de la Blockchain neuronal con transformacion sinaptica e IPFS."""

    # Cuota SMTPLC por ubicacion fisica (hash de cluster; nunca la ubicacion cruda).
    # 3 cuentas por ubicacion admite hogares legitimos; el cooldown de 72 h frena
    # las rafagas automatizadas aunque no se alcance el tope.
    CUOTA_MAX_CUENTAS_POR_UBICACION = 3
    CUOTA_COOLDOWN_UBICACION_SEG = 72 * 3600

    def __init__(self, dificultad: int = 2) -> None:
        self.dificultad = dificultad
        self.cadena: List[BloqueNeuronal] = []
        self.transacciones_pendientes: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.conversor: ConversorRespuestaPesos = get_conversor_pesos()
        self.ipfs_mgr: IPFSManager = get_ipfs_manager()
        self.actualizador_activo = False
        self._hilo_actualizador: Optional[threading.Thread] = None
        self._inicializar_o_cargar_cadena()

    def _inicializar_o_cargar_cadena(self) -> None:
        """Carga el ledger previo desde disco o forja el bloque genesis."""
        if LEDGER_PATH.exists():
            try:
                with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                bloques_cargados = []
                for b in raw.get("cadena", []):
                    bloque = BloqueNeuronal(
                        indice=b["indice"], hash_previo=b["hash_previo"],
                        transacciones=b.get("transacciones", []),
                        estado_neuronal=b.get("estado_neuronal", {}),
                        dificultad=b.get("dificultad", self.dificultad), nonce=b.get("nonce", 0),
                        hash_existente=b.get("hash_bloque"),
                        merkle_root_existente=b.get("merkle_root"),
                    )
                    bloques_cargados.append(bloque)
                if bloques_cargados:
                    self.cadena = bloques_cargados
                    return
            except Exception: pass
        self._crear_bloque_genesis()

    def _crear_bloque_genesis(self) -> None:
        """Forja el bloque 0 inicial con metadatos del cluster Celebro 2026."""
        estado_inicial = {
            "total_neuronas": len(self.conversor.neuronas),
            "capas": ["ENRN", "RF_SL", "RF_EN", "RNP", "SLRN"],
            "version_cluster": __version__, "consenso": "Proof-of-Neural-Learning (PoNL)",
        }
        tx_genesis = {
            "tipo": "GENESIS_COGNITIVO", "emisor": "SYSTEM_CELEBRO", "receptor": "CLUSTER_P2P",
            "descripcion": "Arranque formal de la blockchain neuronal WoldVirtualP2P3D",
            "hash_semilla": hashlib.sha256(b"genesis_seed_2026").hexdigest(),
        }
        genesis = BloqueNeuronal(
            indice=0, hash_previo="0" * 64, transacciones=[tx_genesis],
            estado_neuronal=estado_inicial, dificultad=1,
        )
        genesis.minar_bloque()
        self.cadena = [genesis]
        self.guardar_ledger()

    def obtener_ultimo_bloque(self) -> BloqueNeuronal:
        """Retorna el ultimo bloque confirmado de la cadena."""
        return self.cadena[-1]

    def agregar_transaccion(
        self, tipo: str, emisor: str, receptor: str, datos: Dict[str, Any],
        cid_ipfs: Optional[str] = None,
    ) -> int:
        """Anade una nueva transaccion al pool de espera con validacion criptografica."""
        with self.lock:
            tx = {
                "id_tx": hashlib.sha256(f"{emisor}:{receptor}:{time.time_ns()}".encode()).hexdigest()[:16],
                "tipo": tipo, "emisor": emisor, "receptor": receptor,
                "cid_ipfs": cid_ipfs or "", "datos": datos,
            }
            self.transacciones_pendientes.append(tx)
            return self.obtener_ultimo_bloque().indice + 1

    @staticmethod
    def validar_huella(huella: Any) -> Optional[str]:
        """Valida la huella de maquina: el UUID de identidad que genera Godot
        (Identidad.asegurar_identidad), 32 caracteres hexadecimales. Devuelve la
        huella normalizada a minusculas o None si no es valida."""
        if not isinstance(huella, str):
            return None
        h = huella.strip()
        if len(h) != 32:
            return None
        if any(c not in "0123456789abcdefABCDEF" for c in h):
            return None
        return h.lower()

    @staticmethod
    def validar_ubicacion_hash(ubicacion_hash: Any) -> Optional[str]:
        """Valida el hash de cluster de ubicacion fisica (SMTPLC): SHA-256 de
        64 hex que calcula el cliente (LocationFingerprinter.ComputeLocationClusterHash).
        Devuelve el hash normalizado a minusculas, "" si no se envia (campo opcional)
        o None si es invalido. Nunca se recibe la ubicacion cruda, solo su hash."""
        if ubicacion_hash is None or (isinstance(ubicacion_hash, str) and not ubicacion_hash.strip()):
            return ""
        if not isinstance(ubicacion_hash, str):
            return None
        h = ubicacion_hash.strip()
        if len(h) != 64:
            return None
        if any(c not in "0123456789abcdefABCDEF" for c in h):
            return None
        return h.lower()

    def alta_cuenta(self, nick: str, huella: str, ubicacion_hash: str = "") -> Dict[str, Any]:
        """Registra una cuenta nueva: un bloque ALTA_CUENTA = un hash unico de cuenta.

        Contrato F9: una cuenta por PC registrado. La huella cruda del equipo no se
        escribe en la cadena; solo viaja su compromiso (doble SHA-256). El campo
        opcional ubicacion_hash es el hash de cluster fisico (SMTPLC) y se guarda
        tal cual (ya hasheado) para la cuota por ubicacion. El hash de cuenta
        devuelto es el hash del bloque minado y sirve en este PC o en cualquier otro
        desde el que el jugador se conecte.
        """
        nick = str(nick or "").strip()
        if not 10 <= len(nick) <= 15:
            return {"codigo": 422, "error": "El nick debe tener entre 10 y 15 letras."}
        huella_norm = self.validar_huella(huella)
        if not huella_norm:
            return {"codigo": 422, "error": "Huella de maquina invalida: debe ser el UUID de identidad (32 hexadecimales)."}
        ubicacion_norm = self.validar_ubicacion_hash(ubicacion_hash)
        if ubicacion_norm is None:
            return {"codigo": 422, "error": "ubicacion_hash invalido: debe ser un SHA-256 de 64 hexadecimales."}
        compromiso = hashlib.sha256(hashlib.sha256(huella_norm.encode("utf-8")).digest()).hexdigest()
        with self.lock:
            if not PERMITIR_REPETIR and self._buscar_cuenta_por_huella(compromiso):
                return {"codigo": 409, "error": "Este PC ya tiene una cuenta registrada (un bloque por PC)."}
            if not PERMITIR_REPETIR and self._buscar_cuenta_por_nick(nick):
                return {"codigo": 409, "error": "Ese nick ya esta registrado en la cadena."}
            error_ubicacion = self._cuota_ubicacion(ubicacion_norm)
            if error_ubicacion:
                return error_ubicacion
        datos_tx = {
            "nick": nick,
            "huella_comprometida": compromiso,
            "ubicacion_hash": ubicacion_norm,
            "fecha_alta": time.strftime("%Y-%m-%d %H:%M:%S"),
            "alta_ts": time.time(),
        }
        self.agregar_transaccion(
            tipo="ALTA_CUENTA", emisor="BKSVCB", receptor=nick, datos=datos_tx,
        )
        bloque = self.minar_transacciones_pendientes()
        if not bloque:
            return {"codigo": 500, "error": "No se pudo minar el bloque de cuenta."}
        return {
            "codigo": 201, "nick": nick, "cuenta_hash": bloque.hash_bloque,
            "indice_bloque": bloque.indice, "bloque": bloque.to_dict(),
        }

    def migrar_cuenta(self, nick: str, huella: str, ubicacion_hash: str = "",
                      prueba: str = "") -> Dict[str, Any]:
        """Migra una cuenta antigua (llave + hash PC + semilla) al nuevo sistema de hash único.

        Busca si existe una cuenta antigua con la huella dada y, si no existe una cuenta
        nueva con esa huella, crea un bloque MIGRACION_CUENTA que genera el hash único.
        Esto permite sustituir el sistema antiguo por el nuevo sin perder la identidad.

        ``prueba`` es el SHA-256 que calcula el cliente con la llave de acceso y la
        frase semilla; se guarda en el bloque como evidencia de la migración (no se
        puede revertir a esas credenciales).
        """
        nick = str(nick or "").strip()
        # Las cuentas antiguas pueden tener nicks cortos: se permiten al migrar,
        # pero nunca más de 15 (misma regla que el alta para los nuevos).
        if len(nick) < 3:
            return {"codigo": 422, "error": "El nick debe tener al menos 3 letras."}
        if len(nick) > 15:
            return {"codigo": 422, "error": "El nick no puede pasar de 15 letras."}
        huella_norm = self.validar_huella(huella)
        if not huella_norm:
            return {"codigo": 422, "error": "Huella de maquina invalida: debe ser el UUID de identidad (32 hexadecimales)."}
        ubicacion_norm = self.validar_ubicacion_hash(ubicacion_hash)
        if ubicacion_norm is None:
            return {"codigo": 422, "error": "ubicacion_hash invalido: debe ser un SHA-256 de 64 hexadecimales."}
        prueba_norm = ""
        if str(prueba or "").strip():
            prueba_norm = str(prueba).strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", prueba_norm):
                return {"codigo": 422,
                        "error": "prueba invalida: debe ser un SHA-256 de 64 hexadecimales."}
        compromiso = hashlib.sha256(hashlib.sha256(huella_norm.encode("utf-8")).digest()).hexdigest()
        with self.lock:
            # Verificar si ya existe una cuenta nueva con esta huella
            if not PERMITIR_REPETIR and self._buscar_cuenta_por_huella(compromiso):
                return {"codigo": 409, "error": "Este PC ya tiene una cuenta migrada o registrada."}
            # Verificar si el nick ya está en uso
            if not PERMITIR_REPETIR and self._buscar_cuenta_por_nick(nick):
                return {"codigo": 409, "error": "Ese nick ya esta registrado en la cadena."}
            error_ubicacion = self._cuota_ubicacion(ubicacion_norm)
            if error_ubicacion:
                return error_ubicacion
        datos_tx = {
            "nick": nick,
            "huella_comprometida": compromiso,
            "ubicacion_hash": ubicacion_norm,
            "fecha_migracion": time.strftime("%Y-%m-%d %H:%M:%S"),
            "migracion_ts": time.time(),
            "tipo_migracion": "LLAVE_SEMILLA_A_HASH_UNICO",
        }
        if prueba_norm:
            datos_tx["prueba_llave_semilla"] = prueba_norm
        self.agregar_transaccion(
            tipo="MIGRACION_CUENTA", emisor="BKSVCB", receptor=nick, datos=datos_tx,
        )
        bloque = self.minar_transacciones_pendientes()
        if not bloque:
            return {"codigo": 500, "error": "No se pudo minar el bloque de migración."}
        return {
            "codigo": 200, "nick": nick, "cuenta_hash": bloque.hash_bloque,
            "indice_bloque": bloque.indice, "bloque": bloque.to_dict(),
        }

    def generar_zip_cuenta(self, cuenta_hash: str) -> Dict[str, Any]:
        """Genera un archivo .zip JSON con el hash único de cuenta para descarga.

        El .zip contiene un archivo cuenta.json con el hash único y metadatos.
        Este archivo sirve como identificación portable del usuario (funciona en
        cualquier PC desde el que se conecte).
        """
        if not cuenta_hash or len(cuenta_hash) != 64:
            return {"exito": False, "error": "Hash de cuenta inválido (debe ser 64 hexadecimales)."}

        # Buscar la cuenta en la cadena
        cuenta_encontrada = None
        for bloque in self.cadena:
            for tx in bloque.transacciones:
                if tx.get("tipo") in ["ALTA_CUENTA", "MIGRACION_CUENTA"]:
                    if bloque.hash_bloque == cuenta_hash:
                        datos = tx.get("datos", {})
                        cuenta_encontrada = {
                            "nick": datos.get("nick", ""),
                            "cuenta_hash": cuenta_hash,
                            "indice_bloque": bloque.indice,
                            "hash_previo": bloque.hash_previo,
                            "fecha": datos.get("fecha_alta") or datos.get("fecha_migracion", ""),
                            "tipo": tx.get("tipo", ""),
                        }
                        break
            if cuenta_encontrada:
                break

        if not cuenta_encontrada:
            return {"exito": False, "error": "Cuenta no encontrada en la cadena."}

        try:
            import zipfile
            import io

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Agregar cuenta.json
                json_str = json.dumps(cuenta_encontrada, indent=2, ensure_ascii=False)
                zipf.writestr("cuenta.json", json_str)

                # Agregar metadata.txt
                metadata = f"""Hash Único de Cuenta - WoldVirtualP2P3D
Nick: {cuenta_encontrada['nick']}
Cuenta Hash: {cuenta_hash}
Bloque: #{cuenta_encontrada['indice_bloque']}
Tipo: {cuenta_encontrada['tipo']}
Fecha: {cuenta_encontrada['fecha']}

Este archivo es tu identificación portable en el metaverso.
"""
                zipf.writestr("metadata.txt", metadata)

            zip_buffer.seek(0)
            filename = f"cuenta_{cuenta_encontrada['nick']}_{cuenta_hash[:16]}.zip"

            return {
                "exito": True,
                "zip_data": zip_buffer.getvalue(),
                "filename": filename,
                "cuenta": cuenta_encontrada,
            }
        except Exception as e:
            return {"exito": False, "error": f"Error al generar ZIP: {str(e)}"}

    def _buscar_cuenta_por_huella(self, compromiso: str) -> Optional[Dict[str, Any]]:
        """Busca una cuenta (alta o migración) con la huella comprometida dada.

        Se miran los dos tipos a propósito: si solo se mirara ALTA_CUENTA, una
        cuenta migrada podría migrarse otra vez y tener dos bloques.
        """
        for bloque in self.cadena:
            for tx in bloque.transacciones:
                if (tx.get("tipo") in ("ALTA_CUENTA", "MIGRACION_CUENTA")
                        and (tx.get("datos") or {}).get("huella_comprometida") == compromiso):
                    return tx
        for tx in self.transacciones_pendientes:
            if (tx.get("tipo") in ("ALTA_CUENTA", "MIGRACION_CUENTA")
                    and (tx.get("datos") or {}).get("huella_comprometida") == compromiso):
                return tx
        return None

    def _buscar_cuenta_por_nick(self, nick: str) -> Optional[Dict[str, Any]]:
        """Busca una cuenta (alta o migración) con el nick dado."""
        for bloque in self.cadena:
            for tx in bloque.transacciones:
                if (tx.get("tipo") in ("ALTA_CUENTA", "MIGRACION_CUENTA")
                        and (tx.get("datos") or {}).get("nick") == nick):
                    return tx
        for tx in self.transacciones_pendientes:
            if (tx.get("tipo") in ("ALTA_CUENTA", "MIGRACION_CUENTA")
                    and (tx.get("datos") or {}).get("nick") == nick):
                return tx
        return None

    def _cuota_ubicacion(self, ubicacion_hash: str) -> Optional[Dict[str, Any]]:
        """Cuota SMTPLC por ubicacion fisica: tope de cuentas y cooldown entre altas.

        Se llama dentro del lock de alta_cuenta (no lo adquiere, igual que los
        _buscar_cuenta_*). Sin ubicacion_hash no hay cuota que aplicar: el llamador
        decide si el cliente la envia.
        """
        if not ubicacion_hash:
            return None
        cuentas = []
        for bloque in self.cadena:
            for tx in bloque.transacciones:
                if tx.get("tipo") == "ALTA_CUENTA":
                    datos = tx.get("datos") or {}
                    if datos.get("ubicacion_hash") == ubicacion_hash:
                        cuentas.append(datos)
        for tx in self.transacciones_pendientes:
            if tx.get("tipo") == "ALTA_CUENTA":
                datos = tx.get("datos") or {}
                if datos.get("ubicacion_hash") == ubicacion_hash:
                    cuentas.append(datos)
        if len(cuentas) >= self.CUOTA_MAX_CUENTAS_POR_UBICACION:
            return {"codigo": 409, "error": f"Ubicacion al limite: maximo {self.CUOTA_MAX_CUENTAS_POR_UBICACION} cuentas por ubicacion fisica."}
        if cuentas:
            ultima_ts = max(float(d.get("alta_ts", 0.0)) for d in cuentas)
            restante = self.CUOTA_COOLDOWN_UBICACION_SEG - (time.time() - ultima_ts)
            if restante > 0:
                return {"codigo": 429, "error": f"Cooldown activo en esta ubicacion: reintenta en {int(restante)} segundos.", "reintentar_en_segundos": int(restante) + 1}
        return None

    def registrar_aprendizaje_neural(self, prompt: str, respuesta: str, modelo: str) -> Dict[str, Any]:
        """Procesa consulta a traves de las 50 neuronas activas y emite transaccion."""
        t0 = time.perf_counter()
        info_neural = self.conversor.asimilar_respuestas_y_calcular_sintesis(prompt, respuesta, modelo)
        res_ipfs = self.ipfs_mgr.almacenar_pesos(
            origen=json.dumps(info_neural).encode("utf-8"),
            nombre_modelo=f"tx_neural_{int(time.time())}", eliminar_local=False,
        )
        cid = res_ipfs.get("cid", "")
        datos_tx = {
            "modelo": modelo, "prompt_resumen": prompt[:80],
            "norma_delta": info_neural.get("norma_delta_aplicada", 0.0),
            "estado_emocional": info_neural.get("estado_emocional", 0.0),
            "tono": info_neural.get("tono_cognitivo", "neutral"),
            "duracion_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }
        self.agregar_transaccion(
            tipo="ACTUALIZACION_SINAPTICA", emisor="CONVERSOR_PSNRCV",
            receptor="CELEBRO_P2P", datos=datos_tx, cid_ipfs=cid,
        )
        return {"neural": info_neural, "ipfs_cid": cid, "transacciones_espera": len(self.transacciones_pendientes)}

    # Umbral de originalidad del avatar: media absoluta sobre las 33 dimensiones
    # que mide el cliente (5 tintes + 18 campos, normalizados a 0..1). Debe
    # coincidir con AvatarFirma.UMBRAL_ORIGINALIDAD en el lado Godot.
    UMBRAL_ORIGINALIDAD_AVATAR = 0.12

    def _bloque_por_hash(self, hash_bloque: str) -> Optional[BloqueNeuronal]:
        """Devuelve el bloque con ese hash (o None). La cadena es local y corta."""
        for bloque in self.cadena:
            if bloque.hash_bloque == hash_bloque:
                return bloque
        return None

    def registrar_avatar_original(self, cuenta_hash: str, nick: str,
                                  avatar_firma: str, avatar_delta: Any) -> Dict[str, Any]:
        """Ancla un avatar propio a una cuenta y lo asimila la red neuronal.

        Solo se acepta si el avatar se diferencia del base lo suficiente
        (``avatar_delta >= UMBRAL_ORIGINALIDAD_AVATAR``). El bloque AVATAR_ORIGINAL
        guarda la **firma** del aspecto (nunca la imagen) ligada al hash de
        cuenta; la misma operacion alimenta las 50 neuronas con la sintesis del
        aspecto, que es el dato de entrenamiento.
        """
        cuenta = str(cuenta_hash or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", cuenta):
            return {"codigo": 422, "error": "cuenta_hash invalido: debe ser SHA-256 de 64 hexadecimales."}
        firma = str(avatar_firma or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", firma):
            return {"codigo": 422, "error": "avatar_firma invalida: debe ser SHA-256 de 64 hexadecimales."}
        try:
            delta = float(avatar_delta)
        except (TypeError, ValueError):
            return {"codigo": 422, "error": "avatar_delta invalido: debe ser un numero entre 0 y 1."}
        if not 0.0 <= delta <= 1.0:
            return {"codigo": 422, "error": "avatar_delta fuera de rango: debe estar entre 0 y 1."}
        if delta < self.UMBRAL_ORIGINALIDAD_AVATAR:
            return {"codigo": 422,
                    "error": (f"El avatar no se diferencia lo suficiente ({delta * 100:.0f}% "
                              f"< {self.UMBRAL_ORIGINALIDAD_AVATAR * 100:.0f}%).")}

        with self.lock:
            bloque_cuenta = self._bloque_por_hash(cuenta)
            if bloque_cuenta is None:
                return {"codigo": 404, "error": "Cuenta no encontrada en la cadena."}
            tx_cuenta = next((t for t in bloque_cuenta.transacciones
                              if t.get("tipo") in ("ALTA_CUENTA", "MIGRACION_CUENTA")), None)
            if tx_cuenta is None:
                return {"codigo": 404, "error": "El bloque no contiene un alta de cuenta."}
            datos_cuenta = tx_cuenta.get("datos") or {}
            nick_cuenta = str(datos_cuenta.get("nick", ""))
            if str(nick or "").strip() and str(nick).strip() != nick_cuenta:
                return {"codigo": 409, "error": "El nick no coincide con el de la cuenta."}
            for bloque in self.cadena:
                for tx in bloque.transacciones:
                    if (tx.get("tipo") == "AVATAR_ORIGINAL"
                            and (tx.get("datos") or {}).get("cuenta_hash") == cuenta
                            and (tx.get("datos") or {}).get("avatar_firma") == firma):
                        return {"codigo": 409, "error": "Ese avatar ya esta registrado para esta cuenta."}

        datos_tx = {
            "cuenta_hash": cuenta,
            "nick": nick_cuenta,
            "avatar_firma": firma,
            "avatar_delta": round(delta, 6),
            "huella_comprometida": datos_cuenta.get("huella_comprometida", ""),
            "fecha_registro": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.agregar_transaccion(tipo="AVATAR_ORIGINAL", emisor="BKSVCB",
                                 receptor=nick_cuenta, datos=datos_tx)
        # El aspecto sintetizado entra en las 50 neuronas (dato de entrenamiento).
        res_neural = self.registrar_aprendizaje_neural(
            prompt=f"avatar propio de {nick_cuenta} (delta {delta:.3f})",
            respuesta=f"firma {firma}",
            modelo="avatar-original-demo",
        )
        bloque = self.minar_transacciones_pendientes()
        if not bloque:
            return {"codigo": 500, "error": "No se pudo minar el bloque de avatar."}
        return {"codigo": 201, "indice_bloque": bloque.indice, "bloque": bloque.to_dict(),
                "neuronal": res_neural.get("neural", {})}

    def minar_transacciones_pendientes(self, minero_id: str = "CelebroLocalNode") -> Optional[BloqueNeuronal]:
        """Empaqueta transacciones en espera, acopla estado de las 50 neuronas y mina bloque."""
        with self.lock:
            if not self.transacciones_pendientes: return None
            ultimo = self.obtener_ultimo_bloque()
            resumen_neuronas = {
                "activas": len(self.conversor.neuronas),
                "deriva_acumulada": round(self.conversor.deriva_acumulada, 6),
                "pasos_sesion": self.conversor.pasos_sesion, "minero": minero_id,
            }
            txs = list(self.transacciones_pendientes)
            self.transacciones_pendientes.clear()
            nuevo_bloque = BloqueNeuronal(
                indice=ultimo.indice + 1, hash_previo=ultimo.hash_bloque,
                transacciones=txs, estado_neuronal=resumen_neuronas, dificultad=self.dificultad,
            )
            if nuevo_bloque.minar_bloque():
                self.cadena.append(nuevo_bloque)
                self.guardar_ledger()
                return nuevo_bloque
            return None

    def transformar_ledger_a_pesos_neuronales(self) -> Dict[str, Any]:
        """Transduce todos los bloques y hashes criptograficos a pesos neuronales en PSNRL."""
        if not LEDGER_PATH.exists(): return {"total_bloques": 0, "norma_acumulada": 0.0, "npz_pesos": "", "json_meta": ""}
        with open(LEDGER_PATH, "r", encoding="utf-8") as f: ledger_data = json.load(f)
        bloques = ledger_data.get("cadena", [])
        norma_acum = 0.0
        # Propagar cada bloque directamente sin persistir en cada iteracion
        for b in bloques:
            sintesis = f"Bloque {b['indice']} | Hash: {b['hash_bloque']} | Merkle: {b['merkle_root']}"
            try:
                v = self.conversor.encoder.encode(sintesis)
                act, _ = self.conversor._propagar_todas_las_neuronas(v)
                _, norma_app, _ = self.conversor._actualizar_pesos_en_todas_las_neuronas(v, act, factor=1.0)
                norma_acum += norma_app
            except Exception: pass
        # Persistir UNA sola vez al final de la transformacion completa
        npz_path, json_path = self.conversor.persistir_pesos_en_psnrl(etiqueta="blockchain_ledger")
        print(f"  [PSNRL] {len(bloques)} bloques -> pesos neuronales | Norma total: {round(norma_acum,5)}")
        return {
            "total_bloques": len(bloques), "norma_acumulada": round(norma_acum, 5),
            "npz_pesos": str(npz_path.name), "json_meta": str(json_path.name),
        }

    def _bucle_actualizacion_continua(self) -> None:
        """Hilo de fondo que mantiene actualizando la red neuronal mientras la sesion este activa."""
        while self.actualizador_activo:
            time.sleep(12.0)
            if not self.actualizador_activo: break
            try:
                ult = self.obtener_ultimo_bloque()
                self.conversor.procesar_consulta_a_pesos(f"Latido Bloque #{ult.indice} Hash:{ult.hash_bloque[:16]}")
            except Exception: pass

    def arrancar_actualizador_red(self) -> None:
        """Inicia el sincronizador dinamico de pesos durante la sesion."""
        if not self.actualizador_activo:
            self.actualizador_activo = True
            self._hilo_actualizador = threading.Thread(target=self._bucle_actualizacion_continua, daemon=True)
            self._hilo_actualizador.start()

    def detener_actualizador_red(self) -> None:
        """Detiene el bucle de actualizacion."""
        self.actualizador_activo = False

    def cerrar_sesion_y_subir_ipfs(self) -> Dict[str, Any]:
        """Hook de cierre: persiste pesos y anuncia el estado real (H1, P0-1).

        Ya NO borra el ledger ni el PSNRL.  Si el shim IPFS reporta ok=False,
        emite un aviso honesto en lugar de anunciar sincronización completada.
        El borrado de datos de sesión sólo puede ocurrir mediante
        ``borrar_datos_sesion_confirmado(confirmado=True)`` con backup verificado.
        """
        self.detener_actualizador_red()
        # Checkpoint final de pesos antes de cerrar
        self.conversor.persistir_pesos_en_psnrl(etiqueta="cierre_sesion_blockchain")

        cid_ledger = None
        ipfs_ok = False
        ipfs_error = ""

        if LEDGER_PATH.exists():
            try:
                # H1: eliminar_local=False SIEMPRE; nunca borrar sin CID real verificado
                res_l = self.ipfs_mgr.almacenar_pesos(
                    origen=LEDGER_PATH,
                    nombre_modelo="blockchain_ledger_final",
                    eliminar_local=False,   # H1: shim no borra
                )
                cid_ledger = res_l.get("cid")
                ipfs_ok = res_l.get("ok", False)
                ipfs_error = res_l.get("error", "")
                if not ipfs_ok:
                    import logging as _log
                    _log.getLogger(__name__).warning(
                        "[BKSVCB] cerrar_sesion_y_subir_ipfs: IPFS no disponible — "
                        "ledger y PSNRL conservados en disco. Error: %s", ipfs_error
                    )
            except Exception as exc:  # pragma: no cover
                ipfs_error = str(exc)

        # Intentar subir PSNRL (el shim devolverá ok=False y no borrará nada)
        res_psnrl = self.ipfs_mgr.subir_y_limpiar_psnrl(forzar_borrado_sin_daemon=False)

        return {
            "cid_ledger": cid_ledger,
            "ledger_borrado": False,       # H1: nunca borrado en el cierre normal
            "ipfs_ok": ipfs_ok,
            "ipfs_error": ipfs_error,
            "cids_psnrl": res_psnrl.get("cids", []),
            "borrados": res_psnrl.get("borrados", []),  # [] con el shim H1
            "psnrl_ok": res_psnrl.get("ok", False),
        }

    def validar_cadena(self) -> Tuple[bool, Optional[str]]:
        """Verifica la integridad criptografica total de hashes, enlaces y Merkle roots."""
        for i in range(1, len(self.cadena)):
            act, prev = self.cadena[i], self.cadena[i - 1]
            if act.hash_previo != prev.hash_bloque: return False, f"Ruptura en #{act.indice}"
            if act.calcular_hash() != act.hash_bloque: return False, f"Hash corrupto en #{act.indice}"
            if act.calcular_merkle_root() != act.merkle_root: return False, f"Merkle invalido en #{act.indice}"
            prefijo = "0" * getattr(act, "dificultad", self.dificultad)
            if not act.hash_bloque.startswith(prefijo) and act.indice > 0:
                return False, f"PoW insuficiente en #{act.indice}"
        return True, None

    def guardar_ledger(self) -> bool:
        """Persiste toda la cadena en el archivo JSON ledger local de forma atomica."""
        data = {
            "version": __version__, "servidor": __server_name__,
            "total_bloques": len(self.cadena), "dificultad": self.dificultad,
            "cadena": [b.to_dict() for b in self.cadena],
        }
        try:
            tmp_path = LEDGER_PATH.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            tmp_path.replace(LEDGER_PATH)
            return True
        except Exception:
            return False

    def mostrar_cadena_hashes_terminal(self) -> None:
        """Muestra en terminal la cadena con el hash unico de cada bloque sin fechas."""
        print("\033[1;36m" + "=" * 74 + "\033[0m")
        print("  \033[1;32mLIBRO MAYOR DISTRIBUIDO - HASHES UNICOS DE BLOQUES (2026)\033[0m")
        print("\033[1;36m" + "=" * 74 + "\033[0m")
        for b in self.cadena:
            h_prev = b.hash_previo[:18] + "..." if len(b.hash_previo) > 18 else b.hash_previo
            print(f"  [Bloque #{b.indice:<2}] \033[1;33mHASH: {b.hash_bloque}\033[0m")
            print(f"            Prev: {h_prev} | Merkle: {b.merkle_root[:16]}... | Txs: {len(b.transacciones)}")
        print("\033[1;36m" + "-" * 74 + "\033[0m")


try:
    from STM_BKCH.bksvcb_net import (
        BlockchainHTTPHandler,
        BlockchainServerDaemon,
        get_blockchain_server,
        iniciar_servidor_blockchain,
    )
except ImportError:
    try:
        from .bksvcb_net import (
            BlockchainHTTPHandler,
            BlockchainServerDaemon,
            get_blockchain_server,
            iniciar_servidor_blockchain,
        )
    except ImportError:
        pass


