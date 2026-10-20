using System;
using System.IO;
using System.Net;
using System.Text;
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
        private readonly HttpListener _listener = new HttpListener();
        private readonly CancellationTokenSource _cts = new CancellationTokenSource();
        private Thread? _thread;
        private bool _disposed;
        private string? _publicTunnelUrl;

        public bool IsRunning => _listener.IsListening;

        // Seteado desde MainWindow cuando el tunel P2P esta activo
        public string? PublicTunnelUrl
        {
            get => _publicTunnelUrl;
            set => _publicTunnelUrl = value;
        }

        private static readonly int Port = 3030;
        private static readonly string ExeName = "DMWoldVirtualp2pCNX_v0.0.011actualizacion_2069d33a.exe";
        private static readonly string ExeUrl =
            "https://github.com/Chicook/WoldVirtualP2P3D/releases/download/v0.0.111_actualizacion_2069d33a/DMWoldVirtualp2pCNX_v0.0.011actualizacion_2069d33a.exe";

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
        <button class=""copy-btn"" id=""btn-copy-link"" onclick=""copiarEnlace()"">📋 Copiar Enlace de Invitado</button>
      </div>
      <a href=""/descargar"" class=""btn-download-hero"" id=""btn-descarga"">
        <span>⬇</span>
        <span id=""lbl-descarga"">Descargar {ExeName}</span>
      </a>
      <div class=""session-grid"">
        <div class=""info-box"">
          <div class=""label"">🏠 Nodo Anfitrión</div>
          <div class=""val"" id=""val-host"">P2P Host</div>
        </div>
        <div class=""info-box"">
          <div class=""label"">🔗 Enlace P2P de Conexión (túnel efímero)</div>
          <div class=""val"" id=""link-p2p"">{{TUNNEL_URL}}</div>
        </div>
      </div>
    </div>
    <footer>Wold Virtual P2P 3D — Red Descentralizada Peer-to-Peer — Sin Intermediarios</footer>
  </div>
  <script>
    function copiarEnlace(){{
      const url=document.getElementById('link-p2p').innerText.trim();
      navigator.clipboard.writeText(url).then(()=>{{
        const btn=document.getElementById('btn-copy-link');const orig=btn.innerHTML;
        btn.innerHTML='✅ ¡Copiado!';setTimeout(()=>{{btn.innerHTML=orig;}},2500);
      }}).catch(()=>alert('Enlace: '+url));
    }}
    document.getElementById('link-p2p').innerText=window.location.href;
    fetch('/api/info').then(r=>r.json()).then(d=>{{
      if(d.disponible){{
        document.getElementById('lbl-descarga').innerText=`Descargar ${{d.nombre}} (${{d.tamano_mb}} MB)`;
        document.getElementById('btn-descarga').href=d.url_descarga;
      }}
    }}).catch(()=>{{}});
    fetch('/api/p2p-status').then(r=>r.json()).then(d=>{{
      if(d.online && d.tunnel_url) document.getElementById('link-p2p').innerText=d.tunnel_url;
    }}).catch(()=>{{}});
  </script>
</body>
</html>";
        public void Start()
        {
            if (_disposed) return;
            try
            {
                _listener.Prefixes.Add($"http://+:{Port}/");
                _listener.Start();
                _thread = new Thread(ListenerLoop) { IsBackground = true };
                _thread.Start(_cts.Token);
            }
            catch (Exception ex)
            {
                // Puerto en uso o sin permisos: WebNodo no es crítico para el visor.
                System.Diagnostics.Debug.WriteLine($"[WebNodo] No se pudo iniciar: {ex.Message}");
            }
        }

        public void Stop()
        {
            if (_disposed) return;
            try { _cts.Cancel(); } catch { }
            try { _listener.Stop(); } catch { }
            _listener.Prefixes.Clear();
        }

        private void ListenerLoop(object? state)
        {
            var token = (CancellationToken)state!;
            while (!token.IsCancellationRequested && _listener.IsListening)
            {
                try
                {
                    var ctx = _listener.GetContext();
                    _ = Task.Run(() => ProcessRequest(ctx), token);
                }
                catch (HttpListenerException) { break; }
                catch (ObjectDisposedException) { break; }
                catch { break; }
            }
        }

        private async Task ProcessRequest(HttpListenerContext ctx)
        {
            try
            {
                var req = ctx.Request;
                var res = ctx.Response;
                var path = req.Url?.AbsolutePath ?? "/";

                if (path == "/")
                {
                    res.ContentType = "text/html; charset=utf-8";
                    var tunnel = string.IsNullOrWhiteSpace(_publicTunnelUrl)
                        ? $"http://localhost:{Port}/"
                        : _publicTunnelUrl;
                    var html = IndexHtml.Replace("{TUNNEL_URL}", tunnel);
                    var bytes = Encoding.UTF8.GetBytes(html);
                    res.ContentLength64 = bytes.Length;
                    await res.OutputStream.WriteAsync(bytes, 0, bytes.Length);
                }
                else if (path == "/metaverso.jpg")
                {
                    var jpgPath = Path.Combine(AppContext.BaseDirectory, "webnodo", "public", "metaverso.jpg");
                    if (!File.Exists(jpgPath))
                        jpgPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "webnodo", "public", "metaverso.jpg");
                    if (File.Exists(jpgPath))
                    {
                        res.ContentType = "image/jpeg";
                        var bytes = File.ReadAllBytes(jpgPath);
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
                    res.Redirect(ExeUrl);
                }
                else if (path == "/api/info")
                {
                    var json = $"{{\"disponible\":true,\"nombre\":\"{ExeName}\",\"tamano_mb\":\"675.5\",\"url_descarga\":\"{ExeUrl}\"}}";
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
                try { ctx.Response.OutputStream.Close(); } catch { }
            }
        }

        public void Dispose()
        {
            if (_disposed) return;
            Stop();
            _cts.Dispose();
            _listener.Close();
            _disposed = true;
        }
    }
}
