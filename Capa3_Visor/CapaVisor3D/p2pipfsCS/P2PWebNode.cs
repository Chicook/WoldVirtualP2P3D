using System;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;

namespace VisorSingularity
{
    /// <summary>
    /// Nodo P2P del Visor WoldVirtual.
    ///
    /// Flujo CORRECTO y SECUENCIAL (sin IPFS Engine local):
    ///   1. GenerateRepositoryZip()          → crea el ZIP del visor localmente
    ///   2. UploadFileToCatboxAsync(zip)      → sube el ZIP → catboxZipUrl permanente
    ///   3. BuildFinalInviteHtml(catboxZipUrl)→ genera HTML con la URL YA INCRUSTADA
    ///   4. UploadFileToCatboxAsync(html)     → sube el HTML → catboxHtmlUrl permanente
    ///   5. GatewayUrl = catboxHtmlUrl        → este es el enlace final a compartir
    ///
    /// El servidor HTTP local sirve el ZIP y el HTML como fallback LAN.
    /// Catbox.moe sirve los archivos con el Content-Type correcto desde su CDN global.
    /// </summary>
    public class P2PWebNode
    {
        // ── Propiedades públicas ──────────────────────────────────────────────
        public string NodeId       { get; private set; }
        public string SimulatedUrl { get; private set; }
        public int    Port         { get; private set; } = 8082;
        public string LocalUrl     { get; private set; }
        public string ZipPath      { get; private set; }

        // Estado ZIP
        public bool IsZipping { get; private set; } = false;
        public bool ZipReady  { get; private set; } = false;

        // Enlace público del ZIP (Catbox)
        public string? ZipPublicUrl { get; private set; }

        // Enlace público de la página HTML de invitación (Catbox)
        // GatewayUrl = catboxHtmlUrl — esto es lo que se copia y se comparte
        public string? GatewayUrl { get; private set; }
        public bool    IsOnIpfs   { get; private set; } = false;   // Reutilizado: "enlace público listo"

        // RealCid para compatibilidad con MainWindow.xaml.cs (vacío, no usamos IPFS Engine)
        public string? RealCid => null;

        // ── Campos privados ───────────────────────────────────────────────────
        private HttpListener             _listener;
        private CancellationTokenSource? _cts;
        private string                   _repoPath;

        public event Action<string>? OnStatusChanged;

        // ── Constructor ───────────────────────────────────────────────────────
        public P2PWebNode(string username, string repoPath)
        {
            _repoPath = repoPath;

            int seed    = Math.Abs((username + DateTime.Now.Ticks).GetHashCode()) % 90000 + 10000;
            NodeId       = $"ND{seed}";
            SimulatedUrl = $"www.{NodeId}.ipfs";

            Port     = FindAvailablePort(8082);
            LocalUrl = $"http://127.0.0.1:{Port}/";

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

            Task.Run(() => ListenLoop(_cts.Token));
            Task.Run(() => RunMainFlowAsync());

            LogStatus("Comprimiendo visor...");
        }

        // ── Parada ────────────────────────────────────────────────────────────
        public void Stop()
        {
            _cts?.Cancel();
            _cts?.Dispose();
            _cts = null;

            if (_listener?.IsListening == true)
                try { _listener.Stop(); _listener.Close(); } catch { }

            if (File.Exists(ZipPath))
                try { File.Delete(ZipPath); } catch { }

            LogStatus("Nodo P2P apagado.");
        }

