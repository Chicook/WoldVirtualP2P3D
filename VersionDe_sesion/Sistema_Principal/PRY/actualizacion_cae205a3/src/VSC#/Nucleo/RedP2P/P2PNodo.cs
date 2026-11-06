using System;
using System.Net;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Visor3D.Services;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Servidor HTTP embebido minimalista que actúa como nodo P2P del visor.
    /// Escucha en <see cref="Puerto"/> y responde a:
    ///   GET /ping  → "pong" (keepalive/descubrimiento)
    ///   GET /info  → JSON con info del nodo
    ///   POST /peer → recibe la URL de un par remoto; exige la invitación
    ///                de la sesión (campo «invitacion» del cuerpo), valida
    ///                la URL y aplica tope de pares y límite de intentos.
    /// </summary>
    public class P2PNodo : IDisposable
    {
        /// <summary>
        /// Máximo de pares registrados a la vez. El registro es una lista de
        /// amigos de la sesión, no un directorio público: con el tope lleno,
        /// los registros nuevos se rechazan (429) en vez de crecer sin límite.
        /// </summary>
        public const int MaxPares = 100;

        /// <summary>Intentos de registro admitidos por IP y minuto.</summary>
        private const int MaxIntentosRegistroPorMinuto = 30;

        /// <summary>Longitud máxima aceptada para la URL de un par.</summary>
        private const int LongitudMaxUrlPar = 1024;

        private HttpListener? _listener;
        private CancellationTokenSource? _cts;
        private bool _disposed;
        private readonly string _nombreUsuario;
        private readonly object _candadoPares = new();
        private readonly RateLimiter _limiteRegistro = new();

        public int Puerto { get; }

        /// <summary>
        /// Credencial de la sesión P2P: la misma invitación que protege el
        /// portal WebNodo. POST /peer solo registra si la petición la trae en
        /// el campo «invitacion» del cuerpo; sin ella, cualquier visitante del
        /// túnel podría registrar URLs de par ajenas y sin límite.
        /// Se genera una aleatoria al crear el nodo (nunca queda abierta la
        /// puerta por defecto): el visor la sustituye por la invitación
        /// vigente de la sesión a través de <see cref="RedP2PServicio.TokenInvitacion"/>.
        /// Solo vive en memoria; no se persiste ni se escribe en logs.
        /// </summary>
        public string TokenInvitacion { get; set; } =
            Convert.ToHexString(RandomNumberGenerator.GetBytes(16)).ToLowerInvariant();

        /// <summary>Lista de URLs de pares descubiertos remotamente.</summary>
        public System.Collections.Generic.List<string> Pares { get; } = new();

        /// <summary>Disparado cuando se registra un nuevo par.</summary>
        public event Action<string>? NuevoPar;

        public P2PNodo(int puerto, string nombreUsuario)
        {
            Puerto = puerto;
            _nombreUsuario = nombreUsuario;
        }

        public Task IniciarAsync()
        {
            _cts = new CancellationTokenSource();
            _listener = new HttpListener();
            _listener.Prefixes.Add($"http://localhost:{Puerto}/");
            _listener.Prefixes.Add($"http://127.0.0.1:{Puerto}/");

            try
            {
                _listener.Start();
            }
            catch (HttpListenerException ex)
            {
                System.Diagnostics.Debug.WriteLine($"[P2PNodo] No se pudo iniciar listener: {ex.Message}");
                return Task.CompletedTask;
            }

            Task.Run(() => BucleEscuchaAsync(_cts.Token), _cts.Token);
            return Task.CompletedTask;
        }

        private async Task BucleEscuchaAsync(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested && (_listener?.IsListening ?? false))
            {
                try
                {
                    var ctx = await _listener!.GetContextAsync().ConfigureAwait(false);
                    _ = ProcesarPeticionAsync(ctx);
                }
                catch (ObjectDisposedException) { break; }
                catch (HttpListenerException) { break; }
                catch { }
            }
        }

        private async Task ProcesarPeticionAsync(HttpListenerContext ctx)
        {
            string ruta = ctx.Request.Url?.AbsolutePath.ToLowerInvariant() ?? "/";
            ctx.Response.ContentType = "application/json; charset=utf-8";
            ctx.Response.Headers["Access-Control-Allow-Origin"] = "*";

            byte[] respuesta;

            if (ruta == "/ping")
            {
                ctx.Response.StatusCode = 200;
                respuesta = Encoding.UTF8.GetBytes("{\"status\":\"pong\"}");
            }
            else if (ruta == "/info")
            {
                ctx.Response.StatusCode = 200;
                int numPares;
                lock (_candadoPares) { numPares = Pares.Count; }
                var info = new
                {
                    nodo    = _nombreUsuario,
                    version = "0.1.0",
                    puerto  = Puerto,
                    pares   = numPares
                };
                respuesta = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(info));
            }
            else if (ruta == "/peer" && ctx.Request.HttpMethod == "POST")
            {
                // Registrar par remoto: admisión autenticada (ver RegistrarPar).
                using var reader = new System.IO.StreamReader(ctx.Request.InputStream, Encoding.UTF8);
                string body = await reader.ReadToEndAsync().ConfigureAwait(false);
                string ipOrigen = ctx.Request.RemoteEndPoint?.Address?.ToString() ?? "desconocida";
                var (codigo, cuerpo) = RegistrarPar(body, ipOrigen);
                ctx.Response.StatusCode = codigo;
                respuesta = Encoding.UTF8.GetBytes(cuerpo);
            }
            else
            {
                ctx.Response.StatusCode = 404;
                respuesta = Encoding.UTF8.GetBytes("{\"error\":\"not found\"}");
            }

            await ctx.Response.OutputStream.WriteAsync(respuesta).ConfigureAwait(false);
            ctx.Response.Close();
        }

        /// <summary>
        /// Admisión de un registro de par (POST /peer). En orden:
        ///   1. Límite de intentos por IP de origen (la observada en el
        ///      socket, nunca una cabecera): frena la fuerza bruta contra
        ///      la invitación y el relleno del tope.
        ///   2. La URL debe ser absoluta http/https, con host y longitud
        ///      acotada: el valor se guarda y se muestra en la interfaz.
        ///   3. El campo «invitacion» debe coincidir con la credencial de
        ///      la sesión: conocer la URL pública del túnel no basta.
        ///   4. Tope de pares: duplicados idempotentes (200 sin cambios);
        ///      con el tope lleno, un par nuevo se rechaza con 429.
        /// Devuelve (código HTTP, cuerpo JSON de respuesta).
        /// </summary>
        private (int Codigo, string Cuerpo) RegistrarPar(string body, string ipOrigen)
        {
            if (!_limiteRegistro.Permitir(ipOrigen, MaxIntentosRegistroPorMinuto, TimeSpan.FromMinutes(1)))
                return (429, "{\"error\":\"demasiados intentos de registro\"}");

            string? urlPar = null;
            string? invitacion = null;
            try
            {
                using var doc = JsonDocument.Parse(body);
                if (doc.RootElement.TryGetProperty("url", out var urlProp))
                    urlPar = urlProp.GetString();
                if (doc.RootElement.TryGetProperty("invitacion", out var invProp))
                    invitacion = invProp.GetString();
            }
            catch { /* cuerpo no JSON o campos no textuales: registro inválido */ }

            if (!EsUrlParValida(urlPar))
                return (400, "{\"error\":\"url de par no válida\"}");

            if (!TokenCoincide(invitacion))
                return (401, "{\"error\":\"invitación de sesión ausente o incorrecta\"}");

            bool esNuevo = false;
            lock (_candadoPares)
            {
                if (!Pares.Contains(urlPar!))
                {
                    if (Pares.Count >= MaxPares)
                        return (429, "{\"error\":\"límite de pares alcanzado\"}");
                    Pares.Add(urlPar!);
                    esNuevo = true;
                }
            }
            if (esNuevo) NuevoPar?.Invoke(urlPar!);
            return (200, "{\"status\":\"ok\"}");
        }

        /// <summary>
        /// La URL de un par debe ser absoluta http/https con host y de
        /// longitud acotada: es el mismo criterio con el que luego se
        /// contacta al par (<see cref="PingParAsync"/>) y se muestra en la
        /// lista de pares, así que una cadena arbitraria no entra.
        /// </summary>
        private static bool EsUrlParValida(string? url)
        {
            if (string.IsNullOrWhiteSpace(url) || url.Length > LongitudMaxUrlPar) return false;
            if (!Uri.TryCreate(url, UriKind.Absolute, out Uri? uri)) return false;
            return (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps)
                   && !string.IsNullOrEmpty(uri.Host);
        }

        /// <summary>
        /// Compara la invitación recibida con la de la sesión. Sin
        /// credencial configurada o sin invitación en la petición, no hay
        /// coincidencia posible (puerta cerrada por defecto).
        /// </summary>
        private bool TokenCoincide(string? invitacion)
        {
            string esperado = TokenInvitacion;
            if (string.IsNullOrEmpty(esperado) || string.IsNullOrEmpty(invitacion)) return false;
            return string.Equals(invitacion, esperado, StringComparison.Ordinal);
        }

        /// <summary>
        /// Intenta contactar al par en <paramref name="urlPar"/> para anunciarse.
        /// Si se conoce la invitación de la sesión del par (la que traía su
        /// enlace de invitación), viaja en el cuerpo como «invitacion»: su
        /// nodo la exige para admitir el registro. Sin ella, un nodo
        /// protegido rechazará el anuncio.
        /// </summary>
        public async Task AnunciarseAlParAsync(string urlPar, string miUrlPublica, string? tokenInvitacion = null)
        {
            try
            {
                using var http = new System.Net.Http.HttpClient { Timeout = TimeSpan.FromSeconds(8) };
                object datos = string.IsNullOrEmpty(tokenInvitacion)
                    ? new { url = miUrlPublica }
                    : new { url = miUrlPublica, invitacion = tokenInvitacion };
                var payload = new StringContent(
                    JsonSerializer.Serialize(datos),
                    Encoding.UTF8, "application/json");
                await http.PostAsync($"{urlPar.TrimEnd('/')}/peer", payload).ConfigureAwait(false);
            }
            catch { /* el par puede no estar disponible aún */ }
        }

        /// <summary>
        /// Verifica si el par en <paramref name="urlPar"/> responde al ping.
        /// </summary>
        public static async Task<bool> PingParAsync(string urlPar)
        {
            try
            {
                using var http = new System.Net.Http.HttpClient { Timeout = TimeSpan.FromSeconds(5) };
                var resp = await http.GetAsync($"{urlPar.TrimEnd('/')}/ping").ConfigureAwait(false);
                return resp.IsSuccessStatusCode;
            }
            catch { return false; }
        }

        public void Detener()
        {
            _cts?.Cancel();
            try { _listener?.Stop(); } catch { }
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            Detener();
            _listener?.Close();
        }
    }
}
