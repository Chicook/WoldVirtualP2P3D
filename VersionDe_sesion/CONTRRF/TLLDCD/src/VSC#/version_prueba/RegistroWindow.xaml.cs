using System;
using System.IO;
using System.IO.Compression;
using System.Management;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;
using Microsoft.Win32;

namespace Visor3D
{
    /// <summary>
    /// Paso 1: Registrar PC.
    /// Los datos se guardan en datos_usuario\ junto al exe — en la carpeta que el usuario controla.
    /// </summary>
    public partial class RegistroWindow : Window
    {
        private static readonly string UserDataDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "datos_usuario");

        private string _os = "";
        private string _motherboard = "";
        private string _cpu = "";
        private string _hardwareHash = "";
        private bool _zipDescargado = false;

        public RegistroWindow()
        {
            InitializeComponent();
            this.Loaded += OnLoaded;
            BtnDescargar.Click += OnDescargarClicked;
            BtnVolver.Click += OnVolverOSiguienteClicked;
        }

        private void OnVolverOSiguienteClicked(object sender, RoutedEventArgs e)
        {
            if (_zipDescargado)
            {
                var formulario = new FormularioUsuarioWindow(_hardwareHash);
                formulario.Show();
                this.Close();
            }
            else
            {
                this.Close();
            }
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            Directory.CreateDirectory(UserDataDir);
            DetectarHardware();
        }

        private void DetectarHardware()
        {
            try
            {
                _os          = ObtenerWmi("Win32_OperatingSystem", "Caption") + " " +
                               ObtenerWmi("Win32_OperatingSystem", "Version");
                _motherboard = ObtenerWmi("Win32_BaseBoard", "Manufacturer") + " " +
                               ObtenerWmi("Win32_BaseBoard", "Product");
                _cpu         = ObtenerWmi("Win32_Processor", "Name");

                string rawId = $"{_os}|{_motherboard}|{_cpu}";
                using var sha = SHA256.Create();
                byte[] hashBytes = sha.ComputeHash(Encoding.UTF8.GetBytes(rawId));
                _hardwareHash = BitConverter.ToString(hashBytes).Replace("-", "").ToLowerInvariant();

                Dispatcher.Invoke(() =>
                {
                    TxtOS.Text          = _os.Trim();
                    TxtMotherboard.Text = _motherboard.Trim();
                    TxtCPU.Text         = _cpu.Trim();
                    TxtHash.Text        = _hardwareHash;
                });
            }
            catch (Exception ex)
            {
                Dispatcher.Invoke(() =>
                {
                    TxtOS.Text = TxtMotherboard.Text = TxtCPU.Text = "No se pudo detectar";
                    TxtHash.Text = $"Error: {ex.Message}";
                });
            }
        }

        private static string ObtenerWmi(string clase, string propiedad)
        {
            try
            {
                using var searcher = new ManagementObjectSearcher($"SELECT {propiedad} FROM {clase}");
                foreach (ManagementObject obj in searcher.Get())
                {
                    var val = obj[propiedad]?.ToString() ?? "";
                    if (!string.IsNullOrWhiteSpace(val)) return val.Trim();
                }
            }
            catch { }
            return "Desconocido";
        }

        private void OnDescargarClicked(object sender, RoutedEventArgs e)
        {
            if (string.IsNullOrEmpty(_hardwareHash))
            {
                MessageBox.Show("El hardware aun se esta detectando. Espera un momento.",
                                "Aviso", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            // El usuario elige donde guardar el ZIP — el lo controla
            var dialog = new SaveFileDialog
            {
                Title      = "Guardar identificador de hardware — pon esto donde TU lo controles",
                FileName   = $"wold_hardware_id_{_hardwareHash[..8]}",
                DefaultExt = ".zip",
                Filter     = "Archivo ZIP|*.zip"
            };

            if (dialog.ShowDialog() != true) return;

            try
            {
                CrearZipConJson(dialog.FileName);
                _zipDescargado = true;
                TxtDescargaOk.Visibility = Visibility.Visible;
                BtnVolver.Content = "Siguiente paso";

                MessageBox.Show(
                    $"Identificador guardado en:\n{dialog.FileName}\n\n" +
                    "Guardalo en un lugar seguro que TU controles (USB, carpeta cifrada, etc.).\n\n" +
                    "Nota: se guarda una copia local en datos_usuario\\ junto al visor.",
                    "Descarga completada", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al guardar:\n{ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void CrearZipConJson(string destZipPath)
        {
            var hardwareData = new
            {
                generado          = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                sistema_operativo = _os.Trim(),
                placa_base        = _motherboard.Trim(),
                procesador        = _cpu.Trim(),
                hash_sha256       = _hardwareHash,
                nota              = "Identificador de hardware para Wold Virtual P2P 3D. No contiene datos personales."
            };

            string jsonContent = JsonSerializer.Serialize(hardwareData, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });

            // Copia local junto al exe (en datos_usuario\)
            Directory.CreateDirectory(UserDataDir);
            File.WriteAllText(Path.Combine(UserDataDir, "hardware_id.json"), jsonContent, Encoding.UTF8);

            if (File.Exists(destZipPath)) File.Delete(destZipPath);

            using var zipStream = new FileStream(destZipPath, FileMode.Create, FileAccess.Write);
            using var archive   = new ZipArchive(zipStream, ZipArchiveMode.Create, leaveOpen: false);

            var jsonEntry = archive.CreateEntry("hardware_id.json", CompressionLevel.Optimal);
            using (var s = jsonEntry.Open())
            using (var w = new StreamWriter(s, new UTF8Encoding(false)))
            { w.Write(jsonContent); w.Flush(); }

            var readmeEntry = archive.CreateEntry("LEEME.txt", CompressionLevel.Optimal);
            using (var s = readmeEntry.Open())
            using (var w = new StreamWriter(s, new UTF8Encoding(false)))
            {
                w.WriteLine("=== WOLD VIRTUAL P2P 3D - Identificador de Hardware ===");
                w.WriteLine("Guarda este archivo en un lugar seguro que TU controles.");
                w.WriteLine($"Hash: {_hardwareHash}");
                w.WriteLine($"Generado: {DateTime.UtcNow:yyyy-MM-dd HH:mm:ss} UTC");
                w.Flush();
            }
        }
    }
}
