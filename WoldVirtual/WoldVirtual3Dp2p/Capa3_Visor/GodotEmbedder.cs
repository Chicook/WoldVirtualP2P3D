using System;
using System.Runtime.InteropServices;
using System.Windows.Interop;

namespace VisorSingularity
{
    /// <summary>
    /// Incrusta el proceso de Godot 4 dentro de WPF de forma limpia y sin tembleques.
    ///
    /// ARQUITECTURA:
    ///   WPF → HwndHost (contenedor nativo) → Ventana de Godot (hijo del contenedor)
    ///
    /// WPF solo interactúa con el contenedor Win32 que creamos nosotros.
    /// Godot renderiza sus píxeles como hijo de ese contenedor, sin ningún
    /// sistema de composición de WPF interponiéndose. Esto elimina el
    /// "WPF Airspace Problem" que causa el tembleque del avatar.
    ///
    /// TECLADO:
    ///   No se usa PostMessage ni ThreadFilterMessage.
    ///   Cuando el usuario hace clic en el área 3D, se llama a FocusGodot()
    ///   y Windows enruta los eventos de teclado directamente a Godot.
    ///   Sin duplicación → sin tembleque de movimiento.
    /// </summary>
    public sealed class GodotEmbedder : HwndHost
    {
        // ── Win32: Estilos de ventana ──────────────────────────────────────
        private const int GWL_STYLE       = -16;
        private const int GWL_EXSTYLE     = -20;
        private const int WS_CHILD        = 0x40000000;
        private const int WS_VISIBLE      = 0x10000000;
        private const int WS_CLIPCHILDREN = 0x02000000;
        private const int WS_CLIPSIBLINGS = 0x04000000;
        private const int WS_CAPTION      = 0x00C00000;
        private const int WS_THICKFRAME   = 0x00040000;
        private const int WS_BORDER       = 0x00800000;
        private const int WS_DLGFRAME     = 0x00400000;
        private const int WS_SYSMENU      = 0x00080000;

        // ── Win32: Mensajes ────────────────────────────────────────────────
        private const int WM_SIZE = 0x0005;

        // ── Win32: Imports ─────────────────────────────────────────────────
        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr CreateWindowEx(
            uint   dwExStyle,
            string lpClassName,
            string lpWindowName,
            uint   dwStyle,
            int x, int y, int nWidth, int nHeight,
            IntPtr hWndParent,
            IntPtr hMenu,
            IntPtr hInstance,
            IntPtr lpParam);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool DestroyWindow(IntPtr hWnd);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr SetParent(IntPtr hWndChild, IntPtr hWndNewParent);

        [DllImport("user32.dll")]
        private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

