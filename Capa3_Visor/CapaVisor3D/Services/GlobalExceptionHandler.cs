using System;
using System.IO;
using System.Windows;
using System.Threading.Tasks;
using System.Diagnostics;

namespace VisorSingularity.Services
{
    /// <summary>
    /// Módulo de Prevención de Errores:
    /// Captura excepciones no controladas de la aplicación, hilos y tareas en segundo plano.
    /// Evita que el visor se cierre silenciosamente ("crashes" invisibles) y registra la
    /// traza del error en un archivo de log para facilitar su diagnóstico y corrección.
    /// </summary>
    public static class GlobalExceptionHandler
    {
        private static readonly string LogDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "WoldVirtualP2P", "logs");

        private static readonly string LogFile = Path.Combine(LogDir, "crash_log.txt");

        public static void Initialize()
        {
            if (!Directory.Exists(LogDir))
                Directory.CreateDirectory(LogDir);

            // 1. Excepciones en el hilo principal de la UI (WPF)
            Application.Current.DispatcherUnhandledException += (s, e) =>
            {
                LogException("DispatcherUnhandledException", e.Exception);
                ShowErrorDialog("Error crítico en la interfaz gráfica", e.Exception);
                e.Handled = true; // Intenta evitar que la app se cierre si es posible
            };

            // 2. Excepciones no controladas en hilos de fondo (AppDomain)
            AppDomain.CurrentDomain.UnhandledException += (s, e) =>
            {
                var ex = e.ExceptionObject as Exception;
                LogException("AppDomain.UnhandledException", ex);
                ShowErrorDialog("Error crítico en un proceso de fondo", ex);
            };

            // 3. Excepciones no controladas en tareas asíncronas (TaskScheduler)
            TaskScheduler.UnobservedTaskException += (s, e) =>
            {
                LogException("TaskScheduler.UnobservedTaskException", e.Exception);
                // No mostramos MessageBox aquí para no bloquear tareas silenciosas, pero se loguea.
                e.SetObserved();
            };
        }

        private static void LogException(string source, Exception? ex)
        {
            if (ex == null) return;
            try
            {
                string timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
                string logEntry = $"[{timestamp}] [{source}]\n{ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}\n";
                if (ex.InnerException != null)
                {
                    logEntry += $"--- Inner Exception ---\n{ex.InnerException.Message}\n{ex.InnerException.StackTrace}\n";
                }
                logEntry += new string('-', 80) + "\n";

                File.AppendAllText(LogFile, logEntry);
                Debug.WriteLine(logEntry);
            }
            catch
            {
                // Si el logger falla, no podemos hacer mucho más.
            }
        }

        private static void ShowErrorDialog(string title, Exception? ex)
        {
            if (ex == null) return;
            string message = $"Se ha producido un error inesperado. La aplicación intentará continuar, pero podría ser inestable.\n\nDetalle:\n{ex.Message}\n\nLos detalles completos se han guardado en:\n{LogFile}";

            MessageBox.Show(message, title, MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }
}
