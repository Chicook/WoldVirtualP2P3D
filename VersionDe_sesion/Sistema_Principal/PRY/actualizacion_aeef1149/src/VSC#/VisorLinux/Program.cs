using System;
using Avalonia;
using Visor3D.Services;

namespace Visor3D.Linux
{
    internal static class Program
    {
        [STAThread]
        public static int Main(string[] args)
        {
            // Modo sin ventana: valida un despliegue sin abrir el entorno gráfico.
            if (Array.Exists(args, a => a.Equals("--comprobar", StringComparison.OrdinalIgnoreCase)))
                return ComprobacionLocal.Ejecutar();

            // Modo sin ventana: extrae motor y mundo del propio visor y publica las
            // rutas (lo usa woldvirtual-linux.sh para el modo mundo directo).
            if (Array.Exists(args, a => a.Equals("--extraer", StringComparison.OrdinalIgnoreCase)))
                return ComprobacionLocal.Extraer();

            if (!InstanciaUnica.EsPrimeraInstancia())
            {
                InstanciaUnica.EnfocarInstanciaExistente();
                return 0;
            }

            if (OperatingSystem.IsLinux() &&
                string.IsNullOrEmpty(Environment.GetEnvironmentVariable("DISPLAY")) &&
                string.IsNullOrEmpty(Environment.GetEnvironmentVariable("WAYLAND_DISPLAY")))
            {
                Console.Error.WriteLine(
                    "El visor necesita un entorno gráfico (DISPLAY o WAYLAND_DISPLAY). " +
                    "Para comprobar el despliegue sin ventana usa «woldvirtual-linux --comprobar».");
                return 2;
            }

            return BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
        }

        public static AppBuilder BuildAvaloniaApp() =>
            AppBuilder.Configure<Vistas.Aplicacion>()
                .UsePlatformDetect()
                .WithInterFont()
                .LogToTrace();
    }
}
