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
        private readonly SemaphoreSlim _inicio = new(1, 1);

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
            if (EstaEnLinea) return true;

            // Varias llamadas del arranque (registro de eventos y entrada al mundo)
            // pueden coincidir; solo una debe sondear y lanzar el proceso.
            await _inicio.WaitAsync(ct);
            try
            {
                if (EstaEnLinea) return true;

                // 1. Salud primero: si ya responde, no se toca ningún proceso.
                if (await ConsultarSaludConEsperaAsync(ct))
                {
                    UltimoError = null;
                    VisorLog.Info($"[Blockchain] Servidor oficial ya activo en {UrlServidor} (Bloques: {TotalBloques})");
                    return true;
                }

                // 2. Solo sin respuesta se limpian huérfanos de ejecuciones previas
                LimpiarHuerfano();

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
                    // Otra instancia pudo levantarlo mientras se buscaba el script:
                    // el puerto manda sobre la ruta.
                    if (await ConsultarSaludConEsperaAsync(ct))
                    {
                        UltimoError = null;
                        VisorLog.Info($"[Blockchain] Servidor oficial activo en {UrlServidor} (levantado por otra instancia).");
                        return true;
                    }
                    UltimoError = $"No se encontró el script del servidor oficial ({scriptPath ?? "nulo"}).";
                    VisorLog.Error($"[Blockchain] {UltimoError}");
                    return false;
                }

                string logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WoldVirtualP2P3D");
                Directory.CreateDirectory(logDir);
                string logFile = Path.Combine(logDir, "servidor_oficial.log");
                var logLock = new object();
                void RegistrarSalida(string? linea)
                {
                    if (string.IsNullOrWhiteSpace(linea)) return;
                    try
                    {
                        lock (logLock)
                            File.AppendAllText(logFile, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {linea}{Environment.NewLine}");
                    }
                    catch { }
                }

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
                        // Capturar la salida para que los fallos de importación,
                        // permisos o puerto ocupado no queden invisibles.
                        RedirectStandardOutput = true,
                        RedirectStandardError = true
                    };

                    VisorLog.Info($"[Blockchain] Arrancando servidor oficial: {psi.FileName} {psi.Arguments}");
                    _proceso = Process.Start(psi);

                    if (_proceso != null && !_proceso.HasExited)
                    {
                        _proceso.OutputDataReceived += (_, e) => RegistrarSalida(e.Data);
                        _proceso.ErrorDataReceived += (_, e) => RegistrarSalida(e.Data);
                        _proceso.BeginOutputReadLine();
                        _proceso.BeginErrorReadLine();
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
                                UltimoError = $"Python terminó prematuramente (código: {_proceso.ExitCode}). Registro: {logFile}";
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

                EstaEnLinea = await ConsultarSaludConEsperaAsync(ct);
                if (!EstaEnLinea)
                {
                    UltimoError = $"El servidor no respondió en {UrlServidor}. Registro: {logFile}";
                    VisorLog.Error($"[Blockchain] {UltimoError}");
                }
                return EstaEnLinea;
            }
            finally
            {
                _inicio.Release();
            }
        }

        /// <summary>
        /// Sondea /status con reintentos cortos: el servidor puede estar ocupado
        /// minando o atendiendo otra petición en el instante de la comprobación.
        /// </summary>
        private async Task<bool> ConsultarSaludConEsperaAsync(CancellationToken ct)
        {
            for (int intento = 0; intento < 3; intento++)
            {
                if (await ConsultarSaludAsync()) return true;
                if (intento < 2)
                {
                    try { await Task.Delay(400, ct); }
                    catch (OperationCanceledException) { return false; }
                }
            }
            return false;
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
                // 1. Python embebido en LC_STM (árbol activo y archivo de versiones)
                GodotConfig.GetPythonExePath() ?? "",
                srcDir != null ? Path.Combine(srcDir, "LC_STM", "python", "python.exe") : "",
                Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "LC_STM", "python", "python.exe")),
                Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", "LC_STM", "python", "python.exe")),
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
            var raicesSrc = new List<string>();
            void AgregarSrc(string? ruta)
            {
                if (string.IsNullOrWhiteSpace(ruta)) return;
                string? actual = ruta;
                if (File.Exists(actual)) actual = Path.GetDirectoryName(actual);
                if (actual == null || !Directory.Exists(actual)) return;
                actual = Path.GetFullPath(actual);
                if (!raicesSrc.Contains(actual, StringComparer.OrdinalIgnoreCase)) raicesSrc.Add(actual);
            }

            // El proyecto Godot activo vive bajo src/MTBGT/WoldVirtualP2P3D.
            // Subir hasta encontrar src permite funcionar tanto en checkout como
            // si projectDir apunta a recursos extraídos bajo LocalAppData.
            DirectoryInfo? dir = new(projectDir);
            while (dir != null)
            {
                if (string.Equals(dir.Name, "src", StringComparison.OrdinalIgnoreCase))
                {
                    AgregarSrc(dir.FullName);
                    break;
                }
                dir = dir.Parent;
            }

            foreach (string src in GodotConfig.SrcCandidatos()) AgregarSrc(src);

            // También cubre desarrollo cuando el exe se inicia desde una salida
            // de build situada dentro del repositorio, independientemente del CWD.
            foreach (string inicio in new[] { baseDir, GodotConfig.RepoRoot() ?? "" })
            {
                if (string.IsNullOrWhiteSpace(inicio)) continue;
                dir = new DirectoryInfo(inicio);
                while (dir != null)
                {
                    if (string.Equals(dir.Name, "src", StringComparison.OrdinalIgnoreCase))
                    {
                        AgregarSrc(dir.FullName);
                        break;
                    }
                    dir = dir.Parent;
                }
            }

            var candidatos = new List<string>
            {
                // En la publicación el script se copia junto al exe bajo STM_BKCH.
                Path.Combine(baseDir, "STM_BKCH", "stm_bkch1", "servidor_oficial.py"),
                Path.Combine(baseDir, "STM_BKCH", "servidor_oficial.py"),
                Path.Combine(baseDir, "servidor_oficial.py")
            };
            foreach (string src in raicesSrc)
            {
                candidatos.Add(Path.Combine(src, "STM_BKCH", "stm_bkch1", "servidor_oficial.py"));
                candidatos.Add(Path.Combine(src, "STM_BKCH", "servidor_oficial.py"));
            }

            foreach (string candidato in candidatos)
            {
                if (File.Exists(candidato))
                {
                    VisorLog.Info($"[Blockchain] Script Python localizado: {candidato}");
                    return candidato;
                }
            }

            return null;
        }

        public void Dispose()
        {
            Detener();
            _http.Dispose();
            _inicio.Dispose();
        }
    }
}
