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
    public partial class RegistroWindow : Window
    {
        // Carpeta local de datos de prueba del usuario
        private static readonly string TestUserDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "test_user_data", "user");

        // Datos de hardware detectados
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
            // Crear carpeta de usuario de prueba si no existe
            Directory.CreateDirectory(TestUserDir);

            // Detectar hardware en segundo plano para no bloquear la UI
            DetectarHardware();
        }

        private void DetectarHardware()
        {
            try
            {
                _os = ObtenerWmi("Win32_OperatingSystem", "Caption") + " " +
                      ObtenerWmi("Win32_OperatingSystem", "Version");
                _motherboard = ObtenerWmi("Win32_BaseBoard", "Manufacturer") + " " +
                               ObtenerWmi("Win32_BaseBoard", "Product");
                _cpu = ObtenerWmi("Win32_Processor", "Name");

                // Generar hash combinado con SHA-256
                string rawId = $"{_os}|{_motherboard}|{_cpu}";
                using var sha = SHA256.Create();
                byte[] hashBytes = sha.ComputeHash(Encoding.UTF8.GetBytes(rawId));
                _hardwareHash = BitConverter.ToString(hashBytes).Replace("-", "").ToLowerInvariant();

                // Actualizar UI en el hilo principal
                Dispatcher.Invoke(() =>
                {
                    TxtOS.Text = _os.Trim();
                    TxtMotherboard.Text = _motherboard.Trim();
                    TxtCPU.Text = _cpu.Trim();
                    TxtHash.Text = _hardwareHash;
                });
            }
            catch (Exception ex)
            {
                Dispatcher.Invoke(() =>
                {
                    TxtOS.Text = "No se pudo detectar";
                    TxtMotherboard.Text = "No se pudo detectar";
                    TxtCPU.Text = "No se pudo detectar";
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
            catch { /* Se maneja en DetectarHardware */ }
            return "Desconocido";
        }

        private void OnDescargarClicked(object sender, RoutedEventArgs e)
        {
            if (string.IsNullOrEmpty(_hardwareHash))
            {
                MessageBox.Show("El hardware aún se está detectando. Espera un momento.",
                                "Aviso", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            // Cuadro de guardar archivo
            var dialog = new SaveFileDialog
            {
                Title = "Guardar identificador de hardware",
                FileName = $"wold_hardware_id_{_hardwareHash[..8]}",
                DefaultExt = ".zip",
                Filter = "Archivo ZIP|*.zip"
            };

            if (dialog.ShowDialog() != true) return;

            try
            {
                CrearZipConJson(dialog.FileName);

                // Marcar descarga completada y actualizar UI
                _zipDescargado = true;
                TxtDescargaOk.Visibility = Visibility.Visible;
                BtnVolver.Content = "Siguiente paso →";
                BtnVolver.Foreground = new System.Windows.Media.SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#00D9FF"));
                BtnVolver.Background = new System.Windows.Media.SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#0F2744"));
                BtnVolver.BorderBrush = new System.Windows.Media.SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#00D9FF"));
                BtnVolver.FontWeight = FontWeights.Bold;

                MessageBox.Show(
                    $"Archivo guardado correctamente:\n{dialog.FileName}\n\n" +
                    "Guárdalo en un lugar seguro.\nPulsa \"Siguiente paso →\" para crear tu usuario.",
                    "Descarga completada",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al guardar el archivo:\n{ex.Message}",
                                "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void CrearZipConJson(string destZipPath)
        {
            // Construir el JSON con los datos de hardware
            var hardwareData = new
            {
                generado = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                sistema_operativo = _os.Trim(),
                placa_base = _motherboard.Trim(),
                procesador = _cpu.Trim(),
                hash_sha256 = _hardwareHash,
                nota = "Este archivo contiene tu identificador de hardware único para Wold Virtual P2P 3D. " +
                       "Guárdalo en un lugar seguro. No contiene datos personales."
            };

            string jsonContent = JsonSerializer.Serialize(hardwareData, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });

            // Guardar copia local en test_user_data/user/
            Directory.CreateDirectory(TestUserDir);
            string localJsonPath = Path.Combine(TestUserDir, "hardware_id.json");
            File.WriteAllText(localJsonPath, jsonContent, Encoding.UTF8);

            // Crear el ZIP — bloques using explícitos para garantizar orden correcto de cierre
            if (File.Exists(destZipPath)) File.Delete(destZipPath);

            using (var zipStream = new FileStream(destZipPath, FileMode.Create, FileAccess.Write))
            {
                using (var archive = new ZipArchive(zipStream, ZipArchiveMode.Create, leaveOpen: false))
                {
                    // ── Entrada 1: hardware_id.json ──
                    {
                        var jsonEntry = archive.CreateEntry("hardware_id.json", CompressionLevel.Optimal);
                        using (var entryStream = jsonEntry.Open())
                        using (var writer = new StreamWriter(entryStream, new UTF8Encoding(false)))
                        {
                            writer.Write(jsonContent);
                            writer.Flush();
                        }
                    }

                    // ── Entrada 2: LEEME.txt ──
                    {
                        var readmeEntry = archive.CreateEntry("LEEME.txt", CompressionLevel.Optimal);
                        using (var readmeStream = readmeEntry.Open())
                        using (var readmeWriter = new StreamWriter(readmeStream, new UTF8Encoding(false)))
                        {
                            readmeWriter.WriteLine("=== WOLD VIRTUAL P2P 3D — Identificador de Hardware ===");
                            readmeWriter.WriteLine();
                            readmeWriter.WriteLine("Este archivo contiene tu identificador único de hardware.");
                            readmeWriter.WriteLine("El hash SHA-256 se genera a partir de tu SO, placa base y procesador.");
                            readmeWriter.WriteLine();
                            readmeWriter.WriteLine("IMPORTANTE: Guarda este archivo en un lugar seguro.");
                            readmeWriter.WriteLine("Lo necesitarás para recuperar el acceso a tu cuenta.");
                            readmeWriter.WriteLine();
                            readmeWriter.WriteLine($"Hash: {_hardwareHash}");
                            readmeWriter.WriteLine($"Generado: {DateTime.UtcNow:yyyy-MM-dd HH:mm:ss} UTC");
                            readmeWriter.Flush();
                        }
                    }
                } // archive se cierra aquí correctamente
            } // zipStream se cierra aquí
        }
    }
}
