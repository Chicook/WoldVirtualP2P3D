"""Tests de la Etapa 1 · S6: registro de pares autenticado (POST /peer).

El barrido de seguridad de S3 (W5) encontró que el endpoint de registro de
pares de P2PNodo aceptaba cualquier URL de cualquiera: sin autenticación,
sin validación, sin tope y sin desalojo, en un puerto que el propio
servicio expone por túnel (RedP2PServicio cablea el 7890 a
P2PTunnelManager). Estos tests verifican sobre la fuente que:

  (a) POST /peer exige la invitación de la sesión y la comprueba ANTES de
      registrar: sin ella o con una incorrecta responde 401 y no toca Pares;
  (b) la credencial del nodo se genera con aleatoriedad criptográfica al
      crearlo (nunca una constante ni cadena vacía en la fuente);
  (c) la URL del par se valida (absoluta http/https, con host, longitud
      acotada) y lo inválido se rechaza con 400;
  (d) hay tope duro de pares (MaxPares) con rechazo 429 y duplicados
      idempotentes;
  (e) hay límite de intentos por IP (la del socket) con el RateLimiter
      compartido, aplicado antes de cualquier admisión;
  (f) el anuncio saliente (AnunciarseAlParAsync / ConectarConParAsync)
      transporta la invitación del destino, y ambas interfaces fijan la
      credencial del nodo desde la invitación vigente de la sesión;
  (g) GET /ping y GET /info siguen siendo públicos de solo lectura: la
      puerta se pone en el registro, no en el descubrimiento.

Estilo de la casa (inspección de fuente), como test_stage1_s3_ip.py.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
P2P_NODO = SRC_DIR / "VSC#" / "Nucleo" / "RedP2P" / "P2PNodo.cs"
P2P_SERVICIO = SRC_DIR / "VSC#" / "Nucleo" / "RedP2P" / "RedP2PServicio.cs"
MAINWINDOW = SRC_DIR / "VSC#" / "MainWindow.xaml.cs"
RED_LINUX = SRC_DIR / "VSC#" / "VisorLinux" / "Vistas" / "VentanaPrincipal.Red.cs"


def _leer(ruta: Path) -> str:
    assert ruta.is_file(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _cuerpo(texto: str, inicio: str) -> str:
    """Devuelve el cuerpo { ... } que sigue a la firma localizada."""
    i = texto.index(inicio)
    j = texto.index("{", i)
    profundidad = 0
    for k in range(j, len(texto)):
        if texto[k] == "{":
            profundidad += 1
        elif texto[k] == "}":
            profundidad -= 1
            if profundidad == 0:
                return texto[j : k + 1]
    raise AssertionError(f"cuerpo no cerrado tras: {inicio}")


def _registrar_par() -> str:
    return _cuerpo(_leer(P2P_NODO), "private (int Codigo, string Cuerpo) RegistrarPar")


def test_registro_exige_invitacion_antes_de_anadir():
    """(a) La comprobación de la invitación precede a cualquier alta."""
    cuerpo = _registrar_par()
    assert "TokenCoincide(invitacion)" in cuerpo
    assert "401" in cuerpo
    assert cuerpo.index("TokenCoincide(invitacion)") < cuerpo.index("Pares.Add")


def test_token_coincide_rechaza_vacios():
    """(a) Sin credencial configurada o sin invitación, no hay registro."""
    cuerpo = _cuerpo(_leer(P2P_NODO), "private bool TokenCoincide")
    assert "string.IsNullOrEmpty(esperado)" in cuerpo
    assert "string.IsNullOrEmpty(invitacion)" in cuerpo
    assert "StringComparison.Ordinal" in cuerpo


def test_credencial_por_defecto_es_aleatoria():
    """(b) TokenInvitacion nace de RandomNumberGenerator, no de una constante."""
    texto = _leer(P2P_NODO)
    assert "RandomNumberGenerator.GetBytes(16)" in texto
    assert not re.search(r'TokenInvitacion\s*\{\s*get;\s*set;\s*\}\s*=\s*"[0-9a-f]{32}"', texto)
    assert 'TokenInvitacion { get; set; } =\n            Convert.ToHexString' in texto


def test_url_de_par_validada():
    """(c) Solo entran URLs absolutas http/https con host y longitud acotada."""
    cuerpo = _cuerpo(_leer(P2P_NODO), "private static bool EsUrlParValida")
    assert "Uri.TryCreate(url, UriKind.Absolute" in cuerpo
    assert "Uri.UriSchemeHttp" in cuerpo and "Uri.UriSchemeHttps" in cuerpo
    assert "LongitudMaxUrlPar" in cuerpo
    registro = _registrar_par()
    assert "EsUrlParValida(urlPar)" in registro
    assert "400" in registro
    assert registro.index("EsUrlParValida(urlPar)") < registro.index("Pares.Add")


def test_tope_duro_de_pares():
    """(d) Con MaxPares lleno, un par nuevo se rechaza con 429."""
    texto = _leer(P2P_NODO)
    assert "public const int MaxPares" in texto
    cuerpo = _registrar_par()
    assert "Pares.Count >= MaxPares" in cuerpo
    assert "429" in cuerpo
    assert cuerpo.index("Pares.Count >= MaxPares") < cuerpo.index("Pares.Add")
    # El duplicado se resuelve antes del tope: re-anunciarse es idempotente.
    assert cuerpo.index("Pares.Contains") < cuerpo.index("Pares.Count >= MaxPares")


def test_limite_de_intentos_por_ip_del_socket():
    """(e) RateLimiter sobre la IP observada, antes de parsear ni admitir."""
    texto = _leer(P2P_NODO)
    assert "private readonly RateLimiter _limiteRegistro" in texto
    cuerpo = _registrar_par()
    assert "_limiteRegistro.Permitir(ipOrigen" in cuerpo
    assert cuerpo.index("_limiteRegistro.Permitir") < cuerpo.index("JsonDocument.Parse")
    handler = _cuerpo(texto, "private async Task ProcesarPeticionAsync")
    assert "RemoteEndPoint" in handler


def test_anuncio_saliente_lleva_la_invitacion():
    """(f) El cliente anuncia presentando la invitación del destino."""
    texto = _leer(P2P_NODO)
    anuncio = _cuerpo(texto, "public async Task AnunciarseAlParAsync")
    assert "tokenInvitacion" in anuncio
    assert "invitacion = tokenInvitacion" in anuncio
    servicio = _leer(P2P_SERVICIO)
    conectar = _cuerpo(servicio, "public async Task<bool> ConectarConParAsync")
    assert "tokenInvitacion" in conectar
    assert "AnunciarseAlParAsync(urlPar, UrlPublicaPropia, tokenInvitacion)" in conectar


def test_servicio_e_interfaces_fijan_la_credencial():
    """(f) El nodo recibe la invitación vigente de la sesión en ambos visores."""
    servicio = _leer(P2P_SERVICIO)
    assert "Nodo.TokenInvitacion" in servicio
    main = _leer(MAINWINDOW)
    assert "_p2pServicio.TokenInvitacion = TokenSesionP2P;" in main
    assert "if (_p2pServicio != null) _p2pServicio.TokenInvitacion = token!;" in main
    assert "ConectarConParAsync(_urlAmigoPendiente, string.IsNullOrEmpty(_tokenInvitacion)" in main
    assert "red.TokenInvitacion = _portal.TokenInvitacion;" in _leer(RED_LINUX)


def test_descubrimiento_sigue_siendo_publico():
    """(g) /ping y /info no exigen invitación: solo el registro la exige."""
    handler = _cuerpo(_leer(P2P_NODO), "private async Task ProcesarPeticionAsync")
    rama_ping = handler.index('ruta == "/ping"')
    rama_peer = handler.index('ruta == "/peer"')
    assert rama_ping < rama_peer
    assert "invitacion" not in handler[:rama_peer]
