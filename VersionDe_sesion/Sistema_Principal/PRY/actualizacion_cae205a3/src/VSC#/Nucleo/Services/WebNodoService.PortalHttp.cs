using System;
using System.Globalization;
using System.IO;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Visor3D.RedP2P;

namespace Visor3D.Services
{
    /// <summary>
    /// Pieza HTTP del WebNodo: el router de rutas, los recursos del portal, la
    /// identificación de la IP del cliente y los límites por IP.
    /// </summary>
    public partial class WebNodoService
    {
        // Token por sesión para /api/*: la página lo recibe embebido y lo envía en cada llamada.
        private static readonly string _apiToken =
            Convert.ToHexString(System.Security.Cryptography.RandomNumberGenerator.GetBytes(16)).ToLowerInvariant();

        /// <summary>Token de sesión; la autoprueba lo necesita para llamar a /api/*.</summary>
        internal static string ApiToken => _apiToken;

        // La página y los estáticos NO se limitan: solo /api/* y /descargar.
        private static readonly RateLimiter _limiteApi = new();
        private static readonly RateLimiter _limiteDescarga = new();
        private readonly SemaphoreSlim _descargaUnica = new(1, 1);

        private async Task ProcessRequest(HttpListenerContext ctx)
        {
            bool reservaDescarga = false;
            try
            {
                var req = ctx.Request;
                var res = ctx.Response;
                var path = req.Url?.AbsolutePath ?? "/";

                // IMPORTANTE: el handshake WebSocket del metaverso (Godot -> ws://localhost:8911)
                // llega a la ruta raíz. Debe comprobarse ANTES que el HTML del portal; de lo
                // contrario el upgrade se responde con HTML y el cliente nunca conecta.
                if (req.IsWebSocketRequest)
                {
                    // Sin la invitación de esta sesión no se reenvía nada al motor:
                    // copiar la URL del portal no abre una sesión de metaverso.
                    string? invitacion = req.QueryString["invitacion"];
                    if (!string.Equals(invitacion, TokenInvitacion, StringComparison.Ordinal))
                    {
                        VisorLog.Warn($"WS rechazado por invitación no válida desde {req.RemoteEndPoint} ({path})");
                        res.StatusCode = 403;
                        res.StatusDescription = "Invitación no válida";
                        res.Close();
                        return;
                    }

                    // /chat -> relay del chat; cualquier otra ruta -> motor Godot (8911).
                    string rutaWs = req.Url?.AbsolutePath ?? "/";
                    if (rutaWs.StartsWith("/chat", StringComparison.OrdinalIgnoreCase))
                    {
                        if (!ChatEnabled || ChatLocalPort <= 0)
                        {
                            ctx.Response.StatusCode = 503;
                            ctx.Response.StatusDescription = "Chat no disponible";
                            ctx.Response.Close();
                            return;
                        }
                        // El relay exige el token de la sesión: el proxy lo inyecta
                        // como ?token= al abrir contra el relay. El cliente de túnel
                        // ya acreditó su invitación ante este WebNodo (arriba) y no
                        // maneja otra credencial: es el mismo valor de sesión.
                        await ProxyWebSocketAsync(ctx, $"ws://localhost:{ChatLocalPort}/chat?token={TokenInvitacion}");
                    }
                    else
                    {
                        await ProxyWebSocketAsync(ctx, $"ws://localhost:{ConfigRed.PuertoMotorWs}");
                    }
                    return;
                }

                // /api/* exige el token de esta sesión (evita llamadas cruzadas desde webs ajenas).
                // Excepción: /api/p2p-status es la señal de presencia que otro visor consulta
                // antes de entrar. Solo devuelve si el nodo está en línea y su propio túnel,
                // que su página ya publica; no expone la API de descarga.
                bool consultaPresencia = path.Equals("/api/p2p-status", StringComparison.OrdinalIgnoreCase);
                if (!consultaPresencia &&
                    path.StartsWith("/api/", StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(req.QueryString["token"], _apiToken, StringComparison.Ordinal))
                {
                    res.StatusCode = 403;
                    var prohibido = Encoding.UTF8.GetBytes("{\"error\":\"forbidden\"}");
                    res.ContentType = "application/json";
                    res.ContentLength64 = prohibido.Length;
                    await res.OutputStream.WriteAsync(prohibido, 0, prohibido.Length);
                    return;
                }

                // La página y los estáticos no se limitan nunca: solo la API y las descargas.
                string ipCliente = ObtenerIpCliente(req);

                if (path.StartsWith("/api/", StringComparison.OrdinalIgnoreCase) &&
                    !_limiteApi.Permitir(ipCliente, 120, TimeSpan.FromMinutes(1)))
                {
                    VisorLog.Warn($"429 en {path} para {ipCliente}");
                    await Responder429Async(res, 30);
                    return;
                }

                bool esDescarga = path == "/descargar" || path.StartsWith("/descargar/");
                if (esDescarga)
                {
                    if (!_limiteDescarga.Permitir(ipCliente, 3, TimeSpan.FromMinutes(1)) ||
                        !_descargaUnica.Wait(0))
                    {
                        VisorLog.Warn($"429 en descarga para {ipCliente}");
                        await Responder429Async(res, 60);
                        return;
                    }
                    reservaDescarga = true;
                }

                if (path == "/" || path == "/index.html")
                {
                    string? html = ObtenIndexHtml();
                    if (html == null)
                    {
                        // Sin portal no hay nada que servir: se responde 503 en vez de
                        // una página vacía que el invitado leería como un nodo sin binario.
                        res.StatusCode = 503;
                        res.StatusDescription = "Portal no disponible";
                        return;
                    }
                    res.ContentType = "text/html; charset=utf-8";
                    var tunnel = string.IsNullOrWhiteSpace(_publicTunnelUrl)
                        ? $"http://localhost:{ActivePort}/"
                        : _publicTunnelUrl;
                    html = html.Replace("{{API_TOKEN}}", _apiToken);
                    if (!string.IsNullOrWhiteSpace(_publicTunnelUrl))
                    {
                        html = html.Replace($"http://localhost:{ConfigRed.PuertoPortal}/", tunnel);
                        html = html.Replace($"http://localhost:{ActivePort}/", tunnel);
                        html = html.Replace($"http://127.0.0.1:{ActivePort}/", tunnel);
                    }
                    var bytes = Encoding.UTF8.GetBytes(html);
                    res.ContentLength64 = bytes.Length;
                    await res.OutputStream.WriteAsync(bytes, 0, bytes.Length);
                }
                else if (path == "/metaverso.jpg")
                {
                    var bytes = ObtenMetaversoJpg();
                    if (bytes != null && bytes.Length > 0)
                    {
                        res.ContentType = "image/jpeg";
                        res.ContentLength64 = bytes.Length;
                        await res.OutputStream.WriteAsync(bytes, 0, bytes.Length);
                    }
                    else
                    {
                        res.StatusCode = 404;
                        res.StatusDescription = "Not Found";
                    }
                }
                else if (path == "/descargar" || path.StartsWith("/descargar/"))
                {
                    string anunciado = AnuncioRelease.ExeName;
                    VisorLog.Info($"WebNodo: descarga solicitada desde {req.RemoteEndPoint} ({anunciado})");

                    // Tras un OTA el propio .exe en ejecución YA es la release vigente,
                    // aunque en disco conserve el nombre antiguo. Se entregan sus bytes
                    // bajo el nombre anunciado, sin renombrar en disco (no rompe accesos
                    // directos ni el paso de reemplazo del .bat).
                    string? origen = AnuncioRelease.RutaBinarioEnEjecucion;
                    if (origen == null)
                    {
                        // Sin apphost localizable: se busca la copia empaquetada junto al visor.
                        foreach (var carpeta in new[]
                        {
                            Path.Combine(AppContext.BaseDirectory, "webnodo", "descargas"),
                            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "webnodo", "descargas"),
                            AppContext.BaseDirectory
                        })
                        {
                            string candidato = Path.Combine(carpeta, anunciado);
                            if (File.Exists(candidato)) { origen = candidato; break; }
                        }
                    }

                    if (origen != null)
                    {
                        res.ContentType = "application/octet-stream";
                        res.AddHeader("Content-Disposition", $"attachment; filename=\"{anunciado}\"");
                        using var fs = File.OpenRead(origen);
                        res.ContentLength64 = fs.Length;
                        await fs.CopyToAsync(res.OutputStream);
                    }
                    else
                    {
                        res.Redirect(AnuncioRelease.ExeUrl);
                    }
                }
                else if (path == "/api/info")
                {
                    var payload = new
                    {
                        disponible = true,
                        nombre = AnuncioRelease.ExeName,
                        version = AnuncioRelease.ExeVersion,
                        version_instalada = AnuncioRelease.VersionInstalada,
                        tamano_mb = AnuncioRelease.ExeSizeMb,
                        url_descarga = "/descargar"
                    };
                    var bytes = JsonSerializer.SerializeToUtf8Bytes(payload);
                    res.ContentType = "application/json; charset=utf-8";
                    res.ContentLength64 = bytes.Length;
                    await res.OutputStream.WriteAsync(bytes, 0, bytes.Length);
                }
                else if (path == "/api/p2p-status")
                {
                    var tunnel = string.IsNullOrWhiteSpace(_publicTunnelUrl) ? "" : _publicTunnelUrl;
                    var payload = new
                    {
                        online = !string.IsNullOrWhiteSpace(tunnel),
                        tunnel_url = tunnel,
                        timestamp = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture)
                    };
                    var bytes = JsonSerializer.SerializeToUtf8Bytes(payload);
                    res.ContentType = "application/json; charset=utf-8";
                    res.ContentLength64 = bytes.Length;
                    await res.OutputStream.WriteAsync(bytes, 0, bytes.Length);
                }
                else
                {
                    res.StatusCode = 404;
                    res.StatusDescription = "Not Found";
                }
            }
            catch
            {
                try { ctx.Response.StatusCode = 500; } catch { }
            }
            finally
            {
                if (reservaDescarga)
                {
                    try { _descargaUnica.Release(); } catch { }
                }
                try { ctx.Response.OutputStream.Close(); } catch { }
            }
        }

