using System;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;
using System.Collections.Generic;

namespace VisorSingularity
{
    /// <summary>
    /// Nodo P2P del Visor WoldVirtual.
    ///
    /// Flujo P2P (túmel SSH prioritario):
    ///   1. GenerateRepositoryZip()  → Comprime el visor completo a disco temporal (~330 MB)
    ///   2. Túmel SSH Reverso       → Expone el servidor local (puerto 8082) a internet via serveo.net/localhost.run
    ///                                 URL activa SOLO mientras el avatar esté conectado. Al apagar: URL desaparece.
    ///   3. IPFS en background       → Kubo anuncia el contenido en el DHT para seeding P2P adicional
    ///   4. Fallback CDN             → Pixeldrain/GoFile/Transfer.sh si SSH e IPFS fallan ambos
    /// </summary>
    public class P2PWebNode
    {
        // ── Propiedades públicas ──────────────────────────────────────────────
        public string NodeId       { get; private set; }
        public string SimulatedUrl { get; private set; }
        public int    Port         { get; private set; } = 8082;
        public string LocalUrl     { get; private set; }
        public string ZipPath      { get; private set; }

        public bool IsZipping { get; private set; } = false;
        public bool ZipReady  { get; private set; } = false;

        public string? ZipPublicUrl { get; private set; }   // URL del ZIP en IPFS o CDN
        public string? GatewayUrl   { get; private set; }   // URL final (Landing en IPFS / CDN)
        public bool    IsOnIpfs     { get; private set; } = false;  // Indica si está publicado en red pública/IPFS
        public string? RealCid      => _ipfsPublisher?.LastCid;   // CID para MainWindow

        /// <summary>URL del gateway local en puerto 8082 para acceder a cualquier CID IPFS.</summary>
        public string LocalIpfsGatewayUrl => $"http://127.0.0.1:{Port}/ipfs/";

        /// <summary>True si hay un túmel SSH reverso activo hacia internet.</summary>
        public bool IsTunnelActive => _tunnelProcess != null && !_tunnelProcess.HasExited;

        // ── Campos privados ───────────────────────────────────────────────────
        private HttpListener             _listener;
        private CancellationTokenSource? _cts;
        private readonly string          _repoPath;
        private static readonly HttpClient _http = new HttpClient();

        private IpfsManager?             _ipfsManager;
        private IpfsPublisher?           _ipfsPublisher;
        private Process?                 _tunnelProcess;   // Proceso SSH del túmel reverso activo
        private int                      _internalPort;
        private TcpListener?             _proxyListener;   // Proxy TCP local para reescribir Host header

        public event Action<string>? OnStatusChanged;

        // ── Constructor ───────────────────────────────────────────────────────
        public P2PWebNode(string username, string repoPath)
        {
            _repoPath = repoPath;

            int seed    = Math.Abs((username + DateTime.Now.Ticks).GetHashCode()) % 90000 + 10000;
            NodeId       = $"ND{seed}";
            SimulatedUrl = $"www.{NodeId}.woldvirtual";

            Port          = FindAvailablePort(8082);
            _internalPort = FindAvailablePort(Port + 1);
            LocalUrl      = $"http://127.0.0.1:{Port}/";

            string tempDir = Path.Combine(Path.GetTempPath(), "WoldVirtualP2P");
            Directory.CreateDirectory(tempDir);
            ZipPath = Path.Combine(tempDir, $"WoldVirtualVisor_{NodeId}.zip");

            _listener = new HttpListener();
            _listener.Prefixes.Add($"http://127.0.0.1:{_internalPort}/");
            _listener.Prefixes.Add($"http://localhost:{_internalPort}/");

            // TimeOut global generoso para archivos grandes
            _http.Timeout = TimeSpan.FromMinutes(20);
        }

        // ── Inicio ────────────────────────────────────────────────────────────
        public void Start()
        {
            _cts = new CancellationTokenSource();
            _listener.Start();
            Task.Run(() => ListenLoop(_cts.Token));

            // Iniciar proxy TCP para reescribir Host header (evita HTTP 400 por Host de Serveo)
            try
            {
                _proxyListener = new TcpListener(IPAddress.Loopback, Port);
                _proxyListener.Start();
                Task.Run(() => ProxyLoop(_cts.Token));
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Proxy-Start] Error: {ex.Message}");
                LogStatus($"⚠️ Error iniciando proxy local: {ex.Message}");
            }

            Task.Run(() => RunMainFlowAsync());
            LogStatus("📦 Comprimiendo visor...");
        }

        // ── Parada ────────────────────────────────────────────────────────────
        public void Stop()
        {
            _cts?.Cancel();
            _cts?.Dispose();
            _cts = null;

            // Detener proxy TCP
            if (_proxyListener != null)
            {
                try { _proxyListener.Stop(); } catch { }
                _proxyListener = null;
            }

            // Matar túmel SSH — cuando muere, la URL pública deja de funcionar (diseño intencional)
            if (_tunnelProcess != null)
            {
                try { _tunnelProcess.Kill(entireProcessTree: true); } catch { }
                try { _tunnelProcess.Dispose(); }                    catch { }
                _tunnelProcess = null;
            }

            if (_listener?.IsListening == true)
                try { _listener.Stop(); _listener.Close(); } catch { }

            if (_ipfsManager != null)
            {
                try { _ipfsManager.StopDaemon(); _ipfsManager.Dispose(); } catch { }
                _ipfsManager = null;
            }

            if (File.Exists(ZipPath))
                try { File.Delete(ZipPath); } catch { }

            LogStatus("⏹ Nodo P2P apagado.");
        }

