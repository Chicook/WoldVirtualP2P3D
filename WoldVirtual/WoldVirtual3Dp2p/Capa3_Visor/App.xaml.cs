using System.Configuration;
using System.Data;
using System.Windows;

namespace VisorSingularity;

/// <summary>
/// Interaction logic for App.xaml
/// </summary>
public partial class App : System.Windows.Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        // Initialize Windows Forms for Godot embedding
        System.Windows.Forms.Application.EnableVisualStyles();
        System.Windows.Forms.Application.SetCompatibleTextRenderingDefault(false);

        // Global exception handling
        AppDomain.CurrentDomain.UnhandledException += (sender, args) =>
        {
            try
            {
                string logPath = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "visor_debug.log");
                System.IO.File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss.fff}] UNHANDLED EXCEPTION: {args.ExceptionObject}\r\n");
            }
            catch { }
        };

        DispatcherUnhandledException += (sender, args) =>
        {
            try
            {
                string logPath = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "visor_debug.log");
                System.IO.File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss.fff}] DISPATCHER UNHANDLED EXCEPTION: {args.Exception}\r\n");
                args.Handled = true;
            }
            catch { }
            
            System.Windows.MessageBox.Show($"Error crítico: {args.Exception.Message}", "Error", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Error);
        };

        base.OnStartup(e);
    }
}

