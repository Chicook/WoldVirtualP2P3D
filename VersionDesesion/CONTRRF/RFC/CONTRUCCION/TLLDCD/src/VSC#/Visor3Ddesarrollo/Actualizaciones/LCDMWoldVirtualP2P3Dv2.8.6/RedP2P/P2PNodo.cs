using System;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Servidor HTTP embebido minimalista que actúa como nodo P2P del visor.
    /// Escucha en <see cref="Puerto"/> y responde a:
    ///   GET /ping  → "pong" (keepalive/descubrimiento)
    ///   GET /info  → JSON con info del nodo
    ///   POST /peer → recibe la URL de un par remoto
    /// </summary>
    public class P2PNodo : IDisposable
    {
        private HttpListener? _listener;
        private CancellationTokenSource? _cts;
        private bool _disposed;
        private readonly string _nombreUsuario;

        public int Puerto { get; }

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
                var info = new
                {
                    nodo    = _nombreUsuario,
                    version = "0.1.0",
                    puerto  = Puerto,
                    pares   = Pares.Count
                };
                respuesta = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(info));
            }
            else if (ruta == "/peer" && ctx.Request.HttpMethod == "POST")
            {
                // Registrar par remoto
                using var reader = new System.IO.StreamReader(ctx.Request.InputStream, Encoding.UTF8);
                string body = await reader.ReadToEndAsync().ConfigureAwait(false);
                try
                {
                    using var doc = JsonDocument.Parse(body);
                    if (doc.RootElement.TryGetProperty("url", out var urlProp))
                    {
                        string? urlPar = urlProp.GetString();
                        if (!string.IsNullOrWhiteSpace(urlPar) && !Pares.Contains(urlPar!))
                        {
                            Pares.Add(urlPar!);
                            NuevoPar?.Invoke(urlPar!);
                        }
                    }
                }
                catch { }

                ctx.Response.StatusCode = 200;
                respuesta = Encoding.UTF8.GetBytes("{\"status\":\"ok\"}");
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
        /// Intenta contactar al par en <paramref name="urlPar"/> para anunciarse.
        /// </summary>
        public async Task AnunciarseAlParAsync(string urlPar, string miUrlPublica)
        {
            try
            {
                using var http = new System.Net.Http.HttpClient { Timeout = TimeSpan.FromSeconds(8) };
                var payload = new StringContent(
                    JsonSerializer.Serialize(new { url = miUrlPublica }),
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
