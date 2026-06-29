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
        private PeerSyncService? _peerSync;  // Sincronización P2P LAN de peers

        // ── Login de usuario existente (ZIP detectado) ───────────────────────────
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
            var (lang, country) = GetSystemLocaleInfo();
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

        // ─── DETECCIÓN DE CUENTA EXISTENTE ────────────────────────────────────────────────
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
                var (projectDir, _) = FindLocalGodotPaths();
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
                string os = GetOSName();
                string cpu = GetCpuName();
                string motherboard = GetMotherboardName();
                _hardwareFingerprint = GenerateSHA256Signature(os, cpu, motherboard);
                _loginFingerprint = _hardwareFingerprint;

                // Actualizar firma mostrada en la pantalla
                string display = _loginFingerprint.Length > 48 ? _loginFingerprint.Substring(0, 48) + "..." : _loginFingerprint;
                TxtLoginFingerprint.Text = $"SHA-256: {display}";

                // ── Crear ZIP de actualización de firma temporal ──
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

                // ── Pedir al usuario donde guardar el ZIP de firma actualizado ──
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
                    // El usuario canceló — limpiar y abortar sin error
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
                    return $"第 2 阶段成功完成。ZIP 已保存至：{path}\n第 3 阶段已解锁：通过 MetaMask 登录以进入。";
                case "ja":
                    return $"フェーズ 2 が正常に完了しました。ZIP 保存先: {path}\nフェーズ 3 解除: MetaMaskでログインして入ってください。";
                case "es":
                default:
                    return $"Fase 2 completada con éxito. ZIP guardado en: {path}\nFase 3 desbloqueada: Inicie sesión con MetaMask para entrar.";
            }
        }


        // ─── BOTON LOGIN METAMASK ────────────────────────────────────────────────────────────
        private void BtnLoginMetaMask_Click(object sender, RoutedEventArgs e)
        {
            BtnLoginMetaMask.IsEnabled     = false;
            BorderLoginStatus.Visibility   = Visibility.Visible;
            TxtLoginStatus.Text            = "INICIANDO SESIÓN CON METAMASK...";

            var userInfo = GetSavedUserInfo();

            // Arrancar el servidor HTTP puente en modo login (puerto 8080)
            StartHttpBridgeLogin();

            // Abrir navegador con metamask.html en modo login pasando el usuario e isla correctos
            try
            {
                string url = $"http://localhost:8080/?mode=login&user={Uri.EscapeDataString(userInfo.username)}&islandId={Uri.EscapeDataString(userInfo.islandId)}";
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show($"No se pudo abrir el navegador: {ex.Message}\nNavega a http://localhost:8080/ manualmente.",
                    "Aviso", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }


        private void StartHttpBridgeLogin()
        {
            try
            {
                if (_httpListener != null) { _httpListener.Stop(); _httpListener.Close(); }
                _httpListener = new HttpListener();
                _httpListener.Prefixes.Add("http://localhost:8080/");
                _httpListener.Start();
                Task.Run(() => ListenLoopLogin());
            }
            catch (Exception ex)
            {
                MessageBox.Show($"ERROR al iniciar HTTP Bridge: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                BorderLoginStatus.Visibility = Visibility.Collapsed;
                BtnLoginMetaMask.IsEnabled   = true;
            }
        }

        private async Task ListenLoopLogin()
        {
            while (_httpListener != null && _httpListener.IsListening && !_isClosing)
            {
                try
                {
                    var context  = await _httpListener.GetContextAsync();
                    var request  = context.Request;
                    var response = context.Response;
                    string path  = request.Url?.AbsolutePath ?? "/";

                    if (path == "/confirm")
                    {
                        string user      = request.QueryString["user"]      ?? "Usuario";
                        string wallet    = request.QueryString["wallet"]    ?? "0x0000";
                        string island    = request.QueryString["islandId"]  ?? "1 : 0.0.0";
                        string signature = request.QueryString["signature"] ?? "";

                        // Responder OK al navegador
                        string html = "<html><head><meta charset='UTF-8'><style>body{background:#0a0f1a;color:#00d9ff;font-family:sans-serif;text-align:center;padding-top:100px;}h1{color:#00ff8c;}</style></head><body><h1>✅ Sesión Iniciada</h1><p>Puedes regresar al Visor.</p></body></html>";
                        byte[] buf = System.Text.Encoding.UTF8.GetBytes(html);
                        response.ContentLength64 = buf.Length;
                        response.ContentType = "text/html; charset=UTF-8";
                        await response.OutputStream.WriteAsync(buf, 0, buf.Length);
                        response.OutputStream.Close();

                        if (_httpListener != null) { try { _httpListener.Stop(); _httpListener.Close(); } catch { } _httpListener = null; }

                        Dispatcher.Invoke(() => _OnLoginConfirmed(user, wallet, island, signature));
                    }
                    else
                    {
                        // Servir metamask.html con ?mode=login
                        string wwwPath  = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "www");
                        string filePath = Path.Combine(wwwPath, "metamask.html");
                        byte[] buf;
                        if (File.Exists(filePath))
                        {
                            buf = File.ReadAllBytes(filePath);
                            response.ContentType = "text/html; charset=UTF-8";
                        }
                        else
                        {
                            string fallback = $"<html><body style='background:#0a0f1a;color:#fff;font-family:sans-serif;text-align:center;padding:50px'><h1>WoldVirtual — Inicio de Sesión</h1><a style='background:#00d9ff;color:#000;padding:12px 24px;text-decoration:none;font-weight:bold;border-radius:6px' href='/confirm?user=Usuario&wallet=0x{Guid.NewGuid().ToString().Replace("-","").Substring(0,40)}&islandId=1+%3A+0.0.0&mode=login'>SIMULAR LOGIN METAMASK</a></body></html>";
                            buf = System.Text.Encoding.UTF8.GetBytes(fallback);
                            response.ContentType = "text/html; charset=UTF-8";
                        }
                        response.ContentLength64 = buf.Length;
                        await response.OutputStream.WriteAsync(buf, 0, buf.Length);
                        response.OutputStream.Close();
                    }
                }
                catch { }
            }
        }

        /// <summary>Llamado tras confirmar la firma MetaMask en modo login.</summary>
        private void _OnLoginConfirmed(string user, string wallet, string island, string signature)
        {
            TxtLoginStatus.Text = "✅ FIRMA CONFIRMADA — ENTRANDO AL METAVERSO...";

            // 1) Actualizar el ZIP de registro con la firma de esta sesión
            UpdateLoginZip(wallet, signature);

            // 2) Transicionar al visor
            GridLoginScreen.Visibility = Visibility.Collapsed;
            GridMainViewer.Visibility  = Visibility.Visible;
            _currentUsername = user;
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
                _osName = GetOSName();
                TxtOsName.Text = _osName;
                ProgScan.Value = 35;
                await Task.Delay(300);

                // Paso 2: Escanear Procesador (60%)
                TxtScanStatus.Text = t["ScanCPU"];
                ProgScan.Value = 50;
                await Task.Delay(600);
                _cpuName = GetCpuName();
                TxtCpuName.Text = _cpuName;
                ProgScan.Value = 70;
                await Task.Delay(300);

                // Paso 3: Escanear Placa Base (85%)
                TxtScanStatus.Text = t["ScanMB"];
                ProgScan.Value = 80;
                await Task.Delay(500);
                _motherboard = GetMotherboardName();
                TxtMotherboardName.Text = _motherboard;
                ProgScan.Value = 90;
                await Task.Delay(200);

                // Paso 4: Generar Huella Digital (100%)
                TxtScanStatus.Text = t["ScanHash"];
                ProgScan.Value = 95;
                await Task.Delay(400);

                _hardwareFingerprint = GenerateSHA256Signature(_osName, _cpuName, _motherboard);
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
            return HardwareFingerprintService.GetOSName();
        }

        private string GetCpuName()
        {
            return HardwareFingerprintService.GetCpuName();
        }

        private string GetMotherboardName()
        {
            return HardwareFingerprintService.GetMotherboardName();
        }

        private string GenerateSHA256Signature(string os, string cpu, string motherboard)
        {
            return HardwareFingerprintService.GenerateSignature(os, cpu, motherboard);
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
                    BtnGenerateZip.Content    = "✓ RESPALDO GUARDADO";
                    BtnGenerateZip.IsEnabled  = false;

                    // ── Guardar TAMBIÉN copia automática en AppData para detección de login ──
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
                                try { _httpListener.Stop(); _httpListener.Close(); } catch { }
                                _httpListener = null;
                            }

                            GridMetaMaskOverlay.Visibility    = Visibility.Collapsed;
                            GridUserRegistration.Visibility   = Visibility.Collapsed;
                            GridMainViewer.Visibility         = Visibility.Visible;

                            _currentUsername = user;
                            TxtChatActiveUser.Text = $"Usuario: {user}";

                            // Registro nuevo: carga EscenaPrincipal (flujo normal)
                            LaunchAndEmbedGodot(wallet, user, island,
                                scenePath: "res://EscenaPrincipal.tscn");
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
        /// <param name="scenePath">Ruta de escena Godot (res://...). Null = usa EscenaPrincipal.tscn</param>
        private async void LaunchAndEmbedGodot(string wallet, string user, string island, string scenePath = "res://EscenaPrincipal.tscn")
        {
            if (_godotProcess != null && !_godotProcess.HasExited)
            {
                return;
            }

            _metaverseUiActivated = false;

            // Buscar rutas de Godot localmente
            var (projectDir, exePath) = FindLocalGodotPaths();
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

            // Configurar resolución de inicio
            int width = (int)Math.Max(800, GodotPlaceholder.ActualWidth);
            int height = (int)Math.Max(600, GodotPlaceholder.ActualHeight);

            // Detectar país e idioma del sistema para pasarlo a Godot
            var (detectedLang, detectedCountry) = GetSystemLocaleInfo();

            // Argumentos de línea de comandos de Godot
            string arguments = $"--path \"{projectDir}\" {scenePath} --rendering-driver opengl3 --windowed --resolution {width}x{height} -- --wallet {wallet} --user-id \"{user}\" --island-id \"{island}\" --lang \"{detectedLang}\" --country \"{detectedCountry}\"";


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
            var paths = GodotProjectLocator.Resolve();
            return (paths.ProjectDir, paths.ExePath);
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
                    { "SignatureUpdated", "✓ FIRMA ACTUALIZADA" }
                }
            },
            {
                "en", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL — LOGIN SYSTEM" },
                    { "PcRegSubtitle", "AUTOMATIC HARDWARE SIGNATURE REGISTRATION" },
                    { "OsCardTitle", "OPERATING SYSTEM" },
                    { "CpuCardTitle", "PROCESSOR" },
                    { "MbCardTitle", "MOTHERBOARD" },
                    { "CryptoLabel", "HARDWARE SIGNED / UNIQUE CRYPTO FINGERPRINT (SHA-256)" },
                    { "Copy", "COPY" },
                    { "RegisterPc", "REGISTER PC & SAVE ZIP" },
                    { "EnterMetaverse", "ENTER METAVERSE" },
                    { "UserRegTitle", "WOLD VIRTUAL — USER REGISTRATION" },
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
                    { "SignatureUpdated", "✓ SIGNATURE UPDATED" }
                }
            },
            {
                "fr", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL — SYSTÈME DE CONNEXION" },
                    { "PcRegSubtitle", "ENREGISTREMENT AUTOMATIQUE DE LA SIGNATURE MATÉRIELLE" },
                    { "OsCardTitle", "SYSTÈME D'EXPLOITATION" },
                    { "CpuCardTitle", "PROCESSEUR" },
                    { "MbCardTitle", "CARTE MÈRE" },
                    { "CryptoLabel", "SIGNÉ MATÉRIEL / SIGNATURE CRYPTO UNIQUE (SHA-256)" },
                    { "Copy", "COPIER" },
                    { "RegisterPc", "ENREGISTRER LE PC & SAUVEGARDER LE ZIP" },
                    { "EnterMetaverse", "ENTRER DANS LE MÉTAVERS" },
                    { "UserRegTitle", "WOLD VIRTUAL — INSCRIPTION DE L'UTILISATEUR" },
                    { "UserRegSubtitle", "CRÉATION D'IDENTITÉ ET ATTRIBUTION DE CRÉDENTIELS" },
                    { "UsernameLabel", "Nom d'utilisateur :" },
                    { "PasswordLabel", "Mot de passe :" },
                    { "ConfirmPasswordLabel", "Répéter le mot de passe :" },
                    { "UuidLabel", "Identifiant unique universel (UUID) :" },
                    { "GenerateUuid", "GÉNÉRER UN UUID" },
                    { "RegisterAndEnter", "S'INSCRIRE & ENTRER" },
                    { "WaitingMetaMaskTitle", "ATTENTE DE LA SIGNATURE METAMASK" },
                    { "WaitingMetaMaskDesc", "Veuillez ouvrir votre navigateur par défaut et signer la demande MetaMask pour lier votre portefeuille." },
                    { "LoginInfoTitle", "SIGNATURE MATÉRIELLE DÉTECTÉE" },
                    { "LoginPhaseStatus_Phase1", "Phase 1 : Entrez votre nom d'utilisateur et votre mot de passe pour continuer." },
                    { "LoginPhaseStatus_Phase2", "Phase 1 terminée avec succès. Phase 2 déverrouillée : Signez et mettez à jour l'enregistrement ZIP de votre PC." },
                    { "LoginMetaMaskDesc", "Ouvrez votre navigateur et autorisez la demande MetaMask" },
                    { "LoginUserLabel", "Nom d'utilisateur :" },
                    { "LoginRememberUser", "Se souvenir du nom" },
                    { "LoginPassLabel", "Mot de passe :" },
                    { "LoginRememberPass", "Se souvenir du mot de passe" },
                    { "LoginMetaMaskBtn", "🦊 Connexion avec MetaMask" },
                    { "LoginBtn", "Connexion" },
                    { "UpdateSignatureBtn", "✍️ Mettre à jour la signature" },
                    { "ScanInit", "Initialisation de l'analyse du système..." },
                    { "ScanOS", "Analyse du système d'exploitation..." },
                    { "ScanCPU", "Identification du processeur (CPU)..." },
                    { "ScanMB", "Détection de la carte mère et du chipset..." },
                    { "ScanHash", "Génération de la signature cryptographique SHA-256..." },
                    { "ScanDone", "Analyse terminée. Signature matérielle générée." },
                    { "ScanError", "Erreur lors de l'analyse : " },
                    { "ScanOSLoading", "Obtention des informations système..." },
                    { "ScanCPULoading", "Obtention des spécifications du processeur..." },
                    { "ScanMBLoading", "Détection de la carte mère..." },
                    { "GeneratingHashText", "GÉNÉRATION DE LA SIGNATURE CRYPTOGRAPHIQUE..." },
                    { "ScanningShort", "Analyse..." },
                    { "IdentifyingCpuShort", "Identification du processeur..." },
                    { "MotherboardShort", "Carte mère..." },
                    { "SigningShort", "Signature..." },
                    { "SignatureOkShort", "Signature OK" },
                    { "CancelledShort", "Annulé" },
                    { "SignatureUpdated", "✓ SIGNATURE MISE À GRANDE" }
                }
            },
            {
                "de", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL — ANMELDUNGS-SYSTEM" },
                    { "PcRegSubtitle", "AUTOMATISCHE REGISTRIERUNG DER HARDWARE-SIGNATUR" },
                    { "OsCardTitle", "BETRIEBSSYSTEM" },
                    { "CpuCardTitle", "PROZESSOR" },
                    { "MbCardTitle", "MAINBOARD" },
                    { "CryptoLabel", "HARDWARE SIGNIERT / EINZIGARTIGER KRYPTO-FINGERABDRUCK (SHA-256)" },
                    { "Copy", "KOPIEREN" },
                    { "RegisterPc", "PC REGISTRIEREN & ZIP SPEICHERN" },
                    { "EnterMetaverse", "METAVERSE BETRETEN" },
                    { "UserRegTitle", "WOLD VIRTUAL — BENUTZERREGISTRIERUNG" },
                    { "UserRegSubtitle", "IDENTITÄTSERSTELLUNG UND ZUWEISUNG VON ANMELDEDATEN" },
                    { "UsernameLabel", "Benutzername:" },
                    { "PasswordLabel", "Kennwort:" },
                    { "ConfirmPasswordLabel", "Kennwort wiederholen:" },
                    { "UuidLabel", "Universell eindeutiger Identifikator (UUID):" },
                    { "GenerateUuid", "UUID GENERIEREN" },
                    { "RegisterAndEnter", "REGISTRIEREN & BETRETEN" },
                    { "WaitingMetaMaskTitle", "WARTE AUF METAMASK-SIGNATUR" },
                    { "WaitingMetaMaskDesc", "Bitte öffnen Sie Ihren Standardbrowser und signieren Sie die MetaMask-Anfrage, um Ihre Wallet zu verknüpfen." },
                    { "LoginInfoTitle", "HARDWARE-SIGNATUR ERKANNT" },
                    { "LoginPhaseStatus_Phase1", "Phase 1: Geben Sie Ihren Benutzernamen und Ihr Kennwort ein, um fortzufahren." },
                    { "LoginPhaseStatus_Phase2", "Phase 1 erfolgreich abgeschlossen. Phase 2 freigeschaltet: Signieren und aktualisieren Sie die ZIP-Registrierung Ihres PCs." },
                    { "LoginMetaMaskDesc", "Öffnen Sie Ihren Browser und autorisieren Sie die MetaMask-Anfrage" },
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
                    { "SignatureUpdated", "✓ SIGNATUR AKTUALISIERT" }
                }
            },
            {
                "pt", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL — SISTEMA DE LOGIN" },
                    { "PcRegSubtitle", "REGISTRO AUTOMÁTICO DA ASSINATURA DE HARDWARE" },
                    { "OsCardTitle", "SISTEMA OPERACIONAL" },
                    { "CpuCardTitle", "PROCESSADOR" },
                    { "MbCardTitle", "PLACA-MÃE" },
                    { "CryptoLabel", "ASSINADO EM HARDWARE / HUELLA CRYPTO ÚNICA (SHA-256)" },
                    { "Copy", "COPIAR" },
                    { "RegisterPc", "REGISTRAR PC & SALVAR ZIP" },
                    { "EnterMetaverse", "ENTRAR NO METAVERSO" },
                    { "UserRegTitle", "WOLD VIRTUAL — REGISTRO DE USUÁRIO" },
                    { "UserRegSubtitle", "CRIAÇÃO DE IDENTIDADE E ATRIBUIÇÃO DE CREDENCIAIS" },
                    { "UsernameLabel", "Nome de Usuário:" },
                    { "PasswordLabel", "Senha:" },
                    { "ConfirmPasswordLabel", "Repetir Senha:" },
                    { "UuidLabel", "Identificador Único Universal (UUID):" },
                    { "GenerateUuid", "GERAR UUID" },
                    { "RegisterAndEnter", "REGISTRAR & ENTRAR" },
                    { "WaitingMetaMaskTitle", "AGUARDANDO ASSINATURA METAMASK" },
                    { "WaitingMetaMaskDesc", "Por favor, abra o navegador padrão e assine a solicitação do MetaMask para vincular a sua carteira." },
                    { "LoginInfoTitle", "ASSINATURA DE HARDWARE DETECTADA" },
                    { "LoginPhaseStatus_Phase1", "Fase 1: Insira seu usuário e senha para continuar." },
                    { "LoginPhaseStatus_Phase2", "Fase 1 concluída com sucesso. Fase 2 desbloqueada: Assine e atualize o registro ZIP do seu PC." },
                    { "LoginMetaMaskDesc", "Abra seu navegador e autorize a solicitação do MetaMask" },
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
                    { "ScanMB", "Detectando Placa-Mãe e Chipset..." },
                    { "ScanHash", "Gerando assinatura criptográfica SHA-256..." },
                    { "ScanDone", "Escaneamento concluído. Assinatura de hardware gerada." },
                    { "ScanError", "Erro durante o escaneamento: " },
                    { "ScanOSLoading", "Obtendo informações do sistema..." },
                    { "ScanCPULoading", "Obtendo especificações da CPU..." },
                    { "ScanMBLoading", "Detectando placa-mãe..." },
                    { "GeneratingHashText", "GERANDO ASSINATURA CRIPTOGRÁFICA..." },
                    { "ScanningShort", "Escaneando..." },
                    { "IdentifyingCpuShort", "Identificando CPU..." },
                    { "MotherboardShort", "Placa-mãe..." },
                    { "SigningShort", "Assinando..." },
                    { "SignatureOkShort", "Assinatura OK" },
                    { "CancelledShort", "Cancelado" },
                    { "SignatureUpdated", "✓ ASSINATURA ATUALIZADA" }
                }
            },
            {
                "it", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL — SISTEMA DI ACCESSO" },
                    { "PcRegSubtitle", "REGISTRAZIONE AUTOMATICA DELLA FIRMA HARDWARE" },
                    { "OsCardTitle", "SISTEMA OPERATIVO" },
                    { "CpuCardTitle", "PROCESSORE" },
                    { "MbCardTitle", "SCHEDA MADRE" },
                    { "CryptoLabel", "FIRMATO IN HARDWARE / IMPRONTA CRITTOGRAFICA UNICA (SHA-256)" },
                    { "Copy", "COPIA" },
                    { "RegisterPc", "REGISTRA PC & SALVA ZIP" },
                    { "EnterMetaverse", "ENTRA NEL METAVERSO" },
                    { "UserRegTitle", "WOLD VIRTUAL — REGISTRAZIONE UTENTE" },
                    { "UserRegSubtitle", "CREAZIONE IDENTITÀ E ASSEGNAZIONE CREDENZIALI" },
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
                    { "SignatureUpdated", "✓ FIRMA AGGIORNATA" }
                }
            },
            {
                "zh", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL — 登录系统" },
                    { "PcRegSubtitle", "自动硬件签名注册" },
                    { "OsCardTitle", "操作系统" },
                    { "CpuCardTitle", "处理器" },
                    { "MbCardTitle", "主板" },
                    { "CryptoLabel", "硬件签名 / 唯一加密指纹 (SHA-256)" },
                    { "Copy", "复制" },
                    { "RegisterPc", "注册电脑并保存 ZIP" },
                    { "EnterMetaverse", "进入元宇宙" },
                    { "UserRegTitle", "WOLD VIRTUAL — 用户注册" },
                    { "UserRegSubtitle", "身份创建与凭据分配" },
                    { "UsernameLabel", "用户名:" },
                    { "PasswordLabel", "密码:" },
                    { "ConfirmPasswordLabel", "重复密码:" },
                    { "UuidLabel", "通用唯一识别码 (UUID):" },
                    { "GenerateUuid", "生成 UUID" },
                    { "RegisterAndEnter", "注册并进入" },
                    { "WaitingMetaMaskTitle", "正在等待 METAMASK 签名" },
                    { "WaitingMetaMaskDesc", "请打开默认浏览器并签署 MetaMask 请求以链接您的钱包。" },
                    { "LoginInfoTitle", "已检测到硬件签名" },
                    { "LoginPhaseStatus_Phase1", "第 1 阶段：输入用户名和密码以继续。" },
                    { "LoginPhaseStatus_Phase2", "第 1 阶段成功完成。第 2 阶段已解锁：签名并更新您电脑的 ZIP 注册。" },
                    { "LoginMetaMaskDesc", "打开浏览器并授权 MetaMask 请求" },
                    { "LoginUserLabel", "用户:" },
                    { "LoginRememberUser", "记住用户名" },
                    { "LoginPassLabel", "密码:" },
                    { "LoginRememberPass", "记住密码" },
                    { "LoginMetaMaskBtn", "🦊 通过 MetaMask 登录" },
                    { "LoginBtn", "登录" },
                    { "UpdateSignatureBtn", "✍️ 更新签名" },
                    { "ScanInit", "正在初始化系统扫描..." },
                    { "ScanOS", "正在扫描操作系统..." },
                    { "ScanCPU", "正在识别处理器 (CPU)..." },
                    { "ScanMB", "正在检测主板和芯片组..." },
                    { "ScanHash", "正在生成 SHA-256 加密签名..." },
                    { "ScanDone", "扫描完成。已生成硬件签名。" },
                    { "ScanError", "扫描期间出错：" },
                    { "ScanOSLoading", "正在获取系统信息..." },
                    { "ScanCPULoading", "正在获取 CPU 规格..." },
                    { "ScanMBLoading", "正在检测主板..." },
                    { "GeneratingHashText", "正在生成加密签名..." },
                    { "ScanningShort", "正在扫描..." },
                    { "IdentifyingCpuShort", "正在识别 CPU..." },
                    { "MotherboardShort", "主板..." },
                    { "SigningShort", "正在签名..." },
                    { "SignatureOkShort", "签名成功" },
                    { "CancelledShort", "已取消" },
                    { "SignatureUpdated", "✓ 签名已更新" }
                }
            },
            {
                "ja", new Dictionary<string, string>
                {
                    { "PcRegTitle", "WOLD VIRTUAL — ログインシステム" },
                    { "PcRegSubtitle", "自動ハードウェア署名登録" },
                    { "OsCardTitle", "オペレーティングシステム" },
                    { "CpuCardTitle", "プロセッサ" },
                    { "MbCardTitle", "マザーボード" },
                    { "CryptoLabel", "ハードウェア署名 / 固有の暗号指紋 (SHA-256)" },
                    { "Copy", "コピー" },
                    { "RegisterPc", "PC登録＆ZIP保存" },
                    { "EnterMetaverse", "メタバースに入る" },
                    { "UserRegTitle", "WOLD VIRTUAL — ユーザー登録" },
                    { "UserRegSubtitle", "ID作成と資格情報の割り当て" },
                    { "UsernameLabel", "ユーザー名:" },
                    { "PasswordLabel", "パスワード:" },
                    { "ConfirmPasswordLabel", "パスワード再入力:" },
                    { "UuidLabel", "宇宙共通一意識別子 (UUID):" },
                    { "GenerateUuid", "UUID生成" },
                    { "RegisterAndEnter", "登録して入る" },
                    { "WaitingMetaMaskTitle", "METAMASK署名待ち" },
                    { "WaitingMetaMaskDesc", "デフォルトのブラウザを開き、MetaMaskのリクエストに署名してウォレットをリンクしてください。" },
                    { "LoginInfoTitle", "ハードウェア署名を検出しました" },
                    { "LoginPhaseStatus_Phase1", "フェーズ 1: ユーザー名とパスワードを入力して続行してください。" },
                    { "LoginPhaseStatus_Phase2", "フェーズ 1 が正常に完了しました。フェーズ 2 解除: PCのZIP登録に署名して更新してください。" },
                    { "LoginMetaMaskDesc", "ブラウザを開き、MetaMaskのリクエストを承認してください" },
                    { "LoginUserLabel", "ユーザー:" },
                    { "LoginRememberUser", "ユーザー名を記憶する" },
                    { "LoginPassLabel", "パスワード:" },
                    { "LoginRememberPass", "パスワードを記憶する" },
                    { "LoginMetaMaskBtn", "🦊 MetaMaskでログイン" },
                    { "LoginBtn", "ログイン" },
                    { "UpdateSignatureBtn", "✍️ 署名を更新" },
                    { "ScanInit", "システムスキャンを初期化中..." },
                    { "ScanOS", "OSをスキャン中..." },
                    { "ScanCPU", "プロセッサ (CPU) を識別中..." },
                    { "ScanMB", "マザーボードとチップセットを検出中..." },
                    { "ScanHash", "SHA-256暗号署名を生成中..." },
                    { "ScanDone", "スキャンが完了しました。ハードウェア署名が生成されました。" },
                    { "ScanError", "スキャン中にエラーが発生しました：" },
                    { "ScanOSLoading", "システム情報を取得中..." },
                    { "ScanCPULoading", "CPU仕様を取得中..." },
                    { "ScanMBLoading", "マザーボードを検出中..." },
                    { "GeneratingHashText", "暗号署名を生成中..." },
                    { "ScanningShort", "スキャン中..." },
                    { "IdentifyingCpuShort", "CPU識別中..." },
                    { "MotherboardShort", "マザーボード..." },
                    { "SigningShort", "署名中..." },
                    { "SignatureOkShort", "署名完了" },
                    { "CancelledShort", "キャンセル" },
                    { "SignatureUpdated", "✓ 署名が更新されました" }
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

                string os = GetOSName();
                string cpu = GetCpuName();
                string motherboard = GetMotherboardName();
                string currentFingerprint = GenerateSHA256Signature(os, cpu, motherboard);

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

                DeleteGodotCurrentUserJson();
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[ResetRegistration] Error deleting registration files: {ex.Message}");
            }
        }

        private void DeleteGodotCurrentUserJson()
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                DirectoryInfo? dir = new DirectoryInfo(baseDir);
                while (dir != null)
                {
                    string candidate = Path.Combine(dir.FullName, "WoldVirtual", "woldvirtual", "scene", "MTC", "users3D", "current_user.json");
                    if (File.Exists(candidate))
                    {
                        File.Delete(candidate);
                        Debug.WriteLine($"[ResetRegistration] Deleted Godot current_user.json at: {candidate}");
                        return;
                    }
                    candidate = Path.Combine(dir.FullName, "woldvirtual", "scene", "MTC", "users3D", "current_user.json");
                    if (File.Exists(candidate))
                    {
                        File.Delete(candidate);
                        Debug.WriteLine($"[ResetRegistration] Deleted Godot current_user.json at: {candidate}");
                        return;
                    }
                    dir = dir.Parent;
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[ResetRegistration] Error deleting Godot user JSON: {ex.Message}");
            }
        }

        /// <summary>
        /// Detecta el idioma y país del sistema operativo usando CultureInfo.
        /// Devuelve (langCode, countryCode) p.ej: ("es", "ES"), ("en", "US"), ("fr", "FR").
        /// </summary>
        private (string lang, string country) GetSystemLocaleInfo()
        {
            try
            {
                var culture = System.Globalization.CultureInfo.CurrentCulture;

                // Código ISO 639-1 del idioma: "es", "en", "fr", "de", "pt", "zh", etc.
                string lang = culture.TwoLetterISOLanguageName.ToLowerInvariant();

                // Código ISO 3166-1 alpha-2 del país: "ES", "US", "FR", "DE", "BR", "CN", etc.
                // Se extrae de la región del sistema (RegionInfo)
                string country = "??";
                try
                {
                    var region = new System.Globalization.RegionInfo(culture.Name);
                    country = region.TwoLetterISORegionName.ToUpperInvariant();
                }
                catch
                {
                    // Si la cultura es neutral (sin región), extraerla del nombre: "es-ES" → "ES"
                    if (culture.Name.Contains('-'))
                    {
                        country = culture.Name.Split('-')[1].ToUpperInvariant();
                    }
                }

                Debug.WriteLine($"[Locale] Sistema detectado: idioma='{lang}', país='{country}', cultura='{culture.Name}'");
                return (lang, country);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[Locale] Error detectando locale: {ex.Message}");
                return ("en", "??");
            }
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
            _peerSync?.Stop();  // Detener sincronización P2P LAN
            _peerSync = null;
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

            // Iniciar sincronización P2P LAN de peers
            if (_peerSync == null)
            {
                try
                {
                    var (projectDir, _) = FindLocalGodotPaths();
                    string peersDir = Path.GetFullPath(Path.Combine(projectDir, "..", "Estado_Global", "peers"));
                    if (!Directory.Exists(peersDir))
                        Directory.CreateDirectory(peersDir);

                    _peerSync = new PeerSyncService(peersDir, username);
                    _peerSync.PeerReceived += (remoteId, json) => 
                    {
                        P2PWebNode.BroadcastToWs(json);
                    };
                    _peerSync.Start();
                    Debug.WriteLine($"[PeerSync] Servicio LAN iniciado para usuario '{username}' en '{peersDir}'");
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[PeerSync] Error al iniciar servicio LAN: {ex.Message}");
                }
            }

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
