using System;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace VisorSingularity.p2pipfsCS
{
    public partial class P2PNodeControl : UserControl
    {
        public P2PNodeControl()
        {
            InitializeComponent();
            UpdateStatus("Inactivo", Brushes.Gray);
        }

        public void UpdateNodeInfo(string nodeId, string simulatedUrl, bool isTunnelActive)
        {
            NodeUrl.Text = simulatedUrl;
            if (isTunnelActive)
            {
                UpdateStatus("Activo", Brushes.LimeGreen);
            }
            else
            {
                UpdateStatus("Inactivo", Brushes.Gray);
            }
        }

        private void UpdateStatus(string status, Brush color)
        {
            NodeStatus.Text = $"Estado: {status}";
            NodeStatus.Foreground = color;
        }

        private void CopyButton_Click(object sender, RoutedEventArgs e)
        {
            Clipboard.SetText(NodeUrl.Text);
            MessageBox.Show("URL copiada al portapapeles.", "Copiado", MessageBoxButton.OK, MessageBoxImage.Information);
        }

        private void OpenButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                Process.Start(new ProcessStartInfo(NodeUrl.Text) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show($"No se pudo abrir la URL: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }
    }
}