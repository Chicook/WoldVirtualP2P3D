"""Portal WebNodo mínimo de respaldo.

Sirve la portada, la descarga del visor y /api/info sin HttpListener, para
equipos donde HTTP.sys falla dentro de WPF. Escucha en 127.0.0.1:3030.
"""
from __future__ import annotations

import argparse
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

TOKEN = "wvp"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--puerto", type=int, default=3030)
    parser.add_argument("--raiz", default="")
    parser.add_argument("--exe", default="")
    args = parser.parse_args()

    raiz = Path(args.raiz or Path(__file__).resolve().parent / "public").resolve()
    exe = Path(args.exe).resolve() if args.exe else None
    if not exe or not exe.is_file():
        candidatos = list(Path.cwd().glob("DMWoldVirtualP2P3D*.exe"))
        exe = candidatos[0] if candidatos else None

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(raiz), **kw)

        def log_message(self, formato, *a):
            print(f"[webnodo] {self.address_string()} {formato % a}", flush=True)

        def _enviar(self, codigo: int, cuerpo: bytes, tipo: str):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            ruta = urlparse(self.path).path
            if ruta in ("/", "/index.html"):
                html = (raiz / "index.html").read_text(encoding="utf-8")
                html = html.replace("{{API_TOKEN}}", TOKEN)
                self._enviar(200, html.encode("utf-8"), "text/html; charset=utf-8")
                return
            if ruta == "/api/info":
                datos = {
                    "nombre": exe.name if exe else "DMWoldVirtualP2P3D.exe",
                    "version": "2.8.2",
                    "tamano_mb": round(exe.stat().st_size / (1024 * 1024), 1) if exe else 0,
                    "url_descarga": "/descargar",
                }
                self._enviar(200, json.dumps(datos).encode("utf-8"), "application/json")
                return
            if ruta.startswith("/descargar"):
                if not exe or not exe.is_file():
                    self._enviar(404, b"No hay visor disponible", "text/plain; charset=utf-8")
                    return
                self._enviar(200, exe.read_bytes(), "application/octet-stream")
                return
            return super().do_GET()

    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Handler)
    print(f"[webnodo] Portal en http://127.0.0.1:{args.puerto}/", flush=True)
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
