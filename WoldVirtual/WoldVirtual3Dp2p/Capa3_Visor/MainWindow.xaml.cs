using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Management; // Added for WMI
using System.Net;
using System.Security.Cryptography; // Added for SHA256
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Threading;

using Application = System.Windows.Application;
using Button = System.Windows.Controls.Button;
using Color = System.Windows.Media.Color;
using MessageBox = System.Windows.MessageBox;

namespace VisorSingularity
{
    public partial class MainWindow : Window
    {
        // ── Datos de la Sesión (minimal for now) ──
        private string _username = "";
        private string _wallet = "";
        private string _islandId = "137 : 190.1.0";
        private string _hardwareFingerprint = ""; // Added for hardware fingerprint

        // ── MetaMask HTTP Bridge ──
        private HttpListener? _httpListener;
        private const string MetaMaskBridgeUrl = "http://localhost:8080/";
        private CancellationTokenSource _ctsMetaMaskBridge = new CancellationTokenSource();

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
            // Generate hardware fingerprint on load
            _hardwareFingerprint = GenerateHardwareFingerprint();
            TxtHardwareFingerprint.Text = _hardwareFingerprint;

            // For initial testing, launch Godot directly from here.
            // Later, this will be called after the wizard is completed.
            // await LaunchGodot(_username, _wallet, _islandId, false);
        }

        private void MainWindow_Closed(object? sender, EventArgs e)
        {
            LogDebug("MainWindow Closed.");
            _godotEmbedder.StopGodot(); // Ensure Godot process is stopped
            StopMetaMaskBridge(); // Ensure HTTP listener is stopped
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
                // Create a WindowsFormsHost to host the GodotViewer (HwndHost)
                System.Windows.Forms.Integration.WindowsFormsHost host = new System.Windows.Forms.Integration.WindowsFormsHost();
                GodotViewer godotViewer = new GodotViewer(_godotEmbedder, _godotExecutablePath, _godotProjectPath, godotArgs);
                host.Child = godotViewer;
                GodotHost.Child = host; // Assign the WindowsFormsHost to the WPF element

                LogDebug("GodotViewer assigned to GodotHost.Child.");
                await _godotEmbedder.LaunchAndEmbed(_godotExecutablePath, _godotProjectPath, godotViewer.HostPanel, godotArgs);
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

            if (isNewRegistration)
            {
                // If it's a new registration, we assume the username is already set from TxtUsername.Text
                // and the wallet from TxtWalletAddress.Text during the wizard flow.
                // We just need to update the overlay.
                TxtOverlayUsername.Text = _username;
            }
            else
            {
                // For existing users, we might load their profile data here
                // For now, we'll just use the existing _username
                TxtOverlayUsername.Text = _username;
            }

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
            if (_godotEmbedder.IsGodotRunning && GodotHost.Child is System.Windows.Forms.Integration.WindowsFormsHost host && host.Child is GodotViewer godotViewer)
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
            string recoveryHash = Guid.NewGuid().ToString("D").ToUpper();
            if (GenerateIdentityZip(recoveryHash, false))
            {
                TxtUuid.Text = recoveryHash;
                BtnStep1Next.IsEnabled = true; // ¡Habilitar el botón Siguiente!
                TxtFooterStatus.Text = "Firma Digital guardada. Haz clic en Siguiente para continuar.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));
            }
            else
            {
                TxtFooterStatus.Text = "Debes guardar tu Firma Digital (.zip) para poder continuar.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Yellow);
            }
        }

        private void BtnStep1Next_Click(object sender, RoutedEventArgs e)
        {
            GoToNextStep();
        }

