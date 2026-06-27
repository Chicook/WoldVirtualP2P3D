using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Módulo de Corrección Automática de Errores en Tiempo de Ejecución.
    /// Detecta condiciones anómalas comunes durante la operación del visor
    /// y aplica acciones correctivas de forma autónoma antes de que se
    /// conviertan en fallos visibles o crashes.
    /// </summary>
    public static class RuntimeSelfHealer
    {
        private static readonly string LogDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "WoldVirtualP2P", "logs");

        private static readonly string HealLogFile = Path.Combine(LogDir, "selfheal_log.txt");

        private static Timer? _watchdogTimer;
        private static bool _initialized;

        // ─── Directorios críticos que el visor necesita para funcionar ────────
        private static readonly List<string> CriticalDirectories = [];

        /// <summary>Evento para notificar a la UI de acciones correctivas.</summary>
        public static event Action<string>? OnHealAction;

        // ─── API Pública ─────────────────────────────────────────────────────

        /// <summary>
        /// Inicializa el módulo de auto-corrección.
        /// Ejecuta un chequeo inicial y programa un watchdog periódico.
        /// </summary>
        /// <param name="peersDir">Ruta al directorio de peers del visor.</param>
        /// <param name="estadoGlobalDir">Ruta al directorio Estado_Global.</param>
        /// <param name="intervalSeconds">Intervalo del watchdog en segundos (por defecto 60).</param>
        public static void Initialize(string? peersDir = null, string? estadoGlobalDir = null, int intervalSeconds = 60)
        {
            if (_initialized) return;
            _initialized = true;

            if (!Directory.Exists(LogDir))
                Directory.CreateDirectory(LogDir);

            // Registrar directorios críticos
            if (!string.IsNullOrEmpty(peersDir))
                CriticalDirectories.Add(peersDir);
            if (!string.IsNullOrEmpty(estadoGlobalDir))
                CriticalDirectories.Add(estadoGlobalDir);

            // Chequeo inmediato al arranque
            RunAllChecks();

            // Watchdog periódico
            _watchdogTimer = new Timer(
                _ => RunAllChecks(),
                null,
                TimeSpan.FromSeconds(intervalSeconds),
                TimeSpan.FromSeconds(intervalSeconds));

            Log("🛡️ RuntimeSelfHealer inicializado.");
        }

        /// <summary>
        /// Ejecuta todos los chequeos de salud y aplica correcciones.
        /// Puede invocarse manualmente además del watchdog automático.
        /// </summary>
        public static void RunAllChecks()
        {
            try
            {
                CheckCriticalDirectories();
                CheckCorruptedPeerFiles();
                CheckDiskSpace();
                CheckStaleLockFiles();
            }
            catch (Exception ex)
            {
                Log($"⚠️ Error durante chequeo de salud: {ex.Message}");
            }
        }

        /// <summary>Detiene el watchdog periódico.</summary>
        public static void Shutdown()
        {
            _watchdogTimer?.Dispose();
            _watchdogTimer = null;
            _initialized = false;
            Log("⏹ RuntimeSelfHealer detenido.");
        }

        // ─── Chequeos Individuales ───────────────────────────────────────────

        /// <summary>
        /// Verifica que los directorios críticos existan. Si alguno fue borrado
        /// accidentalmente, lo recrea de forma silenciosa para evitar NullRef o
        /// DirectoryNotFoundException en tiempo de ejecución.
        /// </summary>
        private static void CheckCriticalDirectories()
        {
            foreach (var dir in CriticalDirectories)
            {
                if (!Directory.Exists(dir))
                {
                    try
                    {
                        Directory.CreateDirectory(dir);
                        LogHeal($"📁 Directorio crítico recreado: {dir}");
                    }
                    catch (Exception ex)
                    {
                        Log($"❌ No se pudo recrear directorio {dir}: {ex.Message}");
                    }
                }
            }
        }

        /// <summary>
        /// Escanea archivos peer_*.json buscando archivos corruptos (vacíos,
        /// JSON inválido o de tamaño 0) y los elimina para evitar que el
        /// deserializador lance excepciones en el bucle de sincronización.
        /// </summary>
        private static void CheckCorruptedPeerFiles()
        {
            foreach (var dir in CriticalDirectories)
            {
                if (!Directory.Exists(dir)) continue;

                foreach (var file in Directory.GetFiles(dir, "peer_*.json"))
                {
                    try
                    {
                        var info = new FileInfo(file);

                        // Archivo vacío o extremadamente pequeño (< 3 bytes = "{}")
                        if (info.Length < 3)
                        {
                            info.Delete();
                            LogHeal($"🗑️ Archivo peer vacío eliminado: {info.Name}");
                            continue;
                        }

                        // Intentar leer y verificar que empiece con '{'
                        string content = File.ReadAllText(file);
                        string trimmed = content.TrimStart();
                        if (trimmed.Length == 0 || trimmed[0] != '{')
                        {
                            File.Delete(file);
                            LogHeal($"🗑️ Archivo peer corrupto eliminado (no es JSON): {Path.GetFileName(file)}");
                        }
                    }
                    catch (IOException)
                    {
                        // Archivo bloqueado por otro proceso, ignorar
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"[SelfHealer] Error verificando {file}: {ex.Message}");
                    }
                }
            }
        }

        /// <summary>
        /// Comprueba que haya espacio libre suficiente en el disco donde opera
        /// el visor. Si queda menos de 100 MB, emite una advertencia para que
        /// el usuario libere espacio antes de que IPFS o el filesystem fallen.
        /// </summary>
        private static void CheckDiskSpace()
        {
            try
            {
                string rootPath = Path.GetPathRoot(LogDir) ?? "C:\\";
                var driveInfo = new DriveInfo(rootPath);

                if (driveInfo.IsReady && driveInfo.AvailableFreeSpace < 100L * 1024 * 1024)
                {
                    LogHeal($"⚠️ Espacio en disco bajo: {driveInfo.AvailableFreeSpace / (1024 * 1024)} MB libres en {rootPath}");
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SelfHealer] Error comprobando espacio en disco: {ex.Message}");
            }
        }

        /// <summary>
        /// Detecta y elimina archivos de bloqueo huérfanos del repositorio IPFS
        /// que pueden impedir que el daemon Kubo arranque después de un cierre
        /// inesperado de la aplicación.
        /// </summary>
        private static void CheckStaleLockFiles()
        {
            try
            {
                string ipfsRepo = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "WoldVirtualP2P", "ipfs", "repo");

                if (!Directory.Exists(ipfsRepo)) return;

                string lockFile = Path.Combine(ipfsRepo, "repo.lock");
                string apiFile = Path.Combine(ipfsRepo, "api");

                // Solo limpiar si no hay proceso ipfs corriendo
                bool ipfsRunning = false;
                try
                {
                    var procs = Process.GetProcessesByName("ipfs");
                    ipfsRunning = procs.Length > 0;
                    foreach (var p in procs) p.Dispose();
                }
                catch { /* sin permisos para listar procesos */ }

                if (!ipfsRunning)
                {
                    if (File.Exists(lockFile))
                    {
                        File.Delete(lockFile);
                        LogHeal("🔓 Lock huérfano de IPFS eliminado: repo.lock");
                    }
                    if (File.Exists(apiFile))
                    {
                        File.Delete(apiFile);
                        LogHeal("🔓 Archivo API huérfano de IPFS eliminado: api");
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SelfHealer] Error limpiando locks IPFS: {ex.Message}");
            }
        }

        // ─── Logging ─────────────────────────────────────────────────────────

        private static void LogHeal(string message)
        {
            Log(message);
            OnHealAction?.Invoke(message);
        }

        private static void Log(string message)
        {
            try
            {
                string timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
                string entry = $"[{timestamp}] {message}\n";
                File.AppendAllText(HealLogFile, entry);
                Debug.WriteLine($"[SelfHealer] {message}");
            }
            catch
            {
                // Si el logger falla, no propagamos la excepción.
            }
        }
    }
}
