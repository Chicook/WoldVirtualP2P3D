using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity.Services
{
    internal static class RuntimeSelfHealer
    {
        private const int DefaultIntervalSeconds = 60;
        private const long LowDiskSpaceThresholdBytes = 100L * 1024 * 1024;

        private static readonly object SyncRoot = new();
        private static readonly SemaphoreSlim CheckGate = new(1, 1);

        private static CancellationTokenSource? _cts;
        private static Task? _loopTask;
        private static bool _initialized;
        private static TimeSpan _interval = TimeSpan.FromSeconds(DefaultIntervalSeconds);

        public static event Action<string>? OnHealAction;

        private static string AppDataRoot =>
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "WoldVirtualP2P");

        private static string LogsDir => Path.Combine(AppDataRoot, "logs");
        private static string IpfsDir => Path.Combine(AppDataRoot, "ipfs");

        public static void Initialize(TimeSpan? interval = null)
        {
            lock (SyncRoot)
            {
                if (_initialized)
                {
                    return;
                }

                _initialized = true;
                _interval = interval ?? TimeSpan.FromSeconds(DefaultIntervalSeconds);
                _cts = new CancellationTokenSource();
            }

            EnsureCriticalDirectories();
            PerformHealthCheck("startup");

            _loopTask = WatchdogLoopAsync(_cts.Token);
            Emit($"RuntimeSelfHealer iniciado. Intervalo: {_interval.TotalSeconds:0}s");
        }

        public static void Stop()
        {
            lock (SyncRoot)
            {
                if (!_initialized)
                {
                    return;
                }

                _cts?.Cancel();
            }

            try
            {
                _loopTask?.Wait(TimeSpan.FromSeconds(2));
            }
            catch
            {
                // Nada: el apagado debe ser silencioso.
            }

            lock (SyncRoot)
            {
                _cts?.Dispose();
                _cts = null;
                _loopTask = null;
                _initialized = false;
            }
        }

        private static async Task WatchdogLoopAsync(CancellationToken token)
        {
            try
            {
                using var timer = new PeriodicTimer(_interval);
                while (await timer.WaitForNextTickAsync(token).ConfigureAwait(false))
                {
                    PerformHealthCheck("watchdog");
                }
            }
            catch (OperationCanceledException)
            {
                // Cierre normal.
            }
            catch (Exception ex)
            {
                Emit($"Self-healer watchdog detenido por error: {ex.Message}");
                Debug.WriteLine(ex);
            }
        }

        private static void PerformHealthCheck(string phase)
        {
            if (!CheckGate.Wait(0))
            {
                return;
            }

            try
            {
                EnsureCriticalDirectories();
                CheckCorruptedPeerFiles();
                CheckStaleLockFiles();
                CheckDiskSpace(phase);
            }
            finally
            {
                CheckGate.Release();
            }
        }

        private static void EnsureCriticalDirectories()
        {
            foreach (var (path, label) in GetCriticalDirectories())
            {
                try
                {
                    if (!Directory.Exists(path))
                    {
                        Directory.CreateDirectory(path);
                        Emit($"Directorio restaurado: {label}");
                    }
                }
                catch (Exception ex)
                {
                    Emit($"No se pudo asegurar '{label}': {ex.Message}");
                }
            }
        }

        private static IEnumerable<(string Path, string Label)> GetCriticalDirectories()
        {
            string projectDir = ResolveProjectDir();
            string stateDir = Path.Combine(projectDir, "Estado_Global");
            string peersDir = Path.Combine(stateDir, "peers");
            string wwwDir = Path.Combine(AppContext.BaseDirectory, "www");

            yield return (AppDataRoot, "AppData WoldVirtualP2P");
            yield return (LogsDir, "Logs de autocuración");
            yield return (IpfsDir, "Base IPFS");
            yield return (Path.Combine(IpfsDir, "repo"), "Repositorio IPFS");
            yield return (stateDir, "Estado_Global");
            yield return (peersDir, "Estado_Global/peers");
            yield return (wwwDir, "Recursos web locales");
        }

        private static string ResolveProjectDir()
        {
            try
            {
                var project = GodotProjectLocator.Resolve();
                return project.ProjectDir;
            }
            catch
            {
                return Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "WoldVirtual"));
            }
        }

        private static void CheckCorruptedPeerFiles()
        {
            string peersDir = Path.Combine(ResolveProjectDir(), "Estado_Global", "peers");
            if (!Directory.Exists(peersDir))
            {
                return;
            }

            foreach (string file in Directory.GetFiles(peersDir, "peer_*.json"))
            {
                try
                {
                    var info = new FileInfo(file);
                    if (info.Length <= 0)
                    {
                        File.Delete(file);
                        Emit($"Archivo peer vacío eliminado: {Path.GetFileName(file)}");
                        continue;
                    }

                    string json = File.ReadAllText(file);
                    if (string.IsNullOrWhiteSpace(json))
                    {
                        File.Delete(file);
                        Emit($"Archivo peer en blanco eliminado: {Path.GetFileName(file)}");
                        continue;
                    }

                    using var doc = JsonDocument.Parse(json);
                    _ = doc.RootElement.ValueKind;
                }
                catch (JsonException)
                {
                    TryDeletePeerFile(file, "JSON inválido");
                }
                catch (Exception ex)
                {
                    TryDeletePeerFile(file, ex.Message);
                }
            }
        }

        private static void TryDeletePeerFile(string file, string reason)
        {
            try
            {
                File.Delete(file);
                Emit($"Peer corrupto eliminado ({reason}): {Path.GetFileName(file)}");
            }
            catch (Exception ex)
            {
                Emit($"No se pudo eliminar peer corrupto '{Path.GetFileName(file)}': {ex.Message}");
            }
        }

        private static void CheckStaleLockFiles()
        {
            string[] staleFiles =
            {
                Path.Combine(IpfsManager.RepoPath, "repo.lock"),
                Path.Combine(IpfsManager.RepoPath, "api")
            };

            foreach (string file in staleFiles)
            {
                try
                {
                    if (File.Exists(file))
                    {
                        File.Delete(file);
                        Emit($"Bloqueo IPFS huérfano eliminado: {Path.GetFileName(file)}");
                    }
                }
                catch (Exception ex)
                {
                    Emit($"No se pudo limpiar '{Path.GetFileName(file)}': {ex.Message}");
                }
            }
        }

        private static void CheckDiskSpace(string phase)
        {
            foreach (string path in GetPathsToInspect())
            {
                try
                {
                    string root = Path.GetPathRoot(Path.GetFullPath(path)) ?? string.Empty;
                    if (string.IsNullOrWhiteSpace(root))
                    {
                        continue;
                    }

                    var drive = new DriveInfo(root);
                    if (!drive.IsReady)
                    {
                        continue;
                    }

                    long freeBytes = drive.AvailableFreeSpace;
                    if (freeBytes < LowDiskSpaceThresholdBytes)
                    {
                        Emit($"Espacio libre bajo ({phase}) en {drive.Name}: {freeBytes / 1024 / 1024} MiB");
                    }
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[SelfHeal] Error comprobando disco para '{path}': {ex.Message}");
                }
            }
        }

        private static IEnumerable<string> GetPathsToInspect()
        {
            yield return AppContext.BaseDirectory;
            yield return ResolveProjectDir();
            yield return IpfsManager.RepoPath;
        }

        private static void Emit(string message)
        {
            string line = $"[{DateTimeOffset.Now:O}] {message}";
            Debug.WriteLine(line);
            var handlers = OnHealAction;
            if (handlers != null)
            {
                foreach (Action<string> handler in handlers.GetInvocationList())
                {
                    try
                    {
                        handler(message);
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"[SelfHeal] Listener error: {ex.Message}");
                    }
                }
            }
            WriteLogLine(line);
        }

        private static void WriteLogLine(string line)
        {
            try
            {
                Directory.CreateDirectory(LogsDir);
                File.AppendAllText(Path.Combine(LogsDir, "selfheal_log.txt"), line + Environment.NewLine);
            }
            catch
            {
                // Nunca dejamos que el autocorrector falle por el log.
            }
        }
    }
}
