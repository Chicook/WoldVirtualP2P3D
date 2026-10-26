using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using System.Reflection;
using System.Management;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Effects;
using Microsoft.Win32;
using Visor3D.RedP2P;
using Visor3D.Seguridad;
using Visor3D.Services;
using Visor3D.Update;

namespace Visor3D
{
    public partial class MainWindow : Window
    {
        // Versión local, leída del propio ensamblado (definida en Visor3D.csproj <Version>).
        private static readonly string CurrentVersion = ObtenerVersionLocal();

        // Carpeta de datos del usuario en el perfil local del SO (%LocalAppData%\WoldVirtualP2P3D\)
        // Se usa LocalApplicationData para que no aparezca ninguna carpeta junto al .exe descargado.
        private static readonly string TestUserDataDir =
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "WoldVirtualP2P3D");

        private static readonly string CredentialsPath =
            Path.Combine(TestUserDataDir, "credentials.json");

        private static readonly string UserProfilePath =
            Path.Combine(TestUserDataDir, "user", "user_profile.json");

        private GodotHwndHost? _godotHostMain;
        private RedP2PServicio? _p2pServicio;
        private Process? _tunnelProcess;
        private const string TunelWebNodoSlot = "webnodo";   // slot del PID persistido para el túnel del portal
        private string _urlAmigoPendiente = "";
        private string _ipsLanFallback = "";
        private string _urlPublica = "";
        private string _enlaceCompartible = "";
        private string _hostSesionUrl = "";
        private string _hostInicial = "";
        private readonly DateTime _arranqueUtc = DateTime.UtcNow;
        private string _llaveHashActual = "";
        private int _rotacionesLlave;
        private ReleaseInfo? _updateInfo;
        private bool _descargandoActualizacion;
        private CancellationTokenSource? _ctsDescarga;
        private System.Windows.Threading.DispatcherTimer? _timerMigracion;

        public MainWindow(string? initialConnectionUrl = null)
        {
            InitializeComponent();
            if (!string.IsNullOrWhiteSpace(initialConnectionUrl))
            {
                // El enlace puede traer ?host=<anfitrión raíz>. Todos los invitados
                // deben converger en ese anfitrión, aunque compartan su propio enlace.
                _urlAmigoPendiente = NormalizarUrlSesion(initialConnectionUrl.Trim(), out string? raiz);
                _hostSesionUrl = raiz ?? _urlAmigoPendiente;
                _hostInicial = _hostSesionUrl;
                System.Diagnostics.Debug.WriteLine($"[MainWindow] Enlace de sesión: {_urlAmigoPendiente} (raíz: {_hostSesionUrl})");
                Console.WriteLine($"[MainWindow] Enlace de sesión: {_urlAmigoPendiente} (raíz: {_hostSesionUrl})");
            }

            this.Loaded += OnLoaded;
            this.SizeChanged += (s, e) => AjustarBarraResponsive();
            this.Closing += (s, e) =>
            {
                _godotHostMain?.StopGodot();
                _p2pServicio?.Dispose();
                DetenerTunelWebNodo();
            };

            // Navegación de bienvenida
            BtnCrearCuenta.Click += OnCrearCuentaClicked;
            BtnAcceder.Click += OnAccederClicked;
            BtnVolverBienvenida.Click += OnVolverBienvenidaClicked;

            // Login
            BtnLogin.Click += OnLoginClicked;
            BtnCerrarSesion.Click += (s, e) => MostrarPantallaBienvenida();

            // P2P Interacción
            BtnCopiarUrlP2P.Click += OnCopiarUrlP2PClicked;
            TxtUrlP2P.MouseLeftButtonDown += (s, e) => OnCopiarUrlP2PClicked(s, e);
            BtnConectarAmigo.Click += OnConectarAmigoClicked;

            // WebNodo — portal de descarga y conexión para amigos en el metaverso
            BtnWebNodo.Click += OnWebNodoClicked;

            // Si Godot se cae, se puede reincrustar sin cerrar el visor
            BtnReiniciar3D.Click += (s, e) => ReiniciarMotor3D();

            // Copiar diagnóstico al portapapeles
            BtnDiagnostico.Click += OnDiagnosticoClicked;

            // Vigilar si Godot migró el anfitrión (otro peer asumió la sesión)
            _timerMigracion = new System.Windows.Threading.DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(4)
            };
            _timerMigracion.Tick += (s, e) => ComprobarHostMigrado();
            _timerMigracion.Start();
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            MostrarPantallaBienvenida();
            // MostrarPantallaBienvenida limpia el estado de sesión; si veníamos de un
            // enlace de invitación, se restaura el anfitrión raíz para no perderlo.
            if (!string.IsNullOrEmpty(_hostInicial)) _hostSesionUrl = _hostInicial;
            if (!string.IsNullOrWhiteSpace(_urlAmigoPendiente))
            {
                TxtUrlAmigo.Text = _urlAmigoPendiente;
                TxtEstadoP2P.Text = $"🔗 Destino amigo fijado: {_urlAmigoPendiente}";
            }

