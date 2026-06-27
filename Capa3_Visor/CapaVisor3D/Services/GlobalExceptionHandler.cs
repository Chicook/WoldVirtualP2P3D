using System;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Threading;

namespace VisorSingularity.Services
{
    internal static class GlobalExceptionHandler
    {
        private static readonly object SyncRoot = new();
        private static bool _initialized;

        private static string LogDirectory =>
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "WoldVirtualP2P", "logs");

        private static string LogFilePath => Path.Combine(LogDirectory, "global_exceptions.log");

        public static void Initialize()
        {
            lock (SyncRoot)
            {
                if (_initialized)
                {
                    return;
                }

                _initialized = true;
            }

            AppDomain.CurrentDomain.UnhandledException += OnAppDomainUnhandledException;
            TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;

            if (Application.Current != null)
            {
                Application.Current.DispatcherUnhandledException += OnDispatcherUnhandledException;
            }

            Log("GlobalExceptionHandler inicializado.");
        }

        private static void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
        {
            LogException("DispatcherUnhandledException", e.Exception);
            e.Handled = true;
        }

        private static void OnAppDomainUnhandledException(object sender, UnhandledExceptionEventArgs e)
        {
            if (e.ExceptionObject is Exception ex)
            {
                LogException("AppDomain.UnhandledException", ex);
            }
            else
            {
                Log($"AppDomain.UnhandledException: {e.ExceptionObject}");
            }
        }

        private static void OnUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
        {
            LogException("TaskScheduler.UnobservedTaskException", e.Exception);
            e.SetObserved();
        }

        private static void LogException(string context, Exception exception)
        {
            var builder = new StringBuilder();
            builder.AppendLine($"[{DateTimeOffset.Now:O}] {context}");
            builder.AppendLine(exception.ToString());
            builder.AppendLine(new string('-', 90));
            WriteLog(builder.ToString());
        }

        private static void Log(string message)
        {
            WriteLog($"[{DateTimeOffset.Now:O}] {message}{Environment.NewLine}");
        }

        private static void WriteLog(string content)
        {
            try
            {
                Directory.CreateDirectory(LogDirectory);
                File.AppendAllText(LogFilePath, content, Encoding.UTF8);
            }
            catch
            {
                // Nunca dejamos que el logger global provoque otra excepción.
            }
        }
    }
}
