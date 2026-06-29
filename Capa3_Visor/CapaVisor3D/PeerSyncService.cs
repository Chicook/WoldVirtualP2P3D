using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using System.Text.Json.Nodes;

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
        private const double PEER_INACTIVE_SECONDS = 35.0; // sin actividad => inactivo
        private const double PEER_PURGE_SECONDS = 60.0;      // purga RAM + aviso a Godot
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

        // Resolucion de conflictos: anti-replay (seq), causalidad y autoria de isla.
        private readonly Services.ConflictResolver _conflictResolver = new();
        // Reloj vectorial local del nodo, avanzado en cada broadcast propio.
        private readonly Services.VectorClock _localClock = new();
        // Numero de secuencia monotonico de los estados emitidos por este nodo.
        private long _localSeq = 0;

        private readonly Services.PeerRateLimiter _rateLimiter = new();
        private readonly ConcurrentDictionary<string, byte> _trustedPeers = new();
        private readonly ConcurrentDictionary<string, string> _helloFromByIp = new();
        private readonly ConcurrentDictionary<string, double> _inactiveSince = new();
        private readonly string? _walletAddress;
        private readonly string? _walletSignature;

        public event Action<string, string>? PeerReceived;  // (remoteId, json)
        public event Action<string>? PeerExpired;           // (expiredId)

        // ── Constructor ───────────────────────────────────────────────────
        public PeerSyncService(
            string peersDir,
            string localId,
            string? walletAddress = null,
            string? walletSignature = null)
        {
            _peersDir = peersDir;
            _localId = localId;
            _localPeerPath = Path.Combine(peersDir, $"peer_{localId}.json");
            _walletAddress = walletAddress;
            _walletSignature = walletSignature ?? "0x_simulated_signature_local";

            if (!string.IsNullOrWhiteSpace(walletAddress))
            {
                try
                {
                    using var identity = VisorSingularity.Identity.NodeIdentity.LoadOrCreate();
                    identity.BindWallet(walletAddress, _walletSignature);
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[PeerSync] No se pudo vincular wallet al nodo: {ex.Message}");
                }
            }

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

            _listenTask = Task.Run(() => ListenLoop(_cts.Token), _cts.Token);
            _heartbeatTask = Task.Run(() => HeartbeatLoop(_cts.Token), _cts.Token);

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
                    Services.NetworkTelemetryService.Instance.RecordPacketReceived(result.Buffer.Length);
                    DispatchIncoming(json, result.RemoteEndPoint);
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
                    BroadcastHello();
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

                // Cargar identidad local y firmar el estado
                var node = JsonNode.Parse(json);
                if (node != null)
                {
                    node.AsObject().Remove("sig");
                    node.AsObject().Remove("pubkey");

                    // Avanzar secuencia monotonica y reloj vectorial del nodo local.
                    // Ambos campos quedan dentro del payload firmado para evitar manipulacion.
                    long seq = System.Threading.Interlocked.Increment(ref _localSeq);
                    _localClock.Increment(_localId);
                    node.AsObject()["seq"] = seq;
                    node.AsObject()["vc"] = JsonNode.Parse(_localClock.ToJson());

                    string cleanJson = node.ToJsonString();
                    byte[] cleanBytes = Encoding.UTF8.GetBytes(cleanJson);

                    using var identity = VisorSingularity.Identity.NodeIdentity.LoadOrCreate();
                    byte[] signatureBytes = identity.Sign(cleanBytes);
                    string signatureHex = BitConverter.ToString(signatureBytes).Replace("-", "").ToLower();
                    string pubKeyHex = BitConverter.ToString(identity.PublicKey).Replace("-", "").ToLower();

                    node.AsObject()["sig"] = signatureHex;
                    node.AsObject()["pubkey"] = pubKeyHex;

                    json = node.ToJsonString();
                }

                var bytes = Encoding.UTF8.GetBytes(json);
                if (bytes.Length > MAX_PACKET_BYTES)
                {
                    Debug.WriteLine($"[PeerSync] Peer local demasiado grande ({bytes.Length} bytes), omitido.");
                    return;
                }

                var endpoint = new IPEndPoint(IPAddress.Broadcast, UDP_PORT);
                _sender.Send(bytes, bytes.Length, endpoint);
                Services.NetworkTelemetryService.Instance.RecordPacketSent(bytes.Length);
                Debug.WriteLine($"[PeerSync] Broadcast enviado con firma criptográfica ({bytes.Length} bytes)");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error al difundir peer: {ex.Message}");
            }
        }

        // ── Bootstrap: saludar a nodos semilla por unicast (fuera de la LAN) ──
        /// <summary>
        /// Envía un HELLO dirigido a cada nodo semilla conocido (cargado desde la
        /// lista IPNS de bootstrap). Esto permite descubrir la malla P2P más allá
        /// del broadcast de la red local; cada semilla que responda iniciará el
        /// flujo normal de handshake/catch-up.
        /// </summary>
        public void GreetSeedPeers(IEnumerable<Services.SeedPeer> seedPeers)
        {
            if (_disposed || _sender == null || seedPeers == null) return;

            string hello = Services.CatchupProtocol.BuildHello(_localId, _localClock);
            foreach (var seed in seedPeers)
            {
                if (seed == null || seed.NodeId == _localId) continue;
                try
                {
                    if (!IPAddress.TryParse(seed.Host, out var addr))
                    {
                        // Resolver nombres DNS de forma defensiva.
                        var resolved = Dns.GetHostAddresses(seed.Host);
                        if (resolved.Length == 0) continue;
                        addr = resolved[0];
                    }
                    var endpoint = new IPEndPoint(addr, seed.Port);
                    SendUnicast(hello, endpoint);
                    SendHandshakeUnicast(endpoint);
                    Debug.WriteLine($"[PeerSync] HELLO de bootstrap enviado a semilla {seed.Host}:{seed.Port}");
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[PeerSync] No se pudo contactar semilla {seed.Host}: {ex.Message}");
                }
            }
        }

        // ── Difundir HELLO con el reloj vectorial (descubrimiento + catch-up) ──
        /// <summary>
        /// Anuncia por broadcast la identidad y el reloj vectorial del nodo. Los
        /// peers que se reincorporan tras una partición usan este mensaje para
        /// detectar quién está más avanzado y solicitar un catch-up.
        /// </summary>
        private void BroadcastHello()
        {
            if (_disposed || _sender == null) return;
            try
            {
                string hello = Services.CatchupProtocol.BuildHello(_localId, _localClock);
                var bytes = Encoding.UTF8.GetBytes(hello);
                var endpoint = new IPEndPoint(IPAddress.Broadcast, UDP_PORT);
                _sender.Send(bytes, bytes.Length, endpoint);
                Services.NetworkTelemetryService.Instance.RecordPacketSent(bytes.Length);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error al difundir HELLO: {ex.Message}");
            }
        }

        // ── Procesar peer recibido ─────────────────────────────────────────
        private void ProcessReceivedPeer(string json, string sourceIp)
        {
            if (string.IsNullOrWhiteSpace(json)) return;

            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                // Extraer el ID del remoto del bloque "u" (primer key del dict de usuarios)
                string remoteId = "";
                if (root.TryGetProperty("u", out var usersEl) && usersEl.ValueKind == JsonValueKind.Object)
                {
                    foreach (var prop in usersEl.EnumerateObject())
                    {
                        remoteId = prop.Name;
                        break;
                    }
                }

                // Si no hay usuarios, intentar bloque "i" (islas)
                if (string.IsNullOrEmpty(remoteId) && root.TryGetProperty("i", out var islandsEl)
                    && islandsEl.ValueKind == JsonValueKind.Object)
                {
                    foreach (var prop in islandsEl.EnumerateObject())
                    {
                        remoteId = prop.Name;
                        break;
                    }
                }

                // Ignorar paquetes propios o vacíos
                if (string.IsNullOrEmpty(remoteId) || remoteId == _localId) return;

                // Saneamiento de Directory Traversal
                if (!Regex.IsMatch(remoteId, "^[a-fA-F0-9]{64}$") && !Regex.IsMatch(remoteId, "^[a-zA-Z0-9_\\-]+$"))
                {
                    Services.NetworkTelemetryService.Instance.RecordInjectionAttempt();
                    _rateLimiter.BlockIp(sourceIp);
                    Debug.WriteLine($"[PeerSync] Intento de inyección detectado o remoteId inválido '{remoteId}', IP bloqueada temporalmente.");
                    return;
                }

                if (!_trustedPeers.ContainsKey(remoteId))
                {
                    Debug.WriteLine($"[PeerSync] Peer '{remoteId}' sin handshake previo, descartando estado.");
                    return;
                }

                if (!_rateLimiter.TryAllowPeerUpdate(remoteId))
                {
                    Debug.WriteLine($"[PeerSync] Rate limit excedido para '{remoteId}', descartando.");
                    return;
                }

                // Validación de esquema y firma
                if (root.TryGetProperty("sig", out var sigEl) && root.TryGetProperty("pubkey", out var pubKeyEl))
                {
                    string sigHex = sigEl.GetString() ?? "";
                    string pubKeyHex = pubKeyEl.GetString() ?? "";

                    if (!string.IsNullOrEmpty(sigHex) && !string.IsNullOrEmpty(pubKeyHex))
                    {
                        var node = JsonNode.Parse(json);
                        if (node != null)
                        {
                            node.AsObject().Remove("sig");
                            node.AsObject().Remove("pubkey");
                            string cleanJson = node.ToJsonString();
                            byte[] cleanBytes = Encoding.UTF8.GetBytes(cleanJson);

                            byte[] signatureBytes = ConvertHexToBytes(sigHex);
                            byte[] publicKeyBytes = ConvertHexToBytes(pubKeyHex);

                            bool isSignatureValid = false;
                            try
                            {
                                using var ecdsa = ECDsa.Create();
                                ecdsa.ImportSubjectPublicKeyInfo(publicKeyBytes, out _);
                                isSignatureValid = ecdsa.VerifyData(cleanBytes, signatureBytes, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence);
                            }
                            catch (Exception ex)
                            {
                                Debug.WriteLine($"[PeerSync] Error al verificar firma remota: {ex.Message}");
                            }

                            if (!isSignatureValid)
                            {
                                Services.NetworkTelemetryService.Instance.RecordSignatureRejected();
                                Debug.WriteLine($"[PeerSync] Firma criptográfica inválida para el peer '{remoteId}', descartando.");
                                return;
                            }
                        }
                    }
                    else
                    {
                        Services.NetworkTelemetryService.Instance.RecordSignatureRejected();
                        Debug.WriteLine($"[PeerSync] Peer '{remoteId}' contiene firma vacía, descartando.");
                        return;
                    }
                }
                else
                {
                    Services.NetworkTelemetryService.Instance.RecordSignatureRejected();
                    Debug.WriteLine($"[PeerSync] Peer '{remoteId}' no firmado, descartando.");
                    return;
                }

                // ── Resolucion de conflictos (anti-replay + causalidad + autoria) ──
                if (!ResolveIncomingState(remoteId, root))
                {
                    return; // estado descartado por el resolvedor
                }

                // Escribir el peer en el directorio compartido
                var targetPath = Path.Combine(_peersDir, $"peer_{remoteId}.json");
                var tmpPath = targetPath + ".tmp";

                using (var fs = new FileStream(tmpPath, FileMode.Create, FileAccess.Write, FileShare.None))
                using (var sw = new StreamWriter(fs, Encoding.UTF8))
                    sw.Write(json);

                if (File.Exists(targetPath)) File.Delete(targetPath);
                File.Move(tmpPath, targetPath);

                Services.NetworkTelemetryService.Instance.RecordPeerSeen(remoteId);
                Debug.WriteLine($"[PeerSync] Peer remoto '{remoteId}' verificado y persistido desde {sourceIp} ({json.Length} chars)");
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

        private static byte[] ConvertHexToBytes(string hex)
        {
            byte[] bytes = new byte[hex.Length / 2];
            for (int i = 0; i < bytes.Length; i++)
            {
                bytes[i] = Convert.ToByte(hex.Substring(i * 2, 2), 16);
            }
            return bytes;
        }

        // ── Despacho de entrada: control (catch-up) vs estado normal ──────────
        /// <summary>
        /// Determina si el datagrama recibido es un mensaje de control del
        /// protocolo de catch-up (campo "_t") o un broadcast de estado normal,
        /// y lo encamina al handler correspondiente.
        /// </summary>
        private void DispatchIncoming(string json, IPEndPoint remoteEndpoint)
        {
            if (string.IsNullOrWhiteSpace(json)) return;

            string sourceIp = remoteEndpoint.Address.ToString();
            if (_rateLimiter.IsIpBlocked(sourceIp))
            {
                return;
            }

            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                string? messageType = Services.CatchupProtocol.GetMessageType(root);
                if (messageType != null)
                {
                    HandleControlMessage(messageType, root, remoteEndpoint);
                    return;
                }

                if (Services.HandshakeProtocol.LooksLikeHandshake(root))
                {
                    HandleHandshake(json, remoteEndpoint);
                    return;
                }
            }
            catch (JsonException)
            {
                Debug.WriteLine($"[PeerSync] JSON inválido recibido desde {sourceIp}, ignorado.");
                return;
            }

            ProcessReceivedPeer(json, sourceIp);
        }

        // ── Handlers del protocolo de catch-up ────────────────────────────────
        private void HandleControlMessage(string messageType, JsonElement root, IPEndPoint remoteEndpoint)
        {
            switch (messageType)
            {
                case Services.CatchupMessageType.Hello:
                    HandleHello(root, remoteEndpoint);
                    break;
                case Services.CatchupMessageType.SyncRequest:
                    HandleSyncRequest(root, remoteEndpoint);
                    break;
                case Services.CatchupMessageType.SyncResponse:
                    HandleSyncResponse(root, remoteEndpoint);
                    break;
                default:
                    Debug.WriteLine($"[PeerSync] Mensaje de control desconocido '{messageType}'.");
                    break;
            }
        }

        /// <summary>
        /// Al recibir un HELLO, si el reloj del peer indica que está más avanzado
        /// (o concurrente) le solicitamos un catch-up dirigido (unicast).
        /// </summary>
        private void HandleHello(JsonElement root, IPEndPoint remoteEndpoint)
        {
            string from = Services.CatchupProtocol.GetString(root, "from");
            if (string.IsNullOrEmpty(from) || from == _localId) return;

            _helloFromByIp[remoteEndpoint.Address.ToString()] = from;
            SendHandshakeUnicast(remoteEndpoint);

            var peerClock = Services.CatchupProtocol.ExtractClock(root);
            if (Services.CatchupProtocol.ShouldRequestCatchup(_localClock, peerClock))
            {
                string req = Services.CatchupProtocol.BuildSyncRequest(_localId, from, _localClock);
                SendUnicast(req, remoteEndpoint);
                Debug.WriteLine($"[PeerSync] Catch-up solicitado a '{from}' (peer más avanzado).");
            }
        }

        private void HandleHandshake(string json, IPEndPoint remoteEndpoint)
        {
            var result = Services.HandshakeProtocol.Validate(json);
            if (!result.IsValid || result.Envelope == null)
            {
                Debug.WriteLine($"[PeerSync] Handshake rechazado desde {remoteEndpoint.Address}: {result.Reason}");
                return;
            }

            string peerId = result.Envelope.SenderId;
            _trustedPeers[peerId] = 1;

            string sourceIp = remoteEndpoint.Address.ToString();
            if (_helloFromByIp.TryGetValue(sourceIp, out string? username) && !string.IsNullOrEmpty(username))
            {
                _trustedPeers[username] = 1;
            }

            Services.NetworkTelemetryService.Instance.RecordReconnection();
            Debug.WriteLine($"[PeerSync] Handshake OK con '{peerId}' desde {remoteEndpoint.Address}");

            SendHandshakeUnicast(remoteEndpoint);
        }

        private void SendHandshakeUnicast(IPEndPoint remoteEndpoint)
        {
            if (string.IsNullOrWhiteSpace(_walletAddress)) return;

            try
            {
                using var identity = VisorSingularity.Identity.NodeIdentity.LoadOrCreate();
                string envelope = Services.HandshakeProtocol.BuildResponse(
                    identity,
                    _walletAddress,
                    _walletSignature ?? "0x_simulated_signature_local");
                SendUnicast(envelope, remoteEndpoint);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error enviando handshake: {ex.Message}");
            }
        }

        /// <summary>
        /// Al recibir una solicitud dirigida a este nodo, respondemos con nuestro
        /// estado local firmado para que el peer atrasado reconcilie.
        /// </summary>
        private void HandleSyncRequest(JsonElement root, IPEndPoint remoteEndpoint)
        {
            string to = Services.CatchupProtocol.GetString(root, "to");
            if (to != _localId) return; // no es para nosotros

            string from = Services.CatchupProtocol.GetString(root, "from");
            string? signedState = BuildSignedLocalState();
            if (signedState == null) return;

            string resp = Services.CatchupProtocol.BuildSyncResponse(_localId, from, signedState);
            var bytes = Encoding.UTF8.GetBytes(resp);
            if (bytes.Length <= MAX_PACKET_BYTES)
            {
                SendUnicast(resp, remoteEndpoint);
                Debug.WriteLine($"[PeerSync] Catch-up respondido a '{from}'.");
            }
            else
            {
                Debug.WriteLine($"[PeerSync] Estado de catch-up demasiado grande ({bytes.Length} bytes), omitido.");
            }
        }

        /// <summary>
        /// Al recibir una respuesta de catch-up, extraemos el estado embebido y lo
        /// procesamos por la misma ruta de validación/resolución que un broadcast.
        /// </summary>
        private void HandleSyncResponse(JsonElement root, IPEndPoint remoteEndpoint)
        {
            string to = Services.CatchupProtocol.GetString(root, "to");
            if (to != _localId) return;

            string? embedded = Services.CatchupProtocol.ExtractEmbeddedState(root);
            if (embedded != null)
            {
                Services.NetworkTelemetryService.Instance.RecordReconnection();
                Debug.WriteLine("[PeerSync] Catch-up recibido, reconciliando estado.");
                ProcessReceivedPeer(embedded, remoteEndpoint.Address.ToString());
            }
        }

        // ── Envío dirigido (unicast) para el protocolo de catch-up ────────────
        private void SendUnicast(string message, IPEndPoint endpoint)
        {
            if (_disposed || _sender == null) return;
            try
            {
                var bytes = Encoding.UTF8.GetBytes(message);
                _sender.Send(bytes, bytes.Length, endpoint);
                Services.NetworkTelemetryService.Instance.RecordPacketSent(bytes.Length);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error en envío unicast: {ex.Message}");
            }
        }

        /// <summary>
        /// Lee el estado local del disco y le añade firma, seq y vector clock
        /// (sin avanzar el seq) para responder a una solicitud de catch-up.
        /// Reutiliza el formato firmado del broadcast normal.
        /// </summary>
        private string? BuildSignedLocalState()
        {
            if (!File.Exists(_localPeerPath)) return null;
            try
            {
                string json;
                using (var fs = new FileStream(_localPeerPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (var sr = new StreamReader(fs, Encoding.UTF8))
                    json = sr.ReadToEnd();

                if (string.IsNullOrWhiteSpace(json) || !json.TrimStart().StartsWith("{"))
                    return null;

                var node = JsonNode.Parse(json);
                if (node == null) return null;

                node.AsObject().Remove("sig");
                node.AsObject().Remove("pubkey");
                node.AsObject()["seq"] = System.Threading.Interlocked.Read(ref _localSeq);
                node.AsObject()["vc"] = JsonNode.Parse(_localClock.ToJson());

                string cleanJson = node.ToJsonString();
                byte[] cleanBytes = Encoding.UTF8.GetBytes(cleanJson);

                using var identity = VisorSingularity.Identity.NodeIdentity.LoadOrCreate();
                byte[] signatureBytes = identity.Sign(cleanBytes);
                node.AsObject()["sig"] = BitConverter.ToString(signatureBytes).Replace("-", "").ToLower();
                node.AsObject()["pubkey"] = BitConverter.ToString(identity.PublicKey).Replace("-", "").ToLower();

                return node.ToJsonString();
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PeerSync] Error construyendo estado firmado: {ex.Message}");
                return null;
            }
        }

        // ── Resolucion de conflictos del estado entrante ──────────────────────
        /// <summary>
        /// Aplica anti-replay (seq), causalidad (vector clock + LWW) y autoria de
        /// isla al estado recibido. Devuelve true si debe persistirse, false si se
        /// descarta. Mantiene compatibilidad con estados antiguos sin seq/vc.
        /// </summary>
        private bool ResolveIncomingState(string remoteId, JsonElement root)
        {
            long incomingSeq = Services.ConflictResolver.ExtractSeq(root);
            var incomingClock = Services.ConflictResolver.ExtractClock(root);
            long incomingTs = ExtractStateTimestamp(root);

            var decision = _conflictResolver.Resolve(
                remoteId, incomingSeq, incomingClock, _localClock,
                incomingTs, DateTimeOffset.UtcNow.ToUnixTimeMilliseconds());

            if (decision == Services.ResolutionDecision.IgnoreStale)
            {
                Debug.WriteLine($"[PeerSync] Estado de '{remoteId}' ignorado (replay/anterior).");
                return false;
            }
            if (decision == Services.ResolutionDecision.RejectConcurrentLose)
            {
                Debug.WriteLine($"[PeerSync] Conflicto concurrente con '{remoteId}' resuelto a favor local (LWW).");
                return false;
            }

            // Autoria de isla: solo el creador puede modificar datos estructurales.
            if (!ValidateIslandAuthorship(remoteId, root))
            {
                Services.NetworkTelemetryService.Instance.RecordInjectionAttempt();
                Debug.WriteLine($"[PeerSync] '{remoteId}' intento modificar una isla ajena, descartando.");
                return false;
            }

            return true;
        }

        /// <summary>
        /// Verifica que el peer es el autor de cada isla que declara en su bloque
        /// "i". Usa la wallet vinculada (campo "w" de la isla) o, en su defecto, el
        /// propio remoteId como clave de autoria.
        /// </summary>
        private bool ValidateIslandAuthorship(string remoteId, JsonElement root)
        {
            if (!root.TryGetProperty("i", out var islandsEl) ||
                islandsEl.ValueKind != JsonValueKind.Object)
            {
                return true; // sin islas que validar
            }

            foreach (var island in islandsEl.EnumerateObject())
            {
                string islandId = island.Name;
                string claimant = remoteId;
                if (island.Value.ValueKind == JsonValueKind.Object &&
                    island.Value.TryGetProperty("w", out var wEl) &&
                    wEl.ValueKind == JsonValueKind.String)
                {
                    claimant = wEl.GetString() ?? remoteId;
                }

                if (!_conflictResolver.IsIslandModificationAuthorized(islandId, claimant))
                {
                    return false;
                }
            }
            return true;
        }

        /// <summary>
        /// Obtiene un timestamp comparable del estado para el desempate LWW.
        /// Prioriza el campo "t" del primer usuario; si no existe usa 0.
        /// </summary>
        private static long ExtractStateTimestamp(JsonElement root)
        {
            if (root.TryGetProperty("u", out var usersEl) &&
                usersEl.ValueKind == JsonValueKind.Object)
            {
                foreach (var user in usersEl.EnumerateObject())
                {
                    if (user.Value.ValueKind == JsonValueKind.Object &&
                        user.Value.TryGetProperty("t", out var tEl) &&
                        tEl.ValueKind == JsonValueKind.Number &&
                        tEl.TryGetDouble(out double t))
                    {
                        return (long)(t * 1000); // segundos → ms
                    }
                    break;
                }
            }
            return 0;
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

                        if (peerT > 0 && now - peerT > PEER_INACTIVE_SECONDS)
                        {
                            _inactiveSince.TryAdd(peerId, now);
                        }

                        if (peerT > 0 && now - peerT > PEER_PURGE_SECONDS)
                        {
                            File.Delete(file);
                            _conflictResolver.ForgetPeer(peerId);
                            _rateLimiter.ForgetPeer(peerId);
                            _trustedPeers.TryRemove(peerId, out _);
                            _inactiveSince.TryRemove(peerId, out _);
                            Services.NetworkTelemetryService.Instance.RecordPeerExpired(peerId);
                            Debug.WriteLine($"[PeerSync] Peer purgado tras {PEER_PURGE_SECONDS}s sin actividad: {peerId}");
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

            try { _listener?.Close(); } catch { }
            try { _sender?.Close(); } catch { }

            try { _listenTask?.Wait(1000); } catch { }
            try { _heartbeatTask?.Wait(500); } catch { }

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
