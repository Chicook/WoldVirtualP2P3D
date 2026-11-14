using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Visor3D.RedP2P;

namespace Visor3D.Services
{
    /// <summary>
    /// Gestiona el ciclo de vida del Servidor Oficial de Cuentas y Blockchain (STM_BKCH)
    /// en el puerto 8545. LucIA 3D y el visor consumen este servidor para alta de cuentas,
    /// minado de bloques inmutables y validación de originalidad de avatar.
    /// </summary>
    public class ServidorBlockchainOficial : IDisposable
    {
        private const string SlotPid = "servidor-blockchain";
        public const int PuertoPorDefecto = 8545;

        private Process? _proceso;
        private readonly int _puerto;
        private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(2) };

        public bool EstaEnLinea { get; private set; }
        public int TotalBloques { get; private set; }
        public string? UltimoError { get; private set; }
        public string UrlServidor => $"http://127.0.0.1:{_puerto}";

        public ServidorBlockchainOficial(int puerto = PuertoPorDefecto)
        {
            _puerto = puerto;
        }

        /// <summary>
        /// Comprueba si el servidor ya está activo o lo levanta si no lo está.
        /// </summary>
        public async Task<bool> IniciarAsync(CancellationToken ct = default)
        {
            // 1. Limpiar procesos huérfanos anteriores
            LimpiarHuerfano();

            // 2. Comprobar si ya responde en el puerto
            if (await ConsultarSaludAsync())
            {
                EstaEnLinea = true;
                VisorLog.Info($"[Blockchain] Servidor oficial ya activo en {UrlServidor} (Bloques: {TotalBloques})");
                return true;
            }

            // 3. Localizar python y script oficial
            string? pyExe = BuscarPython();
            if (string.IsNullOrEmpty(pyExe) || !File.Exists(pyExe))
            {
                UltimoError = "No se localizó el intérprete de Python para arrancar el servidor blockchain.";
                VisorLog.Error($"[Blockchain] {UltimoError}");
                return false;
            }

            string? scriptPath = BuscarScriptServidor();
            if (string.IsNullOrEmpty(scriptPath) || !File.Exists(scriptPath))
            {
                UltimoError = $"No se encontró el script del servidor oficial ({scriptPath ?? "nulo"}).";
                VisorLog.Error($"[Blockchain] {UltimoError}");
                return false;
            }

            string logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WoldVirtualP2P3D");
            Directory.CreateDirectory(logDir);
            string logFile = Path.Combine(logDir, "servidor_oficial.log");

            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = pyExe,
                    Arguments = $"\"{scriptPath}\" --puerto {_puerto} --sin-cuota-ubicacion",
                    WorkingDirectory = Path.GetDirectoryName(scriptPath) ?? "",
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden,
                    RedirectStandardOutput = false,
                    RedirectStandardError = false
                };

                VisorLog.Info($"[Blockchain] Arrancando servidor oficial: {psi.FileName} {psi.Arguments}");
                _proceso = Process.Start(psi);

