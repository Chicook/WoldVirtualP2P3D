"""Tests para la autenticación del relé de chat (Etapa 1, hueco G1).

Verifica que ChatRelayServer exija el token de sesión tras el handshake y
cierre a quien no lo presente, que ningún cliente se registre ni reciba
difusiones antes de autenticarse, que el cliente local presente el token
antes del hello, que el proxy del túnel (WebNodoService) inyecte el token
al proxiar /chat y que el token compartido (TokenSesionChat) nazca de un
RNG criptográfico, sin valores fijados ni persistencia.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
CHAT_DIR = SRC_DIR / "VSC#" / "Nucleo" / "Chat"
SERVICES_DIR = SRC_DIR / "VSC#" / "Nucleo" / "Services"
# El proxy del túnel está repartido en ficheros parciales, uno por responsabilidad.
FICHEROS_WEBNODO = (
    "WebNodoService.cs",
    "WebNodoService.ProxyTcp.cs",
    "WebNodoService.ProxyWebSocket.cs",
    "WebNodoService.PortalHttp.cs",
    "AnuncioRelease.cs",
)


def _leer(ruta: Path) -> str:
    assert ruta.is_file(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _relay() -> str:
    return _leer(CHAT_DIR / "ChatRelayServer.cs")


def _cliente() -> str:
    return _leer(CHAT_DIR / "ChatClient.cs")


def _helper() -> str:
    return _leer(CHAT_DIR / "TokenSesionChat.cs")


def _webnodo() -> str:
    """Proxy del túnel completo: se lee el conjunto de sus ficheros parciales."""
    return "\n".join(_leer(SERVICES_DIR / nombre) for nombre in FICHEROS_WEBNODO)


def _segmento(texto: str, inicio: str, fin: str) -> str:
    """Trozo de código entre dos marcas (definición de un método y el siguiente)."""
    assert inicio in texto, f"marca de inicio ausente: {inicio}"
    assert fin in texto, f"marca de fin ausente: {fin}"
    return texto.split(inicio, 1)[1].split(fin, 1)[0]


# ---------------------------------------------------------------------------
# Helper compartido del token (TokenSesionChat.cs)
# ---------------------------------------------------------------------------

def test_helper_genera_el_token_con_rng_criptografico():
    """Generar() debe usar RandomNumberGenerator: 16 bytes en hex minúscula (32)."""
    contenido = _helper()
    assert "public static class TokenSesionChat" in contenido
    assert "private const int TokenBytes = 16;" in contenido
    assert "private const int TokenChars = 32;" in contenido
    generar = _segmento(contenido, "public static string Generar()", "public static void Establecer")
    assert "RandomNumberGenerator.GetBytes(TokenBytes)" in generar
    assert "Convert.ToHexString(bytes).ToLowerInvariant()" in generar
    # Actual es perezoso: el token nace en el primer acceso, solo en memoria.
    assert "return _actual ??= Generar();" in contenido


def test_helper_formato_estricto_y_comparacion_en_tiempo_fijo():
    """FormatoValido exige 32 hex en minúscula y EsValido compara en tiempo fijo."""
    contenido = _helper()
    formato = _segmento(contenido, "public static bool FormatoValido", "\n    }\n}")
    assert "token is null || token.Length != TokenChars" in formato
    assert "c >= '0' && c <= '9'" in formato
    assert "c >= 'a' && c <= 'f'" in formato
    es_valido = _segmento(contenido, "public static bool EsValido", "public static bool FormatoValido")
    assert "if (!FormatoValido(token)) return false;" in es_valido
    assert "CryptographicOperations.FixedTimeEquals" in es_valido
    # Establecer ignora lo que no cumpla el formato; Renovar genera y adopta.
    establecer = _segmento(contenido, "public static void Establecer", "public static string Renovar")
    assert "if (!FormatoValido(token)) return;" in establecer
    renovar = _segmento(contenido, "public static string Renovar", "public static bool EsValido")
    assert "_actual = Generar();" in renovar


def test_helper_sin_persistencia_ni_token_fijado_en_el_codigo():
    """El token no se guarda en disco, no se registra y no vale ningún literal."""
    contenido = _helper()
    for prohibido in ("File.", "Path.", "StreamWriter", "WriteAllText",
                      "Registry", "VisorLog", "Console.", "Debug.Write"):
        assert prohibido not in contenido, f"persistencia/log en el helper: {prohibido}"
    # Ningún fichero de la cadena de chat lleva un token literal de 32 hex.
    for ruta in (CHAT_DIR / "TokenSesionChat.cs", CHAT_DIR / "ChatRelayServer.cs",
                 CHAT_DIR / "ChatClient.cs",
                 *(SERVICES_DIR / nombre for nombre in FICHEROS_WEBNODO)):
        texto = _leer(ruta)
        assert re.findall(r'"[0-9a-f]{32}"', texto) == [], f"token fijado en {ruta.name}"


# ---------------------------------------------------------------------------
# Relé: exige el token tras el handshake y cierra a quien no se autentica
# ---------------------------------------------------------------------------

def test_relay_fija_su_token_al_arrancar_y_da_5_segundos_de_plazo():
    """Start() adopta TokenSesionChat.Actual; sin auth la lectura caduca a los 5 s."""
    contenido = _relay()
    assert "private static readonly TimeSpan PlazoAutenticacion = TimeSpan.FromSeconds(5);" in contenido
    assert "private const ushort CodigoCierreSinAuth = 1008;" in contenido
    assert "public string TokenSesion => _tokenSesion;" in contenido
    arranque = _segmento(contenido, "public bool Start(int puertoPreferido = Visor3D.RedP2P.ConfigRed.PuertoChat", "private async Task BucleAceptacionAsync")
    assert "_tokenSesion = TokenSesionChat.Actual;" in arranque
    bucle = _segmento(contenido, "private async Task BucleClienteAsync", "private async Task<bool> ProcesarMensajeAsync")
    # Mientras no haya auth se lee con el token del plazo; el ping se responde
    # pero no renueva el plazo: CancelAfter aparece una sola vez en el bucle.
    assert bucle.count("CancelAfter") == 1
    assert "plazoAuth.CancelAfter(PlazoAutenticacion);" in bucle
    assert "c.Autenticado ? ct : plazoAuth.Token" in bucle
    assert "case 0x9:" in bucle


def test_relay_no_procesa_nada_antes_de_la_autenticacion():
    """ProcesarMensajeAsync desvía todo lo no autenticado a la vía de auth."""
    contenido = _relay()
    puerta = _segmento(contenido, "private async Task<bool> ProcesarMensajeAsync",
                        "private async Task<bool> ProcesarTextoAsync")
    assert "if (!c.Autenticado)" in puerta
    assert "return await ProcesarAutenticacionAsync(c, payload, ct);" in puerta
    assert "await CerrarSinAuthAsync(c, ct);" in puerta
    assert "return false;" in puerta
    # La puerta va antes que el proceso normal de texto y de binario.
    assert puerta.index("if (!c.Autenticado)") < puerta.index("ProcesarTextoAsync(c, payload, ct)")
    assert puerta.index("if (!c.Autenticado)") < puerta.index("ProcesarBinarioAsync(c, payload, ct)")


def test_relay_cierra_con_auth_fail_y_1008_si_el_token_no_vale():
    """Auth ausente, mal formada o incorrecta: auth_fail, cierre 1008 y corte."""
    contenido = _relay()
    auth = _segmento(contenido, "private async Task<bool> ProcesarAutenticacionAsync",
                     "private bool RegistrarCliente")
    assert 'tipoProp.GetString() == "auth"' in auth
    assert 'doc.RootElement.TryGetProperty("token", out var tokenProp)' in auth
    assert "if (token == null || !EsTokenValido(token) || !RegistrarCliente(c))" in auth
    assert "await CerrarSinAuthAsync(c, ct);" in auth
    assert "return false;" in auth
    cierre = _segmento(contenido, "private async Task CerrarSinAuthAsync",
                       "private static string? ExtraerTokenDeRuta")
    assert 'ChatProtocol.TextFrame(new { t = "auth_fail", text = "Autenticación requerida" })' in cierre
    assert "BinaryPrimitives.WriteUInt16BigEndian(cierre, CodigoCierreSinAuth);" in cierre
    assert "await EnviarFrameAsync(c, 0x8, cierre, ct);" in cierre
    # La validación acepta el token fijado en Start() o el vigente del helper,
    # siempre comparando en tiempo fijo.
    validacion = _segmento(contenido, "private bool EsTokenValido", "private static bool CoincideToken")
    assert "CoincideToken(token, _tokenSesion) || TokenSesionChat.EsValido(token)" in validacion
    assert "CryptographicOperations.FixedTimeEquals" in contenido


# ---------------------------------------------------------------------------
# Relé: nadie se registra ni recibe nada antes de autenticarse
# ---------------------------------------------------------------------------

def test_relay_no_registra_al_cliente_en_el_handshake():
    """Tras el handshake el cliente queda fuera de _clientes hasta validar el token."""
    contenido = _relay()
    atencion = _segmento(contenido, "private async Task AtenderClienteAsync",
                         "private async Task BucleClienteAsync")
    # El alta directa que existía antes de G1 ha desaparecido de esta vía.
    assert "_clientes.Add" not in atencion
    assert "if (!Handshake(stream, cabecera, out string? error))" in atencion
    # Solo hay un alta en todo el servidor: la de RegistrarCliente.
    assert contenido.count("_clientes.Add(") == 1
    registro = _segmento(contenido, "private bool RegistrarCliente", "private bool EsTokenValido")
    assert "_clientes.Add(c);" in registro
    assert "if (_clientes.Count >= ChatProtocol.MaxClients) return false;" in registro
    # Las difusiones solo llegan a clientes de la lista ya anunciados: un no
    # autenticado no está en la lista y tampoco puede ser destino.
    difusion = _segmento(contenido, "private async Task DifundirAsync", "private static async Task EnviarFrameAsync")
    assert "if (!destino.Anunciado) continue;" in difusion
    # hello/msg/state/binario exigen el Anunciado que solo llega tras la auth.
    binario = _segmento(contenido, "private async Task<bool> ProcesarBinarioAsync", "private bool Permitir")
    assert "if (!c.Anunciado || frame.Length < 2) return true;" in binario


def test_relay_autentica_por_la_url_del_handshake():
    """La vía del proxy: /chat?token= o /chat?invitacion= registra si el token vale."""
    contenido = _relay()
    atencion = _segmento(contenido, "private async Task AtenderClienteAsync",
                         "private async Task BucleClienteAsync")
    assert "string? tokenRuta = ExtraerTokenDeRuta(cabecera);" in atencion
    assert "if (tokenRuta != null && EsTokenValido(tokenRuta))" in atencion
    assert "if (!RegistrarCliente(cliente)) return;" in atencion
    assert "cliente.Autenticado = true;" in atencion
    extraccion = _segmento(contenido, "private static string? ExtraerTokenDeRuta",
                           "private async Task<bool> ProcesarSolicitudAmistadAsync")
    assert 'nombre.Equals("token", StringComparison.OrdinalIgnoreCase)' in extraccion
    assert 'nombre.Equals("invitacion", StringComparison.OrdinalIgnoreCase)' in extraccion
    assert "Uri.UnescapeDataString" in extraccion


def test_relay_con_auth_correcta_registra_y_responde_auth_ok():
    """Con el token válido: registro, Autenticado=true y trama auth_ok."""
    contenido = _relay()
    auth = _segmento(contenido, "private async Task<bool> ProcesarAutenticacionAsync",
                     "private bool RegistrarCliente")
    assert "c.Autenticado = true;" in auth
    assert 'ChatProtocol.TextFrame(new { t = "auth_ok" })' in auth
    # El registro queda condicionado a que el token ya haya resultado válido.
    assert auth.index("!EsTokenValido(token)") < auth.index("c.Autenticado = true;")


def test_relay_ignora_una_auth_cuando_ya_esta_autenticado():
    """Un auth repetido (p. ej. tras la inyección del proxy) no re-verifica ni corta."""
    contenido = _relay()
    texto = _segmento(contenido, "private async Task<bool> ProcesarTextoAsync",
                      "private async Task<bool> ProcesarSolicitudAmistadAsync")
    assert 'if (tipo == "auth")' in texto
    assert texto.index('if (tipo == "auth")') < texto.index('if (tipo == "hello")')
    rama_auth = texto.split('if (tipo == "auth")', 1)[1].split('if (tipo == "hello")', 1)[0]
    assert "return true;" in rama_auth
    assert "CerrarSinAuth" not in rama_auth


# ---------------------------------------------------------------------------
# Cliente local: presenta el token al conectar
# ---------------------------------------------------------------------------

def test_cliente_envia_la_auth_como_primera_trama_antes_del_hello():
    """ConnectAsync envía {t:auth} antes que {t:hello}, o el relay lo cerraría."""
    contenido = _cliente()
    conexion = _segmento(contenido, "public async Task<bool> ConnectAsync",
                         "private string ResolverTokenSesion")
    trama_auth = 'await EnviarJsonAsync(new { t = "auth", token = ResolverTokenSesion(uri) }, _cts.Token);'
    trama_hello = 'await EnviarJsonAsync(new { t = "hello", name = Name, uid = _uid }, _cts.Token);'
    assert trama_auth in conexion
    assert trama_hello in conexion
    assert conexion.index(trama_auth) < conexion.index(trama_hello)
    # El token puede venir fijado por la vista: propiedad y parámetro del ctor.
    assert 'public string TokenSesion { get; set; } = "";' in contenido
    assert 'public ChatClient(string name, string uid = "", string tokenSesion = "")' in contenido


def test_cliente_resuelve_el_token_en_el_orden_previsto():
    """Orden: explícito de la vista, ?invitacion=/?token= de la URI, helper local."""
    contenido = _cliente()
    resolver = _segmento(contenido, "private string ResolverTokenSesion", "public Task SendTextAsync")
    assert "if (TokenSesionChat.FormatoValido(TokenSesion))" in resolver
    assert "return TokenSesion;" in resolver
    assert 'clave.Equals("invitacion", StringComparison.OrdinalIgnoreCase)' in resolver
    assert 'clave.Equals("token", StringComparison.OrdinalIgnoreCase)' in resolver
    assert "if (TokenSesionChat.FormatoValido(valor)) return valor;" in resolver
    assert "return TokenSesionChat.Actual;" in resolver
    assert resolver.index("return TokenSesion;") < resolver.index("return TokenSesionChat.Actual;")


def test_cliente_reconoce_auth_ok_y_auth_fail():
    """El cliente procesa la respuesta del relay: auth_ok sigue; auth_fail avisa."""
    contenido = _cliente()
    assert 'case "auth_ok":' in contenido
    assert 'case "auth_fail":' in contenido
    rama_fallo = contenido.split('case "auth_fail":', 1)[1].split('case "welcome":', 1)[0]
    assert "_authRechazada = true;" in rama_fallo
    assert "ErrorReceived?.Invoke" in rama_fallo


# ---------------------------------------------------------------------------
# Proxy del túnel (WebNodoService): verifica e inyecta el token
# ---------------------------------------------------------------------------

def test_proxy_rechaza_sin_invitacion_e_inyecta_el_token_en_chat():
    """Sin ?invitacion= válida hay 403; con ella, /chat se proxya con ?token=."""
    contenido = _webnodo()
    assert 'string? invitacion = req.QueryString["invitacion"];' in contenido
    assert "if (!string.Equals(invitacion, TokenInvitacion, StringComparison.Ordinal))" in contenido
    assert "res.StatusCode = 403;" in contenido
    destino_chat = 'await ProxyWebSocketAsync(ctx, $"ws://localhost:{ChatLocalPort}/chat?token={TokenInvitacion}");'
    assert destino_chat in contenido
    # La comprobación de la invitación precede a cualquier proxy de /chat.
    assert contenido.index('req.QueryString["invitacion"]') < contenido.index(destino_chat)
    # El destino sin inyección que existía antes de G1 ya no está.
    assert 'ProxyWebSocketAsync(ctx, $"ws://localhost:{ChatLocalPort}/chat")' not in contenido


def test_proxy_comparte_el_token_con_el_helper_de_sesion():
    """TokenInvitacion ya no es una segunda credencial: vive en TokenSesionChat."""
    contenido = _webnodo()
    assert "get => Visor3D.Chat.TokenSesionChat.Actual;" in contenido
    assert "set => Visor3D.Chat.TokenSesionChat.Establecer(value);" in contenido
    assert "public string TokenInvitacion { get; set; }" not in contenido


# ---------------------------------------------------------------------------
# Visor Linux: mismo código compartido y adopción del token del portal
# ---------------------------------------------------------------------------

def test_visor_linux_adopta_el_token_antes_de_arrancar_el_relay():
    """VentanaPrincipal.Chat adopta la invitación en el helper antes de Start()."""
    ventana = _leer(SRC_DIR / "VSC#" / "VisorLinux" / "Vistas" / "VentanaPrincipal.Chat.cs")
    assert "TokenSesionChat.Establecer(_portal.TokenInvitacion);" in ventana
    assert "bool ok = _relay.Start(ConfigRed.PuertoChat, ConfigRed.RangoChat);" in ventana
    assert ventana.index("TokenSesionChat.Establecer(_portal.TokenInvitacion);") < ventana.index("_relay.Start(ConfigRed.PuertoChat")
    # Los endpoints que salen a otro anfitrión llevan la invitación en la URL
    # del handshake (vía túnel http/https y vía LAN directa al puerto del relay).
    assert "string token = LanzadorMundo.ExtraerInvitacion(destino);" in ventana
    assert ventana.count('?invitacion={Uri.EscapeDataString(token)}') == 2
    assert 'return $"ws://{host}:{ConfigRed.PuertoChat}/chat{consulta}";' in ventana


def test_visor_linux_compila_el_relay_cliente_y_helper_desde_el_nucleo():
    """U3: los dos visores consumen el mismo ensamblado, no la misma ficha enlazada.

    Antes `VisorLinux.csproj` enumeraba 17 `<Compile Include="../…">` y cada PR
    tenía que acordarse de añadir la suya; una ficha olvidada significaba que el
    visor Linux cargaba código distinto sin que nada lo dijera. El invariante que
    importa es «ChatRelayServer/ChatClient/TokenSesionChat están en Nucleo y los
    dos visores referencian Nucleo», así que eso es lo que se comprueba — y que
    la lista de enlaces no vuelva, porque recompilaría el código dos veces.
    """
    raiz = SRC_DIR / "VSC#"
    nucleo = _leer(raiz / "Nucleo" / "Nucleo.csproj")
    visor_linux = _leer(raiz / "VisorLinux" / "VisorLinux.csproj")
    visor_wpf = _leer(raiz / "Visor3D.csproj")

    # El núcleo es net8.0 sin UI: lo mismo vale para el exe de Windows y para Avalonia.
    assert "<TargetFramework>net8.0</TargetFramework>" in nucleo
    assert "<UseWPF>" not in nucleo
    assert 'PackageReference Include="Avalonia' not in nucleo
    assert "<OutputType>" not in nucleo  # librería: nadie puede ejecutarla suelta

    for ficha in ("ChatRelayServer.cs", "ChatClient.cs", "TokenSesionChat.cs"):
        assert (raiz / "Nucleo" / "Chat" / ficha).is_file(), f"{ficha} no está en Nucleo/Chat"

    assert '<ProjectReference Include="..\\Nucleo\\Nucleo.csproj"' in visor_linux
    assert '<ProjectReference Include="Nucleo\\Nucleo.csproj"' in visor_wpf

    # Regresión de la estructura vieja: ni un `<Compile Include="../…">` suelto.
    assert '<Compile Include="../' not in visor_linux
    # Y el WPF no puede globar lo que ya aporta la referencia (doble compilación).
    assert '<Compile Remove="Nucleo\\**"' in visor_wpf
