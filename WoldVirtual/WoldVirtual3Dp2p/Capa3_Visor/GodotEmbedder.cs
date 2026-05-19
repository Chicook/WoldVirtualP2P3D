using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows;
using System.Threading.Tasks;

namespace VisorSingularity
{
    /// <summary>
    /// Controlador Win32 para overlay de Godot sobre WPF (Sin HwndHost).
    /// Ejecuta Godot como un proceso top-level pero elimina sus bordes
    /// y lo superpone sobre el visor, eliminando el parpadeo de SetParent/HwndHost.
    /// </summary>
    public sealed class GodotViewer
    {
        // ──────────────────────────────────────────────────────────────────
        // Win32 — Constantes y Flags
        // ──────────────────────────────────────────────────────────────────
        private const int GWL_STYLE = -16;
        
        // Estilos para hacer la ventana sin bordes (Borderless Pop-up)
        private const uint WS_POPUP = 0x80000000;
        private const uint WS_VISIBLE = 0x10000000;
        
        private const uint WS_CAPTION = 0x00C00000;
        private const uint WS_THICKFRAME = 0x00040000;
        private const uint WS_MINIMIZEBOX = 0x00020000;
        private const uint WS_MAXIMIZEBOX = 0x00010000;
        private const uint WS_SYSMENU = 0x00080000;

        private const uint SWP_NOACTIVATE = 0x0010;
        private const uint SWP_SHOWWINDOW = 0x0040;
        private static readonly IntPtr HWND_TOP = new IntPtr(0);

        // ──────────────────────────────────────────────────────────────────
        // Win32 — Imports
        // ──────────────────────────────────────────────────────────────────
        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        [DllImport("user32.dll")]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
        private const int SW_RESTORE = 9;
        private const uint SWP_FRAMECHANGED = 0x0020;

        [DllImport("user32.dll")]
        private static extern IntPtr SetFocus(IntPtr hWnd);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

        [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")]
        private static extern IntPtr GetWindowLongPtrW(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll", EntryPoint = "GetWindowLongW")]
        private static extern int GetWindowLongW(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")]
        private static extern IntPtr SetWindowLongPtrW(IntPtr hWnd, int nIndex, IntPtr dwNewLong);

        [DllImport("user32.dll", EntryPoint = "SetWindowLongW")]
        private static extern int SetWindowLongW(IntPtr hWnd, int nIndex, int dwNewLong);

        public static IntPtr GetWindowLong(IntPtr hWnd, int nIndex)
        {
            if (IntPtr.Size == 8) return GetWindowLongPtrW(hWnd, nIndex);
            return (IntPtr)GetWindowLongW(hWnd, nIndex);
        }

        public static IntPtr SetWindowLong(IntPtr hWnd, int nIndex, IntPtr dwNewLong)
        {
            if (IntPtr.Size == 8) return SetWindowLongPtrW(hWnd, nIndex, dwNewLong);
            return (IntPtr)SetWindowLongW(hWnd, nIndex, dwNewLong.ToInt32());
        }

        // ──────────────────────────────────────────────────────────────────
        // Estado
        // ──────────────────────────────────────────────────────────────────
        private IntPtr _godotHwnd = IntPtr.Zero;
        private uint _godotProcessId;

        private static void Log(string message)
        {
            try
            {
                string logPath = System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "visor_debug.log");
                System.IO.File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss.fff}] {message}\r\n");
            }
            catch { }
        }

        public uint GodotProcessId 
        { 
            get => _godotProcessId; 
            set => _godotProcessId = value; 
        }

        public bool IsReady => _godotHwnd != IntPtr.Zero;

        // ──────────────────────────────────────────────────────────────────
        // API Pública
        // ──────────────────────────────────────────────────────────────────

