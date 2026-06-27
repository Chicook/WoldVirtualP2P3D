using System.Windows;
using VisorSingularity.Services;

namespace VisorSingularity
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            GlobalExceptionHandler.Initialize();

            base.OnStartup(e);

            RuntimeSelfHealer.Initialize();
        }

        protected override void OnExit(ExitEventArgs e)
        {
            RuntimeSelfHealer.Stop();
            base.OnExit(e);
        }
    }
}