        /// <summary>
        /// HTML del portal. Una sola fuente: <c>webnodo/public/index.html</c>, en
        /// disco si está junto al visor (permite edits sin reconstruir) y como
        /// recurso embebido del ensamblado en la distribución de un solo fichero.
        /// Antes existía una tercera copia cableada en una cadena de este fichero,
        /// que se quedó obsoleta frente al recurso y hacía de la página algo
        /// inatacable desde el árbol del proyecto.
        /// </summary>
        private static string? ObtenIndexHtml()
        {
            // 1. Probar desde disco
            var pathOnDisk = Path.Combine(AppContext.BaseDirectory, "webnodo", "public", "index.html");
            if (!File.Exists(pathOnDisk))
                pathOnDisk = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "webnodo", "public", "index.html");
            if (File.Exists(pathOnDisk))
            {
                try { return File.ReadAllText(pathOnDisk, Encoding.UTF8); } catch { }
            }

            // 2. Probar recurso embebido en el ensamblado
            try
            {
                var asm = typeof(WebNodoService).Assembly;
                using var stream = asm.GetManifestResourceStream("Visor3D.webnodo.public.index.html");
                if (stream != null)
                {
                    using var reader = new StreamReader(stream, Encoding.UTF8);
                    return reader.ReadToEnd();
                }
            }
            catch { }

