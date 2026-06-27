using System.Windows;
using VisorSingularity.Services;

namespace VisorSingularity
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            // Inicializar el módulo de prevención y captura global de errores
            GlobalExceptionHandler.Initialize();

            // Inicializar el módulo de auto-corrección en tiempo de ejecución
            RuntimeSelfHealer.Initialize();

            base.OnStartup(e);
        }
    }
}
