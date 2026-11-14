using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Services
{
    /// <summary>
    /// Sincroniza automáticamente las rutas Python del proyecto al arrancar el visor.
    /// Llama al motor de sincronización en STM_HRTS (sincronizar_rutas.py) usando
    /// el intérprete Python embebido en src\LC_STM\python\python.exe.
    ///
    /// Se llama desde App.xaml.cs durante el arranque, antes de mostrar la ventana
    /// principal. La operación es asíncrona y fire-and-forget: si falla no bloquea
    /// el arranque del visor.
    /// </summary>
    public static class RutasSyncService
    {
        // Ruta relativa del intérprete Python embebido desde la raíz del repositorio
        private const string PythonRelPath = @"LC_STM\python\python.exe";

        // Tiempo máximo de espera antes de cancelar la sincronización (ms)
        private const int TimeoutMs = 15_000;

        /// <summary>
        /// Resultado devuelto por la sincronización de rutas.
        /// </summary>
        public sealed class ResultadoSync
        {
            public bool Ok { get; init; }
            public int Corregidas { get; init; }
            public int Correctas { get; init; }
            public string? Mensaje { get; init; }
            public string? Error { get; init; }
        }

        /// <summary>
        /// Lanza la sincronización de rutas de forma asíncrona y fire-and-forget.
        /// Los resultados se escriben al log del visor; no lanza excepciones.
        /// </summary>
        public static void LanzarEnSegundoPlano()
        {
            _ = Task.Run(async () =>
            {
                try
                {
                    var r = await SincronizarRutasAsync();
                    if (r.Ok)
                        VisorLog.Info($"[RutasSync] OK — {r.Correctas} correctas, {r.Corregidas} corregidas. {r.Mensaje}");
                    else
                        VisorLog.Info($"[RutasSync] Sin ejecutar: {r.Error}");
                }
                catch (Exception ex)
                {
                    VisorLog.Info($"[RutasSync] Error inesperado: {ex.Message}");
                }
            });
        }

        /// <summary>
        /// Busca el intérprete Python embebido subiendo por los directorios padre
        /// desde la ubicación del ejecutable, con el mismo patrón que GodotConfig.
        /// </summary>
        private static string? EncontrarPythonExe()
        {
            // 1. Variable de entorno de override (útil para tests / CI)
            string? envPy = Environment.GetEnvironmentVariable("WOLDVIRTUAL_PYTHON_EXE");
            if (!string.IsNullOrWhiteSpace(envPy) && File.Exists(envPy))
                return envPy;

            string? current = Path.GetDirectoryName(
                Process.GetCurrentProcess().MainModule?.FileName
                ?? AppDomain.CurrentDomain.BaseDirectory);

            // 2. Subir hasta 10 niveles buscando LC_STM\python\python.exe
            for (int i = 0; i < 10 && current != null; i++)
            {
                string candidate = Path.Combine(current, PythonRelPath);
                if (File.Exists(candidate)) return candidate;

                // También bajo src/
                string withSrc = Path.Combine(current, "src", PythonRelPath);
                if (File.Exists(withSrc)) return withSrc;

                current = Directory.GetParent(current)?.FullName;
            }

            // 3. Rutas absolutas de desarrollo (E: y C:)
            string[] rutas =
            {
                @"E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\" + PythonRelPath,
                @"C:\Users\User\Desktop\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\" + PythonRelPath,
            };
            foreach (var r in rutas)
                if (File.Exists(r)) return r;

            return null;
        }

        /// <summary>
        /// Ejecuta <c>python.exe -m STM_HRTS.utils.add_utils sincronizar --json</c>
        /// usando el Python embebido y devuelve el resultado parseado.
        /// </summary>
        public static async Task<ResultadoSync> SincronizarRutasAsync(
            CancellationToken ct = default)
        {
            string? pythonExe = EncontrarPythonExe();
            if (pythonExe == null)
                return new ResultadoSync { Ok = false, Error = "Python embebido no encontrado." };

            // El módulo STM_HRTS está en src/STM_HRTS; trabajamos desde src/
            string workDir = Path.GetDirectoryName(pythonExe)!;
            // Subir desde LC_STM\python\ hasta src\
            workDir = Path.Combine(workDir, "..", ".."); // → src/
            workDir = Path.GetFullPath(workDir);

            var psi = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = "-m STM_HRTS.utils.add_utils sincronizar --json",
                WorkingDirectory = workDir,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };

            using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            cts.CancelAfter(TimeoutMs);

            try
            {
                using var proc = Process.Start(psi);
                if (proc == null)
                    return new ResultadoSync { Ok = false, Error = "No se pudo iniciar python.exe." };

                string stdout = await proc.StandardOutput.ReadToEndAsync();
                string stderr = await proc.StandardError.ReadToEndAsync();

                await proc.WaitForExitAsync(cts.Token);

                return ParsearSalida(stdout, stderr, proc.ExitCode);
            }
            catch (OperationCanceledException)
            {
                return new ResultadoSync { Ok = false, Error = "Tiempo de espera agotado (>15 s)." };
            }
            catch (Exception ex)
            {
                return new ResultadoSync { Ok = false, Error = ex.Message };
            }
        }

        private static ResultadoSync ParsearSalida(string stdout, string stderr, int exitCode)
        {
            // La salida JSON tiene la forma:
            // {"ok": true, "correctas": 19, "corregidas": 0, "mensaje": "...", "cambios": [...]}
            if (!string.IsNullOrWhiteSpace(stdout))
            {
                try
                {
                    // Extraer la primera línea JSON válida
                    foreach (var line in stdout.Split('\n'))
                    {
                        string trimmed = line.Trim();
                        if (!trimmed.StartsWith("{")) continue;
                        using var doc = JsonDocument.Parse(trimmed);
                        var root = doc.RootElement;
                        bool ok = root.TryGetProperty("ok", out var okProp) && okProp.GetBoolean();
                        int correctas = root.TryGetProperty("correctas", out var cProp) ? cProp.GetInt32() : 0;
                        int corregidas = root.TryGetProperty("corregidas", out var xProp) ? xProp.GetInt32() : 0;
                        string msg = root.TryGetProperty("mensaje", out var mProp) ? mProp.GetString() ?? "" : "";
                        return new ResultadoSync
                        {
                            Ok = true,
                            Correctas = correctas,
                            Corregidas = corregidas,
                            Mensaje = msg,
                        };
                    }
                }
                catch
                {
                    // JSON no parseable: registrar texto plano como mensaje
                    return new ResultadoSync
                    {
                        Ok = exitCode == 0,
                        Mensaje = stdout.Trim(),
                        Error = exitCode != 0 ? (stderr.Trim().Length > 0 ? stderr.Trim() : stdout.Trim()) : null,
                    };
                }
            }

            return new ResultadoSync
            {
                Ok = false,
                Error = !string.IsNullOrWhiteSpace(stderr) ? stderr.Trim() : $"Proceso terminó con código {exitCode} sin salida.",
            };
        }
    }
}
