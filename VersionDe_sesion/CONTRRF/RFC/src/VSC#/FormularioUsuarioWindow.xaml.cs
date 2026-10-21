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
        private static readonly string TestUserDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "test_user_data", "user");

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

            // Hash de contraseña (SHA-256)
            string passHash = ComputeSha256(pass);

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

                // Guardar también credentials.json en test_user_data para login directo
                string credsPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "test_user_data", "credentials.json");
                var creds = new { username = nombre, passwordHash = passHash };
                File.WriteAllText(credsPath, JsonSerializer.Serialize(creds), Encoding.UTF8);

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
