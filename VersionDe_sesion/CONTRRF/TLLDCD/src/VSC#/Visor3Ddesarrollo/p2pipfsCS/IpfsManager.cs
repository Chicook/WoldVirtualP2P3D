using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Services.P2PIPFS
{
    /// <summary>
    /// Gestiona el ciclo de vida del daemon Kubo (go-ipfs):
    /// descarga autom├ítica, inicializaci├│n del repo, arranque del daemon y parada limpia.
    /// El daemon expone la API IPFS en http://127.0.0.1:5001 y el gateway en http://127.0.0.1:8080.
    /// </summary>
    public class IpfsManager : IDisposable
    {
        // ÔöÇÔöÇÔöÇ Versi├│n y URL de descarga ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        private const string KuboVersion    = "0.28.0";
        private const string KuboWindowsUrl =
            "https://dist.ipfs.tech/kubo/v" + KuboVersion +
            "/kubo_v" + KuboVersion + "_windows-amd64.zip";

        // ÔöÇÔöÇÔöÇ Rutas base ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        private static readonly string BaseDir =
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "WoldVirtualP2P", "ipfs");

        /// <summary>Ruta al ejecutable ipfs.exe de Kubo.</summary>
        public static readonly string IpfsExePath =
            Path.Combine(BaseDir, "kubo", "kubo", "ipfs.exe");

        /// <summary>Ruta al repositorio IPFS local.</summary>
        public static readonly string RepoPath =
            Path.Combine(BaseDir, "repo");

        /// <summary>URL de la API HTTP del daemon local.</summary>
        public const string ApiUrl     = "http://127.0.0.1:5001";

        /// <summary>URL del gateway HTTP local.</summary>
        public const string GatewayUrl = "http://127.0.0.1:8080";

        // ÔöÇÔöÇÔöÇ Estado ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        private Process? _daemon;
        private bool     _disposed;

        /// <summary>True si el proceso daemon est├í activo.</summary>
        public bool IsDaemonRunning => _daemon != null && !_daemon.HasExited;

        public string? LocalPeerId { get; private set; }

        /// <summary>Evento de log de estado para la UI.</summary>
        public event Action<string>? OnStatusChanged;

        // ÔöÇÔöÇÔöÇ API P├║blica ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

        /// <summary>
        /// Garantiza que Kubo est├® instalado, el repo inicializado y el daemon en ejecuci├│n.
        /// Es seguro llamarlo varias veces (idempotente).
        /// </summary>
        /// <returns>True si la API IPFS responde correctamente.</returns>
        public async Task<bool> EnsureReadyAsync(CancellationToken token = default)
        {
            try
            {
                // 0. Limpieza de procesos y bloqueos previos para evitar hangs
                LogStatus("­ƒº╣ Limpiando procesos de IPFS previos...");
                KillAllIpfsProcesses();
                CleanStaleLocks();

                // 1. Descargar Kubo si no existe
                if (!File.Exists(IpfsExePath))
                {
                    LogStatus($"­ƒôÑ Descargando IPFS Kubo v{KuboVersion} (25MB)...");
                    await DownloadKuboAsync(token);
                    LogStatus("Ô£à Kubo descargado correctamente.");
                }

                // 2. Inicializar repositorio si no existe
                string blocksDir = Path.Combine(RepoPath, "blocks");
                if (!Directory.Exists(blocksDir))
                {
                    LogStatus("­ƒöº Inicializando repositorio IPFS local...");
                    await RunCliAsync("init --profile=server", token, timeoutMs: 45000);
                    LogStatus("Ô£à Repositorio IPFS inicializado.");
                }

                // 3. Arrancar daemon
                await ConfigureApiAsync(token);
                LogStatus("­ƒÜÇ Iniciando daemon IPFS...");
                StartDaemon();

                bool ready = await WaitForApiAsync(maxAttempts: 40, token);
                if (!ready)
                {
                    LogStatus("ÔÜá´©Å El daemon IPFS no respondi├│ a tiempo.");
                    return false;
                }

                // 4. Obtener Peer ID real
                string rawId = await RunCliAsync("id --format=<id>", token);
                LocalPeerId  = rawId.Trim().Trim('<', '>');
                LogStatus($"­ƒîÉ IPFS activo ÔÇö Peer ID: {LocalPeerId}");

                return true;
            }
            catch (OperationCanceledException)
            {
                LogStatus("ÔÅ╣ Inicializaci├│n IPFS cancelada.");
                return false;
            }
            catch (Exception ex)
            {
                LogStatus($"ÔÜá´©Å Error iniciando IPFS: {ex.Message}");
                return false;
            }
        }

        /// <summary>
        /// Ejecuta un comando de la CLI de ipfs y devuelve el stdout.
        /// Evita deadlocks de buffer y maneja timeouts.
        /// </summary>
        public async Task<string> RunCliAsync(string args, CancellationToken token = default, int timeoutMs = 30000)
        {
            if (!File.Exists(IpfsExePath))
                throw new FileNotFoundException("ipfs.exe no encontrado.", IpfsExePath);

            using var cts = CancellationTokenSource.CreateLinkedTokenSource(token);
            cts.CancelAfter(timeoutMs);

            var psi = new ProcessStartInfo
            {
                FileName               = IpfsExePath,
                Arguments              = args,
                UseShellExecute        = false,
                RedirectStandardOutput = true,
                RedirectStandardError  = false,
                CreateNoWindow         = true,
            };
            psi.EnvironmentVariables["IPFS_PATH"] = RepoPath;

            using var proc = Process.Start(psi)
                ?? throw new InvalidOperationException("No se pudo iniciar ipfs.exe.");

            try
            {
                string stdout = await proc.StandardOutput.ReadToEndAsync(cts.Token);
                await proc.WaitForExitAsync(cts.Token);
                return stdout.Trim();
            }
            catch (OperationCanceledException)
            {
                try { proc.Kill(entireProcessTree: true); } catch { }
                throw new TimeoutException($"El comando 'ipfs {args}' super├│ el tiempo l├¡mite de {timeoutMs}ms.");
            }
        }

        /// <summary>Detiene el daemon IPFS limpiamente.</summary>
        public void StopDaemon()
        {
            try
            {
                if (_daemon != null && !_daemon.HasExited)
                {
                    _daemon.Kill(entireProcessTree: true);
                    _daemon.WaitForExit(3000);
                }
                _daemon?.Dispose();
                _daemon = null;
                LogStatus("ÔÅ╣ Daemon IPFS detenido.");
            }
            catch (Exception ex)
            {
                LogStatus($"ÔÜá´©Å Error al detener daemon IPFS: {ex.Message}");
            }
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            StopDaemon();
        }

        // ÔöÇÔöÇÔöÇ M├®todos Privados ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

        private void KillAllIpfsProcesses()
        {
            try
            {
                foreach (var p in Process.GetProcessesByName("ipfs"))
                {
                    try
                    {
                        p.Kill(entireProcessTree: true);
                        p.WaitForExit(2000);
                    }
                    catch { }
                }
            }
            catch { }
        }

        private void CleanStaleLocks()
        {
            try
            {
                if (Directory.Exists(RepoPath))
                {
                    string lockPath = Path.Combine(RepoPath, "repo.lock");
                    if (File.Exists(lockPath))
                    {
                        File.Delete(lockPath);
                    }

                    string apiPath = Path.Combine(RepoPath, "api");
                    if (File.Exists(apiPath))
                    {
                        File.Delete(apiPath);
                    }
                }
            }
            catch { }
        }

        private async Task DownloadKuboAsync(CancellationToken token)
        {
            string extractRoot = Path.GetDirectoryName(Path.GetDirectoryName(IpfsExePath)!)!;
            Directory.CreateDirectory(extractRoot);

            string zipPath = Path.Combine(extractRoot, "kubo.zip");

            using var http = new HttpClient { Timeout = TimeSpan.FromMinutes(10) };
            LogStatus($"   ÔåÆ Conectando a dist.ipfs.tech...");

            var response = await http.GetAsync(KuboWindowsUrl, HttpCompletionOption.ResponseHeadersRead, token);
            response.EnsureSuccessStatusCode();

            await using (var fs = File.Create(zipPath))
            {
                await response.Content.CopyToAsync(fs, token);
            }

            LogStatus("­ƒôª Extrayendo Kubo...");
            ZipFile.ExtractToDirectory(zipPath, extractRoot, overwriteFiles: true);
            File.Delete(zipPath);
        }

        private async Task ConfigureApiAsync(CancellationToken token)
        {
            try
            {
                // Configurar direccionamiento b├ísico
                await RunCliAsync("config Addresses.API /ip4/127.0.0.1/tcp/5001", token);
                await RunCliAsync("config Addresses.Gateway /ip4/127.0.0.1/tcp/8080", token);
                await RunCliAsync("config --json API.HTTPHeaders.Access-Control-Allow-Origin \"[\\\"*\\\"]\"", token);
                await RunCliAsync("config --json Swarm.ConnMgr.HighWater 300", token);

                // Aplicar el perfil de servidor (modo DHT Server activo) para que otros nodos nos descubran
                await RunCliAsync("config profile apply server", token);

                // Habilitar UPnP / NAT-PMP autom├ítico para abrir el puerto 4001 en el router del usuario
                await RunCliAsync("config --json Swarm.DisableNatPortMap false", token);

                // ÔöÇÔöÇ Relay: Permite que el nodo sea alcanzable desde gateways p├║blicos aunque est├® detr├ís de NAT ÔöÇÔöÇ
                // Cuando un gateway IPFS no puede conectar directamente (puerto 4001 cerrado),
                // el protocolo circuit-relay v2 enruta las conexiones a trav├®s de nodos intermediarios.
                await RunCliAsync("config --json Swarm.RelayClient.Enabled true", token);
                await RunCliAsync("config --json Swarm.EnableAutoRelay true", token);

                // Modo DHT agresivo: anunciar activamente que tenemos los bloques de datos
                // Esto acelera que las pasarelas p├║blicas encuentren el contenido en el DHT
                await RunCliAsync("config --json Routing.Type \"\\\"dhtserver\\\"\"", token);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[ConfigureApi] Advertencia de configuraci├│n: {ex.Message}");
            }
        }

        private void StartDaemon()
        {
            var psi = new ProcessStartInfo
            {
                FileName               = IpfsExePath,
                Arguments              = "daemon --migrate=true --enable-gc",
                UseShellExecute        = false,
                RedirectStandardOutput = true,
                RedirectStandardError  = false,
                CreateNoWindow         = true,
            };
            psi.EnvironmentVariables["IPFS_PATH"] = RepoPath;

            _daemon = Process.Start(psi);
        }

        private async Task<bool> WaitForApiAsync(int maxAttempts, CancellationToken token)
        {
            using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(3) };

            for (int i = 0; i < maxAttempts; i++)
            {
                if (token.IsCancellationRequested) return false;
                try
                {
                    var resp = await http.PostAsync(ApiUrl + "/api/v0/id", null, token);
                    if (resp.IsSuccessStatusCode) return true;
                }
                catch { /* Esperando arranque... */ }

                await Task.Delay(1000, token);
            }
            return false;
        }

        private void LogStatus(string msg) => OnStatusChanged?.Invoke(msg);
    }
}

