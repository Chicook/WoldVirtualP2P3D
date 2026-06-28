using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity
{
    /// <summary>
    /// Transporte WAN de estados de avatares vía IPFS PubSub (GossipSub).
    /// 
    /// Permite la sincronización multijugador global sin modificar el código de Godot:
    ///   - Publicación: Lee el peer JSON local del disco y lo publica en el topic global.
    ///   - Suscripción: Recibe estados de peers remotos del topic global y los escribe en
    ///     la carpeta Estado_Global/peers/ para que NetworkLayer.gd los integre automáticamente.
    ///
    /// Topic IPFS: /wcv/metaverse/state/v1
    /// Modo: Proceso streaming con 'ipfs pubsub sub --encoding=json' vía HTTP API de Kubo.
    /// </summary>
    public sealed class IpfsPubSubTransport : IDisposable
    {
        // ─── Topic Global del Metaverso ───────────────────────────────────────
        public const string Topic = "/wcv/metaverse/state/v1";

        // ─── URL de la API HTTP de Kubo ───────────────────────────────────────
        private const string KuboApiBase = "http://127.0.0.1:5001/api/v0";

        // ─── Límites de seguridad ─────────────────────────────────────────────
        private const int MAX_MESSAGE_BYTES   = PeerSchema.MaxPeerSizeBytes;  // 64 KB máximo por mensaje
        private const int MAX_PEERS_ON_DISK   = PeerSchema.MaxPeersOnDisk;    // cuota máxima de peers en disco
        private const int PUBLISH_INTERVAL_MS = 3000;   // publicar estado local cada 3 s
        private const int RECONNECT_BASE_MS   = 1000;   // backoff exponencial inicial
        private const int RECONNECT_MAX_MS    = 30000;  // techo del backoff exponencial

        // ─── Estado ───────────────────────────────────────────────────────────
        private readonly string _peersDir;
        private readonly string _localId;
        private readonly string _localPeerPath;
        private readonly IpfsManager _ipfs;

        private CancellationTokenSource _cts = new();
        private Task? _subscribeTask;
        private Task? _publishTask;
        private bool _disposed;

        // ─── Eventos ──────────────────────────────────────────────────────────
        /// <summary>Se dispara cuando se recibe y valida el estado de un peer remoto (id, json).</summary>
        public event Action<string, string>? PeerReceived;

        /// <summary>Se dispara cuando se produce un cambio en el estado del transporte.</summary>
        public event Action<string>? OnStatusChanged;

        // ─── Constructor ──────────────────────────────────────────────────────
        public IpfsPubSubTransport(string peersDir, string localId, IpfsManager ipfs)
        {
            _peersDir      = peersDir;
            _localId       = localId;
            _localPeerPath = Path.Combine(peersDir, $"peer_{localId}.json");
            _ipfs          = ipfs;
        }

        // ─── Arranque ─────────────────────────────────────────────────────────
        /// <summary>
        /// Inicia los loops de suscripción WAN y publicación periódica en paralelo.
        /// Llama a Start() después de que IpfsManager.EnsureReadyAsync() haya tenido éxito.
        /// </summary>
        public void Start()
        {
            if (_disposed) return;

            // Renovar CTS por si se llamó Stop() y luego Start() de nuevo
            _cts = new CancellationTokenSource();

            _subscribeTask = Task.Run(() => SubscribeLoopAsync(_cts.Token));
            _publishTask   = Task.Run(() => PublishLoopAsync(_cts.Token));

            LogStatus("🌍 [PubSub] Transporte WAN iniciado.");
            Debug.WriteLine($"[PubSub] Suscripción al topic: {Topic}");
        }

        // ─── Publicación Periódica ────────────────────────────────────────────
        /// <summary>Publica el estado del peer local en el topic global cada PUBLISH_INTERVAL_MS.</summary>
        private async Task PublishLoopAsync(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    await Task.Delay(PUBLISH_INTERVAL_MS, token);
                    await PublishLocalPeerAsync(token);
                }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[PubSub] Error en PublishLoopAsync: {ex.Message}");
                }
            }
        }

        /// <summary>
        /// Publica el JSON del peer local en el topic IPFS PubSub.
        /// Usa la HTTP API de Kubo: POST /api/v0/pubsub/pub
        /// </summary>
        public async Task PublishLocalPeerAsync(CancellationToken token = default)
        {
            if (!File.Exists(_localPeerPath)) return;

            try
            {
                string json;
                using (var fs = new FileStream(_localPeerPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (var sr = new StreamReader(fs, Encoding.UTF8))
                    json = await sr.ReadToEndAsync();

                if (string.IsNullOrWhiteSpace(json) || !json.TrimStart().StartsWith("{")) return;

                var identity = NodeIdentityService.GetOrCreate();
                if (_localId == identity.PeerId && PeerAuth.TrySignOutgoing(json, identity, out var signed))
                    json = signed;

                var payload = Encoding.UTF8.GetBytes(json);
                if (payload.Length > MAX_MESSAGE_BYTES)
                {
                    Debug.WriteLine($"[PubSub] Peer local excede el límite ({payload.Length} bytes), publicación omitida.");
                    return;
                }

                // POST multipart/form-data con el payload al endpoint de publicación de Kubo
                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(8) };
                using var content = new MultipartFormDataContent();
                using var byteContent = new ByteArrayContent(payload);
                content.Add(byteContent, "data");

                string encodedTopic = Uri.EscapeDataString(Topic);
                var response = await http.PostAsync($"{KuboApiBase}/pubsub/pub?arg={encodedTopic}", content, token);

                if (response.IsSuccessStatusCode)
                    Debug.WriteLine($"[PubSub] Estado local publicado ({payload.Length} bytes) → {Topic}");
                else
                    Debug.WriteLine($"[PubSub] Error al publicar: HTTP {(int)response.StatusCode}");
            }
            catch (OperationCanceledException) { }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PubSub] Error al publicar peer local: {ex.Message}");
            }
        }

        // ─── Suscripción con Reconexión Automática ────────────────────────────
        /// <summary>
        /// Loop de suscripción con backoff exponencial. El daemon Kubo expone un stream NDJSON
        /// (Newline-Delimited JSON) en /api/v0/pubsub/sub que devuelve un mensaje por línea.
        /// </summary>
        private async Task SubscribeLoopAsync(CancellationToken token)
        {
            int delay = RECONNECT_BASE_MS;

            while (!token.IsCancellationRequested)
            {
                try
                {
                    await ConnectAndSubscribeAsync(token);
                    // Si ConnectAndSubscribeAsync retorna limpiamente (no por excepción), es una desconexión normal
                    delay = RECONNECT_BASE_MS; // reset backoff al reconectar exitosamente
                }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[PubSub] Suscripción interrumpida: {ex.Message}. Reconectando en {delay}ms...");
                    LogStatus($"⚠️ [PubSub] Reconectando en {delay / 1000}s...");
                }

                if (token.IsCancellationRequested) break;

                await Task.Delay(delay, token).ConfigureAwait(false);
                delay = Math.Min(delay * 2, RECONNECT_MAX_MS); // backoff exponencial
            }
        }

        /// <summary>
        /// Establece una conexión de streaming con la API PubSub de Kubo y procesa
        /// los mensajes NDJSON línea a línea hasta que se cancela la operación.
        /// </summary>
        private async Task ConnectAndSubscribeAsync(CancellationToken token)
        {
            using var http = new HttpClient();
            http.Timeout = Timeout.InfiniteTimeSpan; // stream de larga duración

            string encodedTopic = Uri.EscapeDataString(Topic);
            string url          = $"{KuboApiBase}/pubsub/sub?arg={encodedTopic}&encoding=json";

            LogStatus("🔗 [PubSub] Conectando al stream de estados WAN...");

            using var request  = new HttpRequestMessage(HttpMethod.Post, url);
            using var response = await http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, token);

            response.EnsureSuccessStatusCode();
            LogStatus("✅ [PubSub] Suscrito al metaverso global.");

            using var stream = await response.Content.ReadAsStreamAsync(token);
            using var reader = new StreamReader(stream, Encoding.UTF8);

            while (!token.IsCancellationRequested)
            {
                string? line = await reader.ReadLineAsync(token);
                if (line == null) break; // stream cerrado por el servidor

                if (!string.IsNullOrWhiteSpace(line))
                    ProcessPubSubMessage(line);
            }
        }

        // ─── Procesamiento de Mensajes ────────────────────────────────────────
        /// <summary>
        /// Decodifica el sobre PubSub de Kubo (base64), extrae el peer JSON y lo
        /// escribe en el directorio de peers de Godot si supera la validación.
        /// </summary>
        private void ProcessPubSubMessage(string rawLine)
        {
            try
            {
                using var envelope = JsonDocument.Parse(rawLine);
                var root = envelope.RootElement;

                // El campo "data" en la respuesta de Kubo está en Base64
                if (!root.TryGetProperty("data", out var dataEl)) return;
                string? base64Data = dataEl.GetString();
                if (string.IsNullOrEmpty(base64Data)) return;

                byte[] decoded = Convert.FromBase64String(base64Data);
                if (decoded.Length > MAX_MESSAGE_BYTES)
                {
                    Debug.WriteLine($"[PubSub] Mensaje recibido excede el límite ({decoded.Length} bytes), descartado.");
                    return;
                }

                string peerJson = Encoding.UTF8.GetString(decoded);
                ValidateAndSavePeer(peerJson);
            }
            catch (JsonException ex)
            {
                Debug.WriteLine($"[PubSub] Sobre PubSub con JSON inválido, ignorado: {ex.Message}");
            }
            catch (FormatException ex)
            {
                Debug.WriteLine($"[PubSub] Error decodificando Base64 del sobre PubSub: {ex.Message}");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PubSub] Error procesando mensaje: {ex.Message}");
            }
        }

        // ─── Validación y Escritura ───────────────────────────────────────────
        /// <summary>
        /// Pipeline de validación centralizado usando PeerSchema antes de escribir en disco:
        /// 1. JSON válido y con estructura mínima esperada.
        /// 2. Sanitización estricta del ID para prevenir Path Traversal.
        /// 3. Ignorar mensajes propios.
        /// 4. Cuota máxima de peers en disco.
        /// </summary>
        private void ValidateAndSavePeer(string peerJson)
        {
            try
            {
                if (!PeerAuth.TryValidateIncoming(peerJson, _localId, out string remoteId))
                {
                    Debug.WriteLine("[PubSub] JSON de peer inválido/no firmado, ignorado.");
                    return;
                }

                if (remoteId == _localId) return;

                // Cuota de disco: no aceptar más de MAX_PEERS_ON_DISK peers
                var existingFiles = Directory.GetFiles(_peersDir, "peer_*.json");
                if (existingFiles.Length >= MAX_PEERS_ON_DISK)
                {
                    Debug.WriteLine($"[PubSub] Cuota de peers en disco alcanzada ({MAX_PEERS_ON_DISK}). Descartando peer '{remoteId}'.");
                    return;
                }

                // Escritura atómica: escribir en .tmp y luego renombrar
                string targetPath = Path.Combine(_peersDir, PeerSchema.GetPeerFileName(remoteId));
                string tmpPath    = targetPath + ".tmp";

                using (var fs = new FileStream(tmpPath, FileMode.Create, FileAccess.Write, FileShare.None))
                using (var sw = new StreamWriter(fs, Encoding.UTF8))
                    sw.Write(peerJson);

                if (File.Exists(targetPath)) File.Delete(targetPath);
                File.Move(tmpPath, targetPath);

                Debug.WriteLine($"[PubSub] ✅ Peer WAN guardado: '{remoteId}' ({peerJson.Length} chars)");
                PeerReceived?.Invoke(remoteId, peerJson);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PubSub] Error al guardar peer: {ex.Message}");
            }
        }

        // ─── Helpers ──────────────────────────────────────────────────────────
        private static string ExtractRemoteId(JsonElement root)
        {
            if (root.TryGetProperty("u", out var usersEl) && usersEl.ValueKind == JsonValueKind.Object)
                foreach (var prop in usersEl.EnumerateObject())
                    return prop.Name;

            if (root.TryGetProperty("i", out var islandsEl) && islandsEl.ValueKind == JsonValueKind.Object)
                foreach (var prop in islandsEl.EnumerateObject())
                    return prop.Name;

            return string.Empty;
        }

        /// <summary>
        /// Valida que el ID de un peer solo contenga caracteres seguros y no sea
        /// susceptible a Path Traversal. Permitidos: alfanumérico, '-', '_', ':', '.'
        /// </summary>
        private static bool IsValidPeerId(string id)
        {
            if (id.Contains("..") || id.Contains("/") || id.Contains("\\")) return false;
            if (id.Length > 128) return false; // límite razonable de longitud

            foreach (char c in id)
                if (!char.IsLetterOrDigit(c) && c != '-' && c != '_' && c != ':' && c != '.')
                    return false;

            return true;
        }

        private void LogStatus(string msg) => OnStatusChanged?.Invoke(msg);

        // ─── Parada y Limpieza ────────────────────────────────────────────────
        public void Stop()
        {
            if (_disposed) return;
            _cts.Cancel();
            try { _subscribeTask?.Wait(2000); } catch { }
            try { _publishTask?.Wait(1000); } catch { }
            LogStatus("⏹ [PubSub] Transporte WAN detenido.");
            Debug.WriteLine("[PubSub] Transporte detenido.");
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            Stop();
            _cts.Dispose();
        }
    }
}
