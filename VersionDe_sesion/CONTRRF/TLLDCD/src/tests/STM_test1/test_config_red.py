"""U4 · ConfigRed: una sola tabla de puertos para los dos lenguajes.

El producto reparte cinco números por C# (WPF + Avalonia + Nucleo) y por Godot
(GDScript): el WebSocket del motor, la baliza UDP de LAN, la API del nodo P2P,
el rango del portal y el relay de chat. Hasta U4 cada ficha escribía su literal
y la regla de «este puerto no escucha el mundo, reescríbelo a 8911» estaba
copiada tres veces (WPF `TryParseConnectionTarget`, Avalonia
`LanzadorMundo.TryParsearDestino` y `Red.parsear_url_host_puerto`).

El plan pedía «un único `ConfigRed` leído por `Red.gd` y por el C#». Un fichero
compartido en tiempo de ejecución (JSON) habría añadido un modo de fallo nuevo
—ausencia del fichero, export al PCK— y el C# no puede leer `res://`. La fuente
única se implementa entonces como: **una tabla por lenguaje** y **esta prueba**
que las obliga a coincidir. Si alguien cambia 8911 en un lado, CI lo para.

Estilo de la casa (inspección de fuente), como `test_h2_h3_red.py`.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2]

CONFIG_CS = SRC_DIR / "VSC#" / "Nucleo" / "RedP2P" / "ConfigRed.cs"
RED_GD = SRC_DIR / "MTBGT" / "WoldVirtualP2P3D" / "gdscrip" / "Red.gd"

# Los números que viajan entre los dos lenguajes.
PUERTOS = {
    "motor_ws": 8911,
    "baliza_udp": 8912,
    "api_p2p": 7890,
    "portal_min": 3030,
    "portal_max": 3040,
    "chat": 8920,
}

# Pares (nombre en ConfigRed.cs, nombre en Red.gd) para los números compartidos.
ESPEJO = [
    ("PuertoMotorWs", "PUERTO_WS", "motor_ws"),
    ("PuertoBalizaUdp", "PUERTO_BEACON", "baliza_udp"),
    ("PuertoApiP2P", "PUERTO_API_P2P", "api_p2p"),
    ("PuertoPortal", "PUERTO_PORTAL_MIN", "portal_min"),
    ("PuertoPortalMax", "PUERTO_PORTAL_MAX", "portal_max"),
]

# Ficheros que usan puertos sin declararlos: no deben llevar literales sueltos.
CONSUMIDORES_CS = [
    "VSC#/MainWindow.xaml.cs",
    "VSC#/Nucleo/Services/WebNodoService.cs",
    "VSC#/Nucleo/Services/WebNodoService.PortalHttp.cs",
    "VSC#/Nucleo/Services/DescubrimientoP2P.cs",
    "VSC#/Nucleo/Chat/ChatRelayServer.cs",
    "VSC#/Nucleo/RedP2P/P2PTunnelManager.cs",
    "VSC#/Nucleo/RedP2P/RedP2PServicio.cs",
    "VSC#/VisorLinux/Linux/LanzadorMundo.cs",
    "VSC#/VisorLinux/Vistas/VentanaPrincipal.Chat.cs",
    "VSC#/VisorLinux/Vistas/VentanaPrincipal.Red.cs",
    "MTBGT/WoldVirtualP2P3D/gdscrip/ChunkManager.gd",
    "MTBGT/WoldVirtualP2P3D/gdscrip/Sonda.gd",
]


def _leer(ruta: Path) -> str:
    assert ruta.is_file(), f"fuente no encontrada: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str, marca: str) -> str:
    """Queda el código de cada línea: citar un puerto en un comentario no es
    volver a tomar la decisión."""
    return "\n".join(linea.split(marca)[0] for linea in texto.splitlines())


def _const_cs(texto: str, nombre: str) -> int:
    m = re.search(rf"public const int {nombre}\s*=\s*(\d+)\s*;", texto)
    assert m, f"ConfigRed.cs no declara el const {nombre}"
    return int(m.group(1))


def _const_gd(texto: str, nombre: str) -> int:
    m = re.search(rf"^const {nombre}\s*:=\s*(\d+)\s*$", texto, re.MULTILINE)
    assert m, f"Red.gd no declara el const {nombre}"
    return int(m.group(1))


def test_config_red_declarara_los_cinco_numeros():
    """La tabla C# existe y dice los números que espera el producto."""
    cs = _leer(CONFIG_CS)
    assert _const_cs(cs, "PuertoMotorWs") == PUERTOS["motor_ws"]
    assert _const_cs(cs, "PuertoBalizaUdp") == PUERTOS["baliza_udp"]
    assert _const_cs(cs, "PuertoApiP2P") == PUERTOS["api_p2p"]
    assert _const_cs(cs, "PuertoPortal") == PUERTOS["portal_min"]
    assert _const_cs(cs, "PuertoPortalMax") == PUERTOS["portal_max"]
    assert _const_cs(cs, "PuertoChat") == PUERTOS["chat"]
    assert _const_cs(cs, "DesplazamientoProxyInterno") == 100
    assert _const_cs(cs, "RangoChat") == 10


