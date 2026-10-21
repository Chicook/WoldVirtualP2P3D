using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;

namespace Visor3D
{
    /// <summary>
    /// Host Win32 que incrusta Godot 4 dentro de WPF via SetParent.
    /// Sincroniza las colas de entrada con AttachThreadInput y reenvía mensajes de teclado
    /// para permitir escribir en los controles de texto de Godot (LineEdit, TextEdit, etc.).
    /// </summary>
    public class GodotHwndHost : HwndHost
    {
        private IntPtr _childHwnd = IntPtr.Zero;
        private IntPtr _hostHwnd  = IntPtr.Zero;
        private Process? _godotProcess;
        private CancellationTokenSource? _cts;

        private readonly string? _godotExePath;
        private readonly string? _projectPath;
        private readonly string? _scenePath;
        private readonly string? _userArgs;

        public GodotHwndHost(IntPtr childHwnd)
        {
            _childHwnd = childHwnd;
        }

        public GodotHwndHost(string godotExePath, string projectPath, string scenePath = "", string userArgs = "")
        {
            _godotExePath = godotExePath;
            _projectPath  = projectPath;
            _scenePath    = scenePath;
            _userArgs     = userArgs;
        }

        public IntPtr ChildHwnd => _childHwnd;

        // ──────────────────────────────────────────────────────────────
        // HwndHost overrides
        // ──────────────────────────────────────────────────────────────

        protected override HandleRef BuildWindowCore(HandleRef hwndParent)
        {
            // Crear ventana contenedora Win32 "static"
            _hostHwnd = CreateWindowEx(
                0, "static", "",
                WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN,
                0, 0, 1, 1,
                hwndParent.Handle,
                IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);

            if (_hostHwnd == IntPtr.Zero)
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());

            this.Focusable = true;

            if (_childHwnd != IntPtr.Zero)
            {
                EmbedChildWindow();
            }
            else if (!string.IsNullOrEmpty(_godotExePath))
            {
                LaunchGodotAsync();
            }

            return new HandleRef(this, _hostHwnd);
        }

        protected override void DestroyWindowCore(HandleRef hwnd)
        {
            _cts?.Cancel();

            if (_hostHwnd != IntPtr.Zero)
            {
                DestroyWindow(_hostHwnd);
                _hostHwnd = IntPtr.Zero;
            }

            StopGodot();
        }

        // ──────────────────────────────────────────────────────────────
        // Godot process management
        // ──────────────────────────────────────────────────────────────

        private void LaunchGodotAsync()
        {
            _cts = new CancellationTokenSource();
            var token = _cts.Token;

            Task.Run(() =>
            {
                try
                {
                    // Godot 4 NO tiene el flag "--scene": la escena se pasa como
                    // argumento POSICIONAL (o se deja que use run/main_scene de
                    // project.godot). Un "--scene" desconocido hace que el motor
                    // avise del error y puede abortar el arranque antes de leer los
                    // argumentos de usuario (--client / --ip), cayendo al modo local.
                    string args = $"--path \"{_projectPath}\"";
                    if (!string.IsNullOrEmpty(_scenePath))
                        args += $" \"{_scenePath}\"";
                    if (!string.IsNullOrEmpty(_userArgs))
                        args += $" -- {_userArgs}";

                    var psi = new ProcessStartInfo
                    {
                        FileName         = _godotExePath,
                        Arguments        = args,
                        UseShellExecute  = false,
                        CreateNoWindow   = false
                    };

                    Console.WriteLine($"[GodotHwndHost] Lanzando proceso Godot: {_godotExePath}");
                    Console.WriteLine($"[GodotHwndHost] Argumentos completos pasados al motor: {args}");
                    Console.WriteLine($"[GodotHwndHost] Args de red (tras '--'): {(string.IsNullOrEmpty(_userArgs) ? "(ninguno -> SERVIDOR_LOCAL por defecto)" : _userArgs)}");
                    Debug.WriteLine($"[GodotHwndHost] Lanzando proceso Godot: {_godotExePath} {args}");

                    _godotProcess = Process.Start(psi);
                    if (_godotProcess == null)
                    {
                        Console.WriteLine("[GodotHwndHost] ERROR: No se pudo iniciar el proceso de Godot.");
                        return;
                    }

                    // Polling: esperar hasta 12 s a que Godot cree su ventana
                    IntPtr hwnd = IntPtr.Zero;
                    int elapsed = 0;
                    while (!token.IsCancellationRequested && !_godotProcess.HasExited && elapsed < 12000)
                    {
                        Thread.Sleep(100);
                        elapsed += 100;
                        _godotProcess.Refresh();

                        hwnd = _godotProcess.MainWindowHandle;
                        if (hwnd != IntPtr.Zero) break;

                        if (elapsed % 500 == 0)
                            hwnd = FindGodotWindow(_godotProcess.Id);

                        if (hwnd != IntPtr.Zero) break;
                    }

                    if (hwnd == IntPtr.Zero || token.IsCancellationRequested) return;

                    _childHwnd = hwnd;

                    // Volver al hilo UI para embeber
                    Application.Current.Dispatcher.Invoke(() =>
                    {
                        if (_hostHwnd != IntPtr.Zero && _childHwnd != IntPtr.Zero)
                        {
                            EmbedChildWindow();
                        }
                    });
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[GodotHwndHost] Error: {ex.Message}");
                }
            }, token);
        }

