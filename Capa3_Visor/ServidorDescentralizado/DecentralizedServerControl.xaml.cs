using System;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace VisorSingularity.ServidorDescentralizado
{
    public partial class DecentralizedServerControl : UserControl
    {
        private ResourceMonitor? _resourceMonitor;
        private bool _isMonitoring;
        
        public DecentralizedServerControl()
        {
            InitializeComponent();
            UpdateUI();
            this.Unloaded += OnControlUnloaded;
        }
        
        public void Initialize(ResourceMonitor resourceMonitor)
        {
            if (resourceMonitor == null)
                throw new ArgumentNullException(nameof(resourceMonitor));
            
            _resourceMonitor = resourceMonitor;
            
            // Suscribirse a eventos
            _resourceMonitor.OnMetricsUpdated += OnResourceMetricsUpdated;
            _resourceMonitor.OnResourceLimitExceeded += OnResourceLimitExceeded;
            
            StatusIndicator.Foreground = Brushes.LimeGreen;
            StatusIndicator.Text = "● Listo";
            
            // Iniciar monitoreo si no está ya iniciado
            if (!_isMonitoring)
            {
                _resourceMonitor.StartMonitoring(1000);
                _isMonitoring = true;
            }
        }
        
        private void InitializeResourceMonitor()
        {
            try
            {
                _resourceMonitor = new ResourceMonitor();
                
                // Configurar límites por defecto (total no supera 1GB)
                _resourceMonitor.SetResourceLimits(
                    cpuPercent: 10.0,      // 10% de CPU
                    ramMB: 256,           // 256 MB RAM
                    diskMB: 500,          // 500 MB disco
                    vramMB: 128,          // 128 MB VRAM
                    bandwidthMbps: 10     // 10 Mbps
                );
                
                // Suscribirse a eventos
                _resourceMonitor.OnMetricsUpdated += OnResourceMetricsUpdated;
                _resourceMonitor.OnResourceLimitExceeded += OnResourceLimitExceeded;
                
                StatusIndicator.Foreground = Brushes.LimeGreen;
                StatusIndicator.Text = "● Listo";
            }
            catch (Exception ex)
            {
                StatusIndicator.Foreground = Brushes.Red;
                StatusIndicator.Text = "● Error";
                Debug.WriteLine($"[DecentralizedServerControl] Error inicializando monitor: {ex.Message}");
            }
        }
        
        private void OnResourceMetricsUpdated(ResourceMetrics metrics)
        {
            // Actualizar UI en el hilo de dispatcher
            Dispatcher.Invoke(() =>
            {
                // CPU
                CpuBar.Value = metrics.CpuPercent;
                CpuLabel.Text = $"{metrics.CpuPercent:F1}%/{metrics.CpuLimitPercent}%";
                
                // RAM
                double ramPercent = (double)metrics.RamBytes / metrics.RamLimitBytes * 100;
                RamBar.Value = ramPercent;
                RamLabel.Text = $"{FormatBytes(metrics.RamBytes)}/{FormatBytes(metrics.RamLimitBytes)}";
                
                // Actualizar indicador de estado
                if (metrics.IsCpuLimitExceeded || metrics.IsRamLimitExceeded || 
                    metrics.IsDiskLimitExceeded || metrics.IsVramLimitExceeded || 
                    metrics.IsBandwidthLimitExceeded)
                {
                    StatusIndicator.Foreground = Brushes.Orange;
                    StatusIndicator.Text = "⚠️ Límites";
                }
                else
                {
                    StatusIndicator.Foreground = Brushes.LimeGreen;
                    StatusIndicator.Text = "● Activo";
                }
                
                // Verificar total de recursos (no debe superar 1GB)
                long totalBytes = metrics.TotalUsedBytes;
                if (totalBytes > 1024L * 1024 * 1024) // 1 GB
                {
                    StatusIndicator.Foreground = Brushes.Red;
                    StatusIndicator.Text = "🚫 >1GB";
                }
            });
        }
        
        private void OnResourceLimitExceeded(string resource, double value)
        {
            Dispatcher.Invoke(() =>
            {
                Debug.WriteLine($"[ResourceLimit] {resource} excedió límite: {value}");
                
                // Cambiar color de la barra correspondiente
                switch (resource)
                {
                    case "CPU":
                        CpuBar.Foreground = Brushes.Orange;
                        break;
                    case "RAM":
                        RamBar.Foreground = Brushes.Orange;
                        break;
                }
            });
        }
        
        private void ToggleMonitoring_Checked(object sender, RoutedEventArgs e)
        {
            if (_resourceMonitor == null) return;
            
            try
            {
                _resourceMonitor.StartMonitoring();
                _isMonitoring = true;
                ToggleMonitoring.Content = "Desactivar";
                StatusIndicator.Foreground = Brushes.LimeGreen;
                StatusIndicator.Text = "● Activo";
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[DecentralizedServerControl] Error activando monitoreo: {ex.Message}");
                ToggleMonitoring.IsChecked = false;
            }
        }
        
        private void ToggleMonitoring_Unchecked(object sender, RoutedEventArgs e)
        {
            if (_resourceMonitor == null) return;
            
            try
            {
                _resourceMonitor.StopMonitoring();
                _isMonitoring = false;
                ToggleMonitoring.Content = "Activar";
                StatusIndicator.Foreground = Brushes.Gray;
                StatusIndicator.Text = "● Inactivo";
                
                // Resetear barras
                CpuBar.Value = 0;
                RamBar.Value = 0;
                CpuLabel.Text = "0%";
                RamLabel.Text = "0/256 MB";
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[DecentralizedServerControl] Error desactivando monitoreo: {ex.Message}");
            }
        }
        
        private void SettingsButton_Click(object sender, RoutedEventArgs e)
        {
            // Abrir ventana de configuración de límites
            var settingsDialog = new ResourceSettingsDialog(_resourceMonitor);
            settingsDialog.Owner = Window.GetWindow(this);
            
            if (settingsDialog.ShowDialog() == true)
            {
                // Actualizar UI con nuevos límites
                UpdateUI();
            }
        }
        
        private void MiningRigButton_Click(object sender, RoutedEventArgs e)
        {
            // Abrir ventana para vincular rig de minería
            var miningDialog = new MiningRigDialog();
            miningDialog.Owner = Window.GetWindow(this);
            miningDialog.ShowDialog();
        }
        
        private void IpfsShareButton_Click(object sender, RoutedEventArgs e)
        {
            // Compartir recursos vía IPFS
            ShareResourcesViaIpfs();
        }
        
        private void ShareResourcesViaIpfs()
        {
            try
            {
                if (_resourceMonitor == null) return;
                
                var metrics = _resourceMonitor.GetCurrentMetrics();
                
                // Crear objeto con información de recursos
                var resourceData = new
                {
                    timestamp = metrics.Timestamp,
                    nodeId = Guid.NewGuid().ToString("N").Substring(0, 8),
                    cpu = new { percent = metrics.CpuPercent, limit = metrics.CpuLimitPercent },
                    ram = new { bytes = metrics.RamBytes, limit = metrics.RamLimitBytes },
                    disk = new { bytes = metrics.DiskBytes, limit = metrics.DiskLimitBytes },
                    vram = new { bytes = metrics.VramBytes, limit = metrics.VramLimitBytes },
                    bandwidth = new { bps = metrics.BandwidthBps, limit = metrics.BandwidthLimitBps },
                    totalUsedBytes = metrics.TotalUsedBytes
                };
                
                // Aquí se integraría con el sistema IPFS existente
                // Por ahora solo mostramos un mensaje
                MessageBox.Show(
                    $"Recursos compartidos vía IPFS:\n\n" +
                    $"CPU: {metrics.CpuPercent:F1}%/{metrics.CpuLimitPercent}%\n" +
                    $"RAM: {FormatBytes(metrics.RamBytes)}/{FormatBytes(metrics.RamLimitBytes)}\n" +
                    $"Total: {FormatBytes(metrics.TotalUsedBytes)}",
                    "Compartir vía IPFS",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[IpfsShare] Error compartiendo recursos: {ex.Message}");
                MessageBox.Show($"Error compartiendo recursos: {ex.Message}", "Error", 
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }
        
        private void UpdateUI()
        {
            if (_resourceMonitor == null) return;
            
            var metrics = _resourceMonitor.GetCurrentMetrics();
            
            // Actualizar etiquetas con límites actuales
            CpuLabel.Text = $"0%/{metrics.CpuLimitPercent}%";
            RamLabel.Text = $"0/{FormatBytes(metrics.RamLimitBytes)}";
            
            // Actualizar estado
            if (_isMonitoring)
            {
                StatusIndicator.Foreground = Brushes.LimeGreen;
                StatusIndicator.Text = "● Activo";
            }
            else
            {
                StatusIndicator.Foreground = Brushes.Gray;
                StatusIndicator.Text = "● Inactivo";
            }
        }
        
        private static string FormatBytes(long bytes)
        {
            string[] suffixes = { "B", "KB", "MB", "GB", "TB" };
            int suffixIndex = 0;
            double size = bytes;
            
            while (size >= 1024 && suffixIndex < suffixes.Length - 1)
            {
                size /= 1024;
                suffixIndex++;
            }
            
            return $"{size:F1} {suffixes[suffixIndex]}";
        }
        
        private void OnControlUnloaded(object sender, RoutedEventArgs e)
        {
            // Limpiar recursos
            if (_resourceMonitor != null)
            {
                _resourceMonitor.OnMetricsUpdated -= OnResourceMetricsUpdated;
                _resourceMonitor.OnResourceLimitExceeded -= OnResourceLimitExceeded;
                _resourceMonitor.Dispose();
                _resourceMonitor = null;
            }
        }
    }
}