            // Iniciar búsqueda de actualizaciones en segundo plano
            _ = Task.Run(CheckUpdatesAsync);
        }

        private void Log(string message)
        {
            VisorLog.Info(message);
            try
            {
                string logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "WoldVirtualP2P3D");
                if (!Directory.Exists(logDir)) Directory.CreateDirectory(logDir);
                string logPath = Path.Combine(logDir, "update_debug.log");
                
                File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss}] {message}{Environment.NewLine}");
                Console.WriteLine($"[Updater] {message}");
            }
            catch { }
        }

        /// <summary>
        /// Lee la versión local del propio ensamblado (definida en el .csproj).
        /// Se usa <c>AssemblyInformationalVersion</c> porque respeta el formato
        /// del tag de GitHub (p. ej. "0.0.013").
        /// </summary>
        private static string ObtenerVersionLocal()
        {
            try
            {
                var asm = Assembly.GetExecutingAssembly();
                var info = asm.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
                if (!string.IsNullOrWhiteSpace(info))
                {
                    int plus = info.IndexOf('+');       // descarta metadatos "+<sha>"
                    return plus >= 0 ? info.Substring(0, plus) : info;
                }

                var v = asm.GetName().Version;
                if (v != null) return $"{v.Major}.{v.Minor}.{v.Build}";
            }
            catch { }
            return "0.0.0";
        }

        private async Task CheckUpdatesAsync()
        {
            Log("Iniciando CheckUpdatesAsync...");
            Dispatcher.Invoke(MostrarActualizadorBuscando);

            try
            {
                Log($"Versión local: {CurrentVersion}");
                var checker = new UpdateChecker();
                _updateInfo = await checker.CheckForUpdateAsync(CurrentVersion);

                var info = _updateInfo;
                if (info != null)
                {
                    Log($"¡Actualización encontrada!: {info.TagName} ({info.Version})");
                    Dispatcher.Invoke(() => MostrarActualizadorDisponible(info));
                }
                else
                {
                    Log("Sistema al día.");
                    Dispatcher.Invoke(MostrarActualizadorAlDia);
                }
            }
            catch (Exception ex)
            {
                Log($"Error crítico: {ex.Message}");
                Dispatcher.Invoke(() => MostrarActualizadorError("No se pudo comprobar si hay actualizaciones."));
            }
        }

        // ── Estados del botón de actualización ────────────────────────────
        // El botón vive SIEMPRE dentro de la barra de sesión: es zona WPF pura,
        // fuera del HwndHost de Godot, así que se ve y recibe clics siempre.

        private static SolidColorBrush Pincel(byte r, byte g, byte b)
        {
            var br = new SolidColorBrush(Color.FromRgb(r, g, b));
            br.Freeze();
            return br;
        }

        private void PararPulso()
        {
            GlowActualizar.BeginAnimation(DropShadowEffect.OpacityProperty, null);
            GlowActualizar.Opacity = 0;
        }

        private void IniciarPulso()
        {
            var pulso = new DoubleAnimation(0.15, 0.85, TimeSpan.FromSeconds(1.6))
            {
                AutoReverse = true,
                RepeatBehavior = new RepeatBehavior(3)
            };
            GlowActualizar.BeginAnimation(DropShadowEffect.OpacityProperty, pulso);
        }

        private void MostrarActualizadorBuscando()
        {
            PararPulso();
            BtnActualizar.IsEnabled = false;
            BtnActualizar.Cursor = System.Windows.Input.Cursors.Wait;
            BtnActualizar.Background = Pincel(0x0F, 0x27, 0x44);
            BtnActualizar.BorderBrush = Pincel(0x1D, 0x3A, 0x5C);
            BtnActualizar.Foreground = Pincel(0x7E, 0xCF, 0xFF);
            IconoDescarga.Visibility = Visibility.Visible;
            IconoAlDia.Visibility = Visibility.Collapsed;
            TxtEtiquetaActualizar.Text = "Buscando…";
            TxtProgresoPorcentaje.Visibility = Visibility.Collapsed;
            BarProgreso.Visibility = Visibility.Collapsed;
            BtnActualizar.ToolTip = "Buscando actualizaciones…";
        }

        private void MostrarActualizadorDisponible(ReleaseInfo info)
        {
            BtnActualizar.IsEnabled = true;
            BtnActualizar.Cursor = System.Windows.Input.Cursors.Hand;
            BtnActualizar.Background = Pincel(0x0B, 0x2A, 0x46);
            BtnActualizar.BorderBrush = Pincel(0x38, 0xBD, 0xF8);
            BtnActualizar.Foreground = Pincel(0xE2, 0xF6, 0xFF);
            IconoDescarga.Visibility = Visibility.Visible;
            IconoAlDia.Visibility = Visibility.Collapsed;
            TxtEtiquetaActualizar.Text = $"Actualizar v{info.Version}";
            TxtProgresoPorcentaje.Visibility = Visibility.Collapsed;
            BarProgreso.Visibility = Visibility.Collapsed;
            BtnActualizar.ToolTip =
                $"Nueva versión {info.Version} disponible.\n" +
                $"Tamaño: {info.AssetSize / 1048576.0:0} MB\n" +
                "Haz clic para descargar e instalar.";
            IniciarPulso();
        }

        private void MostrarActualizadorAlDia()
        {
            PararPulso();
            _updateInfo = null;
            BtnActualizar.IsEnabled = true;
            BtnActualizar.Cursor = System.Windows.Input.Cursors.Hand;
            BtnActualizar.Background = Pincel(0x0F, 0x1F, 0x1A);
            BtnActualizar.BorderBrush = Pincel(0x22, 0xC5, 0x5E);
            BtnActualizar.Foreground = Pincel(0x94, 0xA3, 0xB8);
            IconoDescarga.Visibility = Visibility.Collapsed;
            IconoAlDia.Visibility = Visibility.Visible;
            TxtEtiquetaActualizar.Text = "Al día";
            TxtProgresoPorcentaje.Visibility = Visibility.Collapsed;
            BarProgreso.Visibility = Visibility.Collapsed;
            BtnActualizar.ToolTip = $"Sistema al día (v{CurrentVersion}).\nHaz clic para volver a comprobar.";
        }

        private void MostrarActualizadorDescargando()
        {
            PararPulso();
            BtnActualizar.IsEnabled = true;              // clic = cancelar
            BtnActualizar.Cursor = System.Windows.Input.Cursors.Hand;
            BtnActualizar.Background = Pincel(0x0B, 0x2A, 0x46);
            BtnActualizar.BorderBrush = Pincel(0x38, 0xBD, 0xF8);
            BtnActualizar.Foreground = Pincel(0xE2, 0xF6, 0xFF);
            IconoDescarga.Visibility = Visibility.Visible;
            IconoAlDia.Visibility = Visibility.Collapsed;
            TxtEtiquetaActualizar.Text = "Descargando…";
            TxtProgresoPorcentaje.Text = "0 %";
            TxtProgresoPorcentaje.Visibility = Visibility.Visible;
            FijarProgreso(0);
            BarProgreso.Visibility = Visibility.Visible;
            BtnActualizar.ToolTip = "Descargando la actualización…\nHaz clic para cancelar.";
        }

        private void FijarProgreso(double porcentaje)
        {
            double pct = Math.Clamp(porcentaje, 0, 100);
            ColProgreso.Width = new GridLength(pct, GridUnitType.Star);
            ColResto.Width = new GridLength(Math.Max(0.001, 100 - pct), GridUnitType.Star);
        }

        private void MostrarActualizadorError(string mensaje)
        {
            PararPulso();
            _descargandoActualizacion = false;
            BtnActualizar.IsEnabled = true;
            BtnActualizar.Cursor = System.Windows.Input.Cursors.Hand;
            BtnActualizar.Background = Pincel(0x2A, 0x12, 0x15);
            BtnActualizar.BorderBrush = Pincel(0xF8, 0x71, 0x71);
            BtnActualizar.Foreground = Pincel(0xFC, 0xA5, 0xA5);
            IconoDescarga.Visibility = Visibility.Visible;
            IconoAlDia.Visibility = Visibility.Collapsed;
            TxtEtiquetaActualizar.Text = "Reintentar";
            TxtProgresoPorcentaje.Visibility = Visibility.Collapsed;
            BarProgreso.Visibility = Visibility.Collapsed;
            BtnActualizar.ToolTip = mensaje;
            Log($"[Error updater] {mensaje}");
        }

        private async void OnActualizarClicked(object sender, RoutedEventArgs e)
        {
            // Durante la descarga, el clic cancela (el .part se conserva para reanudar).
            if (_descargandoActualizacion)
            {
                _ctsDescarga?.Cancel();
                return;
            }

            // Sin actualización pendiente, el clic sirve para volver a comprobar.
            if (_updateInfo == null)
            {
                _ = CheckUpdatesAsync();
                return;
            }

            var info = _updateInfo;

            try
            {
                _descargandoActualizacion = true;
                MostrarActualizadorDescargando();

                // Progreso: barra de 2 px en el borde inferior de la barra + % en el pill.
                var progreso = new Progress<DownloadProgress>(p =>
                {
                    FijarProgreso(p.Percentage);
                    TxtProgresoPorcentaje.Text = $"{p.Percentage:0} %";
                });

                _ctsDescarga?.Dispose();
                _ctsDescarga = new CancellationTokenSource();

                var downloader = new UpdateDownloader();
                bool success = await downloader.DownloadAsync(info, progreso, _ctsDescarga.Token);

                if (_ctsDescarga.IsCancellationRequested)
                {
                    _descargandoActualizacion = false;
                    MostrarActualizadorDisponible(info);
                    return;
                }

                if (!success)
                {
                    MostrarActualizadorError(downloader.LastError ??
                        "No se pudo descargar la actualización. Pulsa «Reintentar».");
                    return;
                }

                FijarProgreso(100);
                TxtProgresoPorcentaje.Text = "100 %";
                TxtEtiquetaActualizar.Text = "Reiniciando…";
                BtnActualizar.IsEnabled = false;
                _descargandoActualizacion = false;

                // Delegar el reemplazo del .exe en el script externo y cerrar limpiamente.
                string exeActual = Environment.ProcessPath
                                   ?? Process.GetCurrentProcess().MainModule?.FileName
                                   ?? "";
                bool lanzado = UpdateApplier.ApplyPendingUpdate(exeActual);
                if (!lanzado)
                {
                    MostrarActualizadorError("La actualización se descargó pero no pudo aplicarse automáticamente.");
                    return;
                }

                Application.Current.Shutdown();
            }
            catch (Exception ex)
            {
                MostrarActualizadorError($"Error durante la actualización: {ex.Message}");
            }
        }

        public void MostrarPantallaBienvenida()
        {
            _godotHostMain?.StopGodot();
            ContenedorGodotMain.Children.Clear();
            _godotHostMain = null;

            _p2pServicio?.Dispose();
            _p2pServicio = null;
            DetenerTunelWebNodo();
            BannerP2P.Visibility = Visibility.Collapsed;
            TxtUrlP2P.Text = "";
            _urlPublica = "";
            _enlaceCompartible = "";
            _hostSesionUrl = "";
            _llaveHashActual = "";
            TxtSesionLlave.Text = "Llave: ---";
            TxtSesionLlave.ToolTip = null;

            // Limpiar URL del tunel en el WebNodo al cerrar sesión
            App.WebNodo.PublicTunnelUrl = null;
            BtnWebNodo.Content = "🌐 WebNodo";
            BtnWebNodo.ClearValue(System.Windows.Controls.Button.BackgroundProperty);
            BtnWebNodo.ClearValue(System.Windows.Controls.Button.BorderBrushProperty);
            BtnWebNodo.ToolTip = "Abre el portal de descarga del visor (WebNodo) para compartirlo con tus amigos";

            PanelBienvenida.Visibility = Visibility.Visible;
            PanelMundo3D.Visibility = Visibility.Collapsed;
            BarraInferiorLogin.Visibility = Visibility.Collapsed;

            // Si el usuario ya tiene cuenta local creada y llave, solo mostrar Acceder
            bool estaRegistrado = (File.Exists(UserProfilePath) || File.Exists(CredentialsPath)) &&
                File.Exists(Path.Combine(TestUserDataDir, "user", "llave_acceso.json"));
            BtnCrearCuenta.Visibility = estaRegistrado ? Visibility.Collapsed : Visibility.Visible;
        }

        public void ActivarModoLogin(string username = "")
        {
            _godotHostMain?.StopGodot();
            ContenedorGodotMain.Children.Clear();
            _godotHostMain = null;

            PanelBienvenida.Visibility = Visibility.Collapsed;
            PanelMundo3D.Visibility = Visibility.Collapsed;
            BarraInferiorLogin.Visibility = Visibility.Visible;

            if (!string.IsNullOrEmpty(username))
            {
                TxtLoginUser.Text = username;
                TxtLoginPass.Clear();
                TxtLoginPass.Focus();
            }
            else
            {
                TxtLoginUser.Focus();
            }
        }

        private void OnCrearCuentaClicked(object sender, RoutedEventArgs e)
        {
            // ── Sesión única por PC: bloquear si ya existe una cuenta ──────────
            if (!Visor3D.Seguridad.SesionUnica.SesionUnicaGuarda.ComprobarAntesDeRegistro(this))
                return; // El guard ya mostró el mensaje al usuario

            var registro = new RegistroWindow();
            registro.Show();
        }

        private void OnAccederClicked(object sender, RoutedEventArgs e)
        {
            ActivarModoLogin();
        }

        private void OnVolverBienvenidaClicked(object sender, RoutedEventArgs e)
        {
            MostrarPantallaBienvenida();
        }

        private void OnLoginClicked(object sender, RoutedEventArgs e)
        {
            string user = TxtLoginUser.Text.Trim();
            string pass = TxtLoginPass.Password;

            // Si el usuario introdujo o pegó una URL en TxtUrlAmigo y no había pulsado "Conectar", capturarla
            if (string.IsNullOrWhiteSpace(_urlAmigoPendiente) && !string.IsNullOrWhiteSpace(TxtUrlAmigo.Text))
            {
                _urlAmigoPendiente = NormalizarUrlSesion(TxtUrlAmigo.Text, out string? raiz);
                _hostSesionUrl = raiz ?? _urlAmigoPendiente;
                Console.WriteLine($"[MainWindow] Enlace de sesión desde el formulario: {_urlAmigoPendiente} (raíz: {_hostSesionUrl})");
                System.Diagnostics.Debug.WriteLine($"[MainWindow] Enlace de sesión desde el formulario: {_urlAmigoPendiente} (raíz: {_hostSesionUrl})");
            }

            if (string.IsNullOrWhiteSpace(user) || string.IsNullOrWhiteSpace(pass))
            {
                MessageBox.Show("Por favor, introduce tu usuario y contraseña.",
                                "Validación", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Validar credenciales
            if (!ValidarCredenciales(user, pass))
            {
                MessageBox.Show("Usuario o contraseña incorrectos.",
                                "Ingreso fallido", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Credenciales válidas: comprobar sesión única por PC (segunda barrera)
            // Si el PC ya tiene sello de OTRO usuario, bloqueamos aquí antes del diálogo de llave.
            string uuidLogin = ObtenerUuidDelPerfil(user);
            if (!Visor3D.Seguridad.SesionUnica.SesionUnicaGuarda.ComprobarSesionActivaEnPc(uuidLogin, this))
                return;

            // Credenciales válidas: Solicitar «La Llave»
            MessageBox.Show(
                $"Credenciales de «{user}» verificadas con éxito.\n\n" +
                "A continuación, selecciona tu archivo «La Llave» (llave_acceso.json) para autenticar la sesión criptográfica.",
                "Paso de Autenticación con Llave",
                MessageBoxButton.OK,
                MessageBoxImage.Information);

            var dialog = new OpenFileDialog
            {
                Title = "Selecciona tu archivo «La Llave» (llave_acceso.json)",
                Filter = "Archivo Llave (*.json)|*.json|Todos los archivos (*.*)|*.*",
                InitialDirectory = Path.Combine(TestUserDataDir, "user")
            };

            if (dialog.ShowDialog() != true)
            {
                MessageBox.Show("No se seleccionó ninguna llave. Inicio de sesión cancelado.",
                                "Aviso", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Verificar la llave y rotar su hash único
            try
            {
                string jsonLlave = File.ReadAllText(dialog.FileName, Encoding.UTF8);
                using var doc = JsonDocument.Parse(jsonLlave);
                var root = doc.RootElement;

                // Comprobar que sea una llave válida y pertenezca al usuario
                string llaveUsuario = root.TryGetProperty("usuario", out var u) ? u.GetString() ?? "" : "";
                if (!llaveUsuario.Equals(user, StringComparison.OrdinalIgnoreCase))
                {
                    MessageBox.Show(
                        $"La llave seleccionada pertenece a «{llaveUsuario}», no a «{user}».\nAcceso denegado.",
                        "Llave no coincide",
                        MessageBoxButton.OK,
                        MessageBoxImage.Error);
                    return;
                }

                string oldHash = root.TryGetProperty("hash_llave", out var h) ? h.GetString() ?? "" : "";
                string uuid = root.TryGetProperty("uuid", out var idProp) ? idProp.GetString() ?? "" : "";
                string hwHash = root.TryGetProperty("hardware_hash", out var hw) ? hw.GetString() ?? "" : "";
                string seedHash = root.TryGetProperty("seed_hash", out var sh) ? sh.GetString() ?? "" : "";
                string creado = root.TryGetProperty("creado", out var cr) ? cr.GetString() ?? "" : "";

                int rotaciones = 0;
                if (root.TryGetProperty("rotaciones", out var rot)) rotaciones = rot.GetInt32();
                rotaciones++;

                // Comprobar que la llave pertenece a ESTE hardware (núcleo del sistema).
                // Recalculamos el hash de hardware del PC actual con la misma lógica
                // que se usó al crear la cuenta (RegistroWindow).
                string hwHashActual = ObtenerHardwareHashActual();
                if (!string.IsNullOrEmpty(hwHash) &&
                    !hwHash.Equals(hwHashActual, StringComparison.OrdinalIgnoreCase))
                {
                    MessageBox.Show(
                        "Esta llave de acceso fue generada en un hardware diferente.\n\n" +
                        "Solo es válida en el PC donde se creó la cuenta.\n" +
                        "Si cambiaste de equipo, contacta con soporte.",
                        "Llave no válida en este equipo",
                        MessageBoxButton.OK,
                        MessageBoxImage.Error);
                    return;
                }

                // Rotar el hash único al entrar al visor
                string newHash = ComputeSha256($"{oldHash}|{Guid.NewGuid()}|{DateTime.UtcNow.Ticks}");

                var updatedKey = new
                {
                    tipo = "WoldVirtual_MasterKey_DeFi_v1",
                    uuid = uuid,
                    usuario = user,
                    hash_llave = newHash,
                    hash_anterior = oldHash,
                    hardware_hash = hwHash,
                    seed_hash = seedHash,
                    creado = creado,
                    ultima_sesion = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                    rotaciones = rotaciones
                };

                string updatedJson = JsonSerializer.Serialize(updatedKey, new JsonSerializerOptions
                {
                    WriteIndented = true,
                    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                });

                // Actualizar SOLO el archivo seleccionado por el usuario.
                // No se escribe copia local: la llave válida es únicamente la que
                // el usuario custodia en la carpeta que él eligió.
                File.WriteAllText(dialog.FileName, updatedJson, Encoding.UTF8);

                // Notificar cambio de hash exitoso
                string previewOld = oldHash.Length >= 16 ? oldHash[..16] : oldHash;
                string previewNew = newHash.Length >= 16 ? newHash[..16] : newHash;

                MessageBox.Show(
                    $"✔ ¡Sesión Iniciada con éxito en el Metaverso!\n\n" +
                    $"Usuario: {user}\n" +
                    $"Llave: {Path.GetFileName(dialog.FileName)}\n" +
                    $"Hash anterior: {previewOld}...\n" +
                    $"Nuevo Hash único generado: {previewNew}...\n\n" +
                    $"El hash de tu archivo de llave ha sido actualizado.",
                    "Acceso Concedido — Wold Virtual P2P",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);

                // Entrar al mundo 3D / HUD autenticado
                BarraInferiorLogin.Visibility = Visibility.Collapsed;
                PanelBienvenida.Visibility = Visibility.Collapsed;
                PanelMundo3D.Visibility = Visibility.Visible;

                TxtSesionUsuario.Text = $"Usuario: {user}";
                _llaveHashActual = newHash;
                _rotacionesLlave = rotaciones;
                AjustarBarraResponsive();

                IniciarGodotMain();
                _ = EstablecerTunelEfimeroAsync();
                IniciarP2P(user);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al validar o rotar la llave:\n{ex.Message}",
                                "Error de Llave", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void IniciarGodotMain()
        {
            if (_godotHostMain != null) return;
            // Pequeño retraso para asegurar que el panel ya tiene tamaño real
            Dispatcher.InvokeAsync(() =>
            {
                try
                {
                    string godotExe   = GodotConfig.GetGodotExePath();
                    string projectDir = GodotConfig.GetProjectPath();
                    string scenePath  = GodotConfig.GetScenePath();
                    string mainPack   = GodotConfig.GetMainPackPath();

                    // Guardar p2p_session.json para que Godot siempre lo tenga accesible
                    GuardarP2PSessionConfig();

                    string userArgs = "";
                    string rolLog = "";
                    if (!string.IsNullOrWhiteSpace(_urlAmigoPendiente))
                    {
                        if (TryParseConnectionTarget(_urlAmigoPendiente, out string targetHost, out int targetPort))
                        {
                            // Inyectar rol explícito de cliente hacia el destino remoto
                            userArgs = $"--client --ip={targetHost} --port={targetPort} --peer-url=\"{_urlAmigoPendiente}\"";
                            rolLog = $"[Visor3D -> Godot] Rol: CLIENTE_REMOTO -> {targetHost}:{targetPort} (peer-url={_urlAmigoPendiente})";
                            Console.WriteLine($"[Visor3D -> Godot] Parámetros inyectados: {userArgs}");
                            System.Diagnostics.Debug.WriteLine($"[Visor3D -> Godot] Parámetros inyectados: {userArgs}");

                            if (!EsIpLiteral(targetHost))
                            {
                                // Ya no hay ENet: el motor usa WebSocket sobre el túnel (TCP 8911),
                                // así que un nombre de host es un destino válido.
                                Console.WriteLine($"[Visor3D -> Godot] Destino por túnel/URL: {targetHost}:{targetPort} (WebSocket TCP 8911).");
                                System.Diagnostics.Debug.WriteLine($"[Visor3D -> Godot] Destino por túnel/URL: {targetHost}:{targetPort} (WebSocket TCP 8911).");
                            }
                        }
                        else
                        {
                            userArgs = $"--peer-url=\"{_urlAmigoPendiente}\"";
                            rolLog = $"[Visor3D -> Godot] Rol: CLIENTE_REMOTO (URL sin parsear: {_urlAmigoPendiente})";
                            Console.WriteLine($"[Visor3D -> Godot] Parámetros inyectados (URL sin parsear): {userArgs}");
                            System.Diagnostics.Debug.WriteLine($"[Visor3D -> Godot] Parámetros inyectados (URL sin parsear): {userArgs}");
                        }
                    }
                    else
                    {
                        rolLog = "[Visor3D -> Godot] Rol: SERVIDOR_LOCAL / modo local por defecto (sin destino remoto).";
                        Console.WriteLine("[Visor3D -> Godot] Sin destino remoto previo. Modo autónomo/local por defecto.");
                        System.Diagnostics.Debug.WriteLine("[Visor3D -> Godot] Sin destino remoto previo. Modo autónomo/local por defecto.");

                        // Somos el anfitrión: mostrar la IP LAN + WebSocket 8911 como alternativa local.
                        MostrarDireccionAnfitrion();
                    }
                    Console.WriteLine(rolLog);
                    System.Diagnostics.Debug.WriteLine(rolLog);

                    _godotHostMain = new GodotHwndHost(godotExe, projectDir, scenePath, userArgs, mainPack);
                    _godotHostMain.GodotExited += OnGodotExited;
                    ContenedorGodotMain.Children.Clear();
                    ContenedorGodotMain.Children.Add(_godotHostMain);
                    BtnReiniciar3D.Visibility = Visibility.Collapsed;
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"No se pudo incrustar la escena 3D:\n{ex.Message}",
                                    "Aviso", MessageBoxButton.OK, MessageBoxImage.Warning);
                }
            }, System.Windows.Threading.DispatcherPriority.Loaded);
        }

        /// <summary>El proceso de Godot terminó por su cuenta: avisar y ofrecer reinicio.</summary>
        private void OnGodotExited(object? sender, EventArgs e)
        {
            Dispatcher.Invoke(() =>
            {
                BtnReiniciar3D.Visibility = Visibility.Visible;
                TxtEstadoP2P.Text = "⚠️ Motor 3D detenido";
                BordeEstadoP2P.Background = new SolidColorBrush(Color.FromRgb(120, 53, 15));
                Log("[Godot] El proceso del motor 3D terminó.");
            });
        }

        /// <summary>Reincrusta Godot sin cerrar el visor (tras un cierre inesperado).</summary>
        private void ReiniciarMotor3D()
        {
            try { _godotHostMain?.StopGodot(); } catch { }
            ContenedorGodotMain.Children.Clear();
            _godotHostMain = null;
            BtnReiniciar3D.Visibility = Visibility.Collapsed;
            TxtEstadoP2P.Text = "🔄 Reiniciando motor 3D…";
            IniciarGodotMain();
        }

        /// <summary>Copia al portapapeles versión, estado, rutas y las últimas líneas del log.</summary>
        private async void OnDiagnosticoClicked(object sender, RoutedEventArgs e)
        {
            try
            {
                var sb = new StringBuilder();
                sb.AppendLine($"Wold Virtual P2P 3D v{CurrentVersion}");
                sb.AppendLine($"Windows: {Environment.OSVersion}");
                sb.AppendLine($"Runtime: {AppExtractor.RuntimeDir}");
                sb.AppendLine($"PCK: {File.Exists(AppExtractor.PckPath)} ({TamanoMb(AppExtractor.PckPath)} MB)");
                sb.AppendLine($"Godot: {File.Exists(AppExtractor.GodotExePath)}");
                sb.AppendLine($"Estado: {TxtEstadoP2P.Text}");
                sb.AppendLine($"Logs: {VisorLog.Carpeta}");
                sb.AppendLine("---- log (últimas 40 líneas) ----");
                sb.AppendLine(VisorLog.Cola(40));

                if (!CopiarAlPortapapeles(sb.ToString())) return;

                string previo = TxtEstadoP2P.Text;
                TxtEstadoP2P.Text = "🩺 Diagnóstico copiado";
                await Task.Delay(3000);
                if (TxtEstadoP2P.Text.StartsWith("🩺")) TxtEstadoP2P.Text = previo;
            }
            catch (Exception ex)
            {
                VisorLog.Error("No se pudo copiar el diagnóstico", ex);
            }
        }

        private static string TamanoMb(string path)
        {
            try
            {
                return File.Exists(path)
                    ? (new FileInfo(path).Length / 1048576.0).ToString("0.0")
                    : "0";
            }
            catch { return "?"; }
        }

        /// <summary>
        /// Godot escribe user://session_host.txt cuando migra el anfitrión.
        /// Se relee para actualizar el enlace de invitación sin reiniciar.
        /// </summary>
        private void ComprobarHostMigrado()
        {
            try
            {
                string path = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "Godot", "app_userdata", "WoldVirtualP2P3D", "session_host.txt");
                if (!File.Exists(path)) return;

                // session_host.txt sólo lo escribe el anfitrión LOCAL, y su túnel
                // efímero muere al cerrar el proceso. Un archivo anterior a este
                // arranque es de una sesión pasada: no debe convertirnos en
                // clientes de un destino que ya no existe.
                if (File.GetLastWriteTimeUtc(path) < _arranqueUtc) return;

                string nuevo = File.ReadAllText(path).Trim();
                if (string.IsNullOrWhiteSpace(nuevo)) return;
                if (nuevo.Equals(_hostSesionUrl, StringComparison.OrdinalIgnoreCase)) return;
                // Si el archivo apunta a nuestro propio portal, somos el anfitrión.
                if (!string.IsNullOrEmpty(_urlPublica) &&
                    nuevo.Equals(_urlPublica, StringComparison.OrdinalIgnoreCase)) return;

                _hostSesionUrl = nuevo;
                // Sólo se actualiza el enlace de invitación. _urlAmigoPendiente no se
                // toca: eso decide el rol con el que arranca Godot y un anfitrión no
                // debe arrancar como cliente de su propio túnel.
                if (!string.IsNullOrEmpty(_urlPublica))
                {
                    _enlaceCompartible = _urlPublica.Equals(nuevo, StringComparison.OrdinalIgnoreCase)
                        ? _urlPublica
                        : $"{_urlPublica}?host={Uri.EscapeDataString(nuevo)}";
                }
                AjustarBarraResponsive();
                TxtUrlP2P.ToolTip = $"Anfitrión actual de la sesión:\n{nuevo}\n\nTu portal: {_urlPublica}";
                Log($"[Migracion] Nuevo anfitrión de sesión: {nuevo}");
            }
            catch { }
        }

        /// <summary>
        /// Normaliza un enlace de invitación: devuelve la URL base y, si trae
        /// <c>?host=</c>, el anfitrión raíz al que deben conectarse todos.
        /// </summary>
        public static string NormalizarUrlSesion(string url, out string? hostRaiz)
        {
            hostRaiz = null;
            string limpia = (url ?? "").Trim().Trim('"', '\'');

            if (!Uri.TryCreate(limpia, UriKind.Absolute, out Uri? uri))
                return limpia;

            string query = uri.Query.TrimStart('?');
            foreach (string parte in query.Split('&', StringSplitOptions.RemoveEmptyEntries))
            {
                int igual = parte.IndexOf('=');
                if (igual <= 0) continue;

                string clave = Uri.UnescapeDataString(parte[..igual]);
                if (!clave.Equals("host", StringComparison.OrdinalIgnoreCase)) continue;

                string valor = Uri.UnescapeDataString(parte[(igual + 1)..]);
                if (Uri.TryCreate(valor, UriKind.Absolute, out _))
                    hostRaiz = valor.TrimEnd('/');
            }

            return uri.GetLeftPart(UriPartial.Path).TrimEnd('/');
        }

        public static bool TryParseConnectionTarget(string input, out string host, out int port)
        {
            host = "";
            port = 8911; // WebSocket del motor Godot (TCP)
            if (string.IsNullOrWhiteSpace(input)) return false;

            string s = input.Trim().Trim('"', '\'');
            if (s.StartsWith("http://", StringComparison.OrdinalIgnoreCase)) s = s.Substring(7);
            else if (s.StartsWith("https://", StringComparison.OrdinalIgnoreCase)) s = s.Substring(8);
            else if (s.StartsWith("woldvirtual://", StringComparison.OrdinalIgnoreCase)) s = s.Substring(14);

            int slashIdx = s.IndexOf('/');
            if (slashIdx >= 0) s = s.Substring(0, slashIdx);

            int colonIdx = s.LastIndexOf(':');
            if (colonIdx >= 0 && colonIdx < s.Length - 1)
            {
                string portPart = s.Substring(colonIdx + 1);
                if (int.TryParse(portPart, out int parsedPort))
                {
                    // Si el puerto recibido es el del WebNodo HTTP (3030-3040) o de la API P2P (7890),
                    // el tráfico del motor Godot viaja por WebSocket (TCP 8911) del anfitrión.
                    if ((parsedPort >= 3030 && parsedPort <= 3040) || parsedPort == 7890 || parsedPort == 80 || parsedPort == 443)
                    {
                        port = 8911;
                    }
                    else
                    {
                        port = parsedPort;
                    }
                }
                s = s.Substring(0, colonIdx);
            }

            host = s.Trim();
            return !string.IsNullOrEmpty(host);
        }

        /// <summary>
        /// True si el texto es una dirección IPv4 literal (p. ej. 192.168.1.10).
        /// Permite distinguir una IP directa de un nombre de host de túnel HTTP.
        /// </summary>
        public static bool EsIpLiteral(string texto)
        {
            if (string.IsNullOrWhiteSpace(texto)) return false;
            string[] partes = texto.Trim().Split('.');
            if (partes.Length != 4) return false;
            foreach (string p in partes)
            {
                if (!byte.TryParse(p, out _)) return false;
            }
            return true;
        }

        /// <summary>
        /// Al entrar como anfitrión, el banner queda a la espera del endpoint público del
        /// túnel efímero (SSH/Cloudflare), que se genera de forma asíncrona tras el login.
        /// La IP LAN privada (192.168.x.x) NO se muestra como enlace principal porque no es
        /// accesible desde fuera de la red local: queda solo como alternativa en el tooltip.
        /// </summary>
        private void MostrarDireccionAnfitrion()
        {
            var ips = IpsLanCompartibles();
            _ipsLanFallback = string.Join(", ", ips.Select(ip => ip + ":8911"));

            TxtUrlP2P.Text = "⏳ Generando enlace público…";
            TxtUrlP2P.ToolTip = string.IsNullOrEmpty(_ipsLanFallback)
                ? "El enlace público efímero se está generando…"
                : $"Enlace público en preparación…\n(Alternativa en la misma red local: {_ipsLanFallback})";
            BtnCopiarUrlP2P.Content = "📋 Copiar enlace";
            BannerP2P.Visibility = Visibility.Visible;

            Console.WriteLine(string.IsNullOrEmpty(_ipsLanFallback)
                ? "[Visor3D] ANFITRIÓN: generando túnel público (sin IPs LAN alternativas)."
                : $"[Visor3D] ANFITRIÓN: túnel público en preparación. Fallback LAN: {_ipsLanFallback}");
        }

        /// <summary>
        /// Refleja en el banner el endpoint público/efímero del túnel activo (en lugar de la
        /// IP privada LAN). El botón «Copiar enlace» pasa a copiar la URL completa del túnel.
        /// </summary>
        private void MostrarEnlacePublico(string url)
        {
            if (string.IsNullOrWhiteSpace(url)) return;

            _urlPublica = url;
            if (string.IsNullOrEmpty(_hostSesionUrl)) _hostSesionUrl = url;   // soy el anfitrión raíz

            // El enlace que se comparte lleva el anfitrión raíz para que el siguiente
            // invitado se conecte a la MISMA sesión, aunque comparta su propio portal.
            _enlaceCompartible = _hostSesionUrl.Equals(url, StringComparison.OrdinalIgnoreCase)
                ? url
                : $"{url}?host={Uri.EscapeDataString(_hostSesionUrl)}";

            AjustarBarraResponsive();
            TxtUrlP2P.ToolTip =
                $"Enlace de la sesión:\n{_enlaceCompartible}\n\n" +
                $"Tu portal: {url}\nAnfitrión raíz: {_hostSesionUrl}";
            BtnCopiarUrlP2P.Content = "📋 Copiar enlace";
            BannerP2P.Visibility = Visibility.Visible;
        }

        /// <summary>
        /// La barra debe caber en la ventana por defecto (1120 px). En anchos ajustados
        /// la llave se acorta y el enlace pasa a modo compacto; la URL completa sigue en
        /// el tooltip y se copia igual (se guarda en <see cref="_urlPublica"/>).
        /// </summary>
        private void AjustarBarraResponsive()
        {
            bool amplio = ActualWidth >= 1360;

            TxtEtiquetaEnlace.Visibility = amplio ? Visibility.Visible : Visibility.Collapsed;
            string enlace = !string.IsNullOrEmpty(_enlaceCompartible) ? _enlaceCompartible : _urlPublica;
            if (!string.IsNullOrEmpty(enlace))
                TxtUrlP2P.Text = amplio ? enlace : "enlace listo";

            if (!string.IsNullOrEmpty(_llaveHashActual))
            {
                string corto = _llaveHashActual.Length >= 8 ? _llaveHashActual[..8] : _llaveHashActual;
                TxtSesionLlave.Text = amplio
                    ? $"Llave: {corto}… (#{_rotacionesLlave})"
                    : $"🔑 {corto}…";
                TxtSesionLlave.ToolTip = $"Hash actual: {_llaveHashActual}\nRotación #{_rotacionesLlave}";
            }
        }

        /// <summary>IPv4 de la máquina excluyendo loopback (127.) y APIPA (169.254.).</summary>
        private static System.Collections.Generic.List<string> IpsLanCompartibles()
        {
            var resultado = new System.Collections.Generic.List<string>();
            try
            {
                foreach (var ni in NetworkInterface.GetAllNetworkInterfaces())
                {
                    if (ni.OperationalStatus != OperationalStatus.Up) continue;
                    if (ni.NetworkInterfaceType == NetworkInterfaceType.Loopback) continue;
                    foreach (var ua in ni.GetIPProperties().UnicastAddresses)
                    {
                        if (ua.Address.AddressFamily != AddressFamily.InterNetwork) continue;
                        string ip = ua.Address.ToString();
                        if (ip.StartsWith("127.") || ip.StartsWith("169.254.")) continue;
                        if (!resultado.Contains(ip)) resultado.Add(ip);
                    }
                }
            }
            catch { }
            return resultado;
        }

        private void GuardarP2PSessionConfig()
        {
            try
            {
                bool hasTarget = TryParseConnectionTarget(_urlAmigoPendiente, out string targetHost, out int targetPort);
                bool esClienteRemoto = hasTarget && targetHost != "127.0.0.1" && targetHost != "localhost" && !string.IsNullOrEmpty(targetHost);
                var sessionData = new
                {
                    peerUrl = _urlAmigoPendiente ?? "",
                    remoteIp = hasTarget ? targetHost : "",
                    remotePort = hasTarget ? targetPort : 8911,
                    esCliente = esClienteRemoto,
                    rolEfectivo = esClienteRemoto ? "cliente_remoto" : "servidor_local",
                    hostResuelto = esClienteRemoto ? targetHost : "127.0.0.1",
                    myTunnelUrl = App.WebNodo.PublicTunnelUrl ?? "",
                    puertoLocal = 7890,
                    puertoGodot = 8911,
                    esPrimerUsuario = !hasTarget,
                    timestamp = DateTime.UtcNow.ToString("o")
                };

                string json = JsonSerializer.Serialize(sessionData, new JsonSerializerOptions { WriteIndented = true });
                string dir = Path.Combine(TestUserDataDir, "user");
                if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
                File.WriteAllText(Path.Combine(dir, "p2p_session.json"), json, Encoding.UTF8);

                // También en la carpeta del proyecto Godot user:// si aplica
                string godotUserDir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "Godot", "app_userdata", "WoldVirtualP2P3D");
                if (!Directory.Exists(godotUserDir)) Directory.CreateDirectory(godotUserDir);
                File.WriteAllText(Path.Combine(godotUserDir, "p2p_session.json"), json, Encoding.UTF8);

                // También en la raíz del proyecto para redundancia
                try
                {
                    string pDir = GodotConfig.GetProjectPath();
                    if (Directory.Exists(pDir))
                    {
                        File.WriteAllText(Path.Combine(pDir, "p2p_session.json"), json, Encoding.UTF8);
                    }
                }
                catch { }

                Console.WriteLine($"[Visor3D] p2p_session.json generado: target={targetHost}:{targetPort}, esCliente={sessionData.esCliente}");
                System.Diagnostics.Debug.WriteLine($"[Visor3D] p2p_session.json generado: target={targetHost}:{targetPort}, esCliente={sessionData.esCliente}");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[Visor3D] Error guardando p2p_session.json: {ex.Message}");
            }
        }

        private async void IniciarP2P(string user)
        {
            try
            {
                _p2pServicio = new RedP2PServicio(user);

                _p2pServicio.UrlTunnelLista += url =>
                {
                    // Este es el túnel de la API P2P local (puerto 7890). El enlace público que
                    // se comparte con los amigos es el del túnel WebNodo (ver EstablecerTunelEfimeroAsync),
                    // que es el que transporta el tráfico del metaverso por WebSocket.
                    Dispatcher.Invoke(() =>
                    {
                        GuardarP2PSessionConfig();
                        TxtEstadoP2P.Text = "🟢 Red P2P Online";
                        BordeEstadoP2P.Background = new System.Windows.Media.SolidColorBrush(
                            System.Windows.Media.Color.FromRgb(6, 78, 59));
                    });
                };

                // Reconexión automática del túnel: informar en la barra de estado.
                _p2pServicio.TunelCaido += host =>
                {
                    Dispatcher.Invoke(() =>
                    {
                        TxtEstadoP2P.Text = $"🔄 Túnel SSH ({host}) caído, reconectando…";
                        BordeEstadoP2P.Background = new System.Windows.Media.SolidColorBrush(
                            System.Windows.Media.Color.FromRgb(120, 53, 15));
                    });
                };

                _p2pServicio.TunelReintentando += (intento, espera) =>
                {
                    Dispatcher.Invoke(() =>
                    {
                        TxtEstadoP2P.Text = $"🔄 Reconectando túnel… (intento {intento}, en {espera}s)";
                    });
                };

                _p2pServicio.NuevoPar += peer =>
                {
                    Dispatcher.Invoke(() =>
                    {
                        TxtEstadoP2P.Text = $"🟢 Amigo Conectado: {peer}";
                    });
                };

                await _p2pServicio.IniciarAsync();

                // Levantar túnel público efímero para WebNodo (cloudflared / SSH)
                _ = EstablecerTunelEfimeroAsync();

                // Si había URL de amigo ingresada en el login, conectarse automáticamente
                if (!string.IsNullOrWhiteSpace(_urlAmigoPendiente))
                {
                    bool ok = await _p2pServicio.ConectarConParAsync(_urlAmigoPendiente);
                    Dispatcher.Invoke(() =>
                    {
                        if (ok)
                        {
                            TxtEstadoP2P.Text = $"🟢 Enlazado con amigo";
                        }
                    });
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[P2P] Error al iniciar: {ex.Message}");
            }
        }

        private void OnCopiarUrlP2PClicked(object sender, RoutedEventArgs e)
        {
            string enlace = !string.IsNullOrWhiteSpace(_enlaceCompartible)
                ? _enlaceCompartible
                : (!string.IsNullOrWhiteSpace(_urlPublica) ? _urlPublica : TxtUrlP2P.Text.Trim());
            if (string.IsNullOrWhiteSpace(enlace)) return;

            // Evitar copiar el texto de estado mientras el túnel aún no está listo.
            if (!enlace.StartsWith("http", StringComparison.OrdinalIgnoreCase))
            {
                MessageBox.Show(
                    "El enlace público aún se está generando. Espera unos segundos e inténtalo de nuevo.",
                    "Enlace en preparación",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
                return;
            }

            if (!CopiarAlPortapapeles(enlace))
            {
                MessageBox.Show(
                    $"El portapapeles está ocupado por otra aplicación. Copia el enlace manualmente:\n\n{enlace}",
                    "Portapapeles ocupado",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
                return;
            }

            MessageBox.Show(
                $"¡Enlace público copiado al portapapeles!\n\n{enlace}\n\n" +
                "Compártelo con tu amigo (por WhatsApp u otro medio) para que pueda unirse a tu mundo desde cualquier red.",
                "Enlace P2P Copiado",
                MessageBoxButton.OK,
                MessageBoxImage.Information);
        }

        /// <summary>
        /// Copia texto al portapapeles con reintentos. En Windows el portapapeles puede estar
        /// bloqueado momentáneamente por otra aplicación (COMException / ExternalException),
        /// por lo que un único intento puede fallar de forma espuria.
        /// </summary>
        private static bool CopiarAlPortapapeles(string texto)
        {
            for (int intento = 0; intento < 5; intento++)
            {
                try
                {
                    Clipboard.SetText(texto);
                    return true;
                }
                catch
                {
                    Thread.Sleep(60);
                }
            }
            return false;
        }

        private async void OnConectarAmigoClicked(object sender, RoutedEventArgs e)
        {
            string url = TxtUrlAmigo.Text.Trim();
            if (string.IsNullOrWhiteSpace(url))
            {
                MessageBox.Show("Por favor ingresa o pega el enlace P2P de tu amigo primero.",
                                "Aviso", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            _urlAmigoPendiente = NormalizarUrlSesion(url, out string? raiz);
            _hostSesionUrl = raiz ?? _urlAmigoPendiente;
            BtnConectarAmigo.Content = "⏳ Probando...";
            BtnConectarAmigo.IsEnabled = false;

            bool responde = await P2PNodo.PingParAsync(url);
            BtnConectarAmigo.Content = "🔗 Conectar";
            BtnConectarAmigo.IsEnabled = true;

            if (responde)
            {
                MessageBox.Show("✔ ¡Conexión con el amigo detectada con éxito!\nAhora introduce tu usuario y contraseña y haz clic en 'Iniciar Sesión'.",
                                "Amigo Disponible", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            else
            {
                MessageBox.Show("No se pudo contactar al amigo en ese enlace.\nAsegúrate de que su visor esté abierto y tenga la sesión activa.",
                                "Aviso P2P", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        private bool ValidarCredenciales(string user, string pass)
        {
            return ValidarFicheroCredenciales(UserProfilePath, "nombre", user, pass)
                || ValidarFicheroCredenciales(CredentialsPath, "username", user, pass);
        }

        /// <summary>
        /// Lee el UUID del usuario desde su perfil local (user_profile.json o credentials.json).
        /// Devuelve cadena vacía si no se puede obtener (no bloquea el flujo).
        /// </summary>
        private string ObtenerUuidDelPerfil(string user)
        {
            foreach (var (path, campoUsuario) in new[] {
                (UserProfilePath, "nombre"),
                (CredentialsPath, "username") })
            {
                if (!File.Exists(path)) continue;
                try
                {
                    using var doc = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
                    var root = doc.RootElement;
                    string guardado = root.TryGetProperty(campoUsuario, out var u) ? u.GetString() ?? "" : "";
                    if (!guardado.Equals(user, StringComparison.OrdinalIgnoreCase)) continue;
                    // uuid puede estar como "uuid", "id", "userId"
                    foreach (string campo in new[] { "uuid", "id", "userId" })
                        if (root.TryGetProperty(campo, out var v) && !string.IsNullOrEmpty(v.GetString()))
                            return v.GetString()!;
                }
                catch { }
            }
            return string.Empty;
        }

        /// <summary>
        /// Verifica la contraseña contra un fichero de credenciales. Acepta PBKDF2
        /// (nuevo) y SHA-256 (legado); si es legado, migra el hash al vuelo.
        /// </summary>
        private bool ValidarFicheroCredenciales(string path, string campoUsuario, string user, string pass)
        {
            if (!File.Exists(path)) return false;

            try
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
                var root = doc.RootElement;

                string guardado = root.TryGetProperty(campoUsuario, out var u) ? u.GetString() ?? "" : "";
                string hash = root.TryGetProperty("passwordHash", out var h) ? h.GetString() ?? "" : "";

                if (!guardado.Equals(user, StringComparison.OrdinalIgnoreCase)) return false;
                if (!PasswordHasher.Verify(pass, hash, out bool migrar)) return false;

                if (migrar) MigrarHashPassword(path, pass);
                return true;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>Re-hashea una cuenta antigua (SHA-256 sin sal) a PBKDF2 sin pedir nada.</summary>
        private void MigrarHashPassword(string path, string pass)
        {
            try
            {
                var nodo = JsonNode.Parse(File.ReadAllText(path, Encoding.UTF8));
                if (nodo is not JsonObject obj) return;

                obj["passwordHash"] = PasswordHasher.Hash(pass);
                obj["hashVersion"] = 2;

                File.WriteAllText(path, obj.ToJsonString(new JsonSerializerOptions
                {
                    WriteIndented = true,
                    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                }), Encoding.UTF8);

                Log($"[Seguridad] Hash de contraseña migrado a PBKDF2 en {Path.GetFileName(path)}");
            }
            catch (Exception ex)
            {
                Log($"[Seguridad] No se pudo migrar el hash: {ex.Message}");
            }
        }

        private static string ComputeSha256(string input)
        {
            using var sha = SHA256.Create();
            byte[] bytes = sha.ComputeHash(Encoding.UTF8.GetBytes(input));
            var sb = new StringBuilder();
            foreach (byte b in bytes) sb.Append(b.ToString("x2"));
            return sb.ToString();
        }

        /// <summary>
        /// Calcula el hash de hardware del PC actual usando las mismas fuentes WMI
        /// que se usaron al crear la cuenta en <c>RegistroWindow</c>.
        /// Se usa para verificar que la llave de acceso pertenece a este equipo.
        /// Devuelve una cadena vacía si WMI no está disponible (no bloquea el acceso).
        /// </summary>
        private static string ObtenerHardwareHashActual()
        {
            try
            {
                string os          = ObtenerWmiValor("Win32_OperatingSystem", "Caption") + " " +
                                     ObtenerWmiValor("Win32_OperatingSystem", "Version");
                string motherboard = ObtenerWmiValor("Win32_BaseBoard", "Manufacturer") + " " +
                                     ObtenerWmiValor("Win32_BaseBoard", "Product");
                string cpu         = ObtenerWmiValor("Win32_Processor", "Name");

                string rawId = $"{os}|{motherboard}|{cpu}";
                using var sha = SHA256.Create();
                byte[] hashBytes = sha.ComputeHash(Encoding.UTF8.GetBytes(rawId));
                return BitConverter.ToString(hashBytes).Replace("-", "").ToLowerInvariant();
            }
            catch
            {
                // WMI no disponible: devolver vacío → la comprobación de hardware se omite.
                return string.Empty;
            }
        }

        private static string ObtenerWmiValor(string clase, string propiedad)
        {
            try
            {
                using var searcher = new ManagementObjectSearcher($"SELECT {propiedad} FROM {clase}");
                foreach (ManagementObject obj in searcher.Get())
                {
                    string val = obj[propiedad]?.ToString() ?? "";
                    if (!string.IsNullOrWhiteSpace(val)) return val.Trim();
                }
            }
            catch { }
            return "Desconocido";
        }

        private void OnWebNodoClicked(object sender, RoutedEventArgs e)
        {
            try
            {
                // Arrancar el servidor WebNodo embebido si no está corriendo
                if (!App.WebNodo.IsRunning)
                {
                    App.WebNodo.Start();
                }

                // Si el servidor no pudo iniciar, avisar al usuario
                if (!App.WebNodo.IsRunning)
                {
                    string err = App.WebNodo.StartError ?? "Error desconocido al enlazar el servidor local.";
                    MessageBox.Show($"WebNodo no pudo iniciarse en el puerto local ({App.WebNodo.ActivePort}):\n{err}",
                                    "WebNodo", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }

                // Si ya hay túnel público efímero listo (ej. https://xxx.trycloudflare.com/)
                if (!string.IsNullOrWhiteSpace(App.WebNodo.PublicTunnelUrl))
                {
                    string publicUrl = App.WebNodo.PublicTunnelUrl;
                    try { Clipboard.SetText(publicUrl); } catch { }

                    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(publicUrl)
                    {
                        UseShellExecute = true
                    });

                    MessageBox.Show(
                        $"🌍 ¡Portal WebNodo Efímero de Sesión en línea!\n\n" +
                        $"URL Pública:\n{publicUrl}\n\n" +
                        $"✅ Enlace copiado al portapapeles.\n" +
                        $"Compártelo con cualquier amigo para que descargue el visor y se una a tu sesión en el metaverso 3D.",
                        "WebNodo Público Efímero",
                        MessageBoxButton.OK,
                        MessageBoxImage.Information);
                    return;
                }

                // Si aún no ha terminado de conectar el túnel público, abrir local y avisar
                string localUrl = $"http://localhost:{App.WebNodo.ActivePort}/";
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(localUrl)
                {
                    UseShellExecute = true
                });

                // Asegurar que el túnel efímero se esté generando
                _ = EstablecerTunelEfimeroAsync();

                MessageBox.Show(
                    $"🌐 Portal WebNodo abierto localmente en:\n{localUrl}\n\n" +
                    $"⏳ El túnel público efímero Cloudflare se está conectando en segundo plano...\n" +
                    $"En unos segundos el botón cambiará a '🌐 WebNodo (Online)' y la URL pública quedará lista y copiada al portapapeles.",
                    "WebNodo — Conectando túnel efímero",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"No se pudo abrir el portal WebNodo:\n{ex.Message}",
                                "WebNodo", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        // ═══════════════════════════════════════════════════════════
        // TÚNEL PÚBLICO EFÍMERO para WebNodo (cloudflared → SSH reverso)
        // ═══════════════════════════════════════════════════════════
        private async Task EstablecerTunelEfimeroAsync()
        {
            // Idempotente: si ya hay un túnel activo con URL, no volver a levantarlo
            if (_tunnelProcess != null && !_tunnelProcess.HasExited && !string.IsNullOrWhiteSpace(App.WebNodo.PublicTunnelUrl))
            {
                return;
            }

            try
            {
                // Barrido defensivo: si una ejecución anterior murió sin limpiar (p. ej. el
                // usuario "finalizó la tarea" desde el Administrador de tareas), aquí matamos
                // el cloudflared/ssh huérfano antes de crear uno nuevo.
                TunnelProcessRegistry.BarrerHuerfano(TunelWebNodoSlot);

                // Asegurar que WebNodo está activo antes de levantar el túnel
                if (!App.WebNodo.IsRunning)
                {
                    App.WebNodo.Start();
                }

                int webPort = App.WebNodo.ActivePort;

                // Opción 1: cloudflared (HTTPS sin advertencia de seguridad, ej. trycloudflare.com)
                string? cfExe = await BuscarODescargarCloudflaredAsync(CancellationToken.None);
                if (cfExe != null)
                {
                    System.Diagnostics.Debug.WriteLine($"[Tunel] Probando cloudflared en puerto {webPort}...");
                    var res = await TryRunProcessTunnelAsync(
                        cfExe,
                        $"tunnel --url http://127.0.0.1:{webPort} --http-host-header 127.0.0.1:{webPort} --no-autoupdate",
                        @"https://[\w\-]+\.trycloudflare\.com",
                        35000,
                        CancellationToken.None);
                    if (res != null && !string.IsNullOrEmpty(res.Url))
                    {
                        _tunnelProcess = res.Process;
                        TunnelProcessRegistry.Persistir(TunelWebNodoSlot, res.Process.Id);
                        string pubUrl = res.Url;
                        Dispatcher.Invoke(() =>
                        {
                            TxtEstadoP2P.Text = "🌍 Túnel público activo";
                            App.WebNodo.PublicTunnelUrl = pubUrl;
                            GuardarP2PSessionConfig(); // Refrescar config con la URL del túnel
                            MostrarEnlacePublico(pubUrl);
                            BtnWebNodo.Content = "🌐 WebNodo (Online)";
                            BtnWebNodo.ToolTip = $"WebNodo público activo:\n{pubUrl}\nHaz clic para abrir en el navegador y copiar.";
                            BtnWebNodo.Background = new System.Windows.Media.SolidColorBrush(
                                System.Windows.Media.Color.FromRgb(6, 78, 59));
                            BtnWebNodo.BorderBrush = new System.Windows.Media.SolidColorBrush(
                                System.Windows.Media.Color.FromRgb(34, 197, 94));
                            try { Clipboard.SetText(pubUrl); } catch { }
                        });
                        return;
                    }
                }

                // Opción 2: SSH reverso (serveo.net / localhost.run)
                string sshExe = @"C:\Windows\System32\OpenSSH\ssh.exe";
                if (!File.Exists(sshExe)) sshExe = "ssh";

                var candidates = new[]
                {
                    new { Name = "serveo.net", Args = $"-o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ConnectTimeout=15 -R 80:127.0.0.1:{webPort} serveo.net", Pat = @"https://[\w\-]+\.serveo\.net" },
                    new { Name = "localhost.run", Args = $"-o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=30 -o ConnectTimeout=15 -R 80:127.0.0.1:{webPort} nokey@localhost.run", Pat = @"https://[\w\-]+\.lhr\.life" }
                };

                foreach (var c in candidates)
                {
                    System.Diagnostics.Debug.WriteLine($"[Tunel] Probando {c.Name} en puerto {webPort}...");
                    var res = await TryRunProcessTunnelAsync(sshExe, c.Args, c.Pat, 23000, CancellationToken.None);
                    if (res != null && !string.IsNullOrEmpty(res.Url))
                    {
                        _tunnelProcess = res.Process;
                        TunnelProcessRegistry.Persistir(TunelWebNodoSlot, res.Process.Id);
                        string pubUrl = res.Url;
                        Dispatcher.Invoke(() =>
                        {
                            TxtEstadoP2P.Text = $"🌍 Túnel público ({c.Name})";
                            App.WebNodo.PublicTunnelUrl = pubUrl;
                            GuardarP2PSessionConfig(); // Refrescar config con la URL del túnel
                            MostrarEnlacePublico(pubUrl);
                            BtnWebNodo.Content = "🌐 WebNodo (Online)";
                            BtnWebNodo.ToolTip = $"WebNodo público ({c.Name}):\n{pubUrl}\nHaz clic para abrir en el navegador y copiar.";
                            BtnWebNodo.Background = new System.Windows.Media.SolidColorBrush(
                                System.Windows.Media.Color.FromRgb(6, 78, 59));
                            BtnWebNodo.BorderBrush = new System.Windows.Media.SolidColorBrush(
                                System.Windows.Media.Color.FromRgb(34, 197, 94));
                            try { Clipboard.SetText(pubUrl); } catch { }
                        });
                        return;
                    }
                }

                Dispatcher.Invoke(() =>
                {
                    TxtEstadoP2P.Text = "🟢 WebNodo local (sin túnel público)";
                });
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[Tunel] Error: {ex.Message}");
            }
        }

        /// <summary>
        /// Detiene de forma forzosa y limpia el proceso del túnel del portal (cloudflared/ssh):
        /// mata todo su árbol de procesos y olvida su PID persistido. Idempotente.
        /// </summary>
        private void DetenerTunelWebNodo()
        {
            TunnelProcessRegistry.MatarYOlvidar(TunelWebNodoSlot, _tunnelProcess);
            _tunnelProcess = null;
        }

        private async Task<Visor3D.Services.P2PIPFS.EphemeralTunnelResult?> TryRunProcessTunnelAsync(string exe, string args, string urlPattern, int timeoutMs, CancellationToken token)
        {
            return await Visor3D.Services.P2PIPFS.EphemeralTunnelRunner.StartAsync(exe, args, urlPattern, timeoutMs, token);
        }

        private async Task<string?> BuscarODescargarCloudflaredAsync(CancellationToken token)
        {
            string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string progFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
            string appBase = AppDomain.CurrentDomain.BaseDirectory;
            string localAppDataWold = Path.Combine(localApp, "WoldVirtualP2P3D");
            string tempDir = Path.GetTempPath();

            string[] candidateLocations = {
                "cloudflared",
                Path.Combine(appBase, "cloudflared.exe"),
                Path.Combine(localAppDataWold, "cloudflared.exe"),
                Path.Combine(tempDir, "cloudflared.exe"),
                Path.Combine(localApp, "Programs", "cloudflared", "cloudflared.exe"),
                Path.Combine(progFiles, "Cloudflare", "cloudflared.exe"),
                @"C:\ProgramData\chocolatey\bin\cloudflared.exe",
                Path.Combine(localApp, "Microsoft", "WinGet", "Links", "cloudflared.exe")
            };

            foreach (var loc in candidateLocations)
            {
                try
                {
                    if (loc == "cloudflared" || File.Exists(loc))
                    {
                        using var test = Process.Start(new ProcessStartInfo
                        {
                            FileName = loc,
                            Arguments = "--version",
                            UseShellExecute = false,
                            RedirectStandardOutput = true,
                            RedirectStandardError = true,
                            CreateNoWindow = true
                        });
                        if (test != null && test.WaitForExit(3000) && test.ExitCode == 0)
                            return loc;
                    }
                }
                catch { }
            }

            // Descargar cloudflared si no está instalado (a LocalAppData para asegurar permisos de escritura)
            try
            {
                Directory.CreateDirectory(localAppDataWold);
                string downloadTarget = Path.Combine(localAppDataWold, "cloudflared.exe");

                const string cfUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe";
                using var dl = new HttpClient { Timeout = TimeSpan.FromMinutes(3) };
                dl.DefaultRequestHeaders.UserAgent.ParseAdd("WoldVirtualP2P/1.0");
                using var resp = await dl.GetAsync(cfUrl, HttpCompletionOption.ResponseHeadersRead, token);
                if (resp.IsSuccessStatusCode)
                {
                    await using var fs = File.Create(downloadTarget);
                    await resp.Content.CopyToAsync(fs, token);
                    return downloadTarget;
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[Cloudflare-Download] {ex.Message}");
            }

            return null;
        }
    }
}
