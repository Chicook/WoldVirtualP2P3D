using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;

namespace Visor3D
{
    /// <summary>
    /// Paso 2: Crear usuario. Datos guardados en datos_usuario\ junto al exe.
    /// </summary>
    public partial class FormularioUsuarioWindow : Window
    {
        private static readonly string UserDataDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "datos_usuario");

        private readonly string _hardwareHash;
        private string _uuid = "";

        public FormularioUsuarioWindow(string hardwareHash)
        {
            _hardwareHash = hardwareHash;
            InitializeComponent();
            this.Loaded += OnLoaded;
            BtnCrearUsuario.Click += OnCrearUsuarioClicked;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            Directory.CreateDirectory(UserDataDir);
            TxtNombre.Focus();
        }

        private void OnCrearUsuarioClicked(object sender, RoutedEventArgs e)
        {
            TxtError.Visibility = Visibility.Collapsed;

            string nombre  = TxtNombre.Text.Trim();
            string pass    = TxtPassword.Password;
            string passRep = TxtPasswordRepetir.Password;

            if (string.IsNullOrWhiteSpace(nombre) || nombre.Length < 3)
            { MostrarError("El nombre debe tener al menos 3 caracteres."); return; }

            if (pass.Length < 6)
            { MostrarError("La contrasena debe tener al menos 6 caracteres."); return; }

            if (pass != passRep)
            {
                MostrarError("Las contrasenias no coinciden.");
                TxtPasswordRepetir.Clear();
                TxtPasswordRepetir.Focus();
                return;
            }

            _uuid = Guid.NewGuid().ToString();
            string passHash = ComputeSha256(pass);

            try
            {
                var perfil = new
                {
                    uuid         = _uuid,
                    nombre       = nombre,
                    passwordHash = passHash,
                    hardwareHash = _hardwareHash,
                    creado       = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
                };

                string json = JsonSerializer.Serialize(perfil, new JsonSerializerOptions
                {
                    WriteIndented = true,
                    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                });

                // Todo en datos_usuario\ junto al exe
                File.WriteAllText(Path.Combine(UserDataDir, "user_profile.json"), json, Encoding.UTF8);

                var creds = new { username = nombre, passwordHash = passHash };
                File.WriteAllText(
                    Path.Combine(UserDataDir, "credentials.json"),
                    JsonSerializer.Serialize(creds, new JsonSerializerOptions { WriteIndented = true }),
                    Encoding.UTF8);

                var semillaWin = new SemillaWalletWindow(_uuid, nombre, passHash, _hardwareHash);
                semillaWin.Show();
                this.Close();
            }
            catch (Exception ex)
            {
                MostrarError($"No se pudo guardar el perfil:\n{ex.Message}");
            }
        }

        private void MostrarError(string msg)
        {
            TxtError.Text = msg;
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
