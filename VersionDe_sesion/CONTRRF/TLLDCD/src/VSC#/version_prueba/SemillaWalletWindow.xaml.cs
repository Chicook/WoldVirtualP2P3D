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
    /// <summary>
    /// Paso 3: Generar y descargar la frase semilla de la Wallet DeFi.
    /// Datos guardados en datos_usuario\ junto al exe.
    /// </summary>
    public partial class SemillaWalletWindow : Window
    {
        private static readonly string UserDataDir =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "datos_usuario");

        private readonly string _uuid;
        private readonly string _username;
        private readonly string _passwordHash;
        private readonly string _hardwareHash;

        private readonly List<string> _palabras = new();
        private string _seedHash = "";
        private bool _zipDescargado = false;

        private static readonly string[] Diccionario = new[]
        {
            "alpha","beacon","crypto","delta","echo","falcon","galaxy","horizon",
            "impact","jupiter","kinetic","lunar","matrix","nexus","orbit","pulse",
            "quantum","radar","stellar","titan","unity","vortex","zenith","crystal",
            "dragon","energy","fusion","glory","harbor","island","jungle","karma",
            "legend","meteor","nature","oasis","planet","quest","rocket","spark",
            "thunder","utopia","vector","wisdom","xenon","yield","zero","anchor",
            "blade","comet","dynamo","element","flux","gravity","halo","infinity",
            "journey","knight","laser","magma","nova","omega","plasma","prism"
        };

        public SemillaWalletWindow(string uuid, string username, string passwordHash, string hardwareHash)
        {
            _uuid = uuid; _username = username;
            _passwordHash = passwordHash; _hardwareHash = hardwareHash;
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
            var usados = new HashSet<int>();
            while (_palabras.Count < 12)
            {
                int i = RandomNumberGenerator.GetInt32(Diccionario.Length);
                if (usados.Add(i)) _palabras.Add(Diccionario[i]);
            }
            _seedHash = ComputeSha256(string.Join(" ", _palabras));
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
                    BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(6),
                    Margin = new Thickness(4), Padding = new Thickness(8, 6, 8, 6)
                };
                var sp = new StackPanel { Orientation = Orientation.Horizontal };
                sp.Children.Add(new TextBlock
                {
                    Text = $"#{i+1:D2} ", FontSize = 11, FontWeight = FontWeights.Bold,
                    Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00D9FF")),
                    VerticalAlignment = VerticalAlignment.Center
                });
                sp.Children.Add(new TextBlock
                {
                    Text = _palabras[i], FontSize = 11.5, FontWeight = FontWeights.SemiBold,
                    Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#E2E8F0")),
                    VerticalAlignment = VerticalAlignment.Center
                });
                border.Child = sp;
                GridPalabras.Children.Add(border);
            }
        }

        private void OnDescargarSemillaClicked(object sender, RoutedEventArgs e)
        {
            var dialog = new SaveFileDialog
            {
                Title = "Guardar Frase Semilla — pon esto donde TU lo controles",
                FileName = $"semilla_wallet_{_seedHash[..8]}",
                DefaultExt = ".zip", Filter = "Archivo ZIP|*.zip"
            };
            if (dialog.ShowDialog() != true) return;

            try
            {
                CrearZipSemilla(dialog.FileName);
                _zipDescargado = true;
                TxtEstado.Visibility = Visibility.Visible;
                BtnContinuar.IsEnabled = true;
                BtnContinuar.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00D9FF"));
                BtnContinuar.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#0F2744"));
                BtnContinuar.BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00D9FF"));

                MessageBox.Show(
                    $"Semilla guardada en:\n{dialog.FileName}\n\n" +
                    "IMPORTANTE: Guarda este archivo en un lugar SOLO tuyo (USB, caja fuerte digital).\n" +
                    "Una copia de seguridad local queda en datos_usuario\\ junto al visor.",
                    "Semilla Descargada", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error:\n{ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void CrearZipSemilla(string destZipPath)
        {
            var semillaData = new
            {
                tipo = "WoldVirtual_DeFi_Seed_v1", uuid = _uuid, usuario = _username,
                palabras = _palabras.ToArray(), hash_semilla = _seedHash,
                hardware_hash = _hardwareHash,
                generado = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                advertencia = "CLAVE PRIVADA MAESTRA. No comparta este archivo con nadie."
            };

            string json = JsonSerializer.Serialize(semillaData, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });

            // Copia en datos_usuario\ junto al exe
            Directory.CreateDirectory(UserDataDir);
            File.WriteAllText(Path.Combine(UserDataDir, "semilla_wallet.json"), json, Encoding.UTF8);

            if (File.Exists(destZipPath)) File.Delete(destZipPath);
            using var zs = new FileStream(destZipPath, FileMode.Create, FileAccess.Write);
            using var ar = new ZipArchive(zs, ZipArchiveMode.Create, leaveOpen: false);

            var je = ar.CreateEntry("semilla_wallet.json", CompressionLevel.Optimal);
            using (var s = je.Open()) using (var w = new StreamWriter(s, new UTF8Encoding(false)))
            { w.Write(json); w.Flush(); }

            var re = ar.CreateEntry("LEEME_WALLET.txt", CompressionLevel.Optimal);
            using (var s = re.Open()) using (var w = new StreamWriter(s, new UTF8Encoding(false)))
            {
                w.WriteLine("=== WOLD VIRTUAL P2P 3D - WALLET DEFI FRASE SEMILLA ===");
                w.WriteLine($"Usuario: {_username}  |  UUID: {_uuid}");
                w.WriteLine($"Hash Semilla: {_seedHash}");
                w.WriteLine($"Generado: {DateTime.UtcNow:yyyy-MM-dd HH:mm:ss} UTC");
                w.WriteLine(); w.WriteLine("TUS 12 PALABRAS DE RECUPERACION:");
                for (int i = 0; i < _palabras.Count; i++) w.WriteLine($"  {i+1:D2}. {_palabras[i]}");
                w.WriteLine(); w.WriteLine("Guarda este archivo en un medio seguro y SOLO tuyo.");
                w.Flush();
            }
        }

        private void OnContinuarClicked(object sender, RoutedEventArgs e)
        {
            if (!_zipDescargado) return;
            new VerificarSemillaWindow(_uuid, _username, _palabras, _seedHash, _hardwareHash).Show();
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
