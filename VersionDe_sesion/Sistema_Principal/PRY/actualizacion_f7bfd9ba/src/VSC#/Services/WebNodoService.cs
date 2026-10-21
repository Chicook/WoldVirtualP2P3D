using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Services
{
    /// <summary>
    /// WebNodo embebido en el visor C# (sin Node.js).
    /// Sirve en http://localhost:3030/:
    ///   GET /           -> portal de descarga (index.html)
    ///   GET /metaverso.jpg -> imagen del portal
    ///   GET /descargar  -> redirige al release de GitHub
    ///   GET /api/info  -> JSON con info del .exe disponible
    ///   GET /api/p2p-status -> estado de la sesion P2P (si esta activa)
    /// </summary>
    public class WebNodoService : IDisposable
    {
        private HttpListener? _listener;
        private TcpListener? _proxyListener;
        private int _internalPort;
        private CancellationTokenSource? _cts;
        private Thread? _thread;
        private bool _disposed;
        private string? _publicTunnelUrl;
        private string? _startError;
        private readonly object _lock = new object();

        public bool IsRunning
        {
            get
            {
                lock (_lock)
                {
                    return _listener != null && _listener.IsListening;
                }
            }
        }

        public string? StartError => _startError;

        public int ActivePort { get; private set; } = 3030;

        // Seteado desde MainWindow cuando el tunel P2P esta activo
        public string? PublicTunnelUrl
        {
            get => _publicTunnelUrl;
            set => _publicTunnelUrl = value;
        }

        public static readonly int Port = 3030;
        private const string ExeNameFallback = "DMWoldVirtualp2pCNXv0.1.0_p2p.exe";
        private const string ExeUrlFallback =
            "https://github.com/Chicook/WoldVirtualP2P3D/releases/download/v.0.1.0/DMWoldVirtualp2pCNXv0.1.0_p2p.exe";

        // El nombre, la URL y el tamaño salen de release.json (junto al .exe) cuando existe.
        private static readonly (string Name, string Url, string SizeMb) Release = LeerRelease();
        private static string ExeName => Release.Name;
        private static string ExeUrl => Release.Url;
        private static string ExeSizeMb => Release.SizeMb;

        // Token por sesión para /api/*: la página lo recibe embebido y lo envía en cada llamada.
        private static readonly string _apiToken =
            Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant();

        // La página y los estáticos NO se limitan: solo /api/* y /descargar.
        private static readonly RateLimiter _limiteApi = new();
        private static readonly RateLimiter _limiteDescarga = new();
        private readonly SemaphoreSlim _descargaUnica = new(1, 1);

        private static (string Name, string Url, string SizeMb) LeerRelease()
        {
            try
            {
                string path = Path.Combine(AppContext.BaseDirectory, "release.json");
                if (File.Exists(path))
                {
                    using var doc = JsonDocument.Parse(File.ReadAllText(path));
                    var root = doc.RootElement;
                    string? name = root.TryGetProperty("exe", out var e) ? e.GetString() : null;
                    string? url = root.TryGetProperty("url", out var u) ? u.GetString() : null;
                    double size = root.TryGetProperty("size_mb", out var s) && s.TryGetDouble(out var d) ? d : 0;
                    if (!string.IsNullOrWhiteSpace(name) && !string.IsNullOrWhiteSpace(url))
                        return (name!, url!, size > 0 ? size.ToString("0.0") : "—");
                }
            }
            catch { /* release.json corrupto: usar valores por defecto */ }

            return (ExeNameFallback, ExeUrlFallback, "—");
        }

        private static string IndexHtml =>
            $@"<html lang=""es"">
<head>
  <meta charset=""UTF-8""/>
  <meta name=""viewport"" content=""width=device-width, initial-scale=1.0""/>
  <title>Wold Virtual P2P 3D — WebNodo</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',sans-serif;background:#070913;color:#f1f5f9;min-height:100vh;display:flex;flex-direction:column;align-items:center;overflow-x:hidden}}
    .cyber-grid{{position:fixed;inset:0;z-index:0;pointer-events:none;
      background-image:linear-gradient(rgba(0,217,255,0.04) 1px,transparent 1px),linear-gradient(90deg,rgba(0,217,255,0.04) 1px,transparent 1px);
      background-size:50px 50px;animation:gridDrift 28s linear infinite}}
    @keyframes gridDrift{{0%{{transform:translateY(0)}}100%{{transform:translateY(50px)}}}}
    .container{{position:relative;z-index:1;max-width:860px;width:100%;padding:40px 24px 80px;display:flex;flex-direction:column;align-items:center;gap:28px}}
    header{{text-align:center}}
    h1{{font-size:clamp(30px,5.5vw,54px);font-weight:900;line-height:1.12;
      background:linear-gradient(135deg,#ffffff 10%,#00d9ff 55%,#a855f7 100%);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:12px}}
    .subtitle{{color:#94a3b8;font-size:16px;max-width:620px;margin:0 auto;line-height:1.5}}
    .portal-frame{{width:100%;border-radius:20px;overflow:hidden;background:#0d1224;
      border:1px solid rgba(0,217,255,0.3);box-shadow:0 12px 40px rgba(0,0,0,0.6)}}
    .portal-img{{width:100%;height:auto;display:block;max-height:440px;object-fit:cover}}
    .download-card{{width:100%;background:rgba(13,21,42,0.75);border:1px solid rgba(0,217,255,0.22);
      border-radius:20px;padding:34px;backdrop-filter:blur(16px);box-shadow:0 10px 40px rgba(0,0,0,0.45);
      display:flex;flex-direction:column;gap:24px}}
    .dl-header{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px}}
    .dl-title-box h2{{font-size:22px;font-weight:700;color:#fff;margin-bottom:4px}}
    .dl-title-box p{{font-size:13.5px;color:#94a3b8}}
    .btn-download-hero{{width:100%;padding:18px 30px;
      background:linear-gradient(135deg,#00d9ff 0%,#0284c7 50%,#9333ea 100%);
      color:#fff;font-family:'Segoe UI',sans-serif;font-size:18px;font-weight:800;
      text-decoration:none;border:none;border-radius:14px;cursor:pointer;
      display:flex;align-items:center;justify-content:center;gap:12px;
      box-shadow:0 6px 30px rgba(0,217,255,0.4);transition:transform 0.15s,box-shadow 0.25s}}
    .btn-download-hero:hover{{transform:translateY(-2px);box-shadow:0 10px 40px rgba(0,217,255,0.6)}}
    .session-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;width:100%}}
    .info-box{{background:rgba(13,21,42,0.5);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:14px 18px}}
    .info-box .label{{font-size:11px;text-transform:uppercase;letter-spacing:0.8px;color:#94a3b8;font-weight:600;margin-bottom:4px}}
    .info-box .val{{font-family:'Consolas','JetBrains Mono',monospace;font-size:13.5px;font-weight:600;color:#fff;word-break:break-all}}
    .copy-btn{{background:rgba(0,217,255,0.1);border:1px solid #00d9ff;color:#00d9ff;padding:8px 14px;
      border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;display:inline-flex;align-items:center;gap:6px}}
    .copy-btn:hover{{background:rgba(0,217,255,0.2)}}
    footer{{font-size:12.5px;color:#94a3b8;text-align:center;line-height:1.6}}
  </style>
</head>
<body>
  <div class=""cyber-grid""></div>
  <div class=""container"">
    <header>
      <h1>Wold Virtual P2P 3D</h1>
      <p class=""subtitle"">Portal WebNodo — descarga directa del visor desde este nodo anfitrión.</p>
    </header>
    <div class=""portal-frame"">
      <img src=""/metaverso.jpg"" alt=""Portal Holográfico Metaverso 3D"" class=""portal-img""/>
    </div>
    <div class=""download-card"">
      <div class=""dl-header"">
        <div class=""dl-title-box"">
          <h2>Descargar Visor 3D</h2>
          <p>Ejecutable portable Windows 64-bit · Sin instalación requerida</p>
        </div>
        <button class=""copy-btn"" id=""btn-copy-link"" onclick=""copiarEnlace()""> Copiar Enlace de Invitado</button>
      </div>
      <a href=""/descargar"" class=""btn-download-hero"" id=""btn-descarga"">
        <span></span>
        <span id=""lbl-descarga"">Descargar {ExeName}</span>
      </a>
      <div class=""session-grid"">
        <div class=""info-box"">
          <div class=""label""> Nodo Anfitrión</div>
          <div class=""val"" id=""val-host"">P2P Host</div>
        </div>
        <div class=""info-box"">
          <div class=""label""> Enlace P2P de Conexión (túnel efímero)</div>
          <div class=""val"" id=""link-p2p"">{{TUNNEL_URL}}</div>
        </div>
      </div>
    </div>
    <footer>Wold Virtual P2P 3D — Red Descentralizada Peer-to-Peer — Sin Intermediarios</footer>
  </div>
  <script>
    const WT='{_apiToken}';
    function copiarEnlace(){{
      const url=document.getElementById('link-p2p').innerText.trim();
      navigator.clipboard.writeText(url).then(()=>{{
        const btn=document.getElementById('btn-copy-link');const orig=btn.innerHTML;
        btn.innerHTML='OK ¡Copiado!';setTimeout(()=>{{btn.innerHTML=orig;}},2500);
      }}).catch(()=>alert('Enlace: '+url));
    }}
    document.getElementById('link-p2p').innerText=window.location.href;
    fetch('/api/info?token='+WT).then(r=>r.json()).then(d=>{{
      if(d.disponible){{
        document.getElementById('lbl-descarga').innerText=`Descargar ${{d.nombre}} (${{d.tamano_mb}} MB)`;
        document.getElementById('btn-descarga').href=d.url_descarga;
      }}
    }}).catch(()=>{{}});
    fetch('/api/p2p-status?token='+WT).then(r=>r.json()).then(d=>{{
      if(d.online && d.tunnel_url) document.getElementById('link-p2p').innerText=d.tunnel_url;
    }}).catch(()=>{{}});
  </script>
</body>
</html>";
        public void Start()
        {
            lock (_lock)
            {
                if (_disposed) return;
                if (IsRunning)
                {
                    _startError = null;
                    return;
                }

                _startError = null;
                _cts = new CancellationTokenSource();

                // Si había recursos previos en estado inconsistente, limpiarlo
                try { _proxyListener?.Stop(); } catch { }
                _proxyListener = null;
                try { _listener?.Close(); } catch { }
                _listener = null;

                // Intentar puertos en rango [3030..3040]
                int[] candidatePorts = new int[] { 3030, 3031, 3032, 3033, 3034, 3035, 3036, 3037, 3038, 3039, 3040 };
                Exception? lastEx = null;

                // Opción principal: Proxy TCP en candidatePort + HttpListener en internalPort
                // Esto reescribe la cabecera Host a "localhost:{internalPort}", lo que elimina
                // completamente el error "400 Bad Request - Invalid Hostname" de HTTP.sys en túneles Cloudflare/SSH.
                foreach (int port in candidatePorts)
                {
                    try
                    {
                        int intPort = port + 100;
                        var candidateHttp = new HttpListener();
                        candidateHttp.Prefixes.Add($"http://localhost:{intPort}/");
                        candidateHttp.Prefixes.Add($"http://127.0.0.1:{intPort}/");
                        candidateHttp.Start();

                        var candidateProxy = new TcpListener(IPAddress.Loopback, port);
                        candidateProxy.Start();

                        _internalPort = intPort;
                        _listener = candidateHttp;
                        _proxyListener = candidateProxy;
                        ActivePort = port;
                        lastEx = null;
                        break;
                    }
                    catch (Exception exProxy)
                    {
                        lastEx = exProxy;
                        try { _proxyListener?.Stop(); } catch { }
                        _proxyListener = null;
                        try { _listener?.Close(); } catch { }
                        _listener = null;
                    }
                }

                // Fallback: Si no se pudo iniciar el proxy TCP, probar HttpListener directo
                if (_listener == null)
                {
                    foreach (int port in candidatePorts)
                    {
                        try
                        {
                            var candidate = new HttpListener();
                            candidate.Prefixes.Add($"http://localhost:{port}/");
                            candidate.Prefixes.Add($"http://127.0.0.1:{port}/");
                            candidate.Start();

                            _listener = candidate;
                            ActivePort = port;
                            lastEx = null;
                            break;
                        }
                        catch (Exception exDirect)
                        {
                            lastEx = exDirect;
                        }
                    }
                }

                if (_listener != null && _listener.IsListening)
                {
                    _thread = new Thread(ListenerLoop) { IsBackground = true };
                    _thread.Start(_cts.Token);

                    if (_proxyListener != null)
                    {
                        Task.Run(() => ProxyLoop(_cts.Token));
                        System.Diagnostics.Debug.WriteLine($"[WebNodo] Proxy TCP en puerto {ActivePort} -> HttpListener interno en {_internalPort}");
                    }
                    else
                    {
                        System.Diagnostics.Debug.WriteLine($"[WebNodo] HttpListener directo en puerto {ActivePort}");
                    }
                }
                else
                {
                    _startError = lastEx?.Message ?? "No se pudo enlazar ningún puerto local.";
                    System.Diagnostics.Debug.WriteLine($"[WebNodo] No se pudo iniciar: {_startError}");
                }
            }
        }

        public void Stop()
        {
            lock (_lock)
            {
                if (_disposed) return;
                try { _cts?.Cancel(); } catch { }
                try { _proxyListener?.Stop(); } catch { }
                _proxyListener = null;
                try { _listener?.Stop(); } catch { }
                try { _listener?.Close(); } catch { }
                _listener = null;
            }
        }

        private async Task ProxyLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    TcpListener? pl;
                    lock (_lock) { pl = _proxyListener; }
                    if (pl == null) break;

                    TcpClient client = await pl.AcceptTcpClientAsync(token).ConfigureAwait(false);
                    _ = Task.Run(() => HandleProxyClientAsync(client, token), token);
                }
                catch (ObjectDisposedException) { break; }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"[WebNodo-Proxy] Error accept: {ex.Message}");
                }
            }
        }

        private async Task HandleProxyClientAsync(TcpClient client, CancellationToken token)
        {
            using (client)
            {
                client.NoDelay = true;
                using var target = new TcpClient();
                try
                {
                    await target.ConnectAsync(IPAddress.Loopback, _internalPort, token).ConfigureAwait(false);
                    target.NoDelay = true;

                    using NetworkStream clientStream = client.GetStream();
                    using NetworkStream targetStream = target.GetStream();

                    byte[] buffer = new byte[8192];
                    int bytesRead = 0;
                    using var ms = new MemoryStream();

                    while (true)
                    {
                        int read = await clientStream.ReadAsync(buffer, 0, buffer.Length, token).ConfigureAwait(false);
                        if (read <= 0) break;
                        ms.Write(buffer, 0, read);
                        bytesRead += read;

                        byte[] currentBytes = ms.ToArray();
                        if (FindBytes(currentBytes, new byte[] { 13, 10, 13, 10 }) != -1 || bytesRead > 16384)
                        {
                            break;
                        }
                    }

                    byte[] requestBytes = ms.ToArray();
                    if (requestBytes.Length > 0)
                    {
                        byte[] separator = new byte[] { 13, 10, 13, 10 };
                        int headerEndIdx = FindBytes(requestBytes, separator);

                        if (headerEndIdx >= 0)
                        {
                            string headersStr = Encoding.UTF8.GetString(requestBytes, 0, headerEndIdx);
                            var hostRegex = new Regex(@"\r\nHost:\s*[^\r\n]+", RegexOptions.IgnoreCase);

                            if (hostRegex.IsMatch(headersStr))
                            {
                                headersStr = hostRegex.Replace(headersStr, $"\r\nHost: localhost:{_internalPort}");
                            }
                            else
                            {
                                headersStr += $"\r\nHost: localhost:{_internalPort}";
                            }

                            byte[] headerBytes = Encoding.UTF8.GetBytes(headersStr);
                            await targetStream.WriteAsync(headerBytes, 0, headerBytes.Length, token).ConfigureAwait(false);
                            await targetStream.WriteAsync(separator, 0, separator.Length, token).ConfigureAwait(false);

                            int bodyOffset = headerEndIdx + separator.Length;
                            int bodyLength = requestBytes.Length - bodyOffset;
                            if (bodyLength > 0)
                            {
                                await targetStream.WriteAsync(requestBytes, bodyOffset, bodyLength, token).ConfigureAwait(false);
                            }
                        }
                        else
                        {
                            await targetStream.WriteAsync(requestBytes, 0, requestBytes.Length, token).ConfigureAwait(false);
                        }
                    }

                    var clientToTarget = clientStream.CopyToAsync(targetStream, token);
                    var targetToClient = targetStream.CopyToAsync(clientStream, token);
                    await Task.WhenAll(clientToTarget, targetToClient).ConfigureAwait(false);
                }
                catch { }
            }
        }

        private static int FindBytes(byte[] src, byte[] pattern)
        {
            for (int i = 0; i <= src.Length - pattern.Length; i++)
            {
                bool match = true;
                for (int j = 0; j < pattern.Length; j++)
                {
                    if (src[i + j] != pattern[j])
                    {
                        match = false;
                        break;
                    }
                }
                if (match) return i;
            }
            return -1;
        }

        private void ListenerLoop(object? state)
        {
            var token = (CancellationToken)state!;
            while (!token.IsCancellationRequested)
            {
                HttpListener? l;
                lock (_lock) { l = _listener; }
                if (l == null || !l.IsListening) break;

                try
                {
                    var ctx = l.GetContext();
                    _ = Task.Run(() => ProcessRequest(ctx), token);
                }
                catch (HttpListenerException) { break; }
                catch (ObjectDisposedException) { break; }
                catch { break; }
            }
        }

        private static string ObtenIndexHtml()
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

            // 3. Fallback inline HTML
            return IndexHtml;
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
                    // PROXY WEBSOCKET para P2P (Godot -> localhost:8911)
                    await ProxyWebSocketAsync(ctx);
                    return;
                }

                // /api/* exige el token de esta sesión (evita llamadas cruzadas desde webs ajenas).
                if (path.StartsWith("/api/", StringComparison.OrdinalIgnoreCase) &&
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
                    res.ContentType = "text/html; charset=utf-8";
                    var tunnel = string.IsNullOrWhiteSpace(_publicTunnelUrl)
                        ? $"http://localhost:{ActivePort}/"
                        : _publicTunnelUrl;
                    var html = ObtenIndexHtml();
                    html = html.Replace("{{TUNNEL_URL}}", tunnel);
                    html = html.Replace("{{API_TOKEN}}", _apiToken);
                    if (!string.IsNullOrWhiteSpace(_publicTunnelUrl))
                    {
                        html = html.Replace("http://localhost:3030/", tunnel);
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
                    VisorLog.Info($"WebNodo: descarga solicitada desde {req.RemoteEndPoint} ({ExeName})");
                    string localExe = Path.Combine(AppContext.BaseDirectory, "webnodo", "descargas", ExeName);
                    if (!File.Exists(localExe))
                        localExe = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "webnodo", "descargas", ExeName);
                    if (!File.Exists(localExe))
                        localExe = Path.Combine(AppContext.BaseDirectory, ExeName);

                    if (File.Exists(localExe))
                    {
                        res.ContentType = "application/octet-stream";
                        res.AddHeader("Content-Disposition", $"attachment; filename=\"{ExeName}\"");
                        using var fs = File.OpenRead(localExe);
                        res.ContentLength64 = fs.Length;
                        await fs.CopyToAsync(res.OutputStream);
                    }
                    else
                    {
                        res.Redirect(ExeUrl);
                    }
                }
                else if (path == "/api/info")
                {
                    var json = $"{{\"disponible\":true,\"nombre\":\"{ExeName}\",\"tamano_mb\":\"{ExeSizeMb}\",\"url_descarga\":\"/descargar\"}}";
                    var bytes = Encoding.UTF8.GetBytes(json);
                    res.ContentType = "application/json";
                    res.ContentLength64 = bytes.Length;
                    await res.OutputStream.WriteAsync(bytes, 0, bytes.Length);
                }
                else if (path == "/api/p2p-status")
                {
                    var tunnel = string.IsNullOrWhiteSpace(_publicTunnelUrl) ? "" : _publicTunnelUrl;
                    var json = $"{{\"online\":{(!string.IsNullOrWhiteSpace(tunnel)).ToString().ToLower()},\"tunnel_url\":\"{tunnel}\",\"timestamp\":\"{DateTime.UtcNow:o}\"}}";
                    var bytes = Encoding.UTF8.GetBytes(json);
                    res.ContentType = "application/json";
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
        /// IP real del cliente. Detrás del túnel la conexión llega de loopback, así que
        /// se usa CF-Connecting-IP / X-Forwarded-For solo en ese caso.
        /// </summary>
        private static string ObtenerIpCliente(HttpListenerRequest req)
        {
            try
            {
                var remoto = req.RemoteEndPoint?.Address;
                if (remoto != null && IPAddress.IsLoopback(remoto))
                {
                    string? cf = req.Headers["CF-Connecting-IP"];
                    if (!string.IsNullOrWhiteSpace(cf)) return cf.Trim();

                    string? xff = req.Headers["X-Forwarded-For"];
                    if (!string.IsNullOrWhiteSpace(xff)) return xff.Split(',')[0].Trim();
                }
                return remoto?.ToString() ?? "desconocida";
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

        private async Task ProxyWebSocketAsync(HttpListenerContext ctx)
        {
            try
            {
                var wsContext = await ctx.AcceptWebSocketAsync(null);
                var clientWs = wsContext.WebSocket;

                using var serverWs = new System.Net.WebSockets.ClientWebSocket();
                await serverWs.ConnectAsync(new Uri("ws://localhost:8911"), CancellationToken.None);

                var clientToRemote = Task.Run(async () =>
                {
                    byte[] buffer = new byte[8192];
                    while (clientWs.State == System.Net.WebSockets.WebSocketState.Open && serverWs.State == System.Net.WebSockets.WebSocketState.Open)
                    {
                        var res = await clientWs.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
                        if (res.MessageType == System.Net.WebSockets.WebSocketMessageType.Close) break;
                        await serverWs.SendAsync(new ArraySegment<byte>(buffer, 0, res.Count), res.MessageType, res.EndOfMessage, CancellationToken.None);
                    }
                });

                var remoteToClient = Task.Run(async () =>
                {
                    byte[] buffer = new byte[8192];
                    while (clientWs.State == System.Net.WebSockets.WebSocketState.Open && serverWs.State == System.Net.WebSockets.WebSocketState.Open)
                    {
                        var res = await serverWs.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
                        if (res.MessageType == System.Net.WebSockets.WebSocketMessageType.Close) break;
                        await clientWs.SendAsync(new ArraySegment<byte>(buffer, 0, res.Count), res.MessageType, res.EndOfMessage, CancellationToken.None);
                    }
                });

                await Task.WhenAny(clientToRemote, remoteToClient);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[WebNodo-WSProxy] Error: {ex.Message}");
            }
            finally
            {
                ctx.Response.Close();
            }
        }

        public void Dispose()
        {
            lock (_lock)
            {
                if (_disposed) return;
                Stop();
                try { _cts?.Dispose(); } catch { }
                _disposed = true;
            }
        }
    }
}
