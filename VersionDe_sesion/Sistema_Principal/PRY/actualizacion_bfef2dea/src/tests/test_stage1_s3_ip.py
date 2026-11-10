"""Tests de la Etapa 1 · S3: IP de cliente fiable (hallazgo H2).

Verifica sobre las fichas del WebNodo (parciales + AnuncioRelease) y RateLimiter.cs que:
  (a) ObtenerIpCliente ignora X-Forwarded-For / CF-Connecting-IP salvo que
      la peticion traiga el marcador de proxy de confianza valido;
  (b) el proxy TCP elimina las cabeceras suplantables del cliente y
      sobreescribe X-Forwarded-For con la IP observada en el socket,
      estampando su marcador;
  (c) RateLimiter acota el numero de claves con expulsion LRU;
  (d) el valor del marcador no es una constante ni un secreto fijo en la
      fuente: se genera aleatoriamente en cada proceso.

Estilo de la casa (inspeccion de fuente), como test_h2_h3_red.py.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
SERVICES = SRC_DIR / "VSC#" / "Nucleo" / "Services"
# El WebNodo está repartido en ficheros parciales (una responsabilidad por ficha)
# más el anuncio de release. Las comprobaciones de esta prueba cruzan el router y
# el proxy TCP, así que leen el conjunto en un orden fijo.
FICHEROS_WEBNODO = (
    "WebNodoService.cs",
    "WebNodoService.ProxyTcp.cs",
    "WebNodoService.ProxyWebSocket.cs",
    "WebNodoService.PortalHttp.cs",
    "AnuncioRelease.cs",
)
RATE_LIMITER = SERVICES / "RateLimiter.cs"


def _leer_webnodo() -> str:
    trozos = []
    for nombre in FICHEROS_WEBNODO:
        ruta = SERVICES / nombre
        assert ruta.is_file(), f"pieza del WebNodo no encontrada: {ruta.name}"
        trozos.append(ruta.read_text(encoding="utf-8"))
    return "\n".join(trozos)


def _leer_limiter() -> str:
    assert RATE_LIMITER.is_file(), "RateLimiter.cs no encontrado"
    return RATE_LIMITER.read_text(encoding="utf-8")


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


def test_obtener_ip_ignora_forwarded_sin_marcador_valido():
    """Sin marcador valido, ObtenerIpCliente devuelve la IP del socket (H2-a)."""
    cuerpo = _cuerpo(_leer_webnodo(), "private static string ObtenerIpCliente")

    # CF-Connecting-IP deja de leerse en este metodo: una sola fuente de verdad.
    assert "CF-Connecting-IP" not in cuerpo

    # La conexion directa (no loopback) devuelve el socket e ignora cabeceras,
    # y ese retorno ocurre ANTES de cualquier lectura de X-Forwarded-For.
    pos_directa = cuerpo.index("!IPAddress.IsLoopback(remoto)")
    pos_xff = cuerpo.index('Headers["X-Forwarded-For"]')
    assert cuerpo.index("return remoto.ToString();", pos_directa) < pos_xff

    # El guarda del marcador precede a la lectura de X-Forwarded-For y su
    # rama de fallo devuelve la IP del socket (loopback comparte cubo).
    pos_marcador = cuerpo.index("EsMarcadorProxyValido(req.Headers[CabeceraMarcadorProxy])")
    assert "!EsMarcadorProxyValido" in cuerpo
    assert pos_marcador < pos_xff
    assert cuerpo.index("return remoto.ToString();", pos_marcador) < pos_xff


def test_obtener_ip_con_marcador_valido_exige_ip_parseable():
    """Con marcador valido solo se acepta el primer XFF si analiza como IP (H2-a)."""
    cuerpo = _cuerpo(_leer_webnodo(), "private static string ObtenerIpCliente")

    assert "IPAddress.TryParse" in cuerpo
    assert "xff.Split(',')[0]" in cuerpo
    # Se devuelve la IP normalizada, no el texto crudo de la cabecera.
    assert "return declarada.ToString();" in cuerpo
    # Si no analiza, se cae a la IP del socket: el retorno de respaldo va
    # DESPUES de la comprobacion TryParse.
    pos_parse = cuerpo.index("IPAddress.TryParse")
    assert cuerpo.rindex("return remoto.ToString();") > pos_parse


def test_marcador_proxy_es_secreto_efimero_sin_valor_fijo():
    """El marcador se genera por proceso; en la fuente no hay valor fijo (H2-d)."""
    contenido = _leer_webnodo()

    # Generacion aleatoria en tiempo de ejecucion (>= 16 bytes de entropia).
    m = re.search(
        r"_valorMarcadorProxy\s*=\s*Convert\.ToHexString\(RandomNumberGenerator\.GetBytes\((\d+)\)\)",
        contenido,
    )
    assert m is not None, "el marcador no se genera con RandomNumberGenerator"
    assert int(m.group(1)) >= 16

    # Ninguna constante ni literal asigna el VALOR del marcador: la unica
    # constante de cabecera guarda el NOMBRE, nunca el secreto.
    assert not re.search(r"_valorMarcadorProxy\s*=\s*\"", contenido)
    assert not re.search(r"const\s+string\s+_valor\w*\s*=", contenido)
    assert 'CabeceraMarcadorProxy = "X-Wold-Proxy"' in contenido

    # Comparacion en tiempo constante contra el valor del proceso.
    cuerpo_validador = _cuerpo(contenido, "internal static bool EsMarcadorProxyValido")
    assert "CryptographicOperations.FixedTimeEquals" in cuerpo_validador
    assert "_valorMarcadorProxy" in cuerpo_validador

    # El valor vive solo en su declaracion, el validador y el estampado del
    # proxy: no se esparce por la clase (p. ej. no se sirve en pagina alguna).
    assert contenido.count("_valorMarcadorProxy") <= 5


def test_proxy_elimina_cabeceras_suplantables_del_cliente():
    """El proxy borra XFF, CF-Connecting-IP y el marcador entrantes (H2-b)."""
    contenido = _leer_webnodo()

    # La expresion de saneado nombra las tres cabeceras suplantables.
    m = re.search(r"_cabecerasSuplantables = new\(\s*@\"([^\"]*)\"", contenido)
    assert m is not None, "falta la expresion de cabeceras suplantables"
    patron = m.group(1)
    assert "X-Forwarded-For" in patron
    assert "CF-Connecting-IP" in patron
    assert "X-Wold-Proxy" in patron

    # ReescribirCabecerasDelProxy aplica el borrado sobre lo recibido y el
    # bucle del proxy invoca la reescritura con la IP observada.
    cuerpo_reesc = _cuerpo(contenido, "private static string ReescribirCabecerasDelProxy")
    assert '_cabecerasSuplantables.Replace(cabeceras, "")' in cuerpo_reesc
    cuerpo_proxy = _cuerpo(contenido, "private async Task HandleProxyClientAsync")
    assert "ReescribirCabecerasDelProxy(headersStr, ipRealProxy)" in cuerpo_proxy


def test_proxy_sobreescribe_forwarded_con_ip_del_socket():
    """El unico XFF reenviado es la IP del socket, con marcador estampado (H2-b)."""
    contenido = _leer_webnodo()
    cuerpo_proxy = _cuerpo(contenido, "private async Task HandleProxyClientAsync")
    cuerpo_reesc = _cuerpo(contenido, "private static string ReescribirCabecerasDelProxy")

    # La IP declarada sale del extremo remoto del socket aceptado.
    assert "client.Client.RemoteEndPoint" in cuerpo_proxy
    assert "ipRealProxy" in cuerpo_proxy

    # Sobreescritura (un solo valor, sin encadenar nada del cliente).
    assert "X-Forwarded-For: {ipReal" in cuerpo_reesc
    assert cuerpo_reesc.count("X-Forwarded-For") == 1
    # CF-Connecting-IP no se reescribe: desaparece del trafico interno.
    assert "CF-Connecting-IP" not in cuerpo_reesc
    # El marcador del propio proceso acompana a la IP estampada.
    assert "CabeceraMarcadorProxy}: {_valorMarcadorProxy}" in cuerpo_reesc


def test_rate_limiter_tiene_capacidad_maxima_dura():
    """El numero de claves rastreadas esta acotado por una constante (H2-c)."""
    contenido = _leer_limiter()
    m = re.search(r"CapacidadMaximaClaves\s*=\s*(\d+)", contenido)
    assert m is not None, "falta la constante de capacidad de claves"
    assert int(m.group(1)) == 4096
    cuerpo = _cuerpo(contenido, "public bool Permitir")
    assert "_ventanas.Count > CapacidadMaximaClaves" in cuerpo


def test_rate_limiter_expulsa_la_menos_reciente_al_insertar():
    """Al insertar con el almacen lleno se expulsa la clave LRU (H2-c)."""
    contenido = _leer_limiter()
    cuerpo = _cuerpo(contenido, "public bool Permitir")
    assert "ExpulsarMenosReciente()" in cuerpo
    cuerpo_exp = _cuerpo(contenido, "private void ExpulsarMenosReciente")
    # La victima es la cabeza de la lista de uso (la menos reciente) y sale
    # de las tres estructuras a la vez.
    assert "_ordenUso.First" in cuerpo_exp
    assert "_ordenUso.RemoveFirst()" in cuerpo_exp
    assert "_nodos.Remove" in cuerpo_exp
    assert "_ventanas.Remove" in cuerpo_exp


def test_rate_limiter_marca_uso_en_cada_acceso():
    """Cada acceso mueve la clave al extremo mas reciente de la lista (H2-c)."""
    contenido = _leer_limiter()
    assert "LinkedList<string>" in contenido
    assert "LinkedListNode<string>" in contenido
    cuerpo = _cuerpo(contenido, "public bool Permitir")
    assert "_ordenUso.Remove(nodo)" in cuerpo
    assert "_ordenUso.AddLast(nodo)" in cuerpo
    # La clave nueva tambien entra registrada en el orden de uso.
    assert "_ordenUso.AddLast(clave)" in cuerpo
