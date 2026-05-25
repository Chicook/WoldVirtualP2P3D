using System;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;

namespace VisorSingularity
{
    public sealed class P2PWebNode
    {
        public string NodeId { get; private set; }
        public string SimulatedUrl { get; private set; }
        public int Port { get; private set; } = 8082;
        public string LocalUrl { get; private set; }
        public string ZipPath { get; private set; }
        public bool IsZipping { get; private set; }
        public bool ZipReady { get; private set; }
        public bool TunnelConnected { get; private set; }
        public string? PublicUrl { get; private set; }

        private HttpListener _listener;
        private CancellationTokenSource? _cts;
        private string _repoPath;
        private IPFSTunnelConnector? _tunnel;

        public event Action<string>? OnStatusChanged;

        public P2PWebNode(string username, string repoPath)
        {
            _repoPath = repoPath;

            int seed = Math.Abs((username + DateTime.Now.Ticks).GetHashCode()) % 90000 + 10000;
            NodeId = $"ND{seed}";
            SimulatedUrl = $"{NodeId}.local";

            Port = FindAvailablePort(8082);
            LocalUrl = $"http://127.0.0.1:{Port}/";

            string tempDir = Path.Combine(Path.GetTempPath(), "WoldVirtualP2P");
            Directory.CreateDirectory(tempDir);
            ZipPath = Path.Combine(tempDir, $"wold_virtual_visor_{NodeId}.zip");

            _listener = new HttpListener();
            _listener.Prefixes.Add(LocalUrl);
            _listener.Prefixes.Add($"http://localhost:{Port}/");
        }

        public void Start()
        {
            _cts = new CancellationTokenSource();
            _listener.Start();

            Task.Run(() => ListenLoop(_cts.Token));
            Task.Run(() => GenerateRepositoryZip());
            Task.Run(() => StartTunnel());

            LogStatus($"Nodo local: {LocalUrl}");
        }

        private async Task StartTunnel()
        {
            try
            {
                _tunnel = new IPFSTunnelConnector(Port);
                _tunnel.OnStatusChanged += msg => LogStatus(msg);
                _tunnel.OnUrlReceived += url =>
                {
                    PublicUrl = url;
                    SimulatedUrl = url;
                    TunnelConnected = true;
                    LogStatus($"Nodo público: {url}");
                };
                _tunnel.OnConnectionChanged += connected =>
                {
                    TunnelConnected = connected;
                    if (!connected) PublicUrl = null;
                };

                await _tunnel.ConnectAsync();
            }
            catch (Exception ex)
            {
                LogStatus($"Error en túnel: {ex.Message}");
                _tunnel?.Dispose();
                _tunnel = null;
            }
        }

        public void Stop()
        {
            try { _cts?.Cancel(); } catch { }
            try { _cts?.Dispose(); } catch { }
            _cts = null;

            try { if (_listener.IsListening) _listener.Stop(); } catch { }

            try { _tunnel?.Disconnect(); } catch { }
            try { _tunnel?.Dispose(); } catch { }
            _tunnel = null;

            try { if (File.Exists(ZipPath)) File.Delete(ZipPath); } catch { }

            TunnelConnected = false;
            LogStatus("Nodo P2P apagado.");
        }

        private int FindAvailablePort(int startingPort)
        {
            int port = startingPort;
            while (port < startingPort + 100)
            {
                try
                {
                    using var c = new System.Net.Sockets.TcpClient();
                    var r = c.BeginConnect("127.0.0.1", port, null, null);
                    if (!r.AsyncWaitHandle.WaitOne(100))
                        return port;
                    c.EndConnect(r);
                }
                catch { return port; }
                port++;
            }
            return startingPort;
        }

