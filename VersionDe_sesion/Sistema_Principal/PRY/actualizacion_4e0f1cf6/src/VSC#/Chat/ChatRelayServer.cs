using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Chat
{
    /// <summary>
    /// Relay del chat del metaverso. Escucha WebSocket en todas las interfaces para
    /// que el anfitrión pueda atender tanto al túnel público como a la LAN.
    /// El servidor implementa el handshake y las tramas básicas de RFC 6455 para no
    /// depender de HttpListener (que exigiría reservar la URL con permisos de admin).
    /// </summary>
    public sealed class ChatRelayServer : IDisposable
    {
        private const string WsGuid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
        private const int MaxCabeceraHttp = 16 * 1024;

        private readonly object _gate = new();
        private readonly List<Cliente> _clientes = new();
        private TcpListener? _listener;
        private CancellationTokenSource? _cts;
        private int _siguienteId = 1;
        private bool _disposed;

        public int Port { get; private set; }
        public bool IsRunning { get { lock (_gate) return _listener != null; } }
        public int ClientCount { get { lock (_gate) return _clientes.Count; } }

        public event Action<string>? Log;

        public bool Start(int puertoPreferido = 8920, int intentos = 10)
        {
            lock (_gate)
            {
                if (_disposed || _listener != null) return _listener != null;

                for (int p = puertoPreferido; p < puertoPreferido + intentos; p++)
                {
                    try
                    {
                        var listener = new TcpListener(IPAddress.Any, p);
                        listener.Start(32);
                        _listener = listener;
                        Port = p;
                        _cts = new CancellationTokenSource();
                        _ = Task.Run(() => BucleAceptacionAsync(listener, _cts.Token));
                        Log?.Invoke($"Chat: relay escuchando en 0.0.0.0:{p}");
                        return true;
                    }
                    catch (SocketException) { }
                }

                Log?.Invoke("Chat: no se pudo abrir ningún puerto para el relay (8920-8929).");
                return false;
            }
        }

        public void Stop()
        {
            CancellationTokenSource? cts;
            TcpListener? listener;
            Cliente[] clientes;
            lock (_gate)
            {
                cts = _cts;
                listener = _listener;
                clientes = _clientes.ToArray();
                _clientes.Clear();
                _cts = null;
                _listener = null;
            }

            try { cts?.Cancel(); } catch { }
            try { listener?.Stop(); } catch { }
            foreach (var c in clientes)
            {
                try { c.Tcp.Close(); } catch { }
            }
            cts?.Dispose();
        }

        private async Task BucleAceptacionAsync(TcpListener listener, CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                TcpClient tcp;
                try { tcp = await listener.AcceptTcpClientAsync(ct); }
                catch (OperationCanceledException) { break; }
                catch (ObjectDisposedException) { break; }
                catch (SocketException) { break; }
                catch { continue; }

                _ = Task.Run(() => AtenderClienteAsync(tcp, ct), ct);
            }
        }

        private async Task AtenderClienteAsync(TcpClient tcp, CancellationToken ct)
        {
            Cliente? cliente = null;
            try
            {
                tcp.NoDelay = true;
                using (tcp)
                using (var stream = tcp.GetStream())
                {
                    string? cabecera = await LeerCabeceraHttpAsync(stream, ct);
                    if (cabecera == null) return;

                    lock (_gate)
                    {
                        if (_clientes.Count >= ChatProtocol.MaxClients)
                        {
                            _ = ResponderHttpAsync(stream, "503 Service Unavailable", ct);
                            return;
                        }
                    }

                    if (!Handshake(stream, cabecera, out string? error))
                    {
                        await ResponderHttpAsync(stream, error ?? "400 Bad Request", ct);
                        return;
                    }

                    lock (_gate)
                    {
                        cliente = new Cliente
                        {
                            Id = _siguienteId++,
                            Tcp = tcp,
                            Stream = stream
                        };
                        _clientes.Add(cliente);
                    }

                    await BucleClienteAsync(cliente, ct);
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[ChatRelay] Cliente: {ex.Message}");
            }
            finally
            {
                if (cliente != null)
                    await QuitarClienteAsync(cliente, ct);
            }
        }

        private async Task BucleClienteAsync(Cliente c, CancellationToken ct)
        {
            MemoryStream? fragmentado = null;
            int opcodeFragmentado = 0;

            while (!ct.IsCancellationRequested)
            {
                Marco? marco = await LeerMarcoAsync(c.Stream, ct);
                if (marco == null) return;

                switch (marco.Opcode)
                {
                    case 0x8: // close
                        await EnviarFrameAsync(c, 0x8, ReadOnlyMemory<byte>.Empty, ct);
                        return;

                    case 0x9: // ping
                        await EnviarFrameAsync(c, 0xA, marco.Payload, ct);
                        continue;

                    case 0xA: // pong
                        continue;

                    case 0x0: // continuación
                        if (fragmentado == null || opcodeFragmentado == 0) continue;
                        fragmentado.Write(marco.Payload, 0, marco.Payload.Length);
                        if (fragmentado.Length > ChatProtocol.MaxFrameBytes) return;
                        if (marco.Fin)
                        {
                            byte[] completo = fragmentado.ToArray();
                            int op = opcodeFragmentado;
                            fragmentado.Dispose();
                            fragmentado = null;
                            opcodeFragmentado = 0;
                            if (!await ProcesarMensajeAsync(c, op, completo, ct)) return;
                        }
                        continue;

                    case 0x1:
                    case 0x2:
                        if (!marco.Fin)
                        {
                            fragmentado?.Dispose();
                            fragmentado = new MemoryStream();
                            opcodeFragmentado = marco.Opcode;
                            fragmentado.Write(marco.Payload, 0, marco.Payload.Length);
                            if (fragmentado.Length > ChatProtocol.MaxFrameBytes) return;
                        }
                        else if (!await ProcesarMensajeAsync(c, marco.Opcode, marco.Payload, ct))
                        {
                            return;
                        }
                        continue;

                    default:
                        return;
                }
            }
        }

        private async Task<bool> ProcesarMensajeAsync(Cliente c, int opcode, byte[] payload, CancellationToken ct)
        {
            if (opcode == 0x1)
                return await ProcesarTextoAsync(c, payload, ct);

            if (opcode == 0x2)
                return await ProcesarBinarioAsync(c, payload, ct);

            return true;
        }

        private async Task<bool> ProcesarTextoAsync(Cliente c, byte[] payload, CancellationToken ct)
        {
            if (!Permitir(c, binario: false)) return true;

            JsonDocument doc;
            try { doc = JsonDocument.Parse(payload); }
            catch { return true; }

            using (doc)
            {
                if (!doc.RootElement.TryGetProperty("t", out var tipoProp)) return true;
                string tipo = tipoProp.GetString() ?? "";

                if (tipo == "hello")
                {
                    if (!c.Anunciado)
                    {
                        string nombre = doc.RootElement.TryGetProperty("name", out var n)
                            ? ChatProtocol.CleanName(n.GetString())
                            : "Invitado";
                        string uid = ChatProtocol.CleanUid(
                            doc.RootElement.TryGetProperty("uid", out var u) ? u.GetString() : "");
                        if (uid.Length == 0) uid = ChatProtocol.BuildFallbackUid(nombre);

                        c.Name = nombre;
                        c.Uid = uid;
                        c.Anunciado = true;
                        await EnviarBienvenidaAsync(c, ct);
                        await DifundirAsync(
                            ChatProtocol.TextFrame(new { t = "join", id = c.Id, name = c.Name, uid = c.Uid }),
                            opcode: 0x1, excepto: c.Id, ct);
                        await DifundirSistemaAsync(
                            $"{c.Name} se ha unido al chat", c.Id, excepto: c.Id, ct);
                    }
                    return true;
                }

                if (tipo == "msg")
                {
                    if (!c.Anunciado)
                    {
                        c.Name = "Invitado";
                        c.Uid = ChatProtocol.BuildFallbackUid(c.Name);
                        c.Anunciado = true;
                        await EnviarBienvenidaAsync(c, ct);
                    }

                    string texto = doc.RootElement.TryGetProperty("text", out var t)
                        ? ChatProtocol.CleanText(t.GetString())
                        : "";
                    if (texto.Length == 0) return true;

                    var salida = new
                    {
                        t = "msg",
                        id = c.Id,
                        name = c.Name,
                        ts = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                        text = texto
                    };
                    await DifundirAsync(ChatProtocol.TextFrame(salida), opcode: 0x1, excepto: null, ct);
                    return true;
                }

                if (tipo == "state")
                {
                    c.Audio = doc.RootElement.TryGetProperty("audio", out var a) && a.GetBoolean();
                    c.Video = doc.RootElement.TryGetProperty("video", out var v) && v.GetBoolean();
                    if (!c.Anunciado) return true;

                    var estado = new
                    {
                        t = "state",
                        id = c.Id,
                        name = c.Name,
                        uid = c.Uid,
                        audio = c.Audio,
                        video = c.Video
                    };
                    await DifundirAsync(ChatProtocol.TextFrame(estado), opcode: 0x1, excepto: null, ct);
                    return true;
                }

                if (tipo == "friend_req")
                    return await ProcesarSolicitudAmistadAsync(c, doc.RootElement, ct);

                if (tipo == "friend_ok" || tipo == "friend_no")
                    return await ProcesarRespuestaAmistadAsync(c, tipo, doc.RootElement, ct);

                if (tipo == "dm")
                    return await ProcesarMensajePrivadoAsync(c, doc.RootElement, ct);

                if (tipo == "bye")
                    return false;
            }

            return true;
        }

        private async Task<bool> ProcesarSolicitudAmistadAsync(
            Cliente c, JsonElement raiz, CancellationToken ct)
        {
            if (!c.Anunciado) return true;
            string destino = ChatProtocol.CleanUid(
                raiz.TryGetProperty("to", out var t) ? t.GetString() : "");
            if (destino.Length == 0 || destino == c.Uid) return true;

            if (!PermitirSocial(c))
            {
                await EnviarFrameAsync(c, 0x1, ChatProtocol.TextFrame(new
                {
                    t = "friend_fail",
                    to = destino,
                    reason = "Demasiadas solicitudes seguidas. Espera unos segundos."
                }), ct);
                return true;
            }

            List<Cliente> objetivos = ResolverPorUid(destino);
            if (objetivos.Count == 0)
            {
                List<Cliente> porCodigo = ResolverPorCodigo(destino);
                if (porCodigo.Count > 0)
                {
                    var uids = new HashSet<string>(porCodigo.Select(x => x.Uid));
                    if (uids.Count == 1)
                        objetivos = porCodigo;
                }
            }

            if (objetivos.Count == 0)
            {
                await EnviarFrameAsync(c, 0x1, ChatProtocol.TextFrame(new
                {
                    t = "friend_fail",
                    to = destino,
                    reason = "Esa persona no está conectada en esta sesión."
                }), ct);
                return true;
            }

            string uidDestino = objetivos[0].Uid;
            string nombreDestino = objetivos[0].Name;
            string nota = ChatProtocol.CleanText(
                raiz.TryGetProperty("text", out var n) ? n.GetString() : "");
            if (nota.Length > ChatProtocol.MaxFriendNoteChars)
                nota = nota[..ChatProtocol.MaxFriendNoteChars];

            var aviso = ChatProtocol.TextFrame(new
            {
                t = "friend_req",
                from = c.Uid,
                fromName = c.Name,
                text = nota,
                ts = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
            });

            var enviados = new HashSet<string>();
            foreach (var objetivo in objetivos)
            {
                if (!enviados.Add(objetivo.Uid)) continue;
                await EnviarFrameAsync(objetivo, 0x1, aviso, ct);
            }

            await EnviarFrameAsync(c, 0x1, ChatProtocol.TextFrame(new
            {
                t = "friend_sent",
                uid = uidDestino,
                name = nombreDestino,
                to = destino
            }), ct);
            return true;
        }

        private async Task<bool> ProcesarRespuestaAmistadAsync(
            Cliente c, string tipo, JsonElement raiz, CancellationToken ct)
        {
            if (!c.Anunciado) return true;
            string destino = ChatProtocol.CleanUid(
                raiz.TryGetProperty("to", out var t) ? t.GetString() : "");
            if (destino.Length == 0 || destino == c.Uid) return true;
            if (!PermitirSocial(c)) return true;

            List<Cliente> objetivos = ResolverPorUid(destino);
            if (objetivos.Count == 0)
            {
                await EnviarFrameAsync(c, 0x1, ChatProtocol.TextFrame(new
                {
                    t = "friend_fail",
                    to = destino,
                    reason = "Esa persona ya no está conectada."
                }), ct);
                return true;
            }

            var aviso = ChatProtocol.TextFrame(new
            {
                t = tipo,
                from = c.Uid,
                fromName = c.Name,
                ts = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()
            });

            var enviados = new HashSet<string>();
            foreach (var objetivo in objetivos)
            {
                if (!enviados.Add(objetivo.Uid)) continue;
                await EnviarFrameAsync(objetivo, 0x1, aviso, ct);
            }
            return true;
        }

        private async Task<bool> ProcesarMensajePrivadoAsync(
            Cliente c, JsonElement raiz, CancellationToken ct)
        {
            if (!c.Anunciado) return true;
            string destino = ChatProtocol.CleanUid(
                raiz.TryGetProperty("to", out var t) ? t.GetString() : "");
            string texto = ChatProtocol.CleanText(
                raiz.TryGetProperty("text", out var x) ? x.GetString() : "");
            if (destino.Length == 0 || destino == c.Uid || texto.Length == 0) return true;

            if (!PermitirSocial(c))
            {
                await EnviarFrameAsync(c, 0x1, ChatProtocol.TextFrame(new
                {
                    t = "dm_fail",
                    to = destino,
                    reason = "Demasiados mensajes seguidos. Espera unos segundos."
                }), ct);
                return true;
            }

            List<Cliente> objetivos = ResolverPorUid(destino);
            if (objetivos.Count == 0)
            {
                await EnviarFrameAsync(c, 0x1, ChatProtocol.TextFrame(new
                {
                    t = "dm_fail",
                    to = destino,
                    reason = "Esa persona no está conectada en esta sesión."
                }), ct);
                return true;
            }

            var salida = ChatProtocol.TextFrame(new
            {
                t = "dm",
                id = c.Id,
                from = c.Uid,
                fromName = c.Name,
                ts = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                text = texto
            });

            var enviados = new HashSet<string>();
            foreach (var objetivo in objetivos)
            {
                if (!enviados.Add(objetivo.Uid)) continue;
                await EnviarFrameAsync(objetivo, 0x1, salida, ct);
            }
            return true;
        }

        private List<Cliente> ResolverPorUid(string uid)
        {
            lock (_gate)
                return _clientes.Where(x => x.Anunciado && x.Uid == uid).ToList();
        }

        private List<Cliente> ResolverPorCodigo(string codigo)
        {
            string buscado = codigo.Trim().ToUpperInvariant();
            if (buscado.Length == 0) return new List<Cliente>();

            lock (_gate)
                return _clientes
                    .Where(x => x.Anunciado && ChatProtocol.BuildFriendCode(x.Uid) == buscado)
                    .ToList();
        }

        private async Task<bool> ProcesarBinarioAsync(Cliente c, byte[] frame, CancellationToken ct)
        {
            if (!c.Anunciado || frame.Length < 2) return true;
            if (!Permitir(c, binario: true)) return true;

            int kind = frame[0];
            int tam = frame.Length - 1;

            if (kind == ChatProtocol.KindAudio)
            {
                if (tam <= 0 || tam > ChatProtocol.MaxAudioBytes || (tam & 1) != 0) return true;
            }
            else if (kind == ChatProtocol.KindVideo)
            {
                if (tam < 4 || tam > ChatProtocol.MaxVideoBytes) return true;
                // JPEG: FF D8 ... FF D9 (se acepta sin comprobar el cierre por velocidad).
                if (frame[1] != 0xFF || frame[2] != 0xD8) return true;
            }
            else
            {
                return true;
            }

            byte[] salida = ChatProtocol.BuildServerFrame(kind, c.Id, frame.AsSpan(1));
            await DifundirAsync(salida, opcode: 0x2, excepto: c.Id, ct);
            return true;
        }

        private bool Permitir(Cliente c, bool binario)
        {
            var ahora = DateTime.UtcNow;
            if (binario)
            {
                if (ahora - c.VentanaBinaria > TimeSpan.FromSeconds(1))
                {
                    c.VentanaBinaria = ahora;
                    c.ContadorBinario = 0;
                }
                c.ContadorBinario++;
                return c.ContadorBinario <= 90;
            }

            if (ahora - c.VentanaTexto > TimeSpan.FromSeconds(1))
            {
                c.VentanaTexto = ahora;
                c.ContadorTexto = 0;
            }
            c.ContadorTexto++;
            return c.ContadorTexto <= 10;
        }

        /// <summary>
        /// Límite adicional para amistades y privados: 20 acciones cada 10 s.
        /// Evita que una cuenta inunde a otra con solicitudes o mensajes.
        /// </summary>
        private static bool PermitirSocial(Cliente c)
        {
            var ahora = DateTime.UtcNow;
            if (ahora - c.VentanaSocial > TimeSpan.FromSeconds(10))
            {
                c.VentanaSocial = ahora;
                c.ContadorSocial = 0;
            }
            c.ContadorSocial++;
            return c.ContadorSocial <= 20;
        }

        private async Task EnviarBienvenidaAsync(Cliente c, CancellationToken ct)
        {
            var pares = new List<object>();
            lock (_gate)
            {
                foreach (var otro in _clientes)
                {
                    if (otro.Id == c.Id || !otro.Anunciado) continue;
                    pares.Add(new
                    {
                        id = otro.Id,
                        name = otro.Name,
                        uid = otro.Uid,
                        audio = otro.Audio,
                        video = otro.Video
                    });
                }
            }

            var bienvenida = new
            {
                t = "welcome",
                id = c.Id,
                name = c.Name,
                uid = c.Uid,
                code = ChatProtocol.BuildFriendCode(c.Uid),
                max = ChatProtocol.MaxClients,
                peers = pares
            };
            await EnviarFrameAsync(c, 0x1, ChatProtocol.TextFrame(bienvenida), ct);
        }

        private async Task DifundirSistemaAsync(string texto, int id, int? excepto, CancellationToken ct)
        {
            var aviso = new { t = "sys", id, text = ChatProtocol.CleanText(texto) };
            await DifundirAsync(ChatProtocol.TextFrame(aviso), opcode: 0x1, excepto, ct);
        }

        private async Task DifundirAsync(byte[] frame, int opcode, int? excepto, CancellationToken ct)
        {
            Cliente[] copia;
            lock (_gate) copia = _clientes.ToArray();

            foreach (var destino in copia)
            {
                if (excepto.HasValue && destino.Id == excepto.Value) continue;
                if (!destino.Anunciado) continue;
                await EnviarFrameAsync(destino, opcode, frame, ct);
            }
        }

        private static async Task EnviarFrameAsync(Cliente c, int opcode, ReadOnlyMemory<byte> payload, CancellationToken ct)
        {
            try
            {
                await c.SendLock.WaitAsync(ct);
            }
            catch { return; }

            try
            {
                int len = payload.Length;
                byte[] cabecera;
                if (len < 126)
                {
                    cabecera = new byte[] { (byte)(0x80 | opcode), (byte)len };
                }
                else if (len <= 0xFFFF)
                {
                    cabecera = new byte[4];
                    cabecera[0] = (byte)(0x80 | opcode);
                    cabecera[1] = 126;
                    BinaryPrimitives.WriteUInt16BigEndian(cabecera.AsSpan(2), (ushort)len);
                }
                else
                {
                    cabecera = new byte[10];
                    cabecera[0] = (byte)(0x80 | opcode);
                    cabecera[1] = 127;
                    BinaryPrimitives.WriteUInt64BigEndian(cabecera.AsSpan(2), (ulong)len);
                }

                await c.Stream.WriteAsync(cabecera, ct);
                if (len > 0) await c.Stream.WriteAsync(payload, ct);
                await c.Stream.FlushAsync(ct);
            }
            catch
            {
                // La lectura del socket detectará la caída y retirará al cliente.
            }
            finally
            {
                try { c.SendLock.Release(); } catch { }
            }
        }

        private async Task QuitarClienteAsync(Cliente c, CancellationToken ct)
        {
            bool anunciado;
            lock (_gate)
            {
                anunciado = c.Anunciado;
                _clientes.Remove(c);
            }

            if (anunciado)
            {
                await DifundirSistemaAsync($"{c.Name} ha salido del chat", c.Id, excepto: c.Id, ct);
                var salida = ChatProtocol.TextFrame(new { t = "bye", id = c.Id, name = c.Name, uid = c.Uid });
                await DifundirAsync(salida, opcode: 0x1, excepto: c.Id, ct);
            }
        }

        private static async Task<string?> LeerCabeceraHttpAsync(NetworkStream stream, CancellationToken ct)
        {
            var ms = new MemoryStream();
            byte[] buffer = new byte[512];
            while (ms.Length < MaxCabeceraHttp)
            {
                int n = await stream.ReadAsync(buffer, ct);
                if (n <= 0) return null;
                ms.Write(buffer, 0, n);

                byte[] datos = ms.ToArray();
                if (ContieneFinCabecera(datos))
                    return Encoding.UTF8.GetString(datos);
            }
            return null;
        }

        private static bool ContieneFinCabecera(byte[] datos)
        {
            for (int i = 0; i <= datos.Length - 4; i++)
            {
                if (datos[i] == 13 && datos[i + 1] == 10 && datos[i + 2] == 13 && datos[i + 3] == 10)
                    return true;
            }
            return false;
        }

        private static bool Handshake(NetworkStream stream, string cabecera, out string? error)
        {
            error = null;
            string[] lineas = cabecera.Split("\r\n");
            if (lineas.Length == 0) { error = "400 Bad Request"; return false; }

            string[] peticion = lineas[0].Split(' ');
            if (peticion.Length < 2 || peticion[0] != "GET") { error = "400 Bad Request"; return false; }

            string ruta = peticion[1];
            if (!ruta.StartsWith("/chat", StringComparison.OrdinalIgnoreCase)) { error = "404 Not Found"; return false; }

            string? upgrade = null;
            string? connection = null;
            string? key = null;
            for (int i = 1; i < lineas.Length; i++)
            {
                int sep = lineas[i].IndexOf(':');
                if (sep <= 0) continue;
                string nombre = lineas[i][..sep].Trim();
                string valor = lineas[i][(sep + 1)..].Trim();
                if (nombre.Equals("Upgrade", StringComparison.OrdinalIgnoreCase)) upgrade = valor;
                else if (nombre.Equals("Connection", StringComparison.OrdinalIgnoreCase)) connection = valor;
                else if (nombre.Equals("Sec-WebSocket-Key", StringComparison.OrdinalIgnoreCase)) key = valor;
            }

            if (upgrade == null || !upgrade.Equals("websocket", StringComparison.OrdinalIgnoreCase) ||
                connection == null || !connection.Contains("Upgrade", StringComparison.OrdinalIgnoreCase) ||
                string.IsNullOrWhiteSpace(key))
            {
                error = "400 Bad Request";
                return false;
            }

            string aceptado = Convert.ToBase64String(
                SHA1.HashData(Encoding.ASCII.GetBytes(key.Trim() + WsGuid)));
            string respuesta =
                "HTTP/1.1 101 Switching Protocols\r\n" +
                "Upgrade: websocket\r\n" +
                "Connection: Upgrade\r\n" +
                $"Sec-WebSocket-Accept: {aceptado}\r\n\r\n";
            byte[] bytes = Encoding.ASCII.GetBytes(respuesta);
            try
            {
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush();
            }
            catch { error = "400 Bad Request"; return false; }

            return true;
        }

        private static async Task ResponderHttpAsync(NetworkStream stream, string estado, CancellationToken ct)
        {
            try
            {
                byte[] bytes = Encoding.ASCII.GetBytes(
                    $"HTTP/1.1 {estado}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n");
                await stream.WriteAsync(bytes, ct);
                await stream.FlushAsync(ct);
            }
            catch { }
        }

        private sealed class Marco
        {
            public bool Fin;
            public int Opcode;
            public byte[] Payload = Array.Empty<byte>();
        }

        private static async Task<Marco?> LeerMarcoAsync(NetworkStream stream, CancellationToken ct)
        {
            byte[] cabecera = new byte[2];
            if (!await LeerExactoAsync(stream, cabecera, 2, ct)) return null;

            bool fin = (cabecera[0] & 0x80) != 0;
            int opcode = cabecera[0] & 0x0F;
            bool enmascarado = (cabecera[1] & 0x80) != 0;
            long longitud = cabecera[1] & 0x7F;

            if (longitud == 126)
            {
                byte[] ext = new byte[2];
                if (!await LeerExactoAsync(stream, ext, 2, ct)) return null;
                longitud = BinaryPrimitives.ReadUInt16BigEndian(ext);
            }
            else if (longitud == 127)
            {
                byte[] ext = new byte[8];
                if (!await LeerExactoAsync(stream, ext, 8, ct)) return null;
                ulong valor = BinaryPrimitives.ReadUInt64BigEndian(ext);
                if (valor > (ulong)ChatProtocol.MaxFrameBytes) return null;
                longitud = (long)valor;
            }

            if (longitud < 0 || longitud > ChatProtocol.MaxFrameBytes) return null;
            if (!enmascarado) return null; // RFC 6455: el cliente siempre enmascara.

            byte[] mascara = new byte[4];
            if (!await LeerExactoAsync(stream, mascara, 4, ct)) return null;

            byte[] payload = new byte[(int)longitud];
            if (longitud > 0 && !await LeerExactoAsync(stream, payload, (int)longitud, ct)) return null;

            for (int i = 0; i < payload.Length; i++)
                payload[i] ^= mascara[i & 3];

            return new Marco { Fin = fin, Opcode = opcode, Payload = payload };
        }

        private static async Task<bool> LeerExactoAsync(NetworkStream stream, byte[] buffer, int cantidad, CancellationToken ct)
        {
            int total = 0;
            while (total < cantidad)
            {
                int n;
                try { n = await stream.ReadAsync(buffer.AsMemory(total, cantidad - total), ct); }
                catch { return false; }
                if (n <= 0) return false;
                total += n;
            }
            return true;
        }

        public void Dispose()
        {
            lock (_gate)
            {
                if (_disposed) return;
                _disposed = true;
            }
            Stop();
        }

        private sealed class Cliente
        {
            public int Id;
            public string Name = "";
            public string Uid = "";
            public bool Anunciado;
            public bool Audio;
            public bool Video;
            public TcpClient Tcp = null!;
            public NetworkStream Stream = null!;
            public SemaphoreSlim SendLock = new(1, 1);
            public DateTime VentanaTexto = DateTime.MinValue;
            public int ContadorTexto;
            public DateTime VentanaBinaria = DateTime.MinValue;
            public int ContadorBinario;
            public DateTime VentanaSocial = DateTime.MinValue;
            public int ContadorSocial;
        }
    }
}
