#!/usr/bin/env python3
"""Traspasa las 5 animaciones del rig jugable a los modelos Mixamo que no las tienen.

Los avatares jugables (gltfimport/avatares/*.gltf) son un rig de Blender con una capa
de controles IK, pero dentro llevan un esqueleto Mixamo (mixamorig8:*) con los mismos
65 huesos que los modelos nuevos (avtrnCRS/**/*.glb, prefijo mixamorigN:*). Las
animaciones animan esos 65 huesos, así que el traspaso se hace hueso a hueso.

No se copian valores absolutos: se copia el DELTA respecto a la pose de reposo de
cada esqueleto, lo que absorbe las diferencias de orientación de raíz y de unidades.

    q_nuevo(t) = q_reposo_nuevo * (q_reposo_viejo^-1 * q_viejo(t))
    t_nuevo(t) = t_reposo_nuevo + (t_viejo(t) - t_reposo_viejo) * 100   (m -> cm)

Solo se transfieren rotaciones de los 65 huesos y la traslación de Hips: en el
origen todo lo demás es constante y añadirlo solo engordaría el fichero.

El modelo de origen NO se modifica: se escribe `<nombre>_anim.glb` al lado.
"""

from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
FUENTE_GLTF = RAIZ / "gltfimport" / "avatares" / "AVMJ1.gltf"
DESTINO_GLOB = "avtrnCRS/GTLF_GODOT/GltfIMP/AVATARES/**/*.glb"
SUFIJO_SALIDA = "_anim"
ESCALA_UNIDADES = 100.0          # el rig viejo está en metros; los GLB nuevos, en cm
HUESO_RAIZ = "Hips"


# ── lectura/escritura de GLB ──────────────────────────────────────────────

def leer_glb(ruta: Path) -> tuple[dict, bytearray]:
    datos = ruta.read_bytes()
    magic, version, _ = struct.unpack_from("<III", datos, 0)
    if magic != 0x46546C67 or version != 2:
        raise ValueError(f"{ruta}: no es un GLB 2.0")
    offset, gltf, binario = 12, None, bytearray()
    while offset < len(datos):
        longitud, tipo = struct.unpack_from("<II", datos, offset)
        trozo = datos[offset + 8: offset + 8 + longitud]
        if tipo == 0x4E4F534A:
            gltf = json.loads(trozo.decode("utf-8"))
        elif tipo == 0x004E4942:
            binario = bytearray(trozo)
        offset += 8 + longitud
    if gltf is None:
        raise ValueError(f"{ruta}: GLB sin bloque JSON")
    return gltf, binario


def escribir_glb(ruta: Path, gltf: dict, binario: bytearray) -> None:
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binario = bytearray(binario)
    binario += b"\0" * (-len(binario) % 4)
    total = 12 + 8 + len(js) + (8 + len(binario) if binario else 0)
    with ruta.open("wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A))
        f.write(js)
        if binario:
            f.write(struct.pack("<II", len(binario), 0x004E4942))
            f.write(binario)


# ── accessors ─────────────────────────────────────────────────────────────

COMPONENTES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
TIPO_FLOAT = 5126


def leer_accessor(gltf: dict, binario: bytes, indice: int) -> np.ndarray:
    acc = gltf["accessors"][indice]
    if acc["componentType"] != TIPO_FLOAT:
        raise ValueError(f"accessor {indice}: solo se soportan float32")
    n = COMPONENTES[acc["type"]]
    bv = gltf["bufferViews"][acc["bufferView"]]
    inicio = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or n * 4
    crudo = np.frombuffer(binario, dtype=np.uint8)
    if stride == n * 4:
        datos = np.frombuffer(binario, dtype="<f4", count=acc["count"] * n, offset=inicio).reshape(-1, n)
    else:
        datos = np.stack([
            np.frombuffer(binario, dtype="<f4", count=n, offset=inicio + i * stride)
            for i in range(acc["count"])
        ])
    return datos.astype(np.float64)


def añadir_accessor(gltf: dict, binario: bytearray, datos: np.ndarray, tipo: str) -> int:
    datos = np.ascontiguousarray(datos, dtype="<f4")
    binario += b"\0" * (-len(binario) % 4)
    gltf["bufferViews"].append({
        "buffer": 0,
        "byteOffset": len(binario),
        "byteLength": datos.nbytes,
    })
    binario += datos.tobytes()
    valores = datos.reshape(-1, datos.shape[-1]) if datos.ndim > 1 else datos.reshape(-1, 1)
    gltf["accessors"].append({
        "bufferView": len(gltf["bufferViews"]) - 1,
        "componentType": TIPO_FLOAT,
        "count": int(valores.shape[0]),
        "type": tipo,
        "min": [float(v) for v in valores.min(axis=0)],
        "max": [float(v) for v in valores.max(axis=0)],
    })
    return len(gltf["accessors"]) - 1


# ── cuaterniones ──────────────────────────────────────────────────────────

def normalizar(q: np.ndarray) -> np.ndarray:
    norma = np.linalg.norm(q, axis=-1, keepdims=True)
    norma[norma == 0] = 1.0
    return q / norma


def conjugar(q: np.ndarray) -> np.ndarray:
    return np.concatenate([-q[..., :3], q[..., 3:]], axis=-1)


def multiplicar(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ax, ay, az, aw = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    bx, by, bz, bw = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ], axis=-1)


def traslacion(valor) -> np.ndarray:
    return np.array(valor, dtype=np.float64) if valor else np.zeros(3)