            return null;
        }

        private static byte[]? ObtenMetaversoJpg()
        {
            // 1. Probar desde disco
            var pathOnDisk = Path.Combine(AppContext.BaseDirectory, "webnodo", "public", "metaverso.jpg");
            if (!File.Exists(pathOnDisk))
                pathOnDisk = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "webnodo", "public", "metaverso.jpg");
            if (File.Exists(pathOnDisk))
            {
                try { return File.ReadAllBytes(pathOnDisk); } catch { }
            }

            // 2. Probar recurso embebido
            try
            {
                var asm = typeof(WebNodoService).Assembly;
                using var stream = asm.GetManifestResourceStream("Visor3D.webnodo.public.metaverso.jpg");
                if (stream != null)
                {
                    using var ms = new MemoryStream();
                    stream.CopyTo(ms);
                    return ms.ToArray();
                }
            }
            catch { }

            return null;
        }

        /// <summary>
        /// IP real del cliente para el limitador (H2). Orden de decisión:
        /// 1) Conexión directa (socket no loopback): manda la IP del socket
        ///    y las cabeceras se ignoran siempre.
        /// 2) Socket loopback sin el marcador del proxy de confianza, o con
        ///    un marcador distinto: las cabeceras pueden venir del cliente,
        ///    así que se ignoran y manda la IP del socket (todo ese tráfico
        ///    comparte el cubo loopback: fail-closed).
        /// 3) Socket loopback con marcador válido: el proxy ya sobrescribió
        ///    X-Forwarded-For con la IP observada en su socket, así que se
        ///    usa su primer valor si analiza como IP válida.
        /// CF-Connecting-IP ya no se lee aquí: el proxy lo elimina al
        /// reenviar y la única fuente autorizada pasa a ser el
        /// X-Forwarded-For marcado. Nota: tras un túnel público el proxy
        /// observa al demonio local del túnel (loopback), así que los
        /// invitados del túnel comparten el cubo 127.0.0.1; es la opción
        /// fail-closed elegida en H2: no se adopta ninguna cabecera fijada
        /// fuera de este proceso.
        /// </summary>
        private static string ObtenerIpCliente(HttpListenerRequest req)
        {
            try
            {
                var remoto = req.RemoteEndPoint?.Address;
                if (remoto == null) return "desconocida";
                if (remoto.IsIPv4MappedToIPv6) remoto = remoto.MapToIPv4();

                if (!IPAddress.IsLoopback(remoto)) return remoto.ToString();

                if (!EsMarcadorProxyValido(req.Headers[CabeceraMarcadorProxy]))
                    return remoto.ToString();

                string? xff = req.Headers["X-Forwarded-For"];
                if (!string.IsNullOrWhiteSpace(xff) &&
                    IPAddress.TryParse(xff.Split(',')[0].Trim(), out var declarada))
                {
                    if (declarada.IsIPv4MappedToIPv6) declarada = declarada.MapToIPv4();
                    return declarada.ToString();
                }
                return remoto.ToString();
            }
            catch
            {
                return "desconocida";
            }
        }

        private static async Task Responder429Async(HttpListenerResponse res, int segundos)
        {
            try
            {
                res.StatusCode = 429;
                res.Headers["Retry-After"] = segundos.ToString();
                var cuerpo = Encoding.UTF8.GetBytes("{\"error\":\"rate_limited\"}");
                res.ContentType = "application/json";
                res.ContentLength64 = cuerpo.Length;
                await res.OutputStream.WriteAsync(cuerpo, 0, cuerpo.Length);
            }
            catch { }
        }
    }
}
