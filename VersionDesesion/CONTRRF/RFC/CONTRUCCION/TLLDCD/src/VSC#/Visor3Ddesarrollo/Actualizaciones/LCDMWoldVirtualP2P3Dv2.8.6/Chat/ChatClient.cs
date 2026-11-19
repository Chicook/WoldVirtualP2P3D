using System;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Chat
{
    /// <summary>
    /// Cliente del chat: habla con el relay del anfitrión mediante WebSocket.
    /// Los eventos llegan desde el hilo de recepción; la interfaz debe marshalling
    /// a su Dispatcher.
    /// </summary>
    public sealed class ChatClient : IDisposable
    {
        private ClientWebSocket? _ws;
        private CancellationTokenSource? _cts;
        private readonly SemaphoreSlim _envio = new(1, 1);
        private int _avisoDesconexion;
        private int _suprimirAviso;
        private int _id;
        private volatile string _uid;
        private bool _disposed;

        public string Name { get; }
        public string Uid => _uid;
        public int MyId => Volatile.Read(ref _id);
        public string EndPoint { get; private set; } = "";
        public bool IsConnected => _ws?.State == WebSocketState.Open;

        public event Action<string>? Connected;
        public event Action<string>? Disconnected;
        public event Action<int, string, string>? TextReceived;
        public event Action<string>? SystemReceived;
        public event Action<int, string, bool, bool>? PeerState;
        public event Action<int, string, string>? PeerJoined;   // id, nombre, uid
        public event Action<int, string>? PeerLeft;             // id, uid
        public event Action<int, byte[], int>? MediaReceived;
        public event Action<string>? ErrorReceived;
        public event Action<string, string, string>? FriendRequestReceived; // uid, nombre, nota
        public event Action<string, string, string>? FriendRequestSent;     // uid, nombre, destino original
        public event Action<string, string>? FriendAccepted;                // uid, nombre
        public event Action<string, string>? FriendDeclined;                // uid, nombre
        public event Action<string, string>? FriendRequestFailed;           // destino, motivo
        public event Action<string, string, string, long>? DirectMessageReceived; // uid, nombre, texto, ts
        public event Action<string, string>? DirectMessageFailed;           // uid, motivo

        public ChatClient(string name, string uid = "")
        {
            Name = ChatProtocol.CleanName(name);
            string limpio = ChatProtocol.CleanUid(uid);
            _uid = limpio.Length > 0 ? limpio : ChatProtocol.BuildFallbackUid(Name);
        }

        public async Task<bool> ConnectAsync(string uri, CancellationToken exterior = default)
        {
            await CerrarSocketAsync(silencioso: true);
            Volatile.Write(ref _suprimirAviso, 0);

            var ws = new ClientWebSocket();
            ws.Options.KeepAliveInterval = TimeSpan.FromSeconds(15);
            Volatile.Write(ref _avisoDesconexion, 0);
            Volatile.Write(ref _id, -1);

            try
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(exterior);
                timeout.CancelAfter(TimeSpan.FromSeconds(6));
                await ws.ConnectAsync(new Uri(uri), timeout.Token);
            }
            catch
            {
                try { ws.Dispose(); } catch { }
                return false;
            }

            _ws = ws;
            EndPoint = uri;
            _cts = new CancellationTokenSource();
            _ = Task.Run(() => BucleRecepcionAsync(ws, _cts.Token));

            await EnviarJsonAsync(new { t = "hello", name = Name, uid = _uid }, _cts.Token);
            Connected?.Invoke(uri);
            return true;
        }

        public Task SendTextAsync(string text)
        {
            string limpio = ChatProtocol.CleanText(text);
            if (limpio.Length == 0) return Task.CompletedTask;
            return EnviarJsonAsync(new { t = "msg", text = limpio });
        }

        public Task SendFriendRequestAsync(string target, string note = "")
        {
            string destino = ChatProtocol.CleanUid(target);
            if (destino.Length == 0) return Task.CompletedTask;

            string limpio = ChatProtocol.CleanText(note);
            if (limpio.Length > ChatProtocol.MaxFriendNoteChars)
                limpio = limpio[..ChatProtocol.MaxFriendNoteChars];

            return EnviarJsonAsync(new { t = "friend_req", to = destino, text = limpio });
        }

        public Task SendFriendResponseAsync(string uid, bool accept)
        {
            string destino = ChatProtocol.CleanUid(uid);
            if (destino.Length == 0) return Task.CompletedTask;
            return EnviarJsonAsync(new { t = accept ? "friend_ok" : "friend_no", to = destino });
        }

        public Task SendDirectAsync(string uid, string text)
        {
            string destino = ChatProtocol.CleanUid(uid);
            string limpio = ChatProtocol.CleanText(text);
            if (destino.Length == 0 || limpio.Length == 0) return Task.CompletedTask;
            return EnviarJsonAsync(new { t = "dm", to = destino, text = limpio });
        }

        public Task SendStateAsync(bool audio, bool video)
        {
            return EnviarJsonAsync(new { t = "state", audio, video });
        }

        public Task SendMediaAsync(int kind, byte[] payload)
        {
            if (payload == null || payload.Length == 0) return Task.CompletedTask;
            byte[] frame = ChatProtocol.BuildClientFrame(kind, payload);
            return EnviarFrameAsync(WebSocketMessageType.Binary, frame);
        }

        private Task EnviarJsonAsync(object payload, CancellationToken ct = default)
        {
            byte[] bytes = ChatProtocol.TextFrame(payload);
            return EnviarFrameAsync(WebSocketMessageType.Text, bytes, ct);
        }

        private async Task EnviarFrameAsync(WebSocketMessageType tipo, byte[] datos, CancellationToken ct = default)
        {
            var ws = _ws;
            if (ws == null || ws.State != WebSocketState.Open) return;

            try { await _envio.WaitAsync(ct); }
            catch { return; }

            try
            {
                if (ws.State != WebSocketState.Open) return;
                await ws.SendAsync(new ArraySegment<byte>(datos), tipo, true, ct);
            }
            catch
            {
                // La caída se notifica desde el bucle de recepción.
            }
            finally
            {
                try { _envio.Release(); } catch { }
            }
        }

        private async Task BucleRecepcionAsync(ClientWebSocket ws, CancellationToken ct)
        {
            byte[] buffer = new byte[16 * 1024];
            using var acumulado = new MemoryStream();
            string motivo = "Conexión cerrada";

            try
            {
                while (!ct.IsCancellationRequested && ws.State == WebSocketState.Open)
                {
                    WebSocketReceiveResult resultado;
                    try
                    {
                        resultado = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), ct);
                    }
                    catch (OperationCanceledException) { motivo = "Conexión cerrada"; break; }
                    catch (Exception ex) { motivo = ex.Message; break; }

                    if (resultado.MessageType == WebSocketMessageType.Close)
                    {
                        motivo = "El anfitrión cerró el chat";
                        break;
                    }

                    acumulado.Write(buffer, 0, resultado.Count);
                    if (acumulado.Length > ChatProtocol.MaxFrameBytes + 64)
                    {
                        motivo = "Trama demasiado grande";
                        break;
                    }

                    if (!resultado.EndOfMessage) continue;

                    byte[] datos = acumulado.ToArray();
                    acumulado.SetLength(0);

                    if (resultado.MessageType == WebSocketMessageType.Text)
                        ProcesarTexto(datos);
                    else if (resultado.MessageType == WebSocketMessageType.Binary)
                        ProcesarBinario(datos);
                }
            }
            finally
            {
                if (Volatile.Read(ref _suprimirAviso) == 0 &&
                    Interlocked.Exchange(ref _avisoDesconexion, 1) == 0)
                    Disconnected?.Invoke(motivo);
            }
        }

        private static string LeerCadena(JsonElement raiz, string campo)
            => raiz.TryGetProperty(campo, out var prop) ? prop.GetString() ?? "" : "";

        private void ProcesarTexto(byte[] datos)
        {
            try
            {
                using var doc = JsonDocument.Parse(datos);
                var raiz = doc.RootElement;
                if (!raiz.TryGetProperty("t", out var tProp)) return;
                string tipo = tProp.GetString() ?? "";

                switch (tipo)
                {
                    case "welcome":
                        if (raiz.TryGetProperty("id", out var idProp))
                            Volatile.Write(ref _id, idProp.GetInt32());
                        string uidPropio = ChatProtocol.CleanUid(LeerCadena(raiz, "uid"));
                        if (uidPropio.Length > 0) _uid = uidPropio;
                        if (raiz.TryGetProperty("peers", out var pares) && pares.ValueKind == JsonValueKind.Array)
                        {
                            foreach (var par in pares.EnumerateArray())
                            {
                                int pid = par.TryGetProperty("id", out var p) ? p.GetInt32() : -1;
                                string pnombre = par.TryGetProperty("name", out var n) ? (n.GetString() ?? "") : "";
                                string puid = ChatProtocol.CleanUid(
                                    par.TryGetProperty("uid", out var pu) ? pu.GetString() : "");
                                if (pid > 0) PeerJoined?.Invoke(pid, pnombre, puid);
                            }
                        }
                        break;

                    case "join":
                        if (raiz.TryGetProperty("id", out var joinId) && joinId.GetInt32() > 0)
                        {
                            PeerJoined?.Invoke(
                                joinId.GetInt32(),
                                LeerCadena(raiz, "name"),
                                ChatProtocol.CleanUid(LeerCadena(raiz, "uid")));
                        }
                        break;

                    case "msg":
                        TextReceived?.Invoke(
                            raiz.TryGetProperty("id", out var mid) ? mid.GetInt32() : 0,
                            raiz.TryGetProperty("name", out var mn) ? (mn.GetString() ?? "") : "",
                            raiz.TryGetProperty("text", out var mt) ? (mt.GetString() ?? "") : "");
                        break;

                    case "sys":
                        SystemReceived?.Invoke(
                            raiz.TryGetProperty("text", out var st) ? (st.GetString() ?? "") : "");
                        break;

                    case "bye":
                        if (raiz.TryGetProperty("id", out var byeId))
                            PeerLeft?.Invoke(
                                byeId.GetInt32(),
                                ChatProtocol.CleanUid(LeerCadena(raiz, "uid")));
                        break;

                    case "state":
                        PeerState?.Invoke(
                            raiz.TryGetProperty("id", out var sid) ? sid.GetInt32() : 0,
                            raiz.TryGetProperty("name", out var sn) ? (sn.GetString() ?? "") : "",
                            raiz.TryGetProperty("audio", out var sa) && sa.ValueKind == JsonValueKind.True,
                            raiz.TryGetProperty("video", out var sv) && sv.ValueKind == JsonValueKind.True);
                        break;

                    case "error":
                        ErrorReceived?.Invoke(
                            raiz.TryGetProperty("text", out var et) ? (et.GetString() ?? "") : "Error del chat");
                        break;

                    case "friend_req":
                        FriendRequestReceived?.Invoke(
                            ChatProtocol.CleanUid(LeerCadena(raiz, "from")),
                            LeerCadena(raiz, "fromName"),
                            LeerCadena(raiz, "text"));
                        break;

                    case "friend_sent":
                        FriendRequestSent?.Invoke(
                            ChatProtocol.CleanUid(LeerCadena(raiz, "uid")),
                            LeerCadena(raiz, "name"),
                            ChatProtocol.CleanUid(LeerCadena(raiz, "to")));
                        break;

                    case "friend_ok":
                        FriendAccepted?.Invoke(
                            ChatProtocol.CleanUid(LeerCadena(raiz, "from")),
                            LeerCadena(raiz, "fromName"));
                        break;

                    case "friend_no":
                        FriendDeclined?.Invoke(
                            ChatProtocol.CleanUid(LeerCadena(raiz, "from")),
                            LeerCadena(raiz, "fromName"));
                        break;

                    case "friend_fail":
                        FriendRequestFailed?.Invoke(
                            ChatProtocol.CleanUid(LeerCadena(raiz, "to")),
                            LeerCadena(raiz, "reason"));
                        break;

                    case "dm":
                        DirectMessageReceived?.Invoke(
                            ChatProtocol.CleanUid(LeerCadena(raiz, "from")),
                            LeerCadena(raiz, "fromName"),
                            LeerCadena(raiz, "text"),
                            raiz.TryGetProperty("ts", out var tsProp) ? tsProp.GetInt64() : 0);
                        break;

                    case "dm_fail":
                        DirectMessageFailed?.Invoke(
                            ChatProtocol.CleanUid(LeerCadena(raiz, "to")),
                            LeerCadena(raiz, "reason"));
                        break;
                }
            }
            catch (JsonException) { }
        }

        private void ProcesarBinario(byte[] datos)
        {
            if (!ChatProtocol.TryReadServerFrame(datos, out int kind, out int emisor, out int offset)) return;
            int tam = datos.Length - offset;
            if (tam <= 0) return;

            byte[] payload = new byte[tam];
            Buffer.BlockCopy(datos, offset, payload, 0, tam);
            MediaReceived?.Invoke(kind, payload, emisor);
        }

        private async Task CerrarSocketAsync(bool silencioso)
        {
            var cts = _cts;
            var ws = _ws;
            _cts = null;
            _ws = null;

            if (silencioso) Interlocked.Exchange(ref _suprimirAviso, 1);
            try { cts?.Cancel(); } catch { }

            if (ws != null)
            {
                try
                {
                    if (ws.State == WebSocketState.Open)
                    {
                        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(1));
                        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "bye", timeout.Token);
                    }
                }
                catch { }
                try { ws.Dispose(); } catch { }
            }

            cts?.Dispose();
            if (!silencioso && EndPoint.Length > 0 && Interlocked.Exchange(ref _avisoDesconexion, 1) == 0)
                Disconnected?.Invoke("Chat desconectado");
        }

        public Task CloseAsync() => CerrarSocketAsync(silencioso: false);

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            _ = CerrarSocketAsync(silencioso: true);
            _envio.Dispose();
        }
    }
}
