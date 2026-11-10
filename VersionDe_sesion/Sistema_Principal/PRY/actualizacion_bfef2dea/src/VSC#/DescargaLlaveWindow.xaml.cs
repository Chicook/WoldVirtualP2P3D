using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;
using Microsoft.Win32;

namespace Visor3D
{
    public partial class DescargaLlaveWindow : Window
    {
        // Datos del usuario en %LocalAppData%\WoldVirtualP2P3D\user\
        private static readonly string TestUserDir =
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "WoldVirtualP2P3D", "user");

        private readonly string _uuid;
        private readonly string _username;
        private readonly string _seedHash;
        private readonly string _hardwareHash;

        private string _keyHash = "";

        public DescargaLlaveWindow(string uuid, string username, string seedHash, string hardwareHash)
        {
            _uuid         = uuid;
            _username     = username;
            _seedHash     = seedHash;
            _hardwareHash = hardwareHash;

            InitializeComponent();

            this.Loaded  += OnLoaded;
            this.Closing += OnClosing;

            BtnDescargarLlave.Click += OnDescargarLlaveClicked;
            BtnFinalizar.Click      += OnFinalizarClicked;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            TxtUsuario.Text = _username;

            // Generar hash único de la llave
            string rawKey = $"{_uuid}|{_seedHash}|{_hardwareHash}|{DateTime.UtcNow.Ticks}";
            _keyHash = ComputeSha256(rawKey);
            TxtHashLlave.Text = _keyHash;

            // Guardar llave local automáticamente en test_user_data/user/llave_acceso.json
            GuardarLlaveLocal();
        }

        private void OnClosing(object? sender, System.ComponentModel.CancelEventArgs e)
        {
            if (Application.Current.MainWindow is MainWindow mainWin)
            {
                mainWin.ActivarModoLogin(_username);
                mainWin.Show();
                mainWin.Activate();
            }
        }

        private void GuardarLlaveLocal()
        {
            try
            {
                var keyData = new
                {
                    tipo          = "WoldVirtual_MasterKey_DeFi_v1",
                    uuid          = _uuid,
                    usuario       = _username,
                    hash_llave    = _keyHash,
                    hash_anterior = "",
                    hardware_hash = _hardwareHash,
                    seed_hash     = _seedHash,
                    creado        = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                    ultima_sesion = "",
                    rotaciones    = 0
                };

                string jsonContent = JsonSerializer.Serialize(keyData, new JsonSerializerOptions
                {
                    WriteIndented = true,
                    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                });

                Directory.CreateDirectory(TestUserDir);
                File.WriteAllText(Path.Combine(TestUserDir, "llave_acceso.json"), jsonContent, Encoding.UTF8);
            }
            catch { }
        }

        private void OnDescargarLlaveClicked(object sender, RoutedEventArgs e)
        {
            var dialog = new SaveFileDialog
            {
                Title      = "Guardar Copia de «La Llave» de Acceso",
                FileName   = "llave_acceso.json",
                DefaultExt = ".json",
                Filter     = "Archivo JSON (*.json)|*.json"
            };

            if (dialog.ShowDialog() != true) return;

            try
            {
                var keyData = new
                {
                    tipo          = "WoldVirtual_MasterKey_DeFi_v1",
                    uuid          = _uuid,
                    usuario       = _username,
                    hash_llave    = _keyHash,
                    hash_anterior = "",
                    hardware_hash = _hardwareHash,
                    seed_hash     = _seedHash,
                    creado        = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                    ultima_sesion = "",
                    rotaciones    = 0
                };

                string jsonContent = JsonSerializer.Serialize(keyData, new JsonSerializerOptions
                {
                    WriteIndented = true,
                    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                });

                File.WriteAllText(dialog.FileName, jsonContent, Encoding.UTF8);

                MessageBox.Show(
                    $"Copia de «La Llave» guardada correctamente en:\n{dialog.FileName}",
                    "Llave Exportada", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al exportar la llave:\n{ex.Message}",
                                "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void OnFinalizarClicked(object sender, RoutedEventArgs e)
        {
            if (Application.Current.MainWindow is MainWindow main)
            {
                main.ActivarModoLogin(_username);
            }
            this.Close();
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
