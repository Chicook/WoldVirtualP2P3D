using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Services
{
    /// <summary>
    /// Presencia de la red P2P antes de entrar al mundo. Dos fuentes:
    /// la baliza UDP que el anfitrión emite cada 2 s (puerto 8912, la misma que
    /// escucha <c>Red.buscar_host_en_lan</c> en Godot) y el portal del enlace de
    /// invitado. Nunca abre el WebSocket del juego: un handshake real crearía un
    /// invitado fantasma en la sesión.
    /// </summary>
    public static class DescubrimientoP2P
    {
        public const int PuertoBeacon = 8912;
        public const int PuertoGodot = 8911;
        private const string MarcaBeacon = "WOLDVIRTUAL_HOST";

        public sealed class ResultadoLan
        {
            public List<string> Nodos { get; } = new();
            public Dictionary<string, int> Puertos { get; } = new(StringComparer.OrdinalIgnoreCase);
            public string? Error { get; set; }
        }

        /// <summary>Escucha la baliza UDP durante <paramref name="timeoutMs"/>.</summary>
        public static Task<ResultadoLan> BuscarEnLanAsync(
            int timeoutMs = 1600, CancellationToken ct = default, bool incluirPropio = false)
            => Task.Run(() => BuscarEnLan(timeoutMs, ct, incluirPropio), ct);

        private static ResultadoLan BuscarEnLan(int timeoutMs, CancellationToken ct, bool incluirPropio)
        {
            var res = new ResultadoLan();
            using var udp = new UdpClient(AddressFamily.InterNetwork);
            try
            {
                // El motor del mismo equipo puede tener el puerto si sigue vivo;
                // compartir la dirección permite escuchar sin cerrarle el socket.
                udp.Client.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
                udp.Client.Bind(new IPEndPoint(IPAddress.Any, PuertoBeacon));
            }
            catch (Exception ex)
            {
                res.Error = $"No se pudo escuchar el puerto {PuertoBeacon}: {ex.Message}";
                return res;
            }

            var propias = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "127.0.0.1" };
            try
            {
                foreach (var ip in Dns.GetHostAddresses(Dns.GetHostName()))
                    if (ip.AddressFamily == AddressFamily.InterNetwork) propias.Add(ip.ToString());
            }
            catch { }

            udp.Client.ReceiveTimeout = 200;
            var fin = DateTime.UtcNow.AddMilliseconds(Math.Max(300, timeoutMs));
            while (DateTime.UtcNow < fin && !ct.IsCancellationRequested)
            {
                try
                {
                    var origen = new IPEndPoint(IPAddress.Any, 0);
                    byte[] datos = udp.Receive(ref origen);
                    string mensaje = Encoding.UTF8.GetString(datos);
                    string ip = origen.Address.ToString();
                    if (!mensaje.StartsWith(MarcaBeacon, StringComparison.Ordinal)) continue;
                    if (!incluirPropio && propias.Contains(ip)) continue;

                    int puerto = PuertoGodot;
                    int idxWs = mensaje.IndexOf("_WS_", StringComparison.Ordinal);
                    if (idxWs > 0 && int.TryParse(mensaje.Substring(idxWs + 4).Trim(), out int p) && p > 0 && p <= 65535)
                    {
                        puerto = p;
                    }

                    res.Puertos[ip] = puerto;
                    if (!res.Nodos.Contains(ip)) res.Nodos.Add(ip);
                }
                catch (SocketException ex) when (ex.SocketErrorCode == SocketError.TimedOut)
                {
                    // ventana de escucha: seguir hasta agotar el tiempo
                }
                catch (SocketException)
                {
                    break;
                }
            }
            return res;
        }

        /// <summary>
        /// True si el nodo del enlace está en línea. Consulta
        /// <c>/api/p2p-status</c> de su portal, que es lectura pública y no
        /// revela más de lo que ya muestra su página.
        /// </summary>
        public static async Task<bool> ConsultarNodoAsync(string url, CancellationToken ct = default)
        {
            if (!TryConstruirEndpoint(url, out string endpoint)) return false;
            try
            {
                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(6) };
                string json = await http.GetStringAsync(endpoint, ct).ConfigureAwait(false);
                using var doc = JsonDocument.Parse(json);
                return doc.RootElement.TryGetProperty("online", out var online)
                       && online.ValueKind == JsonValueKind.True;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>
        /// Comprueba una entrada cualquiera: enlace de invitación (portal) o
        /// <c>ip:8911</c> de la red local (conexión TCP al WebSocket del motor).
        /// </summary>
        public static async Task<bool> SondearAsync(string entrada, CancellationToken ct = default)
        {
            string limpia = (entrada ?? "").Trim().Trim('"', '\'');
            if (limpia.Length == 0) return false;
            if (limpia.Contains("://"))
                return await ConsultarNodoAsync(limpia, ct).ConfigureAwait(false);

            if (TrySepararHostPuerto(limpia, out string host, out int puerto))
                return await TcpRespondeAsync(host, puerto, 2500, ct).ConfigureAwait(false);

            return await ConsultarNodoAsync("https://" + limpia, ct).ConfigureAwait(false);
        }

        private static bool TryConstruirEndpoint(string url, out string endpoint)
        {
            endpoint = "";
            string limpia = (url ?? "").Trim().Trim('"', '\'');
            if (limpia.Length == 0) return false;
            if (!Uri.TryCreate(limpia, UriKind.Absolute, out Uri? uri)) return false;
            if (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps) return false;
            endpoint = $"{uri.Scheme}://{uri.Authority}/api/p2p-status";
            return true;
        }

        private static bool TrySepararHostPuerto(string entrada, out string host, out int puerto)
        {
            host = entrada;
            puerto = PuertoGodot;
            if (string.IsNullOrWhiteSpace(entrada)) return false;

            int dosPuntos = entrada.LastIndexOf(':');
            if (dosPuntos > 0)
            {
                string resto = entrada[(dosPuntos + 1)..];
                if (int.TryParse(resto, out int p) && p > 0 && p <= 65535)
                {
                    host = entrada[..dosPuntos];
                    puerto = p;
                }
            }
            return !string.IsNullOrWhiteSpace(host);
        }

        private static async Task<bool> TcpRespondeAsync(string host, int puerto, int timeoutMs, CancellationToken ct)
        {
            try
            {
                using var tcp = new TcpClient();
                Task conexion = tcp.ConnectAsync(host, puerto, ct).AsTask();
                Task fin = await Task.WhenAny(conexion, Task.Delay(timeoutMs, ct)).ConfigureAwait(false);
                if (fin != conexion) return false;
                await conexion.ConfigureAwait(false);
                return tcp.Connected;
            }
            catch
            {
                return false;
            }
        }
    }
}
