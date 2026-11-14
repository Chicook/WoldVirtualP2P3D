using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Windows;

namespace Visor3D
{
    public partial class VerificarSemillaWindow : Window
    {
        private readonly string _uuid;
        private readonly string _username;
        private readonly List<string> _palabras;
        private readonly string _seedHash;
        private readonly string _hardwareHash;

        private readonly int _idx1;
        private readonly int _idx2;
        private readonly int _idx3;

        public VerificarSemillaWindow(string uuid, string username, List<string> palabras, string seedHash, string hardwareHash)
        {
            _uuid = uuid;
            _username = username;
            _palabras = palabras;
            _seedHash = seedHash;
            _hardwareHash = hardwareHash;

            InitializeComponent();

            // Elegir 3 posiciones distintas al azar
            var indices = new List<int>();
            while (indices.Count < 3)
            {
                int r = RandomNumberGenerator.GetInt32(_palabras.Count);
                if (!indices.Contains(r)) indices.Add(r);
            }
            indices.Sort();

            _idx1 = indices[0];
            _idx2 = indices[1];
            _idx3 = indices[2];

            this.Loaded += OnLoaded;
            BtnVerificar.Click += OnVerificarClicked;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            LblPalabra1.Text = $"Palabra #{_idx1 + 1:D2}:";
            LblPalabra2.Text = $"Palabra #{_idx2 + 1:D2}:";
            LblPalabra3.Text = $"Palabra #{_idx3 + 1:D2}:";

            TxtPalabra1.Focus();
        }

        private void OnVerificarClicked(object sender, RoutedEventArgs e)
        {
            TxtError.Visibility = Visibility.Collapsed;
            TxtExito.Visibility = Visibility.Collapsed;

            string p1 = TxtPalabra1.Text.Trim().ToLowerInvariant();
            string p2 = TxtPalabra2.Text.Trim().ToLowerInvariant();
            string p3 = TxtPalabra3.Text.Trim().ToLowerInvariant();

            if (string.IsNullOrWhiteSpace(p1) || string.IsNullOrWhiteSpace(p2) || string.IsNullOrWhiteSpace(p3))
            {
                MostrarError("Por favor, rellena las 3 palabras solicitadas.");
                return;
            }

            bool ok1 = p1 == _palabras[_idx1].ToLowerInvariant();
            bool ok2 = p2 == _palabras[_idx2].ToLowerInvariant();
            bool ok3 = p3 == _palabras[_idx3].ToLowerInvariant();

            if (!ok1 || !ok2 || !ok3)
            {
                MostrarError("Una o más palabras no coinciden con tu semilla. Consulta tu archivo semilla_wallet.json e inténtalo de nuevo.");
                return;
            }

            TxtExito.Visibility = Visibility.Visible;
            BtnVerificar.IsEnabled = false;

            // Abrir la ventana para descargar La Llave y cerrar la actual
            var llaveWin = new DescargaLlaveWindow(_uuid, _username, _seedHash, _hardwareHash);
            llaveWin.Show();
            this.Close();
        }

        private void MostrarError(string msg)
        {
            TxtError.Text = msg;
            TxtError.Visibility = Visibility.Visible;
        }
    }
}
