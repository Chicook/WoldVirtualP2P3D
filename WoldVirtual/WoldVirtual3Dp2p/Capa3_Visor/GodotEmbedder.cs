using System;
using System.Runtime.InteropServices;
using System.Windows.Interop;

namespace VisorSingularity
{
    /// <summary>
    /// Contenedor Win32 profesional para incrustar Godot 4 dentro de WPF.
    ///
    /// PRINCIPIO FUNDAMENTAL:
    ///   El contenedor se crea ANTES de lanzar Godot. Su HWND se pasa a Godot
    ///   mediante --wid, de forma que Godot inicializa su contexto OpenGL
    ///   directamente como ventana hija desde el primer fotograma.
    ///
    ///   No hay SetParent a posteriori. No hay conflicto de contextos gráficos.
    ///   No hay parpadeo.
    ///
    /// FLUJO DE USO:
    ///   1. Instanciar GodotViewer y asignarlo como hijo de un Border WPF.
    ///      En ese momento BuildWindowCore() crea el contenedor nativo.
    ///   2. Leer ContainerHandle y pasarlo a Godot con --wid.
    ///   3. Godot arranca embebido de forma nativa.
    ///   4. Llamar a SetGodotHandle() con el HWND de Godot para poder
    ///      gestionar el foco.
    /// </summary>
    public sealed class GodotViewer : HwndHost
    {
        // ──────────────────────────────────────────────────────────────────
        // Win32 — Constantes
        // ──────────────────────────────────────────────────────────────────
        private const uint WS_CHILD        = 0x40000000u;
        private const uint WS_VISIBLE      = 0x10000000u;
        private const uint WS_CLIPCHILDREN = 0x02000000u;
        private const uint WS_CLIPSIBLINGS = 0x04000000u;

        private const uint WS_EX_COMPOSITED     = 0x02000000u;
        private const uint WS_EX_NOPARENTNOTIFY = 0x00000004u;

        private const uint WM_ERASEBKGND = 0x0014u;
        private const uint WM_PAINT      = 0x000Fu;
        private const uint WM_SIZE       = 0x0005u;

        private const int CS_HREDRAW = 0x0002;
        private const int CS_VREDRAW = 0x0001;

        // ──────────────────────────────────────────────────────────────────
        // Win32 — Estructuras
        // ──────────────────────────────────────────────────────────────────
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct WNDCLASSEX
        {
            public uint    cbSize;
            public int     style;
            public IntPtr  lpfnWndProc;
            public int     cbClsExtra;
            public int     cbWndExtra;
            public IntPtr  hInstance;
            public IntPtr  hIcon;
            public IntPtr  hCursor;
            public IntPtr  hbrBackground;
            public IntPtr  lpszMenuName;
            [MarshalAs(UnmanagedType.LPWStr)]
            public string  lpszClassName;
            public IntPtr  hIconSm;
        }

        // ──────────────────────────────────────────────────────────────────
        // Win32 — Imports
        // ──────────────────────────────────────────────────────────────────
        private delegate IntPtr WndProcDel(IntPtr hWnd, uint msg, IntPtr w, IntPtr l);

        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern ushort RegisterClassExW(ref WNDCLASSEX lpwcx);

        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateWindowExW(
            uint exStyle, string cls, string title, uint style,
            int x, int y, int w, int h,
            IntPtr parent, IntPtr menu, IntPtr instance, IntPtr param);

        [DllImport("user32.dll")]
        private static extern bool DestroyWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        private static extern IntPtr DefWindowProcW(IntPtr hWnd, uint msg, IntPtr w, IntPtr l);

        [DllImport("user32.dll")]
        private static extern bool MoveWindow(IntPtr hWnd, int x, int y, int w, int h, bool repaint);

        [DllImport("user32.dll")]
        private static extern IntPtr SetFocus(IntPtr hWnd);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        private static extern IntPtr GetModuleHandleW(string? name);

        // ──────────────────────────────────────────────────────────────────
        // Estado
        // ──────────────────────────────────────────────────────────────────
        private static readonly object   _regLock = new();
        private static bool              _registered;
        private static WndProcDel?       _wndProcDelegate; // evita que GC lo recoja

        private IntPtr _containerHwnd = IntPtr.Zero;
        private IntPtr _godotHwnd     = IntPtr.Zero;

        private const string WndClass = "GodotViewer_v1";

        // ──────────────────────────────────────────────────────────────────
        // Propiedades públicas
        // ──────────────────────────────────────────────────────────────────

        /// <summary>
        /// Handle del contenedor nativo. Pasarlo a Godot mediante --wid
        /// ANTES de lanzar el proceso.
        /// </summary>
        public IntPtr ContainerHandle => _containerHwnd;

        /// <summary>True cuando el contenedor está listo para recibir Godot.</summary>
        public bool IsReady => _containerHwnd != IntPtr.Zero;

