using System.Windows;

namespace VisorSingularity.ServidorDescentralizado
{
    /// <summary>
    /// Lógica de interacción para MiningRigDialog.xaml
    /// </summary>
    public partial class MiningRigDialog : Window
    {
        public MiningRigDialog()
        {
            InitializeComponent();
        }

        private void LinkButton_Click(object sender, RoutedEventArgs e)
        {
            // Lógica para vincular el rig de minería
            // Aquí se debería validar la entrada de los TextBox (IP, Puerto, API Key)
            // y luego intentar establecer la conexión o guardar la configuración.
            // Por ahora, solo cerraremos el diálogo.
            MessageBox.Show("Rig de minería vinculado (simulado).", "Vincular Rig", MessageBoxButton.OK, MessageBoxImage.Information);
            DialogResult = true;
        }
    }
}
