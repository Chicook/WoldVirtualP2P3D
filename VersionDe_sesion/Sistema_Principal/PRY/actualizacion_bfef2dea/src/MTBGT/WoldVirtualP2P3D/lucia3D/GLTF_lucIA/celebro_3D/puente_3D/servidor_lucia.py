"""Puente TCP entre Godot (LucIA 3D) y el nucleo neuronal con Ollama local.

Godot envia lineas JSON y recibe eventos NDJSON:
  -> {"tipo": "consulta", "texto": "..."}
  <- {"tipo": "estado", "estado": "pensando"}
  <- {"tipo": "token", "texto": "<respuesta ya reformulada>"}
  <- {"tipo": "estado", "estado": "sintetizando"}
  <- {"tipo": "voz", "pcm": "<base64>", "rate": 24000, "canales": 1, "duracion": 3.2}
  <- {"tipo": "aviso", "mensaje": "..."}
  <- {"tipo": "fin", "texto": "...", "modelo": "...", "ms": 1234,
      "nucleo": {"neuronas": 50, "deriva": 0.001, "tono": "...", "valencia": 0.2},
      "metricas": {...}}
  <- {"tipo": "error", "mensaje": "..."}

Uso:
  python servidor_lucia.py
  python servidor_lucia.py --modelo qwen2.5:3b --puerto 8765
  python servidor_lucia.py --sin-voz
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nucleo.orquestador_lucia import NucleoLucia
from voz_lucia import precargar_voz, sintetizar_voz

HOST_POR_DEFECTO = "127.0.0.1"
PUERTO_POR_DEFECTO = 8765
OLLAMA_URL = os.getenv("LUCIA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")

# Preferencia por equilibrio calidad/VRAM; los *-coder se evitan para conversacion.
PREFERENCIA_MODELOS = (
    "qwen2.5:3b",
    "qwen2.5:1.5b",
    "llama3.2:1b",
    "gemma2:2b",
    "qwen3:1.7b",
    "qwen2.5:0.5b",
    "qwen2.5:7b",
    "qwen2.5:latest",
    "qwen3.5:latest",
)

SISTEMA = (
    "Eres LucIA, la inteligencia artificial 3D de WoldVirtualP2P3D. "
    "Hablas en español natural, en primera persona, con frases completas y breves "
    "(dos a cuatro frases). Eres cercana, segura y curiosa. No empieces con muletillas "
    "ni expliques tu arquitectura salvo que te lo pidan. Devuelve solo tu respuesta hablada. "
    "Tienes herramientas reales de refactor (RFPRMN) y puedes analizarte y modificarte: "
    "nunca respondas que no puedes refactorizar ni que solo tu equipo puede cambiarte; "
    "si falta la ruta de un archivo, pídela."
)

OPCIONES_MODELO: Dict[str, Any] = {
    "temperature": 0.55,
    "top_p": 0.9,
    "num_ctx": 2048,
    "num_predict": 180,
}


def _ollama(ruta: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Any:
    datos = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    peticion = urllib.request.Request(
        f"{OLLAMA_URL}{ruta}",
        data=datos,
        headers={"Content-Type": "application/json"},
        method="POST" if datos is not None else "GET",
    )
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def modelos_instalados() -> List[str]:
    try:
        datos = _ollama("/api/tags", timeout=3.0)
    except Exception:
        return []
    return [str(m.get("name", "")) for m in datos.get("models", []) if m.get("name")]


def elegir_modelo(forzado: str = "") -> str:
    if forzado:
        return forzado
    instalados = {m.lower(): m for m in modelos_instalados()}
    for candidato in PREFERENCIA_MODELOS:
        if candidato in instalados:
            return instalados[candidato]
    for nombre in instalados.values():
        minuscula = nombre.lower()
        if "coder" not in minuscula and "starcoder" not in minuscula:
            return nombre
    if instalados:
        return next(iter(instalados.values()))
    raise RuntimeError(
        "No hay modelos en Ollama. Descarga uno pequeno con: ollama pull qwen2.5:3b"
    )


def precalentar(modelo: str) -> None:
    inicio = time.perf_counter()
    print(f"[cerebro] Cargando {modelo} en VRAM...")
    try:
        _ollama(
            "/api/chat",
            {
                "model": modelo,
                "stream": False,
                "keep_alive": "10m",
                "messages": [{"role": "user", "content": "hola"}],
                "options": {**OPCIONES_MODELO, "num_predict": 1},
            },
            timeout=300.0,
        )
        print(f"[cerebro] Modelo cargado en VRAM en {time.perf_counter() - inicio:.1f} s")
    except Exception as error:
        print(f"[cerebro] No se pudo precalentar el modelo: {error}")


def _cargar_puente():
    """Carga el puente de comandos de LucIA (STMGNRL) si está disponible.

    El servidor vive dentro del proyecto Godot, así que se sube por los
    directorios hasta encontrar ``STMGNRL/mainLCSTM.py`` en vez de fiarse de
    una profundidad fija.
    """
    for base in Path(__file__).resolve().parents:
        if (base / "STMGNRL" / "mainLCSTM.py").is_file():
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
            break
    try:
        from STMGNRL.mainLCSTM import LucIAPuenteComandos

        return LucIAPuenteComandos()
    except Exception as error:
        print(f"[cerebro] Puente de comandos no disponible: {error}")
        return None


class ServidorLucIA:
    def __init__(
        self,
        host: str,
        puerto: int,
        modelo: str,
        nucleo: NucleoLucia,
        voz_habilitada: bool = True,
    ) -> None:
        self.host = host
        self.puerto = puerto
        self.modelo = modelo
        self.nucleo = nucleo
        self.voz_habilitada = voz_habilitada
        self._turno = threading.Lock()
        self.puente = _cargar_puente()
        if self.puente is not None and self.puente.disponible:
            print("[cerebro] Puente de comandos RFPRMN: ACTIVO")
        else:
            print("[cerebro] Puente de comandos RFPRMN: no disponible")

    def servir(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
            servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servidor.bind((self.host, self.puerto))
            servidor.listen(4)
            print(f"[cerebro] Escuchando en {self.host}:{self.puerto}")
            print(f"[cerebro] Modelo: {self.modelo} | Ollama: {OLLAMA_URL}")
            estado = self.nucleo.estado()
            print(
                f"[cerebro] Nucleo: {estado['neuronas']} sinapsis | "
                f"deriva {estado['deriva']:.6f} | sesion {estado['sesion']}"
            )
            print(f"[cerebro] Voz: {'ACTIVA' if self.voz_habilitada else 'desactivada'}")
            print("[cerebro] Esperando a Godot... (Ctrl+C para salir)")
            while True:
                conexion, direccion = servidor.accept()
                print(f"[cerebro] Godot conectado desde {direccion[0]}:{direccion[1]}")
                threading.Thread(
                    target=self._atender, args=(conexion,), daemon=True
                ).start()

    def _atender(self, conexion: socket.socket) -> None:
        with conexion:
            conexion.settimeout(None)
            self._enviar(conexion, {"tipo": "hola", "protocolo": 1, "modelo": self.modelo})
            lector = conexion.makefile("r", encoding="utf-8", errors="replace")
            try:
                for linea in lector:
                    linea = linea.strip()
                    if not linea:
                        continue
                    try:
                        mensaje = json.loads(linea)
                    except json.JSONDecodeError:
                        self._enviar(conexion, {"tipo": "error", "mensaje": "JSON inválido"})
                        continue
                    tipo = str(mensaje.get("tipo", ""))
                    if tipo == "ping":
                        self._enviar(conexion, {"tipo": "pong"})
                    elif tipo == "consulta":
                        texto = str(mensaje.get("texto", "")).strip()
                        if texto:
                            self._responder(conexion, texto)
                        else:
                            self._enviar(conexion, {"tipo": "error", "mensaje": "Consulta vacía"})
            except (ConnectionError, OSError):
                pass
            finally:
                print("[cerebro] Godot desconectado")

    @staticmethod
    def _enviar(conexion: socket.socket, evento: Dict[str, Any]) -> None:
        conexion.sendall((json.dumps(evento, ensure_ascii=False) + "\n").encode("utf-8"))

    @staticmethod
    def _relato(atencion: Dict[str, Any]) -> str:
        """Convierte lo que hizo el puente en contexto para el modelo."""
        accion = atencion.get("accion", "")
        if atencion.get("ok"):
            if accion == "autoanalisis":
                datos = atencion.get("datos", {})
                return ("Te has analizado con tu agente. Estado interno: "
                        f"{json.dumps(datos, ensure_ascii=False)[:900]}. "
                        "Responde contando lo que has hecho, sin decir que no puedes.")
            return (f"Acabas de ejecutar `{accion}` sobre "
                    f"{atencion.get('ruta', '')} con utilidad "
                    f"{atencion.get('utilidad', 0)}. Confirma lo hecho con "
                    "naturalidad y di el resultado.")
        motivo = atencion.get("motivo", "")
        if "ruta" in motivo.lower():
            return ("La peticion requiere un archivo, pero no lo has encontrado. "
                    "Pide la ruta exacta en una frase, sin excusas.")
        if "umbral" in motivo:
            return (f"Has evaluado `{accion}` y la has descartado: {motivo}. "
                    "No es que no puedas: es que no compensa (por ejemplo, el "
                    "archivo ya esta documentado). Dilo asi, como decision tuya.")
        return (f"No has podido ejecutar `{accion}`: {motivo}. "
                "Explica el motivo real en una frase.")

    def _responder(self, conexion: socket.socket, texto: str) -> None:
        inicio = time.perf_counter()
        self._enviar(conexion, {"tipo": "estado", "estado": "pensando"})
        try:
            info = self.nucleo.preparar_turno(texto)
        except Exception as error:
            self._enviar(
                conexion,
                {"tipo": "error", "mensaje": f"Fallo el nucleo neuronal: {error}"},
            )
            return

        mensajes = [{"role": "system", "content": SISTEMA}]
        if self.puente is not None:
            mensajes.append({"role": "system",
                             "content": self.puente.capacidades()})
            atencion = self.puente.atender(texto)
            if atencion is not None:
                mensajes.append({"role": "system", "content": self._relato(atencion)})
        mensajes += [
            {"role": "system", "content": self.nucleo.contexto_para_prompt(info)},
            {"role": "user", "content": texto},
        ]
        carga = {
            "model": self.modelo,
            "stream": True,
            "keep_alive": "10m",
            "messages": mensajes,
            "options": OPCIONES_MODELO,
        }
        peticion = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=json.dumps(carga, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        fragmentos: List[str] = []
        try:
            with self._turno, urllib.request.urlopen(peticion, timeout=300.0) as flujo:
                for cruda in flujo:
                    if not cruda.strip():
                        continue
                    evento = json.loads(cruda.decode("utf-8"))
                    trozo = str(evento.get("message", {}).get("content", ""))
                    if trozo:
                        fragmentos.append(trozo)
                    if evento.get("done"):
                        break
        except urllib.error.URLError as error:
            self._enviar(
                conexion,
                {"tipo": "error", "mensaje": f"Ollama no responde ({error.reason})"},
            )
            return
        except Exception as error:
            self._enviar(conexion, {"tipo": "error", "mensaje": f"Fallo la generacion: {error}"})
            return

        crudo = "".join(fragmentos).strip()
        if not crudo:
            self._enviar(conexion, {"tipo": "error", "mensaje": "El modelo devolvio una respuesta vacia"})
            return

        ms_generacion = (time.perf_counter() - inicio) * 1000.0
        try:
            respuesta, metricas = self.nucleo.procesar_respuesta(
                texto, crudo, info, ms_generacion, self.modelo
            )
        except Exception as error:
            self._enviar(
                conexion,
                {"tipo": "error", "mensaje": f"Fallo la reformulacion neuronal: {error}"},
            )
            return

        self._enviar(conexion, {"tipo": "token", "texto": respuesta})
        nucleo = metricas.get("nucleo", {})

        if self.voz_habilitada:
            self._enviar(conexion, {"tipo": "estado", "estado": "sintetizando"})
            audio = sintetizar_voz(respuesta)
            if audio:
                self._enviar(conexion, {"tipo": "voz", **audio})
                print(
                    f"[voz] {audio['backend']} | {audio['duracion']} s | "
                    f"{audio['ms']} ms | {audio['rate']} Hz"
                )
            else:
                self._enviar(conexion, {"tipo": "aviso", "mensaje": "No se pudo sintetizar la voz"})

        milisegundos = int((time.perf_counter() - inicio) * 1000)
        self._enviar(
            conexion,
            {
                "tipo": "fin",
                "texto": respuesta,
                "modelo": self.modelo,
                "ms": milisegundos,
                "nucleo": nucleo,
                "metricas": metricas,
            },
        )
        print(
            f"[nucleo] Turno {info.get('turno')} | tono {nucleo.get('tono')} | "
            f"valencia {float(nucleo.get('valencia', 0.0)):+.3f} | "
            f"deriva {float(nucleo.get('deriva', 0.0)):.6f} | "
            f"RPLC {metricas.get('tiempo_rplc_ms', 0)} ms | "
            f"calidad {metricas.get('calidad', 0):.2f}"
        )
        print(f"[cerebro] Turno respondido en {milisegundos} ms: {respuesta[:90]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Puente socket Ollama <-> Godot para LucIA")
    parser.add_argument("--host", default=HOST_POR_DEFECTO)
    parser.add_argument("--puerto", type=int, default=PUERTO_POR_DEFECTO)
    parser.add_argument("--modelo", default=os.getenv("LUCIA_MODELO", ""))
    parser.add_argument("--sin-precalentar", action="store_true")
    parser.add_argument("--sin-voz", action="store_true")
    args = parser.parse_args()

    try:
        modelo = elegir_modelo(args.modelo)
    except Exception as error:
        print(f"[cerebro] {error}")
        return 1

    try:
        nucleo = NucleoLucia()
    except Exception as error:
        print(f"[cerebro] No se pudo iniciar el nucleo neuronal: {error}")
        return 1

    if not args.sin_precalentar:
        threading.Thread(target=precalentar, args=(modelo,), daemon=True).start()
    if not args.sin_voz:
        threading.Thread(target=precargar_voz, daemon=True).start()

    try:
        ServidorLucIA(
            args.host,
            args.puerto,
            modelo,
            nucleo,
            voz_habilitada=not args.sin_voz,
        ).servir()
    except KeyboardInterrupt:
        print("\n[cerebro] Puente detenido")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
