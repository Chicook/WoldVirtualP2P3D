using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;

namespace VisorSingularity
{
    /// <summary>
    /// Servicio de sincronización P2P de peers del metaverso.
    /// Utiliza dos transportes en paralelo:
    ///   - LAN: UDP Broadcast en el puerto 50099 (compatibilidad inmediata en red local).
    ///   - WAN: IPFS PubSub GossipSub en el topic /wcv/metaverse/state/v1 (sincronización global).
    /// Ambos transportes escriben los peers recibidos en Estado_Global/peers/ para que
    /// NetworkLayer.gd los integre automáticamente sin modificaciones en Godot.
    /// </summary>
    public sealed class PeerSyncService : IDisposable
    {
        // ── Configuración ──────────────────────────────────────────────────
        private const int UDP_PORT = 50099;
        private const int BROADCAST_INTERVAL_MS = 3000;   // re-broadcast cada 3 s
        private const double PEER_STALE_SECONDS = 35.0;   // tiempo sin ver un peer => borrar
        private const int MAX_PACKET_BYTES = 65000;        // límite seguro UDP

        // ── Estado ─────────────────────────────────────────────────────────
        private readonly string _peersDir;
        private readonly string _localPeerPath;
        private readonly string _localId;

        private UdpClient? _listener;
        private UdpClient? _sender;
        private FileSystemWatcher? _watcher;
        private CancellationTokenSource _cts = new();
        private Task? _listenTask;
        private Task? _heartbeatTask;

        // ── Transporte WAN (IPFS PubSub) ────────────────────────────────────
        private IpfsPubSubTransport? _pubSub;

        private bool _disposed = false;

        public event Action<string, string>? PeerReceived;  // (remoteId, json)
        public event Action<string>? PeerExpired;           // (expiredId)

        // ── Constructores ─────────────────────────────────────────────────
        /// <summary>Sólo transporte LAN (UDP Broadcast).</summary>
        public PeerSyncService(string peersDir, string localId)
        {
            _peersDir = peersDir;
            _localId = localId;
            _localPeerPath = Path.Combine(peersDir, $"peer_{localId}.json");

            if (!Directory.Exists(_peersDir))
                Directory.CreateDirectory(_peersDir);
        }

        /// <summary>
        /// Transporte dual: LAN (UDP Broadcast) + WAN (IPFS PubSub).
        /// Llama a este constructor cuando IpfsManager ya está listo.
        /// </summary>
        public PeerSyncService(string peersDir, string localId, IpfsManager ipfs)
            : this(peersDir, localId)
        {
            _pubSub = new IpfsPubSubTransport(peersDir, localId, ipfs);
            _pubSub.PeerReceived  += (id, json) => PeerReceived?.Invoke(id, json);
            _pubSub.OnStatusChanged += msg => Debug.WriteLine(msg);
        }

        // ── Arranque ──────────────────────────────────────────────────────
        public void Start()
        {
            if (_disposed) return;

            // Listener UDP en cualquier interfaz
            try
            {
                _listener = new UdpClient();
                _listener.Client.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
                _listener.Client.Bind(new IPEndPoint(IPAddress.Any, UDP_PORT));
                _listener.EnableBroadcast = true;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error al abrir socket listener: {ex.Message}");
                return;
            }

            // Sender UDP
            try
            {
                _sender = new UdpClient();
                _sender.EnableBroadcast = true;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error al abrir socket sender: {ex.Message}");
                return;
            }

            // Watcher sobre el peer local
            _watcher = new FileSystemWatcher(_peersDir, $"peer_{_localId}.json")
            {
                NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.Size,
                EnableRaisingEvents = true
            };
            _watcher.Changed += OnLocalPeerChanged;
            _watcher.Created += OnLocalPeerChanged;

            _listenTask = Task.Run(() => ListenLoop(_cts.Token), _cts.Token);
            _heartbeatTask = Task.Run(() => HeartbeatLoop(_cts.Token), _cts.Token);

            // Arrancar el transporte WAN si está configurado
            _pubSub?.Start();

            string wanStatus = _pubSub != null ? "LAN + WAN (IPFS PubSub)" : "LAN (UDP Broadcast)";
            Debug.WriteLine($"[PeerSync] Servicio iniciado. ID local: {_localId}  Transporte: {wanStatus}");
        }

