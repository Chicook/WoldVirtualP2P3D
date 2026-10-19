using System.Windows;

namespace Visor3D
{
    public partial class App : Application
    {
        private void OnStartup(object sender, StartupEventArgs e)
        {
            // Extraer Godot + proyecto 3D al LocalAppData si no esta ya
            if (!AppExtractor.EnsureExtracted())
            {
                // Si falla la extraccion, abrimos igual la ventana principal
                // (intentara buscar Godot por rutas alternativas)
            }

            var mainWindow = new MainWindow();
            mainWindow.Show();
        }
    }
}