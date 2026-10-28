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

        private async void OnCrearUsuarioClicked(object sender, RoutedEventArgs e)
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

            // Evaluación de Seguridad SMTPLC (Anti-VM, Anti-VPN y Anti-Multicuenta en la misma ubicación)
            BtnCrearUsuario.IsEnabled = false;
            try
            {
                var evaluacion = await Visor3D.Seguridad.SMTPLC.SmtplcSecurityService.Instance.EvaluateRegistrationAsync(nombre, _hardwareHash);
                if (!evaluacion.IsAllowed)
                {
                    MostrarError($"{evaluacion.DenialTitle}:\n{evaluacion.DenialReason}");
                    BtnCrearUsuario.IsEnabled = true;
                    return;
                }

                // Generar UUID único para el usuario
                _uuid = Guid.NewGuid().ToString();

                // Hash de contraseña (PBKDF2-SHA256 con sal)
                string passHash = Visor3D.Seguridad.PasswordHasher.Hash(pass);

                // Guardar perfil en test_user_data/user/user_profile.json
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

                // Registrar en el Libro Mayor SMTPLC de la ubicación
                Visor3D.Seguridad.SMTPLC.SmtplcSecurityService.Instance.CommitRegistration(_uuid, nombre, evaluacion, _hardwareHash);

                // Pasar a la siguiente pantalla: Frase Semilla de la Wallet DeFi
                var semillaWin = new SemillaWalletWindow(_uuid, nombre, passHash, _hardwareHash);
                semillaWin.Show();
                this.Close();
            }
            catch (Exception ex)
            {
                MostrarError($"No se pudo guardar el perfil:\n{ex.Message}");
                BtnCrearUsuario.IsEnabled = true;
            }
        }

        private void MostrarError(string mensaje)
        {
            TxtError.Text = mensaje;
            TxtError.Visibility = Visibility.Visible;
        }
    }
}
