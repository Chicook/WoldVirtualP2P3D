using System;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Services
{
    /// <summary>
    /// Pieza de proxy TCP del WebNodo. El visor enlaza un TcpListener en el puerto
    /// público y otro HttpListener en el interno (puerto+100); el proxy reenvía la
    /// petición cabecera a cabecera y es el ÚNICO que puede estampar el marcador de
    /// confianza que autoriza a leer un X-Forwarded-For (hallazgo H2).
    /// </summary>
    public partial class WebNodoService
    {
        // El proxy conecta a IPAddress.Loopback, así que reescribe el Host a esa
        // misma IP: el HttpListener gestionado de .NET en Linux empareja el prefijo
        // por la IP del endpoint y el Host de forma literal, y con «localhost»
        // (que allí resuelve a ::1) devuelve 404 en lugar de atender la petición.
        private const string HostInterno = "127.0.0.1";

        // Marcador de proxy de confianza (H2): cabecera que solo puede escribir
        // este proxy TCP al reenviar hacia el HttpListener interno. El valor es
        // aleatorio por proceso, vive solo en memoria, nunca sale del equipo y
        // no consta en el repositorio: sin este marcador, ObtenerIpCliente no
        // debe fiarse de X-Forwarded-For ni de CF-Connecting-IP.
        internal const string CabeceraMarcadorProxy = "X-Wold-Proxy";
        private static readonly string _valorMarcadorProxy =
            Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant();

        // Cabeceras que un cliente puede intentar suplantar y que el proxy
        // siempre elimina antes de escribir las suyas.
        private static readonly Regex _cabecerasSuplantables = new(
            @"(?:\r\n|\n)[ \t]*(?:X-Forwarded-For|CF-Connecting-IP|X-Wold-Proxy)[ \t]*:[^\r\n]*",
            RegexOptions.IgnoreCase);

        /// <summary>
        /// Verdadero solo si el valor recibido es el marcador que este mismo
        /// proceso generó al arrancar. Comparación en tiempo fijo.
        /// </summary>
        internal static bool EsMarcadorProxyValido(string? valor)
        {
            if (string.IsNullOrEmpty(valor)) return false;
            var recibido = Encoding.UTF8.GetBytes(valor.Trim());
            var esperado = Encoding.UTF8.GetBytes(_valorMarcadorProxy);
            return recibido.Length == esperado.Length &&
                   CryptographicOperations.FixedTimeEquals(recibido, esperado);
        }

        private async Task ProxyLoop(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    TcpListener? pl;
                    lock (_lock) { pl = _proxyListener; }
                    if (pl == null) break;

                    TcpClient client = await pl.AcceptTcpClientAsync(token).ConfigureAwait(false);
                    _ = Task.Run(() => HandleProxyClientAsync(client, token), token);
                }
                catch (ObjectDisposedException) { break; }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"[WebNodo-Proxy] Error accept: {ex.Message}");
                }
            }
        }

        private async Task HandleProxyClientAsync(TcpClient client, CancellationToken token)
        {
            using (client)
            {
                client.NoDelay = true;
                using var target = new TcpClient();
                try
                {
                    await target.ConnectAsync(IPAddress.Loopback, _internalPort, token).ConfigureAwait(false);
                    target.NoDelay = true;

                    // IP real observada en el socket aceptado: es la única que
                    // el proxy declara como IP del cliente al reenviar.
                    string? ipRealProxy = null;
                    try
                    {
                        var direccion = (client.Client.RemoteEndPoint as IPEndPoint)?.Address;
                        if (direccion != null && direccion.IsIPv4MappedToIPv6)
                            direccion = direccion.MapToIPv4();
                        ipRealProxy = direccion?.ToString();
                    }
                    catch { }

                    using NetworkStream clientStream = client.GetStream();
                    using NetworkStream targetStream = target.GetStream();

                    byte[] buffer = new byte[8192];
                    int bytesRead = 0;
                    using var ms = new MemoryStream();

                    while (true)
                    {
                        int read = await clientStream.ReadAsync(buffer, 0, buffer.Length, token).ConfigureAwait(false);
                        if (read <= 0) break;
                        ms.Write(buffer, 0, read);
                        bytesRead += read;

                        byte[] currentBytes = ms.ToArray();
                        if (FindBytes(currentBytes, new byte[] { 13, 10, 13, 10 }) != -1 || bytesRead > 16384)
                        {
                            break;
                        }
                    }

                    byte[] requestBytes = ms.ToArray();
                    if (requestBytes.Length > 0)
                    {
                        byte[] separator = new byte[] { 13, 10, 13, 10 };
                        int headerEndIdx = FindBytes(requestBytes, separator);

                        if (headerEndIdx >= 0)
                        {
                            string headersStr = Encoding.UTF8.GetString(requestBytes, 0, headerEndIdx);
                            var hostRegex = new Regex(@"\r\nHost:\s*[^\r\n]+", RegexOptions.IgnoreCase);

                            if (hostRegex.IsMatch(headersStr))
                            {
                                headersStr = hostRegex.Replace(headersStr, $"\r\nHost: {HostInterno}:{_internalPort}");
                            }
                            else
                            {
                                headersStr += $"\r\nHost: {HostInterno}:{_internalPort}";
                            }

                            headersStr = ReescribirCabecerasDelProxy(headersStr, ipRealProxy);
                            byte[] headerBytes = Encoding.UTF8.GetBytes(headersStr);
                            await targetStream.WriteAsync(headerBytes, 0, headerBytes.Length, token).ConfigureAwait(false);
                            await targetStream.WriteAsync(separator, 0, separator.Length, token).ConfigureAwait(false);

                            int bodyOffset = headerEndIdx + separator.Length;
                            int bodyLength = requestBytes.Length - bodyOffset;
                            if (bodyLength > 0)
                            {
                                await targetStream.WriteAsync(requestBytes, bodyOffset, bodyLength, token).ConfigureAwait(false);
                            }
                        }
                        else
                        {
                            await targetStream.WriteAsync(requestBytes, 0, requestBytes.Length, token).ConfigureAwait(false);
                        }
                    }

                    var clientToTarget = clientStream.CopyToAsync(targetStream, token);
                    var targetToClient = targetStream.CopyToAsync(clientStream, token);
                    await Task.WhenAll(clientToTarget, targetToClient).ConfigureAwait(false);
                }
                catch { }
            }
        }

        /// <summary>
        /// Sanea las cabeceras que el proxy reenvía al HttpListener interno:
        /// elimina cualquier X-Forwarded-For, CF-Connecting-IP o marcador de
        /// proxy traídos por el cliente y escribe, en su lugar, la IP real
        /// observada en el socket como único X-Forwarded-For (sin encadenar
        /// valor alguno del cliente) junto al marcador de proxy de confianza.
        /// CF-Connecting-IP no se reescribe: desaparece, porque la fuente
        /// autorizada de la IP del cliente pasa a ser X-Forwarded-For con
        /// marcador.
        /// </summary>
        private static string ReescribirCabecerasDelProxy(string cabeceras, string? ipReal)
        {
            string limpias = _cabecerasSuplantables.Replace(cabeceras, "");
            if (!string.IsNullOrWhiteSpace(ipReal))
                limpias += $"\r\nX-Forwarded-For: {ipReal.Trim()}";
            limpias += $"\r\n{CabeceraMarcadorProxy}: {_valorMarcadorProxy}";
            return limpias;
        }

        private static int FindBytes(byte[] src, byte[] pattern)
        {
            for (int i = 0; i <= src.Length - pattern.Length; i++)
            {
                bool match = true;
                for (int j = 0; j < pattern.Length; j++)
                {
                    if (src[i + j] != pattern[j])
                    {
                        match = false;
                        break;
                    }
                }
                if (match) return i;
            }
            return -1;
        }
    }
}
