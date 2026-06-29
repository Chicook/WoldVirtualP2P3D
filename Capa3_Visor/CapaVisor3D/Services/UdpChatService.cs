using System;
using System.Diagnostics;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Mensaje de chat recibido desde Godot via UDP (puerto 50008).
    /// </summary>
    public record UdpChatMessage(string User, string Text, bool IsSystem);

    /// <summary>
    /// Gestiona el socket UDP de chat de proximidad en el puerto 50008.
    /// Notifica mediante el evento MessageReceived.
    /// </summary>
    public sealed class UdpChatService : IDisposable
    {
        private const int ChatPort = 50008;

        private UdpClient? _udpClient;
        private CancellationTokenSource? _cts;
        private bool _disposed;

        public event Action<UdpChatMessage>? MessageReceived;

        public void Start()
        {
            Stop();
            _cts = new CancellationTokenSource();
            var token = _cts.Token;
            try
            {
                _udpClient = new UdpClient(ChatPort);
                Task.Run(() => ListenLoopAsync(token), token);
                Debug.WriteLine($"[UdpChatService] Escuchando en puerto {ChatPort}");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[UdpChatService] Error al abrir puerto {ChatPort}: {ex.Message}");
            }
        }

        public void Stop()
        {
            if (_cts != null) { _cts.Cancel(); _cts.Dispose(); _cts = null; }
            if (_udpClient != null) { _udpClient.Close(); _udpClient = null; }
        }

        private async Task ListenLoopAsync(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    var result  = await _udpClient!.ReceiveAsync();
                    string json = Encoding.UTF8.GetString(result.Buffer);
                    ProcessMessage(json);
                }
                catch (ObjectDisposedException) { break; }
                catch (Exception ex) { Debug.WriteLine($"[UdpChatService] Error al recibir: {ex.Message}"); }
            }
        }

        private void ProcessMessage(string jsonStr)
        {
            try
            {
                using var doc = JsonDocument.Parse(jsonStr);
                var root      = doc.RootElement;
                if (!root.TryGetProperty("type", out var typeProp)) return;
                string type = typeProp.GetString() ?? string.Empty;

                if (type == "chat")
                {
                    string user = root.TryGetProperty("user", out var u) ? u.GetString() ?? "Anonymous" : "Anonymous";
                    string text = root.TryGetProperty("text", out var t) ? t.GetString() ?? "" : "";
                    MessageReceived?.Invoke(new UdpChatMessage(user, text, false));
                }
                else if (type == "system")
                {
                    string text = root.TryGetProperty("text", out var t) ? t.GetString() ?? "" : "";
                    MessageReceived?.Invoke(new UdpChatMessage("", text, true));
                }
            }
            catch (Exception ex) { Debug.WriteLine($"[UdpChatService] Error parseo: {ex.Message}"); }
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            Stop();
        }
    }
}
