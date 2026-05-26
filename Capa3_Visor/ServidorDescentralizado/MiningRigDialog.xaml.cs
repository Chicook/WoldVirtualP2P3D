using System;
using System.Net;
using System.Net.Sockets;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;

namespace VisorSingularity.ServidorDescentralizado
{
    public partial class MiningRigDialog : Window
    {
        public MiningRigDialog()
        {
            InitializeComponent();
            
            // Configurar eventos
            RigCpuSlider.ValueChanged += RigCpuSlider_ValueChanged;
            
            // Actualizar etiquetas iniciales
            UpdateRigCpuLabel();
        }
        
        private void RigCpuSlider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            UpdateRigCpuLabel();
        }
        
        private void UpdateRigCpuLabel()
        {
            RigCpuLabel.Text = $"{RigCpuSlider.Value:F0}%";
        }
        
        private async void TestButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                string address = RigAddressTextBox.Text.Trim();
                string portText = RigPortTextBox.Text.Trim();
                
                if (string.IsNullOrEmpty(address) || string.IsNullOrEmpty(portText))
                {
                    MessageBox.Show("Por favor ingresa dirección y puerto válidos.", "Error", 
                        MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }
                
                if (!int.TryParse(portText, out int port) || port < 1 || port > 65535)
                {
                    MessageBox.Show("Puerto inválido. Debe ser un número entre 1 y 65535.", "Error", 
                        MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }
                
                // Deshabilitar botones durante la prueba
                TestButton.IsEnabled = false;
                ConnectButton.IsEnabled = false;
                ConnectionInfoLabel.Text = "Probando conexión...";
                
                // Probar conexión en un hilo separado
                bool connectionSuccessful = await Task.Run(() => TestConnection(address, port));
                
                if (connectionSuccessful)
                {
                    ConnectionInfoLabel.Text = "✅ Conexión exitosa. Rig disponible.";
                    ConnectButton.IsEnabled = true;
                }
                else
                {
                    ConnectionInfoLabel.Text = "❌ No se pudo conectar al rig. Verifica dirección y puerto.";
                }
            }
            catch (Exception ex)
            {
                ConnectionInfoLabel.Text = $"❌ Error: {ex.Message}";
            }
            finally
            {
                TestButton.IsEnabled = true;
            }
        }
        
        private bool TestConnection(string address, int port)
        {
            try
            {
                using (var client = new TcpClient())
                {
                    // Intentar conexión con timeout de 5 segundos
                    var result = client.BeginConnect(address, port, null, null);
                    var success = result.AsyncWaitHandle.WaitOne(TimeSpan.FromSeconds(5));
                    
                    if (success)
                    {
                        client.EndConnect(result);
                        return true;
                    }
                    else
                    {
                        client.Close();
                        return false;
                    }
                }
            }
            catch
            {
                return false;
            }
        }
        
        private void ConnectButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                string address = RigAddressTextBox.Text.Trim();
                string portText = RigPortTextBox.Text.Trim();
                
                if (string.IsNullOrEmpty(address) || string.IsNullOrEmpty(portText))
                {
                    MessageBox.Show("Por favor ingresa dirección y puerto válidos.", "Error", 
                        MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }
                
                if (!int.TryParse(portText, out int port) || port < 1 || port > 65535)
                {
                    MessageBox.Show("Puerto inválido. Debe ser un número entre 1 y 65535.", "Error", 
                        MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }
                
                // Obtener configuración del rig
                var rigConfig = new MiningRigConfig
                {
                    Address = address,
                    Port = port,
                    MaxCpuPercent = RigCpuSlider.Value,
                    EnableCpuMining = CpuMiningCheckBox.IsChecked ?? false,
                    EnableGpuMining = GpuMiningCheckBox.IsChecked ?? false,
                    EnableStorageMining = StorageMiningCheckBox.IsChecked ?? false,
                    ConnectionTime = DateTime.UtcNow
                };
                
                // Aquí se integraría con el sistema de minería
                // Por ahora mostramos un mensaje de éxito
                MessageBox.Show(
                    $"✅ Rig vinculado exitosamente:\n\n" +
                    $"Dirección: {rigConfig.Address}:{rigConfig.Port}\n" +
                    $"CPU máximo: {rigConfig.MaxCpuPercent:F0}%\n" +
                    $"Minería CPU: {(rigConfig.EnableCpuMining ? "Activada" : "Desactivada")}\n" +
                    $"Minería GPU: {(rigConfig.EnableGpuMining ? "Activada" : "Desactivada")}\n" +
                    $"Minería Almacenamiento: {(rigConfig.EnableStorageMining ? "Activada" : "Desactivada")}",
                    "Rig Vinculado",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
                
                // Cerrar ventana
                DialogResult = true;
                Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error vinculando rig: {ex.Message}", "Error", 
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
            // Enfocar el campo de dirección
            RigAddressTextBox.Focus();
            RigAddressTextBox.SelectAll();
        }
    }
    
    /// <summary>
    /// Configuración de un rig de minería
    /// </summary>
    public class MiningRigConfig
    {
        public string Address { get; set; } = string.Empty;
        public int Port { get; set; } = 3333;
        public double MaxCpuPercent { get; set; } = 50.0;
        public bool EnableCpuMining { get; set; } = true;
        public bool EnableGpuMining { get; set; } = true;
        public bool EnableStorageMining { get; set; } = false;
        public DateTime ConnectionTime { get; set; }
        
        public string FullAddress => $"{Address}:{Port}";
        
        public override string ToString()
        {
            return $"{FullAddress} (CPU: {MaxCpuPercent:F0}%, " +
                   $"CPU Mining: {EnableCpuMining}, " +
                   $"GPU Mining: {EnableGpuMining}, " +
                   $"Storage Mining: {EnableStorageMining})";
        }
    }
}