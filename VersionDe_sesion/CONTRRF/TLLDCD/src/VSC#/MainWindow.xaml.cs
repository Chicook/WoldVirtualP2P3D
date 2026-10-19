using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;

namespace Visor3D
{
    public partial class MainWindow : Window
    {
        private static readonly string AppDataDir =
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "WoldVirtual");

        private static readonly string CredentialsPath =
            Path.Combine(AppDataDir, "credentials.json");

        public MainWindow()
        {
            InitializeComponent();
            this.Loaded += OnLoaded;
            BtnLogin.Click += OnLoginClicked;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            TxtLoginUser.Focus();
        }

        private void OnLoginClicked(object sender, RoutedEventArgs e)
        {
            string user = TxtLoginUser.Text.Trim();
            string pass = TxtLoginPass.Password;

            if (string.IsNullOrWhiteSpace(user) || string.IsNullOrWhiteSpace(pass))
            {
                MessageBox.Show("Por favor, ingrese usuario y contrase\u00F1a.",
                                "Validaci\u00F3n", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            if (File.Exists(CredentialsPath))
            {
                if (!ValidarCredenciales(user, pass))
                {
                    MessageBox.Show("Usuario o contrase\u00F1a incorrectos.",
                                    "Ingreso fallido", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }
            }
            else
            {
                CrearCredenciales(user, pass);
            }
        }

        private bool ValidarCredenciales(string user, string pass)
        {
            try
            {
                string json = File.ReadAllText(CredentialsPath, Encoding.UTF8);
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                string savedUser = root.GetProperty("username").GetString() ?? "";
                string savedHash = root.GetProperty("passwordHash").GetString() ?? "";
                string enteredHash = ComputeSha256(pass);

                return savedUser.Equals(user, StringComparison.OrdinalIgnoreCase)
                    && savedHash.Equals(enteredHash, StringComparison.Ordinal);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al leer credenciales: {ex.Message}",
                                "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                return false;
            }
        }

        private void CrearCredenciales(string user, string pass)
        {
            try
            {
                Directory.CreateDirectory(AppDataDir);
                string hash = ComputeSha256(pass);
                var data = new { username = user, passwordHash = hash };
                string json = JsonSerializer.Serialize(data);
                File.WriteAllText(CredentialsPath, json, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"No se guardaron las credenciales: {ex.Message}",
                                "Error", MessageBoxButton.OK, MessageBoxImage.Warning);
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
    }
}