        private static IntPtr FindGodotWindow(int pid)
        {
            IntPtr found = IntPtr.Zero;
            EnumWindows((hWnd, _) =>
            {
                GetWindowThreadProcessId(hWnd, out uint wndPid);
                if (wndPid == (uint)pid && IsWindowVisible(hWnd))
                {
                    found = hWnd;
                    return false;
                }
                return true;
            }, IntPtr.Zero);
            return found;
        }

        // ──────────────────────────────────────────────────────────────
        // Embedding & Focus Management
        // ──────────────────────────────────────────────────────────────

        private void EmbedChildWindow()
        {
            if (_childHwnd == IntPtr.Zero || _hostHwnd == IntPtr.Zero) return;

            // Reparentar
            SetParent(_childHwnd, _hostHwnd);

            // Quitar decoraciones
            int style = GetWindowLong(_childHwnd, GWL_STYLE);
            style &= ~WS_CAPTION & ~WS_BORDER & ~WS_POPUP & ~WS_THICKFRAME;
            style |= WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN;
            SetWindowLong(_childHwnd, GWL_STYLE, style);

            int exStyle = GetWindowLong(_childHwnd, GWL_EXSTYLE);
            exStyle &= ~WS_EX_DLGMODALFRAME & ~WS_EX_CLIENTEDGE & ~WS_EX_STATICEDGE & ~WS_EX_WINDOWEDGE;
            SetWindowLong(_childHwnd, GWL_EXSTYLE, exStyle);

            SetWindowPos(_childHwnd, IntPtr.Zero, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED);

            ShowWindow(_childHwnd, SW_SHOW);
            ResizeToActualPixels();

            // Adjuntar colas de entrada para que el foco y el teclado viajen sin barrera
            AttachGodotThreadInput();
            ActivateGodotFocus();
        }

        private void AttachGodotThreadInput()
        {
            if (_childHwnd == IntPtr.Zero) return;
            try
            {
                uint godotThread = GetWindowThreadProcessId(_childHwnd, out _);
                uint currentThread = GetCurrentThreadId();
                if (godotThread != 0 && godotThread != currentThread)
                {
                    AttachThreadInput(currentThread, godotThread, true);
                }
            }
            catch { }
        }

        public void ActivateGodotFocus()
        {
            if (_childHwnd == IntPtr.Zero) return;
            try
            {
                AttachGodotThreadInput();
                SetFocus(_childHwnd);
                SetActiveWindow(_childHwnd);
            }
            catch { }
        }

        // ──────────────────────────────────────────────────────────────
        // Keyboard Forwarding (TranslateAcceleratorCore & TabIntoCore)
        // ──────────────────────────────────────────────────────────────

        protected override bool TabIntoCore(TraversalRequest request)
        {
            ActivateGodotFocus();
            return true;
        }

        protected override bool TranslateAcceleratorCore(ref MSG msg, ModifierKeys modifiers)
        {
            if (_childHwnd != IntPtr.Zero)
            {
                // Si es un mensaje de tecla (KEYDOWN, KEYUP, CHAR, SYSKEYDOWN, SYSKEYUP),
                // enviarlo tanto por SendMessage como por PostMessage para garantizar que
                // el bucle de mensajes de Godot reciba los eventos de input y movimiento.
                if (msg.message == WM_KEYDOWN || msg.message == WM_KEYUP ||
                    msg.message == WM_CHAR || msg.message == WM_SYSKEYDOWN || msg.message == WM_SYSKEYUP)
                {
                    PostMessage(_childHwnd, msg.message, msg.wParam, msg.lParam);
                    return true;
                }
            }
            return base.TranslateAcceleratorCore(ref msg, modifiers);
        }

        // ──────────────────────────────────────────────────────────────
        // Resize & WPF events
        // ──────────────────────────────────────────────────────────────