        // ── Flujo principal: Túmel SSH (prioritario) → IPFS/CDN (background) ──────────────────────
        private async Task RunMainFlowAsync()
        {
            // Paso 1 — Generar ZIP
            GenerateRepositoryZip();
            if (!ZipReady)
            {
                LogStatus("❌ Error generando ZIP. Solo enlace local disponible.");
                GatewayUrl = LocalUrl;
                return;
            }

            double mb = GetFileSizeMB(ZipPath);
            LogStatus($"✅ ZIP listo ({mb:F1} MB). Estableciendo presencia en red...");

            // Paso 2 — Túmel SSH reverso (PC-a-PC, visible mientras conectado, desaparece al cerrar)
            string? tunnelUrl = await TryEstablishTunnelAsync(_cts?.Token ?? default);
            if (!string.IsNullOrEmpty(tunnelUrl))
            {
                ZipPublicUrl = $"{tunnelUrl}/visor.zip";
                GatewayUrl   = tunnelUrl;
                IsOnIpfs     = false;
                LogStatus("🌍 ¡Nodo visible! URL activa mientras estés conectado.");

                // IPFS en paralelo para seeding DHT adicional (no bloquea)
                _ = Task.Run(() => RunIpfsBackgroundAsync(_cts?.Token ?? default));
                return;
            }

            // Paso 3 — SSH no disponible: intentar IPFS + CDN
            LogStatus("⚠️ Túmel SSH no disponible. Intentando IPFS + CDN...");
            await RunIpfsBackgroundAsync(_cts?.Token ?? default);
        }

        // ── Túnel Público ────────────────────────────────────────────────────────────────────────
        /// <summary>
        /// Prioridad:
        ///   1. Cloudflare Quick Tunnel (cloudflared) → HTTPS, SIN página de advertencia ✅
        ///   2. Serveo.net HTTP (port 80)              → HTTPS con página de advertencia ⚠️
        ///   3. Serveo.net port 443                   → HTTPS con página de advertencia ⚠️
        ///   4. localhost.run                          → HTTPS con página de advertencia ⚠️
        /// </summary>
        private async Task<string?> TryEstablishTunnelAsync(CancellationToken token)
        {
            LogStatus("🔌 Estableciendo túnel público PC-a-PC...");

            // ── Opción 1: cloudflared (HTTPS sin advertencia de seguridad) ──────────
            string? cfExe = await FindOrDownloadCloudflaredAsync(token);
            if (cfExe != null)
            {
                LogStatus("   → Cloudflare Quick Tunnel (sin advertencia)...");
                string? cfUrl = await TryRunProcessTunnelAsync(
                    cfExe,
                    $"tunnel --url http://127.0.0.1:{Port} --no-autoupdate",
                    @"https://[\w\-]+\.trycloudflare\.com",
                    35000, token);
                if (!string.IsNullOrEmpty(cfUrl))
                {
                    LogStatus($"🌍 Túnel activo — Cloudflare: {cfUrl}");
                    return cfUrl;
                }
                LogStatus("   ↳ cloudflared sin respuesta. Probando SSH...");
            }


            // ── Opciones 2-4: SSH reverso (Serveo, localhost.run) ──────────────────
            string sshExe = @"C:\Windows\System32\OpenSSH\ssh.exe";
            if (!File.Exists(sshExe)) sshExe = "ssh";

            var candidates = new[]
            {
                new {
                    Name = "serveo.net",
                    Args = $"-o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ConnectTimeout=15 -R 80:127.0.0.1:{Port} serveo.net",
                    Pat  = @"https://(?!console\b)[\w\-]+\.serveo\.net|https://[\w\-]+\.serveousercontent\.com"
                },
                new {
                    Name = "serveo.net:443",
                    Args = $"-p 443 -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ConnectTimeout=15 -R 80:127.0.0.1:{Port} serveo.net",
                    Pat  = @"https://(?!console\b)[\w\-]+\.serveo\.net|https://[\w\-]+\.serveousercontent\.com"
                },
                new {
                    Name = "localhost.run",
                    Args = $"-o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ConnectTimeout=15 -R 80:127.0.0.1:{Port} nokey@localhost.run",
                    Pat  = @"https://[\w\-]+\.lhr\\.rocks"
                }
            };

            foreach (var c in candidates)
            {
                if (token.IsCancellationRequested) return null;
                LogStatus($"   → {c.Name}...");

                string? url = await TryRunProcessTunnelAsync(sshExe, c.Args, c.Pat, 23000, token);
                if (!string.IsNullOrEmpty(url))
                {
                    LogStatus($"🌍 Túnel activo — {c.Name}: {url}");
                    return url;
                }
            }

            LogStatus("⚠️ Túnel no disponible.");
            return null;
        }

        // ── Buscar (y descargar si no existe) cloudflared ────────────────────────
        private async Task<string?> FindOrDownloadCloudflaredAsync(CancellationToken token)
        {
            string localApp  = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string progFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
            string appBase   = AppDomain.CurrentDomain.BaseDirectory;

            // Ruta local donde lo descargamos si no está instalado
            string localCf = Path.Combine(appBase, "cloudflared.exe");

            string[] locations =
            {
                "cloudflared",       // En el PATH del sistema
                localCf,
                Path.Combine(localApp, "Programs", "cloudflared", "cloudflared.exe"),
                Path.Combine(progFiles, "Cloudflare", "cloudflared.exe"),
                @"C:\ProgramData\chocolatey\bin\cloudflared.exe",
                Path.Combine(localApp, "Microsoft", "WinGet", "Links", "cloudflared.exe"),
            };

            // ── 1. Buscar en el sistema ───────────────────────────────────────────
            foreach (var loc in locations)
            {
                try
                {
                    using var test = Process.Start(new ProcessStartInfo
                    {
                        FileName               = loc,
                        Arguments              = "--version",
                        UseShellExecute        = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError  = true,
                        CreateNoWindow         = true
                    });
                    if (test != null && test.WaitForExit(3000) && test.ExitCode == 0)
                    {
                        Debug.WriteLine($"[Cloudflared] Encontrado: {loc}");
                        return loc;
                    }
                }
                catch { }
            }

            // ── 2. No encontrado → descargar automáticamente ──────────────────────
            LogStatus("⬇️ Descargando cloudflared (túnel sin advertencia)...");
            try
            {
                const string cfUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe";
                using var dl = new HttpClient { Timeout = TimeSpan.FromMinutes(3) };
                dl.DefaultRequestHeaders.UserAgent.ParseAdd("WoldVirtualP2P/1.0");

                using var resp = await dl.GetAsync(cfUrl, HttpCompletionOption.ResponseHeadersRead, token);
                if (resp.IsSuccessStatusCode)
                {
                    await using var fs = File.Create(localCf);
                    await resp.Content.CopyToAsync(fs, token);
                    LogStatus("✅ cloudflared descargado correctamente.");
                    Debug.WriteLine($"[Cloudflared] Descargado en: {localCf}");
                    return localCf;
                }
                LogStatus($"⚠️ Descarga de cloudflared falló: HTTP {(int)resp.StatusCode}");
            }
            catch (Exception ex)
            {
                LogStatus($"⚠️ No se pudo descargar cloudflared: {ex.Message}");
                Debug.WriteLine($"[Cloudflared-DL] {ex}");
            }

            return null;
        }

