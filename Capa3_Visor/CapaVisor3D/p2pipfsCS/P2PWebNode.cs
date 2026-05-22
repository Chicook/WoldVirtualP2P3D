using System;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;
using Ipfs.Engine;

namespace VisorSingularity
{
    /// <summary>
    /// Nodo P2P del Visor WoldVirtual.
    /// — Servidor HTTP local (LAN / fallback) en puerto dinámico.
    /// — Motor IPFS real (Ipfs.Engine, C# puro) para publicar el ZIP en la red
    ///   IPFS pública y generar un enlace que cualquiera puede abrir desde internet.
    /// </summary>
    public class P2PWebNode
    {
        // ── Propiedades públicas ──────────────────────────────────────────────
        public string NodeId        { get; private set; }
        public string SimulatedUrl  { get; private set; }   // www.NDxxxxx.ipfs  (visual)
        public int    Port          { get; private set; } = 8082;
        public string LocalUrl      { get; private set; }   // http://127.0.0.1:PORT/
        public string ZipPath       { get; private set; }

        // Estado ZIP
        public bool IsZipping  { get; private set; } = false;
        public bool ZipReady   { get; private set; } = false;

        // IPFS real
        public string? RealCid     { get; private set; }   // CIDv1 del ZIP en IPFS
        public string? GatewayUrl  { get; private set; }   // https://ipfs.io/ipfs/<CID>
        public bool    IsOnIpfs    { get; private set; } = false;

        // ── Campos privados ───────────────────────────────────────────────────
        private HttpListener              _listener;
        private CancellationTokenSource?  _cts;
        private string                    _repoPath;
        private IpfsEngine?               _ipfsEngine;

        public event Action<string>? OnStatusChanged;

        // ── Constructor ───────────────────────────────────────────────────────
        public P2PWebNode(string username, string repoPath)
        {
            _repoPath = repoPath;

            // NodeId único por sesión
            int seed = Math.Abs((username + DateTime.Now.Ticks).GetHashCode()) % 90000 + 10000;
            NodeId       = $"ND{seed}";
            SimulatedUrl = $"www.{NodeId}.ipfs";

            // Puerto disponible a partir del 8082
            Port     = FindAvailablePort(8082);
            LocalUrl = $"http://127.0.0.1:{Port}/";

            // Ruta del ZIP temporal
            string tempDir = Path.Combine(Path.GetTempPath(), "WoldVirtualP2P");
            Directory.CreateDirectory(tempDir);
            ZipPath = Path.Combine(tempDir, $"wold_virtual_visor_{NodeId}.zip");

            _listener = new HttpListener();
            _listener.Prefixes.Add(LocalUrl);
            _listener.Prefixes.Add($"http://localhost:{Port}/");
        }

        // ── Inicio ────────────────────────────────────────────────────────────
        public void Start()
        {
            _cts = new CancellationTokenSource();
            _listener.Start();

            // Servidor HTTP local (LAN / fallback)
            Task.Run(() => ListenLoop(_cts.Token));

            // Generar ZIP y luego subirlo a IPFS en segundo plano
            Task.Run(() => GenerateZipThenUploadToIpfs());

            LogStatus($"Nodo local activo: {LocalUrl} — conectando a IPFS...");
        }

        // ── Parada ────────────────────────────────────────────────────────────
        public void Stop()
        {
            _cts?.Cancel();
            _cts?.Dispose();
            _cts = null;

            if (_listener?.IsListening == true)
            {
                try { _listener.Stop(); _listener.Close(); } catch { }
            }

            if (_ipfsEngine != null)
            {
                try { _ipfsEngine.StopAsync().Wait(3000); } catch { }
                _ipfsEngine = null;
            }

            if (File.Exists(ZipPath))
            {
                try { File.Delete(ZipPath); } catch { }
            }

            LogStatus("Nodo P2P apagado.");
        }

