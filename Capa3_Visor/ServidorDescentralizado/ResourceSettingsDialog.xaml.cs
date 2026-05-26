using System;
using System.Windows;
using System.Windows.Controls;

namespace VisorSingularity.ServidorDescentralizado
{
    public partial class ResourceSettingsDialog : Window
    {
        private readonly ResourceMonitor _resourceMonitor;
        
        // Valores actuales
        private double _cpuLimitPercent;
        private long _ramLimitMB;
        private long _diskLimitMB;
        private long _vramLimitMB;
        private long _bandwidthLimitMbps;
        
        public ResourceSettingsDialog(ResourceMonitor resourceMonitor)
        {
            InitializeComponent();
            _resourceMonitor = resourceMonitor;
            
            // Cargar valores actuales
            LoadCurrentSettings();
            
            // Configurar eventos de sliders
            CpuSlider.ValueChanged += Slider_ValueChanged;
            RamSlider.ValueChanged += Slider_ValueChanged;
            DiskSlider.ValueChanged += Slider_ValueChanged;
            VramSlider.ValueChanged += Slider_ValueChanged;
            BandwidthSlider.ValueChanged += Slider_ValueChanged;
            
            // Actualizar resumen inicial
            UpdateSummary();
        }
        
        private void LoadCurrentSettings()
        {
            if (_resourceMonitor == null) return;
            
            // Obtener límites actuales
            _cpuLimitPercent = _resourceMonitor.CpuLimitPercent;
            _ramLimitMB = _resourceMonitor.RamLimitBytes / (1024 * 1024);
            _diskLimitMB = _resourceMonitor.DiskLimitBytes / (1024 * 1024);
            _vramLimitMB = _resourceMonitor.VramLimitBytes / (1024 * 1024);
            _bandwidthLimitMbps = _resourceMonitor.BandwidthLimitBps / (1024 * 1024);
            
            // Configurar sliders
            CpuSlider.Value = _cpuLimitPercent;
            RamSlider.Value = _ramLimitMB;
            DiskSlider.Value = _diskLimitMB;
            VramSlider.Value = _vramLimitMB;
            BandwidthSlider.Value = _bandwidthLimitMbps;
            
            // Actualizar etiquetas
            UpdateSliderLabels();
        }
        
        private void UpdateSliderLabels()
        {
            CpuValueLabel.Text = $"{CpuSlider.Value:F0}%";
            RamValueLabel.Text = $"{RamSlider.Value:F0} MB";
            DiskValueLabel.Text = $"{DiskSlider.Value:F0} MB";
            VramValueLabel.Text = $"{VramSlider.Value:F0} MB";
            BandwidthValueLabel.Text = $"{BandwidthSlider.Value:F0} Mbps";
        }
        
        private void Slider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            UpdateSliderLabels();
            UpdateSummary();
        }
        
        private void UpdateSummary()
        {
            // Calcular total estimado en MB
            long totalMB = (long)RamSlider.Value + (long)DiskSlider.Value + (long)VramSlider.Value;
            
            // Actualizar etiqueta
            TotalSummaryLabel.Text = $"{totalMB} MB";
            
            // Verificar límite de 1GB (1024 MB)
            if (totalMB > 1024)
            {
                LimitWarningLabel.Text = $"⚠️ ADVERTENCIA: Total ({totalMB} MB) supera 1GB. Ajusta los límites.";
                SaveButton.IsEnabled = false;
                SaveButton.Background = System.Windows.Media.Brushes.Gray;
            }
            else if (totalMB > 900)
            {
                LimitWarningLabel.Text = $"⚠️ Cerca del límite: {totalMB} MB de 1024 MB disponibles.";
                SaveButton.IsEnabled = true;
                SaveButton.Background = System.Windows.Media.Brushes.Orange;
            }
            else
            {
                LimitWarningLabel.Text = $"✅ Dentro del límite: {totalMB} MB de 1024 MB disponibles.";
                SaveButton.IsEnabled = true;
                SaveButton.Background = System.Windows.Media.Brushes.Green;
            }
            
            // Información adicional
            if (totalMB <= 512)
            {
                LimitWarningLabel.Text += "\n💡 Puedes aumentar los límites si necesitas más rendimiento.";
            }
        }
        
        private void SaveButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_resourceMonitor == null)
                {
                    MessageBox.Show("Error: Monitor de recursos no disponible.", "Error", 
                        MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }
                
                // Aplicar nuevos límites
                _resourceMonitor.SetResourceLimits(
                    cpuPercent: CpuSlider.Value,
                    ramMB: (long)RamSlider.Value,
                    diskMB: (long)DiskSlider.Value,
                    vramMB: (long)VramSlider.Value,
                    bandwidthMbps: (long)BandwidthSlider.Value
                );
                
                // Cerrar con éxito
                DialogResult = true;
                Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error guardando configuración: {ex.Message}", "Error", 
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }
        
        private void CancelButton_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }
        
        private void Window_Loaded(object sender, RoutedEventArgs e)
        {
            // Enfocar el botón de guardar
            SaveButton.Focus();
        }
    }
}