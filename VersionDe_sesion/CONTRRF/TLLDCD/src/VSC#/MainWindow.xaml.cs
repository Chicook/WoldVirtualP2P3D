using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;
using Microsoft.Win32;
using Visor3D.RedP2P;

namespace Visor3D
{
    public partial class MainWindow : Window
    {
        // Carpeta local para datos de usuario y pruebas de flujo
        private static readonly string TestUserDataDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "test_user_data");

        private static readonly string CredentialsPath =
            Path.Combine(TestUserDataDir, "credentials.json");

        private static readonly string UserProfilePath =
            Path.Combine(TestUserDataDir, "user", "user_profile.json");

        private GodotHwndHost? _godotHostMain;
        private RedP2PServicio? _p2pServicio;
        private string _urlAmigoPendiente = "";

        public MainWindow()
        {
            InitializeComponent();
            this.Loaded += OnLoaded;
            this.Closing += (s, e) =>
            {
                _godotHostMain?.StopGodot();
                _p2pServicio?.Dispose();
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
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            MostrarPantallaBienvenida();
        }

        public void MostrarPantallaBienvenida()
        {
            _godotHostMain?.StopGodot();
            ContenedorGodotMain.Children.Clear();
            _godotHostMain = null;

            _p2pServicio?.Dispose();
            _p2pServicio = null;
            BannerP2P.Visibility = Visibility.Collapsed;
            TxtUrlP2P.Text = "";

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
                    if (!string.IsNullOrWhiteSpace(_urlAmigoPendiente))
                    {
                        userArgs = $"--peer-url=\"{_urlAmigoPendiente}\"";
                    }

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

        private void GuardarP2PSessionConfig()
        {
            try
            {
                var sessionData = new
                {
                    peerUrl = _urlAmigoPendiente ?? "",
                    myTunnelUrl = _p2pServicio?.UrlPublicaPropia ?? "",
                    puertoLocal = 7890,
                    puertoGodot = 8910,
                    esPrimerUsuario = string.IsNullOrWhiteSpace(_urlAmigoPendiente),
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
            }
            catch { }
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
                        TxtUrlP2P.Text = url;
                        BannerP2P.Visibility = Visibility.Visible;
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
    }
}