        // ── Ejecutor genérico de proceso de túnel ────────────────────────────────
        /// <summary>
        /// Lanza un proceso de túnel (cloudflared, ssh, etc.), escanea stdout+stderr
        /// buscando una URL con <paramref name="urlPattern"/> y devuelve la URL al detectarla.
        /// Si no la encuentra dentro de <paramref name="timeoutMs"/>, mata el proceso y devuelve null.
        /// </summary>
        private async Task<string?> TryRunProcessTunnelAsync(
            string exe, string args, string urlPattern, int timeoutMs, CancellationToken token)
        {
            Process? proc  = null;
            string?  found = null;

            try
            {
                proc = Process.Start(new ProcessStartInfo
                {
                    FileName               = exe,
                    Arguments              = args,
                    UseShellExecute        = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError  = true,
                    CreateNoWindow         = true
                });
                if (proc == null) return null;

                using var scanCts = CancellationTokenSource.CreateLinkedTokenSource(token);
                scanCts.CancelAfter(timeoutMs);

                async Task Scan(StreamReader sr, string label)
                {
                    try
                    {
                        while (!scanCts.IsCancellationRequested && !proc.HasExited)
                        {
                            string? ln = await sr.ReadLineAsync();
                            if (ln == null) break;
                            Debug.WriteLine($"[{label}] {ln}");
                            var m = System.Text.RegularExpressions.Regex.Match(ln, urlPattern);
                            if (m.Success)
                            {
                                string matched = m.Value;
                                if (!matched.StartsWith("http://") && !matched.StartsWith("https://"))
                                    matched = "http://" + matched;
                                found = matched;
                                scanCts.Cancel();
                                return;
                            }
                        }
                    }
                    catch { }
                }

                await Task.WhenAny(
                    Scan(proc.StandardOutput, exe),
                    Scan(proc.StandardError,  exe),
                    Task.Delay(timeoutMs + 1000, scanCts.Token).ContinueWith(_ => { })
                );

                if (!string.IsNullOrEmpty(found) && !proc.HasExited)
                {
                    _tunnelProcess = proc;
                    return found;
                }

                try { proc.Kill(entireProcessTree: true); } catch { }
                proc.Dispose();
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[TryRunProcessTunnel] {exe}: {ex.Message}");
                try { proc?.Kill(entireProcessTree: true); proc?.Dispose(); } catch { }
            }
            return null;
        }


        // ── IPFS + CDN (ejecutado en background o como fallback si SSH falla) ────────────────────
        private async Task RunIpfsBackgroundAsync(CancellationToken token)
        {
            _ipfsManager   = new IpfsManager();
            _ipfsManager.OnStatusChanged += msg => LogStatus(msg);
            _ipfsPublisher = new IpfsPublisher(_ipfsManager);

            bool ipfsReady = false;
            try   { ipfsReady = await _ipfsManager.EnsureReadyAsync(token); }
            catch (Exception ex) { LogStatus($"⚠️ IPFS: {ex.Message}"); }

            if (ipfsReady && _ipfsPublisher != null)
            {
                LogStatus("🚀 [IPFS BG] Publicando ZIP en la red IPFS...");
                string? zipCid = await _ipfsPublisher.PublishAndPinAsync(ZipPath, token);

                if (!string.IsNullOrEmpty(zipCid))
                {
                    string tempDir = Path.Combine(Path.GetTempPath(), $"WVHtml_{NodeId}");
                    Directory.CreateDirectory(tempDir);
                    File.WriteAllText(Path.Combine(tempDir, "index.html"),
                        GetLandingHtml($"/ipfs/{zipCid}", isIpfsHosted: true, zipCid: zipCid),
                        Encoding.UTF8);

                    string? landingCid = await _ipfsPublisher.PublishDirectoryAsync(tempDir, token);
                    try { Directory.Delete(tempDir, true); } catch { }

                    if (!string.IsNullOrEmpty(landingCid))
                    {
                        // Solo actualizar GatewayUrl si el túmel no está activo
                        if (string.IsNullOrEmpty(GatewayUrl) || GatewayUrl == LocalUrl)
                        {
                            string bestGw = await SelectBestGatewayUrlAsync(landingCid);
                            int    idx    = bestGw.IndexOf("/ipfs/");
                            string pfx    = idx > 0 ? bestGw.Substring(0, idx + 6) : "https://ipfs.io/ipfs/";
                            ZipPublicUrl  = $"{pfx}{zipCid}";
                            GatewayUrl    = bestGw;
                            IsOnIpfs      = true;
                            LogStatus("✅ [IPFS] Enlace IPFS listo. Cópialo y compártelo.");
                        }
                        else
                        {
                            LogStatus($"📌 [IPFS BG] Seeding DHT activo — CID landing: {landingCid}");
                        }
                        PreloadCidsOnPublicGateways(landingCid, zipCid);
                        return;
                    }
                }
            }

            // CDN fallback (solo si no hay túnel ni IPFS)
            if (!string.IsNullOrEmpty(GatewayUrl) && GatewayUrl != LocalUrl) return;

            LogStatus("⚠️ IPFS no disponible. Intentando CDN...");
            string? cdnUrl = await TryUploadZipAsync();
            if (!string.IsNullOrEmpty(cdnUrl))
            {
                ZipPublicUrl = cdnUrl;
                GatewayUrl   = cdnUrl;
                IsOnIpfs     = true;
                LogStatus("✅ Enlace CDN listo. Cópialo y compártelo.");
            }
            else
            {
                GatewayUrl = LocalUrl;
                LogStatus($"⚠️ Solo enlace local activo: {LocalUrl}");
            }
        }

        // ── Selección dinámica de la mejor pasarela pública (evita bloqueos DNS de ISPs) ──
        private async Task<string> SelectBestGatewayUrlAsync(string landingCid)
        {
            string[] candidateGateways = {
                "https://4everland.io/ipfs/",
                "https://w3s.link/ipfs/",
                "https://ipfs.eth.aragon.network/ipfs/",
                "https://cf-ipfs.com/ipfs/",
                "https://storry.tv/ipfs/",
                "https://ipfs.io/ipfs/",
                "https://cloudflare-ipfs.com/ipfs/",
                "https://dweb.link/ipfs/"
            };

            LogStatus("🔍 Verificando pasarelas IPFS libres de bloqueo ISP...");

            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(6));
            using var httpClient = new HttpClient { Timeout = TimeSpan.FromSeconds(4) };
            httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");