        public void ResizeToActualPixels()
        {
            if (_hostHwnd == IntPtr.Zero || _childHwnd == IntPtr.Zero) return;

            var source = PresentationSource.FromVisual(this);
            double dpiX = 1.0, dpiY = 1.0;
            if (source?.CompositionTarget != null)
            {
                dpiX = source.CompositionTarget.TransformToDevice.M11;
                dpiY = source.CompositionTarget.TransformToDevice.M22;
            }

            int w = (int)Math.Max(1, ActualWidth  * dpiX);
            int h = (int)Math.Max(1, ActualHeight * dpiY);

            MoveWindow(_hostHwnd, 0, 0, w, h, true);
            MoveWindow(_childHwnd, 0, 0, w, h, true);
        }

        protected override void OnRenderSizeChanged(SizeChangedInfo sizeInfo)
        {
            base.OnRenderSizeChanged(sizeInfo);
            ResizeToActualPixels();
        }

        protected override void OnGotKeyboardFocus(KeyboardFocusChangedEventArgs e)
        {
            base.OnGotKeyboardFocus(e);
            ActivateGodotFocus();
        }

        protected override void OnPreviewMouseDown(MouseButtonEventArgs e)
        {
            base.OnPreviewMouseDown(e);
            this.Focus();
            ActivateGodotFocus();
        }

        protected override void OnMouseDown(MouseButtonEventArgs e)
        {
            base.OnMouseDown(e);
            ActivateGodotFocus();
        }

        // ──────────────────────────────────────────────────────────────
        // Stop
        // ──────────────────────────────────────────────────────────────

        public void StopGodot()
        {
            _cts?.Cancel();
            try
            {
                if (_godotProcess != null && !_godotProcess.HasExited)
                {
                    _godotProcess.CloseMainWindow();
                    if (!_godotProcess.WaitForExit(1200))
                        _godotProcess.Kill();
                    _godotProcess.Dispose();
                    _godotProcess = null;
                }
            }
            catch { }
        }

        // ──────────────────────────────────────────────────────────────
        // P/Invoke
        // ──────────────────────────────────────────────────────────────

        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        [DllImport("kernel32.dll")]
        private static extern uint GetCurrentThreadId();

        [DllImport("user32.dll")]
        private static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool IsWindowVisible(IntPtr hWnd);

        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode, EntryPoint = "CreateWindowExW")]
        private static extern IntPtr CreateWindowEx(
            int dwExStyle, string lpClassName, string lpWindowName, int dwStyle,
            int x, int y, int nWidth, int nHeight,
            IntPtr hWndParent, IntPtr hMenu, IntPtr hInstance, IntPtr lpParam);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool DestroyWindow(IntPtr hwnd);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr SetParent(IntPtr Child, IntPtr NewParent);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern int GetWindowLong(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        [DllImport("user32.dll")]
        private static extern IntPtr SetFocus(IntPtr hWnd);

        [DllImport("user32.dll")]
        private static extern IntPtr SetActiveWindow(IntPtr hWnd);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        private static extern IntPtr SendMessage(IntPtr hWnd, int Msg, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool PostMessage(IntPtr hWnd, int Msg, IntPtr wParam, IntPtr lParam);

        private const int GWL_STYLE   = -16;
        private const int GWL_EXSTYLE = -20;

        private const int WS_VISIBLE      = 0x10000000;
        private const int WS_CHILD        = 0x40000000;
        private const int WS_POPUP        = unchecked((int)0x80000000);
        private const int WS_BORDER       = 0x00800000;
        private const int WS_DLGFRAME     = 0x00400000;
        private const int WS_CAPTION      = WS_BORDER | WS_DLGFRAME;
        private const int WS_THICKFRAME   = 0x00040000;
        private const int WS_CLIPCHILDREN = 0x02000000;

        private const int WS_EX_DLGMODALFRAME = 0x00000001;
        private const int WS_EX_WINDOWEDGE    = 0x00000100;
        private const int WS_EX_CLIENTEDGE    = 0x00000200;
        private const int WS_EX_STATICEDGE    = 0x00200000;

        private const int SW_SHOW = 5;

        private const uint SWP_NOSIZE       = 0x0001;
        private const uint SWP_NOMOVE       = 0x0002;
        private const uint SWP_NOZORDER     = 0x0004;
        private const uint SWP_NOACTIVATE   = 0x0010;
        private const uint SWP_FRAMECHANGED = 0x0020;

        private const int WM_KEYDOWN    = 0x0100;
        private const int WM_KEYUP      = 0x0101;
        private const int WM_CHAR       = 0x0102;
        private const int WM_SYSKEYDOWN = 0x0104;
        private const int WM_SYSKEYUP   = 0x0105;
    }
}
