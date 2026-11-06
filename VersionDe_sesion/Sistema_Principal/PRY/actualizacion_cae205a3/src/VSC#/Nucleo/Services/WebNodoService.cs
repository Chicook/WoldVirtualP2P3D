using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;
using Visor3D.RedP2P;

namespace Visor3D.Services
{
    /// <summary>
    /// WebNodo embebido en el visor C# (sin Node.js).
    /// Sirve en http://localhost:3030/:
    ///   GET /           -> portal de descarga (index.html)
    ///   GET /metaverso.jpg -> imagen del portal
    ///   GET /descargar  -> entrega el binario que este proceso ejecuta
    ///   GET /api/info  -> JSON con info del .exe disponible
    ///   GET /api/p2p-status -> estado de la sesion P2P (si esta activa)
    ///
    /// Este fichero es la RAÍZ del ciclo de vida: declara los campos mutables (los
    /// parciales los leen, ninguno los vuelve a declarar) y enlaza los puertos.
    /// Cada responsabilidad restante vive en su propio fichero parcial, para que se
    /// pueda leer y probar sola:
    ///   WebNodoService.PortalHttp.cs      -> router HTTP, recursos, IP y límites
    ///   WebNodoService.ProxyTcp.cs        -> proxy TCP y reescritura de cabeceras
    ///   WebNodoService.ProxyWebSocket.cs  -> proxy del handshake WebSocket
    ///   AnuncioRelease.cs                 -> qué release anuncia el portal
    /// </summary>
    public partial class WebNodoService : IDisposable
    {
        private HttpListener? _listener;
        private TcpListener? _proxyListener;
        private int _internalPort;
        private CancellationTokenSource? _cts;
        private Thread? _thread;
        private bool _disposed;
        private string? _publicTunnelUrl;
        private string? _startError;
        private readonly object _lock = new object();

        public bool IsRunning
        {
            get
            {
                lock (_lock)
                {
                    return _listener != null && _listener.IsListening;
                }
            }
        }

        public string? StartError => _startError;

        public int ActivePort { get; private set; } = ConfigRed.PuertoPortal;

        // Seteado desde MainWindow cuando el tunel P2P esta activo
        public string? PublicTunnelUrl
        {
            get => _publicTunnelUrl;
            set => _publicTunnelUrl = value;
        }

        /// <summary>Puerto local del relay de chat; /chat se proxya aquí.</summary>
        public int ChatLocalPort { get; set; } = ConfigRed.PuertoChat;

        /// <summary>False hasta que el relay de chat está escuchando.</summary>
        public bool ChatEnabled { get; set; }

        public static readonly int Port = ConfigRed.PuertoPortal;

        /// <summary>
        /// Credencial de la sesión P2P. El proxy WebSocket (motor y chat) solo
        /// reenvía handshakes que la traen en <c>?invitacion=</c>, de modo que
        /// conocer la URL del portal no basta para entrar en el mundo. Un invitado
        /// adopta el token del anfitrión raíz para poder re-alojar tras una migración.
        /// Es la misma credencial que autentica ante el relay de chat: vive en
        /// TokenSesionChat (única copia en memoria del proceso); esta propiedad
        /// solo la lee y, al asignar, la adopta en ese helper compartido.
        /// </summary>
        public string TokenInvitacion
        {
            get => Visor3D.Chat.TokenSesionChat.Actual;
            set => Visor3D.Chat.TokenSesionChat.Establecer(value);
        }

