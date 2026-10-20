using System;
using System.IO;
using System.Windows;
using Visor3D.Services;

namespace Visor3D
{
    public partial class App : Application
    {
        // WebNodo embebido — accesible globalmente para que MainWindow sincronice la URL del túnel P2P
        public static WebNodoService WebNodo { get; } = new WebNodoService();
        private void OnStartup(object sender, StartupEventArgs e)
        {
            // ── RESET COMPLETO DE SESIÓN ─────────────────────────────────────────
            // Borra datos de usuario locales para que GitHub siempre arranque limpio.
            // El usuario deberá registrarse de nuevo como si fuera la primera vez.
            LimpiarDatosDeUsuario();

            // ── WebNodo embebido (puerto 3030 o fallback dinámico) ─────────────────
            WebNodo.Start();
            if (WebNodo.IsRunning)
                System.Diagnostics.Debug.WriteLine($"[WebNodo] Escuchando en http://localhost:{WebNodo.ActivePort}/");
            else
                System.Diagnostics.Debug.WriteLine($"[WebNodo] No disponible: {WebNodo.StartError}");

            this.Exit += (_, _) => WebNodo.Dispose();

            // Extraer Godot + proyecto 3D al LocalAppData si no esta ya
            if (!AppExtractor.EnsureExtracted())
            {
                // Si falla la extraccion, abrimos igual la ventana principal
                // (intentara buscar Godot por rutas alternativas)
            }

            var mainWindow = new MainWindow();
            mainWindow.Show();
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