        [DllImport("user32.dll")]
        private static extern int GetWindowLong(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll")]
        private static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

        [DllImport("user32.dll")]
        private static extern IntPtr SetFocus(IntPtr hWnd);

        [DllImport("kernel32.dll")]
        private static extern IntPtr GetModuleHandle(string? lpModuleName);

        // ── Estado interno ─────────────────────────────────────────────────
        private IntPtr _containerHwnd = IntPtr.Zero;
        private IntPtr _godotHwnd     = IntPtr.Zero;

        /// <summary>Handle de la ventana de Godot (para diagnóstico externo).</summary>
        public IntPtr GodotHwnd => _godotHwnd;

        /// <summary>True si Godot está correctamente anclado.</summary>
        public bool IsAttached => _godotHwnd != IntPtr.Zero && _containerHwnd != IntPtr.Zero;

        // ── HwndHost: Ciclo de vida ────────────────────────────────────────

        /// <summary>
        /// WPF llama a este método para crear el HWND nativo que actuará como
        /// contenedor. Le decimos a WPF: "hay un hueco Win32 aquí, no toques sus
        /// píxeles". Godot irá dentro de este hueco.
        /// </summary>
        protected override HandleRef BuildWindowCore(HandleRef hwndParent)
        {
            // Creamos un contenedor nativo mínimo con "Static" (clase preregistrada en Windows,
            // no necesita RegisterClass). Es transparente: solo actúa de delimitador de área.
            _containerHwnd = CreateWindowEx(
                dwExStyle:   0,
                lpClassName: "Static",
                lpWindowName: "",
                dwStyle:     WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS,
                x: 0, y: 0, nWidth: 1, nHeight: 1,
                hWndParent:  hwndParent.Handle,
                hMenu:       IntPtr.Zero,
                hInstance:   GetModuleHandle(null),
                lpParam:     IntPtr.Zero
            );

            if (_containerHwnd == IntPtr.Zero)
                throw new InvalidOperationException(
                    $"CreateWindowEx falló. Win32 error: {Marshal.GetLastWin32Error()}");

            return new HandleRef(this, _containerHwnd);
        }

        /// <summary>WPF destruye el contenedor cuando se desmonta el HwndHost.</summary>
        protected override void DestroyWindowCore(HandleRef hwnd)
        {
            if (_containerHwnd != IntPtr.Zero)
            {
                DestroyWindow(_containerHwnd);
                _containerHwnd = IntPtr.Zero;
            }
        }

        /// <summary>
        /// Captura los WM_SIZE que WPF envía al contenedor y los reenvía a Godot,
        /// garantizando que el 3D siempre llene el área disponible.
        /// </summary>
        protected override IntPtr WndProc(
            IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            if (msg == WM_SIZE && _godotHwnd != IntPtr.Zero)
            {
                int w = (int)(lParam.ToInt64() & 0xFFFF);
                int h = (int)((lParam.ToInt64() >> 16) & 0xFFFF);
                if (w > 0 && h > 0)
                    MoveWindow(_godotHwnd, 0, 0, w, h, false);
            }
            return base.WndProc(hwnd, msg, wParam, lParam, ref handled);
        }

        // ── API Pública ────────────────────────────────────────────────────

        /// <summary>
        /// Ancla la ventana de Godot dentro del contenedor nativo.
        /// Llamar desde el hilo del Dispatcher, una vez que la ventana de Godot exista.
        /// </summary>
        /// <param name="godotHwnd">Handle de la ventana principal de Godot.</param>
        /// <param name="width">Ancho en píxeles físicos.</param>
        /// <param name="height">Alto en píxeles físicos.</param>
        public void AttachGodotWindow(IntPtr godotHwnd, int width, int height)
        {
            if (godotHwnd == IntPtr.Zero)
                throw new ArgumentException("godotHwnd no puede ser cero.", nameof(godotHwnd));
            if (_containerHwnd == IntPtr.Zero)
                throw new InvalidOperationException("El contenedor Win32 no está inicializado.");

            _godotHwnd = godotHwnd;

            // 1. Reparentar: Godot pasa a ser hijo de nuestro contenedor nativo
            SetParent(_godotHwnd, _containerHwnd);

            // 2. Quitar bordes, título y marco de redimensionado de la ventana de Godot
            int newStyle = WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS;
            SetWindowLong(_godotHwnd, GWL_STYLE, newStyle);

            // 3. Ajustar tamaño del contenedor al área disponible
            MoveWindow(_containerHwnd, 0, 0, width, height, false);

            // 4. Ajustar Godot para que llene el contenedor
            MoveWindow(_godotHwnd, 0, 0, width, height, true);
        }

        /// <summary>Redimensiona el contenedor y Godot simultáneamente.</summary>
        public void Resize(int width, int height)
        {
            if (_containerHwnd == IntPtr.Zero || width < 1 || height < 1) return;
            MoveWindow(_containerHwnd, 0, 0, width, height, false);
            if (_godotHwnd != IntPtr.Zero)
                MoveWindow(_godotHwnd, 0, 0, width, height, false);
        }

        /// <summary>
        /// Entrega el foco de teclado directamente a Godot.
        /// Después de esto, Windows ruta todos los eventos de teclado a Godot
        /// sin ningún intermediario. Llamar al hacer clic en el área 3D.
        /// </summary>
        public void FocusGodot()
        {
            if (_godotHwnd != IntPtr.Zero)
                SetFocus(_godotHwnd);
        }
    }
}