def rotacion(valor) -> np.ndarray:
    return np.array(valor, dtype=np.float64) if valor else np.array([0.0, 0.0, 0.0, 1.0])


# ── traspaso ──────────────────────────────────────────────────────────────

def leer_fuente() -> tuple[dict, bytes]:
    gltf = json.loads(FUENTE_GLTF.read_text(encoding="utf-8"))
    binario = (FUENTE_GLTF.parent / gltf["buffers"][0]["uri"]).read_bytes()
    return gltf, binario


def huesos_por_nombre(gltf: dict, prefijo: str) -> dict[str, int]:
    """Devuelve {nombre_sin_prefijo: índice_de_nodo} para los huesos del skin."""
    skin = gltf["skins"][0]
    salida = {}
    for indice in skin["joints"]:
        nombre = gltf["nodes"][indice].get("name", "")
        if ":" in nombre:
            pre, _, resto = nombre.partition(":")
            if pre.startswith(prefijo):
                salida[resto] = indice
    return salida


def prefijo_mixamo(gltf: dict) -> str:
    for indice in gltf["skins"][0]["joints"]:
        nombre = gltf["nodes"][indice].get("name", "")
        if nombre.startswith("mixamorig"):
            return nombre.split(":")[0]
    raise ValueError("el skin no contiene huesos mixamorig")


def traspasar(destino: Path, fuente: dict, bin_fuente: bytes) -> dict:
    gltf, binario = leer_glb(destino)

    prefijo_viejo = prefijo_mixamo(fuente)
    huesos_viejos = huesos_por_nombre(fuente, prefijo_viejo)
    huesos_nuevos = huesos_por_nombre(gltf, prefijo_mixamo(gltf))

    comunes = sorted(set(huesos_viejos) & set(huesos_nuevos))
    faltan = sorted(set(huesos_viejos) - set(huesos_nuevos))
    if len(comunes) < 60:
        raise ValueError(f"{destino.name}: solo {len(comunes)} huesos en común")

    reposo = {}
    for hueso in comunes:
        viejo = fuente["nodes"][huesos_viejos[hueso]]
        nuevo = gltf["nodes"][huesos_nuevos[hueso]]
        reposo[hueso] = (
            rotacion(viejo.get("rotation")),
            traslacion(viejo.get("translation")),
            rotacion(nuevo.get("rotation")),
            traslacion(nuevo.get("translation")),
        )

    gltf.setdefault("animations", [])
    for animacion in fuente["animations"]:
        tiempos: dict[int, int] = {}
        samplers, canales = [], []
        for canal in animacion["channels"]:
            nodo_viejo = canal["target"]["node"]
            nombre = fuente["nodes"][nodo_viejo].get("name", "")
            if not nombre.startswith(prefijo_viejo + ":"):
                continue
            hueso = nombre.partition(":")[2]
            if hueso not in reposo:
                continue
            ruta = canal["target"]["path"]
            if ruta not in ("rotation", "translation"):
                continue
            if ruta == "translation" and hueso != HUESO_RAIZ:
                continue        # constante en el origen: no aporta y engorda el fichero

            sampler = animacion["samplers"][canal["sampler"]]
            entrada = sampler["input"]
            if entrada not in tiempos:
                tiempos[entrada] = añadir_accessor(gltf, binario, leer_accessor(fuente, bin_fuente, entrada), "SCALAR")
            valores_viejos = leer_accessor(fuente, bin_fuente, sampler["output"])
            q_rep_viejo, t_rep_viejo, q_rep_nuevo, t_rep_nuevo = reposo[hueso]

            if ruta == "rotation":
                delta = multiplicar(conjugar(q_rep_viejo)[None, :], normalizar(valores_viejos))
                nuevos = normalizar(multiplicar(q_rep_nuevo[None, :], delta))
                tipo = "VEC4"
            else:
                delta = (valores_viejos - t_rep_viejo[None, :]) * ESCALA_UNIDADES
                nuevos = t_rep_nuevo[None, :] + delta
                tipo = "VEC3"

            salida = añadir_accessor(gltf, binario, nuevos, tipo)
            samplers.append({
                "input": tiempos[entrada],
                "output": salida,
                "interpolation": sampler.get("interpolation", "LINEAR"),
            })
            canales.append({
                "sampler": len(samplers) - 1,
                "target": {"node": huesos_nuevos[hueso], "path": ruta},
            })

        if canales:
            gltf["animations"].append({
                "name": animacion["name"],
                "samplers": samplers,
                "channels": canales,
            })

    gltf["buffers"][0]["byteLength"] = len(binario)
    salida = destino.with_name(destino.stem + SUFIJO_SALIDA + destino.suffix)
    escribir_glb(salida, gltf, binario)
    return {"salida": salida.name, "huesos": len(comunes), "faltan": faltan,
            "clips": [a["name"] for a in gltf["animations"]]}


def main() -> int:
    fuente, bin_fuente = leer_fuente()
    objetivos = sorted(RAIZ.glob(DESTINO_GLOB))
    if not objetivos:
        print("No hay GLB objetivo", file=sys.stderr)
        return 1
    for destino in objetivos:
        try:
            info = traspasar(destino, fuente, bin_fuente)
            extra = f" (sin equivalente: {', '.join(info['faltan'])})" if info["faltan"] else ""
            print(f"{destino.name:12} -> {info['salida']:20} {info['huesos']} huesos, "
                  f"{len(info['clips'])} clips{extra}")
        except Exception as error:      # un modelo roto no debe abortar el resto
            print(f"{destino.name:12} ERROR {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
