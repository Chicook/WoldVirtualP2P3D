using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Styling;
using Avalonia.Themes.Fluent;

namespace Visor3D.Linux.Vistas
{
    public sealed class Aplicacion : Application
    {
        public override void Initialize()
        {
            RequestedThemeVariant = ThemeVariant.Dark;
            Styles.Add(new FluentTheme());
        }

        public override void OnFrameworkInitializationCompleted()
        {
            if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime escritorio)
            {
                var ventana = new VentanaPrincipal();
                escritorio.MainWindow = ventana;
                ventana.Show();
            }

            base.OnFrameworkInitializationCompleted();
        }
    }
}
