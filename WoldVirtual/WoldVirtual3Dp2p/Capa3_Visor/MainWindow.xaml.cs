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
        private string _password = "";
        private string _wallet = "";
        private string _islandId = "137.190.1.0";
        private string _hardwareFingerprint = ""; // Added for hardware fingerprint

        // ── MetaMask HTTP Bridge ──
        private HttpListener? _httpListener;
        private const string MetaMaskBridgeUrl = "http://localhost:8080/";
        private CancellationTokenSource _ctsMetaMaskBridge = new CancellationTokenSource();

        // ── Componentes de Ejecución (minimal for now) ──
        private GodotEmbedder _godotEmbedder; // Added GodotEmbedder instance

        // Godot paths
        private readonly string _godotExecutablePath = @"C:\Program Files\Godot\Godot.exe"; // Default Godot installation path
        private readonly string _godotProjectPath = @"D:\WCVcoinMTB\WoldVirtual\WoldVirtual3Dp2p\WoldVirtual"; // Path to your Godot project
        
        // Method to find Godot executable
        private string FindGodotExecutable()
        {
            LogDebug("Searching for Godot executable...");
            
            // Check default installation path first
            if (File.Exists(_godotExecutablePath))
            {
                LogDebug($"Found Godot at default location: {_godotExecutablePath}");
                return _godotExecutablePath;
            }
            
            // Common installation locations
            string[] commonPaths = new string[]
            {
                @"C:\Godot\Godot.exe",
                @"C:\Program Files\Godot\Godot.exe",
                @"C:\Program Files (x86)\Godot\Godot.exe",
                @"D:\Godot\Godot.exe",
                @"D:\Program Files\Godot\Godot.exe",
                @"E:\Godot\Godot.exe",
                @"E:\Program Files\Godot\Godot.exe",
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads", "Godot_v4.2.1-stable_mono_win64.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads", "Godot_v4.2.1-stable_win64.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads", "Godot.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Desktop", "Godot.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Documents", "Godot", "Godot.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "AppData", "Local", "Godot", "Godot.exe")
            };
            
            // Common Godot executable names
            string[] godotNames = new string[]
            {
                "Godot.exe",
                "Godot_v4.2.1-stable_mono_win64.exe",
                "Godot_v4.2.1-stable_win64.exe",
                "Godot_v4.2-stable_mono_win64.exe",
                "Godot_v4.2-stable_win64.exe",
                "Godot_v4.1-stable_mono_win64.exe",
                "Godot_v4.1-stable_win64.exe"
            };
            
            // First, check all common paths with the default name
            foreach (string path in commonPaths)
            {
                if (File.Exists(path))
                {
                    LogDebug($"Found Godot at: {path}");
                    return path;
                }
            }
            
            // If not found, search for Godot in common directories with different names
            string[] searchDirectories = new string[]
            {
                @"C:\",
                @"D:\",
                @"E:\",
                Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),
                Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments)
            };
            
            foreach (string directory in searchDirectories)
            {
                if (!Directory.Exists(directory))
                    continue;
                    
                try
                {
                    // Search for Godot executables in this directory and subdirectories (limited depth)
                    foreach (string godotName in godotNames)
                    {
                        string[] foundFiles = Directory.GetFiles(directory, godotName, SearchOption.TopDirectoryOnly);
                        if (foundFiles.Length > 0)
                        {
                            string foundPath = foundFiles[0];
                            LogDebug($"Found Godot at: {foundPath}");
                            return foundPath;
                        }
                    }
                }
                catch (Exception ex)
                {
                    LogDebug($"Error searching in {directory}: {ex.Message}");
                }
            }
            
            // If not found, return the default path (will show error when trying to launch)
            LogDebug("Godot executable not found in common locations");
            return _godotExecutablePath;
        }

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

        private void MainWindow_Loaded(object? sender, RoutedEventArgs e)
        {
            try
            {
                LogDebug("MainWindow Loaded.");
                // Generate hardware fingerprint on load
                _hardwareFingerprint = GenerateHardwareFingerprint();
                
                // Check if TxtHardwareFingerprint exists before setting text
                if (TxtHardwareFingerprint != null)
                {
                    TxtHardwareFingerprint.Text = _hardwareFingerprint;
                }
                else
                {
                    LogDebug("Warning: TxtHardwareFingerprint is null");
                }

                // For initial testing, launch Godot directly from here.
                // Later, this will be called after the wizard is completed.
                // LaunchGodot(_username, _wallet, _islandId, false);
            }
            catch (Exception ex)
            {
                LogDebug($"Error in MainWindow_Loaded: {ex.Message}");
                MessageBox.Show($"Error al cargar la ventana: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void MainWindow_Closed(object? sender, EventArgs e)
        {
            LogDebug("MainWindow Closed.");
            _godotEmbedder.StopGodot(); // Ensure Godot process is stopped
            StopMetaMaskBridge(); // Ensure HTTP listener is stopped
        }

        // Method to launch and embed Godot
        private void LaunchGodot(string username, string wallet, string islandId, bool isNewRegistration)
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
                // Find Godot executable
                string godotPath = FindGodotExecutable();
                
                // Check if Godot project exists
                if (!Directory.Exists(_godotProjectPath))
                {
                    LogDebug($"Godot project not found at: {_godotProjectPath}");
                    MessageBox.Show($"No se encontró el proyecto Godot en: {_godotProjectPath}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }
                
                // Check if Godot executable exists
                if (!File.Exists(godotPath))
                {
                    LogDebug($"Godot executable not found at: {godotPath}");
                    MessageBox.Show($"No se encontró el ejecutable de Godot. Por favor, instale Godot 4.2.1 o superior.", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }

                // Create the GodotViewer control
                GodotViewer godotViewer = new GodotViewer(_godotEmbedder, godotPath, _godotProjectPath, godotArgs);
                GodotHost.Child = godotViewer; // Assign the GodotViewer control to the WindowsFormsHost

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
            if (_godotEmbedder.IsGodotRunning && GodotHost.Child is GodotViewer godotViewer)
            {
                // The GodotViewer control handles resizing in its OnResize method
                // which calls GodotEmbedder.ResizeGodotWindow.
                // We just need to ensure the control is properly sized.
                godotViewer.Invalidate();
                godotViewer.Update();
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
                LogDebug($"[DEBUG-ZIP] Iniciando generación de ZIP. RecoveryHash: {recoveryHash}, AutoSilent: {autoSilent}");
                
                string zipFilePath = "";
                string zipFileName = "Wold_Firma_Digital.zip";

                if (autoSilent)
                {
                    // Guardado automático silencioso en Escritorio al arrancar
                    string desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
                    zipFilePath = Path.Combine(desktopPath, zipFileName);
                    LogDebug($"[DEBUG-ZIP] Modo autoSilent. Ruta: {zipFilePath}");
                }
                else
                {
                    // Abrir diálogo nativo de Windows (SaveFileDialog) para elegir directorio y nombre de archivo
                    var saveFileDialog = new Microsoft.Win32.SaveFileDialog();
                    saveFileDialog.Filter = "Archivo ZIP (*.zip)|*.zip";
                    saveFileDialog.FileName = zipFileName;
                    saveFileDialog.Title = "Selecciona el directorio para guardar tu Firma Digital";
                    saveFileDialog.InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);

                    LogDebug($"[DEBUG-ZIP] Abriendo SaveFileDialog...");
                    if (saveFileDialog.ShowDialog() == true)
                    {
                        zipFilePath = saveFileDialog.FileName;
                        zipFileName = Path.GetFileName(zipFilePath);
                        LogDebug($"[DEBUG-ZIP] Diálogo confirmado. Ruta: {zipFilePath}, Nombre: {zipFileName}");
                    }
                    else
                    {
                        LogDebug($"[DEBUG-ZIP] Diálogo cancelado por el usuario");
                        TxtFooterStatus.Text = "Exportación de firma cancelada por el usuario.";
                        TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Yellow);
                        return false;
                    }
                }

                // Create a temporary directory for the files to be zipped
                string tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
                LogDebug($"[DEBUG-ZIP] Creando directorio temporal: {tempDir}");
                Directory.CreateDirectory(tempDir);
                LogDebug($"[DEBUG-ZIP] Directorio temporal creado exitosamente");

                // Get detailed hardware information
                LogDebug($"[DEBUG-ZIP] Obteniendo información del hardware...");
                string osInfo = GetOperatingSystemInfo();
                string cpuInfo = GetProcessorInfo();
                string mbInfo = GetMotherboardInfo();
                
                LogDebug($"[DEBUG-ZIP] osInfo: {osInfo}");
                LogDebug($"[DEBUG-ZIP] cpuInfo: {cpuInfo}");
                LogDebug($"[DEBUG-ZIP] mbInfo: {mbInfo}");

                // Create identity.json with detailed information
                string usernameEscaped = EscapeJsonString(TxtUsername.Text);
                string passwordEscaped = EscapeJsonString(TxtPassword.Password);
                string walletEscaped = EscapeJsonString(_wallet);
                
                LogDebug($"[DEBUG-ZIP] Valores escapados - Usuario: {usernameEscaped}, Password: [PROTEGIDO], Wallet: {walletEscaped}");
                
                string identityJsonContent = $@"{{
    ""user"": {{
        ""username"": ""{usernameEscaped}"",
        ""password"": ""{passwordEscaped}"",
        ""registrationDate"": ""{DateTime.Now:yyyy-MM-dd HH:mm:ss}"",
        ""uuid"": ""{recoveryHash}""
    }},
    ""hardware"": {{
        ""fingerprint"": ""{_hardwareFingerprint}"",
        ""operatingSystem"": {osInfo},
        ""processor"": {cpuInfo},
        ""motherboard"": {mbInfo}
    }},
    ""wallet"": {{
        ""address"": ""{walletEscaped}"",
        ""connectedDate"": ""{DateTime.Now:yyyy-MM-dd HH:mm:ss}""
    }}
}}";
                
                LogDebug($"[DEBUG-ZIP] JSON generado (primeras 200 chars): {identityJsonContent.Substring(0, Math.Min(200, identityJsonContent.Length))}");
                
                string identityJsonPath = Path.Combine(tempDir, "identity.json");
                LogDebug($"[DEBUG-ZIP] Guardando identity.json en: {identityJsonPath}");
                File.WriteAllText(identityJsonPath, identityJsonContent);
                LogDebug($"[DEBUG-ZIP] identity.json guardado exitosamente");

                // Create hardware_details.json
                string hardwareDetails = $@"{{
    ""hardware_fingerprint"": ""{_hardwareFingerprint}"",
    ""operating_system"": {osInfo},
    ""processor"": {cpuInfo},
    ""motherboard"": {mbInfo}
}}";
                
                string hardwareDetailsPath = Path.Combine(tempDir, "hardware_details.json");
                LogDebug($"[DEBUG-ZIP] Guardando hardware_details.json en: {hardwareDetailsPath}");
                File.WriteAllText(hardwareDetailsPath, hardwareDetails);
                LogDebug($"[DEBUG-ZIP] hardware_details.json guardado exitosamente");

                // Create the ZIP file
                LogDebug($"[DEBUG-ZIP] Creando archivo ZIP en: {zipFilePath}");
                if (File.Exists(zipFilePath))
                {
                    LogDebug($"[DEBUG-ZIP] Archivo ZIP existente, eliminando...");
                    File.Delete(zipFilePath);
                    LogDebug($"[DEBUG-ZIP] Archivo ZIP anterior eliminado");
                }
                
                ZipFile.CreateFromDirectory(tempDir, zipFilePath);
                LogDebug($"[DEBUG-ZIP] Archivo ZIP creado exitosamente. Tamaño: {new FileInfo(zipFilePath).Length} bytes");

                // Clean up temporary directory
                LogDebug($"[DEBUG-ZIP] Limpiando directorio temporal: {tempDir}");
                Directory.Delete(tempDir, true);
                LogDebug($"[DEBUG-ZIP] Directorio temporal eliminado");

                LogDebug($"[DEBUG-ZIP] Generación de ZIP completada exitosamente");
                return true;
            }
            catch (Exception ex)
            {
                LogDebug($"[DEBUG-ZIP] ERROR generando ZIP: {ex.Message}");
                LogDebug($"[DEBUG-ZIP] StackTrace: {ex.StackTrace}");
                MessageBox.Show($"Error al generar la firma digital: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                return false;
            }
        }

        // Get detailed Operating System information
        private string GetOperatingSystemInfo()
        {
            try
            {
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT Caption, Version, SerialNumber, OSArchitecture, BuildNumber FROM Win32_OperatingSystem"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        return $@"{{
            ""name"": ""{mo["Caption"]?.ToString()?.Replace("\"", "\\\"")}"",
            ""version"": ""{mo["Version"]?.ToString()}"",
            ""serial"": ""{mo["SerialNumber"]?.ToString()}"",
            ""architecture"": ""{mo["OSArchitecture"]?.ToString()}"",
            ""build"": ""{mo["BuildNumber"]?.ToString()}""
        }}";
                    }
                }
            }
            catch (Exception ex)
            {
                LogDebug($"Error getting OS info: {ex.Message}");
            }
            return "\"unknown\"";
        }

        // Get detailed Processor information
        private string GetProcessorInfo()
        {
            try
            {
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT Name, ProcessorId, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed FROM Win32_Processor"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        return $@"{{
            ""name"": ""{mo["Name"]?.ToString()?.Replace("\"", "\\\"")}"",
            ""id"": ""{mo["ProcessorId"]?.ToString()}"",
            ""cores"": {mo["NumberOfCores"]?.ToString() ?? "0"},
            ""threads"": {mo["NumberOfLogicalProcessors"]?.ToString() ?? "0"},
            ""maxClockSpeed"": {mo["MaxClockSpeed"]?.ToString() ?? "0"}
        }}";
                    }
                }
            }
            catch (Exception ex)
            {
                LogDebug($"Error getting CPU info: {ex.Message}");
            }
            return "\"unknown\"";
        }

        // Get detailed Motherboard information
        private string GetMotherboardInfo()
        {
            try
            {
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT Manufacturer, Product, SerialNumber, Version FROM Win32_BaseBoard"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        return $@"{{
            ""manufacturer"": ""{mo["Manufacturer"]?.ToString()?.Replace("\"", "\\\"")}"",
            ""product"": ""{mo["Product"]?.ToString()?.Replace("\"", "\\\"")}"",
            ""serial"": ""{mo["SerialNumber"]?.ToString()}"",
            ""version"": ""{mo["Version"]?.ToString()}""
        }}";
                    }
                }
            }
            catch (Exception ex)
            {
                LogDebug($"Error getting motherboard info: {ex.Message}");
            }
            return "\"unknown\"";
        }

        // STEP 2 Handlers
        private async void BtnConnectMetaMask_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                // Disable the button to prevent multiple clicks
                BtnConnectMetaMask.IsEnabled = false;
                TxtFooterStatus.Text = "Iniciando conexión con MetaMask...";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Yellow);
                
                // Show waiting overlay
                PanMetaMaskWaitOverlay.Visibility = Visibility.Visible;
                
                LogDebug("Starting MetaMask connection process...");
                
                // Start HTTP bridge to receive MetaMask response
                string walletAddress = await StartMetaMaskBridge(_ctsMetaMaskBridge.Token);
                
                if (!string.IsNullOrEmpty(walletAddress))
                {
                    // Successfully connected to MetaMask
                    _wallet = walletAddress;
                    TxtWalletAddress.Text = walletAddress;
                    BtnStep2Next.IsEnabled = true;
                    TxtFooterStatus.Text = "MetaMask conectado exitosamente. Haz clic en Siguiente para continuar.";
                    TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));
                    
                    LogDebug($"MetaMask connected successfully. Wallet: {walletAddress}");
                    
                    // Update confirmation display
                    TxtConfirmWallet.Text = walletAddress;
                }
                else
                {
                    // Failed to connect
                    TxtFooterStatus.Text = "Conexión con MetaMask cancelada o fallida.";
                    TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                    MessageBox.Show("No se pudo conectar con MetaMask. Por favor, intenta nuevamente.", "Error de Conexión", MessageBoxButton.OK, MessageBoxImage.Warning);
                    
                    LogDebug("MetaMask connection failed or was canceled.");
                }
            }
            catch (Exception ex)
            {
                LogDebug($"Error connecting to MetaMask: {ex.Message}");
                MessageBox.Show($"Error al conectar con MetaMask: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
            finally
            {
                // Re-enable the button and hide waiting overlay
                BtnConnectMetaMask.IsEnabled = true;
                PanMetaMaskWaitOverlay.Visibility = Visibility.Collapsed;
            }
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
            int x, y, z;
            
            // Generate random coordinates, but avoid "0.0.0" 
            // since that's reserved for the first node
            do
            {
                x = rand.Next(0, 1000);
                y = rand.Next(0, 1000);
                z = rand.Next(0, 1000);
            } while (x == 0 && y == 0 && z == 0);
            
            TxtIslandCoordinates.Text = $"{x}.{y}.{z}";
            TxtIslandName.Text = $"Isla {x}.{y}.{z}";
        }

        // STEP 4 Handlers
        private void BtnEnterMetaverse_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                // Disable button to prevent multiple clicks
                BtnEnterMetaverse.IsEnabled = false;
                TxtFooterStatus.Text = "Entrando al Metaverso...";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Yellow);
                
                // Final step, enter the metaverse
                _username = TxtUsername.Text;
                _password = TxtPassword.Password;
                _wallet = TxtWalletAddress.Text;
                
                // Check if this is the first node (no island coordinates set)
                // If it's the first node, set location to "0.0.0"
                if (string.IsNullOrWhiteSpace(TxtIslandCoordinates.Text) || TxtIslandCoordinates.Text == "0.0.0")
                {
                    _islandId = "0.0.0";
                    TxtIslandCoordinates.Text = "0.0.0";
                    TxtIslandName.Text = "Nodo Principal (0.0.0)";
                    LogDebug("First node detected, setting location to 0.0.0");
                }
                else
                {
                    _islandId = TxtIslandCoordinates.Text;
                }
                
                // Update confirmation displays
                TxtConfirmUsername.Text = _username;
                TxtConfirmWallet.Text = _wallet;
                TxtConfirmIsland.Text = _islandId;
                
                LogDebug($"Entering metaverse with - User: {_username}, Wallet: {_wallet}, Island: {_islandId}");
                
                // Launch Godot with the EscenaPrincipal.tscn
                // The Godot project path should point to the project containing EscenaPrincipal.tscn
                LaunchGodot(_username, _wallet, _islandId, true);
                
                TxtFooterStatus.Text = "¡Bienvenido al Metaverso Wold Virtual!";
                TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));
                
                LogDebug("Successfully entered the metaverse.");
            }
            catch (Exception ex)
            {
                LogDebug($"Error entering metaverse: {ex.Message}");
                MessageBox.Show($"Error al entrar al Metaverso: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                TxtFooterStatus.Text = "Error al entrar al Metaverso.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
            }
            finally
            {
                // Re-enable button
                BtnEnterMetaverse.IsEnabled = true;
            }
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

                // Get Operating System Information
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT Caption, Version, SerialNumber FROM Win32_OperatingSystem"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        sb.Append($"OS:{mo["Caption"]?.ToString()}|");
                        sb.Append($"OSVersion:{mo["Version"]?.ToString()}|");
                        sb.Append($"OSSerial:{mo["SerialNumber"]?.ToString()}|");
                    }
                }

                // Get Processor Information
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT Name, ProcessorId, NumberOfCores, MaxClockSpeed FROM Win32_Processor"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        sb.Append($"CPU:{mo["Name"]?.ToString()}|");
                        sb.Append($"CPUID:{mo["ProcessorId"]?.ToString()}|");
                        sb.Append($"Cores:{mo["NumberOfCores"]?.ToString()}|");
                        sb.Append($"Clock:{mo["MaxClockSpeed"]?.ToString()}|");
                    }
                }

                // Get Motherboard Information
                using (ManagementObjectSearcher searcher = new ManagementObjectSearcher("SELECT Manufacturer, Product, SerialNumber FROM Win32_BaseBoard"))
                {
                    foreach (ManagementObject mo in searcher.Get())
                    {
                        sb.Append($"MBManufacturer:{mo["Manufacturer"]?.ToString()}|");
                        sb.Append($"MBProduct:{mo["Product"]?.ToString()}|");
                        sb.Append($"MBSerial:{mo["SerialNumber"]?.ToString()}|");
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

        // Helper method to escape JSON strings
        private string EscapeJsonString(string input)
        {
            if (string.IsNullOrEmpty(input))
            {
                return "";
            }
            
            StringBuilder sb = new StringBuilder();
            foreach (char c in input)
            {
                switch (c)
                {
                    case '\\':
                        sb.Append("\\\\");
                        break;
                    case '\"':
                        sb.Append("\\\"");
                        break;
                    case '\b':
                        sb.Append("\\b");
                        break;
                    case '\f':
                        sb.Append("\\f");
                        break;
                    case '\n':
                        sb.Append("\\n");
                        break;
                    case '\r':
                        sb.Append("\\r");
                        break;
                    case '\t':
                        sb.Append("\\t");
                        break;
                    default:
                        if (c < 32 || c > 126)
                        {
                            sb.AppendFormat("\\u{0:X4}", (int)c);
                        }
                        else
                        {
                            sb.Append(c);
                        }
                        break;
                }
            }
            return sb.ToString();
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