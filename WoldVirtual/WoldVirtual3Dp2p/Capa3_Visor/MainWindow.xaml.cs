using System;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Text;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;
using System.Runtime.InteropServices;
using System.Windows.Interop;
using System.Collections.Generic;
using System.Management; // Added for WMI
using System.Security.Cryptography; // Added for SHA256

using Color = System.Windows.Media.Color;
using Button = System.Windows.Controls.Button;
using Application = System.Windows.Application;
using MessageBox = System.Windows.MessageBox;

namespace VisorSingularity
{
    public partial class MainWindow : Window
    {
        // ── Win32: solo lo estrictamente necesario en MainWindow ──
        [DllImport("user32.dll")]
        private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll")]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        // ── Datos de la Sesión (minimal for now) ──
        private string _username = "";
        private string _wallet = "";
        private string _islandId = "137 : 190.1.0";

        // ── Componentes de Ejecución (minimal for now) ──
        private Process? _godotProcess;
        private GodotEmbedder _godotEmbedder; // Added GodotEmbedder instance

        // Placeholder paths - YOU MUST REPLACE THESE WITH YOUR ACTUAL PATHS
        private readonly string _godotExecutablePath = @"C:\Path\To\Your\Godot_v4.2.1-stable_mono_win64.exe"; // Example path
        private readonly string _godotProjectPath = @"D:\WCVcoinMTB\WoldVirtual\WoldVirtual3Dp2p\WoldVirtual"; // Example path to your Godot project