        // ── Loop de escucha ───────────────────────────────────────────────
        private async Task ListenLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested && _listener != null)
            {
                try
                {
                    var result = await _listener.ReceiveAsync(token);
                    var json = Encoding.UTF8.GetString(result.Buffer);
                    ProcessReceivedPeer(json, result.RemoteEndPoint.Address.ToString());
                }
                catch (OperationCanceledException) { break; }
                catch (ObjectDisposedException) { break; }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[PeerSync] Error en ListenLoop: {ex.Message}");
                    await Task.Delay(500, token).ConfigureAwait(false);
                }
            }
        }

        // ── Heartbeat: re-difundir aunque no haya cambios ─────────────────
        private async Task HeartbeatLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    await Task.Delay(BROADCAST_INTERVAL_MS, token);
                    BroadcastLocalPeer();
                    PurgeStaleRemotePeers();
                }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[PeerSync] Error en HeartbeatLoop: {ex.Message}");
                }
            }
        }

        // ── Evento: el peer local cambió → difundir inmediatamente ─────────
        private void OnLocalPeerChanged(object sender, FileSystemEventArgs e)
        {
            // Pequeño delay para que Godot termine de escribir el .tmp → rename
            Task.Delay(80).ContinueWith(_ => BroadcastLocalPeer());
        }

        // ── Difundir el peer local por broadcast ──────────────────────────
        private void BroadcastLocalPeer()
        {
            if (_disposed || _sender == null) return;
            if (!File.Exists(_localPeerPath)) return;

            try
            {
                string json;
                using (var fs = new FileStream(_localPeerPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (var sr = new StreamReader(fs, Encoding.UTF8))
                    json = sr.ReadToEnd();

                if (string.IsNullOrWhiteSpace(json)) return;

                // Validación mínima: debe ser un objeto JSON
                if (!json.TrimStart().StartsWith("{")) return;

                var bytes = Encoding.UTF8.GetBytes(json);
                if (bytes.Length > MAX_PACKET_BYTES)
                {
                    Debug.WriteLine($"[PeerSync] Peer local demasiado grande ({bytes.Length} bytes), omitido.");
                    return;
                }

                var endpoint = new IPEndPoint(IPAddress.Broadcast, UDP_PORT);
                _sender.Send(bytes, bytes.Length, endpoint);
                Debug.WriteLine($"[PeerSync] Broadcast enviado ({bytes.Length} bytes)");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error al difundir peer: {ex.Message}");
            }
        }

        // ── Procesar peer recibido ─────────────────────────────────────────
        private void ProcessReceivedPeer(string json, string sourceIp)
        {
            if (string.IsNullOrWhiteSpace(json)) return;

            try
            {
                // Validación centralizada: esquema, tamaño, ID seguro
                if (!PeerSchema.TryValidate(json, out string remoteId))
                {
                    Debug.WriteLine($"[PeerSync] JSON inválido o peer ID inseguro recibido desde {sourceIp}, ignorado.");
                    return;
                }

                // Ignorar paquetes propios
                if (remoteId == _localId) return;

                // Escritura atómica en el directorio compartido con Godot
                var targetPath = Path.Combine(_peersDir, PeerSchema.GetPeerFileName(remoteId));
                var tmpPath = targetPath + ".tmp";

                using (var fs = new FileStream(tmpPath, FileMode.Create, FileAccess.Write, FileShare.None))
                using (var sw = new StreamWriter(fs, Encoding.UTF8))
                    sw.Write(json);

                if (File.Exists(targetPath)) File.Delete(targetPath);
                File.Move(tmpPath, targetPath);

                Debug.WriteLine($"[PeerSync] Peer remoto '{remoteId}' recibido desde {sourceIp} ({json.Length} chars)");
                PeerReceived?.Invoke(remoteId, json);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error al procesar peer remoto: {ex.Message}");
            }
        }

        // ── Limpiar peers remotos caducados ───────────────────────────────
        private void PurgeStaleRemotePeers()
        {
            if (!Directory.Exists(_peersDir)) return;

            try
            {
                var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;

                foreach (var file in Directory.GetFiles(_peersDir, "peer_*.json"))
                {
                    string? peerId = PeerSchema.ExtractPeerIdFromFileName(file);
                    if (peerId == null || peerId == _localId) continue; // nunca borrar el propio

                    try
                    {
                        string json;
                        using (var fs = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                        using (var sr = new StreamReader(fs, Encoding.UTF8))
                            json = sr.ReadToEnd();

                        using var doc = JsonDocument.Parse(json);
                        var root = doc.RootElement;

                        // Obtener timestamp Unix del campo "t" en el bloque "u"
                        double peerT = 0;
                        if (root.TryGetProperty("u", out var usersEl) && usersEl.ValueKind == JsonValueKind.Object)
                        {
                            foreach (var userProp in usersEl.EnumerateObject())
                            {
                                if (userProp.Value.TryGetProperty("t", out var tEl))
                                    peerT = tEl.GetDouble();
                                break;
                            }
                        }

                        if (peerT > 0 && now - peerT > PEER_STALE_SECONDS)
                        {
                            File.Delete(file);
                            Debug.WriteLine($"[PeerSync] Peer caducado eliminado: {peerId}");
                            PeerExpired?.Invoke(peerId);
                        }
                    }
                    catch { /* Ignorar errores individuales de archivo */ }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error al purgar peers: {ex.Message}");
            }
        }

        // ── Parada y limpieza ─────────────────────────────────────────────
        public void Stop()
        {
            if (_disposed) return;
            _cts.Cancel();

            // Detener transporte WAN primero
            _pubSub?.Stop();

            if (_watcher != null)
            {
                _watcher.EnableRaisingEvents = false;
                _watcher.Dispose();
                _watcher = null;
            }

            try { _listener?.Close(); } catch { }
            try { _sender?.Close(); } catch { }

            try { _listenTask?.Wait(1000); } catch { }
            try { _heartbeatTask?.Wait(500); } catch { }

            Debug.WriteLine("[PeerSync] Servicio detenido (LAN + WAN).");
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            Stop();
            _cts.Dispose();
            _listener?.Dispose();
            _sender?.Dispose();
            _pubSub?.Dispose();
        }
    }
}
