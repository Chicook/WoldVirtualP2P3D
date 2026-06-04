using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Management;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Media.Imaging;
using Microsoft.Win32;
using NAudio.Wave;
using OpenCvSharp;
using OpenCvSharp.WpfExtensions;
using System.Drawing.Imaging;

namespace VisorSingularity
{
    public partial class MainWindow : System.Windows.Window
    {
        private string _osName = "Desconocido";
        private string _cpuName = "Desconocido";
        private string _motherboard = "Desconocido";
        private string _hardwareFingerprint = "";

        // MetaMask local HTTP server bridge variables
        private HttpListener? _httpListener;
        private Process? _godotProcess;
        private IntPtr _godotHwnd = IntPtr.Zero;
        private bool _isClosing = false;
        private GodotHwndHost? _godotHost;
        private string _currentUsername = "Anonymous";
        private UdpClient? _udpListener;
        private CancellationTokenSource? _udpCancellationTokenSource;
        private P2PWebNode? _p2pNode;
        private bool _metaverseUiActivated = false;

        // === Voice Chat (NAudio VAD) ===
        private WaveInEvent? _waveIn;
        private bool _voiceEnabled = false;
        private bool _isSpeaking = false;
        private DateTime _lastSpeechTime = DateTime.MinValue;
        private const double VoiceSilenceMs = 500.0;  // ms de silencio antes de "stopped"
        private const float VoiceThreshold = 0.015f;  // umbral RMS normalizado (0.0–1.0)

        // === Webcam (OpenCvSharp embedded child window) ===
        private VideoCapture? _capture;
        private Task? _captureTask;
        private CancellationTokenSource? _cancellationTokenSource;
        private bool _webcamEnabled = false;
        private HwndSource? _webcamHwndSource;
        private Image? _webcamImageControl;
        private TextBlock? _webcamStatusControl;

