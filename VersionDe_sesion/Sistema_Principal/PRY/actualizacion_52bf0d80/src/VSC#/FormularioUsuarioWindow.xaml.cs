using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;

namespace Visor3D
{
    public partial class FormularioUsuarioWindow : Window
    {
        // Datos del usuario en %LocalAppData%\WoldVirtualP2P3D\user\
        private static readonly string TestUserDir =
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "WoldVirtualP2P3D", "user");

        private readonly string _hardwareHash;
        private string _uuid = "";

        /// <summary>Recibe el hash de hardware generado en el paso anterior.</summary>
        public FormularioUsuarioWindow(string hardwareHash)
        {
            _hardwareHash = hardwareHash;
            InitializeComponent();
            this.Loaded += OnLoaded;
            BtnCrearUsuario.Click += OnCrearUsuarioClicked;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            Directory.CreateDirectory(TestUserDir);
            TxtNombre.Focus();
        }

        private void OnCrearUsuarioClicked(object sender, RoutedEventArgs e)
        {
            TxtError.Visibility = Visibility.Collapsed;

            // Última barrera: ni con el formulario abierto se permite una
            // segunda cuenta si el PC ya tiene identidad guardada.
            if (Visor3D.Seguridad.PerfilUsuario.TieneIdentidad)
            {
                MostrarError("Este equipo ya tiene una cuenta. Sólo se permite UNA cuenta por PC.");
                return;
            }

            string nombre = TxtNombre.Text.Trim();
            string pass = TxtPassword.Password;
            string passRep = TxtPasswordRepetir.Password;

            // Validaciones
            if (string.IsNullOrWhiteSpace(nombre) || nombre.Length < 3)
            {
                MostrarError("El nombre de usuario debe tener al menos 3 caracteres.");
                return;
            }

            if (pass.Length < 6)
            {
                MostrarError("La contraseña debe tener al menos 6 caracteres.");
                return;
            }

            if (pass != passRep)
            {
                MostrarError("Las contraseñas no coinciden. Compruébalas e inténtalo de nuevo.");
                TxtPasswordRepetir.Clear();
                TxtPasswordRepetir.Focus();
                return;
            }

            // Generar UUID único para el usuario
            _uuid = Guid.NewGuid().ToString();

            // Hash de contraseña (PBKDF2-SHA256 con sal)
            string passHash = Visor3D.Seguridad.PasswordHasher.Hash(pass);

            // Guardar perfil en test_user_data/user/user_profile.json
            try
            {
                var perfil = new
                {
                    uuid        = _uuid,
                    nombre      = nombre,
                    passwordHash = passHash,
                    hardwareHash = _hardwareHash,
                    creado      = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
                };

                string json = JsonSerializer.Serialize(perfil, new JsonSerializerOptions
                {
                    WriteIndented = true,
                    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                });

                string perfilPath = Path.Combine(TestUserDir, "user_profile.json");
                File.WriteAllText(perfilPath, json, Encoding.UTF8);

                // Guardar credentials.json en la misma carpeta de datos del usuario
                string credsPath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "WoldVirtualP2P3D", "credentials.json");
                var creds = new { username = nombre, passwordHash = passHash };
                File.WriteAllText(credsPath, JsonSerializer.Serialize(creds), Encoding.UTF8);

                // ── Sesión única: sellar este PC como "ya registrado" ──────────
                Visor3D.Seguridad.SesionUnica.SesionUnicaGuarda.SellarDespuesDeRegistro(_uuid);

                // Pasar a la siguiente pantalla: Frase Semilla de la Wallet DeFi
                var semillaWin = new SemillaWalletWindow(_uuid, nombre, passHash, _hardwareHash);
                semillaWin.Show();
                this.Close();
            }
            catch (Exception ex)
            {
                MostrarError($"No se pudo guardar el perfil:\n{ex.Message}");
            }
        }

        private void MostrarError(string mensaje)
        {
            TxtError.Text = mensaje;
            TxtError.Visibility = Visibility.Visible;
        }
    }
}