        // ── Identity ZIP Generation ──
        private bool GenerateIdentityZip(string recoveryHash, bool autoSilent)
        {
            try
            {
                string zipFilePath = "";
                string zipFileName = "Wold_Firma_Digital.zip";

                if (autoSilent)
                {
                    // Guardado automático silencioso en Escritorio al arrancar
                    string desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
                    zipFilePath = Path.Combine(desktopPath, zipFileName);
                }
                else
                {
                    // Abrir diálogo nativo de Windows (SaveFileDialog) para elegir directorio y nombre de archivo
                    var saveFileDialog = new Microsoft.Win32.SaveFileDialog();
                    saveFileDialog.Filter = "Archivo ZIP (*.zip)|*.zip";
                    saveFileDialog.FileName = zipFileName;
                    saveFileDialog.Title = "Selecciona el directorio para guardar tu Firma Digital";
                    saveFileDialog.InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);

                    if (saveFileDialog.ShowDialog() == true)
                    {
                        zipFilePath = saveFileDialog.FileName;
                        zipFileName = Path.GetFileName(zipFilePath);
                    }
                    else
                    {
                        TxtFooterStatus.Text = "Exportación de firma cancelada por el usuario.";
                        TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Yellow);
                        return false;
                    }
                }

                // Create a temporary directory for the files to be zipped
                string tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
                Directory.CreateDirectory(tempDir);

                // Create identity.json
                string identityJsonContent = $"{{\"username\": \"{TxtUsername.Text}\", \"hardwareFingerprint\": \"{_hardwareFingerprint}\", \"recoveryHash\": \"{recoveryHash}\"}}";
                File.WriteAllText(Path.Combine(tempDir, "identity.json"), identityJsonContent);

                // Create wallet.json (placeholder for now)
                string walletJsonContent = $"{{\"walletAddress\": \"{_wallet}\"}}";
                File.WriteAllText(Path.Combine(tempDir, "wallet.json"), walletJsonContent);

                // Create the ZIP file
                if (File.Exists(zipFilePath))
                {
                    File.Delete(zipFilePath);
                }
                ZipFile.CreateFromDirectory(tempDir, zipFilePath);

                // Clean up temporary directory
                Directory.Delete(tempDir, true);