        // ── Flujo principal SECUENCIAL: ZIP → Catbox(ZIP) → HTML → Catbox(HTML) ─
        private async Task RunMainFlowAsync()
        {
            // ── Paso 1: Generar ZIP ────────────────────────────────────────────
            LogStatus("Comprimiendo el visor (puede tardar 1-2 min)...");
            GenerateRepositoryZip();
            if (!ZipReady)
            {
                LogStatus("❌ Error al generar el ZIP. Nodo en modo local.");
                return;
            }
            double mb = GetFileSizeMB(ZipPath);
            LogStatus($"ZIP listo ({mb:F1} MB). Subiendo a servidor público...");

            // ── Paso 2: Subir ZIP a Catbox ─────────────────────────────────────
            string? catboxZipUrl = await UploadFileToCatboxAsync(ZipPath, "application/zip",
                                                                  $"WoldVirtualVisor_{NodeId}.zip");
            if (string.IsNullOrEmpty(catboxZipUrl))
            {
                // Fallback: enlace local
                ZipPublicUrl = $"{LocalUrl}visor.zip";
                LogStatus("⚠️ No se pudo subir el ZIP a Catbox. Usando enlace local.");
            }
            else
            {
                ZipPublicUrl = catboxZipUrl;
                LogStatus("ZIP en Catbox ✅. Generando página de invitación...");
            }

            // ── Paso 3: Construir HTML con la URL del ZIP ya incrustada ────────
            // Este HTML tiene el botón de descarga apuntando a catboxZipUrl (URL real y permanente)
            string html = BuildFinalInviteHtml(ZipPublicUrl!);

            // ── Paso 4: Subir el HTML a Catbox ─────────────────────────────────
            string htmlTempPath = Path.Combine(
                Path.GetTempPath(), "WoldVirtualP2P", $"invite_{NodeId}.html");
            await File.WriteAllTextAsync(htmlTempPath, html, Encoding.UTF8);

            string? catboxHtmlUrl = await UploadFileToCatboxAsync(
                htmlTempPath, "text/html", $"WoldVirtualInvite_{NodeId}.html");

            // Limpieza del HTML temporal
            try { File.Delete(htmlTempPath); } catch { }

            if (!string.IsNullOrEmpty(catboxHtmlUrl))
            {
                GatewayUrl = catboxHtmlUrl;
                IsOnIpfs   = true;   // reutilizamos el flag para indicar "enlace público listo"
                LogStatus($"✅ Enlace de invitación listo. ¡Cópialo y compártelo!");
            }
            else if (!string.IsNullOrEmpty(catboxZipUrl))
            {
                // Al menos tenemos el ZIP en Catbox — compartir enlace directo al ZIP
                GatewayUrl = catboxZipUrl;
                IsOnIpfs   = true;
                LogStatus($"✅ Enlace al ZIP listo (sin página HTML).");
            }
            else
            {
                // Solo enlace local
                GatewayUrl = LocalUrl;
                LogStatus($"⚠️ Solo enlace local disponible: {LocalUrl}");
            }
        }

        // ── Subida genérica a Catbox.moe ──────────────────────────────────────
        private async Task<string?> UploadFileToCatboxAsync(
            string filePath, string contentType, string fileName)
        {
            try
            {
                using var httpClient = new HttpClient();
                httpClient.Timeout = TimeSpan.FromMinutes(15);

                using var form = new MultipartFormDataContent();
                form.Add(new StringContent("fileupload"), "reqtype");

                using var fileStream    = File.OpenRead(filePath);
                var       streamContent = new StreamContent(fileStream);
                streamContent.Headers.ContentType =
                    new System.Net.Http.Headers.MediaTypeHeaderValue(contentType);
                form.Add(streamContent, "fileToUpload", fileName);

                var response = await httpClient.PostAsync(
                    "https://catbox.moe/user/api.php", form);

                if (response.IsSuccessStatusCode)
                {
                    string result = (await response.Content.ReadAsStringAsync()).Trim();
                    if (result.StartsWith("http://") || result.StartsWith("https://"))
                    {
                        Debug.WriteLine($"[Catbox] ✅ {fileName} → {result}");
                        return result;
                    }
                    Debug.WriteLine($"[Catbox] Respuesta inesperada: {result}");
                }
                else
                {
                    Debug.WriteLine($"[Catbox] HTTP {response.StatusCode}");
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Catbox] Error: {ex.Message}");
                LogStatus($"Error Catbox: {ex.Message}");
            }
            return null;
        }