        // ── Debug Logging ──
        private void LogDebug(string message)
        {
            try
            {
                string logPath = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "visor_debug.log");
                System.IO.File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss.fff}] {message}\r\n");
            }
            catch { }
        }

        public MainWindow()
        {
            InitializeComponent();
            _godotEmbedder = new GodotEmbedder(); // Initialize GodotEmbedder
            this.Loaded += MainWindow_Loaded;
            this.Closed += MainWindow_Closed;
        }

        private async void MainWindow_Loaded(object? sender, RoutedEventArgs e)
        {
            LogDebug("MainWindow Loaded.");
            // For initial testing, launch Godot directly from here.
            // Later, this will be called after the wizard is completed.
            await LaunchGodot(_username, _wallet, _islandId, false);
        }

        private void MainWindow_Closed(object? sender, EventArgs e)
        {
            LogDebug("MainWindow Closed.");
            _godotEmbedder.StopGodot(); // Ensure Godot process is stopped
        }

        // Method to launch and embed Godot
        private async Task LaunchGodot(string username, string wallet, string islandId, bool isNewRegistration)
        {
            LogDebug($"LaunchGodot called. User: {username}, Wallet: {wallet}, Island: {islandId}, NewReg: {isNewRegistration}");

            // Hide wizard and show Godot view
            WizardContainer.Visibility = Visibility.Collapsed;
            PanViewportContainer.Visibility = Visibility.Visible;

            // Construct Godot arguments.
            // The "0.0.0" location will be handled by Godot's project logic based on these parameters.
            string godotArgs = $"--user {username} --wallet {wallet} --island {islandId} --newreg {isNewRegistration}";

            try
            {
                GodotHost.Child = new GodotViewer(_godotEmbedder, _godotExecutablePath, _godotProjectPath, godotArgs);
                LogDebug("GodotViewer assigned to GodotHost.Child.");
            }
            catch (Exception ex)
            {
                LogDebug($"Error embedding Godot: {ex.Message}");
                MessageBox.Show($"Error al iniciar Godot: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        // This method will be called after the wizard is completed
        private void EnterDashboard(bool isNewRegistration = false)
        {
            LogDebug($"EnterDashboard called - isNewRegistration: {isNewRegistration}");

            // Hide the wizard
            WizardContainer.Visibility = Visibility.Collapsed;

            // Show Godot view
            PanViewportContainer.Visibility = Visibility.Visible;

            // Launch Godot (this will be handled by LaunchGodot method)
            // For now, we'll just call LaunchGodot directly from MainWindow_Loaded for testing.
            // In a full implementation, this would trigger the Godot launch after wizard completion.
        }

        // Drag window custom
        private void Window_MouseDown(object sender, MouseButtonEventArgs e)
        {
            if (e.ChangedButton == MouseButton.Left)
            {
                this.DragMove();
            }
        }

        // Minimize Button
        private void BtnMinimize_Click(object sender, RoutedEventArgs e)
        {
            this.WindowState = WindowState.Minimized;
        }

        // Close Button
        private void BtnClose_Click(object sender, RoutedEventArgs e)
        {
            // Cleanup logic will go here later
            Application.Current.Shutdown();
        }

        private void PanViewportContainer_SizeChanged(object sender, SizeChangedEventArgs e)
        {
            if (_godotEmbedder.IsGodotRunning && GodotHost.Child is GodotViewer godotViewer)
            {
                // The GodotViewer (HwndHost) handles its own OnRenderSizeChanged,
                // which in turn calls GodotEmbedder.ResizeGodotWindow.
                // So, we just need to ensure the GodotHost (WindowsFormsHost) itself resizes.
                // This is usually handled by WPF layout, but explicit call ensures it.
                godotViewer.InvalidateMeasure();
                godotViewer.UpdateLayout();
            }
        }

        // ── Wizard Navigation ──
        private void GoToNextStep()
        {
            if (WizardTabControl.SelectedIndex < WizardTabControl.Items.Count - 1)
            {
                WizardTabControl.SelectedIndex++;
            }
        }

        private void GoToPreviousStep()
        {
            if (WizardTabControl.SelectedIndex > 0)
            {
                WizardTabControl.SelectedIndex--;
            }
        }

        // STEP 1 Handlers
        private void BtnGenerateSignature_Click(object sender, RoutedEventArgs e)
        {
            // Logic for generating signature will go here
            // For now, just enable the next button
            BtnStep1Next.IsEnabled = true;
            TxtFooterStatus.Text = "Firma Digital generada. Haz clic en Siguiente para continuar.";
            TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));
        }

        private void BtnStep1Next_Click(object sender, RoutedEventArgs e)
        {
            GoToNextStep();
        }

        // STEP 2 Handlers
        private void BtnConnectMetaMask_Click(object sender, RoutedEventArgs e)
        {
            // Logic for connecting MetaMask will go here
            // For now, just enable the next button and set a dummy wallet
            TxtWalletAddress.Text = "0x1234...ABCD"; // Dummy wallet
            BtnStep2Next.IsEnabled = true;
            TxtFooterStatus.Text = "MetaMask conectado. Haz clic en Siguiente para continuar.";
            TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));
        }

        private void BtnStep2Back_Click(object sender, RoutedEventArgs e)
        {
            GoToPreviousStep();
        }

        private void BtnStep2Next_Click(object sender, RoutedEventArgs e)
        {
            GoToNextStep();
        }

        // STEP 3 Handlers
        private void BtnSelectIsland_Click(object sender, RoutedEventArgs e)
        {
            // Logic for selecting random island will go here
            // For now, just set dummy coordinates
            TxtIslandCoordinates.Text = "100:200:50";
            TxtIslandName.Text = "Isla Aleatoria";
            TxtFooterStatus.Text = "Isla seleccionada. Haz clic en Siguiente para continuar.";
            TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));
        }

        private void BtnStep3Back_Click(object sender, RoutedEventArgs e)
        {
            GoToPreviousStep();
        }

        private void BtnStep3Next_Click(object sender, RoutedEventArgs e)
        {
            GoToNextStep();
        }

        // STEP 4 Handlers
        private void BtnEnterMetaverse_Click(object sender, RoutedEventArgs e)
        {
            // Final step, enter the metaverse
            _username = TxtUsername.Text;
            _wallet = TxtWalletAddress.Text;
            _islandId = TxtIslandCoordinates.Text; // Using coordinates as island ID for now

            EnterDashboard(true); // Assuming new registration for now
        }

        private void BtnStep4Back_Click(object sender, RoutedEventArgs e)
        {
            GoToPreviousStep();
        }
    }
}