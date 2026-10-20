using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;
using Microsoft.Win32;

namespace Visor3D
{
    /// <summary>
    /// Paso 5: Descargar La Llave. Datos guardados en datos_usuario\ junto al exe.
    /// </summary>
    public partial class DescargaLlaveWindow : Window
    {
        private static readonly string UserDataDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "datos_usuario");

        private readonly string _uuid;
        private readonly string _username;
        private readonly string _seedHash;
        private readonly string _hardwareHash;
        private string _keyHash = "";

        public DescargaLlaveWindow(string uuid, string username, string seedHash, string hardwareHash)
        {
            _uuid = uuid; _username = username;
            _seedHash = seedHash; _hardwareHash = hardwareHash;
            InitializeComponent();
            this.Loaded  += OnLoaded;
            this.Closing += OnClosing;
            BtnDescargarLlave.Click += OnDescargarLlaveClicked;
            BtnFinalizar.Click      += OnFinalizarClicked;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            TxtUsuario.Text = _username;
            string rawKey = $"{_uuid}|{_seedHash}|{_hardwareHash}|{DateTime.UtcNow.Ticks}";
            _keyHash = ComputeSha256(rawKey);
            TxtHashLlave.Text = _keyHash;
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
                // Copia local en datos_usuario\ junto al exe
                Directory.CreateDirectory(UserDataDir);
                File.WriteAllText(Path.Combine(UserDataDir, "llave_acceso.json"), BuildKeyJson(), Encoding.UTF8);
            }
            catch { }
        }

        private string BuildKeyJson()
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
            return JsonSerializer.Serialize(keyData, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });
        }

        private void OnDescargarLlaveClicked(object sender, RoutedEventArgs e)
        {
            // El usuario elige donde guardar su copia — en la carpeta que el controla
            var dialog = new SaveFileDialog
            {
                Title      = "Guardar La Llave — pon esto donde SOLO TU tengas acceso",
                FileName   = "llave_acceso.json",
                DefaultExt = ".json",
                Filter     = "Archivo JSON (*.json)|*.json"
            };
            if (dialog.ShowDialog() != true) return;

            try
            {
                File.WriteAllText(dialog.FileName, BuildKeyJson(), Encoding.UTF8);
                MessageBox.Show(
                    $"La Llave guardada en:\n{dialog.FileName}\n\n" +
                    "Guardala en un lugar SOLO tuyo (USB, pendrive, carpeta que SOLO TU controlas).\n\n" +
                    "Esta llave + tu contrasena son lo unico que da acceso al metaverso.\n" +
                    "Una copia de emergencia queda en datos_usuario\\ junto al visor.",
                    "Llave Exportada", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error:\n{ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void OnFinalizarClicked(object sender, RoutedEventArgs e)
        {
            if (Application.Current.MainWindow is MainWindow main)
                main.ActivarModoLogin(_username);
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
