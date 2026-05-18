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
        private DatabaseManager    _db           = null!;
        private int  _currentStep = 1;
        private bool _isClosing   = false;
        private bool _hasAccount  = false;

        private string _username = "";
        private string _wallet   = "";
        private string _islandId = "137 : 190.1.0";

        // ── Componentes de Ejecución ──
        private HttpListener?  _httpListener;
        private Process?       _godotProcess;
        private GodotViewer?   _viewer;

        public MainWindow()
        {
            InitializeComponent();
            this.Loaded += MainWindow_Loaded;
            this.Closed += MainWindow_Closed;

            // Foco a Godot al hacer clic en el área 3D
            GodotPlaceholder.MouseDown += (s, e) => _viewer?.FocusGodot();

            // Redimensionar Godot cuando cambie el placeholder
            GodotPlaceholder.SizeChanged += (s, e) =>
            {
                if (_viewer?.IsReady == true)
                {
                    var dpi = GetDpi();
                    _viewer.Resize(
                        (int)(GodotPlaceholder.ActualWidth  * dpi.X),
                        (int)(GodotPlaceholder.ActualHeight * dpi.Y));
                }
            };
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

            // ── PASO 1: Crear el visor nativo ANTES de lanzar Godot ──
            // GodotViewer.BuildWindowCore() se ejecuta al asignarlo al árbol visual.
            // Esto crea el contenedor Win32 y expone su HWND.
            _viewer = new GodotViewer();
            GodotPlaceholder.Child = _viewer;

            // Esperar a que WPF procese el layout y cree el HWND
            GodotPlaceholder.UpdateLayout();

            IntPtr containerHwnd = _viewer.ContainerHandle;
            if (containerHwnd == IntPtr.Zero)
            {
                TxtFooterStatus.Text = "Error: no se pudo crear el contenedor del visor.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Colors.Red);
                return;
            }

            // Obtener tamaño en píxeles físicos
            var dpi    = GetDpi();
            int width  = (int)(GodotPlaceholder.ActualWidth  * dpi.X);
            int height = (int)(GodotPlaceholder.ActualHeight * dpi.Y);
            if (width  < 100) width  = 1280;
            if (height < 100) height = 720;

            // Redimensionar el contenedor al tamaño real
            _viewer.Resize(width, height);

            // Escribir JSON de perfil del usuario para Godot
            try
            {
                string usersDir = Path.Combine(godotProjectDir, @"woldvirtual\scene\MTC\users3D");
                Directory.CreateDirectory(usersDir);
                string jsonContent = $"{{\n\t\"username\": \"{user}\",\n\t\"gender\": \"male\",\n\t\"wallet\": \"{wallet}\",\n\t\"timestamp\": {(long)(DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalSeconds}\n}}";
                File.WriteAllText(Path.Combine(usersDir, "current_user.json"), jsonContent, Encoding.UTF8);
            }
            catch (Exception ex) { Debug.WriteLine($"current_user.json: {ex.Message}"); }

            // ── PASO 2: Lanzar Godot con --wid apuntando al contenedor ──
            // Godot crea su contexto OpenGL directamente como hijo del contenedor.
            // No hay SetParent a posteriori. No hay conflicto de renderizado.
            string mainScene = "res://woldvirtual/scene/MTC/N3DWoldVirtualMT.tscn";
            string arguments = $"--path \"{godotProjectDir}\" {mainScene} "
                              + $"--rendering-driver opengl3 "
                              + $"--wid {containerHwnd} "
                              + $"-- --wallet {wallet} --user-id \"{user}\" --island-id \"{island}\"";

            var startInfo = new ProcessStartInfo
            {
                FileName         = godotExe,
                Arguments        = arguments,
                WorkingDirectory = godotProjectDir,
                WindowStyle      = ProcessWindowStyle.Hidden,
                UseShellExecute  = false
            };

            try
            {
                _godotProcess = Process.Start(startInfo);
                if (_godotProcess == null)
                    throw new Exception("El sistema operativo deneó la ejecución.");

                try { _godotProcess.PriorityClass = ProcessPriorityClass.High; } catch { }

                TxtFooterStatus.Text = "¡Metaverso cargado! Motor 3D activo dentro del visor.";
                TxtFooterStatus.Foreground = new SolidColorBrush(Color.FromRgb(0, 255, 140));

                // Dar foco a Godot después de que cargue
                Task.Run(() =>
                {
                    Thread.Sleep(3000);
                    Dispatcher.Invoke(() => _viewer?.FocusGodot());
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
                GodotPlaceholder.Child = null;
                _viewer = null;
            }
        }
    }


}
