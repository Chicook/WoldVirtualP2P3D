"""Firma asimetrica (Ed25519) para la cadena de release.

El update OTA se conforma hoy con un ``SHA256SUMS``; eso detecta corrupcion pero
no la **suplantacion** del canal (quien controla el origen puede reescribir
tambien el hash). Este modulo aporta el primitivo que falta, contenido en
``STM_DEF``: verificar (y, para el pipeline, producir) una firma **Ed25519** del
binario contra una clave publica.

El modulo es **autocontenido**: usa la libreria ``cryptography`` cuando esta
disponible y, si no lo esta, recurre a la implementacion Ed25519 de referencia
(RFC 8032) incluida mas abajo. Asi la firma funciona sin instalar nada y todo el
primitivo vive dentro de ``STM_DEF``. La implementacion pura es correcta pero no
es constante en el tiempo; para el pipeline conviene tener ``cryptography``.

Uso como verificador:

    python -m STM_HRTS.STM_DEF firma --binario <f> --firma <b64> --clave <b64>

y, para preparar claves/firmas en el pipeline:

    python -m STM_HRTS.STM_DEF firma --generar
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from pathlib import Path
from typing import Dict, Optional, Tuple

#: Algoritmo de firma soportado.
ALGORITMO = "ed25519"


def _ed25519() -> Tuple[Optional[object], Optional[object], Optional[object]]:
    """Carga perezosa de ``cryptography``; ``(None, None, None)`` si falta."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except Exception:
        return None, None, None
    return Ed25519PrivateKey, Ed25519PublicKey, InvalidSignature


def algoritmo_disponible() -> bool:
    """True siempre: la firma Ed25519 esta operativa (``cryptography`` o respaldo)."""
    return True


# --- Ed25519 de referencia (RFC 8032) — respaldo sin dependencias ----------
# Curva de Edwards retorcida edwards25519 y su orden. Aritmetica con enteros de
# Python: correcta y sin dependencias, a costa de ser mas lenta que una libreria.
_Q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493


def _p_inv(x: int) -> int:
    return pow(x, _Q - 2, _Q)


