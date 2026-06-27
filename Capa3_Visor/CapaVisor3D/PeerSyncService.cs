using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;
using VisorSingularity.Services;

namespace VisorSingularity
{
    /// <summary>
    /// Servicio de sincronización P2P LAN de peers del metaverso.
    /// Difunde el peer JSON local por UDP broadcast y escribe los peers remotos recibidos
    /// en la carpeta Estado_Global/peers/ para que Godot los lea automáticamente.
    /// Puerto: 50099 (UDP broadcast LAN)
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

        private bool _disposed = false;

        public event Action<string, string>? PeerReceived;  // (remoteId, json)
        public event Action<string>? PeerExpired;           // (expiredId)

        // ── Constructor ───────────────────────────────────────────────────
        public PeerSyncService(string peersDir, string localId)
        {
            _peersDir = peersDir;
            _localId = localId;
            _localPeerPath = Path.Combine(peersDir, $"peer_{localId}.json");

            if (!Directory.Exists(_peersDir))
                Directory.CreateDirectory(_peersDir);
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

            _listenTask = ListenLoop(_cts.Token);
            _heartbeatTask = HeartbeatLoop(_cts.Token);

            Debug.WriteLine($"[PeerSync] Servicio iniciado. ID local: {_localId}  Puerto UDP: {UDP_PORT}");
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
        private async void OnLocalPeerChanged(object sender, FileSystemEventArgs e)
        {
            try
            {
                // Pequeño delay para que Godot termine de escribir el .tmp → rename
                await Task.Delay(80);
                BroadcastLocalPeer();
            }
            catch (OperationCanceledException)
            {
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error en OnLocalPeerChanged: {ex.Message}");
            }
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

                // Actualizar a versión 1.1 firmada si la identidad está disponible
                if (NodeIdentityManager.Current != null)
                {
                    try
                    {
                        var state = JsonSerializer.Deserialize<PeerStateContract>(json);
                        if (state != null)
                        {
                            state.Version = "1.1";
                            state.NodeId = NodeIdentityManager.Current.NodeId;
                            state.Timestamp = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
                            state.PublicKeyBase64 = NodeIdentityManager.Current.PublicKeyBase64;
                            state.Signature = NodeIdentityManager.SignData(state.GetSignablePayload());

                            json = JsonSerializer.Serialize(state);
                        }
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"[PeerSync] Error al firmar peer local: {ex.Message}");
                    }
                }

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

        // ── Auxiliares de Validación y Seguridad ──────────────────────────
        private static bool IsSafeId(string id)
        {
            if (string.IsNullOrWhiteSpace(id) || id.Length < 3 || id.Length > 64)
                return false;

            foreach (char c in id)
            {
                if (!char.IsLetterOrDigit(c) && c != '_' && c != '-')
                    return false;
            }
            return true;
        }

        private static DateTime? ParseTimestamp(JsonElement root)
        {
            if (root.TryGetProperty("ts", out var tsEl) && tsEl.ValueKind == JsonValueKind.String)
            {
                if (DateTime.TryParse(tsEl.GetString(), out var dt))
                    return dt.ToUniversalTime();
            }
            return null;
        }

        // ── Procesar peer recibido ─────────────────────────────────────────
        private void ProcessReceivedPeer(string json, string sourceIp)
        {
            if (string.IsNullOrWhiteSpace(json)) return;

            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                string remoteId = "";
                bool isSigned = false;

                // 1. Intentar leer según contrato versión 1.1 (identidad y firma)
                if (root.TryGetProperty("id", out var idProp) && idProp.ValueKind == JsonValueKind.String)
                {
                    remoteId = idProp.GetString() ?? "";
                    isSigned = root.TryGetProperty("sig", out _) && root.TryGetProperty("pk", out _);
                }

                // 2. Fallback a versión 1.0 (usar el primer nombre del diccionario "u" o "i")
                if (string.IsNullOrEmpty(remoteId))
                {
                    if (root.TryGetProperty("u", out var usersEl) && usersEl.ValueKind == JsonValueKind.Object)
                    {
                        foreach (var prop in usersEl.EnumerateObject())
                        {
                            remoteId = prop.Name;
                            break;
                        }
                    }

                    if (string.IsNullOrEmpty(remoteId) && root.TryGetProperty("i", out var islandsEl)
                        && islandsEl.ValueKind == JsonValueKind.Object)
                    {
                        foreach (var prop in islandsEl.EnumerateObject())
                        {
                            remoteId = prop.Name;
                            break;
                        }
                    }
                }

                // Saneamiento de seguridad de ID (previene Path Traversal)
                if (!IsSafeId(remoteId))
                {
                    Debug.WriteLine($"[PeerSync] ID de peer malformado o potencialmente peligroso: '{remoteId}'");
                    return;
                }

                // Ignorar paquetes propios (por ID LAN local o ID persistente del nodo)
                if (remoteId == _localId || (NodeIdentityManager.Current != null && remoteId == NodeIdentityManager.Current.NodeId))
                {
                    return;
                }

                // 3. Validación de firma si está firmado (1.1+)
                if (isSigned)
                {
                    try
                    {
                        var state = JsonSerializer.Deserialize<PeerStateContract>(json);
                        if (state != null)
                        {
                            bool sigOk = NodeIdentityManager.VerifyData(state.GetSignablePayload(), state.Signature, state.PublicKeyBase64);
                            if (!sigOk)
                            {
                                Debug.WriteLine($"[PeerSync] Firma inválida recibida de peer '{remoteId}', descartando.");
                                return;
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"[PeerSync] Error al verificar firma de peer '{remoteId}': {ex.Message}");
                        return;
                    }
                }

                // 4. Verificación de Timestamp (Anti-Replay)
                var targetPath = Path.Combine(_peersDir, $"peer_{remoteId}.json");
                if (File.Exists(targetPath))
                {
                    try
                    {
                        string existingJson = File.ReadAllText(targetPath, Encoding.UTF8);
                        using var existingDoc = JsonDocument.Parse(existingJson);
                        var existingTs = ParseTimestamp(existingDoc.RootElement);
                        var incomingTs = ParseTimestamp(root);

                        if (existingTs.HasValue && incomingTs.HasValue && incomingTs.Value <= existingTs.Value)
                        {
                            // Paquete más viejo o duplicado, ignorar silenciosamente
                            return;
                        }
                    }
                    catch
                    {
                        // Si falla lectura, sobrescribimos
                    }
                }

                // Escribir el peer en el directorio compartido de forma atómica
                var tmpPath = targetPath + ".tmp";
                using (var fs = new FileStream(tmpPath, FileMode.Create, FileAccess.Write, FileShare.None))
                using (var sw = new StreamWriter(fs, Encoding.UTF8))
                    sw.Write(json);

                if (File.Exists(targetPath)) File.Delete(targetPath);
                File.Move(tmpPath, targetPath);

                Debug.WriteLine($"[PeerSync] Peer remoto '{remoteId}' recibido y verificado desde {sourceIp} ({json.Length} chars)");
                PeerReceived?.Invoke(remoteId, json);
            }
            catch (JsonException)
            {
                Debug.WriteLine($"[PeerSync] JSON inválido recibido desde {sourceIp}, ignorado.");
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
                    var name = Path.GetFileNameWithoutExtension(file); // "peer_<id>"
                    var peerId = name.Replace("peer_", "");
                    if (peerId == _localId) continue; // nunca borrar el propio

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

            if (_watcher != null)
            {
                _watcher.EnableRaisingEvents = false;
                _watcher.Dispose();
                _watcher = null;
            }

            try { _listener?.Close(); } catch (Exception ex) { Debug.WriteLine($"[PeerSync] Error al cerrar listener: {ex.Message}"); }
            try { _sender?.Close(); } catch (Exception ex) { Debug.WriteLine($"[PeerSync] Error al cerrar sender: {ex.Message}"); }

            try { _listenTask?.Wait(1000); } catch (Exception ex) { Debug.WriteLine($"[PeerSync] Error al esperar ListenLoop: {ex.Message}"); }
            try { _heartbeatTask?.Wait(500); } catch (Exception ex) { Debug.WriteLine($"[PeerSync] Error al esperar HeartbeatLoop: {ex.Message}"); }

            Debug.WriteLine("[PeerSync] Servicio detenido.");
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            Stop();
            _cts.Dispose();
            _listener?.Dispose();
            _sender?.Dispose();
        }
    }
}
