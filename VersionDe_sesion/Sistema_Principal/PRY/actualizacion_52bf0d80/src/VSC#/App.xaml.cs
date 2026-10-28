using System;
using System.Windows;
using Visor3D.Chat;
using Visor3D.Seguridad.SesionUnica;
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

            // Prueba del descubrimiento P2P: baliza LAN y presencia del portal,
            // sin motor ni PCK. Es la que valida la pantalla previa de ocupación.
            if (Array.Exists(e.Args, a => a.Equals("--red-selftest", StringComparison.OrdinalIgnoreCase)))
            {
                Environment.Exit(RedSelfTest.Run());
                return;
            }

            bool reiniciarCuenta = Array.Exists(e.Args,
                a => a.Equals("--reset-cuenta", StringComparison.OrdinalIgnoreCase));

            // ── UNA SOLA VENTANA ────────────────────────────────────────────────
            // Abrir el visor otra vez debe mostrar la sesión que ya está en
            // marcha (avatar incluido), no un segundo inicio de sesión.
            if (!InstanciaUnica.EsPrimeraInstancia())
            {
                if (reiniciarCuenta)
                {
                    MessageBox.Show(
                        "El visor ya está abierto. Ciérralo antes de reiniciar la cuenta.",
                        "WoldVirtualP2P3D", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                else
                {
                    InstanciaUnica.EnfocarInstanciaExistente();
                }

                Shutdown(0);
                return;
            }

            // ── PERSISTENCIA DE USUARIO ─────────────────────────────────────────
            // El perfil vive fuera de runtime\<versión>, así que una actualización
            // NO debe borrarlo. El reinicio de la base local sólo se ejecuta si se
            // pide expresamente con --reset-cuenta (soporte / reinstalación).
            if (reiniciarCuenta)
            {
                ReinicioCuenta.EjecutarSiProcede(
                    "manual-" + DateTime.UtcNow.ToString("yyyyMMddHHmmss"));
            }

            // Equipos que vienen de instalaciones anteriores conservan su cuenta.
            Visor3D.Seguridad.PerfilUsuario.MigrarSiProcede();

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
    }
}