        /// <summary>
        /// Busca la ventana top-level que pertenezca al PID de Godot.
        /// Retorna el HWND si la encuentra.
        /// </summary>
        public IntPtr GetGodotHwnd()
        {
            if (_godotHwnd != IntPtr.Zero) return _godotHwnd;
            if (_godotProcessId == 0) return IntPtr.Zero;

            IntPtr foundHwnd = IntPtr.Zero;
            EnumWindows((hWnd, lParam) =>
            {
                uint processId;
                GetWindowThreadProcessId(hWnd, out processId);
                
                // Si el PID coincide, verificamos que sea una ventana principal
                if (processId == _godotProcessId)
                {
                    // Comprobamos si tiene el estilo de ventana normal
                    IntPtr style = GetWindowLong(hWnd, GWL_STYLE);
                    uint styleUInt = (uint)(IntPtr.Size == 8 ? style.ToInt64() : style.ToInt32());
                    
                    // Si tiene el WS_VISIBLE o algún borde, lo consideramos
                    if ((styleUInt & WS_VISIBLE) != 0)
                    {
                        foundHwnd = hWnd;
                        return false; // Stop enumeration
                    }
                }
                return true;
            }, IntPtr.Zero);

            _godotHwnd = foundHwnd;
            return _godotHwnd;
        }

        /// <summary>
        /// Transforma la ventana de Godot en un Pop-up sin bordes
        /// de modo que parezca integrada de forma nativa sin usar SetParent.
        /// </summary>
        public void StripWindowBorders()
        {
            IntPtr hwnd = GetGodotHwnd();
            if (hwnd == IntPtr.Zero) return;

            // Obtener el estilo actual
            IntPtr currentStyle = GetWindowLong(hwnd, GWL_STYLE);
            long style = IntPtr.Size == 8 ? currentStyle.ToInt64() : currentStyle.ToInt32();

            // Quitar barra de título, bordes y menú
            style &= ~WS_CAPTION;
            style &= ~WS_THICKFRAME;
            style &= ~WS_MINIMIZEBOX;
            style &= ~WS_MAXIMIZEBOX;
            style &= ~WS_SYSMENU;

            // Asegurarnos de que sea POPUP
            style |= WS_POPUP;

            // Aplicar nuevo estilo
            SetWindowLong(hwnd, GWL_STYLE, new IntPtr(style));
            
            // Forzar actualización del frame de Windows
            SetWindowPos(hwnd, IntPtr.Zero, 0, 0, 0, 0, 0x0027); // SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
            
            // Restaurar si estaba minimizado
            ShowWindow(hwnd, SW_RESTORE);
            
            Log("Bordes de Godot removidos exitosamente.");
        }

        /// <summary>
        /// Mueve la ventana de Godot para que coincida exactamente
        /// con la posición y tamaño del control de WPF proporcionado en coordenadas de pantalla.
        /// </summary>
        public void UpdatePosition(FrameworkElement targetPlaceholder, Window parentWindow)
        {
            IntPtr hwnd = GetGodotHwnd();
            if (hwnd == IntPtr.Zero) return;
            if (targetPlaceholder == null || parentWindow == null) return;
            if (!targetPlaceholder.IsVisible) return;

            try
            {
                // Calcular la posición del placeholder relativa a la pantalla
                System.Windows.Point locationFromScreen = targetPlaceholder.PointToScreen(new System.Windows.Point(0, 0));

                // Calcular el factor de escala DPI de la pantalla actual
                PresentationSource source = PresentationSource.FromVisual(parentWindow);
                double dpiX = 1.0;
                double dpiY = 1.0;
                if (source?.CompositionTarget != null)
                {
                    dpiX = source.CompositionTarget.TransformToDevice.M11;
                    dpiY = source.CompositionTarget.TransformToDevice.M22;
                }

                // Calcular ancho y alto en pixeles físicos
                int width = (int)(targetPlaceholder.ActualWidth * dpiX);
                int height = (int)(targetPlaceholder.ActualHeight * dpiY);
                int x = (int)locationFromScreen.X;
                int y = (int)locationFromScreen.Y;

                // Posicionar la ventana encima del visor de WPF
                SetWindowPos(hwnd, HWND_TOP, x, y, width, height, SWP_SHOWWINDOW | SWP_NOACTIVATE);
            }
            catch (Exception ex)
            {
                Log($"UpdatePosition Error: {ex.Message}");
            }
        }

        public void FocusGodot()
        {
            IntPtr hwnd = GetGodotHwnd();
            if (hwnd != IntPtr.Zero)
            {
                SetFocus(hwnd);
            }
        }
    }
}
