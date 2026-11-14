using System;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Services
{
    /// <summary>
    /// Arranca el cerebro de LucIA (TCP 8765) junto al visor. Si ya hay un
    /// servidor escuchando, no lanza otro. La voz usa System.Speech cuando
    /// gTTS/comtypes no están instalados.
    /// </summary>
    public class ServidorLucIAOficial : IDisposable
    {
        public const int PuertoPorDefecto = 8765;

        private Process? _proceso;
        private readonly int _puerto;

        public bool EstaEnLinea { get; private set; }
        public string? UltimoError { get; private set; }

        public bool EstaEscuchando() => PuertoAbierto();

        /// <summary>
        /// Comprueba que el puerto no sólo esté abierto, sino que LucIA
        /// conteste el saludo inicial. Un pythonw zombi puede tener el puerto
        /// abierto y no atender el chat; entonces hay que reemplazarlo.
        /// </summary>
        public bool EstaListo()
        {
            try
            {
                using var cliente = new TcpClient();
                var conexion = cliente.ConnectAsync("127.0.0.1", _puerto);
                if (!conexion.Wait(900)) return false;
                using var flujo = cliente.GetStream();
                flujo.ReadTimeout = 1500;
                using var lector = new StreamReader(flujo);
                string? linea = lector.ReadLine();
                return !string.IsNullOrWhiteSpace(linea) &&
                       (linea.Contains("\"hola\"") || linea.Contains("\"listo\"") ||
                        linea.Contains("hola") || linea.Contains("listo"));
            }
            catch
            {
                return false;
            }
        }

        public ServidorLucIAOficial(int puerto = PuertoPorDefecto)
        {
            _puerto = puerto;
        }

        public async Task<bool> IniciarAsync(CancellationToken ct = default)
        {
            if (PuertoAbierto())
            {
                if (EstaListo())
                {
                    EstaEnLinea = true;
                    VisorLog.Info($"[LucIA] Cerebro ya activo en 127.0.0.1:{_puerto}");
                    return true;
                }

                // Puerto abierto pero sin saludo: puede estar ocupado sintetizando
                // voz. No matarlo (eso cortaba el chat tras la primera consulta);
                // el vigilante reintentará.
                UltimoError = "El puerto 8765 está ocupado pero LucIA no respondió al saludo.";
                VisorLog.Info("[LucIA] " + UltimoError);
                return false;
            }

            string? python = BuscarPython();
            string? script = BuscarScript();
            if (string.IsNullOrEmpty(python) || !File.Exists(python))
            {
                UltimoError = "No se localizó el Python de LucIA.";
                VisorLog.Error($"[LucIA] {UltimoError}");
                return false;
            }
            if (string.IsNullOrEmpty(script) || !File.Exists(script))
            {
                UltimoError = $"No se encontró servidor_lucia.py ({script ?? "nulo"}).";
                VisorLog.Error($"[LucIA] {UltimoError}");
                return false;
            }

            try
            {
                // pythonw evita la consola y, en Windows, permite que COM/SAPI
                // inicialice la voz correctamente.
                string ejecutable = python;
                string? pythonw = Path.Combine(Path.GetDirectoryName(python) ?? "", "pythonw.exe");
                if (File.Exists(pythonw)) ejecutable = pythonw;

                string bat = Path.Combine(AppContext.BaseDirectory, "Iniciar_Lucia_Visor.bat");
                if (!File.Exists(bat))
                    bat = @"E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\VSC#\Visor3Ddesarrollo\Iniciar_Lucia_Visor.bat";

                string ps1 = Path.Combine(AppContext.BaseDirectory, "Iniciar_Lucia_Visor.ps1");
                if (!File.Exists(ps1))
                    ps1 = @"E:\WoldVirtualP2P3D\VersionDe_sesion\CONTRRF\TLLDCD\src\VSC#\Visor3Ddesarrollo\Iniciar_Lucia_Visor.ps1";

                var psi = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments = $"-NoProfile -ExecutionPolicy Bypass -File \"{ps1}\"",
                    WorkingDirectory = Path.GetDirectoryName(ps1) ?? "",
                    UseShellExecute = false,
                    CreateNoWindow = true,
                };

                string logHijo = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D", "logs", "lucia_child.log");
                try { Directory.CreateDirectory(Path.GetDirectoryName(logHijo)!); } catch { }
                try
                {
                    File.AppendAllText(logHijo,
                        $"\n=== {DateTime.Now:HH:mm:ss} python={python} script={script} exe={ejecutable}\n");
                }
                catch { }

                VisorLog.Info($"[LucIA] Arrancando cerebro: {psi.FileName} {psi.Arguments}");
                VisorLog.Info($"[LucIA] Servidor de LucIA del visor: {script}");
                _proceso = Process.Start(psi);

                for (int i = 0; i < 40; i++)
                {
                    if (ct.IsCancellationRequested) break;
                    await Task.Delay(500, ct);
                    if (PuertoAbierto())
                    {
                        if (EstaListo())
                        {
                            EstaEnLinea = true;
                            VisorLog.Info($"[LucIA] Cerebro listo en 127.0.0.1:{_puerto}");
                            return true;
                        }
                    }
                    if (_proceso != null && _proceso.HasExited)
                    {
                        UltimoError = $"El proceso de LucIA terminó (código {_proceso.ExitCode}).";
                        VisorLog.Error($"[LucIA] {UltimoError}");
                        return false;
                    }
                }
            }
            catch (Exception ex)
            {
                UltimoError = $"Error al lanzar LucIA: {ex.Message}";
                VisorLog.Error($"[LucIA] {UltimoError}");
            }

            return false;
        }

        private bool PuertoAbierto()
        {
            try
            {
                using var cliente = new TcpClient();
                var tarea = cliente.ConnectAsync("127.0.0.1", _puerto);
                if (!tarea.Wait(400)) return false;
                return cliente.Connected;
            }
            catch
            {
                return false;
            }
        }

        private static void MatarServidoresLucia()
        {
            try
            {
                using var buscador = new ManagementObjectSearcher(
                    "SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name LIKE '%python%'");
                foreach (ManagementObject proceso in buscador.Get())
                {
                    try
                    {
                        string linea = proceso["CommandLine"]?.ToString() ?? "";
                        if (!linea.Contains("servidor_lucia.py", StringComparison.OrdinalIgnoreCase))
                            continue;
                        int id = Convert.ToInt32(proceso["ProcessId"]);
                        if (id <= 0) continue;
                        var p = Process.GetProcessById(id);
                        p.Kill(entireProcessTree: true);
                        VisorLog.Info($"[LucIA] Servidor zombi {id} detenido.");
                    }
                    catch { }
                }
            }
            catch (Exception ex)
            {
                VisorLog.Info($"[LucIA] No se pudieron limpiar servidores previos: {ex.Message}");
            }
        }

        private static string? BuscarPython()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string projectDir = GodotConfig.GetProjectPath();
            string? srcDir = Directory.GetParent(Directory.GetParent(projectDir)?.FullName ?? "")?.FullName;

            string[] candidatos =
            {
                srcDir != null ? Path.Combine(srcDir, "LC_STM", "python", "python.exe") : "",
                @"E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\LC_STM\python\python.exe",
                Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "LC_STM", "python", "python.exe")),
                Path.Combine(baseDir, "LC_STM", "python", "python.exe"),
                Path.Combine(baseDir, "python", "python.exe"),
                Environment.GetEnvironmentVariable("WVP_PYTHON") ?? "",
            };

            foreach (var candidato in candidatos)
            {
                if (!string.IsNullOrWhiteSpace(candidato) && File.Exists(candidato))
                    return candidato;
            }
            return null;
        }

        private static string? BuscarScript()
        {
            string projectDir = GodotConfig.GetProjectPath();
            string[] candidatos =
            {
                Path.Combine(projectDir, "lucia3D", "GLTF_lucIA", "celebro_3D", "puente_3D", "servidor_lucia.py"),
                @"E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py",
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "celebro_3D", "puente_3D", "servidor_lucia.py"),
            };

            foreach (var candidato in candidatos)
            {
                if (!string.IsNullOrWhiteSpace(candidato) && File.Exists(candidato))
                    return candidato;
            }
            return null;
        }

        public void Detener()
        {
            try
            {
                if (_proceso != null && !_proceso.HasExited)
                {
                    VisorLog.Info("[LucIA] Deteniendo cerebro...");
                    _proceso.Kill(entireProcessTree: true);
                    _proceso.WaitForExit(3000);
                }
            }
            catch { }
            finally
            {
                _proceso = null;
                EstaEnLinea = false;
            }
        }

        public void Dispose() => Detener();
    }
}