        public void Start()
        {
            lock (_lock)
            {
                if (_disposed) return;
                if (IsRunning)
                {
                    _startError = null;
                    return;
                }

                _startError = null;
                AnuncioRelease.Refrescar();
                _cts = new CancellationTokenSource();

                // Si había recursos previos en estado inconsistente, limpiarlo
                try { _proxyListener?.Stop(); } catch { }
                _proxyListener = null;
                try { _listener?.Close(); } catch { }
                _listener = null;

                // Intentar puertos en el rango del portal [3030..3040]
                int[] candidatePorts = ConfigRed.PuertosPortalCandidatos();
                Exception? lastEx = null;

                // Opción principal: Proxy TCP en candidatePort + HttpListener en internalPort
                // Esto reescribe la cabecera Host a "127.0.0.1:{internalPort}", lo que elimina
                // completamente el error "400 Bad Request - Invalid Hostname" de HTTP.sys en túneles Cloudflare/SSH.
                foreach (int port in candidatePorts)
                {
                    try
                    {
                        int intPort = port + ConfigRed.DesplazamientoProxyInterno;
                        var candidateHttp = new HttpListener();
                        candidateHttp.Prefixes.Add($"http://localhost:{intPort}/");
                        candidateHttp.Prefixes.Add($"http://127.0.0.1:{intPort}/");
                        candidateHttp.Start();

                        var candidateProxy = new TcpListener(IPAddress.Loopback, port);
                        candidateProxy.Start();

                        _internalPort = intPort;
                        _listener = candidateHttp;
                        _proxyListener = candidateProxy;
                        ActivePort = port;
                        lastEx = null;
                        break;
                    }
                    catch (Exception exProxy)
                    {
                        lastEx = exProxy;
                        try { _proxyListener?.Stop(); } catch { }
                        _proxyListener = null;
                        try { _listener?.Close(); } catch { }
                        _listener = null;
                    }
                }

                // Fallback: Si no se pudo iniciar el proxy TCP, probar HttpListener directo
                if (_listener == null)
                {
                    foreach (int port in candidatePorts)
                    {
                        try
                        {
                            var candidate = new HttpListener();
                            candidate.Prefixes.Add($"http://localhost:{port}/");
                            candidate.Prefixes.Add($"http://127.0.0.1:{port}/");
                            candidate.Start();

                            _listener = candidate;
                            ActivePort = port;
                            lastEx = null;
                            break;
                        }
                        catch (Exception exDirect)
                        {
                            lastEx = exDirect;
                        }
                    }
                }

                if (_listener != null && _listener.IsListening)
                {
                    _thread = new Thread(ListenerLoop) { IsBackground = true };
                    _thread.Start(_cts.Token);

                    if (_proxyListener != null)
                    {
                        Task.Run(() => ProxyLoop(_cts.Token));
                        System.Diagnostics.Debug.WriteLine($"[WebNodo] Proxy TCP en puerto {ActivePort} -> HttpListener interno en {_internalPort}");
                    }
                    else
                    {
                        System.Diagnostics.Debug.WriteLine($"[WebNodo] HttpListener directo en puerto {ActivePort}");
                    }
                }
                else
                {
                    _startError = lastEx?.Message ?? "No se pudo enlazar ningún puerto local.";
                    System.Diagnostics.Debug.WriteLine($"[WebNodo] No se pudo iniciar: {_startError}");
                }
            }
        }

        public void Stop()
        {
            lock (_lock)
            {
                if (_disposed) return;
                try { _cts?.Cancel(); } catch { }
                try { _proxyListener?.Stop(); } catch { }
                _proxyListener = null;
                try { _listener?.Stop(); } catch { }
                try { _listener?.Close(); } catch { }
                _listener = null;
            }
        }

        private void ListenerLoop(object? state)
        {
            var token = (CancellationToken)state!;
            while (!token.IsCancellationRequested)
            {
                HttpListener? l;
                lock (_lock) { l = _listener; }
                if (l == null || !l.IsListening) break;

                try
                {
                    var ctx = l.GetContext();
                    _ = Task.Run(() => ProcessRequest(ctx), token);
                }
                catch (HttpListenerException) { break; }
                catch (ObjectDisposedException) { break; }
                catch { break; }
            }
        }

        public void Dispose()
        {
            lock (_lock)
            {
                if (_disposed) return;
                Stop();
                try { _cts?.Dispose(); } catch { }
                _disposed = true;
            }
        }
    }
}
