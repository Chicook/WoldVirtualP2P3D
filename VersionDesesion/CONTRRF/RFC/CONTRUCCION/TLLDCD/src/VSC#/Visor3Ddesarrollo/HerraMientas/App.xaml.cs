using System;
using System.Diagnostics;
using System.IO;
using System.Windows;
using Microsoft.Win32;
using Visor3D.Chat;
using Visor3D.Seguridad.SesionUnica;
using Visor3D.Services;
namespace Visor3D
{
    public partial class App : Application
    {
        // WebNodo embebido — accesible globalmente para que MainWindow sincronice la URL del túnel P2P
        public static WebNodoService WebNodo { get; } = new WebNodoService();
        public App()
        {
            DispatcherUnhandledException += (_, e) =>
                VisorLog.Error("[Inicio] Excepción no controlada en el dispatcher.", e.Exception);
            AppDomain.CurrentDomain.UnhandledException += (_, e) =>
                VisorLog.Error($"[Inicio] Excepción no controlada del proceso (terminando={e.IsTerminating}).", e.ExceptionObject as Exception);
        }

        private void OnStartup(object sender, StartupEventArgs e)
        {
            VisorLog.Info($"[Inicio] OnStartup; ejecutable={Environment.ProcessPath ?? "desconocido"}; argumentos={string.Join(" ", e.Args)}.");
            if (Array.Exists(e.Args, a => a.Equals("--seguridad-selftest", StringComparison.OrdinalIgnoreCase)))
            {
                Environment.Exit(SeguridadSelfTest.Run());
                return;
            }

            if (Array.Exists(e.Args, a => a.Equals("--lucia-selftest", StringComparison.OrdinalIgnoreCase)))
            {
                Environment.Exit(StartupSelfTest.RunLucia());
                return;
            }

            // Prueba del arranque de cuenta sobre directorios temporales.
            if (Array.Exists(e.Args, a => a.Equals("--cuenta-selftest", StringComparison.OrdinalIgnoreCase)))
            {
                Environment.Exit(CuentaSelfTest.Run());
                return;
            }

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

            // Proceso auxiliar para el portal: HttpListener funciona en MTA y
            // falla con "Controlador no válido" en el hilo STA de WPF.
            if (Array.Exists(e.Args, a => a.Equals("--webnodo-helper", StringComparison.OrdinalIgnoreCase)))
            {
                ShutdownMode = ShutdownMode.OnExplicitShutdown;
                var hilo = new System.Threading.Thread(() =>
                {
                    var servicio = new WebNodoService();
                    try
                    {
                        servicio.Start();
                    }
                    catch (Exception ex)
                    {
                        try
                        {
                            System.IO.File.WriteAllText(
                                System.IO.Path.Combine(System.IO.Path.GetTempPath(), "wvp_webnodo_helper.txt"),
                                $"EX|{ex.GetType().Name}|{ex.Message}");
                        }
                        catch { }
                        Environment.Exit(3);
                    }
                    try
                    {
                        System.IO.File.WriteAllText(
                            System.IO.Path.Combine(System.IO.Path.GetTempPath(), "wvp_webnodo_helper.txt"),
                            $"{servicio.IsRunning}|{servicio.ActivePort}|{servicio.StartError}");
                    }
                    catch { }
                    if (servicio.IsRunning)
                        System.Threading.Thread.Sleep(System.Threading.Timeout.Infinite);
                    else
                        Environment.Exit(2);
                });
                hilo.SetApartmentState(System.Threading.ApartmentState.MTA);
                hilo.IsBackground = false;
                hilo.Start();
                // Sin ventana, WPF cerraría al volver de OnStartup; mantener vivo
                // el proceso auxiliar mientras el hilo MTA sirve el portal.
                System.Threading.Thread.Sleep(System.Threading.Timeout.Infinite);
                return;
            }

            // Autoprueba del WebNodo frente al OTA (W-01/DT-11): el portal anuncia
            // la release instalada y /descargar sirve el binario local, no un 301.
            if (Array.Exists(e.Args, a => a.Equals("--webnodo-selftest", StringComparison.OrdinalIgnoreCase)))
            {
                Environment.Exit(WebNodoSelfTest.Run());
                return;
            }

            // Autoprueba de actualización OTA sin GUI (H2 / H4): fail-closed sin digest,
            // rechazo de hash inválido, detección de truncado y verificación íntegra.
            if (Array.Exists(e.Args, a => a.Equals("--update-selftest", StringComparison.OrdinalIgnoreCase)))
            {
                Environment.Exit(Visor3D.Update.UpdateSelfTest.Run());
                return;
            }

            bool reiniciarCuenta = Array.Exists(e.Args,
                a => a.Equals("--reset-cuenta", StringComparison.OrdinalIgnoreCase));

            RegistrarProtocoloInvitacion();

            // ── UNA SOLA VENTANA ────────────────────────────────────────────────
            // Abrir el visor otra vez debe mostrar la sesión que ya está en
            // marcha (avatar incluido), no un segundo inicio de sesión.
            if (!InstanciaUnica.EsPrimeraInstancia())
            {
                VisorLog.Warn("[Inicio] Ya existe una instancia; se enfoca la ventana activa y se cierra este proceso.");
                if (reiniciarCuenta)
                {
                    MessageBox.Show(
                        "El visor ya está abierto. Ciérralo antes de reiniciar la cuenta.",
                        "WoldVirtualP2P3D", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                else
                {
                    string? enlaceInvitacion = ParseCommandLineArgs(e.Args);
                    if (EsInvitacionValida(enlaceInvitacion) && enlaceInvitacion != null)
                        InstanciaUnica.EnviarInvitacionAInstanciaExistente(enlaceInvitacion);
                    InstanciaUnica.EnfocarInstanciaExistente();
                }

                Shutdown(0);
                return;
            }
            VisorLog.Info("[Inicio] Instancia única adquirida.");

            // ── PUERTA DE ARRANQUE STM_DEF (fail-closed) ────────────────────────
            // Antes de abrir el visor se corre el hook del subsistema defensivo
            // (STM_HRTS\STM_DEF): escaneo estatico del arbol + verificacion del
            // sello de integridad. Un hallazgo ALTA o un sello manipulado detienen
            // el arranque, invirtiendo el paso del dropper (aquel ejecutaba sin
            // comprobar; aqui no se abre ventana sin comprobar antes).
            if (Visor3D.Seguridad.ArranqueSeguro.Bloquea())
            {
                VisorLog.Error("[Inicio] STM_DEF bloqueó el arranque.");
                MessageBox.Show(
                    "El analisis de seguridad (STM_DEF) ha detenido el arranque.\n" +
                    "Revisa los registros en %LOCALAPPDATA%\\WoldVirtualP2P3D\\logs.",
                    "WoldVirtualP2P3D — Seguridad", MessageBoxButton.OK, MessageBoxImage.Warning);
                Shutdown(1);
                return;
            }
            VisorLog.Info("[Inicio] STM_DEF permitió continuar.");

            // ── PERSISTENCIA DE USUARIO ─────────────────────────────────────────
            // El perfil vive fuera de runtime\<versión>, así que una actualización
            // NO debe borrarlo. El reinicio de la base local sólo se ejecuta si se
            // pide expresamente con --reset-cuenta (soporte / reinstalación).
            if (reiniciarCuenta)
            {
                ReinicioCuenta.EjecutarSiProcede(
                    "manual-" + DateTime.UtcNow.ToString("yyyyMMddHHmmss"));
            }

            // ── RESET TOTAL ÚNICO (2.6.4) ───────────────────────────────────────
            // Esta versión deja la base local vacía una sola vez —archivándola en
            // respaldo_cuenta— para que el usuario recorra el registro completo. El
            // marcador reset_total.txt impide que se repita: lo que registre ahora persiste.
            ReinicioCuenta.EjecutarResetTotal(AppExtractor.Version);

            // Equipos que vienen de instalaciones anteriores conservan su cuenta,
            // salvo que ya se haya hecho el reset total.
            if (!ReinicioCuenta.ResetTotalHecho())
                Visor3D.Seguridad.PerfilUsuario.MigrarSiProcede();

            // Sin una cuenta utilizable (restos a medias, datos copiados de otro
            // equipo o instalación nueva con motor viejo) se archiva lo que haya
            // en respaldo_cuenta y el visor arranca el ciclo de registro completo.
            ArranqueCuenta.AsegurarCicloRegistro();

            // Estado global del equipo (adaptado de la configuración Estado_Global):
            // si no queda nada de lo necesario, la ventana abre el registro completo.
            var estadoGlobal = Visor3D.Seguridad.EstadoGlobal.Actualizar();
            VisorLog.Info($"[estado] Equipo {estadoGlobal.Equipo}; acción: {estadoGlobal.Accion}.");

            // ── Procesar argumentos de conexión remota (CLI / Enlace de Invitado) ──
            string? initialConnectionUrl = ParseCommandLineArgs(e.Args);
            if (!string.IsNullOrWhiteSpace(initialConnectionUrl))
            {
                Console.WriteLine($"[App] Parámetro de conexión remota detectado: {initialConnectionUrl}");
                System.Diagnostics.Debug.WriteLine($"[App] Parámetro de conexión remota detectado: {initialConnectionUrl}");
            }

            // ── WebNodo embebido (puerto 3030 o fallback dinámico) ─────────────────
            // Se arranca desde MainWindow en un hilo MTA: HttpListener falla con
            // "Controlador no válido" si se inicia en el hilo STA de WPF.

            this.Exit += (_, _) =>
            {
                WebNodo.Dispose();
                Visor3D.CargaVolatil.VolatilePackage.Liberar();
            };

            // Red de seguridad: si el proceso muere sin pasar por App.Exit
            // (kill, cierre forzado), se purga igualmente el directorio temporal.
            AppDomain.CurrentDomain.ProcessExit += (_, _) =>
                Visor3D.CargaVolatil.VolatilePackage.Liberar();

            // Un motor Godot de una ejecución anterior mantiene ocupado el 8911 y
            // bloquea el .exe del runtime: impide re-extraer el mundo y hace que el
            // motor nuevo no registre la isla (el avatar cae al vacío). Se termina
            // antes de tocar el runtime.
            GodotHwndHost.TerminarMotoresHuerfanos(AppExtractor.GodotExePath);
            VisorLog.Info("[Inicio] Limpieza de motores Godot terminada.");

            // Recolector de runtimes antiguos: sólo purga si el arranque anterior
            // terminó bien, y conserva la versión vigente y la última buena.
            RuntimeCleaner.EjecutarAlArrancar();
            VisorLog.Info("[Inicio] Limpieza de runtime terminada.");

            // Extraer Godot + mundo al LocalAppData si no está ya. La build que
            // embebe el mundo completo no puede arrancar sin él: abrir un PCK de
            // desarrollo o una base vieja deja al avatar sin suelo.
            if (!AppExtractor.EnsureExtracted() && AppExtractor.EmbebeMundoCompleto)
            {
                MessageBox.Show(
                    "No se pudo preparar el mundo 3D de esta versión.\n\n" +
                    "Cierra cualquier visor o proceso Godot que siga abierto y " +
                    "vuelve a iniciar WoldVirtualP2P3D.\n\n" +
                    $"Directorio: {AppExtractor.RuntimeDir}",
                    "WoldVirtualP2P3D — Mundo 3D", MessageBoxButton.OK, MessageBoxImage.Error);
                Shutdown(1);
                return;
            }
            VisorLog.Info($"[Inicio] Preparación de recursos terminada; runtime={AppExtractor.RuntimeDir}.");

            // Montar el paquete volátil (mundo + Lucía + config) desde el .exe.
            // Si el .zip no está embebido (build de desarrollo), se cae al flujo
            // clásico de AppExtractor sin interrumpir el arranque.
            if (Visor3D.CargaVolatil.VolatilePackage.EnsureReady())
            {
                System.Diagnostics.Debug.WriteLine("[VolatilePackage] Paquete montado en RAM.");
            }
            else
            {
                System.Diagnostics.Debug.WriteLine("[VolatilePackage] No embebido: usando extracción clásica.");
            }

            // ── Sincronización de rutas Python (fire-and-forget) ──────────────────
            // Lanza sincronizar_rutas.py en segundo plano para corregir rutas
            // desplazadas en src/STM_HRTS/utils/add_utils/rutas.py antes de que
            // cualquier subsistema Python sea invocado. No bloquea el arranque.
            RutasSyncService.LanzarEnSegundoPlano();

            var mainWindow = new MainWindow(initialConnectionUrl, estadoGlobal.FaltaTodo);
            mainWindow.Show();
            VisorLog.Info("[Inicio] MainWindow.Show ejecutado.");
            InstanciaUnica.EscucharInvitaciones(enlace =>
                mainWindow.Dispatcher.BeginInvoke(new Action(() => mainWindow.AbrirInvitacion(enlace))));
        }

        private static void RegistrarProtocoloInvitacion()
        {
            try
            {
                string ejecutable = Environment.ProcessPath
                    ?? Process.GetCurrentProcess().MainModule?.FileName
                    ?? "";
                if (string.IsNullOrWhiteSpace(ejecutable) ||
                    !Path.GetExtension(ejecutable).Equals(".exe", StringComparison.OrdinalIgnoreCase))
                    return;

                const string rutaProtocolo = @"Software\Classes\woldvirtual";
                using (var comandoExistente = Registry.CurrentUser.OpenSubKey(rutaProtocolo + @"\shell\open\command"))
                {
                    string? valor = comandoExistente?.GetValue(null) as string;
                    if (!string.IsNullOrWhiteSpace(valor) &&
                        !valor.Contains(ejecutable, StringComparison.OrdinalIgnoreCase))
                        return; // No reemplazar el manejador de otro programa.
                }

                using var protocolo = Registry.CurrentUser.CreateSubKey(rutaProtocolo);
                protocolo.SetValue(null, "URL: Wold Virtual invitation");
                protocolo.SetValue("URL Protocol", "");
                using var comando = protocolo.CreateSubKey(@"shell\open\command");
                comando.SetValue(null, $"\"{ejecutable}\" \"%1\"");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[Invitaciones] No se registró woldvirtual://: {ex.Message}");
            }
        }

        private static bool EsInvitacionValida(string? enlace)
        {
            if (string.IsNullOrWhiteSpace(enlace)) return false;
            string limpia = enlace.Trim().Trim('"', '\'');
            if (!Uri.TryCreate(limpia, UriKind.Absolute, out var enlaceUri)) return false;
            string? token = null;
            foreach (string parte in enlaceUri.Query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries))
            {
                int igual = parte.IndexOf('=');
                if (igual <= 0 || !Uri.UnescapeDataString(parte[..igual])
                        .Equals("invitacion", StringComparison.OrdinalIgnoreCase)) continue;
                token = Uri.UnescapeDataString(parte[(igual + 1)..]);
                break;
            }
            return token != null && token.Length == 32 &&
                Array.TrueForAll(token.ToCharArray(), c => (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) &&
                ((enlaceUri.Scheme == Uri.UriSchemeHttp || enlaceUri.Scheme == Uri.UriSchemeHttps) ||
                 enlaceUri.Scheme.Equals("woldvirtual", StringComparison.OrdinalIgnoreCase));
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
