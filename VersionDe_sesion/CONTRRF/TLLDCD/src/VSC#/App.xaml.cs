using System;
using System.IO;
using System.Windows;
using Visor3D.Chat;
using Visor3D.Services;

namespace Visor3D
{
    public partial class App : Application
    {
        // WebNodo embebido — accesible globalmente para que MainWindow sincronice la URL del túnel P2P
        public static WebNodoService WebNodo { get; } = new WebNodoService();
        private void OnStartup(object sender, StartupEventArgs e)
        {
            // Prueba de humo del chat sin abrir ventana ni extraer el motor.
            if (Array.Exists(e.Args, a => a.Equals("--chat-selftest", StringComparison.OrdinalIgnoreCase)))
            {
                Environment.Exit(ChatSelfTest.Run());
                return;
            }

            // Prueba de arranque previa a publicar: recursos, extracción, portal y motor.
            if (Array.Exists(e.Args, a => a.Equals("--startup-selftest", StringComparison.OrdinalIgnoreCase)))
            {
                Environment.Exit(StartupSelfTest.Run());
                return;
            }

            // ── RESET COMPLETO DE SESIÓN ─────────────────────────────────────────
            // Comentado para preservar la cuenta del usuario entre sesiones y actualizaciones.
            // LimpiarDatosDeUsuario();

            // ── Procesar argumentos de conexión remota (CLI / Enlace de Invitado) ──
            string? initialConnectionUrl = ParseCommandLineArgs(e.Args);
            if (!string.IsNullOrWhiteSpace(initialConnectionUrl))
            {
                Console.WriteLine($"[App] Parámetro de conexión remota detectado: {initialConnectionUrl}");
                System.Diagnostics.Debug.WriteLine($"[App] Parámetro de conexión remota detectado: {initialConnectionUrl}");
            }

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

            var mainWindow = new MainWindow(initialConnectionUrl);
            mainWindow.Show();
        }

        private static string? ParseCommandLineArgs(string[]? args)
        {
            if (args == null || args.Length == 0) return null;

            string? connectionUrl = null;
            for (int i = 0; i < args.Length; i++)
            {
                string arg = args[i].Trim();
                if (arg.StartsWith("--peer-url=", StringComparison.OrdinalIgnoreCase))
                {
                    connectionUrl = arg.Substring("--peer-url=".Length).Trim('"', '\'');
                }
                else if (arg.StartsWith("--ip=", StringComparison.OrdinalIgnoreCase))
                {
                    connectionUrl = arg.Substring("--ip=".Length).Trim('"', '\'');
                }
                else if (arg.StartsWith("--host=", StringComparison.OrdinalIgnoreCase))
                {
                    connectionUrl = arg.Substring("--host=".Length).Trim('"', '\'');
                }
                else if (arg.Equals("--ip", StringComparison.OrdinalIgnoreCase) ||
                         arg.Equals("-ip", StringComparison.OrdinalIgnoreCase) ||
                         arg.Equals("--host", StringComparison.OrdinalIgnoreCase))
                {
                    if (i + 1 < args.Length && !args[i + 1].StartsWith("-"))
                    {
                        connectionUrl = args[++i].Trim('"', '\'');
                    }
                }
                else if (arg.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
                         arg.StartsWith("https://", StringComparison.OrdinalIgnoreCase) ||
                         arg.StartsWith("woldvirtual://", StringComparison.OrdinalIgnoreCase))
                {
                    connectionUrl = arg.Trim('"', '\'');
                }
                else if (!arg.StartsWith("-") && (arg.Contains(".") || arg.Contains(":")) &&
                         !arg.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) &&
                         !arg.EndsWith(".dll", StringComparison.OrdinalIgnoreCase))
                {
                    connectionUrl = arg.Trim('"', '\'');
                }
            }
            return connectionUrl;
        }

        /// <summary>
        /// Elimina los datos de sesión del usuario guardados en
        /// %LocalAppData%\WoldVirtualP2P3D\ (credenciales, perfil, llave)
        /// y también el archivo registro.cfg del directorio user:// de Godot,
        /// garantizando un estado completamente limpio en cada arranque.
        /// </summary>
        private static void LimpiarDatosDeUsuario()
        {
            try
            {
                // 1. Borrar datos del visor C# de la carpeta de perfil del SO
                string visorDataDir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D");
                if (Directory.Exists(visorDataDir))
                    Directory.Delete(visorDataDir, recursive: true);

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