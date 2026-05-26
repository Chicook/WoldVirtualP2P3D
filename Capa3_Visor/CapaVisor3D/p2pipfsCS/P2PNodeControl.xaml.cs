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
            UpdateGeneralStatus("Inactivo", Brushes.Gray);
        }

        public void UpdateNodeInfo(string nodeId, string simulatedUrl, bool isTunnelActive)
        {
            NodeUrl.Text = simulatedUrl;
            NodeIdText.Text = nodeId; // Asumiendo que tienes un TextBlock llamado NodeIdText en tu XAML
            if (isTunnelActive)
            {
                UpdateGeneralStatus("Activo", Brushes.LimeGreen);
            }
            else
            {
                UpdateGeneralStatus("Inactivo", Brushes.Gray);
            }
        }

        public void UpdateNodeIdAndLink(string nodeId, string link)
        {
            NodeIdText.Text = nodeId; // Asumiendo que tienes un TextBlock llamado NodeIdText en tu XAML
            NodeUrl.Text = link;
        }

        public void UpdateGeneralStatus(string status, Brush color)
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