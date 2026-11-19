// ============================================================
//  P2PTunnelSupervisor.cs
//  Proyecto : Wold Virtual P2P 3D  (WPF + Godot)
//  Namespace: Visor3D.RedP2P
//
//  Propósito (F1 · T2-01 a T2-06):
//    Supervisor unificado de TODOS los túneles del ecosistema:
//      - "p2p"     : API P2P local (puerto 7890)
//      - "webnodo" : Portal metaverso (puerto 8082 / 8083)
//      - "dao"     : Conexión DAO 3D (puerto 7892)
//
//    Características:
//      - Centraliza PIDs en TunnelProcessRegistry (T2-02).
//      - Observabilidad unificada en %LOCALAPPDATA%\WoldVirtualP2P3D\logs\tunnel.log (T2-04).
//      - Detección segura de cloudflared en %LOCALAPPDATA%\WoldVirtualP2P3D\bin\ (T2-01).
//      - Watchdog con reconexión automática y backoff exponencial para WebNodo y p2p (T2-03).
//      - Detección y reporte de «Modo degradado (SSH gratuito)» vs «Cloudflare» para UI (T2-06).
// ============================================================
#nullable enable

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.RedP2P
{
    /// <summary>
    /// Logger centralizado para observabilidad de túneles (T2-04).
    /// Escribe en %LOCALAPPDATA%\WoldVirtualP2P3D\logs\tunnel.log.
    /// </summary>
    public static class TunnelLogger
    {
        private static readonly object _sync = new();
        private static readonly string LogDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P3D",
            "logs");

        public static string LogPath => Path.Combine(LogDir, "tunnel.log");

        static TunnelLogger()
        {
            try
            {
                if (!Directory.Exists(LogDir))
                    Directory.CreateDirectory(LogDir);
            }
            catch { }
        }

        public static void Escribir(string slot, string mensaje, string nivel = "INFO")
        {
            string stamp = DateTimeOffset.Now.ToString("yyyy-MM-dd HH:mm:ss.fff zzz");
            string linea = $"[{stamp}] [{slot.ToUpperInvariant()}] [{nivel}] {mensaje}";
            Debug.WriteLine(linea);

            lock (_sync)
            {
                try
                {
                    if (!Directory.Exists(LogDir))
                        Directory.CreateDirectory(LogDir);

                    // Rotación básica si el log supera los 10 MB
                    var fi = new FileInfo(LogPath);
                    if (fi.Exists && fi.Length > 10 * 1024 * 1024)
                    {
                        string old = Path.Combine(LogDir, "tunnel.log.old");
                        if (File.Exists(old)) File.Delete(old);
                        File.Move(LogPath, old);
                    }

                    File.AppendAllText(LogPath, linea + Environment.NewLine, Encoding.UTF8);
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[TunnelLogger] Fallo al escribir log: {ex.Message}");
                }
            }
        }
    }

    /// <summary>
    /// Información pública del estado de un slot bajo supervisión.
    /// </summary>
    public sealed class TunnelSlotInfo
    {
        public string Slot { get; init; } = string.Empty;
        public int PuertoLocal { get; init; }
        public bool Activo { get; init; }
        public string? UrlPublica { get; init; }
        public string Proveedor { get; init; } = "Desconectado";
        public bool EsModoDegradado { get; init; }
        public int Reconexiones { get; init; }
        public string? UltimoFallo { get; init; }
        public DateTimeOffset UltimaActividad { get; init; }
    }

    /// <summary>
    /// Supervisor unificado y watchdog central de túneles efímeros (T2-01 a T2-06).
    /// </summary>
    public sealed class P2PTunnelSupervisor : IDisposable
    {
        private static readonly Lazy<P2PTunnelSupervisor> _instancia =
            new(() => new P2PTunnelSupervisor());

        public static P2PTunnelSupervisor Instancia => _instancia.Value;

        private const int BackoffInicialSeg = 5;
        private const int BackoffMaxSeg = 30;
        private const int TimeoutUrlMs = 25_000;

        private const string OpcionesSshComunes =
            "-o StrictHostKeyChecking=no " +
            "-o UserKnownHostsFile=NUL " +
            "-o ServerAliveInterval=30 " +
            "-o ServerAliveCountMax=3 " +
            "-o ConnectTimeout=15 " +
            "-o ExitOnForwardFailure=yes";

        private static readonly (string Nombre, string ArgsTemplate, string Patron)[] ProveedoresSsh =
        {
            ("localhost.run", OpcionesSshComunes + " -R 80:localhost:{0} nokey@localhost.run", @"https?://[\w\-]+\.lhr\.life"),
            ("serveo.net",     OpcionesSshComunes + " -R 80:localhost:{0} serveo.net",         @"https?://[\w\-]+\.serveo\.net")
        };

        private readonly object _sync = new();
        private readonly Dictionary<string, SlotInterno> _slots = new(StringComparer.OrdinalIgnoreCase);
        private CancellationTokenSource? _cts;
        private bool _disposed;
        private bool _iniciado;

        public event Action<string, string>? UrlObtenida;
        public event Action<string>? TunnelCaido;
        public event Action<string, bool>? ModoDegradadoCambiado;

        private sealed class SlotInterno
        {
            public string Slot { get; }
            public int PuertoLocal { get; set; }
            public bool DeseadoActivo { get; set; }
            public bool Activo { get; set; }
            public string? UrlPublica { get; set; }
            public string Proveedor { get; set; } = "Desconectado";
            public bool EsModoDegradado { get; set; }
            public int Reconexiones { get; set; }
            public string? UltimoFallo { get; set; }
            public DateTimeOffset UltimaActividad { get; set; } = DateTimeOffset.UtcNow;
            public Process? Proceso { get; set; }
            public Task? Bucle { get; set; }

            public SlotInterno(string slot, int puertoLocal)
            {
                Slot = slot;
                PuertoLocal = puertoLocal;
            }

            public TunnelSlotInfo ToSnapshot() => new()
            {
                Slot = Slot,
                PuertoLocal = PuertoLocal,
                Activo = Activo,
                UrlPublica = UrlPublica,
                Proveedor = Proveedor,
                EsModoDegradado = EsModoDegradado,
                Reconexiones = Reconexiones,
                UltimoFallo = UltimoFallo,
                UltimaActividad = UltimaActividad
            };
        }

        public P2PTunnelSupervisor()
        {
            RegistrarSlot("p2p", 7890);
            RegistrarSlot("webnodo", 8082);
            RegistrarSlot("dao", 7892);
            TunnelLogger.Escribir("supervisor", "Supervisor unificado instanciado correctamente.");
        }

        public void RegistrarSlot(string slot, int puertoLocal)
        {
            lock (_sync)
            {
                if (!_slots.ContainsKey(slot))
                {
                    _slots[slot] = new SlotInterno(slot, puertoLocal);
                    TunnelProcessRegistry.BarrerHuerfano(slot);
                }
                else
                {
                    _slots[slot].PuertoLocal = puertoLocal;
                }
            }
        }

        public Task IniciarSupervisorAsync(CancellationToken ct = default)
        {
            lock (_sync)
            {
                if (_disposed || _iniciado) return Task.CompletedTask;
                _iniciado = true;
                _cts = new CancellationTokenSource();
            }

            TunnelLogger.Escribir("supervisor", "Iniciando bucles de supervisión de slots...");
            lock (_sync)
            {
                var token = _cts.Token;
                foreach (var kvp in _slots)
                {
                    var slot = kvp.Value;
                    if (slot.DeseadoActivo && slot.Bucle == null)
                    {
                        slot.Bucle = Task.Run(() => BucleSlotAsync(slot, token), token);
                    }
                }
            }

            return Task.CompletedTask;
        }

        public Task ActivarSlotAsync(string nombreSlot, int? puertoLocal = null)
        {
            SlotInterno slot;
            CancellationToken token;

            lock (_sync)
            {
                if (!_slots.TryGetValue(nombreSlot, out slot!))
                {
                    slot = new SlotInterno(nombreSlot, puertoLocal ?? 7890);
                    _slots[nombreSlot] = slot;
                }

                if (puertoLocal.HasValue)
                    slot.PuertoLocal = puertoLocal.Value;

                slot.DeseadoActivo = true;

                if (_cts == null || _cts.IsCancellationRequested)
                    _cts = new CancellationTokenSource();

                token = _cts.Token;

                if (slot.Bucle == null || slot.Bucle.IsCompleted)
                {
                    slot.Bucle = Task.Run(() => BucleSlotAsync(slot, token), token);
                }
            }

            TunnelLogger.Escribir(nombreSlot, $"Activación de slot solicitada en puerto {slot.PuertoLocal}.");
            return Task.CompletedTask;
        }

        public void DetenerSlot(string nombreSlot)
        {
            SlotInterno? slot;
            lock (_sync)
            {
                if (!_slots.TryGetValue(nombreSlot, out slot)) return;
                slot.DeseadoActivo = false;
                slot.Activo = false;
                slot.UrlPublica = null;
                slot.Proveedor = "Detenido";
            }

            TunnelLogger.Escribir(nombreSlot, "Deteniendo proceso de slot...");
            MatarProcesoSlot(slot);
            TunnelProcessRegistry.Olvidar(nombreSlot);
        }

        private async Task BucleSlotAsync(SlotInterno slot, CancellationToken token)
        {
            TunnelProcessRegistry.BarrerHuerfano(slot.Slot);
            TunnelLogger.Escribir(slot.Slot, $"Bucle supervisor activo para {slot.Slot}:{slot.PuertoLocal}.");

            int intento = 0;
            int sshIdx = 0;

            while (!token.IsCancellationRequested)
            {
                lock (_sync)
                {
                    if (!slot.DeseadoActivo) break;
                }

                bool publicado = false;

                // 1. Intentar Cloudflare primero (T2-01)
                string? cfExe = ObtenerRutaCloudflared();
                if (cfExe != null)
                {
                    publicado = await IntentarCloudflareAsync(slot, cfExe, token).ConfigureAwait(false);
                }

                // 2. Si Cloudflare no estuvo disponible o falló, recurrir a SSH (modo degradado)
                if (!publicado && !token.IsCancellationRequested)
                {
                    var candSsh = ProveedoresSsh[sshIdx % ProveedoresSsh.Length];
                    sshIdx++;
                    publicado = await IntentarSshAsync(slot, candSsh.Nombre, candSsh.ArgsTemplate, candSsh.Patron, token)
                        .ConfigureAwait(false);
                }

                if (token.IsCancellationRequested) break;

                // Si salió del intento, el túnel cayó
                bool eraPrevActivo;
                lock (_sync)
                {
                    eraPrevActivo = slot.Activo;
                    slot.Activo = false;
                    slot.UrlPublica = null;
                    slot.UltimaActividad = DateTimeOffset.UtcNow;
                }

                if (eraPrevActivo)
                {
                    TunnelLogger.Escribir(slot.Slot, "Túnel cayó. Notificando TunnelCaido.", "WARN");
                    TunnelCaido?.Invoke(slot.Slot);
                }

                lock (_sync)
                {
                    if (!slot.DeseadoActivo) break;
                }

                // Backoff exponencial para reconexión (T2-03)
                intento = publicado ? 1 : intento + 1;
                int espera = (int)Math.Min(BackoffMaxSeg, BackoffInicialSeg * Math.Pow(2, Math.Min(intento - 1, 4)));

                lock (_sync)
                {
                    slot.Reconexiones++;
                    slot.UltimaActividad = DateTimeOffset.UtcNow;
                }

                TunnelLogger.Escribir(slot.Slot, $"Reintento #{intento} programado en {espera}s...");
                try
                {
                    await Task.Delay(TimeSpan.FromSeconds(espera), token).ConfigureAwait(false);
                }
                catch (OperationCanceledException) { break; }
            }

            TunnelLogger.Escribir(slot.Slot, "Bucle supervisor finalizado.");
        }

        private async Task<bool> IntentarCloudflareAsync(SlotInterno slot, string cfExe, CancellationToken token)
        {
            string args = $"tunnel --url http://127.0.0.1:{slot.PuertoLocal} --no-autoupdate";
            string patron = @"https://[\w\-]+\.trycloudflare\.com";
            TunnelLogger.Escribir(slot.Slot, "Intentando túnel Cloudflare Quick Tunnel...");

            return await EjecutarProcesoTunelAsync(
                slot,
                cfExe,
                args,
                patron,
                proveedor: "Cloudflare",
                esDegradado: false,
                timeoutMs: 30_000,
                token
            ).ConfigureAwait(false);
        }

        private async Task<bool> IntentarSshAsync(
            SlotInterno slot,
            string nombreSsh,
            string argsTemplate,
            string patron,
            CancellationToken token)
        {
            string sshExe = ObtenerRutaSsh();
            string args = string.Format(argsTemplate, slot.PuertoLocal);
            TunnelLogger.Escribir(slot.Slot, $"Intentando túnel SSH ({nombreSsh}) [Modo degradado]...", "WARN");

            return await EjecutarProcesoTunelAsync(
                slot,
                sshExe,
                args,
                patron,
                proveedor: nombreSsh,
                esDegradado: true,
                timeoutMs: TimeoutUrlMs,
                token
            ).ConfigureAwait(false);
        }

        private async Task<bool> EjecutarProcesoTunelAsync(
            SlotInterno slot,
            string exe,
            string args,
            string patron,
            string proveedor,
            bool esDegradado,
            int timeoutMs,
            CancellationToken token)
        {
            var psi = new ProcessStartInfo
            {
                FileName = exe,
                Arguments = args,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            var regex = new Regex(patron, RegexOptions.Compiled | RegexOptions.IgnoreCase);
            var tcsUrl = new TaskCompletionSource<string>(TaskCreationOptions.RunContinuationsAsynchronously);
            Process? proc = null;

            try
            {
                proc = new Process { StartInfo = psi, EnableRaisingEvents = true };

                void Escanear(string? linea)
                {
                    if (string.IsNullOrWhiteSpace(linea) || tcsUrl.Task.IsCompleted) return;
                    var m = regex.Match(linea);
                    if (m.Success)
                    {
                        tcsUrl.TrySetResult(m.Value.Trim().TrimEnd('/'));
                    }
                }

                proc.OutputDataReceived += (_, e) => Escanear(e.Data);
                proc.ErrorDataReceived += (_, e) => Escanear(e.Data);

                if (!proc.Start())
                {
                    TunnelLogger.Escribir(slot.Slot, $"Fallo al iniciar ejecutable '{exe}'", "ERROR");
                    return false;
                }

                lock (_sync) slot.Proceso = proc;
                TunnelProcessRegistry.Persistir(slot.Slot, proc.Id);

                proc.BeginOutputReadLine();
                proc.BeginErrorReadLine();

                var esperaExit = proc.WaitForExitAsync(CancellationToken.None);
                _ = esperaExit.ContinueWith(t => { _ = t.Exception; }, TaskContinuationOptions.OnlyOnFaulted);

                var esperaTimeout = Task.Delay(timeoutMs, token);
                var ganador = await Task.WhenAny(tcsUrl.Task, esperaExit, esperaTimeout).ConfigureAwait(false);

                if (ganador == tcsUrl.Task && tcsUrl.Task.Status == TaskStatus.RanToCompletion)
                {
                    string url = tcsUrl.Task.Result;
                    lock (_sync)
                    {
                        slot.Activo = true;
                        slot.UrlPublica = url;
                        slot.Proveedor = proveedor;
                        slot.EsModoDegradado = esDegradado;
                        slot.UltimoFallo = null;
                        slot.UltimaActividad = DateTimeOffset.UtcNow;
                    }

                    string modoMsg = esDegradado ? "Modo degradado (SSH gratuito)" : "Cloudflare Túnel";
                    TunnelLogger.Escribir(slot.Slot, $"Túnel ACTIVO ({proveedor}): {url} [{modoMsg}]");
                    UrlObtenida?.Invoke(slot.Slot, url);
                    ModoDegradadoCambiado?.Invoke(slot.Slot, esDegradado);

                    await esperaExit.ConfigureAwait(false);
                    return true;
                }

                return false;
            }
            catch (Exception ex)
            {
                TunnelLogger.Escribir(slot.Slot, $"Excepción en túnel {proveedor}: {ex.Message}", "ERROR");
                lock (_sync) slot.UltimoFallo = ex.Message;
                return false;
            }
            finally
            {
                tcsUrl.TrySetCanceled();
                MatarProcesoSlot(slot);
                TunnelProcessRegistry.Olvidar(slot.Slot);
            }
        }

        private static void MatarProcesoSlot(SlotInterno slot)
        {
            Process? p;
            lock (slot)
            {
                p = slot.Proceso;
                slot.Proceso = null;
            }

            if (p != null)
            {
                try
                {
                    if (!p.HasExited) p.Kill(entireProcessTree: true);
                }
                catch { }
                try { p.Dispose(); } catch { }
            }
        }

        public static string? ObtenerRutaCloudflared()
        {
            string? envCf = Environment.GetEnvironmentVariable("CLOUDFLARED_EXE");
            if (!string.IsNullOrWhiteSpace(envCf) && File.Exists(envCf))
                return envCf;

            string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string rutaLocalApp = Path.Combine(localApp, "WoldVirtualP2P3D", "bin", "cloudflared.exe");
            if (File.Exists(rutaLocalApp))
                return rutaLocalApp;

            string baseApp = AppContext.BaseDirectory;
            string rutaBase = Path.Combine(baseApp, "cloudflared.exe");
            if (File.Exists(rutaBase))
                return rutaBase;

            return null;
        }

        public static string ObtenerRutaSsh()
        {
            string sysSsh = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                "System32", "OpenSSH", "ssh.exe");
            return File.Exists(sysSsh) ? sysSsh : "ssh";
        }

        public TunnelSlotInfo? ObtenerSlot(string nombreSlot)
        {
            lock (_sync)
            {
                return _slots.TryGetValue(nombreSlot, out var s) ? s.ToSnapshot() : null;
            }
        }

        public bool EsCualquierSlotDegradado()
        {
            lock (_sync)
            {
                return _slots.Values.Any(s => s.Activo && s.EsModoDegradado);
            }
        }

        public string ObtenerEstadoModoGlobal()
        {
            lock (_sync)
            {
                var activos = _slots.Values.Where(s => s.Activo).ToList();
                if (activos.Count == 0) return "Túneles desconectados";
                if (activos.Any(s => s.EsModoDegradado)) return "Modo degradado (SSH gratuito)";
                return "Cloudflare Túnel";
            }
        }

        public string ObtenerEstadoJson()
        {
            List<TunnelSlotInfo> lista;
            lock (_sync)
            {
                lista = _slots.Values.Select(s => s.ToSnapshot()).ToList();
            }

            var sb = new StringBuilder();
            sb.AppendLine("{");
            sb.AppendLine($"  \"timestamp\": \"{DateTimeOffset.UtcNow:O}\",");
            sb.AppendLine($"  \"modoGlobal\": \"{ObtenerEstadoModoGlobal()}\",");
            sb.AppendLine("  \"slots\": [");

            for (int i = 0; i < lista.Count; i++)
            {
                var s = lista[i];
                sb.AppendLine("    {");
                sb.AppendLine($"      \"slot\": \"{s.Slot}\",");
                sb.AppendLine($"      \"puertoLocal\": {s.PuertoLocal},");
                sb.AppendLine($"      \"activo\": {(s.Activo ? "true" : "false")},");
                sb.AppendLine($"      \"urlPublica\": {(s.UrlPublica != null ? $"\"{s.UrlPublica}\"" : "null")},");
                sb.AppendLine($"      \"proveedor\": \"{s.Proveedor}\",");
                sb.AppendLine($"      \"esModoDegradado\": {(s.EsModoDegradado ? "true" : "false")},");
                sb.AppendLine($"      \"reconexiones\": {s.Reconexiones},");
                sb.AppendLine($"      \"ultimoFallo\": {(s.UltimoFallo != null ? $"\"{s.UltimoFallo}\"" : "null")},");
                sb.AppendLine($"      \"ultimaActividad\": \"{s.UltimaActividad:O}\"");
                sb.Append("    }");
                if (i < lista.Count - 1) sb.AppendLine(",");
                else sb.AppendLine();
            }

            sb.AppendLine("  ]");
            sb.Append("}");
            return sb.ToString();
        }

        public void Detener()
        {
            CancellationTokenSource? cts;
            lock (_sync)
            {
                _iniciado = false;
                cts = _cts;
                _cts = null;
                foreach (var s in _slots.Values)
                {
                    s.DeseadoActivo = false;
                    s.Activo = false;
                    s.UrlPublica = null;
                }
            }

            try { cts?.Cancel(); } catch { }

            lock (_sync)
            {
                foreach (var s in _slots.Values)
                {
                    MatarProcesoSlot(s);
                    TunnelProcessRegistry.Olvidar(s.Slot);
                }
            }

            try { cts?.Dispose(); } catch { }
            TunnelLogger.Escribir("supervisor", "Supervisor de túneles detenido por completo.");
        }

        public void Dispose()
        {
            lock (_sync)
            {
                if (_disposed) return;
                _disposed = true;
            }
            Detener();
        }
    }
}