        // ── Flujo principal: ZIP → IPFS ───────────────────────────────────────
        private async Task GenerateZipThenUploadToIpfs()
        {
            // 1. Generar ZIP del visor
            GenerateRepositoryZip();
            if (!ZipReady) return;

            // 2. Iniciar motor IPFS (puro C#, sin binarios externos)
            try
            {
                string ipfsRepo = Path.Combine(
                    _repoPath, "..", "Estado_Global", ".ipfs-woldvirtual");

                _ipfsEngine = new IpfsEngine("WoldVirtualP2P_Node".ToCharArray());
                _ipfsEngine.Options.Repository.Folder = Path.GetFullPath(ipfsRepo);

                LogStatus("Iniciando motor IPFS...");
                await _ipfsEngine.StartAsync();
                LogStatus("Motor IPFS activo. Subiendo ZIP a la red...");
            }
            catch (Exception ex)
            {
                LogStatus($"IPFS no disponible ({ex.Message}). Enlace local activo.");
                return;
            }

            // 3. Añadir ZIP a IPFS → obtener CID público
            await AddZipToIpfsAsync();
        }

        private async Task AddZipToIpfsAsync()
        {
            try
            {
                await using var stream = File.OpenRead(ZipPath);
                var node = await _ipfsEngine!.FileSystem.AddAsync(
                    stream,
                    $"WoldVirtual_Visor_{NodeId}.zip",
                    new Ipfs.CoreApi.AddFileOptions { Pin = true });

                RealCid    = node.Id.ToString();
                GatewayUrl = $"https://ipfs.io/ipfs/{RealCid}";
                IsOnIpfs   = true;

                LogStatus($"✅ ZIP en IPFS | CID: {RealCid[..14]}...");
            }
            catch (Exception ex)
            {
                LogStatus($"Error al subir a IPFS: {ex.Message}");
                Debug.WriteLine($"[IPFS] Error: {ex}");
            }
        }

