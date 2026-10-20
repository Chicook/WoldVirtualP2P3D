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
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Media.Animation;
using Microsoft.Win32;
using Visor3D.RedP2P;
using Visor3D.Update;

namespace Visor3D
{
    public partial class MainWindow : Window
    {
        private const string CurrentVersion = "0.0.1"; // Versión forzada baja para asegurar que detecte la v0.0.12
        // Carpeta local para datos de usuario y pruebas de flujo
        private static readonly string TestUserDataDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "test_user_data");

        private static readonly string CredentialsPath =
            Path.Combine(TestUserDataDir, "credentials.json");

        private static readonly string UserProfilePath =
            Path.Combine(TestUserDataDir, "user", "user_profile.json");

        private GodotHwndHost? _godotHostMain;
        private RedP2PServicio? _p2pServicio;
        private Process? _tunnelProcess;
        private string _urlAmigoPendiente = "";
        private bool _esAnfitrion;
        private ReleaseInfo? _updateInfo;

        public MainWindow(string? initialConnectionUrl = null)
        {
            InitializeComponent();
            if (!string.IsNullOrWhiteSpace(initialConnectionUrl))
            {
                _urlAmigoPendiente = initialConnectionUrl.Trim();
                System.Diagnostics.Debug.WriteLine($"[MainWindow] URL de conexión inicial establecida: {_urlAmigoPendiente}");
                Console.WriteLine($"[MainWindow] URL de conexión inicial establecida: {_urlAmigoPendiente}");
            }

            this.Loaded += OnLoaded;
            this.Closing += (s, e) =>
            {
                _godotHostMain?.StopGodot();
                _p2pServicio?.Dispose();
                try { _tunnelProcess?.Kill(); } catch { }
                _tunnelProcess = null;
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
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            MostrarPantallaBienvenida();
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
            try
            {
                string logPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "update_debug.log");
                File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss}] {message}{Environment.NewLine}");
                Console.WriteLine($"[Updater] {message}");
            }
            catch { }
        }

        private async Task CheckUpdatesAsync()
        {
            Log("Iniciando CheckUpdatesAsync...");
            await Task.Delay(3000); // Dar tiempo a que cargue todo
            
            try
            {
                Log($"Versión local configurada: {CurrentVersion}");
                var checker = new UpdateChecker();
                
                Log("Consultando GitHub...");
                _updateInfo = await checker.CheckForUpdateAsync(CurrentVersion);

                if (_updateInfo != null)
                {
                    Log($"¡Actualización encontrada!: {_updateInfo.TagName}");
                    Dispatcher.Invoke(() =>
                    {
                        try 
                        {
                            Log("Iniciando animación en UI...");
                            // Forzar opacidad y visibilidad
                            BtnActualizarVisual.Opacity = 1.0;
                            BtnActualizar.Visibility = Visibility.Visible;
                            BtnActualizar.ToolTip = $"Nueva versión disponible: {_updateInfo.TagName}";
                            
                            // Animación de color de borde para que sea MUY visible
                            var colorAnim = new ColorAnimation
                            {
                                From = System.Windows.Media.Color.FromRgb(30, 41, 59), // Color original oscuro
                                To = System.Windows.Media.Color.FromRgb(56, 189, 248),   // Color azul brillante
                                Duration = TimeSpan.FromSeconds(0.8),
                                AutoReverse = true,
                                RepeatBehavior = RepeatBehavior.Forever
                            };
                            
                            var brush = new SolidColorBrush(System.Windows.Media.Color.FromRgb(30, 41, 59));
                            BtnActualizarVisual.Background = brush;
                            brush.BeginAnimation(SolidColorBrush.ColorProperty, colorAnim);

                            // También el brillo por si acaso
                            var glowAnim = new DoubleAnimation(0.3, 1.0, TimeSpan.FromSeconds(0.8))
                            {
                                AutoReverse = true,
                                RepeatBehavior = RepeatBehavior.Forever
                            };
                            GlowActualizar.BeginAnimation(DropShadowEffect.OpacityProperty, glowAnim);
                            
                            Log("Animación iniciada con éxito.");
                        }
                        catch (Exception ex)
                        {
                            Log($"Error en Dispatcher.Invoke: {ex.Message}");
                        }
                    });
                }
                else
                {
                    Log("No se encontraron actualizaciones o ya está al día.");
                }
            }
            catch (Exception ex)
            {
                Log($"Error crítico en CheckUpdatesAsync: {ex.Message}");
            }
        }

        private async void OnActualizarClicked(object sender, System.Windows.Input.MouseButtonEventArgs e)
        {
            if (_updateInfo == null) return;

            try
            {
                BtnActualizar.IsEnabled = false;
                BtnActualizar.Cursor = System.Windows.Input.Cursors.Wait;
                TxtEstadoP2P.Text = "⬇️ Descargando actualización...";

                var downloader = new UpdateDownloader();
                bool success = await downloader.DownloadAsync(_updateInfo);

                if (success)
                {
                    TxtEstadoP2P.Text = "🚀 Reiniciando para aplicar actualización...";
                    
                    // Aplicar y reiniciar
                    UpdateApplier.ApplyPendingUpdate(Process.GetCurrentProcess().MainModule?.FileName ?? "");
                    
                    // Cerrar la aplicación actual para que el .bat pueda hacer el reemplazo
                    Application.Current.Shutdown();
                }
                else
                {
                    MessageBox.Show("Error al descargar la actualización. Inténtalo de nuevo más tarde.", 
                                    "Error de Actualización", MessageBoxButton.OK, MessageBoxImage.Error);
                    BtnActualizar.IsEnabled = true;
                    PanelActualizar.Cursor = System.Windows.Input.Cursors.Hand;
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error durante la actualización: {ex.Message}", 
                                "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                BtnActualizar.IsEnabled = true;
                PanelActualizar.Cursor = System.Windows.Input.Cursors.Hand;
            }
        }

        public void MostrarPantallaBienvenida()
        {
            _godotHostMain?.StopGodot();
            ContenedorGodotMain.Children.Clear();
            _godotHostMain = null;

            _p2pServicio?.Dispose();
            _p2pServicio = null;
            try { _tunnelProcess?.Kill(); } catch { }
            _tunnelProcess = null;
            BannerP2P.Visibility = Visibility.Collapsed;
            TxtUrlP2P.Text = "";

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
                _urlAmigoPendiente = TxtUrlAmigo.Text.Trim();
                Console.WriteLine($"[MainWindow] URL de conexión tomada de TxtUrlAmigo: {_urlAmigoPendiente}");
                System.Diagnostics.Debug.WriteLine($"[MainWindow] URL de conexión tomada de TxtUrlAmigo: {_urlAmigoPendiente}");
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

                // Actualizar el archivo seleccionado por el usuario
                File.WriteAllText(dialog.FileName, updatedJson, Encoding.UTF8);

                // Actualizar también la copia local si existe la carpeta
                string localKey = Path.Combine(TestUserDataDir, "user", "llave_acceso.json");
                if (Directory.Exists(Path.GetDirectoryName(localKey)!))
                {
                    File.WriteAllText(localKey, updatedJson, Encoding.UTF8);
                }

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
                TxtSesionLlave.Text = $"Llave: {previewNew}... (Rotación #{rotaciones})";

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
                                Console.WriteLine($"[Visor3D -> Godot] AVISO: '{targetHost}' es un nombre de host (túnel HTTP), no una IP literal.");
                                Console.WriteLine("[Visor3D -> Godot]   Los túneles solo reenvían TCP/HTTP; ENet (UDP 8910) NO los atraviesa.");
                                Console.WriteLine("[Visor3D -> Godot]   Para conexión remota real usa la IP directa del anfitrión (LAN, o IP pública con UDP 8910 reenviado).");
                                System.Diagnostics.Debug.WriteLine($"[Visor3D -> Godot] AVISO: '{targetHost}' no es IP literal; ENet UDP 8910 podría no ser alcanzable.");
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

                        // Somos el anfitrión: mostrar la dirección directa (IP LAN + UDP 8910)
                        // que hay que compartir para que otro equipo se conecte por ENet.
                        MostrarDireccionAnfitrion();
                    }
                    Console.WriteLine(rolLog);
                    System.Diagnostics.Debug.WriteLine(rolLog);

                    _godotHostMain = new GodotHwndHost(godotExe, projectDir, scenePath, userArgs);
                    ContenedorGodotMain.Children.Clear();
                    ContenedorGodotMain.Children.Add(_godotHostMain);
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"No se pudo incrustar la escena 3D:\n{ex.Message}",
                                    "Aviso", MessageBoxButton.OK, MessageBoxImage.Warning);
                }
            }, System.Windows.Threading.DispatcherPriority.Loaded);
        }

        public static bool TryParseConnectionTarget(string input, out string host, out int port)
        {
            host = "";
            port = 8910;
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
                    // el tráfico del motor Godot (ENet UDP) debe ir al puerto 8910 del anfitrión.
                    if ((parsedPort >= 3030 && parsedPort <= 3040) || parsedPort == 7890 || parsedPort == 80 || parsedPort == 443)
                    {
                        port = 8910;
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
        /// Muestra en el banner la dirección directa (IP LAN + UDP 8910) que el anfitrión
        /// debe compartir para que otro equipo se conecte por ENet sin pasar por el túnel HTTP.
        /// </summary>
        private void MostrarDireccionAnfitrion()
        {
            _esAnfitrion = true;
            var ips = IpsLanCompartibles();
            if (ips.Count == 0)
            {
                Console.WriteLine("[Visor3D] ANFITRIÓN: sin IPs LAN no-loopback. Comparte tu IP pública con UDP 8910 reenviado en el router.");
                return;
            }
            string lista = string.Join(", ", ips.Select(ip => ip + ":8910"));
            Console.WriteLine($"[Visor3D] ANFITRIÓN — dirección directa para invitar (ENet UDP 8910): {lista}");
            TxtUrlP2P.Text = lista;
            TxtUrlP2P.ToolTip = $"Comparte esta dirección con el otro equipo: {lista}";
            BtnCopiarUrlP2P.Content = "📋 Copiar IP";
            BannerP2P.Visibility = Visibility.Visible;
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
                    remotePort = hasTarget ? targetPort : 8910,
                    esCliente = esClienteRemoto,
                    rolEfectivo = esClienteRemoto ? "cliente_remoto" : "servidor_local",
                    hostResuelto = esClienteRemoto ? targetHost : "127.0.0.1",
                    myTunnelUrl = _p2pServicio?.UrlPublicaPropia ?? "",
                    puertoLocal = 7890,
                    puertoGodot = 8910,
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
                    Dispatcher.Invoke(() =>
                    {
                        if (_esAnfitrion)
                        {
                            // Actualizar p2p_session.json para que Godot conozca su propia URL de túnel
                            GuardarP2PSessionConfig();
                            TxtUrlP2P.ToolTip = $"Portal WebNodo y P2P Tunnel: {url}";
                        }
                        else
                        {
                            TxtUrlP2P.Text = url;
                            BannerP2P.Visibility = Visibility.Visible;
                        }
                        TxtEstadoP2P.Text = "🟢 Red P2P Online";
                        BordeEstadoP2P.Background = new System.Windows.Media.SolidColorBrush(
                            System.Windows.Media.Color.FromRgb(6, 78, 59));
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
            if (!string.IsNullOrWhiteSpace(TxtUrlP2P.Text))
            {
                Clipboard.SetText(TxtUrlP2P.Text);
                MessageBox.Show(
                    $"¡Enlace P2P copiado al portapapeles!\n\n{TxtUrlP2P.Text}\n\n" +
                    "Compártelo con tu amigo (por WhatsApp u otro medio) para que pueda conectarse a tu mundo.",
                    "Enlace P2P Copiado",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
            }
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

            _urlAmigoPendiente = url;
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
            string enteredHash = ComputeSha256(pass);

            // 1. Intentar validar con user_profile.json
            if (File.Exists(UserProfilePath))
            {
                try
                {
                    string json = File.ReadAllText(UserProfilePath, Encoding.UTF8);
                    using var doc = JsonDocument.Parse(json);
                    var root = doc.RootElement;

                    string savedUser = root.GetProperty("nombre").GetString() ?? "";
                    string savedHash = root.GetProperty("passwordHash").GetString() ?? "";

                    if (savedUser.Equals(user, StringComparison.OrdinalIgnoreCase) && savedHash.Equals(enteredHash, StringComparison.Ordinal))
                    {
                        return true;
                    }
                }
                catch { }
            }

            // 2. Intentar validar con credentials.json
            if (File.Exists(CredentialsPath))
            {
                try
                {
                    string json = File.ReadAllText(CredentialsPath, Encoding.UTF8);
                    using var doc = JsonDocument.Parse(json);
                    var root = doc.RootElement;

                    string savedUser = root.GetProperty("username").GetString() ?? "";
                    string savedHash = root.GetProperty("passwordHash").GetString() ?? "";

                    if (savedUser.Equals(user, StringComparison.OrdinalIgnoreCase) && savedHash.Equals(enteredHash, StringComparison.Ordinal))
                    {
                        return true;
                    }
                }
                catch { }
            }

            return false;
        }

        private static string ComputeSha256(string input)
        {
            using var sha = SHA256.Create();
            byte[] bytes = sha.ComputeHash(Encoding.UTF8.GetBytes(input));
            var sb = new StringBuilder();
            foreach (byte b in bytes) sb.Append(b.ToString("x2"));
            return sb.ToString();
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
                        string pubUrl = res.Url;
                        Dispatcher.Invoke(() =>
                        {
                            TxtEstadoP2P.Text = "🌍 Túnel público activo";
                            App.WebNodo.PublicTunnelUrl = pubUrl;
                            GuardarP2PSessionConfig(); // Refrescar config con la URL del túnel
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
                        string pubUrl = res.Url;
                        Dispatcher.Invoke(() =>
                        {
                            TxtEstadoP2P.Text = $"🌍 Túnel público ({c.Name})";
                            App.WebNodo.PublicTunnelUrl = pubUrl;
                            GuardarP2PSessionConfig(); // Refrescar config con la URL del túnel
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
