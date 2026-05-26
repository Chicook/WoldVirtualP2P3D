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
            if (_resourceMonitor == null)
            {
                Debug.WriteLine("[DecentralizedServerControl] ResourceMonitor no inicializado. No se puede abrir el diálogo de configuración.");
                MessageBox.Show("El monitor de recursos no está activo. Por favor, inicie el servidor descentralizado primero.", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }
            
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
            // Lógica para compartir recursos vía IPFS
            Debug.WriteLine("[DecentralizedServerControl] Compartir recursos vía IPFS (no implementado)");
        }
        
        private void UpdateUI()
        {
            // Lógica para actualizar la UI con los datos del monitor
            Debug.WriteLine("[DecentralizedServerControl] Actualizar UI (no implementado)");
        }
        
        private void OnControlUnloaded(object sender, RoutedEventArgs e)
        {
            // Limpiar suscripciones de eventos
            if (_resourceMonitor != null)
            {
                _resourceMonitor.OnMetricsUpdated -= OnResourceMetricsUpdated;
                _resourceMonitor.OnResourceLimitExceeded -= OnResourceLimitExceeded;
                _resourceMonitor.Dispose();
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
    }
}