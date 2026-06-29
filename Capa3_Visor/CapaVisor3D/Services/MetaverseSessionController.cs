using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Text;
using System.Threading.Tasks;
using System.Windows;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Datos del resultado de confirmacion MetaMask, entregados al host WPF.
    /// </summary>
    public record MetaMaskConfirm(string User, string Wallet, string Island, string Signature, bool IsLogin);

    /// <summary>
    /// Orquesta el ciclo de vida de los subsistemas de metaverso:
    ///  - Puentes HTTP locales (login y registro) en el puerto 8080
    ///  - Inicio del nodo P2P
    ///  - Inicio de la sincronizacion LAN de peers
    /// Notifica a la capa WPF via eventos para mantener la separacion UI/logica.
    /// </summary>
    public sealed class MetaverseSessionController : IDisposable
    {
        private const int BridgePort = 8080;

        private HttpListener? _httpListener;
        private P2PWebNode?   _p2pNode;
        private PeerSyncService? _peerSync;
        private string? _wsPortFilePath;
        private bool _disposed;
        private volatile bool _isClosing;

        // ── Eventos ───────────────────────────────────────────────────────────

        /// <summary>Se dispara cuando MetaMask confirma el login/registro.</summary>
        public event Action<MetaMaskConfirm>? LoginConfirmed;

        /// <summary>Se dispara cuando el estado del nodo P2P cambia.</summary>
        public event Action<string>? P2PStatusChanged;

        /// <summary>Se dispara cuando hay un error critico de inicio de servidor.</summary>
        public event Action<string>? BridgeError;

        // ── Telemetria de red ─────────────────────────────────────────────────

        /// <summary>Instantanea actual de la telemetria de red P2P.</summary>
        public NetworkTelemetrySnapshot NetworkTelemetry => NetworkTelemetryService.Instance.GetSnapshot();

        /// <summary>Resumen de una linea de la telemetria para barras de estado.</summary>
        public string NetworkTelemetrySummary => NetworkTelemetryService.Instance.GetSummaryLine();

        /// <summary>Se dispara cuando cambia la telemetria de red (peers, trafico, etc.).</summary>
        public event Action<NetworkTelemetrySnapshot>? NetworkTelemetryUpdated
        {
            add    => NetworkTelemetryService.Instance.SnapshotUpdated += value;
            remove => NetworkTelemetryService.Instance.SnapshotUpdated -= value;
        }

        // ── Propiedades del nodo P2P ──────────────────────────────────────────
        public string? P2PSimulatedUrl => _p2pNode?.SimulatedUrl;
        public string? P2PLocalUrl     => _p2pNode?.LocalUrl;
        public string? P2PGatewayUrl   => _p2pNode?.GatewayUrl;
        public string? P2PNodeId       => _p2pNode?.NodeId;
        public bool    P2PIsOnIpfs     => _p2pNode?.IsOnIpfs  ?? false;
        public bool    P2PTunnelActive => _p2pNode?.IsTunnelActive ?? false;
        public string? P2PGatewayLink  => _p2pNode?.GatewayUrl;

        // ── HTTP Bridge - Login ───────────────────────────────────────────────

        /// <summary>
        /// Arranca el servidor HTTP en modo LOGIN (usuario ya registrado).
        /// </summary>
        public void StartHttpBridgeLogin()
        {
            try
            {
                StopHttpBridge();
                _httpListener = new HttpListener();
                _httpListener.Prefixes.Add($"http://localhost:{BridgePort}/");
                _httpListener.Start();
                Task.Run(() => ListenLoopLoginAsync());
                Debug.WriteLine("[MetaverseSessionController] HTTP Bridge Login iniciado");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[MetaverseSessionController] Error al iniciar HTTP Bridge: {ex.Message}");
                BridgeError?.Invoke(ex.Message);
            }
        }

        private async Task ListenLoopLoginAsync()
        {
            while (_httpListener != null && _httpListener.IsListening && !_isClosing)
            {
                try
                {
                    var context  = await _httpListener.GetContextAsync();
                    var request  = context.Request;
                    var response = context.Response;
                    string path  = request.Url?.AbsolutePath ?? "/";

                    if (path == "/confirm")
                    {
                        string user      = request.QueryString["user"]      ?? "Usuario";
                        string wallet    = request.QueryString["wallet"]    ?? "0x0000";
                        string island    = request.QueryString["islandId"]  ?? "1 : 0.0.0";
                        string signature = request.QueryString["signature"] ?? "";

                        string html = "<html><head><meta charset='UTF-8'><style>body{background:#0a0f1a;color:#00d9ff;font-family:sans-serif;text-align:center;padding-top:100px;}h1{color:#00ff8c;}</style></head><body><h1>&#x2705; Sesion Iniciada</h1><p>Puedes regresar al Visor.</p></body></html>";
                        await WriteHtmlResponseAsync(response, html);

                        StopHttpBridge();
                        LoginConfirmed?.Invoke(new MetaMaskConfirm(user, wallet, island, signature, IsLogin: true));
                    }
                    else
                    {
                        await ServeMetaMaskHtmlAsync(response, null);
                    }
                }
                catch { }
            }
        }

        // ── HTTP Bridge - Registro ────────────────────────────────────────────

        /// <summary>
        /// Arranca el servidor HTTP en modo REGISTRO (usuario nuevo).
        /// </summary>
        public void StartHttpBridgeRegister(string username)
        {
            try
            {
                StopHttpBridge();
                _httpListener = new HttpListener();
                _httpListener.Prefixes.Add($"http://localhost:{BridgePort}/");
                _httpListener.Start();
                Task.Run(() => ListenLoopRegisterAsync(username));
                Debug.WriteLine($"[MetaverseSessionController] HTTP Bridge Registro iniciado para '{username}'");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[MetaverseSessionController] Error al iniciar HTTP Bridge: {ex.Message}");
                BridgeError?.Invoke(ex.Message);
            }
        }

        private async Task ListenLoopRegisterAsync(string username)
        {
            while (_httpListener != null && _httpListener.IsListening && !_isClosing)
            {
                try
                {
                    var context  = await _httpListener.GetContextAsync();
                    var request  = context.Request;
                    var response = context.Response;
                    string path  = request.Url?.AbsolutePath ?? "/";

                    if (path == "/confirm")
                    {
                        string user      = request.QueryString["user"]     ?? username;
                        string wallet    = request.QueryString["wallet"]   ?? "No Wallet";
                        string island    = request.QueryString["islandId"] ?? "137 : 190.1.0";
                        string signature = request.QueryString["signature"] ?? "";

                        string html = "<html><head><meta charset='UTF-8'><title>Confirmado</title><style>body{background:#0a0f1a;color:#00d9ff;font-family:sans-serif;text-align:center;padding-top:100px;}h1{color:#00ff8c;}</style></head><body><h1>Metaverse Link Confirmed!</h1><p>Puedes regresar al Visor de la aplicacion.</p></body></html>";
                        await WriteHtmlResponseAsync(response, html);

                        LoginConfirmed?.Invoke(new MetaMaskConfirm(user, wallet, island, signature, IsLogin: false));
                    }
                    else
                    {
                        await ServeMetaMaskHtmlAsync(response, username);
                    }
                }
                catch { }
            }
        }

        public void StopHttpBridge()
        {
            if (_httpListener != null)
            {
                try { _httpListener.Stop(); _httpListener.Close(); } catch { }
                _httpListener = null;
            }
        }

        // ── Nodo P2P ──────────────────────────────────────────────────────────

        public void StartP2PWebNode(string username, string repoPath)
        {
            if (_p2pNode != null) return;
            try
            {
                _p2pNode = new P2PWebNode(username, repoPath);
                _p2pNode.OnStatusChanged += (status) => P2PStatusChanged?.Invoke(status);
                _p2pNode.Start();

                // Publicar el puerto WebSocket real para que Godot lo descubra.
                // El puerto puede diferir de 8082 si TcpPortFinder eligió otro libre.
                PublishWebSocketPort(repoPath, _p2pNode.Port);

                Debug.WriteLine($"[MetaverseSessionController] P2PWebNode iniciado para '{username}' (WS port {_p2pNode.Port})");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[MetaverseSessionController] Error al iniciar P2PWebNode: {ex.Message}");
            }
        }

        /// <summary>
        /// Escribe el puerto real del servidor WebSocket local en
        /// <c>Estado_Global/ws_port.txt</c> para que el cliente Godot lo lea y
        /// se conecte al puerto correcto aunque 8082 estuviera ocupado.
        /// </summary>
        private void PublishWebSocketPort(string repoPath, int port)
        {
            try
            {
                string estadoGlobalDir = Path.Combine(repoPath, "Estado_Global");
                Directory.CreateDirectory(estadoGlobalDir);
                _wsPortFilePath = Path.Combine(estadoGlobalDir, "ws_port.txt");
                File.WriteAllText(_wsPortFilePath, port.ToString(System.Globalization.CultureInfo.InvariantCulture));
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[MetaverseSessionController] No se pudo publicar el puerto WS: {ex.Message}");
            }
        }

        // ── Sincronizacion LAN ────────────────────────────────────────────────

        public void StartPeerSync(string peersDir, string username)
        {
            if (_peerSync != null) return;
            try
            {
                if (!Directory.Exists(peersDir)) Directory.CreateDirectory(peersDir);
                _peerSync = new PeerSyncService(peersDir, username);
                _peerSync.PeerReceived += (remoteId, json) => P2PWebNode.BroadcastToWs(json);
                _peerSync.Start();
                Debug.WriteLine($"[MetaverseSessionController] PeerSync LAN iniciado para '{username}'");

                // Bootstrap de Internet: cargar nodos semilla desde IPNS y saludarlos.
                _ = LoadAndGreetBootstrapPeersAsync(peersDir);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[MetaverseSessionController] Error al iniciar PeerSync: {ex.Message}");
            }
        }

        /// <summary>
        /// Resuelve la lista de nodos semilla publicada en IPNS (con caché local)
        /// y envía un HELLO de bootstrap a cada una para descubrir la malla P2P
        /// más allá de la LAN. Es best-effort: cualquier fallo se ignora.
        /// </summary>
        private async Task LoadAndGreetBootstrapPeersAsync(string peersDir)
        {
            try
            {
                // La caché vive junto al estado global, un nivel sobre peers/.
                string estadoGlobalDir = Path.GetFullPath(Path.Combine(peersDir, ".."));
                string cachePath = Path.Combine(estadoGlobalDir, "bootstrap_peers.json");

                var bootstrap = new BootstrapPeerService(cachePath);
                var seeds = await bootstrap.GetSeedPeersAsync().ConfigureAwait(false);
                if (seeds.Count > 0 && _peerSync != null)
                {
                    _peerSync.GreetSeedPeers(seeds);
                    Debug.WriteLine($"[MetaverseSessionController] Bootstrap: {seeds.Count} semillas contactadas.");
                }
                else
                {
                    Debug.WriteLine("[MetaverseSessionController] Bootstrap: sin semillas disponibles (solo LAN).");
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[MetaverseSessionController] Error en bootstrap IPNS: {ex.Message}");
            }
        }

        public void StopAll()
        {
            _isClosing = true;
            StopHttpBridge();
            _peerSync?.Stop();
            _peerSync = null;

            // Eliminar el archivo de descubrimiento de puerto para que Godot no
            // intente reconectar a un servidor WebSocket ya apagado.
            if (!string.IsNullOrEmpty(_wsPortFilePath))
            {
                try { if (File.Exists(_wsPortFilePath)) File.Delete(_wsPortFilePath); } catch { }
                _wsPortFilePath = null;
            }
        }

        // ── Helpers HTTP ──────────────────────────────────────────────────────

        private static async Task WriteHtmlResponseAsync(HttpListenerResponse response, string html)
        {
            byte[] buf = Encoding.UTF8.GetBytes(html);
            response.ContentLength64 = buf.Length;
            response.ContentType = "text/html; charset=UTF-8";
            await response.OutputStream.WriteAsync(buf, 0, buf.Length);
            response.OutputStream.Close();
        }

        private static async Task ServeMetaMaskHtmlAsync(HttpListenerResponse response, string? username)
        {
            string wwwPath  = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "www");
            string filePath = Path.Combine(wwwPath, "metamask.html");

            if (File.Exists(filePath))
            {
                byte[] buf = File.ReadAllBytes(filePath);
                response.ContentLength64 = buf.Length;
                response.ContentType = "text/html; charset=UTF-8";
                await response.OutputStream.WriteAsync(buf, 0, buf.Length);
            }
            else
            {
                string fallbackUser = username ?? "Usuario";
                string fakeWallet   = Guid.NewGuid().ToString().Replace("-", "").Substring(0, 40);
                string fallback     = $"<html><head><meta charset='UTF-8'><style>body{{background:#0a0f1a;color:#fff;font-family:sans-serif;text-align:center;padding:50px;}}a{{background:#00d9ff;color:#000;padding:12px 24px;text-decoration:none;font-weight:bold;border-radius:6px;}}</style></head><body><h1>WoldVirtual</h1><p>Usuario: {fallbackUser}</p><br><a href='/confirm?user={fallbackUser}&wallet=0x{fakeWallet}&islandId=1+%3A+0.0.0'>SIMULAR CONEXION METAMASK</a></body></html>";
                byte[] buf = Encoding.UTF8.GetBytes(fallback);
                response.ContentLength64 = buf.Length;
                response.ContentType = "text/html; charset=UTF-8";
                await response.OutputStream.WriteAsync(buf, 0, buf.Length);
            }
            response.OutputStream.Close();
        }

        // ── IDisposable ───────────────────────────────────────────────────────

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            StopAll();
        }
    }
}