        // ── Servidor HTTP local (fallback LAN) ────────────────────────────────
        private async Task ListenLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested && _listener.IsListening)
            {
                try
                {
                    var ctx      = await _listener.GetContextAsync();
                    var response = ctx.Response;
                    string path  = ctx.Request.Url?.AbsolutePath.ToLower() ?? "/";

                    if (path == "/visor.zip")
                    {
                        await ServeZip(response);
                    }
                    else
                    {
                        // Sirve el HTML con la URL actual (puede ser local o Catbox)
                        string url  = ZipPublicUrl ?? (ZipReady ? "/visor.zip" : "#");
                        byte[] buf  = Encoding.UTF8.GetBytes(BuildFinalInviteHtml(url));
                        response.StatusCode      = 200;
                        response.ContentType     = "text/html; charset=UTF-8";
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
            response.StatusCode  = 200;
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
            try
            {
                if (File.Exists(ZipPath)) File.Delete(ZipPath);
                using var zipStream = new FileStream(ZipPath, FileMode.Create);
                using var archive   = new ZipArchive(zipStream, ZipArchiveMode.Create);
                AddDirectoryToZip(archive, _repoPath, _repoPath);
                ZipReady = true;
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
                string ext  = Path.GetExtension(file).ToLower();
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

        // ── HTML de invitación con URL de descarga INCRUSTADA ─────────────────
        private string BuildFinalInviteHtml(string downloadUrl)
        {
            bool   hasLink  = !string.IsNullOrEmpty(downloadUrl) && downloadUrl != "#";
            string btnClass = hasLink ? "" : "disabled";
            string status   = hasLink
                ? "✅ Descarga directa disponible."
                : "Preparando enlace...";

            return $@"<!DOCTYPE html>
<html lang=""es"">
<head>
<meta charset=""UTF-8"">
<meta name=""viewport"" content=""width=device-width,initial-scale=1"">
<title>Invitación — Wold Virtual P2P 3D</title>
<link href=""https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap"" rel=""stylesheet"">
<style>
:root{{--bg:#060913;--card:rgba(17,22,37,.7);--cyan:#66FCF1;--teal:#45A29E;--green:#00ff8c;--text:#C5C6C7;--white:#FFF;}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:'Outfit',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}}
body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(102,252,241,.03)1px,transparent 1px),linear-gradient(90deg,rgba(102,252,241,.03)1px,transparent 1px);background-size:30px 30px;pointer-events:none}}
.card{{width:90%;max-width:560px;background:var(--card);border:1px solid var(--teal);border-top:2px solid var(--cyan);border-radius:16px;padding:40px;backdrop-filter:blur(12px);box-shadow:0 8px 32px rgba(0,0,0,.37),0 0 20px rgba(102,252,241,.15);text-align:center}}
.icon{{font-size:52px;margin-bottom:12px;filter:drop-shadow(0 0 10px var(--cyan))}}
h1{{font-size:26px;font-weight:800;color:var(--white);letter-spacing:2px;text-transform:uppercase;text-shadow:0 0 12px rgba(102,252,241,.4)}}
.sub{{color:var(--cyan);font-size:12px;font-weight:600;letter-spacing:3px;text-transform:uppercase;margin:6px 0 28px}}
.info-box{{background:rgba(6,9,19,.8);border:1px dashed rgba(102,252,241,.3);border-radius:8px;padding:16px;margin-bottom:22px;text-align:left}}
.lbl{{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--teal);display:block;margin-bottom:3px}}
.val{{font-size:15px;font-weight:600;color:var(--green);text-shadow:0 0 8px rgba(0,255,140,.3);word-break:break-all}}
p.desc{{font-size:14px;line-height:1.7;margin-bottom:28px}}
a.btn{{display:block;background:transparent;color:var(--cyan);border:2px solid var(--cyan);padding:14px 24px;font-size:14px;font-weight:600;text-transform:uppercase;letter-spacing:2px;border-radius:8px;text-decoration:none;transition:all .25s ease;box-shadow:0 0 10px rgba(102,252,241,.1)}}
a.btn:hover:not(.disabled){{background:var(--cyan);color:var(--bg);box-shadow:0 0 24px rgba(102,252,241,.4);transform:translateY(-2px)}}
a.btn.disabled{{border-color:#334;color:#556;pointer-events:none;cursor:not-allowed}}
.status{{margin-top:14px;font-size:12px;color:var(--green)}}
.footer{{margin-top:30px;font-size:10px;color:rgba(197,198,199,.35);text-transform:uppercase;letter-spacing:1px}}
</style>
</head>
<body>
<div class=""card"">
  <div class=""icon"">🌐</div>
  <h1>Wold Virtual 3D</h1>
  <div class=""sub"">P2P Network — Invitación</div>
  <div class=""info-box"">
    <span class=""lbl"">Nodo</span>
    <span class=""val"">{SimulatedUrl}</span>
  </div>
  <p class=""desc"">
    Tu amigo te invita al metaverso 3D descentralizado.<br>
    Descarga el visor, descomprímelo y ejecútalo para crear tu avatar.
  </p>
  <a href=""{downloadUrl}"" class=""btn {btnClass}"" download>
    ⬇ Descargar Visor (.ZIP)
  </a>
  <div class=""status"">{status}</div>
  <div class=""footer"">Powered by Catbox · WoldVirtual P2P Engine · C#</div>
</div>
</body>
</html>";
        }

        // ── Utilidades ────────────────────────────────────────────────────────
        private double GetFileSizeMB(string path)
        {
            try { return new FileInfo(path).Length / 1_048_576.0; } catch { return 0; }
        }

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