_P_D = (-121665 * _p_inv(121666)) % _Q
_P_I = pow(2, (_Q - 1) // 4, _Q)


def _p_xrecover(y: int) -> int:
    """Recupera la coordenada x de un punto a partir de su y."""
    xx = (y * y - 1) * _p_inv(_P_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _P_I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_P_BY = (4 * _p_inv(5)) % _Q
_P_B: Tuple[int, int] = (_p_xrecover(_P_BY) % _Q, _P_BY)


def _p_edwards(punto: Tuple[int, int], otro: Tuple[int, int]) -> Tuple[int, int]:
    """Suma de dos puntos en la curva de Edwards retorcida."""
    x1, y1 = punto
    x2, y2 = otro
    k = _P_D * x1 * x2 * y1 * y2 % _Q
    x3 = (x1 * y2 + x2 * y1) * _p_inv(1 + k) % _Q
    y3 = (y1 * y2 + x1 * x2) * _p_inv(1 - k) % _Q
    return (x3 % _Q, y3 % _Q)


def _p_scalarmult(punto: Tuple[int, int], escalar: int) -> Tuple[int, int]:
    """Multiplicacion escalar (doble y suma, iterativa)."""
    resultado: Tuple[int, int] = (0, 1)
    acumulado = punto
    while escalar > 0:
        if escalar & 1:
            resultado = _p_edwards(resultado, acumulado)
        acumulado = _p_edwards(acumulado, acumulado)
        escalar >>= 1
    return resultado


def _p_encodepoint(punto: Tuple[int, int]) -> bytes:
    x, y = punto
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _p_decodepoint(crudo: bytes) -> Tuple[int, int]:
    y = int.from_bytes(crudo, "little") & ((1 << 255) - 1)
    x = _p_xrecover(y)
    if (x & 1) != ((crudo[31] >> 7) & 1):
        x = _Q - x
    return (x, y)


def _p_expandir(semilla: bytes) -> Tuple[bytes, int]:
    """Deriva el hash y el escalar secreto a partir de la semilla de 32 bytes."""
    h = hashlib.sha512(semilla).digest()
    a = 2 ** 254 + sum(2 ** i * ((h[i >> 3] >> (i & 7)) & 1) for i in range(3, 254))
    return h, a


def _p_publica(semilla: bytes) -> bytes:
    _, a = _p_expandir(semilla)
    return _p_encodepoint(_p_scalarmult(_P_B, a))


def _p_firmar(datos: bytes, semilla: bytes) -> bytes:
    h, a = _p_expandir(semilla)
    publica = _p_encodepoint(_p_scalarmult(_P_B, a))
    r = int.from_bytes(hashlib.sha512(h[32:64] + datos).digest(), "little") % _L
    punto_r = _p_scalarmult(_P_B, r)
    s = (r + int.from_bytes(
        hashlib.sha512(_p_encodepoint(punto_r) + publica + datos).digest(), "little"
    ) * a) % _L
    return _p_encodepoint(punto_r) + s.to_bytes(32, "little")


def _p_verificar(datos: bytes, firma: bytes, clave_publica: bytes) -> bool:
    if len(firma) != 64 or len(clave_publica) != 32:
        return False
    s = int.from_bytes(firma[32:64], "little")
    if s >= _L:
        return False
    try:
        punto_a = _p_decodepoint(clave_publica)
        punto_r = _p_decodepoint(firma[:32])
    except Exception:
        return False
    h = int.from_bytes(
        hashlib.sha512(firma[:32] + clave_publica + datos).digest(), "little"
    ) % _L
    return _p_scalarmult(_P_B, s) == _p_edwards(punto_r, _p_scalarmult(punto_a, h))


# --- API publica -----------------------------------------------------------
def _b64(texto: str) -> bytes:
    return base64.b64decode((texto or "").strip(), validate=True)


def huella_clave(clave_publica_b64: str) -> str:
    """Huella SHA-256 de una clave publica (hex); cadena vacia si es invalida."""
    try:
        return hashlib.sha256(_b64(clave_publica_b64)).hexdigest()
    except Exception:
        return ""


def verificar_bytes(datos: bytes, firma_b64: str, clave_publica_b64: str) -> bool:
    """True si ``firma_b64`` es una firma Ed25519 valida de ``datos``.

    *Fail-closed*: devuelve ``False`` si la firma no cuadra o si la clave/firma
    no son decodificables. Usa ``cryptography`` si esta; si no, el respaldo puro.
    """
    _, publica, invalida = _ed25519()
    try:
        firma = _b64(firma_b64)
        clave_publica = _b64(clave_publica_b64)
    except Exception:
        return False
    if publica is not None:
        try:
            publica.from_public_bytes(clave_publica).verify(firma, datos)
            return True
        except (invalida, ValueError, TypeError):
            return False
    return _p_verificar(datos, firma, clave_publica)


def firmar_bytes(datos: bytes, clave_privada_b64: str) -> str:
    """Firma ``datos`` con una clave privada Ed25519 (semilla de 32 bytes) en b64."""
    privada, _, _ = _ed25519()
    semilla = _b64(clave_privada_b64)
    if privada is not None:
        return base64.b64encode(privada.from_private_bytes(semilla).sign(datos)).decode("ascii")
    return base64.b64encode(_p_firmar(datos, semilla)).decode("ascii")


def generar_claves() -> Dict[str, str]:
    """Genera un par Ed25519 nuevo y lo devuelve en base64 (para el pipeline)."""
    privada, _, _ = _ed25519()
    if privada is None:
        semilla = secrets.token_bytes(32)
        return {
            "privada": base64.b64encode(semilla).decode("ascii"),
            "publica": base64.b64encode(_p_publica(semilla)).decode("ascii"),
        }
    from cryptography.hazmat.primitives import serialization

    clave = privada.generate()
    privada_b64 = base64.b64encode(clave.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )).decode("ascii")
    publica_b64 = base64.b64encode(clave.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )).decode("ascii")
    return {"privada": privada_b64, "publica": publica_b64}


def verificar_fichero(ruta: Path, firma_b64: str, clave_publica_b64: str) -> Dict[str, object]:
    """Verifica la firma de un fichero y resume el resultado.

    Devuelve ``disponible`` (siempre ``True``: la firma esta operativa),
    ``firma_ok`` (``True``/``False``), el ``sha256`` del binario y un ``mensaje``.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        return {
            "disponible": True, "firma_ok": False, "algoritmo": ALGORITMO,
            "sha256": "", "ruta": str(ruta), "mensaje": f"no existe el fichero {ruta}",
        }
    datos = ruta.read_bytes()
    ok = verificar_bytes(datos, firma_b64, clave_publica_b64)
    return {
        "disponible": True, "firma_ok": ok, "algoritmo": ALGORITMO,
        "sha256": hashlib.sha256(datos).hexdigest(), "ruta": str(ruta),
        "mensaje": "firma valida" if ok else "firma INVALIDA o clave publica incorrecta",
    }


__all__ = [
    "ALGORITMO", "algoritmo_disponible", "huella_clave", "verificar_bytes",
    "firmar_bytes", "generar_claves", "verificar_fichero",
]
