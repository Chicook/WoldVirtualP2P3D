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
        // Carpeta local para datos de usuario y pruebas de flujo
        private static readonly string TestUserDataDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "test_user_data");

        private static readonly string CredentialsPath =
            Path.Combine(TestUserDataDir, "credentials.json");

        public MainWindow()
        {
            InitializeComponent();
            this.Loaded += OnLoaded;

            // Navegación de bienvenida
            BtnCrearCuenta.Click += OnCrearCuentaClicked;
            BtnAcceder.Click += OnAccederClicked;
            BtnVolverBienvenida.Click += OnVolverBienvenidaClicked;

            // Login
            BtnLogin.Click += OnLoginClicked;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            MostrarPantallaBienvenida();
        }

        private void MostrarPantallaBienvenida()
        {
            PanelBienvenida.Visibility = Visibility.Visible;
            PanelMundo3D.Visibility = Visibility.Collapsed;
            BarraInferiorLogin.Visibility = Visibility.Collapsed;
        }

        private void OnCrearCuentaClicked(object sender, RoutedEventArgs e)
        {
            MessageBox.Show(
                "Módulo de registro en preparación.\nPronto se desplegará el formulario para crear tu cuenta en Wold Virtual P2P.",
                "Crear Cuenta",
                MessageBoxButton.OK,
                MessageBoxImage.Information);
        }

        private void OnAccederClicked(object sender, RoutedEventArgs e)
        {
            // Oculta bienvenida y muestra el viewport 3D junto con la barra de inicio de sesión
            PanelBienvenida.Visibility = Visibility.Collapsed;
            PanelMundo3D.Visibility = Visibility.Visible;
            BarraInferiorLogin.Visibility = Visibility.Visible;
            TxtLoginUser.Focus();
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

            // Ocultar barra de login tras ingreso exitoso
            BarraInferiorLogin.Visibility = Visibility.Collapsed;
            MessageBox.Show($"Bienvenido a Wold Virtual: {user}", "Sesión Iniciada", MessageBoxButton.OK, MessageBoxImage.Information);
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
                Directory.CreateDirectory(TestUserDataDir);
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
