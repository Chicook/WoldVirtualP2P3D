using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Gestiona un túnel SSH inverso efímero hacia servicios públicos (localhost.run / serveo.net)
    /// utilizando el cliente OpenSSH de Windows, sin instalaciones adicionales.
    ///
    /// Características:
    ///  · Arranque asíncrono: <see cref="IniciarAsync"/> devuelve el control de inmediato; la URL
    ///    pública se comunica por el evento <see cref="UrlObtenida"/>.
    ///  · Reconexión automática con backoff exponencial (máx. 30 s) si el proceso SSH muere o no
    ///    consigue publicar la URL.
    ///  · Control de procesos huérfanos: el PID se persiste en disco y se barren los restos de una
    ///    ejecución anterior (crash / cierre forzado) al arrancar. Al detenerse se mata el árbol
    ///    completo de procesos.
    /// </summary>
    public class P2PTunnelManager : IDisposable
    {
        private const int TimeoutUrlMs = 25_000;   // tiempo máximo esperando la URL pública
        private const int BackoffMaxSeg = 30;      // tope del backoff entre reconexiones
        private const string Slot = "p2p";         // identificador del PID persistido en disco

        /// <summary>Proveedores SSH de respaldo si Cloudflare no está disponible.</summary>
        private static readonly (string Nombre, string Args, string Patron)[] CandidatosSsh =
        {
            ("localhost.run",
             "-o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ConnectTimeout=15 -o ExitOnForwardFailure=yes -R 80:localhost:{0} nokey@localhost.run",
             @"https?://[^\s]+\.lhr\.life[^\s]*"),
            ("serveo.net",
             "-o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ConnectTimeout=15 -o ExitOnForwardFailure=yes -R 80:localhost:{0} serveo.net",
             @"https?://[^\s]+\.serveo\.net[^\s]*")
        };

        private readonly object _sync = new();
        private Process? _proceso;
        private CancellationTokenSource? _cts;
        private Task? _bucle;
        private bool _disposeado;
        private bool _deseaActivo;
        private string? _urlPublica;
        private string? _ultimoFallo;

        /// <summary>Disparado cuando el túnel publica una (nueva) URL accesible desde Internet.</summary>
        public event Action<string>? UrlObtenida;

        /// <summary>Disparado antes de cada reintento de reconexión (intento, segundos de espera).</summary>
        public event Action<int, int>? Reintentando;

        /// <summary>Disparado cuando el túnel deja de estar activo (caída detectada).</summary>
        public event Action<string>? TunnelMuerto;

        /// <summary>Motivo del último fallo de conexión, útil para diagnóstico en la vista previa.</summary>
        public event Action<string>? FalloConexion;

        /// <summary>Puerto local al que se reenvía el tráfico entrante del túnel.</summary>
        public int PuertoLocal { get; }

        public bool EsModoDegradado => ProveedorActivo != null && ProveedorActivo != "Cloudflare Quick Tunnel";
        public string? ProveedorActivo { get; private set; }

        public string? UltimoFallo
        {
            get { lock (_sync) return _ultimoFallo; }
        }

        /// <summary>Última URL pública conocida, o <c>null</c> si aún no está lista.</summary>
        public string? UrlPublica
        {
            get { lock (_sync) return _urlPublica; }
        }

        /// <summary>True si hay proceso SSH vivo y URL pública publicada.</summary>
        public bool Activo
        {
            get
            {
                lock (_sync)
                    return _urlPublica != null && _proceso != null && !_proceso.HasExited;
            }
        }

        public P2PTunnelManager(int puertoLocal = 7890)
        {
            PuertoLocal = puertoLocal;
        }

        /// <summary>
        /// Arranca (de forma no bloqueante) el bucle de vigilancia del túnel. Es idempotente:
        /// si ya hay un bucle activo no hace nada.
        /// </summary>
        public Task IniciarAsync()
        {
            lock (_sync)
            {
                if (_disposeado) return Task.CompletedTask;

                // Barrido de restos de una ejecución previa que no pudo limpiarse (crash).
                TunnelProcessRegistry.BarrerHuerfano(Slot);

                if (_bucle != null) return Task.CompletedTask;

                _deseaActivo = true;
                _cts = new CancellationTokenSource();
                var token = _cts.Token;
                _bucle = Task.Run(() => BucleAsync(token), token);
            }
            return Task.CompletedTask;
        }

        /// <summary>Reinicia el administrador del túnel auxiliar y espera el cierre del bucle anterior.</summary>
        public async Task ReiniciarAsync()
        {
            Task? bucleAnterior;
            lock (_sync) bucleAnterior = _bucle;
            Detener();

            if (bucleAnterior != null)
            {
                try { await bucleAnterior.WaitAsync(TimeSpan.FromSeconds(5)).ConfigureAwait(false); }
                catch (TimeoutException) { }
                catch (OperationCanceledException) { }
            }

            await IniciarAsync().ConfigureAwait(false);
        }

        /// <summary>Bucle de vigilancia: intenta mantener un túnel vivo y se reconecta si cae.</summary>
        private async Task BucleAsync(CancellationToken token)
        {
            int intento = 0;
            int idx = 0;

            while (!token.IsCancellationRequested && QuiereActivo())
            {
                var candidatos = ObtenerCandidatos();
                var cand = candidatos[idx % candidatos.Length];
                idx++;

                bool establecido = false;
                try
                {
                    establecido = await EjecutarIntentoAsync(cand.Nombre, cand.Args, cand.Patron, token)
                        .ConfigureAwait(false);
                }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[P2PTunnel] Error en intento '{cand.Nombre}': {ex.Message}");
                    RegistrarFallo($"{cand.Nombre}: {ex.Message}");
                }

                if (token.IsCancellationRequested || !QuiereActivo()) break;

                // Si llegamos aquí, el túnel ya no está operativo (nunca se estableció o se cayó).
                lock (_sync) _urlPublica = null;
                TunnelMuerto?.Invoke(cand.Nombre);

                // Tras una sesión que funcionó, reiniciamos el contador; si falló, incrementamos.
                intento = establecido ? 1 : intento + 1;
                int espera = (int)Math.Min(BackoffMaxSeg, Math.Pow(2, Math.Min(intento, 5)));
                Reintentando?.Invoke(intento, espera);

                try
                {
                    await Task.Delay(TimeSpan.FromSeconds(espera), token).ConfigureAwait(false);
                }
                catch (OperationCanceledException) { break; }
            }
        }

        /// <summary>
        /// Ejecuta un intento de túnel con un host concreto. Devuelve <c>true</c> si llegó a
        /// publicar la URL (el túnel estuvo operativo, aunque luego se cayera).
        /// </summary>
        private async Task<bool> EjecutarIntentoAsync(string nombre, string argsPlantilla, string patron, CancellationToken token)
        {
            var proveedor = ObtenerProveedor(nombre);
            if (proveedor is null)
            {
                string error = nombre == "Cloudflare Quick Tunnel"
                    ? "No encuentro cloudflared.exe. Revisa CLOUDFLARED_EXE en el lanzador de vista previa."
                    : "No encuentro el cliente OpenSSH (ssh.exe).";
                RegistrarFallo(error);
                return false;
            }

            var psi = new ProcessStartInfo
            {
                FileName = proveedor,
                Arguments = string.Format(argsPlantilla, PuertoLocal),
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            Process? proc = null;
            var tcsUrl = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
            var regex = new Regex(patron, RegexOptions.Compiled | RegexOptions.IgnoreCase);
            var ultimasLineas = new System.Collections.Concurrent.ConcurrentQueue<string>();

            try
            {
                proc = new Process { StartInfo = psi, EnableRaisingEvents = true };

                void Escanear(string? linea)
                {
                    if (string.IsNullOrWhiteSpace(linea)) return;
                    ultimasLineas.Enqueue(linea.Trim());
                    while (ultimasLineas.Count > 8) ultimasLineas.TryDequeue(out _);
                    if (tcsUrl.Task.IsCompleted) return;
                    var m = regex.Match(linea);
                    if (!m.Success) return;
                    tcsUrl.TrySetResult(m.Value.Trim().TrimEnd('/'));
                }

                proc.OutputDataReceived += (_, e) => Escanear(e.Data);
                proc.ErrorDataReceived += (_, e) => Escanear(e.Data);

                if (!proc.Start()) return false;

                lock (_sync) _proceso = proc;
                TunnelProcessRegistry.Persistir(Slot, proc.Id);

                proc.BeginOutputReadLine();
                proc.BeginErrorReadLine();

                var esperaExit = proc.WaitForExitAsync(CancellationToken.None);
                // Observar la tarea para evitar UnobservedTaskException si el proceso se libera antes.
                _ = esperaExit.ContinueWith(t => { _ = t.Exception; }, TaskContinuationOptions.OnlyOnFaulted);

                var esperaTimeout = Task.Delay(TimeoutUrlMs, token);
                var ganador = await Task.WhenAny(tcsUrl.Task, esperaExit, esperaTimeout).ConfigureAwait(false);

                if (ganador == tcsUrl.Task && tcsUrl.Task.Status == TaskStatus.RanToCompletion)
                {
                    string url = tcsUrl.Task.Result;
                    lock (_sync)
                    {
                        _urlPublica = url;
                        ProveedorActivo = nombre;
                    }
                    string modo = EsModoDegradado ? "Modo degradado (SSH gratuito)" : "Cloudflare Túnel";
                    Debug.WriteLine($"[P2PTunnel] Túnel activo ({nombre}): {url} [{modo}]");
                    TunnelLogger.Escribir("p2p", $"Túnel activo ({nombre}): {url} [{modo}]");
                    UrlObtenida?.Invoke(url);

                    // Mantener el proceso vivo hasta que muera o se solicite detener.
                    await esperaExit.ConfigureAwait(false);
                    return true;
                }

                string detalle = string.Join(" | ", ultimasLineas.ToArray().TakeLast(4));
                if (string.IsNullOrWhiteSpace(detalle))
                    detalle = ganador == esperaExit
                        ? $"El proceso terminó sin publicar una URL (código {(proc.HasExited ? proc.ExitCode.ToString() : "desconocido")})."
                        : $"No publicó URL en {TimeoutUrlMs / 1000} s.";
                RegistrarFallo($"{nombre}: {detalle}");

                return false;
            }
            finally
            {
                MatarProceso(proc);
                lock (_sync)
                {
                    if (ReferenceEquals(_proceso, proc)) _proceso = null;
                }
                TunnelProcessRegistry.Olvidar(Slot);
            }
        }

        private static (string Nombre, string Args, string Patron)[] ObtenerCandidatos()
        {
            string preferencia = Environment.GetEnvironmentVariable("WVP_TUNNEL_PROVIDER") ?? "";
            var cloudflare = ("Cloudflare Quick Tunnel",
                "tunnel --no-autoupdate --url http://127.0.0.1:{0}",
                @"https://[a-z0-9-]+\.trycloudflare\.com");
            var ssh = CandidatosSsh;

            if (preferencia.Equals("cloudflare", StringComparison.OrdinalIgnoreCase))
                return new[] { cloudflare };
            if (preferencia.Equals("ssh", StringComparison.OrdinalIgnoreCase))
                return ssh;
            return (EncontrarCloudflared() is not null ? new[] { cloudflare } : Array.Empty<(string, string, string)>())
                .Concat(ssh).ToArray();
        }

        private void RegistrarFallo(string detalle)
        {
            lock (_sync) _ultimoFallo = detalle;
            FalloConexion?.Invoke(detalle);
        }

        private static string? ObtenerProveedor(string nombre)
        {
            if (nombre == "Cloudflare Quick Tunnel") return EncontrarCloudflared();
            string ssh = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "OpenSSH", "ssh.exe");
            return File.Exists(ssh) ? ssh : "ssh";
        }

        private static string? EncontrarCloudflared()
        {
            string? configurado = Environment.GetEnvironmentVariable("CLOUDFLARED_EXE");
            string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string[] candidatos =
            [
                configurado ?? "",
                Path.Combine(localApp, "WoldVirtualP2P3D", "bin", "cloudflared.exe"),
                Path.Combine(AppContext.BaseDirectory, "cloudflared.exe"),
                "cloudflared"
            ];
            return candidatos.FirstOrDefault(p => !string.IsNullOrWhiteSpace(p) && (p == "cloudflared" || File.Exists(p)));
        }

        /// <summary>Mata y libera un proceso de túnel de forma defensiva.</summary>
        private static void MatarProceso(Process? proc)
        {
            try
            {
                if (proc != null && !proc.HasExited)
                    proc.Kill(entireProcessTree: true);
            }
            catch { }
            try { proc?.Dispose(); } catch { }
        }

        private bool QuiereActivo()
        {
            lock (_sync) return _deseaActivo && !_disposeado;
        }

        /// <summary>
        /// Detiene el túnel y libera puertos/procesos. Idempotente y seguro de llamar
        /// aunque nunca se haya iniciado.
        /// </summary>
        public void Detener()
        {
            CancellationTokenSource? cts;
            Process? proc;
            lock (_sync)
            {
                _deseaActivo = false;
                cts = _cts; _cts = null;
                proc = _proceso; _proceso = null;
                _bucle = null;
                _urlPublica = null;
            }

            try { cts?.Cancel(); } catch { }
            MatarProceso(proc);
            try { cts?.Dispose(); } catch { }
            TunnelProcessRegistry.Olvidar(Slot);
        }

        public void Dispose()
        {
            lock (_sync)
            {
                if (_disposeado) return;
                _disposeado = true;
            }
            Detener();
        }
    }
}
