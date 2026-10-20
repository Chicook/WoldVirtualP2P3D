using System;
using System.Diagnostics;
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
        // Carpeta de datos del usuario: JUNTO AL EXE, en la carpeta que el usuario controla.
        // El usuario descarga el visor, lo pone donde quiere y ahi mismo se guardan sus datos.
        // No se crea nada en AppData ni en ningun otro sitio del sistema.
        private static readonly string UserDataDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "datos_usuario");

        private static readonly string CredentialsPath =
            Path.Combine(UserDataDir, "credentials.json");

        private static readonly string UserProfilePath =
            Path.Combine(UserDataDir, "user_profile.json");

        private static readonly string LlavePath =
            Path.Combine(UserDataDir, "llave_acceso.json");

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

            BtnCrearCuenta.Click += OnCrearCuentaClicked;
            BtnAcceder.Click += OnAccederClicked;
            BtnVolverBienvenida.Click += OnVolverBienvenidaClicked;

            BtnLogin.Click += OnLoginClicked;
            BtnCerrarSesion.Click += (s, e) => MostrarPantallaBienvenida();

            BtnCopiarUrlP2P.Click += OnCopiarUrlP2PClicked;
            TxtUrlP2P.MouseLeftButtonDown += (s, e) => OnCopiarUrlP2PClicked(s, e);
            BtnWebNodo.Click += OnWebNodoClicked;
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

            // Mostrar "Crear Cuenta" solo si el usuario aun no tiene datos en esta carpeta
            bool estaRegistrado = File.Exists(UserProfilePath) && File.Exists(LlavePath);
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

        private void OnAccederClicked(object sender, RoutedEventArgs e) => ActivarModoLogin();

        private void OnVolverBienvenidaClicked(object sender, RoutedEventArgs e) => MostrarPantallaBienvenida();

        private void OnLoginClicked(object sender, RoutedEventArgs e)
        {
            string user = TxtLoginUser.Text.Trim();
            string pass = TxtLoginPass.Password;

            if (string.IsNullOrWhiteSpace(user) || string.IsNullOrWhiteSpace(pass))
            {
                MessageBox.Show("Por favor, introduce tu usuario y contrasena.",
                                "Validacion", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            if (!ValidarCredenciales(user, pass))
            {
                MessageBox.Show("Usuario o contrasena incorrectos.",
                                "Ingreso fallido", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Credenciales validas: solicitar La Llave
            MessageBox.Show(
                $"Credenciales de [{user}] verificadas.\n\n" +
                "Selecciona tu archivo La Llave (llave_acceso.json) para autenticar la sesion.\n\n" +
                "Busca el archivo en la carpeta donde guardaste tus datos del visor.",
                "Autenticacion con Llave",
                MessageBoxButton.OK,
                MessageBoxImage.Information);

            var dialog = new OpenFileDialog
            {
                Title = "Selecciona tu archivo La Llave (llave_acceso.json)",
                Filter = "Archivo Llave (*.json)|*.json|Todos los archivos (*.*)|*.*",
                InitialDirectory = UserDataDir
            };

            if (dialog.ShowDialog() != true)
            {
                MessageBox.Show("No se selecciono ninguna llave. Inicio cancelado.",
                                "Aviso", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            try
            {
                string jsonLlave = File.ReadAllText(dialog.FileName, Encoding.UTF8);
                using var doc = JsonDocument.Parse(jsonLlave);
                var root = doc.RootElement;

                string llaveUsuario = root.TryGetProperty("usuario", out var u) ? u.GetString() ?? "" : "";
                if (!llaveUsuario.Equals(user, StringComparison.OrdinalIgnoreCase))
                {
                    MessageBox.Show(
                        $"La llave pertenece a [{llaveUsuario}], no a [{user}].\nAcceso denegado.",
                        "Llave no coincide", MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }

                string oldHash  = root.TryGetProperty("hash_llave", out var h)   ? h.GetString()      ?? "" : "";
                string uuid     = root.TryGetProperty("uuid", out var idProp)     ? idProp.GetString() ?? "" : "";
                string hwHash   = root.TryGetProperty("hardware_hash", out var hw)? hw.GetString()     ?? "" : "";
                string seedHash = root.TryGetProperty("seed_hash", out var sh)    ? sh.GetString()     ?? "" : "";
                string creado   = root.TryGetProperty("creado", out var cr)       ? cr.GetString()     ?? "" : "";

                int rotaciones = 0;
                if (root.TryGetProperty("rotaciones", out var rot)) rotaciones = rot.GetInt32();
                rotaciones++;

                // Rotar el hash de la llave en cada sesion
                string newHash = ComputeSha256($"{oldHash}|{Guid.NewGuid()}|{DateTime.UtcNow.Ticks}");

                var updatedKey = new
                {
                    tipo          = "WoldVirtual_MasterKey_DeFi_v1",
                    uuid          = uuid,
                    usuario       = user,
                    hash_llave    = newHash,
                    hash_anterior = oldHash,
                    hardware_hash = hwHash,
                    seed_hash     = seedHash,
                    creado        = creado,
                    ultima_sesion = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                    rotaciones    = rotaciones
                };

                string updatedJson = JsonSerializer.Serialize(updatedKey, new JsonSerializerOptions
                {
                    WriteIndented = true,
                    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                });

                // Actualizar SOLO el archivo que el usuario ha seleccionado (en su carpeta)
                File.WriteAllText(dialog.FileName, updatedJson, Encoding.UTF8);

                // Si la llave local (junto al exe) existe, actualizarla tambien
                if (File.Exists(LlavePath))
                    File.WriteAllText(LlavePath, updatedJson, Encoding.UTF8);

                string previewNew = newHash.Length >= 16 ? newHash[..16] : newHash;

                MessageBox.Show(
                    $"Sesion iniciada correctamente!\n\n" +
                    $"Usuario: {user}\n" +
                    $"Nuevo hash de llave: {previewNew}... (Rotacion #{rotaciones})",
                    "Bienvenido — Wold Virtual P2P",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);

                BarraInferiorLogin.Visibility = Visibility.Collapsed;
                PanelBienvenida.Visibility = Visibility.Collapsed;
                PanelMundo3D.Visibility = Visibility.Visible;

                TxtSesionUsuario.Text = $"Usuario: {user}";
                TxtSesionLlave.Text   = $"Llave: {previewNew}... (#{rotaciones})";

                IniciarGodotMain();
                IniciarP2P(user);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al validar la llave:\n{ex.Message}",
                                "Error de Llave", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void IniciarGodotMain()
        {
            if (_godotHostMain != null) return;
            Dispatcher.InvokeAsync(() =>
            {
                try
                {
                    string godotExe   = GodotConfig.GetGodotExePath();
                    string projectDir = GodotConfig.GetProjectPath();
                    string scenePath  = GodotConfig.GetScenePath();

                    GuardarP2PSessionConfig();

                    string userArgs = "";
                    if (!string.IsNullOrWhiteSpace(_urlAmigoPendiente))
                        userArgs = $"--peer-url=\"{_urlAmigoPendiente}\"";

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
                    peerUrl         = _urlAmigoPendiente ?? "",
                    myTunnelUrl     = _p2pServicio?.UrlPublicaPropia ?? "",
                    puertoLocal     = 7890,
                    puertoGodot     = 8910,
                    esPrimerUsuario = string.IsNullOrWhiteSpace(_urlAmigoPendiente),
                    timestamp       = DateTime.UtcNow.ToString("o")
                };

                string json = JsonSerializer.Serialize(sessionData, new JsonSerializerOptions { WriteIndented = true });

                // Guardar junto al exe (en datos_usuario)
                Directory.CreateDirectory(UserDataDir);
                File.WriteAllText(Path.Combine(UserDataDir, "p2p_session.json"), json, Encoding.UTF8);

                // Copia tecnica en user:// de Godot — el motor 3D necesita leer este archivo
                // desde su propia ruta. SOLO contiene info de sesion P2P (URL tunel, puertos),
                // NO contiene datos privados (llave, semilla, perfil de usuario).
                string godotUserDir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "Godot", "app_userdata", "WoldVirtualP2P3D");
                Directory.CreateDirectory(godotUserDir);
                File.WriteAllText(Path.Combine(godotUserDir, "p2p_session.json"), json, Encoding.UTF8);
            }
            catch { }
        }

        private async void IniciarP2P(string user)
        {
            try
            {
                _p2pServicio = new RedP2PServicio(user);

                Dispatcher.Invoke(() =>
                {
                    TxtUrlP2P.Text = "⏳ Generando túnel efímero...";
                    BannerP2P.Visibility = Visibility.Visible;
                });

                _p2pServicio.UrlTunnelLista += url =>
                {
                    Dispatcher.Invoke(() =>
                    {
                        TxtUrlP2P.Text = url;
                        BannerP2P.Visibility = Visibility.Visible;
                        TxtEstadoP2P.Text = "Red P2P Online";
                        BordeEstadoP2P.Background = new System.Windows.Media.SolidColorBrush(
                            System.Windows.Media.Color.FromRgb(6, 78, 59));
                    });
                };

                _p2pServicio.NuevoPar += peer =>
                {
                    Dispatcher.Invoke(() => TxtEstadoP2P.Text = $"Amigo Conectado: {peer}");
                };

                await _p2pServicio.IniciarAsync();

                if (!string.IsNullOrWhiteSpace(_urlAmigoPendiente))
                {
                    bool ok = await _p2pServicio.ConectarConParAsync(_urlAmigoPendiente);
                    Dispatcher.Invoke(() => { if (ok) TxtEstadoP2P.Text = "Enlazado con amigo"; });
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[P2P] Error al iniciar: {ex.Message}");
            }
        }

        private void OnCopiarUrlP2PClicked(object sender, RoutedEventArgs e)
        {
            string url = TxtUrlP2P.Text?.Trim() ?? "";
            if (!string.IsNullOrWhiteSpace(url) && !url.StartsWith("⏳"))
            {
                try
                {
                    Clipboard.SetText(url);
                    MessageBox.Show(
                        $"Enlace P2P copiado al portapapeles!\n\n{url}\n\n" +
                        "Compartelo con tu amigo para que se conecte a tu mundo.",
                        "Enlace P2P Copiado", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show($"Error al copiar:\n{ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Warning);
                }
            }
            else
            {
                MessageBox.Show("El enlace P2P todavia no esta disponible. Espera unos segundos a que la red P2P conecte.",
                                "Enlace no disponible", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void OnWebNodoClicked(object sender, RoutedEventArgs e)
        {
            string url = TxtUrlP2P.Text?.Trim() ?? "";
            if (string.IsNullOrWhiteSpace(url) || url.StartsWith("⏳") || url.StartsWith("Iniciando"))
            {
                // Si el túnel público aún está resolviendo, abrir la dirección local del WebNodo
                int puerto = _p2pServicio?.Nodo?.Puerto ?? 7890;
                url = $"http://localhost:{puerto}/";
            }

            try
            {
                // Copiar enlace al portapapeles para facilitar compartirlo
                Clipboard.SetText(url);

                // Abrir la web en el navegador predeterminado del sistema
                Process.Start(new ProcessStartInfo
                {
                    FileName = url,
                    UseShellExecute = true
                });

                MessageBox.Show(
                    $"🌐 Portal WebNodo abierto en tu navegador!\n\n" +
                    $"Enlace de sesión efímero (copiado al portapapeles):\n{url}\n\n" +
                    $"Tus invitados verán la web futurista del metaverso con la información de tu sesión,\n" +
                    $"el túnel efímero y el botón para descargar directamente el visor 3D (.exe) más actualizado.",
                    "WebNodo Metaverso P2P", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al abrir WebNodo:\n{ex.Message}", "Error WebNodo", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        private async void OnConectarAmigoClicked(object sender, RoutedEventArgs e)
        {
            string url = TxtUrlAmigo.Text.Trim();
            if (string.IsNullOrWhiteSpace(url))
            {
                MessageBox.Show("Por favor ingresa el enlace P2P de tu amigo primero.",
                                "Aviso", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            _urlAmigoPendiente = url;
            BtnConectarAmigo.Content = "Probando...";
            BtnConectarAmigo.IsEnabled = false;

            bool responde = await P2PNodo.PingParAsync(url);
            BtnConectarAmigo.Content = "Conectar";
            BtnConectarAmigo.IsEnabled = true;

            if (responde)
                MessageBox.Show("Conexion con el amigo detectada!\nIntroduce tu usuario y contrasena para iniciar sesion.",
                                "Amigo Disponible", MessageBoxButton.OK, MessageBoxImage.Information);
            else
                MessageBox.Show("No se pudo contactar al amigo. Asegurate de que su visor este abierto.",
                                "Aviso P2P", MessageBoxButton.OK, MessageBoxImage.Warning);
        }

        private bool ValidarCredenciales(string user, string pass)
        {
            string enteredHash = ComputeSha256(pass);

            if (File.Exists(UserProfilePath))
            {
                try
                {
                    string json = File.ReadAllText(UserProfilePath, Encoding.UTF8);
                    using var doc = JsonDocument.Parse(json);
                    var root = doc.RootElement;
                    if (root.GetProperty("nombre").GetString()?.Equals(user, StringComparison.OrdinalIgnoreCase) == true &&
                        root.GetProperty("passwordHash").GetString()?.Equals(enteredHash) == true)
                        return true;
                }
                catch { }
            }

            if (File.Exists(CredentialsPath))
            {
                try
                {
                    string json = File.ReadAllText(CredentialsPath, Encoding.UTF8);
                    using var doc = JsonDocument.Parse(json);
                    var root = doc.RootElement;
                    if (root.GetProperty("username").GetString()?.Equals(user, StringComparison.OrdinalIgnoreCase) == true &&
                        root.GetProperty("passwordHash").GetString()?.Equals(enteredHash) == true)
                        return true;
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
