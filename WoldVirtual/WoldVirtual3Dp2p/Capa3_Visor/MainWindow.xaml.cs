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

        // ── Datos de la Sesión ──
        private HardwareFingerprint _fingerprint = null!;
        private DatabaseManager _db = null!;
        private int _currentStep = 1;
        private bool _isClosing = false;
        private bool _hasAccount = false;

        private string _username = "";
        private string _wallet = "";
        private string _islandId = "137 : 190.1.0";

        // ── Componentes de Ejecución ──
        private HttpListener? _httpListener;
        private Process? _godotProcess;
        private GodotViewer? _viewer;

        // ── Debug Logging ──
        private void LogDebug(string message)
        {
            try
            {
                string logPath = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "visor_debug_overlap.log");
                System.IO.File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss.fff}] {message}\r\n");
            }
            catch { }
        }

        public MainWindow()
        {
            LogDebug("MainWindow constructor started");
            InitializeComponent();
            LogDebug("InitializeComponent completed");
            this.Loaded += MainWindow_Loaded;
            this.Closed += MainWindow_Closed;

            // Configurar visibilidad inicial
            WizardContainer.Visibility = Visibility.Visible;
            PanViewportContainer.Visibility = Visibility.Collapsed;
            PanIpfsBar.Visibility = Visibility.Collapsed;
            PanMetricsBar.Visibility = Visibility.Collapsed;
            PanLeftSidebar.Visibility = Visibility.Collapsed;
            PanRightSidebar.Visibility = Visibility.Collapsed;

            // Foco a Godot al hacer clic en el área 3D
            GodotPlaceholder.MouseDown += (s, e) => _viewer?.FocusGodot();

            // Sincronizar posición del overlay sin bordes de Godot
            this.LocationChanged += (s, e) => _viewer?.UpdatePosition(GodotPlaceholder, this);
            this.SizeChanged += (s, e) => _viewer?.UpdatePosition(GodotPlaceholder, this);
            this.StateChanged += (s, e) => _viewer?.UpdatePosition(GodotPlaceholder, this);
            this.Activated += (s, e) => _viewer?.UpdatePosition(GodotPlaceholder, this);
            
            GodotPlaceholder.SizeChanged += (s, e) => _viewer?.UpdatePosition(GodotPlaceholder, this);
            GodotPlaceholder.LayoutUpdated += (s, e) => _viewer?.UpdatePosition(GodotPlaceholder, this);
        }

        private void MainWindow_Loaded(object? sender, RoutedEventArgs e)
        {
            LogDebug("MainWindow_Loaded started");
            try
            {
                // Inicializar Helpers
                _db = new DatabaseManager();
                _fingerprint = new HardwareFingerprint();
                LogDebug($"Hardware fingerprint: {_fingerprint.UniqueHash}");
                LogDebug($"Window dimensions on load: Width={Width}, Height={Height}, ActualWidth={ActualWidth}, ActualHeight={ActualHeight}");
                LogDebug($"GodotPlaceholder dimensions on load: ActualWidth={GodotPlaceholder.ActualWidth}, ActualHeight={GodotPlaceholder.ActualHeight}");

                // Cargar datos de Telemetría de Hardware
                TxtCpuId.Text = $"ID PROCESADOR: {_fingerprint.ProcessorId}";
                TxtBoardId.Text = $"PLACA BASE: {_fingerprint.MotherboardId}";
                TxtOsId.Text = $"ID SISTEMA OPERATIVO: {_fingerprint.OsId}";
                TxtHwHash.Text = _fingerprint.UniqueHash.ToUpper();
                TxtFooterHwSignature.Text = $"ENLACE SEGURO FINGERPRINT: {_fingerprint.UniqueHash.Substring(0, 16).ToUpper()}";

                // Iniciar el HTTP Bridge en puerto 8080 para MetaMask
                StartHttpBridge();

                // Comprobar si esta máquina ya tiene una cuenta registrada
                _hasAccount = _db.CheckHardwareExists(_fingerprint.UniqueHash, out string? registeredUser);
                if (_hasAccount && !string.IsNullOrEmpty(registeredUser))
                {
                    _username = registeredUser;
                    TxtStep1LoggedUser.Text = _username.ToUpper();
                    PanStep1Login.Visibility = Visibility.Visible;
                    BtnStep1Action.Content = "INICIAR SESIÓN / ACCEDER AL METAVERSO";
                    BtnStep1Action.IsEnabled = true; // Habilitado para Login directo
                    TxtFooterStatus.Text = $"Identidad '{_username}' detectada de forma segura en este ordenador.";
                }
                else
                {
                    PanStep1Login.Visibility = Visibility.Collapsed;
                    BtnStep1Action.Content = "VINCULAR MAQUINA / SIGUIENTE";
                    BtnStep1Action.IsEnabled = false; // Deshabilitado hasta que descargue la firma
                    TxtFooterStatus.Text = "Por favor, genera y guarda tu Firma Digital (.zip) primero para continuar.";
                }
            }
            catch (Exception ex)
            {
                TxtFooterStatus.Text = $"Error al cargar inicializadores: {ex.Message}";
            }
        }

        private void MainWindow_Closed(object? sender, EventArgs e)
        {
            LogDebug("MainWindow_Closed called - forcing exit");
            _isClosing = true;
            Cleanup();
            Environment.Exit(0);
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
            LogDebug("BtnClose_Click called - forcing exit");
            _isClosing = true;
            Cleanup();
            Environment.Exit(0);
        }

        // ───── WIZARD ACTIONS & NAVIGATION ─────

        private void ShowStep(int step)
        {
            _currentStep = step;

            // Asegurar que el WizardContainer esté visible cuando mostramos pasos
            WizardContainer.Visibility = Visibility.Visible;

            Step1_PC.Visibility = (step == 1) ? Visibility.Visible : Visibility.Collapsed;
            Step2_User.Visibility = (step == 2) ? Visibility.Visible : Visibility.Collapsed;
            Step3_Metamask.Visibility = (step == 3) ? Visibility.Visible : Visibility.Collapsed;
            Step4_Island.Visibility = (step == 4) ? Visibility.Visible : Visibility.Collapsed;

            switch (step)
            {
                case 1:
                    TxtFooterStatus.Text = "Paso 1: Vinculación de firma de hardware local.";
                    break;
                case 2:
                    TxtFooterStatus.Text = "Paso 2: Registro de datos de usuario y UUID criptográfico.";
                    break;
                case 3:
                    TxtFooterStatus.Text = "Paso 3: Enlace e inicio de sesión de MetaMask DeFi Wallet.";
                    break;
                case 4:
                    TxtFooterStatus.Text = "Paso 4: Selección de coordenadas espaciales para el teletransporte.";
                    break;
            }
        }

        // Helper para Generar Backup de Identidad .ZIP con JSON dentro
        private bool GenerateIdentityZip(string recoveryHash, bool autoSilent = false)
        {
            try
            {
                // 1. Estructurar el contenido JSON con formato estético indentado
                string jsonContent = System.Text.Json.JsonSerializer.Serialize(new
                {
                    FirmaDigital = _fingerprint.UniqueHash,
                    HashRecuperacion = recoveryHash,
                    DetalleCPU = _fingerprint.ProcessorId,
                    DetallePlacaBase = _fingerprint.MotherboardId,
                    DetalleOS = _fingerprint.OsId,
                    FechaVinculacion = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")
                }, new System.Text.Json.JsonSerializerOptions { WriteIndented = true });

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

                // 3. Crear el archivo ZIP y empaquetar el JSON dentro
                using (var fileStream = new FileStream(zipFilePath, FileMode.Create))
                {
                    using (var archive = new ZipArchive(fileStream, ZipArchiveMode.Create))
                    {
                        var zipEntry = archive.CreateEntry("identidad_wold.json");
                        using (var writer = new StreamWriter(zipEntry.Open()))
                        {
                            writer.Write(jsonContent);
                        }
                    }
                }

                // 4. Mostrar alerta visual de confirmación con ruta completa
                MessageBox.Show(
                    $"¡FIRMA DIGITAL Y HASH DE RECUPERACIÓN GUARDADOS CON ÉXITO!\n\n" +
                    $"Se ha creado y guardado tu llave cuántica de identidad segura en:\n" +
                    $"📄 {zipFilePath}\n\n" +
                    $"IMPORTANTE: Conserva este archivo .zip. Contiene tu firma digital de hardware única:\n" +
                    $"{_fingerprint.UniqueHash.ToUpper()}\n\n" +
                    $"Tu llave de recuperación cuántica es:\n" +
                    $"{recoveryHash}",
                    "Criptografía WOLD VIRTUAL P2P",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information
                );

                TxtFooterStatus.Text = $"Backup de Firma guardado en: {zipFileName}";
                TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));
                return true;
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al generar el backup ZIP de identidad: {ex.Message}", "Error Criptográfico", MessageBoxButton.OK, MessageBoxImage.Error);
                return false;
            }
        }

        // STEP 1 Action: Hardware link OR Login
        private void BtnStep1Next_Click(object sender, RoutedEventArgs e)
        {
            if (_hasAccount)
            {
                // Iniciar Sesión Directo con Contraseña
                string pass = TxtStep1Password.Password.Trim();
                if (string.IsNullOrEmpty(pass))
                {
                    TxtFooterStatus.Text = "Error: Por favor introduce tu contraseña de identidad.";
                    TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                    return;
                }

                if (_db.ValidateLogin(_username, pass, _fingerprint.UniqueHash, out string? islandId, out string? wallet))
                {
                    _islandId = islandId ?? "137 : 190.1.0";
                    _wallet = wallet ?? "No Wallet Address";

                    // ROTACIÓN CRIPTOGRÁFICA EN CALIENTE: Generar nueva firma única y exportar ZIP
                    string newRecoveryHash = Guid.NewGuid().ToString("D").ToUpper();
                    _db.UpdateUserId(_username, newRecoveryHash);
                    GenerateIdentityZip(newRecoveryHash);

                    TxtFooterStatus.Text = "¡Firma de sesión actualizada y autenticación correcta! Cargando metaverso...";
                    TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));

                    EnterDashboard();
                }
                else
                {
                    TxtFooterStatus.Text = "Error: Contraseña incorrecta para esta firma de hardware.";
                    TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                }
            }
            else
            {
                // Avanzar al Registro (Sin volver a generar la firma, ya que la descargó antes!)
                TxtFooterStatus.Text = "Firma de hardware vinculada con éxito. Crea tu usuario.";
                ShowStep(2);
            }
        }

        // STEP 1 Action: Botón de Descarga Directa/Manual de la Firma Digital ZIP
        private void BtnDownloadZip_Click(object sender, RoutedEventArgs e)
        {
            string recoveryHash = Guid.NewGuid().ToString("D").ToUpper();
            if (GenerateIdentityZip(recoveryHash, false))
            {
                TxtUuid.Text = recoveryHash;
                BtnStep1Action.IsEnabled = true; // ¡Habilitar el botón Siguiente!
                TxtFooterStatus.Text = "Firma Digital guardada. Haz clic en Siguiente para continuar.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));
            }
            else
            {
                TxtFooterStatus.Text = "Debes guardar tu Firma Digital (.zip) para poder continuar.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Yellow);
            }
        }

        // STEP 2 Action: Generate Account UUID
        private void BtnGenerateUuid_Click(object sender, RoutedEventArgs e)
        {
            TxtUuid.Text = Guid.NewGuid().ToString("D").ToUpper();
            TxtFooterStatus.Text = "UUID de cuenta generado con éxito para la firma digital.";
        }

        // STEP 2 Action: Complete credentials registration
        private void BtnStep2Next_Click(object sender, RoutedEventArgs e)
        {
            string user = TxtRegUser.Text.Trim();
            string pass = TxtRegPass.Password.Trim();
            string passRepeat = TxtRegPassRepeat.Password.Trim();

            if (string.IsNullOrEmpty(user) || string.IsNullOrEmpty(pass))
            {
                TxtFooterStatus.Text = "Error: Rellena los campos de usuario y contraseña.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                return;
            }

            if (pass != passRepeat)
            {
                TxtFooterStatus.Text = "Error: Las contraseñas de identidad no coinciden.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                return;
            }

            if (TxtUuid.Text.Contains("Haz clic"))
            {
                TxtFooterStatus.Text = "Error: Es obligatorio generar un UUID de validación.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                return;
            }

            _username = user;
            TxtFooterStatus.Text = "Datos de identidad pre-registrados. Ahora enlaza tu MetaMask.";
            TxtFooterStatus.Foreground = new SolidColorBrush(Colors.White);
            ShowStep(3);
        }



        // STEP 3 Action: Open browser for real Metamask bridge
        private void BtnValidateRealMetamask_Click(object sender, RoutedEventArgs e)
        {
            PanWaitHttp.Visibility = Visibility.Visible;
            TxtFooterStatus.Text = "Esperando la firma DeFi en la pasarela HTTP local...";
            OpenMetamaskBrowser();
        }

        // Open Metamask HTTP portal
        private void OpenMetamaskBrowser()
        {
            try
            {
                string url = $"http://localhost:8080/?user={Uri.EscapeDataString(_username)}&islandId={Uri.EscapeDataString(_islandId)}";
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show($"No se pudo abrir el navegador automáticamente: {ex.Message}", "HTTP Bridge", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void GenerateUniqueIslandCoordinates()
        {
            int hash = _username.GetHashCode();
            int x = Math.Abs(hash % 900) + 100; // Coordenada X entre 100 y 1000
            int z = Math.Abs((hash / 1000) % 900) + 100; // Coordenada Z entre 100 y 1000
            string generatedIsland = $"{x} : {z}.1.0";
            TxtIslandCoordinates.Text = generatedIsland;
            _islandId = generatedIsland;
        }



        // STEP 4 Action: Finalize and Launch
        private void BtnFinalizeRegister_Click(object sender, RoutedEventArgs e)
        {
            string island = TxtIslandCoordinates.Text.Trim();
            if (string.IsNullOrEmpty(island))
            {
                TxtFooterStatus.Text = "Error: Por favor indica las coordenadas espaciales.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                return;
            }

            _islandId = island;

            try
            {
                // Registrar definitivamente en SQLite local
                _db.RegisterUser(_username, TxtRegPass.Password.Trim(), _fingerprint.UniqueHash, _islandId);
                _db.UpdateWallet(_username, _wallet);

                TxtFooterStatus.Text = "¡Usuario registrado con éxito en base de datos! Cargando creador de avatar...";
                TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));

                EnterDashboard(isNewRegistration: true);
            }
            catch (Exception ex)
            {
                TxtFooterStatus.Text = $"Error al guardar registro: {ex.Message}";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
            }
        }

        // ───── DIALOG HTTP WAIT WINDOW BUTTONS ─────
        private void BtnOpenBrowserAgain_Click(object sender, RoutedEventArgs e)
        {
            OpenMetamaskBrowser();
        }



        // ───── CORE DASHBOARD TRANSITION ─────
        private void EnterDashboard(bool isNewRegistration = false)
        {
            LogDebug($"EnterDashboard called - isNewRegistration: {isNewRegistration}");

            // Ocultar el wizard
            WizardContainer.Visibility = Visibility.Collapsed;

            // Mostrar los paneles tácticos del visor premium
            PanIpfsBar.Visibility = Visibility.Visible;
            PanMetricsBar.Visibility = Visibility.Visible;
            PanLeftSidebar.Visibility = Visibility.Visible;
            PanRightSidebar.Visibility = Visibility.Visible;

            // Actualizar la dirección IPFS del nodo
            TxtIpfsAddress.Text = $"http://localhost:8080/node/{_username.ToLower()}.ipfs";

            // Rellenar datos del sidebar
            TxtSidebarUsername.Text = _username.ToUpper();
            TxtSidebarWallet.Text = _wallet.Length > 16
                ? _wallet.Substring(0, 8) + "..." + _wallet.Substring(_wallet.Length - 6)
                : _wallet;
            TxtSidebarIsland.Text = _islandId;

            // Cargar Lista de Islas del Teletransporte P2P
            LoadTeleportIslandsList();

            // Mostrar el contenedor de Godot
            PanViewportContainer.Visibility = Visibility.Visible;

            // Lanzar Godot e incrustar via --wid
            LaunchGodot(_wallet, _username, _islandId, isNewRegistration);
        }

        private void LoadTeleportIslandsList()
        {
            StackIslandsList.Children.Clear();
            var list = _db.GetAllUsersAndIslands();

            // Asegurar que al menos existe una isla si el nodo está vacío
            if (list.Count == 0)
            {
                list.Add((_username, _islandId));
            }

            int idx = 0;
            foreach (var item in list)
            {
                string isCurrent = item.Username.Equals(_username, StringComparison.OrdinalIgnoreCase) ? " ⬢ [Mía]" : "";
                string btnText = $"⬢ {item.Username.ToUpper()}{isCurrent}\n  ({item.IslandId})";

                var btn = new Button
                {
                    Content = btnText,
                    Height = 44,
                    Margin = new Thickness(0, 0, 0, 8),
                    Style = (Style)FindResource("CyberButton")
                };

                string targetIsland = item.IslandId;
                btn.Click += (s, e) => TeleportToIsland(targetIsland);

                StackIslandsList.Children.Add(btn);
                idx++;
            }
        }

        private void TeleportToIsland(string newIslandId)
        {
            if (_isClosing) return;
            TxtFooterStatus.Text = $"¡Hiper-salto cuántico iniciado hacia la isla {newIslandId}!";
            TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 229, 255));

            _islandId = newIslandId;
            _db.UpdateUserIsland(_username, newIslandId);
            TxtSidebarIsland.Text = newIslandId;

            // Si Godot está ejecutándose, apagarlo y relanzarlo con los nuevos parámetros
            if (_godotProcess != null && !_godotProcess.HasExited)
            {
                try
                {
                    _godotProcess.Kill();
                    _godotProcess.WaitForExit(2000);
                }
                catch { }
                _godotProcess = null;

                Task.Run(() =>
                {
                    Dispatcher.Invoke(() =>
                    {
                        LaunchGodot(_wallet, _username, newIslandId);
                    });
                });
            }
        }

        // Sidebar Actions
        private void BtnValidarMetamask_Click(object sender, RoutedEventArgs e)
        {
            OpenMetamaskBrowser();
            TxtFooterStatus.Text = "Abriendo portal MetaMask en el navegador...";
        }

        private void BtnCerrarSesion_Click(object sender, RoutedEventArgs e)
        {
            Cleanup();

            // Ocultar Dashboard
            PanIpfsBar.Visibility = Visibility.Collapsed;
            PanMetricsBar.Visibility = Visibility.Collapsed;
            PanLeftSidebar.Visibility = Visibility.Collapsed;
            PanRightSidebar.Visibility = Visibility.Collapsed;
            PanViewportContainer.Visibility = Visibility.Collapsed;

            // Resetear datos
            _username = "";
            _wallet = "";
            _islandId = "137 : 190.1.0";

            // Volver a cargar WMI y verificar cuenta para actualizar el Step 1
            _hasAccount = _db.CheckHardwareExists(_fingerprint.UniqueHash, out string? registeredUser);
            if (_hasAccount && !string.IsNullOrEmpty(registeredUser))
            {
                _username = registeredUser;
                TxtStep1LoggedUser.Text = _username.ToUpper();
                PanStep1Login.Visibility = Visibility.Visible;
                BtnStep1Action.Content = "INICIAR SESIÓN / ACCEDER AL METAVERSO";
            }
            else
            {
                PanStep1Login.Visibility = Visibility.Collapsed;
                BtnStep1Action.Content = "VINCULAR MAQUINA / SIGUIENTE";
            }

            TxtStep1Password.Clear();
            ShowStep(1);
        }

        // ───── SERVIDOR PUENTE HTTP LOCAL (METAMASK) ─────
        private void StartHttpBridge()
        {
            try
            {
                _httpListener = new HttpListener();
                _httpListener.Prefixes.Add("http://localhost:8080/");
                _httpListener.Start();

                Task.Run(() => ListenLoop());
            }
            catch (Exception ex)
            {
                _lblBridgeStatus_Error($"ERROR: Puerto 8080 ocupado: {ex.Message}");
            }
        }

        private void _lblBridgeStatus_Error(string errorMsg)
        {
            Dispatcher.Invoke(() =>
            {
                TxtFooterBridgeStatus.Text = "● PUENTE HTTP: ERROR";
                TxtFooterBridgeStatus.Foreground = new SolidColorBrush(Colors.Red);
                TxtFooterStatus.Text = errorMsg;
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
            });
        }

        private async Task ListenLoop()
        {
            while (_httpListener != null && _httpListener.IsListening && !_isClosing)
            {
                try
                {
                    var context = await _httpListener.GetContextAsync();
                    var request = context.Request;
                    var response = context.Response;

                    string path = request.Url?.AbsolutePath ?? "/";

                    if (path == "/confirm")
                    {
                        // MetaMask ha firmado exitosamente la wallet
                        string user = request.QueryString["user"] ?? _username;
                        string wallet = request.QueryString["wallet"] ?? "No Wallet Address";
                        string island = request.QueryString["islandId"] ?? _islandId;

                        _db.UpdateWallet(user, wallet);

                        string responseString = "<html><head><meta charset='UTF-8'><title>Confirmado</title><style>body{background:#0a0f1a;color:#00d9ff;font-family:sans-serif;text-align:center;padding-top:100px;}h1{color:#00ff8c;}</style></head><body><h1>Metaverse Link Confirmed!</h1><p>Puedes regresar al Visor del juego en 3D.</p></body></html>";
                        byte[] buffer = Encoding.UTF8.GetBytes(responseString);
                        response.ContentLength64 = buffer.Length;
                        response.ContentType = "text/html; charset=UTF-8";
                        await response.OutputStream.WriteAsync(buffer, 0, buffer.Length);
                        response.OutputStream.Close();

                        // Actualizar UI del Visor
                        Dispatcher.Invoke(() =>
                        {
                            _wallet = wallet;
                            PanWaitHttp.Visibility = Visibility.Collapsed;
                            TxtFooterStatus.Text = "¡Firma de MetaMask recibida con éxito por el puente HTTP!";
                            TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));

                            // Generar la isla fija única al confirmar (SÓLO si es usuario nuevo)
                            if (!_hasAccount || _islandId == "137 : 190.1.0" || string.IsNullOrEmpty(_islandId))
                            {
                                GenerateUniqueIslandCoordinates();
                            }

                            // Avanzar al paso 4
                            ShowStep(4);
                        });
                    }
                    else if (path.StartsWith("/node"))
                    {
                        // Servir la página de descarga IPFS
                        string responseString = GetIpfsDownloadHtml();
                        byte[] buffer = Encoding.UTF8.GetBytes(responseString);
                        response.ContentLength64 = buffer.Length;
                        response.ContentType = "text/html; charset=UTF-8";
                        await response.OutputStream.WriteAsync(buffer, 0, buffer.Length);
                        response.OutputStream.Close();
                    }
                    else
                    {
                        // Servir metamask.html del visor si existe
                        string wwwPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "www");
                        if (!Directory.Exists(wwwPath))
                        {
                            wwwPath = @"D:\WCVcoinMTB\WoldVirtual\WoldVirtual3Dp2p\Capa3_Visor\www";
                        }

                        string filePath = Path.Combine(wwwPath, "metamask.html");
                        if (File.Exists(filePath))
                        {
                            byte[] buffer = File.ReadAllBytes(filePath);
                            response.ContentLength64 = buffer.Length;
                            response.ContentType = "text/html; charset=UTF-8";
                            await response.OutputStream.WriteAsync(buffer, 0, buffer.Length);
                        }
                        else
                        {
                            // Generar portal Web3 inline de contingencia
                            string responseString = $"<html><head><meta charset='UTF-8'><title>Conectar Wallet</title><style>body{{background:#0a0f1a;color:#fff;font-family:sans-serif;text-align:center;padding:50px;}}a{{background:#00d9ff;color:#000;padding:12px 24px;text-decoration:none;font-weight:bold;border-radius:6px;}}</style></head><body><h1>Link WoldVirtual MetaMask</h1><p>Usuario: {_username}</p><br><br><a href='/confirm?user={_username}&wallet=0x{Guid.NewGuid().ToString().Replace("-", "").Substring(0, 40)}&islandId={_islandId}'>SIMULAR CONEXION METAMASK EN CALIENTE</a></body></html>";
                            byte[] buffer = Encoding.UTF8.GetBytes(responseString);
                            response.ContentLength64 = buffer.Length;
                            response.ContentType = "text/html";
                            await response.OutputStream.WriteAsync(buffer, 0, buffer.Length);
                        }
                        response.OutputStream.Close();
                    }
                }
                catch
                {
                    // Ignorar cierres asíncronos de sockets
                }
            }
        }

        private void BtnCopyIpfs_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                System.Windows.Clipboard.SetText(TxtIpfsAddress.Text);
                TxtFooterStatus.Text = "¡Enlace IPFS local copiado al portapapeles! Abre tu navegador.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));
            }
            catch { }
        }

        private string GetIpfsDownloadHtml()
        {
            string hash = _fingerprint?.UniqueHash ?? "FINGERPRINT_NOT_FOUND";
            string userDisplay = string.IsNullOrEmpty(_username) ? "Invitado" : _username.ToUpper();
            
            return $@"<!DOCTYPE html>
<html>
<head>
    <meta charset='UTF-8'>
    <title>WoldVirtual P2P - IPFS Node Portal</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
        
        body {{
            background: radial-gradient(circle at 50% 0%, #0d1527 0%, #060b14 100%);
            color: #f8fafc;
            font-family: 'Outfit', sans-serif;
            text-align: center;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }}

        .container {{
            background: rgba(13, 22, 40, 0.6);
            border: 1px solid rgba(0, 229, 255, 0.2);
            border-radius: 20px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6), 0 0 30px rgba(0, 229, 255, 0.05);
            backdrop-filter: blur(16px);
            padding: 40px 60px;
            max-width: 600px;
            width: 90%;
            margin: 20px;
            animation: fadeIn 1s ease-out;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .logo {{
            font-size: 50px;
            margin: 0 0 10px 0;
            text-shadow: 0 0 20px #00e5ff;
            color: #00e5ff;
        }}

        h1 {{
            font-weight: 800;
            font-size: 28px;
            letter-spacing: 2px;
            margin: 0 0 5px 0;
            color: #f8fafc;
        }}

        .subtitle {{
            color: #00ff8c;
            font-weight: 600;
            font-size: 13px;
            letter-spacing: 3px;
            margin-bottom: 30px;
            text-transform: uppercase;
        }}

        .status-badge {{
            display: inline-flex;
            align-items: center;
            background: rgba(0, 255, 140, 0.1);
            border: 1px solid rgba(0, 255, 140, 0.3);
            color: #00ff8c;
            padding: 8px 16px;
            border-radius: 30px;
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 30px;
            box-shadow: 0 0 15px rgba(0, 255, 140, 0.1);
        }}

        .status-dot {{
            width: 8px;
            height: 8px;
            background: #00ff8c;
            border-radius: 50%;
            margin-right: 8px;
            box-shadow: 0 0 8px #00ff8c;
        }}

        .description {{
            color: #94a3b8;
            font-size: 15px;
            line-height: 1.6;
            margin-bottom: 35px;
        }}

        .btn-download {{
            display: inline-block;
            background: linear-gradient(135deg, #00e5ff 0%, #007acc 100%);
            color: #060b14;
            font-weight: 700;
            font-size: 15px;
            text-decoration: none;
            padding: 16px 36px;
            border-radius: 8px;
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.4);
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .btn-download:hover {{
            transform: translateY(-3px);
            box-shadow: 0 0 30px rgba(0, 229, 255, 0.6), 0 0 10px rgba(0, 229, 255, 0.2);
            filter: brightness(1.1);
        }}

        .btn-download:active {{
            transform: translateY(-1px);
        }}

        .info-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 15px;
            margin-top: 40px;
            text-align: left;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            padding-top: 30px;
        }}

        .info-item {{
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 12px 18px;
        }}

        .info-label {{
            color: #64748b;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
            margin-bottom: 4px;
            text-transform: uppercase;
        }}

        .info-value {{
            color: #00e5ff;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            word-break: break-all;
        }}

        .footer {{
            margin-top: 40px;
            color: #475569;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 1px;
        }}
    </style>
</head>
<body>
    <div class='container'>
        <div class='logo'>⬢</div>
        <h1>WOLD VIRTUAL</h1>
        <div class='subtitle'>P2P Decentralized Metaverse</div>

        <div class='status-badge'>
            <div class='status-dot'></div>
            NODO IPFS ACTIVO: LOCAL PORTAL
        </div>

        <p class='description'>
            Estás accediendo al portal web distribuido hosteado directamente por el Nodo Soberano de <strong>{userDisplay}</strong>. 
            Desde aquí puedes descargar de forma segura el visor 3D para unirte a la red descentralizada P2P.
        </p>

        <a href='#' class='btn-download' onclick='alert(""Iniciando simulación de descarga segura del Visor 3D (WoldVirtual3D.zip)..."")'>
            Descargar Visor 3D
        </a>

        <div class='info-grid'>
            <div class='info-item'>
                <div class='info-label'>Firma Cuántica del Nodo (Fingerprint)</div>
                <div class='info-value'>{hash.ToUpper()}</div>
            </div>
            <div class='info-item'>
                <div class='info-label'>Dirección del Portal Distribuido</div>
                <div class='info-value'>http://localhost:8080/node/{userDisplay.ToLower()}.ipfs</div>
            </div>
        </div>

        <div class='footer'>
            WOLD VIRTUAL P2P PROTOCOL V0.0.2 • SECURE CONNECTION
        </div>
    </div>
</body>
</html>";
        }

        // ───── PIPELINE DE LANZAMIENTO DE GODOT ──
        private async void LaunchGodot(string wallet, string user, string island, bool isNewRegistration = false)
        {
            if (_godotProcess != null && !_godotProcess.HasExited)
            {
                return;
            }

            // Rutas Relativas
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string godotExe = Path.GetFullPath(Path.Combine(baseDir, @"..\..\..\..\WoldVirtual\servidorinterno\Godot_v4.6.2-stable_mono_win64.exe"));
            string godotProjectDir = Path.GetFullPath(Path.Combine(baseDir, @"..\..\..\..\WoldVirtual"));

            // Rutas Absolutas de contingencia
            if (!File.Exists(godotExe))
            {
                godotExe = @"D:\WCVcoinMTB\WoldVirtual\WoldVirtual3Dp2p\WoldVirtual\servidorinterno\Godot_v4.6.2-stable_mono_win64.exe";
                godotProjectDir = @"D:\WCVcoinMTB\WoldVirtual\WoldVirtual3Dp2p\WoldVirtual";
            }

            if (!File.Exists(godotExe))
            {
                TxtFooterStatus.Text = "Error: El ejecutable de Godot no fue encontrado.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                return;
            }

            // ── PASO 1: Inicializar el controlador del overlay ──
            _viewer = new GodotViewer();

            // Esperar asíncronamente a que WPF calcule el layout
            await Task.Delay(150);

            // Escribir JSON de perfil del usuario para Godot
            try
            {
                string usersDir = Path.Combine(godotProjectDir, @"woldvirtual\scene\MTC\users3D");
                Directory.CreateDirectory(usersDir);
                string jsonContent = $"{{\n\t\"username\": \"{user}\",\n\t\"gender\": \"male\",\n\t\"wallet\": \"{wallet}\",\n\t\"timestamp\": {(long)(DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalSeconds}\n}}";
                File.WriteAllText(Path.Combine(usersDir, "current_user.json"), jsonContent, Encoding.UTF8);
            }
            catch (Exception ex) { Debug.WriteLine($"current_user.json: {ex.Message}"); }

            // ── PASO 2: Lanzar Godot de forma autónoma (Sin --wid) ──
            // Al no incrustar el HWND en WPF, evitamos los conflictos de renderizado 
            // que causan el parpadeo del avatar. Luego lo superpondremos.
            string mainScene = "res://woldvirtual/scene/MTC/N3DWoldVirtualMT.tscn";
            string arguments = $"--path \"{godotProjectDir}\" {mainScene} "
                              + $"--rendering-driver opengl3 "
                              + $"-- --wallet {wallet} --user-id \"{user}\" --island-id \"{island}\"";

            var startInfo = new ProcessStartInfo
            {
                FileName = godotExe,
                Arguments = arguments,
                WorkingDirectory = godotProjectDir,
                WindowStyle = ProcessWindowStyle.Minimized, // Arrancar minimizado para ocultar los bordes primero
                UseShellExecute = false
            };

            try
            {
                _godotProcess = Process.Start(startInfo);
                if (_godotProcess == null)
                    throw new Exception("El sistema operativo denegó la ejecución.");

                _godotProcess.EnableRaisingEvents = true;
                _godotProcess.Exited += (s, e) =>
                {
                    Dispatcher.Invoke(() =>
                    {
                        LogDebug("Godot process exited - shutting down visor");
                        _isClosing = true;
                        Cleanup();
                        Environment.Exit(0);
                    });
                };

                _viewer.GodotProcessId = (uint)_godotProcess.Id; // Asignar el PID de Godot al viewer
                LogDebug($"Godot Process ID: {_viewer.GodotProcessId}");

                try { _godotProcess.PriorityClass = ProcessPriorityClass.High; } catch { }

                TxtFooterStatus.Text = "¡Metaverso cargado! Sincronizando overlay espacial...";
                TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));

                // Esperar de forma asíncrona a que Godot cree su ventana principal
                _ = Task.Run(async () =>
                {
                    IntPtr hwnd = IntPtr.Zero;
                    for (int i = 0; i < 50; i++) // Esperar hasta 5 segundos (50 * 100ms)
                    {
                        await Task.Delay(100);
                        Dispatcher.Invoke(() =>
                        {
                            if (_viewer != null)
                            {
                                hwnd = _viewer.GetGodotHwnd();
                            }
                        });
                        if (hwnd != IntPtr.Zero) break;
                    }

                    if (hwnd != IntPtr.Zero)
                    {
                        Dispatcher.Invoke(() =>
                        {
                            if (_viewer != null)
                            {
                                // Quitar los bordes de la ventana para que parezca embebida
                                _viewer.StripWindowBorders();
                                
                                // Mover y superponer encima de nuestro GodotPlaceholder
                                _viewer.UpdatePosition(GodotPlaceholder, this);
                                _viewer.FocusGodot();
                                
                                TxtFooterStatus.Text = "¡Metaverso activo en modo overlay sincronizado!";
                            }
                        });
                    }
                });
            }
            catch (Exception ex)
            {
                TxtFooterStatus.Text = $"Error al iniciar el metaverso: {ex.Message}";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
            }
        }

        // ── Devuelve el factor de escala DPI de la pantalla principal ──
        private System.Windows.Point GetDpi()
        {
            var source = PresentationSource.FromVisual(this);
            if (source?.CompositionTarget == null)
                return new System.Windows.Point(1, 1);
            var m = source.CompositionTarget.TransformToDevice;
            return new System.Windows.Point(m.M11, m.M22);
        }


        private void Cleanup()
        {
            try { _httpListener?.Stop(); _httpListener?.Close(); } catch { }
            _httpListener = null;

            try { if (_godotProcess?.HasExited == false) _godotProcess.Kill(); } catch { }
            _godotProcess = null;

            if (_viewer != null)
            {
                _viewer = null;
            }
        }
    }


}
