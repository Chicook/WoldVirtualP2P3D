using System;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Layout;
using Avalonia.Threading;
using Visor3D.Chat;
using Visor3D.Linux;
using Visor3D.RedP2P;
using Visor3D.Seguridad;
using Visor3D.Services;

namespace Visor3D.Linux.Vistas
{
    /// <summary>
    /// Visor Linux 2.7.3: cuenta local, mundo 3D, portal WebNodo con túnel,
    /// red P2P e invitación, chat de texto con amigos, actualizaciones y
    /// diagnóstico. Reutiliza el núcleo del visor de Windows; lo específico de
    /// Linux (rutas, sello de equipo, lanzamiento del motor) vive en Linux/.
    /// </summary>
    public sealed partial class VentanaPrincipal : Window
    {
        private readonly WebNodoService _portal = new();
        private readonly LanzadorMundo _motor = new();
        private readonly DispatcherTimer _reloj = new() { Interval = TimeSpan.FromSeconds(2) };

        private RedP2PServicio? _red;
        private ChatRelayServer? _relay;
        private ChatClient? _chat;
        private FriendsStore? _amigos;

        private string _nick = "";
        private string _uuid = "";
        private string _destino = "";
        private bool _dentro;
        private DateTime _arranque = DateTime.UtcNow;

        private readonly TextBlock _txtUsuario = Interfaz.T("Sin sesión", 15, Interfaz.Suave, true);
        private readonly TextBlock _txtSesion = Interfaz.Parrafo("Crea la cuenta local para entrar al mundo.");
        private readonly TextBlock _txtEstado = Interfaz.T("Listo.", 12, Interfaz.Suave);
        private readonly TabControl _pestanas = new();

        public VentanaPrincipal()
        {
            Title = $"Wold Virtual P2P 3D — visor Linux {RutasLinux.Version}";
            Width = 1120;
            Height = 780;
            MinWidth = 940;
            MinHeight = 640;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            Background = Interfaz.Fondo;

            _motor.Salida += linea => EnUi(() => AnadirConsolaMotor(linea));
            _motor.Terminado += _ => EnUi(() =>
            {
                ActualizarEstadoMotor();
                Estado("El motor 3D se ha cerrado.");
            });

            Content = ConstruirInterfaz();
            Opened += (_, _) => IniciarTodo();
            Closed += (_, _) => CerrarTodo();
            _reloj.Tick += (_, _) => Latido();
        }

        // ── Estructura ──────────────────────────────────────────────────────

        private Control ConstruirInterfaz()
        {
            _pestanas.Items.Add(Pestana("Cuenta", ConstruirCuenta()));
            _pestanas.Items.Add(Pestana("Mundo", ConstruirMundo()));
            _pestanas.Items.Add(Pestana("Portal", ConstruirPortal()));
            _pestanas.Items.Add(Pestana("Red P2P", ConstruirRed()));
            _pestanas.Items.Add(Pestana("Chat", ConstruirChat()));
            _pestanas.Items.Add(Pestana("Actualizar", ConstruirActualizar()));
            _pestanas.Items.Add(Pestana("Diagnóstico", ConstruirDiagnostico()));

            var raiz = new Grid
            {
                RowDefinitions = new RowDefinitions("Auto,*,Auto"),
                Margin = new Thickness(18),
            };

            Control cabecera = ConstruirCabecera();
            Grid.SetRow(cabecera, 0);
            raiz.Children.Add(cabecera);

            Grid.SetRow(_pestanas, 1);
            raiz.Children.Add(_pestanas);

            var pie = Interfaz.Tarjeta(_txtEstado);
            pie.Padding = new Thickness(12, 8);
            pie.Margin = new Thickness(0, 10, 0, 0);
            Grid.SetRow(pie, 2);
            raiz.Children.Add(pie);

            return raiz;
        }

        private TabItem Pestana(string titulo, Control contenido) => new()
        {
            Header = titulo,
            Content = new ScrollViewer
            {
                Content = contenido,
                Padding = new Thickness(16),
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            },
        };

        private Control ConstruirCabecera()
        {
            var izquierda = Interfaz.Vertical(
                2,
                Interfaz.T("WOLD VIRTUAL P2P 3D", 26, Interfaz.Acento, true),
                Interfaz.Parrafo($"Visor Linux {RutasLinux.Version} — metaverso P2P con motor Godot 4.7.2", Interfaz.Suave, 13));

            _txtUsuario.HorizontalAlignment = HorizontalAlignment.Right;
            _txtSesion.HorizontalAlignment = HorizontalAlignment.Right;

            var derecha = Interfaz.Vertical(2, _txtUsuario, _txtSesion);
            derecha.HorizontalAlignment = HorizontalAlignment.Right;
            derecha.VerticalAlignment = VerticalAlignment.Center;

            var rejilla = new Grid { ColumnDefinitions = new ColumnDefinitions("*,Auto") };
            Grid.SetColumn(derecha, 1);
            rejilla.Children.Add(izquierda);
            rejilla.Children.Add(derecha);

            var marco = Interfaz.Tarjeta(rejilla);
            marco.Margin = new Thickness(0, 0, 0, 10);
            return marco;
        }