        // Win32 API Imports
        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode, EntryPoint = "GetClassNameW")]
        private static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr SetFocus(IntPtr hWnd);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool IsWindowVisible(IntPtr hWnd);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

        private static readonly IntPtr HWND_TOP = new IntPtr(0);
        private const uint SWP_NOMOVE = 0x0002;
        private const uint SWP_NOSIZE = 0x0001;
        private const uint SWP_NOACTIVATE = 0x0010;
        private const int WS_CHILD = 0x40000000;
        private const int WS_VISIBLE = 0x10000000;
        private const int WS_CLIPSIBLINGS = 0x04000000;

        public MainWindow()
        {

            InitializeComponent();
            this.Loaded += MainWindow_Loaded;

            // Vincular eventos de botones (Paso 1)
            BtnGenerateZip.Click += BtnGenerateZip_Click;
            BtnEnterMetaverse.Click += BtnEnterMetaverse_Click;
            BtnCopyHash.Click += BtnCopyHash_Click;

            // Vincular eventos de botones (Paso 2)
            BtnGenerateUuid.Click += BtnGenerateUuid_Click;
            BtnRegisterAndEnter.Click += BtnRegisterAndEnter_Click;

            // Vincular eventos del Chat P2P
            BtnSendChat.Click += BtnSendChat_Click;
            TxtChatMessage.KeyDown += TxtChatMessage_KeyDown;
            BtnCopyP2PLink.Click += BtnCopyP2PLink_Click;

            // Vincular botón de voz y webcam
            BtnVoiceChat.Click += BtnVoiceChat_Click;
            BtnWebcam.Click += BtnWebcam_Click;

            // Vincular eventos de redimensionado/movimiento de ventana para el Popup del Chat
            this.LocationChanged += (s, ev) => UpdatePopupPosition();
            this.SizeChanged += (s, ev) => { UpdatePopupPosition(); UpdateWebcamPosition(); };
        }

        private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
        {
            await RunHardwareScanAsync();
        }

        private async Task RunHardwareScanAsync()
        {
            try
            {
                ProgScan.Value = 0;
                TxtScanStatus.Text = "Inicializando escaneo del sistema...";
                await Task.Delay(400);

                // Paso 1: Escanear Sistema Operativo (25%)
                TxtScanStatus.Text = "Escaneando Sistema Operativo...";
                ProgScan.Value = 15;
                await Task.Delay(500);
                _osName = GetOSName();
                TxtOsName.Text = _osName;
                ProgScan.Value = 35;
                await Task.Delay(300);

                // Paso 2: Escanear Procesador (60%)
                TxtScanStatus.Text = "Identificando Procesador (CPU)...";
                ProgScan.Value = 50;
                await Task.Delay(600);
                _cpuName = GetCpuName();
                TxtCpuName.Text = _cpuName;
                ProgScan.Value = 70;
                await Task.Delay(300);

                // Paso 3: Escanear Placa Base (85%)
                TxtScanStatus.Text = "Detectando Placa Base y Chipset...";
                ProgScan.Value = 80;
                await Task.Delay(500);
                _motherboard = GetMotherboardName();
                TxtMotherboardName.Text = _motherboard;
                ProgScan.Value = 90;
                await Task.Delay(200);

                // Paso 4: Generar Huella Digital (100%)
                TxtScanStatus.Text = "Generando firma criptográfica SHA-256...";
                ProgScan.Value = 95;
                await Task.Delay(400);

                _hardwareFingerprint = GenerateSHA256Signature(_osName, _cpuName, _motherboard);
                TxtHardwareHash.Text = _hardwareFingerprint;

                ProgScan.Value = 100;
                TxtScanStatus.Text = "Escaneo completado. Firma de hardware generada.";

                // Habilitar botón para guardar el ZIP de respaldo
                BtnGenerateZip.IsEnabled = true;
            }
            catch (Exception ex)
            {
                TxtScanStatus.Text = "Error durante el escaneo: " + ex.Message;
                ProgScan.Value = 100;
                // Incluso si falla WMI, permitimos generar una firma alternativa basada en variables de entorno
                if (string.IsNullOrEmpty(_hardwareFingerprint))
                {
                    _hardwareFingerprint = GenerateSHA256Signature(
                        Environment.OSVersion.ToString(),
                        Environment.ProcessorCount.ToString() + " Cores",
                        Environment.MachineName
                    );
                    TxtHardwareHash.Text = _hardwareFingerprint;
                }
                BtnGenerateZip.IsEnabled = true;
            }
        }

        private string GetOSName()
        {
            try
            {
                using (var searcher = new ManagementObjectSearcher("SELECT Caption FROM Win32_OperatingSystem"))
                {
                    foreach (var obj in searcher.Get())
                    {
                        var caption = obj["Caption"]?.ToString();
                        if (!string.IsNullOrEmpty(caption))
                        {
                            return caption.Trim();
                        }
                    }
                }
            }
            catch
            {
                // Fallback a API de sistema
                return $"{Environment.OSVersion} ({(Environment.Is64BitOperatingSystem ? "64-bit" : "32-bit")})";
            }
            return "Windows OS";
        }

        private string GetCpuName()
        {
            try
            {
                using (var searcher = new ManagementObjectSearcher("SELECT Name FROM Win32_Processor"))
                {
                    foreach (var obj in searcher.Get())
                    {
                        var name = obj["Name"]?.ToString();
                        if (!string.IsNullOrEmpty(name))
                        {
                            return name.Trim();
                        }
                    }
                }
            }
            catch
            {
                return Environment.GetEnvironmentVariable("PROCESSOR_IDENTIFIER") ?? "Desconocido";
            }
            return "Generic CPU";
        }

        private string GetMotherboardName()
        {
            try
            {
                using (var searcher = new ManagementObjectSearcher("SELECT Manufacturer, Product FROM Win32_BaseBoard"))
                {
                    foreach (var obj in searcher.Get())
                    {
                        string manufacturer = obj["Manufacturer"]?.ToString() ?? "";
                        string product = obj["Product"]?.ToString() ?? "";
                        string res = $"{manufacturer} {product}".Trim();
                        if (!string.IsNullOrEmpty(res))
                        {
                            return res;
                        }
                    }
                }
            }
            catch
            {
                return "Placa Base Genérica (WMI no disponible)";
            }
            return "Baseboard";
        }

        private string GenerateSHA256Signature(string os, string cpu, string motherboard)
        {
            string rawData = $"{os.ToLower().Trim()}|{cpu.ToLower().Trim()}|{motherboard.ToLower().Trim()}";
            using (SHA256 sha256 = SHA256.Create())
            {
                byte[] bytes = sha256.ComputeHash(Encoding.UTF8.GetBytes(rawData));
                StringBuilder builder = new StringBuilder();
                for (int i = 0; i < bytes.Length; i++)
                {
                    builder.Append(bytes[i].ToString("x2"));
                }
                return builder.ToString();
            }
        }

        private void BtnCopyHash_Click(object sender, RoutedEventArgs e)
        {
            if (!string.IsNullOrEmpty(TxtHardwareHash.Text))
            {
                Clipboard.SetText(TxtHardwareHash.Text);
                MessageBox.Show("Firma criptográfica copiada al portapapeles.", "Firma Copiada", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void BtnGenerateZip_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                SaveFileDialog saveFileDialog = new SaveFileDialog
                {
                    Title = "Guardar Respaldo Seguro de Registro de PC",
                    FileName = "Firma_Hardware_WoldVirtual.zip",
                    Filter = "Archivo ZIP (*.zip)|*.zip",
                    DefaultExt = ".zip"
                };

                if (saveFileDialog.ShowDialog() == true)
                {
                    string targetZipPath = saveFileDialog.FileName;

                    // Crear directorio temporal seguro
                    string tempDir = Path.Combine(Path.GetTempPath(), "WoldVirtualBackup_" + Guid.NewGuid().ToString("N"));
                    Directory.CreateDirectory(tempDir);

                    // 1. Crear ficha de hardware
                    string reportPath = Path.Combine(tempDir, "registro_hardware.txt");
                    StringBuilder reportBuilder = new StringBuilder();
                    reportBuilder.AppendLine("==================================================");
                    reportBuilder.AppendLine("  WOLD VIRTUAL P2P 3D - REGISTRO DE HARDWARE");
                    reportBuilder.AppendLine("==================================================");
                    reportBuilder.AppendLine($"Fecha de Registro : {DateTime.Now}");
                    reportBuilder.AppendLine($"Sistema Operativo : {_osName}");
                    reportBuilder.AppendLine($"Procesador        : {_cpuName}");
                    reportBuilder.AppendLine($"Placa Base        : {_motherboard}");
                    reportBuilder.AppendLine("-------------------------------------------------- ");
                    reportBuilder.AppendLine("FIRMADO CRYPTO DE HARDWARE (SHA-256):");
                    reportBuilder.AppendLine(_hardwareFingerprint);
                    reportBuilder.AppendLine("==================================================");
                    File.WriteAllText(reportPath, reportBuilder.ToString(), Encoding.UTF8);

                    // 2. Crear archivo de clave de firma
                    string signaturePath = Path.Combine(tempDir, "signature.key");
                    File.WriteAllText(signaturePath, _hardwareFingerprint, Encoding.UTF8);

                    // 3. Comprimir a archivo zip
                    if (File.Exists(targetZipPath))
                    {
                        File.Delete(targetZipPath);
                    }

                    ZipFile.CreateFromDirectory(tempDir, targetZipPath);

                    // Limpiar directorio temporal
                    Directory.Delete(tempDir, true);

                    // Cambiar apariencia del botón
                    BtnGenerateZip.Content = "✓ RESPALDO GUARDADO";
                    BtnGenerateZip.IsEnabled = false;

                    // Desbloquear botón de ingreso al metaverso
                    BtnEnterMetaverse.IsEnabled = true;

                    MessageBox.Show(
                        $"¡Registro completado!\n\nSe ha generado y guardado el archivo de respaldo seguro en:\n{targetZipPath}\n\nGuarde este archivo ZIP en un lugar seguro para su autenticación de hardware.",
                        "Respaldo Exitoso",
                        MessageBoxButton.OK,
                        MessageBoxImage.Information
                    );
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al generar el respaldo ZIP: {ex.Message}", "Error de Registro", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void BtnEnterMetaverse_Click(object sender, RoutedEventArgs e)
        {
            // Paso 1 completado: Transicionar al Paso 2 (Registro de Usuario)
            GridPcRegistration.Visibility = Visibility.Collapsed;
            GridUserRegistration.Visibility = Visibility.Visible;
        }

        private void BtnGenerateUuid_Click(object sender, RoutedEventArgs e)
        {
            // Generar UUID único y ponerlo en el recuadro
            TxtRegUuid.Text = Guid.NewGuid().ToString().ToUpper();
        }

        private void BtnRegisterAndEnter_Click(object sender, RoutedEventArgs e)
        {
            string username = TxtRegUser.Text.Trim();
            string password = TxtRegPass.Password;
            string confirmPass = TxtRegPassConfirm.Password;
            string uuid = TxtRegUuid.Text.Trim();

            // Validaciones
            if (string.IsNullOrEmpty(username))
            {
                MessageBox.Show("Por favor, ingrese un nombre de usuario.", "Error de Validación", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            if (string.IsNullOrEmpty(password))
            {
                MessageBox.Show("Por favor, ingrese una contraseña.", "Error de Validación", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            if (password != confirmPass)
            {
                MessageBox.Show("Las contraseñas no coinciden. Por favor, verifíquelas.", "Error de Validación", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            if (string.IsNullOrEmpty(uuid))
            {
                MessageBox.Show("Por favor, genere un UUID único pulsando el botón 'GENERAR UUID'.", "Error de Validación", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Activar visualización de carga MetaMask en el Paso 2
            GridMetaMaskOverlay.Visibility = Visibility.Visible;

            // Iniciar el Servidor HTTP puente local en el puerto 8080
            StartHttpBridge(username);

            // Abrir automáticamente el navegador predeterminado para iniciar MetaMask
            try
            {
                string defaultIsland = "1 : 0.0.0";
                try
                {
                    var godotPaths = FindLocalGodotPaths();
                    if (!string.IsNullOrEmpty(godotPaths.projectDir))
                    {
                        string peersDir = Path.Combine(godotPaths.projectDir, "Estado_Global", "peers");
                        if (Directory.Exists(peersDir))
                        {
                            bool hasActivePeers = false;
                            var files = Directory.GetFiles(peersDir, "peer_*.json");
                            foreach (var file in files)
                            {
                                var lastWriteTime = File.GetLastWriteTime(file);
                                if ((DateTime.Now - lastWriteTime).TotalSeconds < 25)
                                {
                                    hasActivePeers = true;
                                    break;
                                }
                            }
                            if (!hasActivePeers)
                            {
                                defaultIsland = "1 : 0.0.0";
                            }
                        }
                        else
                        {
                            defaultIsland = "1 : 0.0.0";
                        }
                    }
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine("Error al determinar isla por defecto: " + ex.Message);
                }

                string url = $"http://localhost:8080/?user={Uri.EscapeDataString(username)}&islandId={Uri.EscapeDataString(defaultIsland)}";
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show($"No se pudo abrir el navegador automáticamente: {ex.Message}. Por favor, navegue a http://localhost:8080/ de forma manual.", "Error de Navegador", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        // ── SERVIDOR PUENTE HTTP LOCAL (METAMASK) ──
        private void StartHttpBridge(string username)
        {
            try
            {
                if (_httpListener != null)
                {
                    _httpListener.Stop();
                    _httpListener.Close();
                }

                _httpListener = new HttpListener();
                _httpListener.Prefixes.Add("http://localhost:8080/");
                _httpListener.Start();

                Task.Run(() => ListenLoop(username));
            }
            catch (Exception ex)
            {
                MessageBox.Show($"ERROR al iniciar HTTP Bridge en puerto 8080: {ex.Message}. Asegúrate de que no esté en uso.", "Error de Servidor", MessageBoxButton.OK, MessageBoxImage.Error);
                GridMetaMaskOverlay.Visibility = Visibility.Collapsed;
            }
        }

        private async Task ListenLoop(string username)
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
                        string user = request.QueryString["user"] ?? username;
                        string wallet = request.QueryString["wallet"] ?? "No Wallet";
                        string island = request.QueryString["islandId"] ?? "137 : 190.1.0";
                        string signature = request.QueryString["signature"] ?? "";

                        // Responder HTML de éxito
                        string responseString = "<html><head><meta charset='UTF-8'><title>Confirmado</title><style>body{background:#0a0f1a;color:#00d9ff;font-family:sans-serif;text-align:center;padding-top:100px;}h1{color:#00ff8c;}</style></head><body><h1>Metaverse Link Confirmed!</h1><p>Puedes regresar al Visor de la aplicacion.</p></body></html>";
                        byte[] buffer = Encoding.UTF8.GetBytes(responseString);
                        response.ContentLength64 = buffer.Length;
                        response.ContentType = "text/html; charset=UTF-8";
                        await response.OutputStream.WriteAsync(buffer, 0, buffer.Length);
                        response.OutputStream.Close();

                        // Transicionar la interfaz e iniciar Godot en el hilo UI
                        Dispatcher.Invoke(() =>
                        {
                            // Cerrar Listener
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

                            GridMetaMaskOverlay.Visibility = Visibility.Collapsed;
                            GridUserRegistration.Visibility = Visibility.Collapsed;
                            GridMainViewer.Visibility = Visibility.Visible;

                            _currentUsername = user;
                            TxtChatActiveUser.Text = $"Usuario: {user}";

                            LaunchAndEmbedGodot(wallet, user, island);
                        });
                    }
                    else
                    {
                        // Servir metamask.html local
                        string wwwPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "www");
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
                            // Fallback inline si no encuentra metamask.html
                            string responseString = $"<html><head><meta charset='UTF-8'><title>Conectar Wallet</title><style>body{{background:#0a0f1a;color:#fff;font-family:sans-serif;text-align:center;padding:50px;}}a{{background:#00d9ff;color:#000;padding:12px 24px;text-decoration:none;font-weight:bold;border-radius:6px;}}</style></head><body><h1>Link WoldVirtual MetaMask</h1><p>Usuario: {username}</p><br><br><a href='/confirm?user={username}&wallet=0x{Guid.NewGuid().ToString().Replace("-", "").Substring(0, 40)}&islandId=137_190_1_0'>SIMULAR CONEXION METAMASK</a></body></html>";
                            byte[] buffer = Encoding.UTF8.GetBytes(responseString);
                            response.ContentLength64 = buffer.Length;
                            response.ContentType = "text/html; charset=UTF-8";
                            await response.OutputStream.WriteAsync(buffer, 0, buffer.Length);
                        }
                        response.OutputStream.Close();
                    }
                }
                catch
                {
                    // Evitar excepciones al abortar sockets o listener
                }
            }
        }

        // ── LANZAMIENTO E INCRUSTACIÓN DEL MOTOR GODOT ──
        private async void LaunchAndEmbedGodot(string wallet, string user, string island)
        {
            if (_godotProcess != null && !_godotProcess.HasExited)
            {
                return;
            }

            _metaverseUiActivated = false;

            // Buscar rutas de Godot localmente
            var (projectDir, exePath) = FindLocalGodotPaths();

            if (!File.Exists(exePath))
            {
                MessageBox.Show($"Error: El ejecutable de Godot no fue encontrado localmente en:\n{exePath}", "Error de Lanzamiento", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // Limpiar contenedor placeholder
            GodotPlaceholder.Children.Clear();

            // Ocultar barra inferior de conexión inicialmente mientras se registra el avatar en Godot
            BorderBottomLoginBar.Visibility = Visibility.Collapsed;
            P2PNodeBar.Visibility = Visibility.Collapsed;
            EmbeddedServerNodeBar.Visibility = Visibility.Collapsed;

            // Configurar resolución de inicio
            int width = (int)Math.Max(800, GodotPlaceholder.ActualWidth);
            int height = (int)Math.Max(600, GodotPlaceholder.ActualHeight);

            // Argumentos de línea de comandos de Godot (apuntando a EscenaPrincipal.tscn)
            string arguments = $"--path \"{projectDir}\" res://EscenaPrincipal.tscn --rendering-driver opengl3 --windowed --resolution {width}x{height} -- --wallet {wallet} --user-id \"{user}\" --island-id \"{island}\"";
            string repoPath = Directory.GetParent(projectDir)?.FullName ?? projectDir;

            var startInfo = new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = arguments,
                WorkingDirectory = projectDir,
                UseShellExecute = false,
                CreateNoWindow = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            _godotProcess = new Process();
            _godotProcess.StartInfo = startInfo;
            _godotProcess.EnableRaisingEvents = true;

            // Escuchar la salida estándar de Godot para saber cuándo se registra el avatar
            _godotProcess.OutputDataReceived += (s, ev) =>
            {
                if (!string.IsNullOrEmpty(ev.Data))
                {
                    // Si se registra el perfil de usuario en Godot, mostramos la barra inferior de conexión en WPF
                    if (ev.Data.Contains("AVATAR_LOGIN_CLICKED"))
                    {
                        Dispatcher.Invoke(() =>
                        {
                            ActivateMetaverseUi(user, repoPath);
                        });
                    }
                }
            };

            try
            {
                _godotProcess.Start();
                _godotProcess.BeginOutputReadLine();
                _godotProcess.BeginErrorReadLine();

                // Escanear ventana de Godot en segundo plano
                _godotHwnd = await Task.Run(() => ScanForGodotWindow(_godotProcess.Id, 15000)); // 15 segundos máximo

                if (_godotHwnd != IntPtr.Zero && !_isClosing)
                {
                    // Crear el componente HwndHost e incrustarlo en WPF
                    _godotHost = new GodotHwndHost(_godotHwnd);
                    GodotPlaceholder.Children.Add(_godotHost);

                    // Hook de desvío de teclado
                    ComponentDispatcher.ThreadFilterMessage += ComponentDispatcher_ThreadFilterMessage;

                    // Iniciar el listener de chat UDP en WPF (puerto 50008)
                    StartUdpChatListener();
                }
                else
                {
                    MessageBox.Show("Tiempo de espera agotado para incrustar el motor 3D de Godot.", "Error de Integración", MessageBoxButton.OK, MessageBoxImage.Warning);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al iniciar el metaverso de Godot: {ex.Message}", "Error Crítico", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private IntPtr ScanForGodotWindow(int targetProcessId, int timeoutMs)
        {
            IntPtr result = IntPtr.Zero;
            DateTime start = DateTime.Now;
            IntPtr wpfHwnd = IntPtr.Zero;

            // Obtener el manejador de la ventana WPF en el hilo UI
            Dispatcher.Invoke(() =>
            {
                wpfHwnd = new WindowInteropHelper(this).Handle;
            });

            while (result == IntPtr.Zero && (DateTime.Now - start).TotalMilliseconds < timeoutMs && !_isClosing)
            {
                EnumWindows((hwnd, lParam) =>
                {
                    if (hwnd == wpfHwnd) return true; // Ignorar la ventana principal de WPF

                    // Debe ser una ventana visible en el escritorio
                    if (!IsWindowVisible(hwnd)) return true;

                    // Validar estrictamente que el HWND pertenezca al proceso de Godot que acabamos de arrancar
                    uint processId;
                    GetWindowThreadProcessId(hwnd, out processId);
                    if (processId != targetProcessId) return true; // No es el proceso de Godot, ignorar

                    // Obtener la clase de la ventana nativa
                    StringBuilder className = new StringBuilder(256);
                    GetClassName(hwnd, className, className.Capacity);
                    string cls = className.ToString();

                    // Obtener el título de la ventana
                    StringBuilder sb = new StringBuilder(256);
                    GetWindowText(hwnd, sb, sb.Capacity);
                    string title = sb.ToString();

                    // Descartar ventanas de consola o selectores de depuración, buscando la ventana principal de renderizado (Engine)
                    if (cls == "Engine" || (!title.Contains("Console") && !title.Contains("Select")))
                    {
                        result = hwnd;
                        return false; // Detener enumeración, hemos encontrado la ventana de renderizado correcta
                    }

                    return true; // Continuar
                }, IntPtr.Zero);

                if (result != IntPtr.Zero) break;
                System.Threading.Thread.Sleep(250);
            }

            return result;
        }

        private (string projectDir, string exePath) FindLocalGodotPaths()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            DirectoryInfo? dir = new DirectoryInfo(baseDir);

            while (dir != null)
            {
                string checkProject = Path.Combine(dir.FullName, "WoldVirtual");
                if (Directory.Exists(checkProject) && File.Exists(Path.Combine(checkProject, "project.godot")))
                {
                    string checkExe = Path.Combine(checkProject, "servidorinterno", "Godot_v4.6.2-stable_mono_win64.exe");
                    if (File.Exists(checkExe))
                    {
                        return (checkProject, checkExe);
                    }
                }

                if (dir.Name == "WoldVirtual" && File.Exists(Path.Combine(dir.FullName, "project.godot")))
                {
                    string checkExe = Path.Combine(dir.FullName, "servidorinterno", "Godot_v4.6.2-stable_mono_win64.exe");
                    if (File.Exists(checkExe))
                    {
                        return (dir.FullName, checkExe);
                    }
                }

                dir = dir.Parent;
            }

            // Fallback por defecto relativo
            string defaultProject = Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", "WoldVirtual"));
            string defaultExe = Path.Combine(defaultProject, "servidorinterno", "Godot_v4.6.2-stable_mono_win64.exe");
            return (defaultProject, defaultExe);
        }

        // ── HOOK DE TECLADO PARA AVATAR GODOT ──
        private void ComponentDispatcher_ThreadFilterMessage(ref MSG msg, ref bool handled)
        {
            const int WM_KEYDOWN = 0x0100;
            const int WM_KEYUP = 0x0101;
            const int WM_CHAR = 0x0102;
            const int WM_SYSKEYDOWN = 0x0104;
            const int WM_SYSKEYUP = 0x0105;

            // Si el foco está en un control de texto (TextBox o PasswordBox), permitimos escribir normalmente y no lo enviamos a Godot
            var focusedElement = System.Windows.Input.Keyboard.FocusedElement;
            if (focusedElement is System.Windows.Controls.TextBox || focusedElement is System.Windows.Controls.PasswordBox)
            {
                return;
            }

            if (_godotHwnd != IntPtr.Zero)
            {
                if (this.IsActive)
                {
                    if (msg.message == WM_KEYDOWN || msg.message == WM_KEYUP || msg.message == WM_CHAR || msg.message == WM_SYSKEYDOWN || msg.message == WM_SYSKEYUP)
                    {
                        PostMessage(_godotHwnd, (uint)msg.message, msg.wParam, msg.lParam);

                        // Consumir controles del avatar para evitar comportamientos extraños en WPF
                        int key = (int)msg.wParam;
                        if (key == 0x57 || key == 0x41 || key == 0x53 || key == 0x44 || // W A S D
                            key == 0x20 || // Espacio
                            key == 0x25 || key == 0x26 || key == 0x27 || key == 0x28 || // Flechas
                            key == 0x11 || // Control
                            key == 0x30 || key == 0x60) // Cero (0) y Numpad 0
                        {
                            handled = true;
                        }
                    }
                }
            }
        }

        private void Cleanup()
        {
            _metaverseUiActivated = false;
            StopVoiceCapture(); // Liberar micrófono al cerrar
            StopWebcam();       // Liberar webcam al cerrar
            if (_p2pNode != null)
            {
                try { _p2pNode.Stop(); } catch { }
                _p2pNode = null;
            }
            if (ChatOverlayPopup != null)
            {
                ChatOverlayPopup.IsOpen = false;
            }
            // P2PNodeBar es un Border en la barra de menú — basta con ocultarlo
            if (P2PNodeBar != null)
            {
                P2PNodeBar.Visibility = Visibility.Collapsed;
            }

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

            if (_godotProcess != null && !_godotProcess.HasExited)
            {
                try
                {
                    _godotProcess.Kill();
                }
                catch { }
                _godotProcess = null;
            }

            ComponentDispatcher.ThreadFilterMessage -= ComponentDispatcher_ThreadFilterMessage;
        }

        protected override void OnClosing(System.ComponentModel.CancelEventArgs e)
        {
            _isClosing = true;
            Cleanup();
            base.OnClosing(e);
        }

        private void BtnSendChat_Click(object sender, RoutedEventArgs e)
        {
            SendChatMessage();
        }

        private void TxtChatMessage_KeyDown(object sender, System.Windows.Input.KeyEventArgs e)
        {
            if (e.Key == System.Windows.Input.Key.Enter)
            {
                SendChatMessage();
                e.Handled = true;
            }
        }

        private void SendChatMessage()
        {
            string message = TxtChatMessage.Text.Trim();
            if (string.IsNullOrEmpty(message)) return;

            try
            {
                using (UdpClient udpClient = new UdpClient())
                {
                    string json = $"{{\"type\": \"chat\", \"user\": \"{_currentUsername}\", \"text\": \"{message.Replace("\"", "\\\"")}\"}}";
                    byte[] data = Encoding.UTF8.GetBytes(json);
                    udpClient.Send(data, data.Length, "127.0.0.1", 50007);
                }
                TxtChatMessage.Text = "";

                // Devolver el foco al motor 3D de Godot
                System.Windows.Input.Keyboard.ClearFocus();
                if (_godotHwnd != IntPtr.Zero)
                {
                    SetFocus(_godotHwnd);
                }
                if (_godotHost != null)
                {
                    _godotHost.Focus();
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error al enviar mensaje UDP: {ex.Message}");
            }
        }

        private void StartUdpChatListener()
        {
            StopUdpChatListener();

            _udpCancellationTokenSource = new CancellationTokenSource();
            var token = _udpCancellationTokenSource.Token;

            try
            {
                _udpListener = new UdpClient(50008);
                Task.Run(async () =>
                {
                    while (!token.IsCancellationRequested)
                    {
                        try
                        {
                            var result = await _udpListener.ReceiveAsync();
                            string jsonStr = Encoding.UTF8.GetString(result.Buffer);

                            // Procesar el mensaje JSON recibido de Godot
                            ProcessUdpChatMessage(jsonStr);
                        }
                        catch (ObjectDisposedException)
                        {
                            break; // El socket fue cerrado
                        }
                        catch (Exception ex)
                        {
                            Debug.WriteLine($"Error en UDP Listener recibiendo paquete: {ex.Message}");
                        }
                    }
                }, token);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error al iniciar UDP Chat Listener en puerto 50008: {ex.Message}");
            }
        }

        private void StopUdpChatListener()
        {
            if (_udpCancellationTokenSource != null)
            {
                _udpCancellationTokenSource.Cancel();
                _udpCancellationTokenSource.Dispose();
                _udpCancellationTokenSource = null;
            }
            if (_udpListener != null)
            {
                _udpListener.Close();
                _udpListener = null;
            }
        }

        private void ProcessUdpChatMessage(string jsonStr)
        {
            try
            {
                using (var doc = JsonDocument.Parse(jsonStr))
                {
                    var root = doc.RootElement;
                    if (root.TryGetProperty("type", out var typeProp) && typeProp.GetString() == "chat")
                    {
                        string user = root.TryGetProperty("user", out var userProp) ? userProp.GetString() ?? "Anonymous" : "Anonymous";
                        string text = root.TryGetProperty("text", out var textProp) ? textProp.GetString() ?? "" : "";
                        AddProximityChatMessage(user, text);
                    }
                    else if (root.TryGetProperty("type", out var sysProp) && sysProp.GetString() == "system")
                    {
                        string text = root.TryGetProperty("text", out var textProp) ? textProp.GetString() ?? "" : "";
                        AddProximityChatMessage("", text, isSystem: true);
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error al parsear chat UDP JSON: {ex.Message}");
            }
        }

        private void AddProximityChatMessage(string user, string text, bool isSystem = false)
        {
            Dispatcher.Invoke(() =>
            {
                // Asegurar que el popup esté abierto
                if (!ChatOverlayPopup.IsOpen)
                {
                    ChatOverlayPopup.IsOpen = true;
                }

                // Crear el TextBlock para el mensaje
                var tb = new TextBlock
                {
                    TextAlignment = TextAlignment.Left,
                    TextWrapping = TextWrapping.Wrap,
                    FontSize = 13,
                    FontFamily = new System.Windows.Media.FontFamily("Segoe UI"),
                    Margin = new Thickness(0, 3, 0, 3)
                };

                // Añadir sombra para legibilidad
                var shadow = new System.Windows.Media.Effects.DropShadowEffect
                {
                    Color = System.Windows.Media.Color.FromRgb(0, 0, 0),
                    BlurRadius = 3,
                    ShadowDepth = 1.5,
                    Direction = 315
                };
                tb.Effect = shadow;

                if (isSystem)
                {
                    tb.Inlines.Add(new Run(text)
                    {
                        Foreground = new SolidColorBrush((System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#45A29E")),
                        FontWeight = FontWeights.SemiBold
                    });
                }
                else
                {
                    tb.Inlines.Add(new Run(user + ": ")
                    {
                        Foreground = new SolidColorBrush((System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#66FCF1")),
                        FontWeight = FontWeights.Bold
                    });
                    tb.Inlines.Add(new Run(text)
                    {
                        Foreground = System.Windows.Media.Brushes.White
                    });
                }

                ChatOverlayPanel.Children.Add(tb);

                // Forzar actualización de posición del Popup para acomodar el nuevo elemento
                UpdatePopupPosition();

                // Animación de desvanecimiento
                var fadeOutAnimation = new DoubleAnimation
                {
                    From = 1.0,
                    To = 0.0,
                    Duration = new Duration(TimeSpan.FromSeconds(2.0)),
                    BeginTime = TimeSpan.FromSeconds(8.0) // Esperar 8 segundos antes de iniciar el desvanecimiento
                };

                fadeOutAnimation.Completed += (s, ev) =>
                {
                    ChatOverlayPanel.Children.Remove(tb);
                    if (ChatOverlayPanel.Children.Count == 0)
                    {
                        ChatOverlayPopup.IsOpen = false;
                    }
                };

                tb.BeginAnimation(UIElement.OpacityProperty, fadeOutAnimation);
            });
        }

        private void UpdatePopupPosition()
        {
            if (ChatOverlayPopup != null && ChatOverlayPopup.IsOpen)
            {
                double panelHeight = 180; // Fallback por defecto
                var child = ChatOverlayPopup.Child as UIElement;
                if (child != null)
                {
                    child.Measure(new System.Windows.Size(450, double.PositiveInfinity));
                    panelHeight = child.DesiredSize.Height;
                }

                // Posición en la esquina inferior izquierda (a la derecha de la barra lateral de 200px)
                double targetLeft = 215;
                double targetTop = GodotPlaceholder.ActualHeight - panelHeight - 15;

                ChatOverlayPopup.Placement = System.Windows.Controls.Primitives.PlacementMode.Relative;
                ChatOverlayPopup.HorizontalOffset = targetLeft;
                ChatOverlayPopup.VerticalOffset = targetTop;
            }

            UpdateWebcamPosition();

            // P2PNodeBar está fijo en la esquina superior derecha del visor — no requiere posicionamiento dinámico
        }

        private void ActivateMetaverseUi(string username, string repoPath)
        {
            if (_metaverseUiActivated)
            {
                return;
            }

            _metaverseUiActivated = true;
            BorderBottomLoginBar.Visibility = Visibility.Visible;
            EmbeddedServerNodeBar.Visibility = Visibility.Visible;

            if (_p2pNode == null)
            {
                StartP2PWebNode(username, repoPath);
            }
        }

        private void StartP2PWebNode(string username, string repoPath)
        {
            try
            {
                _p2pNode = new P2PWebNode(username, repoPath);

                // Suscribirse a cambios de estado del zipping/upload
                _p2pNode.OnStatusChanged += (status) =>
                {
                    Dispatcher.Invoke(() =>
                    {
                        TxtP2PStatus.Text = status;
                        // Actualizar el enlace en la barra cuando el link público esté listo (IPFS o Túnel SSH)
                        if ((_p2pNode.IsOnIpfs || _p2pNode.IsTunnelActive) && !string.IsNullOrEmpty(_p2pNode.GatewayUrl))
                        {
                            TxtP2PLink.Text = $"Enlace: {_p2pNode.GatewayUrl}";
                            TxtP2PNodeId.Text = $"NODO: {_p2pNode.NodeId}";
                        }
                    });
                };

                _p2pNode.Start();

                // Actualizar interfaz inicial
                TxtP2PNodeId.Text = $"NODO P2P: {_p2pNode.SimulatedUrl}";
                TxtP2PLink.Text = $"Enlace: {_p2pNode.LocalUrl}";
                TxtP2PStatus.Text = "Generando ZIP...";

                // Mostrar el widget P2P solo cuando el usuario ya está dentro del metaverso
                P2PNodeBar.Visibility = Visibility.Visible;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error al iniciar P2PWebNode: {ex.Message}");
            }
        }

        private void BtnCopyP2PLink_Click(object sender, RoutedEventArgs e)
        {
            if (_p2pNode != null)
            {
                // Preferir URL pública (0x0.st / Catbox / transfer.sh); si no, la local
                string urlToCopy = !string.IsNullOrEmpty(_p2pNode.GatewayUrl)
                    ? _p2pNode.GatewayUrl
                    : _p2pNode.LocalUrl;

                Clipboard.SetText(urlToCopy);

                bool esPublico = (_p2pNode.IsOnIpfs || _p2pNode.IsTunnelActive) && !string.IsNullOrEmpty(_p2pNode.GatewayUrl);
                if (esPublico)
                {
                    MessageBox.Show(
                        $"Enlace público de descarga copiado al portapapeles:\n\n{urlToCopy}\n\n" +
                        "Envíaselo a tu primo — podrá descargar el visor directamente desde el navegador.",
                        "Enlace Público Copiado", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                else
                {
                    MessageBox.Show(
                        $"Enlace LOCAL copiado (solo red local):\n\n{urlToCopy}\n\n" +
                        "Espera a que el ZIP se suba a un servidor público para compartirlo por internet.",
                        "Enlace Local", MessageBoxButton.OK, MessageBoxImage.Warning);
                }
            }
        }

        // ===================================================================
        // ── VOICE CHAT (NAudio + VAD + UDP + Peer JSON) ──
        // ===================================================================

        private void BtnVoiceChat_Click(object sender, RoutedEventArgs e)
        {
            if (!_voiceEnabled)
                StartVoiceCapture();
            else
                StopVoiceCapture();
        }

        private void StartVoiceCapture()
        {
            try
            {
                _waveIn = new WaveInEvent
                {
                    WaveFormat = new WaveFormat(16000, 16, 1),
                    BufferMilliseconds = 100
                };
                _waveIn.DataAvailable += OnVoiceDataAvailable;
                _waveIn.StartRecording();

                _voiceEnabled = true;
                _isSpeaking = false;
                _lastSpeechTime = DateTime.MinValue;
                Dispatcher.Invoke(UpdateVoiceButtonStyle);
                Debug.WriteLine("[VoiceChat] Captura de micrófono iniciada.");
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    $"No se pudo acceder al micrófono:\n{ex.Message}",
                    "Error de Voz", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        private void StopVoiceCapture()
        {
            if (_waveIn != null)
            {
                try
                {
                    _waveIn.StopRecording();
                    _waveIn.DataAvailable -= OnVoiceDataAvailable;
                    _waveIn.Dispose();
                }
                catch { }
                _waveIn = null;
            }

            if (_isSpeaking)
            {
                _isSpeaking = false;
                SendVoiceStateUdp(false, 0.0f);
                UpdateVoicePeerState(false);
            }

            _voiceEnabled = false;
            try { Dispatcher.Invoke(UpdateVoiceButtonStyle); } catch { }
            Debug.WriteLine("[VoiceChat] Captura de micrófono detenida.");
        }

        /// <summary>
        /// Callback de NAudio por cada buffer de 100 ms.
        /// Calcula el RMS normalizado y detecta actividad de voz (VAD).
        /// </summary>
        private void OnVoiceDataAvailable(object? sender, WaveInEventArgs e)
        {
            if (e.BytesRecorded == 0) return;

            // — Cálculo RMS sobre muestras PCM 16-bit signed —
            double sumSquares = 0.0;
            int sampleCount = e.BytesRecorded / 2;
            for (int i = 0; i < e.BytesRecorded - 1; i += 2)
            {
                short sample = (short)(e.Buffer[i] | (e.Buffer[i + 1] << 8));
                double norm = sample / 32768.0;
                sumSquares += norm * norm;
            }
            float rms = (float)Math.Sqrt(sumSquares / Math.Max(sampleCount, 1));

            bool wasSpeaking = _isSpeaking;

            if (rms > VoiceThreshold)
            {
                _lastSpeechTime = DateTime.Now;
                _isSpeaking = true;
            }
            else if (_isSpeaking &&
                     (DateTime.Now - _lastSpeechTime).TotalMilliseconds > VoiceSilenceMs)
            {
                _isSpeaking = false;
            }

            // Notificar solo cuando cambia el estado (evitar flood UDP)
            if (_isSpeaking != wasSpeaking)
            {
                float vol = _isSpeaking ? Math.Min(rms / VoiceThreshold, 1.0f) : 0.0f;
                SendVoiceStateUdp(_isSpeaking, vol);
                UpdateVoicePeerState(_isSpeaking);
                Dispatcher.Invoke(UpdateVoiceButtonStyle);
            }
        }

        /// <summary>Envía el estado de voz a Godot por UDP (puerto 50007).</summary>
        private void SendVoiceStateUdp(bool speaking, float volume)
        {
            try
            {
                using var udp = new UdpClient();
                string speakingStr = speaking ? "true" : "false";
                string json = $"{{\"type\":\"voice\",\"user\":\"{_currentUsername}\",\"speaking\":{speakingStr},\"vol\":{volume:F2}}}";
                byte[] data = Encoding.UTF8.GetBytes(json);
                udp.Send(data, data.Length, "127.0.0.1", 50007);
                Debug.WriteLine($"[VoiceChat] UDP → Godot: speaking={speaking}, vol={volume:F2}");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[VoiceChat] Error UDP voz: {ex.Message}");
            }
        }

        /// <summary>
        /// Escribe el campo "vc" (voice chat active) en el peer JSON del usuario local.
        /// Esto permite que los clientes Godot remotos muestren el indicador en el avatar.
        /// </summary>
        private void UpdateVoicePeerState(bool speaking)
        {
            try
            {
                var (projectDir, _) = FindLocalGodotPaths();
                string peerDir = Path.GetFullPath(
                    Path.Combine(projectDir, "..", "Estado_Global", "peers"));
                string peerFile = Path.Combine(peerDir, $"peer_{_currentUsername}.json");
                if (!File.Exists(peerFile)) return;

                string content = File.ReadAllText(peerFile, Encoding.UTF8).TrimEnd();
                string vcVal = speaking ? "true" : "false";

                if (content.Contains("\"vc\""))
                {
                    // Reemplazar el valor existente de "vc"
                    int vcIdx = content.IndexOf("\"vc\"", StringComparison.Ordinal);
                    int colonIdx = content.IndexOf(':', vcIdx);
                    int endIdx  = content.IndexOfAny(new[] { ',', '}' }, colonIdx + 1);
                    content = content.Substring(0, colonIdx + 1)
                              + vcVal
                              + content.Substring(endIdx);
                }
                else
                {
                    // Añadir campo antes del cierre JSON
                    if (content.EndsWith("}"))
                        content = content.Substring(0, content.Length - 1)
                                  + $",\"vc\":{vcVal}}}";
                }

                string tmp = peerFile + ".tmp";
                File.WriteAllText(tmp, content, Encoding.UTF8);
                if (File.Exists(peerFile)) File.Delete(peerFile);
                File.Move(tmp, peerFile);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[VoiceChat] Error actualizando peer JSON: {ex.Message}");
            }
        }

        /// <summary>Actualiza el aspecto visual del botón de voz según el estado actual.</summary>
        private void UpdateVoiceButtonStyle()
        {
            if (BtnVoiceChat == null) return;

            if (!_voiceEnabled)
            {
                // Estado inactivo — estilo por defecto
                BtnVoiceChat.Content = "🎤 VOZ";
                BtnVoiceChat.ClearValue(BackgroundProperty);
                BtnVoiceChat.ClearValue(ForegroundProperty);
                BtnVoiceChat.ToolTip = "Activar chat de voz";
            }
            else if (_isSpeaking)
            {
                // Hablando — verde cyberpunk brillante
                BtnVoiceChat.Content = "🔴 VOZ ON";
                BtnVoiceChat.Background = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#00FF8C"));
                BtnVoiceChat.Foreground = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#0B0C10"));
                BtnVoiceChat.ToolTip = "Hablando... (clic para desactivar)";
            }
            else
            {
                // Activo pero en silencio — teal suave
                BtnVoiceChat.Content = "🎤 ...";
                BtnVoiceChat.Background = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#1A3040"));
                BtnVoiceChat.Foreground = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#66FCF1"));
                BtnVoiceChat.ToolTip = "Escuchando... (clic para desactivar)";
            }
        }

        // ===================================================================
        // ── WEBCAM (OpenCvSharp PIP) ──
        // ===================================================================

        private void BtnWebcam_Click(object sender, RoutedEventArgs e)
        {
            if (!_webcamEnabled)
            {
                var result = MessageBox.Show(this,
                    "¿Deseas encender y compartir tu cámara web?",
                    "Compartir Webcam",
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Question);

                if (result == MessageBoxResult.Yes)
                {
                    StartWebcam();
                }
            }
            else
            {
                StopWebcam();
            }
        }

        private void StartWebcam()
        {
            try
            {
                // Intentar buscar la cámara en múltiples índices y con distintos backends de Windows
                for (int i = 0; i < 4; i++)
                {
                    _capture = new VideoCapture(i, VideoCaptureAPIs.MSMF); // Media Foundation (moderno)
                    if (_capture.IsOpened()) break;
                    _capture.Dispose();

                    _capture = new VideoCapture(i, VideoCaptureAPIs.DSHOW); // DirectShow (clásico)
                    if (_capture.IsOpened()) break;
                    _capture.Dispose();
                    
                    _capture = null;
                }

                if (_capture == null || !_capture.IsOpened())
                {
                    MessageBox.Show(this, 
                        "No se pudo acceder a la cámara.\n\n" +
                        "Posibles causas:\n" +
                        "1. Otra aplicación (como Zoom, OBS o el navegador) la está usando.\n" +
                        "2. Windows está bloqueando el acceso. Ve a Configuración de Windows -> Privacidad -> Cámara, y activa 'Permitir que las aplicaciones de escritorio accedan a la cámara'.\n" +
                        "3. La cámara está desconectada.", 
                        "Webcam no disponible", MessageBoxButton.OK, MessageBoxImage.Warning);
                    
                    if (_capture != null) { _capture.Dispose(); _capture = null; }
                    return;
                }

                _webcamEnabled = true;

                // Crear e incrustar la ventana de webcam
                CreateWebcamWindow();
                
                if (_webcamStatusControl != null)
                {
                    _webcamStatusControl.Visibility = Visibility.Visible;
                    _webcamStatusControl.Text = "Iniciando cámara...";
                }

                _cancellationTokenSource = new CancellationTokenSource();
                _captureTask = Task.Run(() => CaptureLoop(_cancellationTokenSource.Token));

                UpdateWebcamButtonStyle();
                Debug.WriteLine("[Webcam] Cámara iniciada con OpenCV.");
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, $"Error al acceder a la cámara:\n{ex.Message}", "Error de Webcam", MessageBoxButton.OK, MessageBoxImage.Error);
                StopWebcam();
            }
        }

        private void CaptureLoop(CancellationToken token)
        {
            try
            {
                using (var frame = new Mat())
                {
                    while (!token.IsCancellationRequested && _capture != null && _capture.IsOpened())
                    {
                        if (_capture.Read(frame) && !frame.Empty())
                        {
                            // Actualizar UI
                            Dispatcher.InvokeAsync(() =>
                            {
                                if (!_webcamEnabled) return;
                                if (_webcamImageControl != null)
                                {
                                    _webcamImageControl.Source = frame.ToWriteableBitmap();
                                }
                                if (_webcamStatusControl != null && _webcamStatusControl.Visibility == Visibility.Visible)
                                {
                                    _webcamStatusControl.Visibility = Visibility.Collapsed;
                                }
                            }, System.Windows.Threading.DispatcherPriority.Render);
                        }
                        
                        // Pequeña pausa para no saturar CPU (aprox 30 FPS)
                        Thread.Sleep(33);
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Webcam] Error en loop: {ex.Message}");
            }
        }

        private void StopWebcam()
        {
            _webcamEnabled = false;

            if (_cancellationTokenSource != null)
            {
                _cancellationTokenSource.Cancel();
                _cancellationTokenSource = null;
            }

            if (_captureTask != null)
            {
                try { _captureTask.Wait(500); } catch { }
                _captureTask = null;
            }

            if (_capture != null)
            {
                try
                {
                    _capture.Release();
                    _capture.Dispose();
                }
                catch { }
                _capture = null;
            }

            DestroyWebcamWindow();
            UpdateWebcamButtonStyle();
            Debug.WriteLine("[Webcam] Cámara detenida.");
        }

        private void CreateWebcamWindow()
        {
            if (_webcamHwndSource != null) return;

            IntPtr parentHwnd = IntPtr.Zero;
            if (_godotHost != null && _godotHost.Handle != IntPtr.Zero)
            {
                parentHwnd = _godotHost.Handle;
            }
            else
            {
                parentHwnd = new WindowInteropHelper(this).Handle;
            }

            // Calculamos la escala DPI
            double dpiX = 1.0;
            double dpiY = 1.0;
            var source = PresentationSource.FromVisual(this);
            if (source?.CompositionTarget != null)
            {
                var matrix = source.CompositionTarget.TransformToDevice;
                dpiX = matrix.M11;
                dpiY = matrix.M22;
            }

            int width = (int)(320 * dpiX);
            int height = (int)(240 * dpiY);
            int targetLeft = (int)((GodotPlaceholder.ActualWidth - 340) * dpiX);
            int targetTop = (int)((GodotPlaceholder.ActualHeight - 260) * dpiY);

            HwndSourceParameters parameters = new HwndSourceParameters("WebcamOverlay")
            {
                WindowStyle = WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS,
                ParentWindow = parentHwnd,
                Width = width,
                Height = height,
                PositionX = targetLeft,
                PositionY = targetTop,
                UsesPerPixelOpacity = false // Renderizado seguro y opaco como hijo de HWND
            };

            _webcamHwndSource = new HwndSource(parameters);

            _webcamImageControl = new Image
            {
                Stretch = Stretch.UniformToFill
            };

            _webcamStatusControl = new TextBlock
            {
                Text = "Cargando...",
                Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00FFFF")),
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
                Visibility = Visibility.Collapsed
            };

            var grid = new Grid();
            grid.Children.Add(_webcamImageControl);
            grid.Children.Add(_webcamStatusControl);

            var border = new Border
            {
                Width = 320,
                Height = 240,
                BorderBrush = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#00FFFF")),
                BorderThickness = new Thickness(2),
                Background = new SolidColorBrush(Color.FromRgb(17, 22, 37)), // Fondo oscuro opaco seguro para evitar pantallas negras en HWNDs hijos
                CornerRadius = new CornerRadius(4),
                Child = grid
            };

            _webcamHwndSource.RootVisual = border;

            // Poner encima de los hermanos (el visor 3D de Godot)
            SetWindowPos(_webcamHwndSource.Handle, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
        }

        private void DestroyWebcamWindow()
        {
            if (_webcamHwndSource != null)
            {
                _webcamHwndSource.Dispose();
                _webcamHwndSource = null;
            }
            _webcamImageControl = null;
            _webcamStatusControl = null;
        }

        private void UpdateWebcamPosition()
        {
            if (_webcamHwndSource != null && _webcamHwndSource.Handle != IntPtr.Zero)
            {
                try
                {
                    // Calculamos la escala DPI
                    double dpiX = 1.0;
                    double dpiY = 1.0;
                    var source = PresentationSource.FromVisual(this);
                    if (source?.CompositionTarget != null)
                    {
                        var matrix = source.CompositionTarget.TransformToDevice;
                        dpiX = matrix.M11;
                        dpiY = matrix.M22;
                    }

                    int targetLeft = (int)((GodotPlaceholder.ActualWidth - 340) * dpiX);
                    int targetTop = (int)((GodotPlaceholder.ActualHeight - 260) * dpiY);
                    int width = (int)(320 * dpiX);
                    int height = (int)(240 * dpiY);

                    MoveWindow(_webcamHwndSource.Handle, targetLeft, targetTop, width, height, true);
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[Webcam] Error al actualizar posición: {ex.Message}");
                }
            }
        }

        private void UpdateWebcamButtonStyle()
        {
            if (BtnWebcam == null) return;

            if (!_webcamEnabled)
            {
                BtnWebcam.Content = "📷 CAM";
                BtnWebcam.ClearValue(BackgroundProperty);
                BtnWebcam.ClearValue(ForegroundProperty);
            }
            else
            {
                BtnWebcam.Content = "🔴 CAM ON";
                BtnWebcam.Background = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#00FF8C"));
                BtnWebcam.Foreground = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#0B0C10"));
            }
        }
    }
}
