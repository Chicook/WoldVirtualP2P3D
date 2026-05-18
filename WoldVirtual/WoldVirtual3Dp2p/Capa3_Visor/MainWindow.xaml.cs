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
        // ── Win32 API Imports para el Incrustado de Ventanas ──
        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr SetParent(IntPtr hWndChild, IntPtr hWndNewParent);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

        [DllImport("user32.dll")]
        private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

        private const int GWL_STYLE = -16;
        private const int WS_VISIBLE = 0x10000000;
        private const int WS_CHILD = 0x40000000;

        // ── Datos de la Sesión Actual y Helpers ──
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
        private IntPtr _godotHwnd = IntPtr.Zero;

        public MainWindow()
        {
            InitializeComponent();
            
            this.Loaded += MainWindow_Loaded;
            this.Closed += MainWindow_Closed;
        }

        private void MainWindow_Loaded(object? sender, RoutedEventArgs e)
        {
            try
            {
                // Inicializar Helpers
                _db = new DatabaseManager();
                _fingerprint = new HardwareFingerprint();

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
            _isClosing = true;
            Cleanup();
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
            _isClosing = true;
            Cleanup();
            Application.Current.Shutdown();
        }

        // ───── WIZARD ACTIONS & NAVIGATION ─────
        
        private void ShowStep(int step)
        {
            _currentStep = step;
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

        // STEP 3 Action: Confirm Wallet address
        private void BtnStep3Next_Click(object sender, RoutedEventArgs e)
        {
            string w = TxtWalletAddress.Text.Trim();
            if (string.IsNullOrEmpty(w) || !w.StartsWith("0x") || w.Length < 10)
            {
                TxtFooterStatus.Text = "Error: Especifica una MetaMask Wallet válida (inicia con 0x).";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                return;
            }

            _wallet = w;

            // Generar la isla fija única
            GenerateUniqueIslandCoordinates();

            TxtFooterStatus.Text = "Wallet vinculada. Tu isla espacial única ha sido generada.";
            TxtFooterStatus.Foreground = new SolidColorBrush(Colors.White);
            ShowStep(4);
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
            // Ocultar todos los wizards
            Step1_PC.Visibility = Visibility.Collapsed;
            Step2_User.Visibility = Visibility.Collapsed;
            Step3_Metamask.Visibility = Visibility.Collapsed;
            Step4_Island.Visibility = Visibility.Collapsed;
            PanWaitHttp.Visibility = Visibility.Collapsed;

            // Mostrar el Sidebar y configurar tamaño
            ColSidebar.Width = new GridLength(280);
            PanSidebar.Visibility = Visibility.Visible;

            // Mostrar Viewport 3D
            PanViewportContainer.Visibility = Visibility.Visible;

            // Configurar Header (Ocultado para reubicar la información dentro de la escena 3D de Godot)
            TxtHeaderCryptoInfo.Visibility = Visibility.Collapsed;

            // Configurar datos Sidebar
            TxtSidebarUsername.Text = _username.ToUpper();
            TxtSidebarWallet.Text = _wallet.Length > 16 
                ? _wallet.Substring(0, 8) + "..." + _wallet.Substring(_wallet.Length - 6) 
                : _wallet;
            TxtSidebarIsland.Text = _islandId;

            // Cargar Lista de Islas del Teletransporte P2P
            LoadTeleportIslandsList();

            // Lanzar Godot e Incrustar
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

                Task.Run(() => {
                    Dispatcher.Invoke(() => {
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
            ColSidebar.Width = new GridLength(0);
            PanSidebar.Visibility = Visibility.Collapsed;
            PanViewportContainer.Visibility = Visibility.Collapsed;
            TxtHeaderCryptoInfo.Visibility = Visibility.Collapsed;

            // Resetear datos
            _username = "";
            _wallet = "";
            _islandId = "137 : 190.1.0";
            _godotHwnd = IntPtr.Zero;

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
            Dispatcher.Invoke(() => {
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
                        Dispatcher.Invoke(() => {
                            _wallet = wallet;
                            TxtWalletAddress.Text = wallet;
                            PanWaitHttp.Visibility = Visibility.Collapsed;
                            TxtFooterStatus.Text = "¡Firma de MetaMask recibida con éxito por el puente HTTP!";
                            TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));

                            // Generar la isla fija única al confirmar
                            GenerateUniqueIslandCoordinates();

                            // Avanzar al paso 4
                            ShowStep(4);
                        });
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

        // ───── PIPELINE DE LANZAMIENTO DE GODOT ──
        private void LaunchGodot(string wallet, string user, string island, bool isNewRegistration = false)
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

            // Limpiar controles internos del viewport WPF
            WfGamePanel.Controls.Clear();

            // Configurar resolución de renderizado
            int width = WfGamePanel.Width > 100 ? WfGamePanel.Width : 1100;
            int height = WfGamePanel.Height > 100 ? WfGamePanel.Height : 700;

            // REGISTRO DE AVATAR POR FUERA (EXTERNO) SIN TOCAR LA ESCENA DE GODOT
            try
            {
                string usersDir = Path.Combine(godotProjectDir, @"woldvirtual\scene\MTC\users3D");
                if (!Directory.Exists(usersDir))
                {
                    Directory.CreateDirectory(usersDir);
                }
                string userJsonPath = Path.Combine(usersDir, "current_user.json");

                // Generar JSON de perfil idéntico al formato esperado por el motor 3D de Godot
                string jsonContent = $"{{\n\t\"username\": \"{user}\",\n\t\"gender\": \"male\",\n\t\"wallet\": \"{wallet}\",\n\t\"timestamp\": {(long)(DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalSeconds}\n}}";

                File.WriteAllText(userJsonPath, jsonContent, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error al escribir current_user.json de forma externa: {ex.Message}");
            }

            // Para el visor incrustado, cargamos SIEMPRE la escena principal del Metaverso de forma directa
            string mainScene = "res://woldvirtual/scene/MTC/N3DWoldVirtualMT.tscn";

            // Argumentos de línea de comandos para inicializar a Godot incrustado en el Visor
            // Agregamos --disable-vsync para evitar conflictos con la composición DWM de Windows en ventanas hijas
            string arguments = $"--path \"{godotProjectDir}\" {mainScene} --rendering-driver opengl3 --windowed --disable-vsync --resolution {width}x{height} -- --wallet {wallet} --user-id \"{user}\" --island-id \"{island}\"";

            var startInfo = new ProcessStartInfo
            {
                FileName = godotExe,
                Arguments = arguments,
                WorkingDirectory = godotProjectDir,
                WindowStyle = ProcessWindowStyle.Hidden, // Ocultar para evitar el parpadeo de pantalla externa al iniciar
                UseShellExecute = false
            };

            try
            {
                _godotProcess = Process.Start(startInfo);
                if (_godotProcess == null)
                {
                    throw new Exception("El sistema operativo denegó la ejecución.");
                }

                // Ajustar prioridad del proceso a Alta para evitar la ralentización/throttling de Windows
                try
                {
                    _godotProcess.PriorityClass = ProcessPriorityClass.High;
                }
                catch { }

                TxtFooterStatus.Text = "Motor 3D cargando en el visor. Buscando ventana de renderizado...";
                TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 229, 255));

                // Buscar e incrustar la ventana en un hilo secundario asíncrono
                Task.Run(() => ScanAndEmbed(_godotProcess.Id));
            }
            catch (Exception ex)
            {
                TxtFooterStatus.Text = $"Error al iniciar el metaverso: {ex.Message}";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
            }
        }

        private void ScanAndEmbed(int processId)
        {
            IntPtr hwnd = IntPtr.Zero;
            int retries = 40; // 20 segundos máximo

            while (hwnd == IntPtr.Zero && retries > 0 && !_isClosing)
            {
                hwnd = FindWindowForProcess(processId);
                if (hwnd != IntPtr.Zero) break;

                Thread.Sleep(500);
                retries--;
            }

            if (hwnd != IntPtr.Zero && !_isClosing)
            {
                _godotHwnd = hwnd;
                
                // Docking e Incrustado usando el Dispatcher de WPF
                Dispatcher.Invoke(() => {
                    WfGamePanel.Controls.Clear();

                    SetParent(_godotHwnd, WfGamePanel.Handle);
                    SetWindowLong(_godotHwnd, GWL_STYLE, WS_VISIBLE | WS_CHILD);
                    MoveWindow(_godotHwnd, 0, 0, WfGamePanel.Width, WfGamePanel.Height, true);

                    TxtFooterStatus.Text = "¡Metaverso cargado con éxito! Firma de conexión P2P activa.";
                    TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));

                    // Auto-redimensionar al cambiar el tamaño del panel WPF
                    WfGamePanel.Resize += (s, e) => {
                        if (_godotHwnd != IntPtr.Zero)
                        {
                            MoveWindow(_godotHwnd, 0, 0, WfGamePanel.Width, WfGamePanel.Height, true);
                        }
                    };
                });
            }
            else
            {
                Dispatcher.Invoke(() => {
                    TxtFooterStatus.Text = "Error: Tiempo de espera agotado al incrustar el metaverso.";
                    TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                });
            }
        }

        private IntPtr FindWindowForProcess(int processId)
        {
            IntPtr result = IntPtr.Zero;
            IntPtr selfHwnd = IntPtr.Zero;

            // Obtener el Handle del propio visor WPF
            Dispatcher.Invoke(() => {
                selfHwnd = new WindowInteropHelper(this).Handle;
            });

            EnumWindows((hwnd, lParam) =>
            {
                if (hwnd == selfHwnd)
                    return true;

                GetWindowThreadProcessId(hwnd, out uint pid);

                try
                {
                    using (var proc = Process.GetProcessById((int)pid))
                    {
                        string procName = proc.ProcessName;

                        if (procName.Contains("Godot", StringComparison.OrdinalIgnoreCase))
                        {
                            var sb = new StringBuilder(256);
                            GetWindowText(hwnd, sb, sb.Capacity);
                            string title = sb.ToString();

                            if (title.StartsWith("WoldVirtual", StringComparison.OrdinalIgnoreCase))
                            {
                                result = hwnd;
                                return false; // Parar enumeración
                            }
                        }
                    }
                }
                catch { }

                return true; // Continuar enumeración
            }, IntPtr.Zero);

            return result;
        }

        // ───── FILTRADO DE MENSAJES DE TECLADO PARA REDIRECCIÓN A GODOT ─────
        private void ThreadFilterMessage(ref MSG msg, ref bool handled)
        {
            const int WM_KEYDOWN = 0x0100;
            const int WM_KEYUP = 0x0101;
            const int WM_CHAR = 0x0102;
            const int WM_SYSKEYDOWN = 0x0104;
            const int WM_SYSKEYUP = 0x0105;

            if (_godotHwnd != IntPtr.Zero)
            {
                if (this.IsActive)
                {
                    // Si el teclado ya está enfocado dentro de la zona 3D de Godot, Windows le envía los mensajes directamente.
                    // NO duplicamos los mensajes con PostMessage para evitar que el avatar vibre al andar debido a doble pulsación.
                    if (WfHost.IsKeyboardFocusWithin)
                    {
                        return;
                    }

                    if (msg.message == WM_KEYDOWN || msg.message == WM_KEYUP || msg.message == WM_CHAR || msg.message == WM_SYSKEYDOWN || msg.message == WM_SYSKEYUP)
                    {
                        // Enviar la pulsación de teclado de forma directa y asíncrona a la ventana interna de Godot
                        PostMessage(_godotHwnd, (uint)msg.message, msg.wParam, msg.lParam);

                        // Si es una tecla del avatar (WASD, flechas, espacio), la consumimos para evitar parpadeos en los controles de WPF
                        var key = KeyInterop.KeyFromVirtualKey((int)msg.wParam);
                        if (key == Key.W || key == Key.A || key == Key.S || key == Key.D || 
                            key == Key.Space || key == Key.Up || key == Key.Down || 
                            key == Key.Left || key == Key.Right)
                        {
                            handled = true;
                        }
                    }
                }
            }
        }

        private void Cleanup()
        {
            // Cerrar el servidor HTTP local
            if (_httpListener != null)
            {
                try
                {
                    _httpListener.Stop();
                    _httpListener.Close();
                }
                catch { }
                _httpListener = null;
            }

            // Apagar proceso de Godot
            if (_godotProcess != null && !_godotProcess.HasExited)
            {
                try
                {
                    _godotProcess.Kill();
                }
                catch { }
                _godotProcess = null;
            }
        }
    }
}
