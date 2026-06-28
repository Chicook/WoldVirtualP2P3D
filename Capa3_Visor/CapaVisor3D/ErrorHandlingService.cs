using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;

namespace VisorSingularity
{
    /// <summary>
    /// Módulo de prevención y corrección de errores para el proyecto.
    /// Gestiona logging centralizado, manejo seguro de excepciones y recuperación de errores conocidos.
    /// </summary>
    internal static class ErrorHandlingService
    {
        private static readonly object LogLock = new object();
        private static readonly string LogDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WoldVirtualP2P", "logs");
        private static readonly string LogPath = Path.Combine(LogDir, $"errors_{DateTime.Now:yyyyMMdd}.log");

        static ErrorHandlingService()
        {
            try
            {
                if (!Directory.Exists(LogDir))
                    Directory.CreateDirectory(LogDir);
            }
            catch { /* No fallar por logging */ }
        }

        /// <summary>
        /// Manejo seguro de excepciones genéricas: registra y opcionalmente re-lanza.
        /// Preferir siempre capturar excepciones específicas.
        /// </summary>
        public static void HandleException(Exception ex, string context, bool rethrow = false)
        {
            try
            {
                LogError(ex, context);
            }
            catch { /* No fallar por logging */ }

            if (rethrow)
                throw ex;
        }

        /// <summary>
        /// Registra un error en archivo y consola.
        /// </summary>
        public static void LogError(Exception ex, string context)
        {
            var sb = new StringBuilder();
            sb.AppendLine("========================================");
            sb.AppendLine($"[ERROR] {DateTimeOffset.UtcNow:O}");
            sb.AppendLine($"Context: {context}");
            sb.AppendLine($"Type: {ex.GetType().FullName}");
            sb.AppendLine($"Message: {ex.Message}");
            sb.AppendLine($"StackTrace: {ex.StackTrace}");
            sb.AppendLine("========================================");

            string log = sb.ToString();
            Debug.WriteLine(log);

            try
            {
                lock (LogLock)
                {
                    File.AppendAllText(LogPath, log, Encoding.UTF8);
                }
            }
            catch { /* No fallar por logging */ }
        }

        /// <summary>
        /// Registra un warning (para advertencias del analizador o situaciones no fatales).
        /// </summary>
        public static void LogWarning(string message, string context = "")
        {
            var sb = new StringBuilder();
            sb.AppendLine("========================================");
            sb.AppendLine($"[WARNING] {DateTimeOffset.UtcNow:O}");
            if (!string.IsNullOrWhiteSpace(context))
                sb.AppendLine($"Context: {context}");
            sb.AppendLine($"Message: {message}");
            sb.AppendLine("========================================");

            string log = sb.ToString();
            Debug.WriteLine(log);

            try
            {
                lock (LogLock)
                {
                    File.AppendAllText(LogPath, log, Encoding.UTF8);
                }
            }
            catch { /* No fallar por logging */ }
        }

        /// <summary>
        /// Intenta ejecutar una acción con reintentos para errores transitorios.
        /// </summary>
        public static bool TryWithRetries(Action action, int maxRetries = 3, int delayMs = 500, CancellationToken token = default)
        {
            int attempt = 0;
            while (attempt < maxRetries)
            {
                token.ThrowIfCancellationRequested();
                try
                {
                    action();
                    return true;
                }
                catch (IOException) when (attempt < maxRetries - 1)
                {
                    attempt++;
                    Thread.Sleep(delayMs * attempt);
                }
            }
            return false;
        }

        /// <summary>
        /// Intenta ejecutar una función con reintentos para errores transitorios y devuelve el resultado.
        /// </summary>
        public static T? TryWithRetries<T>(Func<T> func, int maxRetries = 3, int delayMs = 500, CancellationToken token = default) where T : class
        {
            int attempt = 0;
            while (attempt < maxRetries)
            {
                token.ThrowIfCancellationRequested();
                try
                {
                    return func();
                }
                catch (IOException) when (attempt < maxRetries - 1)
                {
                    attempt++;
                    Thread.Sleep(delayMs * attempt);
                }
            }
            return null;
        }
    }
}