            var testTasks = new List<Task<(string gw, bool reachable)>>();

            foreach (var gw in candidateGateways)
            {
                testTasks.Add(Task.Run(async () =>
                {
                    try
                    {
                        // Extraer el dominio raíz para hacer la petición rápida y evitar DHT lookup
                        string rootUrl = gw;
                        int ipfsIdx = gw.IndexOf("/ipfs/");
                        if (ipfsIdx > 0)
                        {
                            rootUrl = gw.Substring(0, ipfsIdx + 1);
                        }

                        using var req = new HttpRequestMessage(HttpMethod.Head, rootUrl);
                        using var resp = await httpClient.SendAsync(req, cts.Token);
                        return (gw, true);
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"[GatewayTest] {gw} bloqueado o inactivo: {ex.Message}");
                        return (gw, false);
                    }
                }));
            }

            var results = await Task.WhenAll(testTasks);

            foreach (var res in results)
            {
                if (res.reachable)
                {
                    LogStatus($"✨ Pasarela óptima detectada: {res.gw}");
                    return $"{res.gw}{landingCid}";
                }
            }

            // Si todas fallan o el usuario no tiene internet, usar el gateway local
            LogStatus("⚠️ No se detectó ninguna pasarela pública activa. Usando pasarela local Kubo.");
            return $"http://127.0.0.1:8080/ipfs/{landingCid}";
        }

        // ── Precarga Activa de Pasarelas IPFS ──────────────────────────────────
        private void PreloadCidsOnPublicGateways(string landingCid, string zipCid)
        {
            string[] gateways = {
                "https://ipfs.io/ipfs/",
                "https://dweb.link/ipfs/",
                "https://gateway.pinata.cloud/ipfs/",
                "https://w3s.link/ipfs/"
            };

            Task.Run(async () =>
            {
                using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(25) };
                client.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");

                LogStatus("📡 Enrutando contenido con pasarelas IPFS públicas...");
                
                var tasks = new List<Task>();

                foreach (var gw in gateways)
                {
                    // 1. Forzar precarga de la Landing Page (descarga el pequeño archivo index.html)
                    tasks.Add(Task.Run(async () =>
                    {
                        try
                        {
                            var resp = await client.GetAsync($"{gw}{landingCid}");
                            Debug.WriteLine($"[Preload-Landing] {gw} → {(int)resp.StatusCode}");
                        }
                        catch (Exception ex)
                        {
                            Debug.WriteLine($"[Preload-Landing-Error] {gw} → {ex.Message}");
                        }
                    }));

                    // 2. Forzar búsqueda de proveedor del archivo ZIP (HEAD request)
                    // Esto obliga a la pasarela a consultar el DHT e indexar el archivo grande sin descargar los 300MB completos
                    tasks.Add(Task.Run(async () =>
                    {
                        try
                        {
                            using var req = new HttpRequestMessage(HttpMethod.Head, $"{gw}{zipCid}");
                            var resp = await client.SendAsync(req);
                            Debug.WriteLine($"[Preload-Zip] {gw} → {(int)resp.StatusCode}");
                        }
                        catch (Exception ex)
                        {
                            Debug.WriteLine($"[Preload-Zip-Error] {gw} → {ex.Message}");
                        }
                    }));
                }

                await Task.WhenAll(tasks);
                LogStatus("✅ Pasarelas IPFS enlazadas con éxito.");
            });
        }

        // ── Cadena de servicios de upload (Fallback) ──────────────────────────
        private async Task<string?> TryUploadZipAsync()
        {
            string fn = $"WoldVirtualVisor_{NodeId}.zip";

            // ── 1. Pixeldrain (enlace directo, sin límite de tamaño, muy fiable) ──
            LogStatus("📤 Subiendo a Pixeldrain...");
            string? url = await UploadToPixeldrainAsync(ZipPath, fn);
            if (!string.IsNullOrEmpty(url)) return url;

            // ── 2. GoFile.io (sin límite, gran fiabilidad, retorna página de descarga) ─
            LogStatus("📤 Pixeldrain falló. Intentando GoFile.io...");
            url = await UploadToGoFileAsync(ZipPath, fn);
            if (!string.IsNullOrEmpty(url)) return url;

            // ── 3. Transfer.sh (14 días, hasta 10 GB, enlace directo) ─────────
            LogStatus("📤 GoFile falló. Intentando Transfer.sh...");
            url = await UploadToTransferShAsync(ZipPath, fn);
            if (!string.IsNullOrEmpty(url)) return url;

            // ── 4. 0x0.st (anónimo, hasta 512 MB) ────────────────────────────
            LogStatus("📤 Transfer.sh falló. Intentando 0x0.st...");
            url = await UploadTo0x0Async(ZipPath, fn);
            if (!string.IsNullOrEmpty(url)) return url;

            return null;
        }

        // ── pixeldrain.com ────────────────────────────────────────────────────
        private async Task<string?> UploadToPixeldrainAsync(string filePath, string fileName)
        {
            try
            {
                using var req  = new HttpRequestMessage(HttpMethod.Post, "https://pixeldrain.com/api/file");
                using var form = new MultipartFormDataContent();
                form.Add(new StringContent(fileName), "name");

                using var fs      = File.OpenRead(filePath);
                var       content = new StreamContent(fs);
                content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/zip");
                form.Add(content, "file", fileName);
                req.Content = form;

                var resp = await _http.SendAsync(req);
                string body = await resp.Content.ReadAsStringAsync();
                Debug.WriteLine($"[Pixeldrain] HTTP {(int)resp.StatusCode} → {body}");

                if (resp.IsSuccessStatusCode)
                {
                    using var doc = JsonDocument.Parse(body);
                    if (doc.RootElement.TryGetProperty("id", out var idEl))
                    {
                        string id = idEl.GetString() ?? "";
                        if (!string.IsNullOrEmpty(id))
                            return $"https://pixeldrain.com/api/file/{id}?download";
                    }
                }
            }
            catch (Exception ex) { Debug.WriteLine($"[Pixeldrain] Error: {ex.Message}"); }
            return null;
        }

        // ── gofile.io ─────────────────────────────────────────────────────────
        private async Task<string?> UploadToGoFileAsync(string filePath, string fileName)
        {
            try
            {
                string server = "store1";
                try
                {
                    var srvResp = await _http.GetStringAsync("https://api.gofile.io/servers");
                    using var srvDoc = JsonDocument.Parse(srvResp);
                    var data = srvDoc.RootElement.GetProperty("data");
                    if (data.TryGetProperty("servers", out var servers) && servers.GetArrayLength() > 0)
                    {
                        server = servers[0].GetProperty("name").GetString() ?? server;
                    }
                }
                catch { /* usar server por defecto */ }

                Debug.WriteLine($"[GoFile] Usando servidor: {server}");

                using var form = new MultipartFormDataContent();
                using var fs   = File.OpenRead(filePath);
                var content    = new StreamContent(fs);
                content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/zip");
                form.Add(content, "file", fileName);

                var resp = await _http.PostAsync($"https://{server}.gofile.io/contents/uploadfile", form);
                string body = await resp.Content.ReadAsStringAsync();
                Debug.WriteLine($"[GoFile] HTTP {(int)resp.StatusCode} → {body[..Math.Min(200,body.Length)]}");

                if (resp.IsSuccessStatusCode)
                {
                    using var doc = JsonDocument.Parse(body);
                    if (doc.RootElement.TryGetProperty("status", out var st) && st.GetString() == "ok")
                    {
                        var d = doc.RootElement.GetProperty("data");
                        if (d.TryGetProperty("downloadPage", out var dp))
                        {
                            string page = dp.GetString() ?? "";
                            if (!string.IsNullOrEmpty(page)) return page;
                        }
                    }
                }
            }
            catch (Exception ex) { Debug.WriteLine($"[GoFile] Error: {ex.Message}"); }
            return null;
        }

        // ── transfer.sh ───────────────────────────────────────────────────────
        private async Task<string?> UploadToTransferShAsync(string filePath, string fileName)
        {
            try
            {
                using var req  = new HttpRequestMessage(HttpMethod.Put, $"https://transfer.sh/{Uri.EscapeDataString(fileName)}");
                req.Headers.Add("Max-Downloads", "500");
                req.Headers.Add("Max-Days", "14");

                using var fs = File.OpenRead(filePath);
                req.Content  = new StreamContent(fs);
                req.Content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/zip");

                var resp = await _http.SendAsync(req);
                string result = (await resp.Content.ReadAsStringAsync()).Trim();
                Debug.WriteLine($"[Transfer.sh] HTTP {(int)resp.StatusCode} → {result}");

                if (resp.IsSuccessStatusCode && (result.StartsWith("https://") || result.StartsWith("http://")))
                    return result;
            }
            catch (Exception ex) { Debug.WriteLine($"[Transfer.sh] Error: {ex.Message}"); }
            return null;
        }

        // ── 0x0.st ────────────────────────────────────────────────────────────
        private async Task<string?> UploadTo0x0Async(string filePath, string fileName)
        {
            try
            {
                using var form = new MultipartFormDataContent();
                using var fs   = File.OpenRead(filePath);
                var content    = new StreamContent(fs);
                content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/zip");
                form.Add(content, "file", fileName);

                using var req = new HttpRequestMessage(HttpMethod.Post, "https://0x0.st");
                req.Headers.UserAgent.ParseAdd("WoldVirtualP2P/1.0");
                req.Content = form;

                var resp = await _http.SendAsync(req);
                string result = (await resp.Content.ReadAsStringAsync()).Trim();
                Debug.WriteLine($"[0x0.st] HTTP {(int)resp.StatusCode} → {result}");

                if (resp.IsSuccessStatusCode && (result.StartsWith("https://") || result.StartsWith("http://")))
                    return result;
            }
            catch (Exception ex) { Debug.WriteLine($"[0x0.st] Error: {ex.Message}"); }
            return null;
        }

        // ── Servidor HTTP local: landing + ZIP + IPFS gateway proxy ───────────
        private async Task ListenLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested && _listener.IsListening)
            {
                try
                {
                    var ctx     = await _listener.GetContextAsync();
                    // ⚠ Preservar la ruta original (no .ToLower()) porque los CIDs son case-sensitive
                    string path = ctx.Request.Url?.AbsolutePath ?? "/";
                    string pLow = path.ToLowerInvariant();

                    if      (pLow == "/visor.zip")         await ServeZipAsync(ctx.Response);
                    else if (pLow == "/status")             await ServeStatusAsync(ctx.Response);
                    else if (pLow.StartsWith("/ipfs/") ||
                             pLow.StartsWith("/ipns/"))     await ServeIpfsProxyAsync(ctx.Request, ctx.Response);
                    else                                    await ServeLandingAsync(ctx.Response);

                    try { ctx.Response.OutputStream.Close(); } catch { }
                }
                catch (ObjectDisposedException) { break; }
                catch (Exception ex) { Debug.WriteLine($"[HTTP] {ex.Message}"); }
            }
        }

        // ── Gateway IPFS local: proxy transparente hacia Kubo:8080 ───────────────────────────
        /// <summary>
        /// Atiende rutas /ipfs/{cid} y /ipns/{name} redirigiendo la petición
        /// al gateway local de Kubo (puerto 8080). Así http://127.0.0.1:8082/ipfs/{hash}
        /// funciona como un gateway IPFS completo mientras el nodo esté activo.
        /// </summary>
        private async Task ServeIpfsProxyAsync(HttpListenerRequest req, HttpListenerResponse r)
        {
            // Construir URL destino en Kubo conservando la ruta EXACTA (los CIDs son case-sensitive)
            string originalPath = req.Url?.AbsolutePath ?? "/";
            string query        = req.Url?.Query ?? "";
            string kuboUrl      = $"{IpfsManager.GatewayUrl}{originalPath}{query}";

            Debug.WriteLine($"[IPFS-Proxy] {req.Url?.AbsolutePath} → {kuboUrl}");

            try
            {
                using var proxyReq  = new HttpRequestMessage(HttpMethod.Get, kuboUrl);
                // Forzar streaming para no cargar 330 MB en RAM
                using var proxyResp = await _http.SendAsync(
                    proxyReq, HttpCompletionOption.ResponseHeadersRead);

                r.StatusCode = (int)proxyResp.StatusCode;

                // Propagar Content-Type
                string ct = proxyResp.Content.Headers.ContentType?.ToString()
                            ?? "application/octet-stream";
                r.ContentType = ct;

                // Propagar Content-Disposition si viene del gateway (activa descarga en el navegador)
                if (proxyResp.Content.Headers.ContentDisposition != null)
                    r.AddHeader("Content-Disposition",
                        proxyResp.Content.Headers.ContentDisposition.ToString());

                // CORS abierto para que otros nodos/scripts puedan acceder
                r.AddHeader("Access-Control-Allow-Origin", "*");

                // Propagar tamaño si se conoce (evita chunked encoding innecesario)
                if (proxyResp.Content.Headers.ContentLength.HasValue)
                    r.ContentLength64 = proxyResp.Content.Headers.ContentLength.Value;

                await using var upstreamStream = await proxyResp.Content.ReadAsStreamAsync();
                await upstreamStream.CopyToAsync(r.OutputStream);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[IPFS-Proxy] Error: {ex.Message}");
                byte[] err = Encoding.UTF8.GetBytes(
                    $"Error al obtener contenido IPFS (Kubo puede estar iniciando): {ex.Message}");
                r.StatusCode  = 502;
                r.ContentType = "text/plain; charset=UTF-8";
                r.ContentLength64 = err.Length;
                await r.OutputStream.WriteAsync(err, 0, err.Length);
            }
        }

        private async Task ServeZipAsync(HttpListenerResponse r)
        {
            if (!ZipReady || !File.Exists(ZipPath))
            {
                byte[] msg = Encoding.UTF8.GetBytes("ZIP generándose, espera unos segundos.");
                r.StatusCode = 503; r.ContentType = "text/plain; charset=UTF-8";
                r.ContentLength64 = msg.Length;
                await r.OutputStream.WriteAsync(msg, 0, msg.Length);
                return;
            }
            r.StatusCode  = 200;
            r.ContentType = "application/zip";
            r.AddHeader("Content-Disposition", $"attachment; filename=\"WoldVirtual_Visor_{NodeId}.zip\"");
            await using var fs = File.OpenRead(ZipPath);
            r.ContentLength64 = fs.Length;
            await fs.CopyToAsync(r.OutputStream);
        }

        private async Task ServeStatusAsync(HttpListenerResponse r)
        {
            string json = $"{{\"zipReady\":{ZipReady.ToString().ToLower()}," +
                          $"\"isOnIpfs\":{IsOnIpfs.ToString().ToLower()}," +
                          $"\"publicUrl\":\"{ZipPublicUrl ?? ""}\"," +
                          $"\"gatewayUrl\":\"{GatewayUrl ?? ""}\"," +
                          $"\"localUrl\":\"{LocalUrl}\"}}";
            byte[] buf = Encoding.UTF8.GetBytes(json);
            r.StatusCode = 200; r.ContentType = "application/json; charset=UTF-8";
            r.ContentLength64 = buf.Length;
            await r.OutputStream.WriteAsync(buf, 0, buf.Length);
        }

        private async Task ServeLandingAsync(HttpListenerResponse r)
        {
            // Si el ZIP está listo localmente (o via túmel) usamos ruta relativa.
            // Así funciona tanto en localhost:8082 como a través del túmel (que proxea al mismo servidor).
            string dl;
            bool   isIpfs  = false;
            string? zipCid = null;

            if (ZipReady)
            {
                dl = "/visor.zip";   // relativo — siempre correcto sea cual sea el host
            }
            else if (!string.IsNullOrEmpty(ZipPublicUrl))
            {
                dl     = ZipPublicUrl;
                isIpfs = IsOnIpfs && ZipPublicUrl.Contains("/ipfs/");
                if (isIpfs)
                {
                    int ls = ZipPublicUrl.LastIndexOf('/');
                    if (ls >= 0) zipCid = ZipPublicUrl.Substring(ls + 1);
                }
            }
            else
            {
                dl = "#";  // ZIP aún no listo
            }

            byte[] buf = Encoding.UTF8.GetBytes(GetLandingHtml(dl, isIpfs, zipCid));
            r.StatusCode = 200; r.ContentType = "text/html; charset=UTF-8";
            r.ContentLength64 = buf.Length;
            await r.OutputStream.WriteAsync(buf, 0, buf.Length);
        }

        // ── Generación del ZIP ────────────────────────────────────────────────
        private void GenerateRepositoryZip()
        {
            if (IsZipping) return;
            IsZipping = true; ZipReady = false;
            try
            {
                if (File.Exists(ZipPath)) File.Delete(ZipPath);
                using var zip     = new FileStream(ZipPath, FileMode.Create);
                using var archive = new ZipArchive(zip, ZipArchiveMode.Create);
                AddDirectoryToZip(archive, _repoPath, _repoPath);
                
                // Verificar archivos esenciales incluidos
                VerifyEssentialFilesIncluded(archive);
                
                ZipReady = true;
            }
            catch (Exception ex)
            {
                LogStatus($"Error al comprimir: {ex.Message}");
                Debug.WriteLine($"[ZIP] {ex}");
            }
            finally { IsZipping = false; }
        }
        
        private void VerifyEssentialFilesIncluded(ZipArchive archive)
        {
            // Lista de archivos esenciales que DEBEN estar en el ZIP
            var essentialFiles = new List<string>
            {
                // Proyecto Godot
                "WoldVirtual/project.godot",
                "WoldVirtual/EscenaPrincipal.tscn",
                "WoldVirtual/woldvirtual/scene/MTC/N3DWoldVirtualMT.tscn",
                
                // Scripts Godot críticos
                "WoldVirtual/woldvirtual/gdscrip/WorldManager.gd",
                "WoldVirtual/woldvirtual/gdscrip/NetworkLayer.gd",
                "WoldVirtual/woldvirtual/gdscrip/ChunkManager.gd",
                "WoldVirtual/woldvirtual/scene/MTC/RegistroAV.gd",
                
                // Ejecutable Godot
                "WoldVirtual/servidorinterno/Godot_v4.6.2-stable_mono_win64.exe",
                
                // Proyecto WPF
                "Capa3_Visor/CapaVisor3D/VisorSingularity.csproj",
                "Capa3_Visor/CapaVisor3D/MainWindow.xaml",
                "Capa3_Visor/CapaVisor3D/MainWindow.xaml.cs",
                "Capa3_Visor/CapaVisor3D/GodotHwndHost.cs",
                
                // Estado Global C#
                "WoldVirtual/Estado_Global/IslandStateManager.cs",
                "WoldVirtual/Estado_Global/SessionManager.cs",
                "WoldVirtual/Estado_Global/GlobalConfig.cs",
                
                // Web interface
                "Capa3_Visor/CapaVisor3D/www/metamask.html",
                
                // Scripts de automatización
                "build-all.ps1",
                "check-dependencies.ps1",
                "check-dependencies-simple.ps1"
            };
            
            var missingFiles = new List<string>();
            foreach (var file in essentialFiles)
            {
                var fullPath = Path.Combine(_repoPath, file);
                if (File.Exists(fullPath))
                {
                    // Verificar si el archivo está en el ZIP
                    var entry = archive.GetEntry(file);
                    if (entry == null)
                    {
                        missingFiles.Add(file);
                        Debug.WriteLine($"[ZIP-WARNING] Archivo esencial no incluido: {file}");
                    }
                    else
                    {
                        Debug.WriteLine($"[ZIP-OK] Archivo esencial incluido: {file}");
                    }
                }
                else
                {
                    Debug.WriteLine($"[ZIP-INFO] Archivo no encontrado (puede ser opcional): {file}");
                }
            }
            
            if (missingFiles.Count > 0)
            {
                Debug.WriteLine($"[ZIP-ERROR] {missingFiles.Count} archivos esenciales faltan en el ZIP:");
                foreach (var file in missingFiles)
                {
                    Debug.WriteLine($"[ZIP-ERROR]   - {file}");
                }
                LogStatus($"ADVERTENCIA: {missingFiles.Count} archivos esenciales no se incluyeron en el ZIP");
            }
            else
            {
                Debug.WriteLine($"[ZIP-SUCCESS] Todos los archivos esenciales incluidos en el ZIP");
            }
        }

        private void AddDirectoryToZip(ZipArchive archive, string sourceDir, string rootDir)
        {
            foreach (string file in Directory.GetFiles(sourceDir))
            {
                string ext  = Path.GetExtension(file).ToLower();
                if (ext is ".zip" or ".tmp" or ".log") continue;
                if (Path.GetFileName(file).ToLower() is "vram_status.json") continue;

                string rel = Path.GetRelativePath(rootDir, file);
                try 
                { 
                    archive.CreateEntryFromFile(file, rel);
                    Debug.WriteLine($"[ZIP-add] {rel}");
                }
                catch (Exception ex) { Debug.WriteLine($"[ZIP-skip] {rel}: {ex.Message}"); }
            }
            foreach (string dir in Directory.GetDirectories(sourceDir))
            {
                string d = Path.GetFileName(dir).ToLower();
                // Excluir solo lo estrictamente necesario para reducir tamaño
                // IMPORTANTE: NO excluir ".godot" - es necesario para que el proyecto funcione
                if (d is ".git" or ".gemini" or ".ipfs-woldvirtual"
                       or "peers" or "logs" or "temp" or "tmp" or "wcvcoinmtb") continue;
                AddDirectoryToZip(archive, dir, rootDir);
            }
        }

        // ── Landing page HTML ─────────────────────────────────────────────────
        private string GetLandingHtml(string downloadUrl, bool isIpfsHosted = false, string? zipCid = null)
        {
            bool   hasLink     = !string.IsNullOrEmpty(downloadUrl) && downloadUrl != "#";
            // Es "público" si la URL es absoluta Y externa, O si es relativa pero hay túmel activo
            bool   isPublic    = hasLink && (
                                    (downloadUrl.StartsWith("https://") || downloadUrl.StartsWith("http://")) &&
                                    !downloadUrl.StartsWith("http://127")
                                 ) || (downloadUrl.StartsWith("/") && IsTunnelActive);

            string btnClass    = hasLink ? "" : "disabled";
            string statusColor = isPublic ? "#00ff8c" : "#FBB824";
            string statusMsg   = isPublic
                ? (IsTunnelActive && downloadUrl.StartsWith("/")
                    ? "✅ Nodo activo. Descarga directa desde tu PC."
                    : isIpfsHosted ? "✅ Descarga descentralizada IPFS disponible." : "✅ Descarga directa disponible.")
                : (ZipReady ? "⚠️ Solo red local. Subiendo a servidor..." : "⏳ Generando ZIP...");

            string service = isPublic
                ? (IsTunnelActive && downloadUrl.StartsWith("/") ? "Túmel SSH Directo (PC-a-PC)"
                   : isIpfsHosted ? "Red IPFS (P2P)"
                   : downloadUrl.Contains("pixeldrain") ? "Pixeldrain"
                   : downloadUrl.Contains("gofile")   ? "GoFile.io"
                   : downloadUrl.Contains("transfer")  ? "Transfer.sh"
                   : downloadUrl.Contains("0x0")       ? "0x0.st"
                   : "CDN")
                : "servidor local";

            string extraIpfsBox = "";
            if (isIpfsHosted && !string.IsNullOrEmpty(zipCid))
            {
                extraIpfsBox = $@"
  <div class=""info-box"" style=""margin-top: 14px; border-color: rgba(0,255,140,0.3);"">
    <span class=""lbl"" style=""color: #00ff8c;"">CID del Visor (IPFS)</span>
    <span class=""val"" style=""color: #fff; font-family: monospace; font-size: 11px;"">{zipCid}</span>
  </div>";
            }

            return $@"<!DOCTYPE html>
<html lang=""es"">
<head>
<meta charset=""UTF-8"">
<meta name=""viewport"" content=""width=device-width,initial-scale=1"">
<title>Invitación — Wold Virtual P2P 3D</title>
<link href=""https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap"" rel=""stylesheet"">
<style>
:root{{--bg:#060913;--card:rgba(17,22,37,.8);--cyan:#66FCF1;--teal:#45A29E;--green:#00ff8c;--text:#C5C6C7;--white:#FFF;}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:'Outfit',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}}
body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(102,252,241,.03)1px,transparent 1px),linear-gradient(90deg,rgba(102,252,241,.03)1px,transparent 1px);background-size:30px 30px;pointer-events:none}}
.card{{width:90%;max-width:560px;background:var(--card);border:1px solid var(--teal);border-top:3px solid var(--cyan);border-radius:18px;padding:44px;backdrop-filter:blur(14px);box-shadow:0 8px 40px rgba(0,0,0,.4),0 0 24px rgba(102,252,241,.12);text-align:center}}
.icon{{font-size:54px;margin-bottom:12px;filter:drop-shadow(0 0 12px var(--cyan))}}
h1{{font-size:28px;font-weight:800;color:var(--white);letter-spacing:2px;text-transform:uppercase;text-shadow:0 0 14px rgba(102,252,241,.4)}}
.sub{{color:var(--cyan);font-size:12px;font-weight:600;letter-spacing:3px;text-transform:uppercase;margin:6px 0 28px}}
.info-box{{background:rgba(6,9,19,.85);border:1px dashed rgba(102,252,241,.3);border-radius:10px;padding:16px;margin-bottom:22px;text-align:left}}
.lbl{{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--teal);display:block;margin-bottom:4px}}
.val{{font-size:14px;font-weight:600;color:var(--green);word-break:break-all}}
p.desc{{font-size:14px;line-height:1.7;margin-bottom:28px}}
a.btn{{display:block;background:transparent;color:var(--cyan);border:2px solid var(--cyan);padding:15px 24px;font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:2px;border-radius:10px;text-decoration:none;transition:all .25s ease;box-shadow:0 0 10px rgba(102,252,241,.08)}}
a.btn:hover:not(.disabled){{background:var(--cyan);color:var(--bg);box-shadow:0 0 28px rgba(102,252,241,.45);transform:translateY(-2px)}}
a.btn.disabled{{border-color:#334;color:#556;pointer-events:none;cursor:not-allowed}}
.status{{margin-top:14px;font-size:12px;color:{statusColor}}}
.footer{{margin-top:32px;font-size:10px;color:rgba(197,198,199,.3);text-transform:uppercase;letter-spacing:1px}}
</style>
</head>
<body>
<div class=""card"">
  <div class=""icon"">🌐</div>
  <h1>Wold Virtual 3D</h1>
  <div class=""sub"">P2P Network — Nodo Activo</div>
  <div class=""info-box"">
    <span class=""lbl"">ID del Nodo</span>
    <span class=""val"">{NodeId}</span>
  </div>
  <p class=""desc"">
    Has sido invitado al metaverso 3D descentralizado.<br>
    Descarga el visor, descomprímelo y ejecútalo para unirte.
  </p>
  <a href=""{downloadUrl}"" class=""btn {btnClass}"" download>
    ⬇ Descargar Visor (.ZIP)
  </a>
  <div class=""status"">{statusMsg}</div>
  {extraIpfsBox}
  <div class=""footer"">Servido vía {service} · WoldVirtual P2P · C#</div>
</div>
{(isPublic ? "" : "<script>setTimeout(()=>location.reload(),8000);</script>")}
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

        // ── Proxy TCP Local (Reescritura de Cabecera Host) ───────────────────
        private async Task ProxyLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    TcpClient client = await _proxyListener!.AcceptTcpClientAsync(token);
                    _ = Task.Run(() => HandleProxyClientAsync(client, token));
                }
                catch (ObjectDisposedException) { break; }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[Proxy] Error de aceptación: {ex.Message}");
                }
            }
        }

        private async Task HandleProxyClientAsync(TcpClient client, CancellationToken token)
        {
            using (client)
            {
                client.NoDelay = true;
                using TcpClient target = new TcpClient();
                try
                {
                    await target.ConnectAsync("127.0.0.1", _internalPort, token);
                    target.NoDelay = true;

                    using NetworkStream clientStream = client.GetStream();
                    using NetworkStream targetStream = target.GetStream();

                    byte[] buffer = new byte[8192];
                    int bytesRead = 0;
                    using MemoryStream ms = new MemoryStream();

                    // Leer cabeceras HTTP (máximo 16 KB)
                    while (true)
                    {
                        int read = await clientStream.ReadAsync(buffer, 0, buffer.Length, token);
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
                            // Convertir cabeceras a string para manipulación segura
                            string headersStr = Encoding.UTF8.GetString(requestBytes, 0, headerEndIdx);
                            
                            // Reemplazar la cabecera Host por la del servidor local interno
                            var hostRegex = new System.Text.RegularExpressions.Regex(@"\r\nHost:\s*[^\r\n]+", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
                            if (hostRegex.IsMatch(headersStr))
                            {
                                headersStr = hostRegex.Replace(headersStr, $"\r\nHost: localhost:{_internalPort}");
                            }
                            else
                            {
                                headersStr += $"\r\nHost: localhost:{_internalPort}";
                            }

                            byte[] headerBytes = Encoding.UTF8.GetBytes(headersStr);
                            await targetStream.WriteAsync(headerBytes, 0, headerBytes.Length, token);
                            await targetStream.WriteAsync(separator, 0, separator.Length, token);

                            // Enviar bytes del cuerpo leídos de forma anticipada
                            int bodyOffset = headerEndIdx + separator.Length;
                            int bodyLength = requestBytes.Length - bodyOffset;
                            if (bodyLength > 0)
                            {
                                await targetStream.WriteAsync(requestBytes, bodyOffset, bodyLength, token);
                            }
                        }
                        else
                        {
                            await targetStream.WriteAsync(requestBytes, 0, requestBytes.Length, token);
                        }
                    }

                    // Copiar bidireccionalmente el tráfico de red remanente
                    var clientToTarget = clientStream.CopyToAsync(targetStream, token);
                    var targetToClient = targetStream.CopyToAsync(clientStream, token);

                    await Task.WhenAll(clientToTarget, targetToClient);
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[Proxy-Session] Error de comunicación: {ex.Message}");
                }
            }
        }

        private int FindBytes(byte[] src, byte[] find)
        {
            for (int i = 0; i < src.Length - find.Length + 1; i++)
            {
                bool match = true;
                for (int j = 0; j < find.Length; j++)
                {
                    if (src[i + j] != find[j])
                    {
                        match = false;
                        break;
                    }
                }
                if (match) return i;
            }
            return -1;
        }

        private void LogStatus(string msg) => OnStatusChanged?.Invoke(msg);
    }
}
