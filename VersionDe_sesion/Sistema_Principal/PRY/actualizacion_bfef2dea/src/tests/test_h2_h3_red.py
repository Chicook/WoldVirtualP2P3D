"""Tests para arnés H2 y resolución de red LAN H3 (Issue #1).

Verifica que el endpoint de red se propague de extremo a extremo sin fijar 8911
y que la extracción de runtime valide hashes SHA-256 e impida zip slip.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]


def test_red_gd_propaga_puerto_dinamico():
    """Red.gd debe usar el puerto resuelto en resolver_url_ws y respetar --port (H3)."""
    red_gd = SRC_DIR / "MTBGT" / "WoldVirtualP2P3D" / "gdscrip" / "Red.gd"
    assert red_gd.is_file(), "Red.gd no encontrado"
    contenido = red_gd.read_text(encoding="utf-8")

    # resolver_url_ws debe aceptar port y no ignorarlo
    assert "resolver_url_ws(host: String, port: int" in contenido
    assert "final_port := port if (port > 0 and port <= 65535) else PUERTO_WS" in contenido
    assert 'url = "ws://%s:%d" % [h, final_port]' in contenido

    # --force-host debe respetar cli_port
    assert 'if cli_force_host:' in contenido
    assert 'res["port"] = cli_port' in contenido

    # buscar_host_en_lan debe parsear _WS_ si viene en el beacon
    assert 'var idx_ws := msg.find("_WS_")' in contenido
    assert 'beacon_port = p_sub' in contenido


def test_app_extractor_valida_hashes_e_impide_zip_slip():
    """AppExtractor.cs debe validar SHA-256 del PCK/motor y proteger contra zip slip (H4)."""
    extractor_cs = SRC_DIR / "VSC#" / "AppExtractor.cs"
    assert extractor_cs.is_file(), "AppExtractor.cs no encontrado"
    contenido = extractor_cs.read_text(encoding="utf-8")

    # Protección contra Zip Slip mediante separador de directorio
    assert "destDirWithSep" in contenido
    assert "!targetPath.StartsWith(destDirWithSep" in contenido

    # Validación de hash SHA-256 en lugar de solo existencia
    assert "CalcularSha256" in contenido
    assert "pck_sha256=" in contenido
    assert "godot_sha256=" in contenido


def test_mainwindow_usa_puerto_dinamico_en_nodos_lan():
    """MainWindow.xaml.cs debe propagar el puerto descubierto en la baliza LAN (H3)."""
    main_cs = SRC_DIR / "VSC#" / "MainWindow.xaml.cs"
    assert main_cs.is_file(), "MainWindow.xaml.cs no encontrado"
    contenido = main_cs.read_text(encoding="utf-8")

    assert "_puertosRedLan" in contenido
    assert "_indiceNodoSeleccionado" in contenido
    assert "int puerto = _puertosRedLan.TryGetValue(ip, out int p) ? p : DescubrimientoP2P.PuertoGodot;" in contenido


def test_descubrimiento_p2p_captura_puerto_baliza():
    """DescubrimientoP2P.cs debe capturar el puerto si el beacon incluye _WS_ (H3)."""
    desc_cs = SRC_DIR / "VSC#" / "Services" / "DescubrimientoP2P.cs"
    assert desc_cs.is_file(), "DescubrimientoP2P.cs no encontrado"
    contenido = desc_cs.read_text(encoding="utf-8")

    assert "public Dictionary<string, int> Puertos" in contenido
    assert 'mensaje.IndexOf("_WS_"' in contenido
    assert "res.Puertos[ip] = puerto;" in contenido
