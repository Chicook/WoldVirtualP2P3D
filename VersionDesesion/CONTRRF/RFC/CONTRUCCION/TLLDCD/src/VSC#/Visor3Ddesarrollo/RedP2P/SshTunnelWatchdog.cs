// ============================================================
//  SshTunnelWatchdog.cs
//  Proyecto : Wold Virtual P2P 3D  (WPF + Godot)
//  Namespace: Visor3D.RedP2P
//
//  Propósito:
//    Supervisión externa y centralizada de TODOS los slots de
//    túnel SSH (p2p, webnodo, dao).  Detecta túneles muertos y
//    los relanza automáticamente con backoff exponencial.
//    Complementa (no reemplaza) a P2PTunnelManager.
//
//  Dependencias: solo BCL — System.Diagnostics.Process, Task, IO.
//  Compilador  : C# 10+, .NET 8, nullable enabled
// ============================================================
#nullable enable

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.RedP2P
{
    // ──────────────────────────────────────────────────────────
    //  Clase de datos: estado de un slot de túnel individual
    // ──────────────────────────────────────────────────────────

    /// <summary>
    /// Captura el estado observable de un slot de túnel SSH
    /// en un instante dado.
    /// </summary>
    public sealed class TunnelSlotEstado
    {
        /// <summary>Nombre del slot: "p2p", "webnodo" o "dao".</summary>
        public string Nombre { get; init; } = string.Empty;

        /// <summary>True si el proceso SSH está vivo y la URL pública es conocida.</summary>
        public bool Activo { get; init; }

        /// <summary>URL pública asignada por el servicio de túnel, o null.</summary>
        public string? UrlPublica { get; init; }

        /// <summary>Último mensaje de error capturado, o null.</summary>
        public string? UltimoError { get; init; }

        /// <summary>Número acumulado de reconexiones automáticas en esta sesión.</summary>
        public int Reconexiones { get; init; }

        /// <summary>Momento del último cambio de estado (UTC).</summary>
        public DateTimeOffset UltimaActividad { get; init; }
    }

    // ──────────────────────────────────────────────────────────
    //  Clase interna: contexto mutable de cada slot
    // ──────────────────────────────────────────────────────────

    /// <summary>
    /// Estado mutable de un slot de túnel. Solo se accede dentro de
    /// <see cref="SshTunnelWatchdog"/> y siempre protegido por su lock.
    /// </summary>
    internal sealed class SlotContext
    {
        internal string Nombre { get; }
        internal int PuertoLocal { get; }

        internal bool Activo;
        internal string? UrlPublica;
        internal string? UltimoError;
        internal int Reconexiones;
        internal DateTimeOffset UltimaActividad = DateTimeOffset.UtcNow;
        internal Process? Proceso;

        internal SlotContext(string nombre, int puertoLocal)
        {
            Nombre = nombre;
            PuertoLocal = puertoLocal;
        }

        /// <summary>Toma una instantánea inmutable del estado actual.</summary>
        internal TunnelSlotEstado Snapshot() => new()
        {
            Nombre         = Nombre,
            Activo         = Activo,
            UrlPublica     = UrlPublica,
            UltimoError    = UltimoError,
            Reconexiones   = Reconexiones,
            UltimaActividad = UltimaActividad
        };
    }

    // ──────────────────────────────────────────────────────────
    //  Clase principal: SshTunnelWatchdog
    // ──────────────────────────────────────────────────────────

    /// <summary>
    /// <para>
    /// Watchdog centralizado que supervisa y relanza automáticamente
    /// los tres slots de túnel SSH del proyecto Wold Virtual P2P 3D:
    /// <c>p2p</c>, <c>webnodo</c> y <c>dao</c>.
    /// </para>
    /// <para>
    /// Características principales:
    /// <list type="bullet">
    ///   <item>Monitorización continua de los tres slots.</item>
    ///   <item>Reintento con backoff exponencial (5 → 10 → 20 → 30 s máx.).</item>
    ///   <item>Opciones SSH completas en todas las rutas, incluyendo
    ///         <c>ServerAliveCountMax=3</c> y <c>ExitOnForwardFailure=yes</c>.</item>
    ///   <item>Regex correcta para localhost.run: <c>lhr.life</c>.</item>
    ///   <item>Log a fichero en <c>%LOCALAPPDATA%\WoldVirtualP2P3D\tunnel-watchdog.log</c>.</item>
    ///   <item>Endpoint de estado en memoria (<see cref="ObtenerEstadoJson"/>).</item>
    ///   <item>Thread-safe (CancellationToken + lock).</item>
    ///   <item>Implementa <see cref="IDisposable"/>.</item>
    /// </list>
    /// </para>
    /// </summary>
    public sealed class SshTunnelWatchdog : IDisposable
    {
        // ── Constantes de configuración ───────────────────────

        /// <summary>Espera inicial entre reintentos (segundos).</summary>
        private const int BackoffInicialSeg = 5;

        /// <summary>Tope máximo del backoff exponencial (segundos).</summary>
        private const int BackoffMaxSeg = 30;

        /// <summary>Tiempo máximo esperando que aparezca la URL pública (ms).</summary>
        private const int TimeoutUrlMs = 25_000;

        /// <summary>Opciones SSH comunes a todos los candidatos.</summary>
        private const string OpcionesSshComunes =
            "-o StrictHostKeyChecking=no " +
            "-o UserKnownHostsFile=NUL " +
            "-o ServerAliveInterval=30 " +
            "-o ServerAliveCountMax=3 " +
            "-o ConnectTimeout=15 " +
            "-o ExitOnForwardFailure=yes";

        /// <summary>
        /// Candidatos de servicio de túnel, en orden de preferencia.
        /// {0} = puerto local.
        /// </summary>
        private static readonly (string Nombre, string ArgsTemplate, string Patron)[] Candidatos =
        {
            (
                "localhost.run",
                // Regex corregida: lhr.life (no lhr.rocks)
                OpcionesSshComunes + " -R 80:localhost:{0} nokey@localhost.run",
                @"https?://[\w\-]+\.lhr\.life"
            ),
            (
                "serveo.net",
                OpcionesSshComunes + " -R 80:localhost:{0} serveo.net",
                @"https?://[\w\-]+\.serveo\.net"
            )
        };

        // ── Rutas de log ──────────────────────────────────────

        /// <summary>Ruta completa del fichero de log de watchdog (T2-04).</summary>
        private static readonly string RutaLog = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P3D",
            "logs",
            "tunnel.log");

        // ── Estado interno ────────────────────────────────────

        private readonly object _sync = new();
        private readonly SlotContext[] _slots;
        private CancellationTokenSource? _cts;
        private bool _disposeado;
        private bool _iniciado;

        // ── Eventos públicos ──────────────────────────────────

        /// <summary>
        /// Disparado cuando un slot obtiene una URL pública activa.
        /// Parámetros: nombre del slot, URL.
        /// </summary>
        public event Action<string, string>? UrlObtenida;

        /// <summary>
        /// Disparado cuando un slot pierde la conexión.
        /// Parámetro: nombre del slot.
        /// </summary>
        public event Action<string>? TunnelCaido;

        // ── Constructor ───────────────────────────────────────

        /// <summary>
        /// Inicializa el watchdog con los puertos locales de cada slot.
        /// </summary>
        /// <param name="puertoLocalP2P">Puerto local del slot p2p (por defecto 7890).</param>
        /// <param name="puertoLocalWebNodo">Puerto local del slot webnodo (por defecto 7891).</param>
        /// <param name="puertoLocalDao">Puerto local del slot dao (por defecto 7892).</param>
        public SshTunnelWatchdog(
            int puertoLocalP2P    = 7890,
            int puertoLocalWebNodo = 7891,
            int puertoLocalDao    = 7892)
        {
            _slots = new[]
            {
                new SlotContext("p2p",     puertoLocalP2P),
                new SlotContext("webnodo", puertoLocalWebNodo),
                new SlotContext("dao",     puertoLocalDao)
            };

            // Crear el directorio de log si no existe.
            try
            {
                var dir = Path.GetDirectoryName(RutaLog);
                if (!string.IsNullOrEmpty(dir))
                    Directory.CreateDirectory(dir);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Watchdog] No se pudo crear directorio de log: {ex.Message}");
            }

            Log("=== SshTunnelWatchdog instanciado ===");
        }

        // ── API pública ───────────────────────────────────────

        /// <summary>
        /// Suscribe el watchdog al evento <see cref="P2PTunnelManager.TunnelMuerto"/>
        /// del manager existente, para que actúe como supervisión externa coordinada.
        /// </summary>
        /// <param name="manager">Instancia de <see cref="P2PTunnelManager"/> ya creada.</param>
        public void SuscribirA(P2PTunnelManager manager)
        {
            if (manager is null) throw new ArgumentNullException(nameof(manager));
            manager.TunnelMuerto += nombreCandidato =>
                Log($"[Watchdog] P2PTunnelManager reportó TunnelMuerto desde candidato '{nombreCandidato}'.");
        }

        /// <summary>
        /// Arranca el watchdog de forma no bloqueante.
        /// Idempotente: si ya está activo no hace nada.
        /// </summary>
        /// <param name="ct">Token de cancelación externo opcional.</param>
        public Task IniciarAsync(CancellationToken ct = default)
        {
            lock (_sync)
            {
                if (_disposeado || _iniciado) return Task.CompletedTask;
                _iniciado = true;
                _cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            }

            var token = _cts!.Token;
            Log("Iniciando watchdog…");

            // Lanza una tarea de vigilancia por cada slot, en paralelo.
            foreach (var slot in _slots)
            {
                var s = slot; // captura local para la lambda
                _ = Task.Run(() => BucleSlotAsync(s, token), token);
            }

            return Task.CompletedTask;
        }

        /// <summary>
        /// Detiene el watchdog y mata todos los procesos SSH supervisados.
        /// Idempotente y seguro aunque nunca se haya iniciado.
        /// </summary>
        public void Detener()
        {
            CancellationTokenSource? cts;
            lock (_sync)
            {
                _iniciado = false;
                cts = _cts;
                _cts = null;
            }

            try { cts?.Cancel(); } catch { }

            // Matar todos los procesos SSH activos.
            lock (_sync)
            {
                foreach (var slot in _slots)
                    MatarProceso(slot.Proceso);
            }

            try { cts?.Dispose(); } catch { }
            Log("Watchdog detenido.");
        }

        /// <summary>
        /// Devuelve un JSON plano con el estado actual de todos los slots.
        /// No usa System.Text.Json para evitar dependencias extra; el
        /// formato es suficiente para logging y diagnóstico.
        /// </summary>
        /// <returns>Cadena JSON con array de estados de slot.</returns>
        public string ObtenerEstadoJson()
        {
            TunnelSlotEstado[] snapshots;
            lock (_sync)
            {
                snapshots = new TunnelSlotEstado[_slots.Length];
                for (int i = 0; i < _slots.Length; i++)
                    snapshots[i] = _slots[i].Snapshot();
            }

            var sb = new StringBuilder();
            sb.AppendLine("{");
            sb.AppendLine($"  \"timestamp\": \"{DateTimeOffset.UtcNow:O}\",");
            sb.AppendLine("  \"slots\": [");

            for (int i = 0; i < snapshots.Length; i++)
            {
                var s = snapshots[i];
                sb.AppendLine("    {");
                sb.AppendLine($"      \"nombre\": {JsonStr(s.Nombre)},");
                sb.AppendLine($"      \"activo\": {(s.Activo ? "true" : "false")},");
                sb.AppendLine($"      \"urlPublica\": {JsonStr(s.UrlPublica)},");
                sb.AppendLine($"      \"ultimoError\": {JsonStr(s.UltimoError)},");
                sb.AppendLine($"      \"reconexiones\": {s.Reconexiones},");
                sb.AppendLine($"      \"ultimaActividad\": \"{s.UltimaActividad:O}\"");
                sb.Append("    }");
                if (i < snapshots.Length - 1) sb.AppendLine(",");
                else sb.AppendLine();
            }

            sb.AppendLine("  ]");
            sb.Append("}");
            return sb.ToString();
        }

        // ── Bucle de vigilancia por slot ──────────────────────

        /// <summary>
        /// Bucle de vigilancia dedicado a un único slot.
        /// Se ejecuta en un Task de fondo; re-lanza el túnel con
        /// backoff exponencial hasta que se cancele.
        /// </summary>
        private async Task BucleSlotAsync(SlotContext slot, CancellationToken token)
        {
            TunnelProcessRegistry.BarrerHuerfano(slot.Nombre);
            Log($"[{slot.Nombre}] Bucle iniciado (puerto local {slot.PuertoLocal}).");
            int intento = 0;
            int candidatoIdx = 0;

            while (!token.IsCancellationRequested)
            {
                var cand = Candidatos[candidatoIdx % Candidatos.Length];
                candidatoIdx++;

                bool tuvoUrl = false;
                try
                {
                    tuvoUrl = await EjecutarIntentoAsync(slot, cand.Nombre, cand.ArgsTemplate, cand.Patron, token)
                        .ConfigureAwait(false);
                }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    lock (_sync)
                    {
                        slot.UltimoError    = ex.Message;
                        slot.UltimaActividad = DateTimeOffset.UtcNow;
                    }
                    Log($"[{slot.Nombre}] Excepción en intento '{cand.Nombre}': {ex.Message}");
                }

                if (token.IsCancellationRequested) break;

                // El túnel ha caído o nunca se estableció.
                bool eraPrevActivo;
                lock (_sync)
                {
                    eraPrevActivo    = slot.Activo;
                    slot.Activo      = false;
                    slot.UrlPublica  = null;
                    slot.UltimaActividad = DateTimeOffset.UtcNow;
                }

                if (eraPrevActivo)
                {
                    Log($"[{slot.Nombre}] Túnel caído. Disparando TunnelCaido.");
                    TunnelCaido?.Invoke(slot.Nombre);
                }

                // Backoff exponencial: si tuvo URL reiniciamos desde intento=1,
                // si nunca llegó a conectar incrementamos.
                intento = tuvoUrl ? 1 : intento + 1;
                int espera = (int)Math.Min(BackoffMaxSeg, BackoffInicialSeg * Math.Pow(2, Math.Min(intento - 1, 4)));

                lock (_sync)
                {
                    slot.Reconexiones++;
                    slot.UltimaActividad = DateTimeOffset.UtcNow;
                }

                Log($"[{slot.Nombre}] Reintento {intento} en {espera}s (candidato siguiente: {Candidatos[candidatoIdx % Candidatos.Length].Nombre}).");

                try
                {
                    await Task.Delay(TimeSpan.FromSeconds(espera), token).ConfigureAwait(false);
                }
                catch (OperationCanceledException) { break; }
            }

            Log($"[{slot.Nombre}] Bucle finalizado.");
        }

        // ── Intento individual de conexión ────────────────────

        /// <summary>
        /// Lanza el proceso SSH para un candidato concreto.
        /// Devuelve <c>true</c> si llegó a publicar URL (el túnel
        /// estuvo activo, aunque luego se cayera).
        /// </summary>
        private async Task<bool> EjecutarIntentoAsync(
            SlotContext slot,
            string nombreCandidato,
            string argsTemplate,
            string patron,
            CancellationToken token)
        {
            string sshExe = @"C:\Windows\System32\OpenSSH\ssh.exe";
            if (!File.Exists(sshExe)) sshExe = "ssh";

            string args = string.Format(argsTemplate, slot.PuertoLocal);

            var psi = new ProcessStartInfo
            {
                FileName               = sshExe,
                Arguments              = args,
                UseShellExecute        = false,
                CreateNoWindow         = true,
                RedirectStandardOutput = true,
                RedirectStandardError  = true
            };

            var regex  = new Regex(patron, RegexOptions.Compiled | RegexOptions.IgnoreCase);
            var tcsUrl = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);

            Log($"[{slot.Nombre}] Iniciando proceso SSH → {nombreCandidato} (puerto {slot.PuertoLocal}).");

            Process? proc = null;
            try
            {
                proc = new Process { StartInfo = psi, EnableRaisingEvents = true };

                // Escanea stdout/stderr buscando la URL pública.
                void Escanear(string? linea)
                {
                    if (string.IsNullOrWhiteSpace(linea) || tcsUrl.Task.IsCompleted) return;
                    var m = regex.Match(linea);
                    if (!m.Success) return;
                    tcsUrl.TrySetResult(m.Value.Trim().TrimEnd('/'));
                }

                proc.OutputDataReceived += (_, e) => Escanear(e.Data);
                proc.ErrorDataReceived  += (_, e) => Escanear(e.Data);

                if (!proc.Start())
                {
                    Log($"[{slot.Nombre}] Process.Start() devolvió false para '{nombreCandidato}'.");
                    return false;
                }

                lock (_sync) slot.Proceso = proc;
                TunnelProcessRegistry.Persistir(slot.Nombre, proc.Id);

                proc.BeginOutputReadLine();
                proc.BeginErrorReadLine();

                var esperaExit    = proc.WaitForExitAsync(CancellationToken.None);
                // Suprimir UnobservedTaskException si la tarea se abandona.
                _ = esperaExit.ContinueWith(t => { _ = t.Exception; }, TaskContinuationOptions.OnlyOnFaulted);

                var esperaTimeout = Task.Delay(TimeoutUrlMs, token);
                var ganador       = await Task.WhenAny(tcsUrl.Task, esperaExit, esperaTimeout)
                                              .ConfigureAwait(false);

                if (ganador == tcsUrl.Task && tcsUrl.Task.Status == TaskStatus.RanToCompletion)
                {
                    string url = tcsUrl.Task.Result;

                    lock (_sync)
                    {
                        slot.Activo          = true;
                        slot.UrlPublica      = url;
                        slot.UltimoError     = null;
                        slot.UltimaActividad = DateTimeOffset.UtcNow;
                    }

                    Log($"[{slot.Nombre}] Túnel ACTIVO ({nombreCandidato}): {url}");
                    UrlObtenida?.Invoke(slot.Nombre, url);

                    // Esperar a que el proceso muera o se cancele.
                    await esperaExit.ConfigureAwait(false);
                    return true;
                }

                if (token.IsCancellationRequested)
                    Log($"[{slot.Nombre}] Cancelado mientras esperaba URL de '{nombreCandidato}'.");
                else if (ganador == esperaExit)
                    Log($"[{slot.Nombre}] Proceso SSH terminó antes de publicar URL ({nombreCandidato}).");
                else
                    Log($"[{slot.Nombre}] Timeout esperando URL de '{nombreCandidato}' ({TimeoutUrlMs / 1000}s).");

                return false;
            }
            finally
            {
                tcsUrl.TrySetCanceled();
                MatarProceso(proc);
                TunnelProcessRegistry.Olvidar(slot.Nombre);
                lock (_sync)
                {
                    if (ReferenceEquals(slot.Proceso, proc))
                    {
                        slot.Proceso    = null;
                        slot.Activo     = false;
                        slot.UrlPublica = null;
                    }
                }
            }
        }

        // ── Utilidades ────────────────────────────────────────

        /// <summary>Mata un proceso SSH de forma defensiva.</summary>
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

        /// <summary>
        /// Escribe una línea en el log de fichero y en Debug.
        /// Thread-safe por el lock interno de StreamWriter.
        /// </summary>
        private static void Log(string mensaje)
        {
            string linea = $"[{DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss zzz}] {mensaje}";
            Debug.WriteLine(linea);
            try
            {
                // Append para conservar historial entre sesiones.
                File.AppendAllText(RutaLog, linea + Environment.NewLine, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Watchdog] Error escribiendo log: {ex.Message}");
            }
        }

        /// <summary>
        /// Serializa un string como valor JSON con comillas y escaping básico,
        /// o "null" si el valor es null.
        /// </summary>
        private static string JsonStr(string? valor)
        {
            if (valor is null) return "null";
            return "\"" + valor.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
        }

        // ── IDisposable ───────────────────────────────────────

        /// <inheritdoc/>
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