        // ── Servidor HTTP local ───────────────────────────────────────────────
        private async Task ListenLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested && _listener.IsListening)
            {
                try
                {
                    var ctx      = await _listener.GetContextAsync();
                    var request  = ctx.Request;
                    var response = ctx.Response;
                    string path  = request.Url?.AbsolutePath.ToLower() ?? "/";

                    if (path == "/visor.zip")
                    {
                        await ServeZip(response);
                    }
                    else
                    {
                        byte[] buf = Encoding.UTF8.GetBytes(GetInvitePageHtml());
                        response.StatusCode   = 200;
                        response.ContentType  = "text/html; charset=UTF-8";
                        response.ContentLength64 = buf.Length;
                        await response.OutputStream.WriteAsync(buf, 0, buf.Length);
                    }
                    response.OutputStream.Close();
                }
                catch (ObjectDisposedException) { break; }
                catch (Exception ex) { Debug.WriteLine($"[HTTP-P2P] {ex.Message}"); }
            }
        }

        private async Task ServeZip(HttpListenerResponse response)
        {
            if (!ZipReady || !File.Exists(ZipPath))
            {
                byte[] err = Encoding.UTF8.GetBytes("ZIP generándose, intenta en unos segundos.");
                response.StatusCode      = 404;
                response.ContentType     = "text/plain; charset=UTF-8";
                response.ContentLength64 = err.Length;
                await response.OutputStream.WriteAsync(err, 0, err.Length);
                return;
            }
            response.StatusCode = 200;
            response.ContentType = "application/zip";
            response.AddHeader("Content-Disposition",
                $"attachment; filename=\"WoldVirtual_Visor_{NodeId}.zip\"");
            await using var fs = File.OpenRead(ZipPath);
            response.ContentLength64 = fs.Length;
            await fs.CopyToAsync(response.OutputStream);
        }

        // ── Generación del ZIP ────────────────────────────────────────────────
        private void GenerateRepositoryZip()
        {
            if (IsZipping) return;
            IsZipping = true;
            ZipReady  = false;
            LogStatus("Comprimiendo visor (excluyendo carpetas pesadas)...");

            try
            {
                if (File.Exists(ZipPath)) File.Delete(ZipPath);

                using var zipStream = new FileStream(ZipPath, FileMode.Create);
                using var archive   = new ZipArchive(zipStream, ZipArchiveMode.Create);
                AddDirectoryToZip(archive, _repoPath, _repoPath);

                ZipReady = true;
                LogStatus("ZIP listo. Subiendo a IPFS...");
            }
            catch (Exception ex)
            {
                LogStatus($"Error al comprimir: {ex.Message}");
                Debug.WriteLine($"[ZIP] {ex}");
            }
            finally { IsZipping = false; }
        }

        private void AddDirectoryToZip(ZipArchive archive, string sourceDir, string rootDir)
        {
            foreach (string file in Directory.GetFiles(sourceDir))
            {
                string ext = Path.GetExtension(file).ToLower();
                if (ext is ".zip" or ".tmp" or ".log") continue;
                string name = Path.GetFileName(file).ToLower();
                if (name == "vram_status.json") continue;

                string rel = Path.GetRelativePath(rootDir, file);
                try { archive.CreateEntryFromFile(file, rel); }
                catch (Exception ex) { Debug.WriteLine($"[ZIP-skip] {rel}: {ex.Message}"); }
            }

            foreach (string dir in Directory.GetDirectories(sourceDir))
            {
                string d = Path.GetFileName(dir).ToLower();
                if (d is ".git" or ".gemini" or ".ipfs-woldvirtual"
                       or "obj" or "bin" or "peers" or "logs"
                       or "temp" or "tmp" or "wcvcoinmtb") continue;
                AddDirectoryToZip(archive, dir, rootDir);
            }
        }

        // ── Página de invitación HTML ─────────────────────────────────────────
        private string GetInvitePageHtml()
        {
            bool   hasIpfs      = IsOnIpfs && GatewayUrl != null;
            string downloadUrl  = hasIpfs ? GatewayUrl! : (ZipReady ? "/visor.zip" : "#");
            string statusMsg    = hasIpfs
                ? $"✅ Disponible en IPFS — descarga directa sin instalar nada."
                : (ZipReady
                    ? "ZIP listo en servidor local. Conectando a IPFS..."
                    : "Generando el paquete del visor, por favor espera...");
            string btnClass     = (hasIpfs || ZipReady) ? "" : "disabled";
            string cidBlock     = hasIpfs
                ? $"<div class=\"cid-row\"><span class=\"lbl\">CID IPFS</span>" +
                  $"<span class=\"cid\">{RealCid}</span></div>"
                : "";

            return $@"<!DOCTYPE html>
<html lang=""es"">
<head>
<meta charset=""UTF-8"">
<meta name=""viewport"" content=""width=device-width,initial-scale=1"">
<title>Invitación — Wold Virtual P2P 3D</title>
<link href=""https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap"" rel=""stylesheet"">
<style>
:root{{--bg:#060913;--card:rgba(17,22,37,.7);--cyan:#66FCF1;--teal:#45A29E;
      --green:#00ff8c;--text:#C5C6C7;--white:#FFF;}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:'Outfit',sans-serif;
     min-height:100vh;display:flex;align-items:center;justify-content:center}}
body::before{{content:'';position:fixed;inset:0;
     background-image:linear-gradient(rgba(102,252,241,.03)1px,transparent 1px),
                      linear-gradient(90deg,rgba(102,252,241,.03)1px,transparent 1px);
     background-size:30px 30px;pointer-events:none}}
.card{{width:90%;max-width:560px;background:var(--card);border:1px solid var(--teal);
      border-top:2px solid var(--cyan);border-radius:16px;padding:40px;
      backdrop-filter:blur(12px);
      box-shadow:0 8px 32px rgba(0,0,0,.37),0 0 20px rgba(102,252,241,.15);
      text-align:center}}
.icon{{font-size:52px;margin-bottom:12px;
       filter:drop-shadow(0 0 10px var(--cyan))}}
h1{{font-size:26px;font-weight:800;color:var(--white);letter-spacing:2px;
    text-transform:uppercase;text-shadow:0 0 12px rgba(102,252,241,.4)}}
.sub{{color:var(--cyan);font-size:12px;font-weight:600;letter-spacing:3px;
     text-transform:uppercase;margin:6px 0 28px}}
.info-box{{background:rgba(6,9,19,.8);border:1px dashed rgba(102,252,241,.3);
          border-radius:8px;padding:16px;margin-bottom:22px;text-align:left}}
.lbl{{font-size:10px;text-transform:uppercase;letter-spacing:2px;
     color:var(--teal);display:block;margin-bottom:3px}}
.val{{font-size:15px;font-weight:600;color:var(--green);
     text-shadow:0 0 8px rgba(0,255,140,.3);word-break:break-all}}
.cid-row{{margin-top:12px;padding-top:12px;
         border-top:1px solid rgba(102,252,241,.1)}}
.cid{{font-size:10px;font-family:monospace;color:var(--cyan);
     word-break:break-all;display:block;margin-top:3px}}
p.desc{{font-size:14px;line-height:1.7;margin-bottom:28px}}
a.btn{{display:block;background:transparent;color:var(--cyan);
      border:2px solid var(--cyan);padding:14px 24px;font-size:14px;
      font-weight:600;text-transform:uppercase;letter-spacing:2px;
      border-radius:8px;text-decoration:none;
      transition:all .25s ease;
      box-shadow:0 0 10px rgba(102,252,241,.1)}}
a.btn:hover:not(.disabled){{background:var(--cyan);color:var(--bg);
      box-shadow:0 0 24px rgba(102,252,241,.4);transform:translateY(-2px)}}
a.btn.disabled{{border-color:#334;color:#556;pointer-events:none;cursor:not-allowed}}
.status{{margin-top:14px;font-size:12px;color:var(--green)}}
.footer{{margin-top:30px;font-size:10px;color:rgba(197,198,199,.35);
        text-transform:uppercase;letter-spacing:1px}}
</style>
</head>
<body>
<div class=""card"">
  <div class=""icon"">🌐</div>
  <h1>Wold Virtual 3D</h1>
  <div class=""sub"">P2P Network — Invitación</div>

  <div class=""info-box"">
    <span class=""lbl"">Dirección del Nodo</span>
    <span class=""val"">{SimulatedUrl}</span>
    {cidBlock}
  </div>

  <p class=""desc"">
    Tu amigo te invita a unirte al metaverso 3D descentralizado.<br>
    Descarga el visor, descomprímelo y ejecútalo para crear tu avatar y conectarte a la red P2P.
  </p>

  <a href=""{downloadUrl}"" class=""btn {btnClass}"">
    ⬇ Descargar Visor (.ZIP)
  </a>
  <div class=""status"">{statusMsg}</div>
  <div class=""footer"">Powered by IPFS · WoldVirtual P2P Engine · C#</div>
</div>
</body>
</html>";
        }

        // ── Utilidades ────────────────────────────────────────────────────────
        private int FindAvailablePort(int start)
        {
            for (int port = start; port < start + 100; port++)
            {
                try
                {
                    using var c = new System.Net.Sockets.TcpClient();
                    var r = c.BeginConnect("127.0.0.1", port, null, null);
                    if (!r.AsyncWaitHandle.WaitOne(100)) return port;
                    c.EndConnect(r);
                }
                catch { return port; }
            }
            return start;
        }

        private void LogStatus(string msg) => OnStatusChanged?.Invoke(msg);
    }
}
