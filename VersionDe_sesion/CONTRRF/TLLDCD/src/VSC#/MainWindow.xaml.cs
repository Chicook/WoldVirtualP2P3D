using System;
using System.Windows;
using Visor3D.RedP2P;

namespace Visor3D
{
    /// <summary>
    /// Ventana principal del visor WoldVirtualP2P3D.
    /// Integra el gestor de validación de conexión con LucIA para túneles SSH efímeros.
    /// </summary>
    public partial class MainWindow : Window
    {
        private readonly LucIAValidacionManager? _luciaValidacionManager;
        private readonly string? _initialConnectionUrl;
        private readonly bool _faltaTodo;

        public MainWindow(string? initialConnectionUrl = null, bool faltaTodo = false)
        {
            InitializeComponent();

            _initialConnectionUrl = initialConnectionUrl;
            _faltaTodo = faltaTodo;

            // Iniciar el gestor de validación de conexión con LucIA
            try
            {
                _luciaValidacionManager = new LucIAValidacionManager();
                _luciaValidacionManager.ValidacionCompletada += OnLucIAValidacionCompletada;
                _luciaValidacionManager.Iniciar();

                Console.WriteLine("[MainWindow] Gestor de validación LucIA iniciado");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[MainWindow] Error iniciando gestor LucIA: {ex.Message}");
            }

            // Cargar el resto de la UI
            Loaded += OnLoaded;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            Console.WriteLine("[MainWindow] Ventana cargada");

            // Aquí se inicializaría el resto de componentes:
            // - GodotHwndHost para incrustar el motor Godot
            // - Chat, webcam, voz
            // - UI de construcción
            // - WebNodoService para túneles P2P
        }

        /// <summary>
        /// Manejador del evento de validación completada por LucIA.
        /// </summary>
        private void OnLucIAValidacionCompletada(bool exito, string mensaje)
        {
            Console.WriteLine($"[MainWindow] Validación LucIA completada: exito={exito}, mensaje={mensaje}");

            // Disparar en el hilo UI para actualizar la interfaz si es necesario
            Dispatcher.Invoke(() =>
            {
                if (exito)
                {
                    Console.WriteLine("[MainWindow] Conexión validada exitosamente");
                    // Aquí se podría actualizar la UI para mostrar que la conexión está lista
                }
                else
                {
                    Console.WriteLine($"[MainWindow] Error de validación: {mensaje}");
                    // Aquí se podría mostrar un mensaje de error al usuario
                }
            });
        }

        protected override void OnClosed(EventArgs e)
        {
            // Detener el gestor de validación al cerrar la ventana
            _luciaValidacionManager?.Dispose();
            base.OnClosed(e);
        }
    }
}