                if (_proceso != null && !_proceso.HasExited)
                {
                    TunnelProcessRegistry.Persistir(SlotPid, _proceso.Id);

                    // Esperar hasta 10 segundos a que responda /status
                    for (int i = 0; i < 20; i++)
                    {
                        if (ct.IsCancellationRequested) break;
                        await Task.Delay(500, ct);

                        if (await ConsultarSaludAsync())
                        {
                            EstaEnLinea = true;
                            VisorLog.Info($"[Blockchain] Servidor oficial listo en {UrlServidor} (Bloques: {TotalBloques})");
                            return true;
                        }

                        if (_proceso.HasExited)
                        {
                            UltimoError = $"El proceso de Python terminó prematuramente (código: {_proceso.ExitCode}).";
                            VisorLog.Error($"[Blockchain] {UltimoError}");
                            return false;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                UltimoError = $"Error al lanzar el servidor oficial: {ex.Message}";
                VisorLog.Error($"[Blockchain] {UltimoError}");
                return false;
            }

            EstaEnLinea = await ConsultarSaludAsync();
            return EstaEnLinea;
        }

        public async Task<bool> ConsultarSaludAsync()
        {
            try
            {
                var resp = await _http.GetAsync($"{UrlServidor}/status");
                if (resp.IsSuccessStatusCode)
                {
                    string json = await resp.Content.ReadAsStringAsync();
                    using var doc = JsonDocument.Parse(json);
                    if (doc.RootElement.TryGetProperty("total_bloques", out var tb))
                    {
                        TotalBloques = tb.GetInt32();
                    }
                    EstaEnLinea = true;
                    return true;
                }
            }
            catch
            {
                // Puerto cerrado o timeout
            }

            EstaEnLinea = false;
            return false;
        }

        public void Detener()
        {
            try
            {
                if (_proceso != null && !_proceso.HasExited)
                {
                    VisorLog.Info("[Blockchain] Deteniendo servidor oficial...");
                    _proceso.Kill(entireProcessTree: true);
                    _proceso.WaitForExit(3000);
                }
            }
            catch { }
            finally
            {
                _proceso = null;
                TunnelProcessRegistry.Olvidar(SlotPid);
                EstaEnLinea = false;
            }
        }

        private static void LimpiarHuerfano()
        {
            try
            {
                string carp = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D");
                string arch = Path.Combine(carp, $"tunnel-{SlotPid}.pid");
                if (!File.Exists(arch)) return;

                string txt = File.ReadAllText(arch).Trim();
                TunnelProcessRegistry.Olvidar(SlotPid);

                var partes = txt.Split('|');
                if (partes.Length >= 1 && int.TryParse(partes[0], out int pid))
                {
                    var p = Process.GetProcessById(pid);
                    if (p.ProcessName.ToLowerInvariant().Contains("python"))
                    {
                        p.Kill(entireProcessTree: true);
                    }
                }
            }
            catch { }
        }

        private static string? BuscarPython()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string projectDir = GodotConfig.GetProjectPath();
            string? srcDir = Directory.GetParent(Directory.GetParent(projectDir)?.FullName ?? "")?.FullName;

            string[] candidatos =
            {
                // 1. Python embebido en LC_STM (prioridad máxima)
                srcDir != null ? Path.Combine(srcDir, "LC_STM", "python", "python.exe") : "",
                Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "LC_STM", "python", "python.exe")),
                Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", "LC_STM", "python", "python.exe")),
                @"E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\LC_STM\python\python.exe",
                Path.Combine(baseDir, "LC_STM", "python", "python.exe"),
                Path.Combine(baseDir, "python", "python.exe"),
                Environment.GetEnvironmentVariable("WVP_PYTHON") ?? "",
                @"C:\Python314\python.exe",
                @"C:\Python313\python.exe",
                @"C:\Python312\python.exe",
                @"C:\Python311\python.exe",
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python313", "python.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python312", "python.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python311", "python.exe"),
            };

            foreach (var c in candidatos)
            {
                if (!string.IsNullOrWhiteSpace(c) && File.Exists(c))
                    return c;
            }

            // Buscar en PATH del sistema
            try
            {
                var p = Process.Start(new ProcessStartInfo
                {
                    FileName = "where",
                    Arguments = "python",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    CreateNoWindow = true
                });
                if (p != null)
                {
                    string salida = p.StandardOutput.ReadLine() ?? "";
                    p.WaitForExit(1000);
                    if (!string.IsNullOrWhiteSpace(salida) && File.Exists(salida))
                        return salida;
                }
            }
            catch { }

            return null;
        }

        private static string? BuscarScriptServidor()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string projectDir = GodotConfig.GetProjectPath();
            string? srcDir = Directory.GetParent(Directory.GetParent(projectDir)?.FullName ?? "")?.FullName;

            string[] candidatos =
            {
                srcDir != null ? Path.Combine(srcDir, "STM_BKCH", "servidor_oficial.py") : "",
                Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "STM_BKCH", "servidor_oficial.py")),
                Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", "STM_BKCH", "servidor_oficial.py")),
                @"E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\STM_BKCH\servidor_oficial.py",
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "STM_BKCH", "servidor_oficial.py"),
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "servidor_oficial.py")
            };

            foreach (var c in candidatos)
            {
                if (!string.IsNullOrWhiteSpace(c) && File.Exists(c))
                    return c;
            }

            return null;
        }

        public void Dispose()
        {
            Detener();
            _http.Dispose();
        }
    }
}
