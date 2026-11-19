"""Respaldo del portal para equipos donde HTTP.sys falla en WPF."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import secrets
import select
import socket
from urllib.parse import parse_qs, quote, urlparse


def leer_json(ruta: Path | None) -> dict:
    try:
        if ruta is None:
            return {}
        with ruta.open(encoding="utf-8-sig") as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def version_numerica(texto: str) -> tuple | None:
    texto = texto.strip().lstrip("vV")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", texto):
        return None
    try:
        return tuple(int(parte) for parte in texto.split("."))
    except ValueError:
        return None


def url_http(texto: object) -> str:
    if not isinstance(texto, str) or any(c.isspace() or ord(c) < 32 for c in texto):
        return ""
    try:
        url = urlparse(texto)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            return ""
        url.port  # Rechazar puertos malformados.
        return texto
    except ValueError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--puerto", type=int, default=3030)
    parser.add_argument("--raiz", default="")
    parser.add_argument("--exe", default="")
    parser.add_argument("--release", default="")
    parser.add_argument("--sesion", default="")
    parser.add_argument("--relay", default="")
    args = parser.parse_args()

    raiz = Path(args.raiz or Path(__file__).resolve().parent / "public").resolve()
    exe = Path(args.exe).resolve() if args.exe else None
    release_path = Path(args.release).resolve() if args.release else None
    sesion_path = Path(args.sesion).resolve() if args.sesion else None
    relay_path = Path(args.relay).resolve() if args.relay else None
    token_independiente = secrets.token_hex(16) if release_path is None else ""

    def estado_release() -> dict:
        datos = leer_json(release_path)
        campos = ("nombre", "url", "version", "tamano_mb", "version_instalada", "api_token")
        if not all(isinstance(datos.get(c), str) for c in campos) or not datos.get("api_token"):
            return {}
        # El token va en un literal JavaScript de la portada.
        if not re.fullmatch(r"[0-9a-fA-F]{32}", datos["api_token"]):
            return {}
        if version_numerica(datos["version"]) is None or version_numerica(datos["version_instalada"]) is None:
            return {}
        if not datos["nombre"] or (datos["url"] and not url_http(datos["url"])):
            return {}
        return datos

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, formato, *a):
            print(f"[webnodo] {self.address_string()} {urlparse(self.path).path}", flush=True)

        def _enviar(self, codigo: int, cuerpo: bytes, tipo: str):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _json(self, codigo: int, datos: dict):
            self._enviar(codigo, json.dumps(datos).encode("utf-8"), "application/json; charset=utf-8")

        def _archivo(self, archivo: Path, tipo: str, nombre: str = ""):
            try:
                flujo = archivo.open("rb")
            except OSError:
                self._enviar(404, b"No disponible", "text/plain; charset=utf-8")
                return
            with flujo:
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(os.fstat(flujo.fileno()).st_size))
                self.send_header("Cache-Control", "no-store")
                if nombre:
                    self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(nombre, safe=""))
                self.end_headers()
                while bloque := flujo.read(1024 * 1024):
                    self.wfile.write(bloque)

        def _websocket(self, solicitud):
            relay = leer_json(relay_path)
            esperado = relay.get("invitacion", "")
            recibido = parse_qs(solicitud.query).get("invitacion", [""])[0]
            if not isinstance(esperado, str) or not esperado or not hmac.compare_digest(esperado.encode(), recibido.encode()):
                self._json(403, {"error": "forbidden"})
                return
            chat = solicitud.path.lower().startswith("/chat")
            puerto = relay.get("chat_port", 0) if chat else 8911
            if chat and (relay.get("chat_enabled") is not True or type(puerto) is not int or not 1 <= puerto <= 65535):
                self._json(503, {"error": "chat unavailable"})
                return
            clave = self.headers.get("Sec-WebSocket-Key", "")
            if not re.fullmatch(r"[A-Za-z0-9+/]{22}==", clave) or self.headers.get("Sec-WebSocket-Version") != "13":
                self._json(400, {"error": "invalid websocket"})
                return
            try:
                remoto = socket.create_connection(("127.0.0.1", puerto), timeout=10)
            except OSError:
                self._json(503, {"error": "world unavailable"})
                return
            with remoto:
                cabeceras = [f"GET {'/chat' if chat else '/'} HTTP/1.1", f"Host: 127.0.0.1:{puerto}", "Upgrade: websocket", "Connection: Upgrade", f"Sec-WebSocket-Key: {clave}", "Sec-WebSocket-Version: 13"]
                for nombre in ("Sec-WebSocket-Protocol", "Sec-WebSocket-Extensions"):
                    valor = self.headers.get(nombre, "")
                    if valor and not any(c in valor for c in "\r\n"):
                        cabeceras.append(f"{nombre}: {valor}")
                try:
                    remoto.sendall(("\r\n".join(cabeceras) + "\r\n\r\n").encode("ascii"))
                    respuesta = bytearray()
                    while b"\r\n\r\n" not in respuesta and len(respuesta) < 65536:
                        bloque = remoto.recv(4096)
                        if not bloque:
                            break
                        respuesta.extend(bloque)
                    if b"\r\n\r\n" not in respuesta or respuesta.split(b"\r\n", 1)[0] != b"HTTP/1.1 101 Switching Protocols":
                        self._json(502, {"error": "upgrade failed"})
                        return
                    self.connection.sendall(respuesta)
                    remoto.settimeout(None)
                    self.close_connection = True
                    while True:
                        disponibles, _, _ = select.select([self.connection, remoto], [], [])
                        for origen in disponibles:
                            bloque = origen.recv(65536)
                            if not bloque:
                                return
                            (remoto if origen is self.connection else self.connection).sendall(bloque)
                except (OSError, UnicodeError):
                    self.close_connection = True

        def do_GET(self):
            solicitud = urlparse(self.path)
            ruta = solicitud.path
            if self.headers.get("Upgrade", "").lower() == "websocket":
                self._websocket(solicitud)
                return
            datos = estado_release()
            token = datos.get("api_token", token_independiente)
            if ruta.startswith("/api/") and ruta != "/api/p2p-status":
                recibido = parse_qs(solicitud.query).get("token", [""])[0]
                if not token or not hmac.compare_digest(recibido.encode("utf-8"), token.encode("utf-8")):
                    self._json(403, {"error": "forbidden"})
                    return

            local = False
            if datos and exe is not None:
                local = version_numerica(datos["version"]) == version_numerica(datos["version_instalada"])
                try:
                    local = local and exe.is_file()
                    size_mb = f"{exe.stat().st_size / 1048576.0:.1f}" if local else datos["tamano_mb"]
                except OSError:
                    local = False
                    size_mb = datos["tamano_mb"]
            else:
                size_mb = datos.get("tamano_mb", "—")

            if ruta in ("/", "/index.html"):
                try:
                    html = (raiz / "index.html").read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    self._enviar(404, b"No disponible", "text/plain; charset=utf-8")
                    return
                html = html.replace("{{API_TOKEN}}", token)
                # La portada consulta la sesión por API; no se fabrica un túnel.
                html = html.replace("{{TUNNEL_URL}}", "")
                self._enviar(200, html.encode("utf-8"), "text/html; charset=utf-8")
            elif ruta == "/metaverso.jpg":
                self._archivo(raiz / "metaverso.jpg", "image/jpeg")
            elif ruta == "/api/info":
                self._json(200, {
                    "disponible": bool(datos) and (local or bool(datos["url"])),
                    "nombre": datos.get("nombre", ""),
                    "version": datos.get("version", ""),
                    "version_instalada": datos.get("version_instalada", ""),
                    "tamano_mb": size_mb,
                    "url_descarga": "/descargar",
                })
            elif ruta == "/api/p2p-status":
                tunnel = url_http(leer_json(sesion_path).get("myTunnelUrl"))
                if any(clave.lower() in ("invitacion", "tokenp2p")
                       for clave in parse_qs(urlparse(tunnel).query, keep_blank_values=True)):
                    tunnel = ""
                self._json(200, {
                    "online": bool(tunnel),
                    "tunnel_url": tunnel,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            elif ruta == "/descargar" or ruta.startswith("/descargar/"):
                if local:
                    self._archivo(exe, "application/octet-stream", datos["nombre"])
                elif datos and datos["url"]:
                    self.send_response(302)
                    self.send_header("Location", datos["url"])
                    self.send_header("Content-Length", "0")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                else:
                    self._enviar(503, b"No hay visor disponible", "text/plain; charset=utf-8")
            else:
                self._enviar(404, b"Not Found", "text/plain; charset=utf-8")

    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Handler)
    print(f"[webnodo] Portal en http://127.0.0.1:{args.puerto}/", flush=True)
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
