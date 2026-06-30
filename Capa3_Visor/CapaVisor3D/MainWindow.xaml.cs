using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
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
using VisorSingularity.Services;

namespace VisorSingularity
{
    public partial class MainWindow : System.Windows.Window
    {
        private string _osName = "Desconocido";
        private string _cpuName = "Desconocido";
        private string _motherboard = "Desconocido";
        private string _hardwareFingerprint = "";

        // Ã¢â€â‚¬Ã¢â€â‚¬ Servicios de sesión/red Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        private readonly MetaverseSessionController _session = new MetaverseSessionController();
        private readonly UdpChatService _udpChat = new UdpChatService();

        private Process? _godotProcess;
        private IntPtr _godotHwnd = IntPtr.Zero;
        private bool _isClosing = false;
        private GodotHwndHost? _godotHost;
        private string _currentUsername = "Anonymous";
        private string _currentWallet = "0x0000";
        private string _currentWalletSignature = "0x_simulated_signature_local";
        private bool _metaverseUiActivated = false;

        // Ã¢â€â‚¬Ã¢â€â‚¬ Login de usuario existente (ZIP detectado) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        // Ruta fija donde se guarda una copia del ZIP de registro para detección automática
        private static readonly string APP_DATA_DIR    = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "WoldVirtual");
        private static readonly string APP_DATA_ZIP    = Path.Combine(APP_DATA_DIR, "firma_hardware.zip");
        private static readonly string APP_DATA_SIG    = Path.Combine(APP_DATA_DIR, "hardware_sig.txt");
        private string _loginFingerprint = "";
#pragma warning disable CS0414
        private bool   _isLoginMode      = false;   // true = usuario ya registrado (reservado para lógica futura)
#pragma warning restore CS0414

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

            // Vincular botón de Login (usuario existente)
            BtnLoginMetaMask.Click += BtnLoginMetaMask_Click;
            BtnLoginPhase1.Click += BtnLoginPhase1_Click;
            BtnLoginPhase2.Click += BtnLoginPhase2_Click;


