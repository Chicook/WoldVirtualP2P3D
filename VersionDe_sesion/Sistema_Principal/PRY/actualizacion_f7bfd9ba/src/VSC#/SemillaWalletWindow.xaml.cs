using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Microsoft.Win32;

namespace Visor3D
{
    public partial class SemillaWalletWindow : Window
    {
        private static readonly string TestUserDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "test_user_data", "user");

        private readonly string _uuid;
        private readonly string _username;
        private readonly string _passwordHash;
        private readonly string _hardwareHash;

        private readonly List<string> _palabras = new();
        private string _seedHash = "";
        private bool _zipDescargado = false;

        public SemillaWalletWindow(string uuid, string username, string passwordHash, string hardwareHash)
        {
            _uuid = uuid;
            _username = username;
            _passwordHash = passwordHash;
            _hardwareHash = hardwareHash;

            InitializeComponent();

            this.Loaded += OnLoaded;
            BtnDescargarSemilla.Click += OnDescargarSemillaClicked;
            BtnContinuar.Click += OnContinuarClicked;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            GenerarFraseSemilla();
            RenderizarPalabras();
        }

        private void GenerarFraseSemilla()
        {
            _palabras.Clear();

            // BIP-39: 12 palabras (128 bits de entropía + checksum), lista oficial de 2048.
            _palabras.AddRange(Visor3D.Seguridad.Bip39.Generate(12));

            string cadenaSemilla = string.Join(" ", _palabras);
            _seedHash = ComputeSha256(cadenaSemilla);
            TxtHashSemilla.Text = _seedHash;
        }

        private void RenderizarPalabras()
        {
            GridPalabras.Children.Clear();

            for (int i = 0; i < _palabras.Count; i++)
            {
                var border = new Border
                {
                    Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#161B26")),
                    BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#1E293B")),
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(6),
                    Margin = new Thickness(4),
                    Padding = new Thickness(8, 6, 8, 6)
                };

                var sp = new StackPanel { Orientation = Orientation.Horizontal };

                var numText = new TextBlock
                {
                    Text = $"#{i + 1:D2} ",
                    Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00D9FF")),
                    FontSize = 11,
                    FontWeight = FontWeights.Bold,
                    VerticalAlignment = VerticalAlignment.Center
                };

                var wordText = new TextBlock
                {
                    Text = _palabras[i],
                    Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E2E8F0")),
                    FontSize = 11.5,
                    FontWeight = FontWeights.SemiBold,
                    VerticalAlignment = VerticalAlignment.Center
                };

                sp.Children.Add(numText);
                sp.Children.Add(wordText);
                border.Child = sp;
                GridPalabras.Children.Add(border);
            }
        }

        private void OnDescargarSemillaClicked(object sender, RoutedEventArgs e)
        {
            var dialog = new SaveFileDialog
            {
                Title = "Guardar Frase Semilla de la Wallet DeFi",
                FileName = $"semilla_wallet_{_seedHash[..8]}",
                DefaultExt = ".zip",
                Filter = "Archivo ZIP|*.zip"
            };

            if (dialog.ShowDialog() != true) return;

            try
            {
                CrearZipSemilla(dialog.FileName);

                _zipDescargado = true;
                TxtEstado.Visibility = Visibility.Visible;

                // Habilitar botón continuar
                BtnContinuar.IsEnabled = true;
                BtnContinuar.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00D9FF"));
                BtnContinuar.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#0F2744"));
                BtnContinuar.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00D9FF"));

                MessageBox.Show(
                    $"Frase semilla guardada correctamente en:\n{dialog.FileName}\n\n" +
                    "IMPORTANTE: No pierdas este archivo. Ahora pasaremos a la verificación de seguridad.",
                    "Semilla Descargada",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al guardar el archivo:\n{ex.Message}",
                                "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void CrearZipSemilla(string destZipPath)
        {
            var semillaData = new
            {
                tipo = "WoldVirtual_DeFi_Seed_v1",
                uuid = _uuid,
                usuario = _username,
                palabras = _palabras.ToArray(),
                hash_semilla = _seedHash,
                hardware_hash = _hardwareHash,
                generado = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                advertencia = "CLAVE PRIVADA MAESTRA DE WALLET DEFI. No comparta este archivo con nadie."
            };

            string jsonContent = JsonSerializer.Serialize(semillaData, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });

            // Guardar copia local en test_user_data/user/
            Directory.CreateDirectory(TestUserDir);
            string localJsonPath = Path.Combine(TestUserDir, "semilla_wallet.json");
            File.WriteAllText(localJsonPath, jsonContent, Encoding.UTF8);

            if (File.Exists(destZipPath)) File.Delete(destZipPath);

            using (var zipStream = new FileStream(destZipPath, FileMode.Create, FileAccess.Write))
            {
                using (var archive = new ZipArchive(zipStream, ZipArchiveMode.Create, leaveOpen: false))
                {
                    // Entrada 1: semilla_wallet.json
                    {
                        var jsonEntry = archive.CreateEntry("semilla_wallet.json", CompressionLevel.Optimal);
                        using (var entryStream = jsonEntry.Open())
                        using (var writer = new StreamWriter(entryStream, new UTF8Encoding(false)))
                        {
                            writer.Write(jsonContent);
                            writer.Flush();
                        }
                    }

                    // Entrada 2: LEEME_WALLET.txt
                    {
                        var readmeEntry = archive.CreateEntry("LEEME_WALLET.txt", CompressionLevel.Optimal);
                        using (var readmeStream = readmeEntry.Open())
                        using (var readmeWriter = new StreamWriter(readmeStream, new UTF8Encoding(false)))
                        {
                            readmeWriter.WriteLine("=== WOLD VIRTUAL P2P 3D — WALLET DEFI FRASE SEMILLA ===");
                            readmeWriter.WriteLine();
                            readmeWriter.WriteLine("Usuario: " + _username);
                            readmeWriter.WriteLine("UUID: " + _uuid);
                            readmeWriter.WriteLine("Hash Semilla: " + _seedHash);
                            readmeWriter.WriteLine("Generado: " + DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss") + " UTC");
                            readmeWriter.WriteLine();
                            readmeWriter.WriteLine("TUS 12 PALABRAS DE RECUPERACIÓN:");
                            for (int i = 0; i < _palabras.Count; i++)
                            {
                                readmeWriter.WriteLine($"  {i + 1:D2}. {_palabras[i]}");
                            }
                            readmeWriter.WriteLine();
                            readmeWriter.WriteLine("IMPORTANTE:");
                            readmeWriter.WriteLine("Estas 12 palabras son el único respaldo de tus criptoactivos en el metaverso P2P.");
                            readmeWriter.WriteLine("Guarda este archivo en un medio seguro y desconectado.");
                            readmeWriter.Flush();
                        }
                    }
                }
            }
        }

        private void OnContinuarClicked(object sender, RoutedEventArgs e)
        {
            if (!_zipDescargado) return;

            var verificarWin = new VerificarSemillaWindow(_uuid, _username, _palabras, _seedHash, _hardwareHash);
            verificarWin.Show();
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