        // ──────────────────────────────────────────────────────────────────
        // HwndHost
        // ──────────────────────────────────────────────────────────────────

        protected override HandleRef BuildWindowCore(HandleRef hwndParent)
        {
            RegisterWindowClass();

            _containerHwnd = CreateWindowExW(
                exStyle:  WS_EX_COMPOSITED,
                cls:      WndClass,
                title:    "",
                style:    WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS,
                x: 0, y: 0, w: 1, h: 1,
                parent:   hwndParent.Handle,
                menu:     IntPtr.Zero,
                instance: GetModuleHandleW(null),
                param:    IntPtr.Zero
            );

            if (_containerHwnd == IntPtr.Zero)
                throw new InvalidOperationException(
                    $"CreateWindowExW falló (Win32 error {Marshal.GetLastWin32Error()}).");

            return new HandleRef(this, _containerHwnd);
        }

        protected override void DestroyWindowCore(HandleRef hwnd)
        {
            if (_containerHwnd != IntPtr.Zero)
            {
                DestroyWindow(_containerHwnd);
                _containerHwnd = IntPtr.Zero;
            }
        }

        /// <summary>
        /// Propaga WM_SIZE de WPF a Godot para que siempre llene el área.
        /// </summary>
        protected override IntPtr WndProc(
            IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            if ((uint)msg == WM_SIZE && _godotHwnd != IntPtr.Zero)
            {
                int w = (int)(lParam.ToInt64() & 0xFFFF);
                int h = (int)((lParam.ToInt64() >> 16) & 0xFFFF);
                if (w > 0 && h > 0)
                    MoveWindow(_godotHwnd, 0, 0, w, h, false);
            }
            return base.WndProc(hwnd, msg, wParam, lParam, ref handled);
        }

        // ──────────────────────────────────────────────────────────────────
        // API Pública
        // ──────────────────────────────────────────────────────────────────

        /// <summary>
        /// Registra el HWND de la ventana que Godot creó como hijo del contenedor.
        /// Llamar después de que Godot haya arrancado completamente.
        /// </summary>
        public void SetGodotHandle(IntPtr godotHwnd)
        {
            _godotHwnd = godotHwnd;
        }

        /// <summary>Redimensiona el contenedor y Godot en píxeles físicos de pantalla.</summary>
        public void Resize(int widthPx, int heightPx)
        {
            if (_containerHwnd == IntPtr.Zero || widthPx < 1 || heightPx < 1) return;
            MoveWindow(_containerHwnd, 0, 0, widthPx, heightPx, false);
            if (_godotHwnd != IntPtr.Zero)
                MoveWindow(_godotHwnd, 0, 0, widthPx, heightPx, false);
        }

        /// <summary>
        /// Da el foco de teclado a Godot directamente.
        /// Windows enrutará los eventos de teclado a Godot sin ningún intermediario.
        /// </summary>
        public void FocusGodot()
        {
            if (_godotHwnd != IntPtr.Zero) SetFocus(_godotHwnd);
            else if (_containerHwnd != IntPtr.Zero) SetFocus(_containerHwnd);
        }

        // ──────────────────────────────────────────────────────────────────
        // Registro de la clase Win32 (una sola vez por proceso)
        // ──────────────────────────────────────────────────────────────────

        private static void RegisterWindowClass()
        {
            lock (_regLock)
            {
                if (_registered) return;

                // El delegado debe vivir mientras el proceso esté activo
                _wndProcDelegate = StaticWndProc;

                var wc = new WNDCLASSEX
                {
                    cbSize        = (uint)Marshal.SizeOf<WNDCLASSEX>(),
                    style         = CS_HREDRAW | CS_VREDRAW,
                    lpfnWndProc   = Marshal.GetFunctionPointerForDelegate(_wndProcDelegate),
                    hInstance     = GetModuleHandleW(null),
                    hbrBackground = IntPtr.Zero,  // Sin pintar fondo → sin parpadeo
                    lpszClassName = WndClass,
                };

                ushort atom = RegisterClassExW(ref wc);
                if (atom == 0)
                    throw new InvalidOperationException(
                        $"RegisterClassExW falló (Win32 error {Marshal.GetLastWin32Error()}).");

                _registered = true;
            }
        }

        /// <summary>
        /// WndProc estático del contenedor.
        /// Suprime WM_ERASEBKGND y WM_PAINT para que el contenedor nunca borre
        /// los píxeles que Godot ha dibujado — causa raíz del parpadeo.
        /// </summary>
        private static IntPtr StaticWndProc(IntPtr hWnd, uint msg, IntPtr w, IntPtr l)
        {
            if (msg == WM_ERASEBKGND) return new IntPtr(1); // "gestionado, no borres"
            if (msg == WM_PAINT)      return IntPtr.Zero;   // Godot pinta, nosotros no
            return DefWindowProcW(hWnd, msg, w, l);
        }
    }
}