        private async Task ListenLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested && _listener.IsListening)
            {
                try
                {
                    var ctx = await _listener.GetContextAsync();
                    var req = ctx.Request;
                    var res = ctx.Response;

                    string path = req.Url?.AbsolutePath.ToLower() ?? "/";

                    if (path == "/visor.zip")
                    {
                        if (!ZipReady || !File.Exists(ZipPath))
                        {
                            res.StatusCode = 404;
                            byte[] err = Encoding.UTF8.GetBytes("El ZIP se está generando. Actualiza en unos segundos.");
                            res.ContentType = "text/plain; charset=UTF-8";
                            res.ContentLength64 = err.Length;
                            await res.OutputStream.WriteAsync(err, 0, err.Length, token);
                        }
                        else
                        {
                            res.StatusCode = 200;
                            res.ContentType = "application/zip";
                            res.AddHeader("Content-Disposition", $"attachment; filename=\"WoldVirtual_Visor_{NodeId}.zip\"");
                            using var fs = File.OpenRead(ZipPath);
                            res.ContentLength64 = fs.Length;
                            await fs.CopyToAsync(res.OutputStream, 81920, token);
                        }
                    }
                    else
                    {
                        byte[] html = Encoding.UTF8.GetBytes(GetInvitePageHtml());
                        res.StatusCode = 200;
                        res.ContentType = "text/html; charset=UTF-8";
                        res.ContentLength64 = html.Length;
                        await res.OutputStream.WriteAsync(html, 0, html.Length, token);
                    }

                    res.OutputStream.Close();
                }
                catch (ObjectDisposedException) { break; }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[P2PWebNode] {ex.Message}");
                }
            }
        }

        private void GenerateRepositoryZip()
        {
            if (IsZipping) return;
            IsZipping = true;
            ZipReady = false;
            LogStatus("Generando ZIP...");

            try
            {
                if (File.Exists(ZipPath))
                    File.Delete(ZipPath);

                using var zs = new FileStream(ZipPath, FileMode.Create);
                using var ar = new ZipArchive(zs, ZipArchiveMode.Create);
                PackDirectory(ar, _repoPath, _repoPath);

                ZipReady = true;
                LogStatus("ZIP listo.");
            }
            catch (Exception ex)
            {
                LogStatus($"Error ZIP: {ex.Message}");
            }
            finally
            {
                IsZipping = false;
            }
        }

        private void PackDirectory(ZipArchive archive, string sourceDir, string rootDir)
        {
            foreach (string file in Directory.GetFiles(sourceDir))
            {
                string rel = Path.GetRelativePath(rootDir, file);
                try { archive.CreateEntryFromFile(file, rel); }
                catch (Exception ex) { Debug.WriteLine($"Error añadiendo {rel}: {ex.Message}"); }
            }

            foreach (string dir in Directory.GetDirectories(sourceDir))
            {
                if (Path.GetFileName(dir).Equals(".git", StringComparison.OrdinalIgnoreCase))
                    continue;

                PackDirectory(archive, dir, rootDir);
            }
        }

        private string GetInvitePageHtml()
        {
            string ready = ZipReady
                ? "El paquete del Visor 3D está listo para descargar."
                : "Generando paquete del Visor 3D...";

            string btnClass = ZipReady ? "" : "disabled";
            string dlUrl = ZipReady ? "/visor.zip" : "#";

            string tunnel = "";
            if (!string.IsNullOrEmpty(PublicUrl))
            {
                tunnel = $@"
        <div class=""card-info"" style=""margin-top:15px;border-color:#00ff8c;"">
            <div class=""peer-id-label"">URL Pública (Sesión Actual)</div>
            <div class=""peer-id-val"" style=""font-size:13px;"">{PublicUrl}</div>
            <div class=""peer-id-label"" style=""margin-top:8px;"">Esta URL expira al cerrar sesión</div>
        </div>";
            }

            return $@"<!DOCTYPE html>
<html lang=""es"">
<head>
    <meta charset=""UTF-8"">
    <meta name=""viewport"" content=""width=device-width, initial-scale=1.0"">
    <title>Invitación Wold Virtual P2P</title>
    <link href=""https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap"" rel=""stylesheet"">
    <style>
        :root {{
            --bg: #060913;
            --card: rgba(17,22,37,0.7);
            --primary: #66FCF1;
            --glow: rgba(102,252,241,0.4);
            --sec: #45A29E;
            --accent: #00ff8c;
            --text: #C5C6C7;
            --bright: #FFFFFF;
        }}
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            background:var(--bg); color:var(--text);
            font-family:'Outfit',sans-serif; min-height:100vh;
            display:flex; align-items:center; justify-content:center;
            overflow-x:hidden; position:relative;
        }}
        body::before {{
            content:''; position:absolute; inset:0;
            background-image:
                linear-gradient(rgba(102,252,241,0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(102,252,241,0.03) 1px, transparent 1px);
            background-size:30px 30px; z-index:1;
        }}
        .glow {{
            position:absolute; width:400px; height:400px; border-radius:50%;
            background:radial-gradient(circle, rgba(102,252,241,0.08) 0%, transparent 70%);
            z-index:2; pointer-events:none;
        }}
        .g1 {{ top:-100px; right:-100px; }}
        .g2 {{ bottom:-100px; left:-100px; }}
        .container {{
            width:90%; max-width:580px; background:var(--card);
            border:1px solid var(--sec); border-radius:16px; padding:40px;
            backdrop-filter:blur(12px);
            box-shadow:0 8px 32px 0 rgba(0,0,0,0.37), 0 0 15px var(--glow);
            z-index:10; text-align:center; border-top:2px solid var(--primary);
            position:relative;
        }}
        .logo {{ font-size:50px; margin-bottom:10px; filter:drop-shadow(0 0 8px var(--primary)); }}
        h1 {{ font-size:28px; font-weight:800; color:var(--bright); letter-spacing:2px; text-transform:uppercase; margin-bottom:5px; text-shadow:0 0 10px var(--glow); }}
        .sub {{ color:var(--primary); font-size:14px; font-weight:600; text-transform:uppercase; letter-spacing:3px; margin-bottom:25px; }}
        .info {{ background:rgba(6,9,19,0.8); border:1px dashed rgba(102,252,241,0.3); border-radius:8px; padding:15px; margin-bottom:25px; }}
        .label {{ font-size:11px; text-transform:uppercase; letter-spacing:2px; color:var(--sec); margin-bottom:5px; }}
        .val {{ font-size:16px; font-weight:600; color:var(--accent); text-shadow:0 0 8px rgba(0,255,140,0.3); word-break:break-all; }}
        p {{ font-size:14px; line-height:1.6; margin-bottom:30px; }}
        .btn {{
            display:inline-block; background:transparent; color:var(--primary);
            border:2px solid var(--primary); padding:14px 30px; font-size:15px;
            font-weight:600; text-transform:uppercase; letter-spacing:2px;
            border-radius:8px; cursor:pointer; text-decoration:none;
            transition:all .3s ease; box-shadow:0 0 10px rgba(102,252,241,0.1); width:100%;
        }}
        .btn:hover:not(.d) {{ background:var(--primary); color:var(--bg); box-shadow:0 0 20px var(--glow); transform:translateY(-2px); }}
        .btn.d {{ border-color:#334; color:#556; cursor:not-allowed; pointer-events:none; }}
        .st {{ margin-top:15px; font-size:12px; color:var(--accent); }}
        .ft {{ margin-top:35px; font-size:11px; color:rgba(197,198,199,0.4); text-transform:uppercase; letter-spacing:1px; }}
    </style>
</head>
<body>
    <div class=""glow g1""></div>
    <div class=""glow g2""></div>
    <div class=""container"">
        <div class=""logo"">&#127760;</div>
        <h1>Wold Virtual 3D</h1>
        <div class=""sub"">P2P Network Node</div>
        <div class=""info"">
            <div class=""label"">Nodo ID</div>
            <div class=""val"">{NodeId}</div>
        </div>
        <p>Te han invitado al metaverso descentralizado 3D. Comparte este enlace para que otros descarguen el visor.</p>
        <a href=""{dlUrl}"" class=""btn {btnClass}"">Descargar Visor (.ZIP)</a>
        <div class=""st"">{ready}</div>
        {tunnel}
        <div class=""ft"">Powered by Cloudflare Tunnel &amp; C# WoldVirtual P2P Engine</div>
    </div>
</body>
</html>";
        }

        private void LogStatus(string msg)
        {
            OnStatusChanged?.Invoke(msg);
        }
    }
}