            // Vincular eventos de redimensionado/movimiento de ventana para el Popup del Chat
            this.LocationChanged += (s, ev) => UpdatePopupPosition();
            this.SizeChanged += (s, ev) => { UpdatePopupPosition(); UpdateWebcamPosition(); };
        }

        private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
        {
            // Detectar idioma y país del sistema operativo en el inicio y aplicar al WPF UI
            var (lang, country) = HardwareFingerprintService.GetSystemLocaleInfo();
            ApplyWpfLocale(lang, country);

            // Comprobar si estamos en otro PC
            if (IsOnAnotherPc())
            {
                ResetRegistrationForNewPc();
            }

            // Detectar si el usuario ya tiene registro previo
            bool hasAccount = await CheckExistingRegistrationAsync();
            if (!hasAccount)
            {
                // Primer uso: mostrar flujo de registro de hardware
                await RunHardwareScanAsync();
            }
        }

        // Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ DETECCIÓN DE CUENTA EXISTENTE Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        /// <summary>
        /// Comprueba si existe el registro de PC (ZIP y firma) y el usuario (credentials y current_user.json).
        /// Si existe todo: muestra la pantalla de Login y devuelve true.
        /// Si falta algo: asegura la visibilidad de GridPcRegistration y devuelve false.
        /// </summary>
        private async Task<bool> CheckExistingRegistrationAsync()
        {
            return await Task.Run(() =>
            {
                bool hasZip = File.Exists(APP_DATA_ZIP);
                bool hasCreds = File.Exists(Path.Combine(APP_DATA_DIR, "credentials.json"));
                bool hasUserJson = DoesCurrentUserJsonExist();

                if (!hasZip || !hasCreds || !hasUserJson)
                {
                    Dispatcher.Invoke(() =>
                    {
                        GridPcRegistration.Visibility = Visibility.Visible;
                        GridUserRegistration.Visibility = Visibility.Collapsed;
                        GridLoginScreen.Visibility = Visibility.Collapsed;
                    });
                    return false;
                }

                // Leer la firma almacenada
                string sig = File.Exists(APP_DATA_SIG)
                    ? File.ReadAllText(APP_DATA_SIG, System.Text.Encoding.UTF8).Trim()
                    : "SHA-256 disponible en ZIP";

                Dispatcher.Invoke(() =>
                {
                    _loginFingerprint = sig;
                    _isLoginMode      = true;

                    // Ocultar pantalla de registro, mostrar pantalla de Login
                    GridPcRegistration.Visibility = Visibility.Collapsed;
                    GridLoginScreen.Visibility    = Visibility.Visible;

                    // Mostrar primeras 48 chars de la firma en la UI
                    string display = sig.Length > 48 ? sig.Substring(0, 48) + "..." : sig;
                    TxtLoginFingerprint.Text = $"SHA-256: {display}";

                    // Cargar configuraciones guardadas de recordar usuario/contraseña
                    LoadLoginSettings();
                });
                return true;
            });
        }

        private bool DoesCurrentUserJsonExist()
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                DirectoryInfo? dir = new DirectoryInfo(baseDir);
                while (dir != null)
                {
                    string candidate = Path.Combine(dir.FullName, "WoldVirtual", "woldvirtual", "scene", "MTC", "users3D", "current_user.json");
                    if (File.Exists(candidate)) return true;
                    candidate = Path.Combine(dir.FullName, "woldvirtual", "scene", "MTC", "users3D", "current_user.json");
                    if (File.Exists(candidate)) return true;
                    dir = dir.Parent;
                }
            }
            catch
            {
                // Ignorar
            }
            return false;
        }

        private (string username, string wallet, string islandId) GetSavedUserInfo()
        {
            string username = "Usuario";
            string wallet = "0x0000";
            string islandId = "1 : 0.0.0";
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                DirectoryInfo? dir = new DirectoryInfo(baseDir);
                string? filePath = null;

                while (dir != null)
                {
                    string candidate = Path.Combine(dir.FullName, "WoldVirtual", "woldvirtual", "scene", "MTC", "users3D", "current_user.json");
                    if (File.Exists(candidate))
                    {
                        filePath = candidate;
                        break;
                    }
                    candidate = Path.Combine(dir.FullName, "woldvirtual", "scene", "MTC", "users3D", "current_user.json");
                    if (File.Exists(candidate))
                    {
                        filePath = candidate;
                        break;
                    }
                    dir = dir.Parent;
                }

                if (filePath != null && File.Exists(filePath))
                {
                    string json = File.ReadAllText(filePath);
                    using (var doc = JsonDocument.Parse(json))
                    {
                        var root = doc.RootElement;
                        if (root.TryGetProperty("username", out var userProp))
                        {
                            username = userProp.GetString() ?? "Usuario";
                        }
                        if (root.TryGetProperty("wallet", out var walletProp))
                        {
                            wallet = walletProp.GetString() ?? "0x0000";
                        }
                    }
                }

                // Intentar cargar la isla por defecto desde los peers locales para que coincida con lo registrado
                var godotPaths = GodotProjectLocator.Resolve();
                var projectDir = godotPaths.ProjectDir;
                if (!string.IsNullOrEmpty(projectDir))
                {
                    string peersDir = Path.Combine(projectDir, "Estado_Global", "peers");
                    if (Directory.Exists(peersDir))
                    {
                        var files = Directory.GetFiles(peersDir, "peer_*.json");
                        foreach (var file in files)
                        {
                            var lastWriteTime = File.GetLastWriteTime(file);
                            if ((DateTime.Now - lastWriteTime).TotalSeconds < 25)
                            {
                                islandId = "1 : 0.0.0";
                                break;
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("[Login] Error al cargar información de usuario guardado: " + ex.Message);
            }
            return (username, wallet, islandId);
        }

        private void SaveUserCredentials(string username, string password)
        {
            try
            {
                Directory.CreateDirectory(APP_DATA_DIR);
                string credPath = Path.Combine(APP_DATA_DIR, "credentials.json");
                string passwordHash = ComputeSHA256(password);
                var credData = new
                {
                    username = username,
                    passwordHash = passwordHash
                };
                string json = JsonSerializer.Serialize(credData);
                File.WriteAllText(credPath, json, Encoding.UTF8);
                System.Diagnostics.Debug.WriteLine("[Registro] Credenciales locales guardadas.");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("[Registro] Error al guardar credenciales locales: " + ex.Message);
            }
        }

        private string ComputeSHA256(string input)
        {
            using (var sha256 = System.Security.Cryptography.SHA256.Create())
            {
                byte[] bytes = sha256.ComputeHash(Encoding.UTF8.GetBytes(input));
                var sb = new StringBuilder();
                foreach (byte b in bytes)
                {
                    sb.Append(b.ToString("x2"));
                }
                return sb.ToString();
            }
        }

        private void LoadLoginSettings()
        {
            try
            {
                string settingsPath = Path.Combine(APP_DATA_DIR, "login_settings.json");
                if (File.Exists(settingsPath))
                {
                    string json = File.ReadAllText(settingsPath);
                    using (var doc = JsonDocument.Parse(json))
                    {
                        var root = doc.RootElement;
                        bool rememberUser = root.TryGetProperty("rememberUser", out var remUser) && remUser.GetBoolean();
                        bool rememberPass = root.TryGetProperty("rememberPass", out var remPass) && remPass.GetBoolean();

                        ChkRememberUser.IsChecked = rememberUser;
                        ChkRememberPass.IsChecked = rememberPass;

                        if (rememberUser && root.TryGetProperty("savedUser", out var userProp))
                        {
                            TxtLoginUser.Text = userProp.GetString() ?? "";
                        }
                        if (rememberPass && root.TryGetProperty("savedPass", out var passProp))
                        {
                            string base64Pass = passProp.GetString() ?? "";
                            if (!string.IsNullOrEmpty(base64Pass))
                            {
                                byte[] data = Convert.FromBase64String(base64Pass);
                                TxtLoginPass.Password = Encoding.UTF8.GetString(data);
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("[Login] Error al cargar configuración de login: " + ex.Message);
            }
        }

        private void SaveLoginSettings()
        {
            try
            {
                Directory.CreateDirectory(APP_DATA_DIR);
                string settingsPath = Path.Combine(APP_DATA_DIR, "login_settings.json");

                bool rememberUser = ChkRememberUser.IsChecked == true;
                bool rememberPass = ChkRememberPass.IsChecked == true;

                string savedUser = rememberUser ? TxtLoginUser.Text : "";
                string savedPass = "";
                if (rememberPass)
                {
                    byte[] data = Encoding.UTF8.GetBytes(TxtLoginPass.Password);
                    savedPass = Convert.ToBase64String(data);
                }

                var settingsData = new
                {
                    rememberUser = rememberUser,
                    rememberPass = rememberPass,
                    savedUser = savedUser,
                    savedPass = savedPass
                };

                string json = JsonSerializer.Serialize(settingsData);
                File.WriteAllText(settingsPath, json, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("[Login] Error al guardar configuración de login: " + ex.Message);
            }
        }

        private void BtnLoginPhase1_Click(object sender, RoutedEventArgs e)
        {
            string enteredUser = TxtLoginUser.Text.Trim();
            string enteredPass = TxtLoginPass.Password;

            if (string.IsNullOrEmpty(enteredUser) || string.IsNullOrEmpty(enteredPass))
            {
                MessageBox.Show("Por favor, ingrese usuario y contraseña.", "Error de Validación", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Validar contra credentials.json
            string credPath = Path.Combine(APP_DATA_DIR, "credentials.json");
            bool isValid = false;

            if (!File.Exists(credPath))
            {
                // Fallback de migración de cuenta existente: registrar credenciales al primer ingreso
                SaveUserCredentials(enteredUser, enteredPass);
                isValid = true;
            }
            else
            {
                try
                {
                    string json = File.ReadAllText(credPath);
                    using (var doc = JsonDocument.Parse(json))
                    {
                        var root = doc.RootElement;
                        string savedUser = root.TryGetProperty("username", out var userProp) ? userProp.GetString() ?? "" : "";
                        string savedHash = root.TryGetProperty("passwordHash", out var hashProp) ? hashProp.GetString() ?? "" : "";

                        string enteredHash = ComputeSHA256(enteredPass);
                        if (savedUser.Equals(enteredUser, StringComparison.OrdinalIgnoreCase) && savedHash.Equals(enteredHash, StringComparison.Ordinal))
                        {
                            isValid = true;
                        }
                    }
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Error al leer credenciales locales: " + ex.Message, "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }
            }

            if (!isValid)
            {
                MessageBox.Show("Usuario o contraseña incorrectos.", "Ingreso Fallido", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // Guardar configuración de recordar
            SaveLoginSettings();

            // Bloquear Fase 1
            TxtLoginUser.IsEnabled = false;
            TxtLoginPass.IsEnabled = false;
            ChkRememberUser.IsEnabled = false;
            ChkRememberPass.IsEnabled = false;
            BtnLoginPhase1.IsEnabled = false;

            // Mostrar Fase 2
            PanelPhase2.Visibility = Visibility.Visible;
            TxtLoginPhaseStatus.Text = WpfTranslations[_currentLang]["LoginPhaseStatus_Phase2"];
        }

        private async void BtnLoginPhase2_Click(object sender, RoutedEventArgs e)
        {
            BtnLoginPhase2.IsEnabled = false;
            ScanProgressPanel.Visibility = Visibility.Visible;
            await RunLoginHardwareScanAsync();
        }

        private async Task RunLoginHardwareScanAsync()
        {
            try
            {
                var t = WpfTranslations[_currentLang];

                ProgLoginScan.Value = 0;
                TxtLoginScanStatus.Text = t["ScanningShort"];
                await Task.Delay(300);

                TxtLoginScanStatus.Text = t["IdentifyingCpuShort"];
                ProgLoginScan.Value = 30;
                await Task.Delay(400);

                TxtLoginScanStatus.Text = t["MotherboardShort"];
                ProgLoginScan.Value = 60;
                await Task.Delay(400);

                TxtLoginScanStatus.Text = t["SigningShort"];
                ProgLoginScan.Value = 90;
                await Task.Delay(300);

                // Obtener huella de hardware actual
                string os = HardwareFingerprintService.GetOSName();
                string cpu = HardwareFingerprintService.GetCpuName();
                string motherboard = HardwareFingerprintService.GetMotherboardName();
                _hardwareFingerprint = HardwareFingerprintService.GenerateSignature(os, cpu, motherboard);
                _loginFingerprint = _hardwareFingerprint;

                // Actualizar firma mostrada en la pantalla
                string display = _loginFingerprint.Length > 48 ? _loginFingerprint.Substring(0, 48) + "..." : _loginFingerprint;
                TxtLoginFingerprint.Text = $"SHA-256: {display}";

                // Ã¢â€â‚¬Ã¢â€â‚¬ Crear ZIP de actualización de firma temporal Ã¢â€â‚¬Ã¢â€â‚¬
                string tempDir = Path.Combine(Path.GetTempPath(), "WoldVirtualLoginUpdate_" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(tempDir);

                // Escribir reporte
                string reportPath = Path.Combine(tempDir, "registro_hardware.txt");
                StringBuilder reportBuilder = new StringBuilder();
                reportBuilder.AppendLine("==================================================");
                reportBuilder.AppendLine("  WOLD VIRTUAL P2P 3D - REGISTRO DE HARDWARE");
                reportBuilder.AppendLine("==================================================");
                reportBuilder.AppendLine($"Fecha de Actualización : {DateTime.Now}");
                reportBuilder.AppendLine($"Sistema Operativo      : {os}");
                reportBuilder.AppendLine($"Procesador             : {cpu}");
                reportBuilder.AppendLine($"Placa Base             : {motherboard}");
                reportBuilder.AppendLine("-------------------------------------------------- ");
                reportBuilder.AppendLine("FIRMADO CRYPTO DE HARDWARE (SHA-256):");
                reportBuilder.AppendLine(_hardwareFingerprint);
                reportBuilder.AppendLine("==================================================");
                File.WriteAllText(reportPath, reportBuilder.ToString(), Encoding.UTF8);

                // Clave de firma
                string signaturePath = Path.Combine(tempDir, "signature.key");
                File.WriteAllText(signaturePath, _hardwareFingerprint, Encoding.UTF8);

                // Ã¢â€â‚¬Ã¢â€â‚¬ Pedir al usuario donde guardar el ZIP de firma actualizado Ã¢â€â‚¬Ã¢â€â‚¬
                string? userZipPath = null;
                var saveDialog = new Microsoft.Win32.SaveFileDialog
                {
                    Title = "Guardar ZIP de Firma de Hardware Actualizado",
                    Filter = "Archivo ZIP (*.zip)|*.zip",
                    FileName = "WoldVirtual_HardwareSignature_Update.zip",
                    InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.Desktop)
                };

                bool? dialogResult = saveDialog.ShowDialog(this);
                if (dialogResult != true)
                {
                    // El usuario canceló Ã¢â‚¬â€ limpiar y abortar sin error
                    Directory.Delete(tempDir, true);
                    TxtLoginScanStatus.Text = t["CancelledShort"];
                    BtnLoginPhase2.IsEnabled = true;
                    return;
                }
                userZipPath = saveDialog.FileName;

                // Comprimir y copiar ZIP a la ruta elegida por el usuario
                string tempZip = Path.Combine(Path.GetTempPath(), "WoldVirtualSignatureTemp_" + Guid.NewGuid().ToString("N") + ".zip");
                ZipFile.CreateFromDirectory(tempDir, tempZip);

                // Copiar el ZIP a la ruta del usuario
                File.Copy(tempZip, userZipPath, overwrite: true);

                // También actualizar AppData interno para que la app pueda verificar la firma
                Directory.CreateDirectory(APP_DATA_DIR);
                if (File.Exists(APP_DATA_ZIP)) File.Delete(APP_DATA_ZIP);
                File.Copy(tempZip, APP_DATA_ZIP);
                File.WriteAllText(APP_DATA_SIG, _hardwareFingerprint, Encoding.UTF8);

                File.Delete(tempZip);
                Directory.Delete(tempDir, true);

                ProgLoginScan.Value = 100;
                TxtLoginScanStatus.Text = t["SignatureOkShort"];
                await Task.Delay(400);

                // Finalizar Fase 2
                BtnLoginPhase2.Content = t["SignatureUpdated"];
                BtnLoginPhase2.IsEnabled = false;
                ScanProgressPanel.Visibility = Visibility.Collapsed;

                // Desbloquear Fase 3 (MetaMask)
                BtnLoginMetaMask.Visibility = Visibility.Visible;
                TxtLoginPhaseStatus.Text = GetPhase3Message(_currentLang, userZipPath ?? "");
            }
            catch (Exception ex)
            {
                TxtLoginScanStatus.Text = "Error";
                MessageBox.Show("Error al actualizar la firma de hardware: " + ex.Message, "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                BtnLoginPhase2.IsEnabled = true;
            }
        }

        private string GetPhase3Message(string lang, string path)
        {
            switch (lang)
            {
                case "en":
                    return $"Phase 2 completed successfully. ZIP saved at: {path}\nPhase 3 unlocked: Login with MetaMask to enter.";
                case "fr":
                    return $"Phase 2 terminée avec succès. ZIP enregistré sous : {path}\nPhase 3 déverrouillée : Connectez-vous avec MetaMask pour entrer.";
                case "de":
                    return $"Phase 2 erfolgreich abgeschlossen. ZIP gespeichert unter: {path}\nPhase 3 freigeschaltet: Melden Sie sich mit MetaMask an, um fortzufahren.";
                case "pt":
                    return $"Fase 2 concluída com sucesso. ZIP salvo em: {path}\nFase 3 desbloqueada: Faça login com MetaMask para entrar.";
                case "it":
                    return $"Fase 2 completata con successo. ZIP salvato in: {path}\nFase 3 sbloccata: Accedi con MetaMask per entrare.";
                case "zh":
                    return $"Ã§Â¬Â¬ 2 Ã©ËœÂ¶Ã¦Â®ÂµÃ¦Ë†ÂÃ¥Å Å¸Ã¥Â®Å’Ã¦Ë†ÂÃ£â‚¬â€šZIP Ã¥Â·Â²Ã¤Â¿ÂÃ¥Â­ËœÃ¨â€¡Â³Ã¯Â¼Å¡{path}\nÃ§Â¬Â¬ 3 Ã©ËœÂ¶Ã¦Â®ÂµÃ¥Â·Â²Ã¨Â§Â£Ã©â€ÂÃ¯Â¼Å¡Ã©â‚¬Å¡Ã¨Â¿â€¡ MetaMask Ã§â„¢Â»Ã¥Â½â€¢Ã¤Â»Â¥Ã¨Â¿â€ºÃ¥â€¦Â¥Ã£â‚¬â€š";
                case "ja":
                    return $"Ã£Æ’â€¢Ã£â€šÂ§Ã£Æ’Â¼Ã£â€šÂº 2 Ã£ÂÅ’Ã¦Â­Â£Ã¥Â¸Â¸Ã£ÂÂ«Ã¥Â®Å’Ã¤Âºâ€ Ã£Ââ€”Ã£ÂÂ¾Ã£Ââ€”Ã£ÂÅ¸Ã£â‚¬â€šZIP Ã¤Â¿ÂÃ¥Â­ËœÃ¥â€¦Ë†: {path}\nÃ£Æ’â€¢Ã£â€šÂ§Ã£Æ’Â¼Ã£â€šÂº 3 Ã¨Â§Â£Ã©â„¢Â¤: MetaMaskÃ£ÂÂ§Ã£Æ’Â­Ã£â€šÂ°Ã£â€šÂ¤Ã£Æ’Â³Ã£Ââ€”Ã£ÂÂ¦Ã¥â€¦Â¥Ã£ÂÂ£Ã£ÂÂ¦Ã£ÂÂÃ£ÂÂ Ã£Ââ€¢Ã£Ââ€žÃ£â‚¬â€š";
                case "es":
                default:
                    return $"Fase 2 completada con éxito. ZIP guardado en: {path}\nFase 3 desbloqueada: Inicie sesión con MetaMask para entrar.";
            }
        }


        // Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ BOTON LOGIN METAMASK Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        private void BtnLoginMetaMask_Click(object sender, RoutedEventArgs e)
        {
            BtnLoginMetaMask.IsEnabled     = false;
            BorderLoginStatus.Visibility   = Visibility.Visible;
            TxtLoginStatus.Text            = "INICIANDO SESIÓN CON METAMASK...";

            var userInfo = GetSavedUserInfo();

            // Arrancar el servidor HTTP puente en modo login (puerto 8080)
            _session.LoginConfirmed += (confirm) => Dispatcher.Invoke(() => _OnLoginConfirmed(confirm.User, confirm.Wallet, confirm.Island, confirm.Signature));
            _session.BridgeError += (msg) => Dispatcher.Invoke(() => {
                MessageBox.Show($"ERROR al iniciar HTTP Bridge: {msg}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                BorderLoginStatus.Visibility = Visibility.Collapsed;
                BtnLoginMetaMask.IsEnabled = true;
            });
            _session.StartHttpBridgeLogin();

            // Abrir navegador con metamask.html en modo login pasando el usuario e isla correctos
            try
            {
                string url = $"http://localhost:8088/?mode=login&user={Uri.EscapeDataString(userInfo.username)}&islandId={Uri.EscapeDataString(userInfo.islandId)}";
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show($"No se pudo abrir el navegador: {ex.Message}\nNavega a http://localhost:8088/ manualmente.",
                    "Aviso", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }


        // StartHttpBridgeLogin → delegado a MetaverseSessionController

        /// <summary>Llamado tras confirmar la firma MetaMask en modo login.</summary>
        private void _OnLoginConfirmed(string user, string wallet, string island, string signature)
        {
            TxtLoginStatus.Text = "✅ FIRMA CONFIRMADA Ã¢â‚¬â€ ENTRANDO AL METAVERSO...";

            // 1) Actualizar el ZIP de registro con la firma de esta sesión
            UpdateLoginZip(wallet, signature);

            // 2) Transicionar al visor
            GridLoginScreen.Visibility = Visibility.Collapsed;
            GridMainViewer.Visibility  = Visibility.Visible;
            _currentUsername = user;
            _currentWallet = wallet;
            _currentWalletSignature = string.IsNullOrWhiteSpace(signature)
                ? "0x_simulated_signature_local"
                : signature;
            TxtChatActiveUser.Text = $"Usuario: {user}";

            // 3) Lanzar Godot apuntando DIRECTAMENTE a N3DWoldVirtualMT.tscn
            LaunchAndEmbedGodot(wallet, user, island,
                scenePath: "res://woldvirtual/scene/MTC/N3DWoldVirtualMT.tscn");
        }

        /// <summary>Actualiza el ZIP de registro añadiendo la firma de sesión MetaMask.</summary>
        private void UpdateLoginZip(string wallet, string signature)
        {
            try
            {
                if (!File.Exists(APP_DATA_ZIP)) return;

                string tempDir = Path.Combine(Path.GetTempPath(), "WoldVirtualLogin_" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(tempDir);

                // Extraer ZIP existente
                ZipFile.ExtractToDirectory(APP_DATA_ZIP, tempDir, overwriteFiles: true);

                // Añadir/actualizar archivo de sesión
                string sessionPath = Path.Combine(tempDir, "ultima_sesion.txt");
                var sb = new System.Text.StringBuilder();
                sb.AppendLine("=== Última Sesión de Login ===");
                sb.AppendLine($"Fecha       : {DateTime.Now}");
                sb.AppendLine($"Usuario     : {_currentUsername}");
                sb.AppendLine($"Wallet      : {wallet}");
                if (!string.IsNullOrEmpty(signature))
                    sb.AppendLine($"Firma MM    : {signature}");
                File.WriteAllText(sessionPath, sb.ToString(), System.Text.Encoding.UTF8);

                // Recomprimir
                string tmpZip = APP_DATA_ZIP + ".tmp";
                if (File.Exists(tmpZip)) File.Delete(tmpZip);
                ZipFile.CreateFromDirectory(tempDir, tmpZip);
                File.Delete(APP_DATA_ZIP);
                File.Move(tmpZip, APP_DATA_ZIP);

                Directory.Delete(tempDir, true);
                System.Diagnostics.Debug.WriteLine("[Login] ZIP actualizado con firma de sesión.");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[Login] Error al actualizar ZIP: {ex.Message}");
            }
        }

        private async Task RunHardwareScanAsync()
        {
            try
            {
                var t = WpfTranslations[_currentLang];

                ProgScan.Value = 0;
                TxtScanStatus.Text = t["ScanInit"];
                await Task.Delay(400);

                // Paso 1: Escanear Sistema Operativo (25%)
                TxtScanStatus.Text = t["ScanOS"];
                ProgScan.Value = 15;
                await Task.Delay(500);
                _osName = HardwareFingerprintService.GetOSName();
                TxtOsName.Text = _osName;
                ProgScan.Value = 35;
                await Task.Delay(300);

                // Paso 2: Escanear Procesador (60%)
                TxtScanStatus.Text = t["ScanCPU"];
                ProgScan.Value = 50;
                await Task.Delay(600);
                _cpuName = HardwareFingerprintService.GetCpuName();
                TxtCpuName.Text = _cpuName;
                ProgScan.Value = 70;
                await Task.Delay(300);

                // Paso 3: Escanear Placa Base (85%)
                TxtScanStatus.Text = t["ScanMB"];
                ProgScan.Value = 80;
                await Task.Delay(500);
                _motherboard = HardwareFingerprintService.GetMotherboardName();
                TxtMotherboardName.Text = _motherboard;
                ProgScan.Value = 90;
                await Task.Delay(200);

                // Paso 4: Generar Huella Digital (100%)
                TxtScanStatus.Text = t["ScanHash"];
                ProgScan.Value = 95;
                await Task.Delay(400);

                _hardwareFingerprint = HardwareFingerprintService.GenerateSignature(_osName, _cpuName, _motherboard);
                TxtHardwareHash.Text = _hardwareFingerprint;

                ProgScan.Value = 100;
                TxtScanStatus.Text = t["ScanDone"];

                // Habilitar botón para guardar el ZIP de respaldo
                BtnGenerateZip.IsEnabled = true;
            }
            catch (Exception ex)
            {
                var t = WpfTranslations[_currentLang];
                TxtScanStatus.Text = t["ScanError"] + ex.Message;
                ProgScan.Value = 100;
                // Incluso si falla WMI, permitimos generar una firma alternativa basada en variables de entorno
                if (string.IsNullOrEmpty(_hardwareFingerprint))
                {
                    _hardwareFingerprint = HardwareFingerprintService.GenerateSignature(
                        Environment.OSVersion.ToString(),
                        Environment.ProcessorCount.ToString() + " Cores",
                        Environment.MachineName
                    );
                    TxtHardwareHash.Text = _hardwareFingerprint;
                }
                BtnGenerateZip.IsEnabled = true;
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
                    BtnGenerateZip.Content    = "✔ RESPALDO GUARDADO";
                    BtnGenerateZip.IsEnabled  = false;

                    // Ã¢â€â‚¬Ã¢â€â‚¬ Guardar TAMBIÃƒâ€°N copia automática en AppData para detección de login Ã¢â€â‚¬Ã¢â€â‚¬
                    try
                    {
                        Directory.CreateDirectory(APP_DATA_DIR);
                        File.Copy(targetZipPath, APP_DATA_ZIP, overwrite: true);
                        File.WriteAllText(APP_DATA_SIG, _hardwareFingerprint, System.Text.Encoding.UTF8);
                        System.Diagnostics.Debug.WriteLine($"[Registro] Copia de seguridad en AppData guardada: {APP_DATA_ZIP}");
                    }
                    catch (Exception exAppData)
                    {
                        System.Diagnostics.Debug.WriteLine($"[Registro] Aviso: no se pudo copiar a AppData: {exAppData.Message}");
                    }

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

            // Guardar credenciales locales para validación de login posterior
            SaveUserCredentials(username, password);

            // Activar visualización de carga MetaMask en el Paso 2
            GridMetaMaskOverlay.Visibility = Visibility.Visible;

            // Iniciar el Servidor HTTP puente local en el puerto 8080
            _session.LoginConfirmed -= OnSessionLoginConfirmed; // evitar subscripcion doble
            _session.LoginConfirmed += OnSessionLoginConfirmed;
            _session.BridgeError -= OnSessionBridgeError;
            _session.BridgeError += OnSessionBridgeError;
            _session.StartHttpBridgeRegister(username);

            // Abrir automáticamente el navegador predeterminado para iniciar MetaMask
            try
            {
                string defaultIsland = "1 : 0.0.0";
                try
                {
                    var godotPaths = GodotProjectLocator.Resolve();
                    if (!string.IsNullOrEmpty(godotPaths.ProjectDir))
                    {
                        string peersDir = Path.Combine(godotPaths.ProjectDir, "Estado_Global", "peers");
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

                string url = $"http://localhost:8088/?user={Uri.EscapeDataString(username)}&islandId={Uri.EscapeDataString(defaultIsland)}";
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show($"No se pudo abrir el navegador automáticamente: {ex.Message}. Por favor, navegue a http://localhost:8088/ de forma manual.", "Error de Navegador", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        // Ã¢â€â‚¬Ã¢â€â‚¬ SERVIDOR PUENTE HTTP LOCAL (METAMASK) → MetaverseSessionController Ã¢â€â‚¬Ã¢â€â‚¬

        private void OnSessionLoginConfirmed(MetaMaskConfirm confirm)
        {
            Dispatcher.Invoke(() =>
            {
                if (confirm.IsLogin)
                {
                    // Flujo login (usuario ya registrado)
                    _OnLoginConfirmed(confirm.User, confirm.Wallet, confirm.Island, confirm.Signature);
                }
                else
                {
                    // Flujo registro (usuario nuevo)
                    GridMetaMaskOverlay.Visibility  = Visibility.Collapsed;
                    GridUserRegistration.Visibility = Visibility.Collapsed;
                    GridMainViewer.Visibility       = Visibility.Visible;
                    _currentUsername = confirm.User;
                    _currentWallet = confirm.Wallet;
                    _currentWalletSignature = string.IsNullOrWhiteSpace(confirm.Signature)
                        ? "0x_simulated_signature_local"
                        : confirm.Signature;
                    TxtChatActiveUser.Text = $"Usuario: {confirm.User}";
                    LaunchAndEmbedGodot(confirm.Wallet, confirm.User, confirm.Island,
                        scenePath: "res://EscenaPrincipal.tscn");
                }
            });
        }

        private void OnSessionBridgeError(string msg)
        {
            Dispatcher.Invoke(() =>
            {
                MessageBox.Show($"ERROR al iniciar HTTP Bridge: {msg}. Asegurate de que el puerto 8088 no este en uso.",
                    "Error de Servidor", MessageBoxButton.OK, MessageBoxImage.Error);
                GridMetaMaskOverlay.Visibility = Visibility.Collapsed;
            });
        }

        // ─── LANZAMIENTO E INCRUSTACIÓN DEL MOTOR GODOT ───
        /// <param name="scenePath">Ruta de escena Godot (res://...). Null = usa EscenaPrincipal.tscn</param>
        private async void LaunchAndEmbedGodot(string wallet, string user, string island, string scenePath = "res://EscenaPrincipal.tscn")
        {
            if (_godotProcess != null && !_godotProcess.HasExited)
            {
                return;
            }

            _metaverseUiActivated = false;

            // Buscar rutas de Godot localmente
            var godotPaths = GodotProjectLocator.Resolve();
            string projectDir = godotPaths.ProjectDir;
            string exePath = godotPaths.ExePath;
            string repoPath = Directory.GetParent(projectDir)?.FullName ?? projectDir;

            if (!File.Exists(exePath))
            {
                MessageBox.Show($"Error: El ejecutable de Godot no fue encontrado localmente en:\n{exePath}", "Error de Lanzamiento", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            // Limpiar contenedor placeholder
            GodotPlaceholder.Children.Clear();

            if (scenePath == "res://EscenaPrincipal.tscn")
            {
                // Ocultar barra inferior de conexión inicialmente mientras se registra el avatar en Godot
                BorderBottomLoginBar.Visibility = Visibility.Collapsed;
                P2PNodeBar.Visibility = Visibility.Collapsed;
                EmbeddedServerNodeBar.Visibility = Visibility.Collapsed;
            }
            else
            {
                // Si entra directo (login), activar de una vez la UI del Metaverso y sus barras (Webnodo, Servidor virtual, Chat)
                ActivateMetaverseUi(user, repoPath);
            }

            // Forzar layout settle para que el placeholder tenga dimensiones válidas
            GodotPlaceholder.UpdateLayout();
            await Task.Delay(100);

            // Configurar resolución de inicio
            int width = (int)Math.Max(800, GodotPlaceholder.ActualWidth);
            int height = (int)Math.Max(600, GodotPlaceholder.ActualHeight);

            // Detectar país e idioma del sistema para pasarlo a Godot
            var (detectedLang, detectedCountry) = HardwareFingerprintService.GetSystemLocaleInfo();

            // Argumentos de línea de comandos de Godot
            string arguments = $"--path \"{projectDir}\" {scenePath} --rendering-driver opengl3 --windowed --resolution {width}x{height} -- --wallet {wallet} --user-id \"{user}\" --island-id \"{island}\" --lang \"{detectedLang}\" --country \"{detectedCountry}\"";

            try
            {
                IntPtr wpfHwnd = new System.Windows.Interop.WindowInteropHelper(this).Handle;
                
                var result = await GodotLauncherService.LaunchGodotAsync(
                    projectDir,
                    exePath,
                    arguments,
                    (output) =>
                    {
                        if (output.Contains("AVATAR_LOGIN_CLICKED"))
                        {
                            Dispatcher.Invoke(() =>
                            {
                                ActivateMetaverseUi(user, repoPath);
                            });
                        }
                    },
                    wpfHwnd,
                    () => _isClosing
                );

                _godotProcess = result.process;
                _godotHwnd = result.godotHwnd;

                if (_godotHwnd != IntPtr.Zero && !_isClosing)
                {
                    // Crear el componente HwndHost e incrustarlo en WPF
                    _godotHost = new GodotHwndHost(_godotHwnd);
                    GodotPlaceholder.Children.Add(_godotHost);

                    // Forzar resize inmediato para asegurar que la ventana de Godot se ajusta correctamente
                    await Task.Delay(50);
                    _godotHost.ResizeToActualPixels();

                    // Hook de desvío de teclado
                    System.Windows.Interop.ComponentDispatcher.ThreadFilterMessage += ComponentDispatcher_ThreadFilterMessage;

                    // Iniciar el listener de chat UDP en WPF (puerto 50008)
                    // Iniciar chat UDP via servicio dedicado
                    _udpChat.MessageReceived += OnUdpChatMessageReceived;
                    _udpChat.Start();
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

        private string _currentLang = "es";

        private static readonly Dictionary<string, Dictionary<string, string>> WpfTranslations = new Dictionary<string, Dictionary<string, string>>
        {
            {
                "es", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL — SISTEMA DE INGRESO" },
                    { "PcRegSubtitle", "REGISTRO AUTOMÁTICO DE FIRMA DE HARDWARE" },
                    { "OsCardTitle", "SISTEMA OPERATIVO" },
                    { "CpuCardTitle", "PROCESADOR" },
                    { "MbCardTitle", "PLACA BASE (MOTHERBOARD)" },
                    { "CryptoLabel", "FIRMADO EN HARDWARE / UNIQUE CRYPTO FINGERPRINT (SHA-256)" },
                    { "Copy", "COPIAR" },
                    { "RegisterPc", "REGISTRAR PC & GUARDAR ZIP" },
                    { "EnterMetaverse", "INGRESAR AL METAVERSO" },
                    { "UserRegTitle", "WOLD VIRTUAL — REGISTRO DE USUARIO" },
                    { "UserRegSubtitle", "CREACIÓN DE IDENTIDAD Y ASIGNACIÓN DE CREDENCIALES" },
                    { "UsernameLabel", "Nombre de Usuario:" },
                    { "PasswordLabel", "Contraseña:" },
                    { "ConfirmPasswordLabel", "Repetir Contraseña:" },
                    { "UuidLabel", "Identificador Único Universal (UUID):" },
                    { "GenerateUuid", "GENERAR UUID" },
                    { "RegisterAndEnter", "REGISTRAR & INGRESAR" },
                    { "WaitingMetaMaskTitle", "ESPERANDO FIRMA DE METAMASK" },
                    { "WaitingMetaMaskDesc", "Por favor, abre tu navegador predeterminado y firma la solicitud de MetaMask para vincular tu billetera." },
                    { "LoginInfoTitle", "FIRMA DE HARDWARE DETECTADA" },
                    { "LoginPhaseStatus_Phase1", "Fase 1: Ingrese su usuario y contraseña para continuar." },
                    { "LoginPhaseStatus_Phase2", "Fase 1 completada con éxito. Fase 2 desbloqueada: Firme y actualice el registro ZIP de su PC." },
                    { "LoginMetaMaskDesc", "Abre tu navegador y autoriza la solicitud de MetaMask" },
                    { "LoginUserLabel", "Usuario:" },
                    { "LoginRememberUser", "Recordar Nombre" },
                    { "LoginPassLabel", "Contraseña:" },
                    { "LoginRememberPass", "Recordar Contraseña" },
                    { "LoginMetaMaskBtn", "🦊 Entrar con MetaMask" },
                    { "LoginBtn", "Iniciar Sesión" },
                    { "UpdateSignatureBtn", "✍️ Actualizar Firma" },
                    { "ScanInit", "Inicializando escaneo del sistema..." },
                    { "ScanOS", "Escaneando OS..." },
                    { "ScanCPU", "Identificando CPU..." },
                    { "ScanMB", "Detectando Placa Base..." },
                    { "ScanHash", "Generando firma criptográfica SHA-256..." },
                    { "ScanDone", "Escaneo completado. Firma de hardware generada." },
                    { "ScanError", "Error durante el escaneo: " },
                    { "ScanOSLoading", "Obteniendo información del sistema..." },
                    { "ScanCPULoading", "Obteniendo especificaciones de la CPU..." },
                    { "ScanMBLoading", "Detectando placa base..." },
                    { "GeneratingHashText", "GENERANDO FIRMA CRIPTOGRÁFICA..." },
                    { "ScanningShort", "Escaneando..." },
                    { "IdentifyingCpuShort", "Identificando CPU..." },
                    { "MotherboardShort", "Placa base..." },
                    { "SigningShort", "Firmando..." },
                    { "SignatureOkShort", "Firma OK" },
                    { "CancelledShort", "Cancelado" },
                    { "SignatureUpdated", "✔ FIRMA ACTUALIZADA" }
                }
            },
            {
                "en", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ LOGIN SYSTEM" },
                    { "PcRegSubtitle", "AUTOMATIC HARDWARE SIGNATURE REGISTRATION" },
                    { "OsCardTitle", "OPERATING SYSTEM" },
                    { "CpuCardTitle", "PROCESSOR" },
                    { "MbCardTitle", "MOTHERBOARD" },
                    { "CryptoLabel", "HARDWARE SIGNED / UNIQUE CRYPTO FINGERPRINT (SHA-256)" },
                    { "Copy", "COPY" },
                    { "RegisterPc", "REGISTER PC & SAVE ZIP" },
                    { "EnterMetaverse", "ENTER METAVERSE" },
                    { "UserRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ USER REGISTRATION" },
                    { "UserRegSubtitle", "IDENTITY CREATION AND CREDENTIAL ASSIGNMENT" },
                    { "UsernameLabel", "Username:" },
                    { "PasswordLabel", "Password:" },
                    { "ConfirmPasswordLabel", "Repeat Password:" },
                    { "UuidLabel", "Universally Unique Identifier (UUID):" },
                    { "GenerateUuid", "GENERATE UUID" },
                    { "RegisterAndEnter", "REGISTER & ENTER" },
                    { "WaitingMetaMaskTitle", "WAITING FOR METAMASK SIGNATURE" },
                    { "WaitingMetaMaskDesc", "Please open your default browser and sign the MetaMask request to link your wallet." },
                    { "LoginInfoTitle", "HARDWARE SIGNATURE DETECTED" },
                    { "LoginPhaseStatus_Phase1", "Phase 1: Enter your username and password to continue." },
                    { "LoginPhaseStatus_Phase2", "Phase 1 completed successfully. Phase 2 unlocked: Sign and update your PC's ZIP registration." },
                    { "LoginMetaMaskDesc", "Open your browser and authorize the MetaMask request" },
                    { "LoginUserLabel", "Username:" },
                    { "LoginRememberUser", "Remember Username" },
                    { "LoginPassLabel", "Password:" },
                    { "LoginRememberPass", "Remember Password" },
                    { "LoginMetaMaskBtn", "🦊 Login with MetaMask" },
                    { "LoginBtn", "Login" },
                    { "UpdateSignatureBtn", "✍️ Update Signature" },
                    { "ScanInit", "Initializing system scan..." },
                    { "ScanOS", "Scanning Operating System..." },
                    { "ScanCPU", "Identifying Processor (CPU)..." },
                    { "ScanMB", "Detecting Motherboard and Chipset..." },
                    { "ScanHash", "Generating SHA-256 cryptographic signature..." },
                    { "ScanDone", "Scan completed. Hardware signature generated." },
                    { "ScanError", "Error during scan: " },
                    { "ScanOSLoading", "Retrieving system information..." },
                    { "ScanCPULoading", "Retrieving CPU specifications..." },
                    { "ScanMBLoading", "Detecting motherboard..." },
                    { "GeneratingHashText", "GENERATING CRYPTOGRAPHIC SIGNATURE..." },
                    { "ScanningShort", "Scanning..." },
                    { "IdentifyingCpuShort", "Identifying CPU..." },
                    { "MotherboardShort", "Motherboard..." },
                    { "SigningShort", "Signing..." },
                    { "SignatureOkShort", "Signature OK" },
                    { "CancelledShort", "Cancelled" },
                    { "SignatureUpdated", "✔ SIGNATURE UPDATED" }
                }
            },
            {
                "fr", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ SYSTÃƒË†ME DE CONNEXION" },
                    { "PcRegSubtitle", "ENREGISTREMENT AUTOMATIQUE DE LA SIGNATURE MATÃƒâ€°RIELLE" },
                    { "OsCardTitle", "SYSTÃƒË†ME D'EXPLOITATION" },
                    { "CpuCardTitle", "PROCESSEUR" },
                    { "MbCardTitle", "CARTE MÃƒË†RE" },
                    { "CryptoLabel", "SIGNÃƒâ€° MATÃƒâ€°RIEL / SIGNATURE CRYPTO UNIQUE (SHA-256)" },
                    { "Copy", "COPIER" },
                    { "RegisterPc", "ENREGISTRER LE PC & SAUVEGARDER LE ZIP" },
                    { "EnterMetaverse", "ENTRER DANS LE MÃƒâ€°TAVERS" },
                    { "UserRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ INSCRIPTION DE L'UTILISATEUR" },
                    { "UserRegSubtitle", "CRÃƒâ€°ATION D'IDENTITÃƒâ€° ET ATTRIBUTION DE CRÃƒâ€°DENTIELS" },
                    { "UsernameLabel", "Nom d'utilisateur :" },
                    { "PasswordLabel", "Mot de passe :" },
                    { "ConfirmPasswordLabel", "Répéter le mot de passe :" },
                    { "UuidLabel", "Identifiant unique universel (UUID) :" },
                    { "GenerateUuid", "GÃƒâ€°NÃƒâ€°RER UN UUID" },
                    { "RegisterAndEnter", "S'INSCRIRE & ENTRER" },
                    { "WaitingMetaMaskTitle", "ATTENTE DE LA SIGNATURE METAMASK" },
                    { "WaitingMetaMaskDesc", "Veuillez ouvrir votre navigateur par défaut et signer la demande MetaMask pour lier votre portefeuille." },
                    { "LoginInfoTitle", "SIGNATURE MATÃƒâ€°RIELLE DÃƒâ€°TECTÃƒâ€°E" },
                    { "LoginPhaseStatus_Phase1", "Phase 1 : Entrez votre nom d'utilisateur et votre mot de passe pour continuer." },
                    { "LoginPhaseStatus_Phase2", "Phase 1 terminée avec succÃƒÂ¨s. Phase 2 déverrouillée : Signez et mettez ÃƒÂ  jour l'enregistrement ZIP de votre PC." },
                    { "LoginMetaMaskDesc", "Ouvrez votre navigateur et autorisez la demande MetaMask" },
                    { "LoginUserLabel", "Nom d'utilisateur :" },
                    { "LoginRememberUser", "Se souvenir du nom" },
                    { "LoginPassLabel", "Mot de passe :" },
                    { "LoginRememberPass", "Se souvenir du mot de passe" },
                    { "LoginMetaMaskBtn", "🦊 Connexion avec MetaMask" },
                    { "LoginBtn", "Connexion" },
                    { "UpdateSignatureBtn", "✍️ Mettre ÃƒÂ  jour la signature" },
                    { "ScanInit", "Initialisation de l'analyse du systÃƒÂ¨me..." },
                    { "ScanOS", "Analyse du systÃƒÂ¨me d'exploitation..." },
                    { "ScanCPU", "Identification du processeur (CPU)..." },
                    { "ScanMB", "Détection de la carte mÃƒÂ¨re et du chipset..." },
                    { "ScanHash", "Génération de la signature cryptographique SHA-256..." },
                    { "ScanDone", "Analyse terminée. Signature matérielle générée." },
                    { "ScanError", "Erreur lors de l'analyse : " },
                    { "ScanOSLoading", "Obtention des informations systÃƒÂ¨me..." },
                    { "ScanCPULoading", "Obtention des spécifications du processeur..." },
                    { "ScanMBLoading", "Détection de la carte mÃƒÂ¨re..." },
                    { "GeneratingHashText", "GÃƒâ€°NÃƒâ€°RATION DE LA SIGNATURE CRYPTOGRAPHIQUE..." },
                    { "ScanningShort", "Analyse..." },
                    { "IdentifyingCpuShort", "Identification du processeur..." },
                    { "MotherboardShort", "Carte mÃƒÂ¨re..." },
                    { "SigningShort", "Signature..." },
                    { "SignatureOkShort", "Signature OK" },
                    { "CancelledShort", "Annulé" },
                    { "SignatureUpdated", "✔ SIGNATURE MISE Ãƒâ‚¬ GRANDE" }
                }
            },
            {
                "de", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ ANMELDUNGS-SYSTEM" },
                    { "PcRegSubtitle", "AUTOMATISCHE REGISTRIERUNG DER HARDWARE-SIGNATUR" },
                    { "OsCardTitle", "BETRIEBSSYSTEM" },
                    { "CpuCardTitle", "PROZESSOR" },
                    { "MbCardTitle", "MAINBOARD" },
                    { "CryptoLabel", "HARDWARE SIGNIERT / EINZIGARTIGER KRYPTO-FINGERABDRUCK (SHA-256)" },
                    { "Copy", "KOPIEREN" },
                    { "RegisterPc", "PC REGISTRIEREN & ZIP SPEICHERN" },
                    { "EnterMetaverse", "METAVERSE BETRETEN" },
                    { "UserRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ BENUTZERREGISTRIERUNG" },
                    { "UserRegSubtitle", "IDENTITÃƒâ€žTSERSTELLUNG UND ZUWEISUNG VON ANMELDEDATEN" },
                    { "UsernameLabel", "Benutzername:" },
                    { "PasswordLabel", "Kennwort:" },
                    { "ConfirmPasswordLabel", "Kennwort wiederholen:" },
                    { "UuidLabel", "Universell eindeutiger Identifikator (UUID):" },
                    { "GenerateUuid", "UUID GENERIEREN" },
                    { "RegisterAndEnter", "REGISTRIEREN & BETRETEN" },
                    { "WaitingMetaMaskTitle", "WARTE AUF METAMASK-SIGNATUR" },
                    { "WaitingMetaMaskDesc", "Bitte ÃƒÂ¶ffnen Sie Ihren Standardbrowser und signieren Sie die MetaMask-Anfrage, um Ihre Wallet zu verknÃƒÂ¼pfen." },
                    { "LoginInfoTitle", "HARDWARE-SIGNATUR ERKANNT" },
                    { "LoginPhaseStatus_Phase1", "Phase 1: Geben Sie Ihren Benutzernamen und Ihr Kennwort ein, um fortzufahren." },
                    { "LoginPhaseStatus_Phase2", "Phase 1 erfolgreich abgeschlossen. Phase 2 freigeschaltet: Signieren und aktualisieren Sie die ZIP-Registrierung Ihres PCs." },
                    { "LoginMetaMaskDesc", "Ãƒâ€“ffnen Sie Ihren Browser und autorisieren Sie die MetaMask-Anfrage" },
                    { "LoginUserLabel", "Benutzername:" },
                    { "LoginRememberUser", "Benutzername merken" },
                    { "LoginPassLabel", "Kennwort:" },
                    { "LoginRememberPass", "Kennwort merken" },
                    { "LoginMetaMaskBtn", "🦊 Mit MetaMask anmelden" },
                    { "LoginBtn", "Anmelden" },
                    { "UpdateSignatureBtn", "✍️ Signatur aktualisieren" },
                    { "ScanInit", "Systemscan wird initialisiert..." },
                    { "ScanOS", "Betriebssystem wird gescannt..." },
                    { "ScanCPU", "Prozessor (CPU) wird identifiziert..." },
                    { "ScanMB", "Motherboard und Chipsatz werden erkannt..." },
                    { "ScanHash", "SHA-256 kryptografische Signatur wird generiert..." },
                    { "ScanDone", "Scan abgeschlossen. Hardware-Signatur generiert." },
                    { "ScanError", "Fehler beim Scannen: " },
                    { "ScanOSLoading", "Systeminformationen werden abgerufen..." },
                    { "ScanCPULoading", "CPU-Spezifikationen werden abgerufen..." },
                    { "ScanMBLoading", "Mainboard wird erkannt..." },
                    { "GeneratingHashText", "KRYPTOGRAFISCHE SIGNATUR WIRD GENERIERT..." },
                    { "ScanningShort", "Scannen..." },
                    { "IdentifyingCpuShort", "CPU wird identifiziert..." },
                    { "MotherboardShort", "Mainboard..." },
                    { "SigningShort", "Signieren..." },
                    { "SignatureOkShort", "Signatur OK" },
                    { "CancelledShort", "Abgebrochen" },
                    { "SignatureUpdated", "✔ SIGNATUR AKTUALISIERT" }
                }
            },
            {
                "pt", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ SISTEMA DE LOGIN" },
                    { "PcRegSubtitle", "REGISTRO AUTOMÁTICO DA ASSINATURA DE HARDWARE" },
                    { "OsCardTitle", "SISTEMA OPERACIONAL" },
                    { "CpuCardTitle", "PROCESSADOR" },
                    { "MbCardTitle", "PLACA-MÃƒÆ’E" },
                    { "CryptoLabel", "ASSINADO EM HARDWARE / HUELLA CRYPTO ÚNICA (SHA-256)" },
                    { "Copy", "COPIAR" },
                    { "RegisterPc", "REGISTRAR PC & SALVAR ZIP" },
                    { "EnterMetaverse", "ENTRAR NO METAVERSO" },
                    { "UserRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ REGISTRO DE USUÁRIO" },
                    { "UserRegSubtitle", "CRIAÃƒâ€¡ÃƒÆ’O DE IDENTIDADE E ATRIBUIÃƒâ€¡ÃƒÆ’O DE CREDENCIAIS" },
                    { "UsernameLabel", "Nome de Usuário:" },
                    { "PasswordLabel", "Senha:" },
                    { "ConfirmPasswordLabel", "Repetir Senha:" },
                    { "UuidLabel", "Identificador Único Universal (UUID):" },
                    { "GenerateUuid", "GERAR UUID" },
                    { "RegisterAndEnter", "REGISTRAR & ENTRAR" },
                    { "WaitingMetaMaskTitle", "AGUARDANDO ASSINATURA METAMASK" },
                    { "WaitingMetaMaskDesc", "Por favor, abra o navegador padrÃƒÂ£o e assine a solicitaÃƒÂ§ÃƒÂ£o do MetaMask para vincular a sua carteira." },
                    { "LoginInfoTitle", "ASSINATURA DE HARDWARE DETECTADA" },
                    { "LoginPhaseStatus_Phase1", "Fase 1: Insira seu usuário e senha para continuar." },
                    { "LoginPhaseStatus_Phase2", "Fase 1 concluída com sucesso. Fase 2 desbloqueada: Assine e atualize o registro ZIP do seu PC." },
                    { "LoginMetaMaskDesc", "Abra seu navegador e autorize a solicitaÃƒÂ§ÃƒÂ£o do MetaMask" },
                    { "LoginUserLabel", "Usuário:" },
                    { "LoginRememberUser", "Lembrar Nome" },
                    { "LoginPassLabel", "Senha:" },
                    { "LoginRememberPass", "Lembrar Senha" },
                    { "LoginMetaMaskBtn", "🦊 Entrar com MetaMask" },
                    { "LoginBtn", "Entrar" },
                    { "UpdateSignatureBtn", "✍️ Atualizar Assinatura" },
                    { "ScanInit", "Inicializando escaneamento do sistema..." },
                    { "ScanOS", "Escaneando Sistema Operacional..." },
                    { "ScanCPU", "Identificando Processador (CPU)..." },
                    { "ScanMB", "Detectando Placa-MÃƒÂ£e e Chipset..." },
                    { "ScanHash", "Gerando assinatura criptográfica SHA-256..." },
                    { "ScanDone", "Escaneamento concluído. Assinatura de hardware gerada." },
                    { "ScanError", "Erro durante o escaneamento: " },
                    { "ScanOSLoading", "Obtendo informaÃƒÂ§ÃƒÂµes do sistema..." },
                    { "ScanCPULoading", "Obtendo especificaÃƒÂ§ÃƒÂµes da CPU..." },
                    { "ScanMBLoading", "Detectando placa-mÃƒÂ£e..." },
                    { "GeneratingHashText", "GERANDO ASSINATURA CRIPTOGRÁFICA..." },
                    { "ScanningShort", "Escaneando..." },
                    { "IdentifyingCpuShort", "Identificando CPU..." },
                    { "MotherboardShort", "Placa-mÃƒÂ£e..." },
                    { "SigningShort", "Assinando..." },
                    { "SignatureOkShort", "Assinatura OK" },
                    { "CancelledShort", "Cancelado" },
                    { "SignatureUpdated", "✔ ASSINATURA ATUALIZADA" }
                }
            },
            {
                "it", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ SISTEMA DI ACCESSO" },
                    { "PcRegSubtitle", "REGISTRAZIONE AUTOMATICA DELLA FIRMA HARDWARE" },
                    { "OsCardTitle", "SISTEMA OPERATIVO" },
                    { "CpuCardTitle", "PROCESSORE" },
                    { "MbCardTitle", "SCHEDA MADRE" },
                    { "CryptoLabel", "FIRMATO IN HARDWARE / IMPRONTA CRITTOGRAFICA UNICA (SHA-256)" },
                    { "Copy", "COPIA" },
                    { "RegisterPc", "REGISTRA PC & SALVA ZIP" },
                    { "EnterMetaverse", "ENTRA NEL METAVERSO" },
                    { "UserRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ REGISTRAZIONE UTENTE" },
                    { "UserRegSubtitle", "CREAZIONE IDENTITÃƒâ‚¬ E ASSEGNAZIONE CREDENZIALI" },
                    { "UsernameLabel", "Nome utente:" },
                    { "PasswordLabel", "Password:" },
                    { "ConfirmPasswordLabel", "Ripeti Password:" },
                    { "UuidLabel", "Identificatore univoco universale (UUID):" },
                    { "GenerateUuid", "GENERA UUID" },
                    { "RegisterAndEnter", "REGISTRA & ENTRA" },
                    { "WaitingMetaMaskTitle", "ATTESA FIRMA METAMASK" },
                    { "WaitingMetaMaskDesc", "Apri il browser predefinito e firma la richiesta di MetaMask per collegare il tuo portafoglio." },
                    { "LoginInfoTitle", "FIRMA HARDWARE RILEVATA" },
                    { "LoginPhaseStatus_Phase1", "Fase 1: Inserisci il tuo nome utente e password per continuare." },
                    { "LoginPhaseStatus_Phase2", "Fase 1 completata con successo. Fase 2 sbloccata: Firma e aggiorna la registrazione ZIP del tuo PC." },
                    { "LoginMetaMaskDesc", "Apri il browser e autorizza la richiesta di MetaMask" },
                    { "LoginUserLabel", "Utente:" },
                    { "LoginRememberUser", "Ricorda Nome" },
                    { "LoginPassLabel", "Password:" },
                    { "LoginRememberPass", "Ricorda Password" },
                    { "LoginMetaMaskBtn", "🦊 Accedi con MetaMask" },
                    { "LoginBtn", "Accedi" },
                    { "UpdateSignatureBtn", "✍️ Aggiorna Firma" },
                    { "ScanInit", "Inizializzazione della scansione del sistema..." },
                    { "ScanOS", "Scansione del sistema operativo..." },
                    { "ScanCPU", "Identificazione del processore (CPU)..." },
                    { "ScanMB", "Rilevamento della scheda madre e del chipset..." },
                    { "ScanHash", "Generazione della firma crittografica SHA-256..." },
                    { "ScanDone", "Scansione completata. Firma hardware generata." },
                    { "ScanError", "Errore durante la scansione: " },
                    { "ScanOSLoading", "Recupero delle informazioni di sistema..." },
                    { "ScanCPULoading", "Recupero delle specifiche della CPU..." },
                    { "ScanMBLoading", "Rilevamento scheda madre..." },
                    { "GeneratingHashText", "GENERAZIONE DELLA FIRMA CRITTOGRAFICA..." },
                    { "ScanningShort", "Scansione..." },
                    { "IdentifyingCpuShort", "Identificazione CPU..." },
                    { "MotherboardShort", "Scheda madre..." },
                    { "SigningShort", "Firma in corso..." },
                    { "SignatureOkShort", "Firma OK" },
                    { "CancelledShort", "Annullato" },
                    { "SignatureUpdated", "✔ FIRMA AGGIORNATA" }
                }
            },
            {
                "zh", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ Ã§â„¢Â»Ã¥Â½â€¢Ã§Â³Â»Ã§Â»Å¸" },
                    { "PcRegSubtitle", "Ã¨â€¡ÂªÃ¥Å Â¨Ã§Â¡Â¬Ã¤Â»Â¶Ã§Â­Â¾Ã¥ÂÂÃ¦Â³Â¨Ã¥â€ Å’" },
                    { "OsCardTitle", "Ã¦â€œÂÃ¤Â½Å“Ã§Â³Â»Ã§Â»Å¸" },
                    { "CpuCardTitle", "Ã¥Â¤â€žÃ§Ââ€ Ã¥â„¢Â¨" },
                    { "MbCardTitle", "Ã¤Â¸Â»Ã¦ÂÂ¿" },
                    { "CryptoLabel", "Ã§Â¡Â¬Ã¤Â»Â¶Ã§Â­Â¾Ã¥ÂÂ / Ã¥â€Â¯Ã¤Â¸â‚¬Ã¥Å Â Ã¥Â¯â€ Ã¦Å’â€¡Ã§ÂºÂ¹ (SHA-256)" },
                    { "Copy", "Ã¥Â¤ÂÃ¥Ë†Â¶" },
                    { "RegisterPc", "Ã¦Â³Â¨Ã¥â€ Å’Ã§â€ÂµÃ¨â€žâ€˜Ã¥Â¹Â¶Ã¤Â¿ÂÃ¥Â­Ëœ ZIP" },
                    { "EnterMetaverse", "Ã¨Â¿â€ºÃ¥â€¦Â¥Ã¥â€¦Æ’Ã¥Â®â€¡Ã¥Â®â„¢" },
                    { "UserRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ Ã§â€Â¨Ã¦Ë†Â·Ã¦Â³Â¨Ã¥â€ Å’" },
                    { "UserRegSubtitle", "Ã¨ÂºÂ«Ã¤Â»Â½Ã¥Ë†â€ºÃ¥Â»ÂºÃ¤Â¸Å½Ã¥â€¡Â­Ã¦ÂÂ®Ã¥Ë†â€ Ã©â€¦Â" },
                    { "UsernameLabel", "Ã§â€Â¨Ã¦Ë†Â·Ã¥ÂÂ:" },
                    { "PasswordLabel", "Ã¥Â¯â€ Ã§Â Â:" },
                    { "ConfirmPasswordLabel", "Ã©â€¡ÂÃ¥Â¤ÂÃ¥Â¯â€ Ã§Â Â:" },
                    { "UuidLabel", "Ã©â‚¬Å¡Ã§â€Â¨Ã¥â€Â¯Ã¤Â¸â‚¬Ã¨Â¯â€ Ã¥Ë†Â«Ã§Â Â (UUID):" },
                    { "GenerateUuid", "Ã§â€Å¸Ã¦Ë†Â UUID" },
                    { "RegisterAndEnter", "Ã¦Â³Â¨Ã¥â€ Å’Ã¥Â¹Â¶Ã¨Â¿â€ºÃ¥â€¦Â¥" },
                    { "WaitingMetaMaskTitle", "Ã¦Â­Â£Ã¥Å“Â¨Ã§Â­â€°Ã¥Â¾â€¦ METAMASK Ã§Â­Â¾Ã¥ÂÂ" },
                    { "WaitingMetaMaskDesc", "Ã¨Â¯Â·Ã¦â€°â€œÃ¥Â¼â‚¬Ã©Â»ËœÃ¨Â®Â¤Ã¦ÂµÂÃ¨Â§Ë†Ã¥â„¢Â¨Ã¥Â¹Â¶Ã§Â­Â¾Ã§Â½Â² MetaMask Ã¨Â¯Â·Ã¦Â±â€šÃ¤Â»Â¥Ã©â€œÂ¾Ã¦Å½Â¥Ã¦â€šÂ¨Ã§Å¡â€žÃ©â€™Â±Ã¥Å’â€¦Ã£â‚¬â€š" },
                    { "LoginInfoTitle", "Ã¥Â·Â²Ã¦Â£â‚¬Ã¦Âµâ€¹Ã¥Ë†Â°Ã§Â¡Â¬Ã¤Â»Â¶Ã§Â­Â¾Ã¥ÂÂ" },
                    { "LoginPhaseStatus_Phase1", "Ã§Â¬Â¬ 1 Ã©ËœÂ¶Ã¦Â®ÂµÃ¯Â¼Å¡Ã¨Â¾â€œÃ¥â€¦Â¥Ã§â€Â¨Ã¦Ë†Â·Ã¥ÂÂÃ¥â€™Å’Ã¥Â¯â€ Ã§Â ÂÃ¤Â»Â¥Ã§Â»Â§Ã§Â»Â­Ã£â‚¬â€š" },
                    { "LoginPhaseStatus_Phase2", "Ã§Â¬Â¬ 1 Ã©ËœÂ¶Ã¦Â®ÂµÃ¦Ë†ÂÃ¥Å Å¸Ã¥Â®Å’Ã¦Ë†ÂÃ£â‚¬â€šÃ§Â¬Â¬ 2 Ã©ËœÂ¶Ã¦Â®ÂµÃ¥Â·Â²Ã¨Â§Â£Ã©â€ÂÃ¯Â¼Å¡Ã§Â­Â¾Ã¥ÂÂÃ¥Â¹Â¶Ã¦â€ºÂ´Ã¦â€“Â°Ã¦â€šÂ¨Ã§â€ÂµÃ¨â€žâ€˜Ã§Å¡â€ž ZIP Ã¦Â³Â¨Ã¥â€ Å’Ã£â‚¬â€š" },
                    { "LoginMetaMaskDesc", "Ã¦â€°â€œÃ¥Â¼â‚¬Ã¦ÂµÂÃ¨Â§Ë†Ã¥â„¢Â¨Ã¥Â¹Â¶Ã¦Å½Ë†Ã¦ÂÆ’ MetaMask Ã¨Â¯Â·Ã¦Â±â€š" },
                    { "LoginUserLabel", "Ã§â€Â¨Ã¦Ë†Â·:" },
                    { "LoginRememberUser", "Ã¨Â®Â°Ã¤Â½ÂÃ§â€Â¨Ã¦Ë†Â·Ã¥ÂÂ" },
                    { "LoginPassLabel", "Ã¥Â¯â€ Ã§Â Â:" },
                    { "LoginRememberPass", "Ã¨Â®Â°Ã¤Â½ÂÃ¥Â¯â€ Ã§Â Â" },
                    { "LoginMetaMaskBtn", "🦊 Ã©â‚¬Å¡Ã¨Â¿â€¡ MetaMask Ã§â„¢Â»Ã¥Â½â€¢" },
                    { "LoginBtn", "Ã§â„¢Â»Ã¥Â½â€¢" },
                    { "UpdateSignatureBtn", "✍️ Ã¦â€ºÂ´Ã¦â€“Â°Ã§Â­Â¾Ã¥ÂÂ" },
                    { "ScanInit", "Ã¦Â­Â£Ã¥Å“Â¨Ã¥Ë†ÂÃ¥Â§â€¹Ã¥Å’â€“Ã§Â³Â»Ã§Â»Å¸Ã¦â€°Â«Ã¦ÂÂ..." },
                    { "ScanOS", "Ã¦Â­Â£Ã¥Å“Â¨Ã¦â€°Â«Ã¦ÂÂÃ¦â€œÂÃ¤Â½Å“Ã§Â³Â»Ã§Â»Å¸..." },
                    { "ScanCPU", "Ã¦Â­Â£Ã¥Å“Â¨Ã¨Â¯â€ Ã¥Ë†Â«Ã¥Â¤â€žÃ§Ââ€ Ã¥â„¢Â¨ (CPU)..." },
                    { "ScanMB", "Ã¦Â­Â£Ã¥Å“Â¨Ã¦Â£â‚¬Ã¦Âµâ€¹Ã¤Â¸Â»Ã¦ÂÂ¿Ã¥â€™Å’Ã¨Å Â¯Ã§â€°â€¡Ã§Â»â€ž..." },
                    { "ScanHash", "Ã¦Â­Â£Ã¥Å“Â¨Ã§â€Å¸Ã¦Ë†Â SHA-256 Ã¥Å Â Ã¥Â¯â€ Ã§Â­Â¾Ã¥ÂÂ..." },
                    { "ScanDone", "Ã¦â€°Â«Ã¦ÂÂÃ¥Â®Å’Ã¦Ë†ÂÃ£â‚¬â€šÃ¥Â·Â²Ã§â€Å¸Ã¦Ë†ÂÃ§Â¡Â¬Ã¤Â»Â¶Ã§Â­Â¾Ã¥ÂÂÃ£â‚¬â€š" },
                    { "ScanError", "Ã¦â€°Â«Ã¦ÂÂÃ¦Å“Å¸Ã©â€”Â´Ã¥â€¡ÂºÃ©â€â„¢Ã¯Â¼Å¡" },
                    { "ScanOSLoading", "Ã¦Â­Â£Ã¥Å“Â¨Ã¨Å½Â·Ã¥Ââ€“Ã§Â³Â»Ã§Â»Å¸Ã¤Â¿Â¡Ã¦ÂÂ¯..." },
                    { "ScanCPULoading", "Ã¦Â­Â£Ã¥Å“Â¨Ã¨Å½Â·Ã¥Ââ€“ CPU Ã¨Â§â€žÃ¦Â Â¼..." },
                    { "ScanMBLoading", "Ã¦Â­Â£Ã¥Å“Â¨Ã¦Â£â‚¬Ã¦Âµâ€¹Ã¤Â¸Â»Ã¦ÂÂ¿..." },
                    { "GeneratingHashText", "Ã¦Â­Â£Ã¥Å“Â¨Ã§â€Å¸Ã¦Ë†ÂÃ¥Å Â Ã¥Â¯â€ Ã§Â­Â¾Ã¥ÂÂ..." },
                    { "ScanningShort", "Ã¦Â­Â£Ã¥Å“Â¨Ã¦â€°Â«Ã¦ÂÂ..." },
                    { "IdentifyingCpuShort", "Ã¦Â­Â£Ã¥Å“Â¨Ã¨Â¯â€ Ã¥Ë†Â« CPU..." },
                    { "MotherboardShort", "Ã¤Â¸Â»Ã¦ÂÂ¿..." },
                    { "SigningShort", "Ã¦Â­Â£Ã¥Å“Â¨Ã§Â­Â¾Ã¥ÂÂ..." },
                    { "SignatureOkShort", "Ã§Â­Â¾Ã¥ÂÂÃ¦Ë†ÂÃ¥Å Å¸" },
                    { "CancelledShort", "Ã¥Â·Â²Ã¥Ââ€“Ã¦Â¶Ë†" },
                    { "SignatureUpdated", "✔ Ã§Â­Â¾Ã¥ÂÂÃ¥Â·Â²Ã¦â€ºÂ´Ã¦â€“Â°" }
                }
            },
            {
                "ja", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ Ã£Æ’Â­Ã£â€šÂ°Ã£â€šÂ¤Ã£Æ’Â³Ã£â€šÂ·Ã£â€šÂ¹Ã£Æ’â€ Ã£Æ’Â " },
                    { "PcRegSubtitle", "Ã¨â€¡ÂªÃ¥â€¹â€¢Ã£Æ’ÂÃ£Æ’Â¼Ã£Æ’â€°Ã£â€šÂ¦Ã£â€šÂ§Ã£â€šÂ¢Ã§Â½Â²Ã¥ÂÂÃ§â„¢Â»Ã©Å’Â²" },
                    { "OsCardTitle", "Ã£â€šÂªÃ£Æ’Å¡Ã£Æ’Â¬Ã£Æ’Â¼Ã£Æ’â€ Ã£â€šÂ£Ã£Æ’Â³Ã£â€šÂ°Ã£â€šÂ·Ã£â€šÂ¹Ã£Æ’â€ Ã£Æ’Â " },
                    { "CpuCardTitle", "Ã£Æ’â€”Ã£Æ’Â­Ã£â€šÂ»Ã£Æ’Æ’Ã£â€šÂµ" },
                    { "MbCardTitle", "Ã£Æ’Å¾Ã£â€šÂ¶Ã£Æ’Â¼Ã£Æ’Å“Ã£Æ’Â¼Ã£Æ’â€°" },
                    { "CryptoLabel", "Ã£Æ’ÂÃ£Æ’Â¼Ã£Æ’â€°Ã£â€šÂ¦Ã£â€šÂ§Ã£â€šÂ¢Ã§Â½Â²Ã¥ÂÂ / Ã¥â€ºÂºÃ¦Å“â€°Ã£ÂÂ®Ã¦Å¡â€”Ã¥ÂÂ·Ã¦Å’â€¡Ã§Â´â€¹ (SHA-256)" },
                    { "Copy", "Ã£â€šÂ³Ã£Æ’â€Ã£Æ’Â¼" },
                    { "RegisterPc", "PCÃ§â„¢Â»Ã©Å’Â²Ã¯Â¼â€ ZIPÃ¤Â¿ÂÃ¥Â­Ëœ" },
                    { "EnterMetaverse", "Ã£Æ’Â¡Ã£â€šÂ¿Ã£Æ’ÂÃ£Æ’Â¼Ã£â€šÂ¹Ã£ÂÂ«Ã¥â€¦Â¥Ã£â€šâ€¹" },
                    { "UserRegTitle", "WOLD VIRTUAL Ã¢â‚¬â€ Ã£Æ’Â¦Ã£Æ’Â¼Ã£â€šÂ¶Ã£Æ’Â¼Ã§â„¢Â»Ã©Å’Â²" },
                    { "UserRegSubtitle", "IDÃ¤Â½Å“Ã¦Ë†ÂÃ£ÂÂ¨Ã¨Â³â€¡Ã¦Â Â¼Ã¦Æ’â€¦Ã¥Â Â±Ã£ÂÂ®Ã¥â€°Â²Ã£â€šÅ Ã¥Â½â€œÃ£ÂÂ¦" },
                    { "UsernameLabel", "Ã£Æ’Â¦Ã£Æ’Â¼Ã£â€šÂ¶Ã£Æ’Â¼Ã¥ÂÂ:" },
                    { "PasswordLabel", "Ã£Æ’â€˜Ã£â€šÂ¹Ã£Æ’Â¯Ã£Æ’Â¼Ã£Æ’â€°:" },
                    { "ConfirmPasswordLabel", "Ã£Æ’â€˜Ã£â€šÂ¹Ã£Æ’Â¯Ã£Æ’Â¼Ã£Æ’â€°Ã¥â€ ÂÃ¥â€¦Â¥Ã¥Å â€º:" },
                    { "UuidLabel", "Ã¥Â®â€¡Ã¥Â®â„¢Ã¥â€¦Â±Ã©â‚¬Å¡Ã¤Â¸â‚¬Ã¦â€žÂÃ¨Â­ËœÃ¥Ë†Â¥Ã¥Â­Â (UUID):" },
                    { "GenerateUuid", "UUIDÃ§â€Å¸Ã¦Ë†Â" },
                    { "RegisterAndEnter", "Ã§â„¢Â»Ã©Å’Â²Ã£Ââ€”Ã£ÂÂ¦Ã¥â€¦Â¥Ã£â€šâ€¹" },
                    { "WaitingMetaMaskTitle", "METAMASKÃ§Â½Â²Ã¥ÂÂÃ¥Â¾â€¦Ã£ÂÂ¡" },
                    { "WaitingMetaMaskDesc", "Ã£Æ’â€¡Ã£Æ’â€¢Ã£â€šÂ©Ã£Æ’Â«Ã£Æ’Ë†Ã£ÂÂ®Ã£Æ’â€“Ã£Æ’Â©Ã£â€šÂ¦Ã£â€šÂ¶Ã£â€šâ€™Ã©â€“â€¹Ã£ÂÂÃ£â‚¬ÂMetaMaskÃ£ÂÂ®Ã£Æ’ÂªÃ£â€šÂ¯Ã£â€šÂ¨Ã£â€šÂ¹Ã£Æ’Ë†Ã£ÂÂ«Ã§Â½Â²Ã¥ÂÂÃ£Ââ€”Ã£ÂÂ¦Ã£â€šÂ¦Ã£â€šÂ©Ã£Æ’Â¬Ã£Æ’Æ’Ã£Æ’Ë†Ã£â€šâ€™Ã£Æ’ÂªÃ£Æ’Â³Ã£â€šÂ¯Ã£Ââ€”Ã£ÂÂ¦Ã£ÂÂÃ£ÂÂ Ã£Ââ€¢Ã£Ââ€žÃ£â‚¬â€š" },
                    { "LoginInfoTitle", "Ã£Æ’ÂÃ£Æ’Â¼Ã£Æ’â€°Ã£â€šÂ¦Ã£â€šÂ§Ã£â€šÂ¢Ã§Â½Â²Ã¥ÂÂÃ£â€šâ€™Ã¦Â¤Å“Ã¥â€¡ÂºÃ£Ââ€”Ã£ÂÂ¾Ã£Ââ€”Ã£ÂÅ¸" },
                    { "LoginPhaseStatus_Phase1", "Ã£Æ’â€¢Ã£â€šÂ§Ã£Æ’Â¼Ã£â€šÂº 1: Ã£Æ’Â¦Ã£Æ’Â¼Ã£â€šÂ¶Ã£Æ’Â¼Ã¥ÂÂÃ£ÂÂ¨Ã£Æ’â€˜Ã£â€šÂ¹Ã£Æ’Â¯Ã£Æ’Â¼Ã£Æ’â€°Ã£â€šâ€™Ã¥â€¦Â¥Ã¥Å â€ºÃ£Ââ€”Ã£ÂÂ¦Ã§Â¶Å¡Ã¨Â¡Å’Ã£Ââ€”Ã£ÂÂ¦Ã£ÂÂÃ£ÂÂ Ã£Ââ€¢Ã£Ââ€žÃ£â‚¬â€š" },
                    { "LoginPhaseStatus_Phase2", "Ã£Æ’â€¢Ã£â€šÂ§Ã£Æ’Â¼Ã£â€šÂº 1 Ã£ÂÅ’Ã¦Â­Â£Ã¥Â¸Â¸Ã£ÂÂ«Ã¥Â®Å’Ã¤Âºâ€ Ã£Ââ€”Ã£ÂÂ¾Ã£Ââ€”Ã£ÂÅ¸Ã£â‚¬â€šÃ£Æ’â€¢Ã£â€šÂ§Ã£Æ’Â¼Ã£â€šÂº 2 Ã¨Â§Â£Ã©â„¢Â¤: PCÃ£ÂÂ®ZIPÃ§â„¢Â»Ã©Å’Â²Ã£ÂÂ«Ã§Â½Â²Ã¥ÂÂÃ£Ââ€”Ã£ÂÂ¦Ã¦â€ºÂ´Ã¦â€“Â°Ã£Ââ€”Ã£ÂÂ¦Ã£ÂÂÃ£ÂÂ Ã£Ââ€¢Ã£Ââ€žÃ£â‚¬â€š" },
                    { "LoginMetaMaskDesc", "Ã£Æ’â€“Ã£Æ’Â©Ã£â€šÂ¦Ã£â€šÂ¶Ã£â€šâ€™Ã©â€“â€¹Ã£ÂÂÃ£â‚¬ÂMetaMaskÃ£ÂÂ®Ã£Æ’ÂªÃ£â€šÂ¯Ã£â€šÂ¨Ã£â€šÂ¹Ã£Æ’Ë†Ã£â€šâ€™Ã¦â€°Â¿Ã¨ÂªÂÃ£Ââ€”Ã£ÂÂ¦Ã£ÂÂÃ£ÂÂ Ã£Ââ€¢Ã£Ââ€ž" },
                    { "LoginUserLabel", "Ã£Æ’Â¦Ã£Æ’Â¼Ã£â€šÂ¶Ã£Æ’Â¼:" },
                    { "LoginRememberUser", "Ã£Æ’Â¦Ã£Æ’Â¼Ã£â€šÂ¶Ã£Æ’Â¼Ã¥ÂÂÃ£â€šâ€™Ã¨Â¨ËœÃ¦â€ Â¶Ã£Ââ„¢Ã£â€šâ€¹" },
                    { "LoginPassLabel", "Ã£Æ’â€˜Ã£â€šÂ¹Ã£Æ’Â¯Ã£Æ’Â¼Ã£Æ’â€°:" },
                    { "LoginRememberPass", "Ã£Æ’â€˜Ã£â€šÂ¹Ã£Æ’Â¯Ã£Æ’Â¼Ã£Æ’â€°Ã£â€šâ€™Ã¨Â¨ËœÃ¦â€ Â¶Ã£Ââ„¢Ã£â€šâ€¹" },
                    { "LoginMetaMaskBtn", "🦊 MetaMaskÃ£ÂÂ§Ã£Æ’Â­Ã£â€šÂ°Ã£â€šÂ¤Ã£Æ’Â³" },
                    { "LoginBtn", "Ã£Æ’Â­Ã£â€šÂ°Ã£â€šÂ¤Ã£Æ’Â³" },
                    { "UpdateSignatureBtn", "✍️ Ã§Â½Â²Ã¥ÂÂÃ£â€šâ€™Ã¦â€ºÂ´Ã¦â€“Â°" },
                    { "ScanInit", "Ã£â€šÂ·Ã£â€šÂ¹Ã£Æ’â€ Ã£Æ’Â Ã£â€šÂ¹Ã£â€šÂ­Ã£Æ’Â£Ã£Æ’Â³Ã£â€šâ€™Ã¥Ë†ÂÃ¦Å“Å¸Ã¥Å’â€“Ã¤Â¸Â­..." },
                    { "ScanOS", "OSÃ£â€šâ€™Ã£â€šÂ¹Ã£â€šÂ­Ã£Æ’Â£Ã£Æ’Â³Ã¤Â¸Â­..." },
                    { "ScanCPU", "Ã£Æ’â€”Ã£Æ’Â­Ã£â€šÂ»Ã£Æ’Æ’Ã£â€šÂµ (CPU) Ã£â€šâ€™Ã¨Â­ËœÃ¥Ë†Â¥Ã¤Â¸Â­..." },
                    { "ScanMB", "Ã£Æ’Å¾Ã£â€šÂ¶Ã£Æ’Â¼Ã£Æ’Å“Ã£Æ’Â¼Ã£Æ’â€°Ã£ÂÂ¨Ã£Æ’ÂÃ£Æ’Æ’Ã£Æ’â€”Ã£â€šÂ»Ã£Æ’Æ’Ã£Æ’Ë†Ã£â€šâ€™Ã¦Â¤Å“Ã¥â€¡ÂºÃ¤Â¸Â­..." },
                    { "ScanHash", "SHA-256Ã¦Å¡â€”Ã¥ÂÂ·Ã§Â½Â²Ã¥ÂÂÃ£â€šâ€™Ã§â€Å¸Ã¦Ë†ÂÃ¤Â¸Â­..." },
                    { "ScanDone", "Ã£â€šÂ¹Ã£â€šÂ­Ã£Æ’Â£Ã£Æ’Â³Ã£ÂÅ’Ã¥Â®Å’Ã¤Âºâ€ Ã£Ââ€”Ã£ÂÂ¾Ã£Ââ€”Ã£ÂÅ¸Ã£â‚¬â€šÃ£Æ’ÂÃ£Æ’Â¼Ã£Æ’â€°Ã£â€šÂ¦Ã£â€šÂ§Ã£â€šÂ¢Ã§Â½Â²Ã¥ÂÂÃ£ÂÅ’Ã§â€Å¸Ã¦Ë†ÂÃ£Ââ€¢Ã£â€šÅ’Ã£ÂÂ¾Ã£Ââ€”Ã£ÂÅ¸Ã£â‚¬â€š" },
                    { "ScanError", "Ã£â€šÂ¹Ã£â€šÂ­Ã£Æ’Â£Ã£Æ’Â³Ã¤Â¸Â­Ã£ÂÂ«Ã£â€šÂ¨Ã£Æ’Â©Ã£Æ’Â¼Ã£ÂÅ’Ã§â„¢ÂºÃ§â€Å¸Ã£Ââ€”Ã£ÂÂ¾Ã£Ââ€”Ã£ÂÅ¸Ã¯Â¼Å¡" },
                    { "ScanOSLoading", "Ã£â€šÂ·Ã£â€šÂ¹Ã£Æ’â€ Ã£Æ’Â Ã¦Æ’â€¦Ã¥Â Â±Ã£â€šâ€™Ã¥Ââ€“Ã¥Â¾â€”Ã¤Â¸Â­..." },
                    { "ScanCPULoading", "CPUÃ¤Â»â€¢Ã¦Â§ËœÃ£â€šâ€™Ã¥Ââ€“Ã¥Â¾â€”Ã¤Â¸Â­..." },
                    { "ScanMBLoading", "Ã£Æ’Å¾Ã£â€šÂ¶Ã£Æ’Â¼Ã£Æ’Å“Ã£Æ’Â¼Ã£Æ’â€°Ã£â€šâ€™Ã¦Â¤Å“Ã¥â€¡ÂºÃ¤Â¸Â­..." },
                    { "GeneratingHashText", "Ã¦Å¡â€”Ã¥ÂÂ·Ã§Â½Â²Ã¥ÂÂÃ£â€šâ€™Ã§â€Å¸Ã¦Ë†ÂÃ¤Â¸Â­..." },
                    { "ScanningShort", "Ã£â€šÂ¹Ã£â€šÂ­Ã£Æ’Â£Ã£Æ’Â³Ã¤Â¸Â­..." },
                    { "IdentifyingCpuShort", "CPUÃ¨Â­ËœÃ¥Ë†Â¥Ã¤Â¸Â­..." },
                    { "MotherboardShort", "Ã£Æ’Å¾Ã£â€šÂ¶Ã£Æ’Â¼Ã£Æ’Å“Ã£Æ’Â¼Ã£Æ’â€°..." },
                    { "SigningShort", "Ã§Â½Â²Ã¥ÂÂÃ¤Â¸Â­..." },
                    { "SignatureOkShort", "Ã§Â½Â²Ã¥ÂÂÃ¥Â®Å’Ã¤Âºâ€ " },
                    { "CancelledShort", "Ã£â€šÂ­Ã£Æ’Â£Ã£Æ’Â³Ã£â€šÂ»Ã£Æ’Â«" },
                    { "SignatureUpdated", "✔ Ã§Â½Â²Ã¥ÂÂÃ£ÂÅ’Ã¦â€ºÂ´Ã¦â€“Â°Ã£Ââ€¢Ã£â€šÅ’Ã£ÂÂ¾Ã£Ââ€”Ã£ÂÅ¸" }
                }
            }
        };

        private void ApplyWpfLocale(string lang, string country)
        {
            if (!WpfTranslations.ContainsKey(lang))
            {
                lang = "en"; // fallback
            }
            _currentLang = lang;

            var t = WpfTranslations[lang];

            // GridPcRegistration UI elements
            if (TxtPcRegTitle != null) TxtPcRegTitle.Text = t["PcRegTitle"];
            if (TxtPcRegSubtitle != null) TxtPcRegSubtitle.Text = t["PcRegSubtitle"];
            if (TxtScanStatus != null) TxtScanStatus.Text = t["ScanInit"];
            if (TxtOsCardTitle != null) TxtOsCardTitle.Text = t["OsCardTitle"];
            if (TxtOsName != null) TxtOsName.Text = t["ScanOSLoading"];
            if (TxtCpuCardTitle != null) TxtCpuCardTitle.Text = t["CpuCardTitle"];
            if (TxtCpuName != null) TxtCpuName.Text = t["ScanCPULoading"];
            if (TxtMbCardTitle != null) TxtMbCardTitle.Text = t["MbCardTitle"];
            if (TxtMotherboardName != null) TxtMotherboardName.Text = t["ScanMBLoading"];
            if (TxtCryptoLabel != null) TxtCryptoLabel.Text = t["CryptoLabel"];
            if (TxtHardwareHash != null) TxtHardwareHash.Text = t["GeneratingHashText"];
            if (BtnCopyHash != null) BtnCopyHash.Content = t["Copy"];
            if (BtnGenerateZip != null) BtnGenerateZip.Content = t["RegisterPc"];
            if (BtnEnterMetaverse != null) BtnEnterMetaverse.Content = t["EnterMetaverse"];

            // GridUserRegistration UI elements
            if (TxtUserRegTitle != null) TxtUserRegTitle.Text = t["UserRegTitle"];
            if (TxtUserRegSubtitle != null) TxtUserRegSubtitle.Text = t["UserRegSubtitle"];
            if (LblRegUser != null) LblRegUser.Content = t["UsernameLabel"];
            if (LblRegPass != null) LblRegPass.Content = t["PasswordLabel"];
            if (LblRegPassConfirm != null) LblRegPassConfirm.Content = t["ConfirmPasswordLabel"];
            if (LblRegUuid != null) LblRegUuid.Content = t["UuidLabel"];
            if (BtnGenerateUuid != null) BtnGenerateUuid.Content = t["GenerateUuid"];
            if (BtnRegisterAndEnter != null) BtnRegisterAndEnter.Content = t["RegisterAndEnter"];
            if (TxtMetaMaskOverlayTitle != null) TxtMetaMaskOverlayTitle.Text = t["WaitingMetaMaskTitle"];
            if (TxtMetaMaskOverlayDesc != null) TxtMetaMaskOverlayDesc.Text = t["WaitingMetaMaskDesc"];

            // GridLoginScreen UI elements
            if (TxtLoginInfoTitle != null) TxtLoginInfoTitle.Text = t["LoginInfoTitle"];
            if (TxtLoginPhaseStatus != null) TxtLoginPhaseStatus.Text = t["LoginPhaseStatus_Phase1"];
            if (TxtLoginMetaMaskDesc != null) TxtLoginMetaMaskDesc.Text = t["LoginMetaMaskDesc"];
            if (TxtLoginUserLabel != null) TxtLoginUserLabel.Text = t["LoginUserLabel"];
            if (ChkRememberUser != null) ChkRememberUser.Content = t["LoginRememberUser"];
            if (TxtLoginPassLabel != null) TxtLoginPassLabel.Text = t["LoginPassLabel"];
            if (ChkRememberPass != null) ChkRememberPass.Content = t["LoginRememberPass"];
            if (BtnLoginMetaMask != null) BtnLoginMetaMask.Content = t["LoginMetaMaskBtn"];
            if (BtnLoginPhase1 != null) BtnLoginPhase1.Content = t["LoginBtn"];
            if (BtnLoginPhase2 != null) BtnLoginPhase2.Content = t["UpdateSignatureBtn"];
        }

        private bool IsOnAnotherPc()
        {
            try
            {
                if (!File.Exists(APP_DATA_SIG))
                {
                    return false;
                }

                string os = HardwareFingerprintService.GetOSName();
                string cpu = HardwareFingerprintService.GetCpuName();
                string motherboard = HardwareFingerprintService.GetMotherboardName();
                string currentFingerprint = HardwareFingerprintService.GenerateSignature(os, cpu, motherboard);

                string savedFingerprint = File.ReadAllText(APP_DATA_SIG, Encoding.UTF8).Trim();

                bool mismatch = !string.Equals(currentFingerprint, savedFingerprint, StringComparison.Ordinal);
                if (mismatch)
                {
                    Debug.WriteLine($"[PC Match Check] Fingerprint mismatch! Current: {currentFingerprint} vs Saved: {savedFingerprint}");
                }
                return mismatch;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PC Match Check] Error: {ex.Message}");
                return false;
            }
        }

        private void ResetRegistrationForNewPc()
        {
            try
            {
                Debug.WriteLine("[ResetRegistration] Clearing old registration files for a new PC.");
                if (File.Exists(APP_DATA_ZIP)) File.Delete(APP_DATA_ZIP);
                if (File.Exists(APP_DATA_SIG)) File.Delete(APP_DATA_SIG);
                
                string credPath = Path.Combine(APP_DATA_DIR, "credentials.json");
                if (File.Exists(credPath)) File.Delete(credPath);
                
                string settingsPath = Path.Combine(APP_DATA_DIR, "login_settings.json");
                if (File.Exists(settingsPath)) File.Delete(settingsPath);

                GodotLauncherService.DeleteGodotCurrentUserJson();
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[ResetRegistration] Error deleting registration files: {ex.Message}");
            }
        }



        // Ã¢â€â‚¬Ã¢â€â‚¬ HOOK DE TECLADO PARA AVATAR GODOT Ã¢â€â‚¬Ã¢â€â‚¬
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
            // UDP chat y sesion detenidos por _session.StopAll() y _udpChat.Stop()
            _udpChat.Stop();


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


        // â”€â”€ CHAT UDP DELEGADO A UdpChatService â”€â”€

        private void OnUdpChatMessageReceived(UdpChatMessage msg)
        {
            AddProximityChatMessage(msg.User, msg.Text, msg.IsSystem);
        }


        private void AddProximityChatMessage(string user, string text, bool isSystem = false)
        {
            Dispatcher.Invoke(() =>
            {
                if (!ChatOverlayPopup.IsOpen)
                {
                    ChatOverlayPopup.IsOpen = true;
                }

                var tb = new TextBlock
                {
                    TextAlignment = TextAlignment.Left,
                    TextWrapping = TextWrapping.Wrap,
                    FontSize = 13,
                    FontFamily = new System.Windows.Media.FontFamily("Segoe UI"),
                    Margin = new Thickness(0, 3, 0, 3)
                };

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
                UpdatePopupPosition();

                var fadeOutAnimation = new DoubleAnimation
                {
                    From = 1.0,
                    To = 0.0,
                    Duration = new Duration(TimeSpan.FromSeconds(2.0)),
                    BeginTime = TimeSpan.FromSeconds(8.0)
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
                double panelHeight = 180;
                var child = ChatOverlayPopup.Child as UIElement;
                if (child != null)
                {
                    child.Measure(new System.Windows.Size(450, double.PositiveInfinity));
                    panelHeight = child.DesiredSize.Height;
                }

                double targetLeft = 215;
                double targetTop = GodotPlaceholder.ActualHeight - panelHeight - 15;

                ChatOverlayPopup.Placement = System.Windows.Controls.Primitives.PlacementMode.Relative;
                ChatOverlayPopup.HorizontalOffset = targetLeft;
                ChatOverlayPopup.VerticalOffset = targetTop;
            }

            UpdateWebcamPosition();
        }

        // ActivateMetaverseUi: delega PeerSync y P2PWebNode a MetaverseSessionController
        private void ActivateMetaverseUi(string username, string repoPath)
        {
            if (_metaverseUiActivated) return;
            _metaverseUiActivated = true;
            BorderBottomLoginBar.Visibility = Visibility.Visible;
            EmbeddedServerNodeBar.Visibility = Visibility.Visible;

            try
            {
                var godotPaths = GodotProjectLocator.Resolve();
                string peersDir = System.IO.Path.GetFullPath(
                    System.IO.Path.Combine(godotPaths.ProjectDir, "..", "Estado_Global", "peers"));
                _session.StartPeerSync(peersDir, username, _currentWallet, _currentWalletSignature);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[ActivateMetaverseUi] Error al resolver paths de Godot: {ex.Message}");
            }

            _session.P2PStatusChanged += (status) => Dispatcher.Invoke(() =>
            {
                TxtP2PStatus.Text = status;
                if ((_session.P2PIsOnIpfs || _session.P2PTunnelActive) && !string.IsNullOrEmpty(_session.P2PGatewayUrl))
                {
                    TxtP2PLink.Text   = $"Enlace: {_session.P2PGatewayUrl}";
                    TxtP2PNodeId.Text = $"NODO: {_session.P2PNodeId}";
                }
            });

            _session.StartP2PWebNode(username, repoPath);
            TxtP2PNodeId.Text = $"NODO P2P: {_session.P2PSimulatedUrl}";
            TxtP2PLink.Text   = $"Enlace: {_session.P2PLocalUrl}";
            TxtP2PStatus.Text = "Generando ZIP...";
            P2PNodeBar.Visibility = Visibility.Visible;
        }

        private void StartP2PWebNode(string username, string repoPath) =>
            _session.StartP2PWebNode(username, repoPath);

        private void BtnCopyP2PLink_Click(object sender, RoutedEventArgs e)
        {
            string urlToCopy = !string.IsNullOrEmpty(_session.P2PGatewayUrl)
                ? _session.P2PGatewayUrl
                : _session.P2PLocalUrl ?? "";

            Clipboard.SetText(urlToCopy);

            bool esPublico = (_session.P2PIsOnIpfs || _session.P2PTunnelActive)
                             && !string.IsNullOrEmpty(_session.P2PGatewayUrl);
            if (esPublico)
            {
                MessageBox.Show(
                    $"Enlace publico de descarga copiado al portapapeles:\n\n{urlToCopy}\n\n" +
                    "Enviaselo a tu primo - podra descargar el visor directamente desde el navegador.",
                    "Enlace Publico Copiado", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            else
            {
                MessageBox.Show(
                    $"Enlace LOCAL copiado (solo red local):\n\n{urlToCopy}\n\n" +
                    "Espera a que el ZIP se suba a un servidor publico para compartirlo por internet.",
                    "Enlace Local", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        // ===================================================================
        // — VOICE CHAT (NAudio + VAD + UDP + Peer JSON) —
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
                var godotPaths = GodotProjectLocator.Resolve();
                var projectDir = godotPaths.ProjectDir;
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
                // Estado inactivo - estilo por defecto
                BtnVoiceChat.Content = "🎤 VOZ";
                BtnVoiceChat.ClearValue(BackgroundProperty);
                BtnVoiceChat.ClearValue(ForegroundProperty);
                BtnVoiceChat.ToolTip = "Activar chat de voz";
            }
            else if (_isSpeaking)
            {
                // Hablando - verde cyberpunk brillante
                BtnVoiceChat.Content = "🔴 VOZ ON";
                BtnVoiceChat.Background = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#00FF8C"));
                BtnVoiceChat.Foreground = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#0B0C10"));
                BtnVoiceChat.ToolTip = "Hablando... (clic para desactivar)";
            }
            else
            {
                // Activo pero en silencio - teal suave
                BtnVoiceChat.Content = "🎤 ...";
                BtnVoiceChat.Background = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#1A3040"));
                BtnVoiceChat.Foreground = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#66FCF1"));
                BtnVoiceChat.ToolTip = "Escuchando... (clic para desactivar)";
            }
        }

        // ===================================================================
        // — WEBCAM (OpenCvSharp PIP) —
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
            
            // El HwndSource de la webcam se crea como hijo de _godotHost.Handle
            // por lo que las coordenadas deben ser relativas al área de cliente del GodotHwndHost.
            // El GodotHwndHost tiene Stretch y ocupa todo el GodotPlaceholder.
            
            // Posicionar en la esquina inferior derecha del área de Godot (sin márgenes, pegado a los bordes)
            int marginRight = 0;   // margen desde la derecha
            int marginBottom = 0;   // margen desde abajo (pegado a la barra del chat)
            
            // Convertir margenes a espacio de coordenadas del DPI
            int marginRightDpi = (int)(marginRight * dpiX);
            int marginBottomDpi = (int)(marginBottom * dpiY);
            
            // Calcular posición: esquina inferior derecha
            int targetLeft = (int)(GodotPlaceholder.ActualWidth * dpiX) - width - marginRightDpi;
            int targetTop = (int)(GodotPlaceholder.ActualHeight * dpiY) - height - marginBottomDpi;

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

                    int width = (int)(320 * dpiX);
                    int height = (int)(240 * dpiY);
                    int targetLeft;
                    int targetTop;

                    if (BorderBottomLoginBar != null && BorderBottomLoginBar.Visibility == Visibility.Visible)
                    {
                        // La webcam debe aparecer dentro de GodotPlaceholder (Grid.Row="1"),
                        // justo encima de BorderBottomLoginBar (Grid.Row="2", Height="80")
                        // El HwndSource de la webcam es hijo de _godotHost.Handle,
                        // por lo que las coordenadas deben ser relativas al área de cliente del GodotHwndHost.
                        
                        // Posicionar en la esquina inferior derecha del área de Godot (sin márgenes, pegado a los bordes)
                        int marginRight = 0;   // margen desde la derecha
                        int marginBottom = 0;   // margen desde abajo (pegado a la barra del chat)
                        
                        // Convertir margenes a espacio de coordenadas del DPI
                        int marginRightDpi = (int)(marginRight * dpiX);
                        int marginBottomDpi = (int)(marginBottom * dpiY);
                        
                        // Calcular posición: esquina inferior derecha del GodotPlaceholder
                        targetLeft = (int)(GodotPlaceholder.ActualWidth * dpiX) - width - marginRightDpi;
                        targetTop = (int)(GodotPlaceholder.ActualHeight * dpiY) - height - marginBottomDpi;
                    }
                    else
                    {
                        // Fallback: esquina inferior derecha del placeholder (sin márgenes)
                        targetLeft = (int)(GodotPlaceholder.ActualWidth * dpiX) - width;
                        targetTop = (int)(GodotPlaceholder.ActualHeight * dpiY) - height;
                    }

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
                BtnWebcam.Content = "\U0001F4F7 CAM";
                BtnWebcam.ClearValue(BackgroundProperty);
                BtnWebcam.ClearValue(ForegroundProperty);
            }
            else
            {
                BtnWebcam.Content = "\U0001F534 CAM ON";
                BtnWebcam.Background = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#00FF8C"));
                BtnWebcam.Foreground = new SolidColorBrush(
                    (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString("#0B0C10"));
            }
        }
    }
}


