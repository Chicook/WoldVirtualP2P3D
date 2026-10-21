using System;
using System.Diagnostics;
using System.IO;
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

        /// <summary>Hosts públicos de túnel SSH, en orden de preferencia.</summary>
        private static readonly (string Nombre, string Args, string Patron)[] Candidatos =
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

        /// <summary>Disparado cuando el túnel publica una (nueva) URL accesible desde Internet.</summary>
        public event Action<string>? UrlObtenida;

        /// <summary>Disparado antes de cada reintento de reconexión (intento, segundos de espera).</summary>
        public event Action<int, int>? Reintentando;

        /// <summary>Disparado cuando el túnel deja de estar activo (caída detectada).</summary>
        public event Action<string>? TunnelMuerto;

        /// <summary>Puerto local al que se reenvía el tráfico entrante del túnel.</summary>
        public int PuertoLocal { get; }

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
                LimpiarHuerfanosAnteriores();

                if (_bucle != null) return Task.CompletedTask;

                _deseaActivo = true;
                _cts = new CancellationTokenSource();
                var token = _cts.Token;
                _bucle = Task.Run(() => BucleAsync(token), token);
            }
            return Task.CompletedTask;
        }

        /// <summary>Bucle de vigilancia: intenta mantener un túnel vivo y se reconecta si cae.</summary>
        private async Task BucleAsync(CancellationToken token)
        {
            int intento = 0;
            int idx = 0;

            while (!token.IsCancellationRequested && QuiereActivo())
            {
                var cand = Candidatos[idx % Candidatos.Length];
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
            string sshExe = @"C:\Windows\System32\OpenSSH\ssh.exe";
            if (!File.Exists(sshExe)) sshExe = "ssh";

            var psi = new ProcessStartInfo
            {
                FileName = sshExe,
                Arguments = string.Format(argsPlantilla, PuertoLocal),
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            Process? proc = null;
            var tcsUrl = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
            var regex = new Regex(patron, RegexOptions.Compiled | RegexOptions.IgnoreCase);

            try
            {
                proc = new Process { StartInfo = psi, EnableRaisingEvents = true };

                void Escanear(string? linea)
                {
                    if (string.IsNullOrWhiteSpace(linea) || tcsUrl.Task.IsCompleted) return;
                    var m = regex.Match(linea);
                    if (!m.Success) return;
                    tcsUrl.TrySetResult(m.Value.Trim().TrimEnd('/'));
                }

                proc.OutputDataReceived += (_, e) => Escanear(e.Data);
                proc.ErrorDataReceived += (_, e) => Escanear(e.Data);

                if (!proc.Start()) return false;

                lock (_sync) _proceso = proc;
                RegistrarPid(proc.Id);

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
                    lock (_sync) _urlPublica = url;
                    Debug.WriteLine($"[P2PTunnel] Túnel activo ({nombre}): {url}");
                    UrlObtenida?.Invoke(url);

                    // Mantener el proceso vivo hasta que muera o se solicite detener.
                    await esperaExit.ConfigureAwait(false);
                    return true;
                }

                return false;
            }
            finally
            {
                MatarProceso(proc);
                lock (_sync)
                {
                    if (ReferenceEquals(_proceso, proc)) _proceso = null;
                }
                OlvidarPid();
            }
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
            OlvidarPid();
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

        // ════════════════════════════════════════════════════════════════════
        //  Control de procesos huérfanos (Windows)
        //  Un .exe single-file no siempre puede limpiar a sus hijos si el usuario
        //  lo mata desde el Administrador de tareas. Persistimos el PID y lo
        //  barremos al arrancar la siguiente vez.
        // ════════════════════════════════════════════════════════════════════

        private static string RutaPid
        {
            get
            {
                string dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D");
                try { Directory.CreateDirectory(dir); } catch { }
                return Path.Combine(dir, "tunnel.pid");
            }
        }

        private static void RegistrarPid(int pid)
        {
            try
            {
                long ticks = 0;
                try { ticks = Process.GetProcessById(pid).StartTime.ToUniversalTime().Ticks; } catch { }
                File.WriteAllText(RutaPid, $"{pid}|{ticks}");
            }
            catch { }
        }

        private static void OlvidarPid()
        {
            try
            {
                string ruta = RutaPid;
                if (File.Exists(ruta)) File.Delete(ruta);
            }
            catch { }
        }

        /// <summary>
        /// Elimina el proceso de túnel dejado por una ejecución anterior que no pudo limpiarse.
        /// Valida nombre de proceso y hora de arranque para no matar un proceso ajeno que
        /// hubiera reciclado el mismo PID.
        /// </summary>
        private static void LimpiarHuerfanosAnteriores()
        {
            try
            {
                string ruta = RutaPid;
                if (!File.Exists(ruta)) return;

                string txt = File.ReadAllText(ruta).Trim();
                OlvidarPid();

                var partes = txt.Split('|');
                if (partes.Length < 1 || !int.TryParse(partes[0], out int pid)) return;

                Process viejo;
                try { viejo = Process.GetProcessById(pid); }
                catch { return; }   // el proceso ya no existe

                string nombreProceso = viejo.ProcessName.ToLowerInvariant();
                bool esTunel = nombreProceso.Contains("ssh") || nombreProceso.Contains("cloudflared");
                if (!esTunel) return;

                if (partes.Length >= 2 && long.TryParse(partes[1], out long ticks) && ticks > 0)
                {
                    long real = viejo.StartTime.ToUniversalTime().Ticks;
                    if (Math.Abs(real - ticks) > TimeSpan.FromSeconds(5).Ticks) return; // PID reciclado
                }

                viejo.Kill(entireProcessTree: true);
                Debug.WriteLine($"[P2PTunnel] Proceso huérfano '{nombreProceso}' (PID {pid}) eliminado al arrancar.");
            }
            catch { }
        }
    }
}
