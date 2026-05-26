using System.IO;
using System.Windows;
using System.Windows.Threading;

namespace VisorSingularity
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);
            // Manejar excepciones no controladas en el hilo principal de la UI
            this.DispatcherUnhandledException += App_DispatcherUnhandledException;
            // Manejar excepciones no controladas en otros hilos (Task, etc.)
            AppDomain.CurrentDomain.UnhandledException += CurrentDomain_UnhandledException;
        }

        private void App_DispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
        {
            LogUnhandledException(e.Exception, "DispatcherUnhandledException");
            e.Handled = true; // Marcar la excepción como manejada para evitar que la aplicación se cierre inmediatamente
            MessageBox.Show("Ha ocurrido un error inesperado. Se ha registrado un informe de error.", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            // Opcional: Cerrar la aplicación después de mostrar el mensaje
            // Current.Shutdown();
        }

        private void CurrentDomain_UnhandledException(object sender, UnhandledExceptionEventArgs e)
        {
            var ex = e.ExceptionObject as Exception;
            if (ex != null)
            {
                LogUnhandledException(ex, "UnhandledException");
            }
            MessageBox.Show("Ha ocurrido un error inesperado en un hilo secundario. Se ha registrado un informe de error.", "Error Crítico", MessageBoxButton.OK, MessageBoxImage.Error);
            // Si e.IsTerminating es true, la aplicación se cerrará de todos modos.
        }

        private void LogUnhandledException(Exception exception, string source)
        {
            string logFilePath = Path.Combine(Path.GetTempPath(), "VisorSingularity_ErrorLog.txt");
            try
            {
                using (StreamWriter writer = new StreamWriter(logFilePath, true))
                {
                    writer.WriteLine("--------------------------------------------------");
                    writer.WriteLine($"Fecha y Hora: {DateTime.Now}");
                    writer.WriteLine($"Fuente: {source}");
                    writer.WriteLine($"Mensaje: {exception.Message}");
                    writer.WriteLine($"StackTrace: {exception.StackTrace}");
                    if (exception.InnerException != null)
                    {
                        writer.WriteLine($"InnerException Mensaje: {exception.InnerException.Message}");
                        writer.WriteLine($"InnerException StackTrace: {exception.InnerException.StackTrace}");
                    }
                    writer.WriteLine("--------------------------------------------------");
                    writer.WriteLine();
                }
            }
            catch (Exception ex)
            {
                // Si no podemos escribir en el log, al menos mostrarlo en la consola de depuración
                System.Diagnostics.Debug.WriteLine($"Error al escribir en el log de errores: {ex.Message}");
            }
        }
    }
}
