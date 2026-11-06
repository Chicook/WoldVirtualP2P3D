using System;
using System.Net;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Services
{
    /// <summary>
    /// Pieza de proxy WebSocket del WebNodo: une el handshake aceptado por el
    /// HttpListener con el destino interno (motor Godot en 8911 o relay de chat)
    /// y copia tramas en ambos sentidos hasta que uno de los dos cierra.
    /// Quién decide el destino, y con qué credencial, es asunto del router
    /// (<c>WebNodoService.PortalHttp.cs</c>); aquí solo se transportan bytes.
    /// </summary>
    public partial class WebNodoService
    {
        private async Task ProxyWebSocketAsync(HttpListenerContext ctx, string destino)
        {
            try
            {
                var wsContext = await ctx.AcceptWebSocketAsync(null);
                var clientWs = wsContext.WebSocket;

                using var serverWs = new System.Net.WebSockets.ClientWebSocket();
                await serverWs.ConnectAsync(new Uri(destino), CancellationToken.None);

                var clientToRemote = Task.Run(async () =>
                {
                    byte[] buffer = new byte[8192];
                    while (clientWs.State == System.Net.WebSockets.WebSocketState.Open && serverWs.State == System.Net.WebSockets.WebSocketState.Open)
                    {
                        var res = await clientWs.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
                        if (res.MessageType == System.Net.WebSockets.WebSocketMessageType.Close) break;
                        await serverWs.SendAsync(new ArraySegment<byte>(buffer, 0, res.Count), res.MessageType, res.EndOfMessage, CancellationToken.None);
                    }
                });

                var remoteToClient = Task.Run(async () =>
                {
                    byte[] buffer = new byte[8192];
                    while (clientWs.State == System.Net.WebSockets.WebSocketState.Open && serverWs.State == System.Net.WebSockets.WebSocketState.Open)
                    {
                        var res = await serverWs.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
                        if (res.MessageType == System.Net.WebSockets.WebSocketMessageType.Close) break;
                        await clientWs.SendAsync(new ArraySegment<byte>(buffer, 0, res.Count), res.MessageType, res.EndOfMessage, CancellationToken.None);
                    }
                });

                await Task.WhenAny(clientToRemote, remoteToClient);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[WebNodo-WSProxy] Error: {ex.Message}");
            }
            finally
            {
                ctx.Response.Close();
            }
        }
    }
}