                return true;
            }
            catch (Exception ex)
            {
                LogDebug($"Error generating identity ZIP: {ex.Message}");
                MessageBox.Show($"Error al generar la firma digital: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                return false;
            }
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
            GenerateRandomIslandCoordinates();
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

        // ── Island Coordinates Generation ──
        private void GenerateRandomIslandCoordinates()
        {
            Random rand = new Random();
            int x = rand.Next(0, 1000);
            int y = rand.Next(0, 1000);
            int z = rand.Next(0, 1000);
            TxtIslandCoordinates.Text = $"{x}:{y}:{z}";
            TxtIslandName.Text = $"Isla {x}-{y}-{z}";
        }

        // STEP 4 Handlers
        private void BtnEnterMetaverse_Click(object sender, RoutedEventArgs e)
        {
            // Final step, enter the metaverse
            _username = TxtUsername.Text;
            _wallet = TxtWalletAddress.Text;
            // Ensure _islandId is "0:0:0" if not explicitly set or invalid
            _islandId = string.IsNullOrWhiteSpace(TxtIslandCoordinates.Text) ? "0:0:0" : TxtIslandCoordinates.Text;

            EnterDashboard(true); // Assuming new registration for now
        }

        private void BtnStep4Back_Click(object sender, RoutedEventArgs e)
        {
            GoToPreviousStep();
        }

        // ── Hardware Fingerprint Generation ──
        private string GenerateHardwareFingerprint()
        {
            try
            {
                StringBuilder sb = new StringBuilder();

                // Get CPU ID
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT ProcessorId FROM Win32_Processor"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        sb.Append(mo["ProcessorId"]?.ToString());
                    }
                }

                // Get BaseBoard Serial Number
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT SerialNumber FROM Win32_BaseBoard"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        sb.Append(mo["SerialNumber"]?.ToString());
                    }
                }

                // Get OS Serial Number
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT SerialNumber FROM Win32_OperatingSystem"))
                    {
                        foreach (ManagementObject mo in searcher.Get())
                        {
                            sb.Append(mo["SerialNumber"]?.ToString());
                        }
                    }

                // Hash the combined string
                using (SHA256 sha256Hash = SHA256.Create())
                {
                    byte[] bytes = sha256Hash.ComputeHash(Encoding.UTF8.GetBytes(sb.ToString()));
                    StringBuilder builder = new StringBuilder();
                    for (int i = 0; i < bytes.Length; i++)
                    {
                        builder.Append(bytes[i].ToString("x2"));
                    }
                    return builder.ToString().ToUpper();
                }
            }
            catch (Exception ex)
            {
                LogDebug($"Error generating hardware fingerprint: {ex.Message}");
                return "ERROR_FINGERPRINT";
            }
        }

        // ── MetaMask HTTP Bridge ──
        private async Task<string> StartMetaMaskBridge(CancellationToken cancellationToken)
        {
            _httpListener = new HttpListener();
            _httpListener.Prefixes.Add(MetaMaskBridgeUrl);
            _httpListener.Start();
            LogDebug($"HTTP Listener started on {MetaMaskBridgeUrl}");

            // Open browser to initiate MetaMask connection
            string metamaskConnectUrl = $"https://metamask.github.io/metamask-deeplinks/connect?dappUrl={System.Net.WebUtility.UrlEncode(MetaMaskBridgeUrl)}";
            Process.Start(new ProcessStartInfo(metamaskConnectUrl) { UseShellExecute = true });
            LogDebug($"Opened browser for MetaMask connection: {metamaskConnectUrl}");

            try
            {
                while (!cancellationToken.IsCancellationRequested)
                {
                    HttpListenerContext context = await _httpListener.GetContextAsync();
                    LogDebug("Received HTTP request.");

                    // Process the request
                    string responseString = "<html><body><h1>MetaMask Connected!</h1><p>You can close this window.</p></body></html>";
                    byte[] buffer = Encoding.UTF8.GetBytes(responseString);

                    context.Response.ContentLength64 = buffer.Length;
                    context.Response.ContentType = "text/html";
                    context.Response.OutputStream.Write(buffer, 0, buffer.Length);
                    context.Response.OutputStream.Close();

                    // Extract wallet address from query string
                    string? walletAddress = ParseQueryString(context.Request.Url?.Query ?? "").GetValueOrDefault("address");
                    LogDebug($"Wallet address received: {walletAddress}");

                    return walletAddress ?? string.Empty;
                }
            }
            catch (HttpListenerException ex) when (ex.ErrorCode == 995) // Operation canceled by user
            {
                LogDebug("HTTP Listener operation canceled.");
            }
            catch (Exception ex)
            {
                LogDebug($"Error in HTTP Listener: {ex.Message}");
            }
            finally
            {
                StopMetaMaskBridge();
            }
            return string.Empty;
        }

        private void StopMetaMaskBridge()
        {
            if (_httpListener != null && _httpListener.IsListening)
            {
                _ctsMetaMaskBridge.Cancel();
                _httpListener.Stop();
                _httpListener.Close();
                _httpListener = null;
                LogDebug("HTTP Listener stopped.");
            }
        }

        // Helper method to parse query string manually
        private Dictionary<string, string> ParseQueryString(string query)
        {
            Dictionary<string, string> queryParameters = new Dictionary<string, string>();
            if (string.IsNullOrEmpty(query))
            {
                return queryParameters;
            }

            // Remove leading '?' if present
            if (query.StartsWith("?"))
            {
                query = query.Substring(1);
            }

            string[] pairs = query.Split('&');
            foreach (string pair in pairs)
            {
                string[] parts = pair.Split('=');
                if (parts.Length == 2)
                {
                    queryParameters[System.Net.WebUtility.UrlDecode(parts[0])] = System.Net.WebUtility.UrlDecode(parts[1]);
                }
                else if (parts.Length == 1)
                {
                    queryParameters[System.Net.WebUtility.UrlDecode(parts[0])] = string.Empty;
                }
            }
            return queryParameters;
        }
    }
}