def test_tabla_godot_y_csharp_coinciden_numero_a_numero():
    """U-C8/issue #1: un cambio de puerto en un lenguaje sin el otro se para aquí."""
    cs = _leer(CONFIG_CS)
    gd = _leer(RED_GD)
    for nombre_cs, nombre_gd, clave in ESPEJO:
        valor_cs = _const_cs(cs, nombre_cs)
        valor_gd = _const_gd(gd, nombre_gd)
        assert valor_cs == valor_gd, (
            f"{nombre_cs} (C#) = {valor_cs} pero {nombre_gd} (Godot) = {valor_gd}"
        )
        assert valor_cs == PUERTOS[clave], f"{nombre_cs} dejó de valer {PUERTOS[clave]}"


def test_chunkmanager_y_sonda_no_repiten_el_literal_del_motor():
    """Los consumidores Godot leen el puerto de Red, no su propia copia."""
    cm = _leer(SRC_DIR / "MTBGT" / "WoldVirtualP2P3D" / "gdscrip" / "ChunkManager.gd")
    assert "const PUERTO_WS := Red.PUERTO_WS" in cm
    assert "Red.PUERTO_BEACON" in cm
    for numero in (8911, 8912):
        assert not re.search(rf"^\s*const \w+\s*:=\s*{numero}\s*$", cm, re.MULTILINE), (
            f"ChunkManager.gd volvió a declarar {numero} por su cuenta"
        )


def test_los_consumidores_no_llevan_literales_de_puerto_en_codigo():
    """Ningún ficho que *usa* un puerto lo escribe como número suelto.

    Se ignoran comentarios y textos entre comillas (etiquetas de la interfaz y
    mensajes de log): ahí el número es prosa para el usuario, no una decisión de
    red. Lo que no se permite es que un `if`, un `bind` o un argumento salga de
    un literal.
    """
    numeros = "|".join(str(n) for n in sorted(set(PUERTOS.values())))
    suelto = re.compile(rf"(?<![\d.])({numeros})(?![\d.])")
    faltantes = []
    for relativa in CONSUMIDORES_CS:
        ruta = SRC_DIR / relativa
        assert ruta.is_file(), f"consumidor ausente: {relativa}"
        es_gd = relativa.endswith(".gd")
        for numero_linea, linea in enumerate(_leer(ruta).splitlines(), start=1):
            despojo = linea.strip()
            if despojo.startswith("//") or despojo.startswith("///") or despojo.startswith("*"):
                continue
            codigo = despojo.split("//")[0]
            # Sin la parte entre comillas: prosa de interfaz o mensaje de log.
            codigo = re.sub(r'"[^"]*"', '""', codigo)
            if es_gd:
                codigo = codigo.split("#")[0]
            for m in suelto.finditer(codigo):
                faltantes.append(f"{relativa}:{numero_linea} → {m.group(1)}")
    assert not faltantes, "literales de puerto sueltos en código:\n" + "\n".join(faltantes)


def test_la_regla_de_reescritura_es_la_misma_en_los_dos_lenguajes():
    """Portal (3030-3040), API (7890), 80 y 443 se reescriben al motor en ambos lados."""
    cs = _leer(CONFIG_CS)
    gd = _leer(RED_GD)
    bloque_cs = cs.split("public static bool EsPuertoReescribibleAlMotor", 1)[1]
    bloque_cs = _sin_comentarios(bloque_cs.split("}", 1)[0], "//")
    for referencia in ("PuertoPortal", "PuertoPortalMax", "PuertoApiP2P"):
        assert referencia in bloque_cs, f"la regla C# dejó de usar {referencia}"
    for literal in ("3030", "3040", "7890"):
        assert literal not in bloque_cs, f"la regla C# volvió a llevar el literal {literal}"

    funcion_gd = gd.split("static func parsear_url_host_puerto", 1)[1].split("return {", 1)[0]
    funcion_gd = _sin_comentarios(funcion_gd, "#")
    for referencia in ("PUERTO_PORTAL_MIN", "PUERTO_PORTAL_MAX", "PUERTO_API_P2P", "PUERTO_WS"):
        assert referencia in funcion_gd, f"la regla Godot dejó de usar {referencia}"
    for literal in ("3030", "3040", "7890"):
        assert literal not in funcion_gd, f"la regla Godot volvió a llevar el literal {literal}"


def test_los_dos_visores_delegan_el_parser_de_destino():
    """H2: WPF y Avalonia ya no mantienen cada uno su corte de esquema y puerto."""
    main_wpf = _leer(SRC_DIR / "VSC#" / "MainWindow.xaml.cs")
    segmento = main_wpf.split("public static bool TryParseConnectionTarget", 1)[1]
    segmento = segmento.split("/// <summary>", 1)[0]
    assert "ConfigRed.ProbarDestino(input, out host, out port)" in segmento

    lanzador = _leer(SRC_DIR / "VSC#" / "VisorLinux" / "Linux" / "LanzadorMundo.cs")
    assert "ConfigRed.ProbarDestino(entrada, out host, out puerto)" in lanzador

    # Y el parser compartido entiende los cinco esquemas, incluidos ws:// y wss://.
    cs = _leer(CONFIG_CS)
    cuerpo = cs.split("public static bool ProbarDestino", 1)[1]
    for esquema in ("https://", "http://", "woldvirtual://", "wss://", "ws://"):
        assert f'"{esquema}"' in cuerpo, f"ProbarDestino dejó de recortar {esquema}"
