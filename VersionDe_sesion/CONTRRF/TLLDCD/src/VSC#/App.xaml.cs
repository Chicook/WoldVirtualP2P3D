using System;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using System.Windows;

namespace Visor3D
{
    public partial class App : Application
    {
        private async void OnStartup(object sender, StartupEventArgs e)
        {
            // ── RESET COMPLETO DE SESIÓN ─────────────────────────────────────────
            // Borra datos de usuario locales para que GitHub siempre arranque limpio.
            // El usuario deberá registrarse de nuevo como si fuera la primera vez.
            LimpiarDatosDeUsuario();

            // Extraer Godot + proyecto 3D al LocalAppData si no esta ya
            if (!AppExtractor.EnsureExtracted())
            {
                // Si falla la extraccion, abrimos igual la ventana principal
                // (intentara buscar Godot por rutas alternativas)
            }

            // Auto-actualización: consultar GitHub Release y descargar versión nueva
            _ = CheckForUpdateAsync();

            var mainWindow = new MainWindow();
            mainWindow.Show();
        }

        private static async Task CheckForUpdateAsync()
        {
            try
            {
                var checker = new Visor3D.Update.UpdateChecker();
                var current = System.Reflection.Assembly.GetExecutingAssembly().GetName().Version?.ToString(3) ?? "0.0.0";
                var release = await checker.CheckForUpdateAsync(current);
                if (release == null) return;

                var downloader = new Visor3D.Update.UpdateDownloader();
                await downloader.DownloadAsync(release);
            }
            catch
            {
                // Sin red o release no disponible: el visor arranca con la versión actual.
            }
        }

        protected override void OnExit(ExitEventArgs e)
        {
            try
            {
                var exe = Process.GetCurrentProcess().MainModule?.FileName
                    ?? Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Visor3D.exe");
                Visor3D.Update.UpdateApplier.ApplyPendingUpdate(exe);
            }
            catch
            {
                // Si falla el reemplazo, el visor sigue con la versión actual.
            }
            base.OnExit(e);
        }

        /// <summary>
        /// Elimina toda la carpeta test_user_data (credenciales, perfil, llave)
        /// y también el archivo registro.cfg del directorio user:// de Godot,
        /// garantizando un estado completamente limpio en cada arranque.
        /// </summary>
        private static void LimpiarDatosDeUsuario()
        {
            try
            {
                // 1. Borrar datos del visor C#
                string testUserDataDir = Path.Combine(
                    AppDomain.CurrentDomain.BaseDirectory, "test_user_data");
                if (Directory.Exists(testUserDataDir))
                    Directory.Delete(testUserDataDir, recursive: true);

                // 2. Borrar registro de Godot (user://registro.cfg) en app_userdata
                string godotUserDir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "Godot", "app_userdata", "WoldVirtualP2P3D");
                string registroCfg = Path.Combine(godotUserDir, "registro.cfg");
                if (File.Exists(registroCfg))
                    File.Delete(registroCfg);

                // 3. Borrar p2p_session.json de Godot para no retomar sesiones viejas
                string p2pSession = Path.Combine(godotUserDir, "p2p_session.json");
                if (File.Exists(p2pSession))
                    File.Delete(p2pSession);

                // 4. Escribir flag para que Boot.gd sepa que debe iniciar como usuario nuevo
                //    (carpeta se recrea luego en RegistroWindow al guardar nuevos datos)
                if (!Directory.Exists(godotUserDir))
                    Directory.CreateDirectory(godotUserDir);
                File.WriteAllText(Path.Combine(godotUserDir, "reset_flag.txt"),
                    "reset_" + DateTime.UtcNow.ToString("yyyyMMddHHmmss"));
            }
            catch
            {
                // Silencioso: si no puede borrar, el visor abre igual
            }
        }
    }
}