        // ── Ciclo de vida ───────────────────────────────────────────────────

        private void IniciarTodo()
        {
            _arranque = DateTime.UtcNow;
            _reloj.Start();

            var estado = EstadoGlobal.Actualizar(null, RutasLinux.GodotUserDir);
            VisorLog.Info($"[arranque] Equipo {estado.Equipo}; acción: {estado.Accion}; versión {RutasLinux.Version}.");

            _portal.Start();
            if (_portal.IsRunning)
                VisorLog.Info($"[portal] WebNodo escuchando en http://localhost:{_portal.ActivePort}/");
            else
                VisorLog.Warn($"[portal] No disponible: {_portal.StartError}");

            ActualizarPortal();
            ActualizarEstadoMotor();
            RefrescarCuenta();
            RefrescarPaquetes();
            RefrescarDiagnostico();

            if (CuentaLinux.HayCuenta)
                Estado($"Cuenta local de «{CuentaLinux.NombreGuardado()}»: inicia sesión para entrar al mundo.");
            else
                Estado("Equipo sin cuenta: crea la cuenta local en la pestaña Cuenta.");

            // La ventana ya está en pie: el recolector puede purgar los runtimes
            // anteriores en el próximo arranque.
            RuntimeLinux.MarcarArranqueCorrecto();
        }

        private void CerrarTodo()
        {
            _reloj.Stop();
            try { _chat?.Dispose(); } catch { }
            try { _relay?.Dispose(); } catch { }
            try { _red?.Dispose(); } catch { }
            try { _motor.Dispose(); } catch { }
            try { _portal.Dispose(); } catch { }
            VisorLog.Info("[visor] Visor Linux cerrado.");
        }

        private void Latido()
        {
            ActualizarPortal();
            ActualizarRedP2P();
            if (_motor.EnEjecucion) ActualizarEstadoMotor();
            MantenerChatSesion();
            RefrescarDiagnostico();
        }

        // ── Sesión ──────────────────────────────────────────────────────────

        private void Entrar(string nombre, string password)
        {
            var resultado = CuentaLinux.Acceder(nombre, password);
            if (!resultado.Ok)
            {
                Estado(resultado.Mensaje, error: true);
                return;
            }

            _nick = nombre.Trim();
            _uuid = resultado.Uuid;
            _dentro = true;

            _txtUsuario.Text = $"Usuario: {_nick}";
            _txtUsuario.Foreground = Interfaz.Acento;
            _txtSesion.Text = $"Sesión iniciada — uuid {Corto(_uuid)}";
            _txtSesion.Foreground = Interfaz.Bien;

            RefrescarCuenta();
            IniciarServiciosSesion();
            Estado($"Sesión iniciada como «{_nick}». Abre el mundo en la pestaña Mundo.");
        }

        private void SalirSesion()
        {
            _dentro = false;
            _nick = "";
            _uuid = "";
            DetenerChat();
            DetenerRedP2P();
            _txtUsuario.Text = "Sin sesión";
            _txtUsuario.Foreground = Interfaz.Suave;
            _txtSesion.Text = "Crea la cuenta local para entrar al mundo.";
            _txtSesion.Foreground = Interfaz.Suave;
            RefrescarCuenta();
            Estado("Sesión cerrada.");
        }

        private void IniciarServiciosSesion()
        {
            if (!_portal.IsRunning)
            {
                _portal.Start();
                ActualizarPortal();
            }

            _ = IniciarRedP2PAsync();
            IniciarChat();
        }

        private static string Corto(string texto)
            => string.IsNullOrEmpty(texto) ? "—" : texto.Length > 8 ? texto[..8] + "…" : texto;

        // ── Utilidades ──────────────────────────────────────────────────────

        private static void EnUi(Action accion) => Dispatcher.UIThread.Post(accion);

        private void Estado(string mensaje, bool error = false)
        {
            _txtEstado.Text = mensaje;
            _txtEstado.Foreground = error ? Interfaz.Mal : Interfaz.Suave;
            VisorLog.Info($"[visor] {mensaje}");
        }

        private void Copiar(string texto)
        {
            var portapapeles = TopLevel.GetTopLevel(this)?.Clipboard;
            if (portapapeles == null || string.IsNullOrWhiteSpace(texto)) return;
            _ = portapapeles.SetTextAsync(texto);
            Estado("Copiado al portapapeles.");
        }

        private void AbrirEnNavegador(string url)
        {
            try
            {
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                Estado($"No se pudo abrir el navegador: {ex.Message}", error: true);
            }
        }
    }
}
