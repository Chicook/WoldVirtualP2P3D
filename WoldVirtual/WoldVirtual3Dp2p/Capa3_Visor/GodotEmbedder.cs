using System;
using System.Runtime.InteropServices;
using System.Windows.Interop;

namespace VisorSingularity
{
    /// <summary>
    /// Embedding profesional de un proceso Godot 4 dentro de WPF.
    ///
    /// DISEÑO:
    ///   Se registra una clase Win32 propia ("GodotHost") con WndProc dedicado.
    ///   Esa clase suprime WM_ERASEBKGND (causa raíz del parpadeo/tembleque) y
    ///   WM_PAINT del contenedor, dejando a Godot pintar sus píxeles sin ninguna
    ///   interferencia de WPF ni del sistema de composición de Windows.
    ///
    ///   WPF (HwndHost)
    ///     └─► Contenedor "GodotHost" (Win32, WS_EX_COMPOSITED)
    ///               └─► Ventana de Godot  (child, WS_CHILD | WS_VISIBLE)
    ///
    ///   El teclado se enruta directamente a Godot con SetFocus().
    ///   No se usa PostMessage → no hay duplicación de input → no hay tembleque.
    /// </summary>
    public sealed class GodotEmbedder : HwndHost
    {
        // ── Constantes Win32 ───────────────────────────────────────────────
        private const int  GWL_STYLE        = -16;
        private const int  GWL_EXSTYLE      = -20;

        private const uint WS_CHILD         = 0x40000000;
        private const uint WS_VISIBLE       = 0x10000000;
        private const uint WS_CLIPCHILDREN  = 0x02000000;
        private const uint WS_CLIPSIBLINGS  = 0x04000000;

        private const uint WS_CAPTION       = 0x00C00000;
        private const uint WS_THICKFRAME    = 0x00040000;
        private const uint WS_BORDER        = 0x00800000;
        private const uint WS_SYSMENU       = 0x00080000;
        private const uint WS_MINIMIZEBOX   = 0x00020000;
        private const uint WS_MAXIMIZEBOX   = 0x00010000;

        // Estilos extendidos
        private const uint WS_EX_COMPOSITED     = 0x02000000; // Anti-parpadeo compuesto
        private const uint WS_EX_NOPARENTNOTIFY = 0x00000004; // No notificar al padre
        private const uint WS_EX_TRANSPARENT    = 0x00000020;

        // Mensajes
        private const int WM_SIZE       = 0x0005;
        private const int WM_ERASEBKGND = 0x0014; // ← causa raíz del tembleque
        private const int WM_PAINT      = 0x000F;
        private const int WM_NCCALCSIZE = 0x0083;

        // Misc
        private const int  CS_HREDRAW  = 0x0002;
        private const int  CS_VREDRAW  = 0x0001;
        private const uint COLOR_WINDOW = 5;

        // ── Estructuras Win32 ──────────────────────────────────────────────
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        private struct WNDCLASSEX
        {
            public uint      cbSize;
            public int       style;
            public WndProcDelegate lpfnWndProc;
            public int       cbClsExtra;
            public int       cbWndExtra;
            public IntPtr    hInstance;
            public IntPtr    hIcon;
            public IntPtr    hCursor;
            public IntPtr    hbrBackground;
            public string?   lpszMenuName;
            public string    lpszClassName;
            public IntPtr    hIconSm;
        }

        private delegate IntPtr WndProcDelegate(
            IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

        // ── Imports Win32 ──────────────────────────────────────────────────
        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        private static extern ushort RegisterClassEx(ref WNDCLASSEX lpwcx);

        [DllImport("user32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        private static extern IntPtr CreateWindowEx(
            uint exStyle, string className, string windowName, uint style,
            int x, int y, int w, int h,
            IntPtr parent, IntPtr menu, IntPtr instance, IntPtr param);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool DestroyWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        private static extern IntPtr DefWindowProc(
            IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

        [DllImport("user32.dll")]
        private static extern IntPtr SetParent(IntPtr child, IntPtr parent);

        [DllImport("user32.dll")]
        private static extern uint SetWindowLong(IntPtr hWnd, int nIndex, uint dwNewLong);

        [DllImport("user32.dll")]
        private static extern uint GetWindowLong(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll")]
        private static extern bool MoveWindow(
            IntPtr hWnd, int x, int y, int w, int h, bool repaint);

        [DllImport("user32.dll")]
        private static extern IntPtr SetFocus(IntPtr hWnd);

        [DllImport("kernel32.dll")]
        private static extern IntPtr GetModuleHandle(string? name);

        // ── Estado ────────────────────────────────────────────────────────
        private IntPtr          _containerHwnd = IntPtr.Zero;
        private IntPtr          _godotHwnd     = IntPtr.Zero;

        // Mantenemos una referencia al delegado para que el GC no lo recolecte
        private WndProcDelegate? _wndProcDelegate;

        private static bool _classRegistered = false;
        private const string ClassName = "GodotHostContainer";

        // ── Propiedades públicas ───────────────────────────────────────────
        public bool   IsAttached     => _godotHwnd != IntPtr.Zero;
        public IntPtr ContainerHwnd  => _containerHwnd;

        // ── HwndHost: Construcción del contenedor nativo ──────────────────

        protected override HandleRef BuildWindowCore(HandleRef hwndParent)
        {
            IntPtr hInstance = GetModuleHandle(null);

            // Registrar la clase Win32 una sola vez por AppDomain
            if (!_classRegistered)
            {
                _wndProcDelegate = ContainerWndProc;

                var wc = new WNDCLASSEX
                {
                    cbSize        = (uint)Marshal.SizeOf<WNDCLASSEX>(),
                    style         = CS_HREDRAW | CS_VREDRAW,
                    lpfnWndProc   = _wndProcDelegate,
                    cbClsExtra    = 0,
                    cbWndExtra    = 0,
                    hInstance     = hInstance,
                    hIcon         = IntPtr.Zero,
                    hCursor       = IntPtr.Zero,
                    hbrBackground = IntPtr.Zero,   // Sin pintar fondo (evita parpadeo)
                    lpszMenuName  = null,
                    lpszClassName = ClassName,
                    hIconSm       = IntPtr.Zero
                };

                ushort atom = RegisterClassEx(ref wc);
                if (atom == 0)
                    throw new InvalidOperationException(
                        $"RegisterClassEx falló. Win32={Marshal.GetLastWin32Error()}");

                _classRegistered = true;
            }
            else
            {
                // Instancias adicionales: necesitamos guardar el delegado igualmente
                _wndProcDelegate = ContainerWndProc;
            }

            // Crear contenedor con WS_EX_COMPOSITED para composición sin parpadeo
            _containerHwnd = CreateWindowEx(
                exStyle:    WS_EX_COMPOSITED,
                className:  ClassName,
                windowName: "",
                style:      WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS,
                x: 0, y: 0, w: 1, h: 1,
                parent:     hwndParent.Handle,
                menu:       IntPtr.Zero,
                instance:   hInstance,
                param:      IntPtr.Zero
            );

            if (_containerHwnd == IntPtr.Zero)
                throw new InvalidOperationException(
                    $"CreateWindowEx falló. Win32={Marshal.GetLastWin32Error()}");

            return new HandleRef(this, _containerHwnd);
        }

        /// <summary>
        /// WndProc del contenedor nativo.
        /// Suprime WM_ERASEBKGND y WM_PAINT para que el fondo nunca se limpie,
        /// eliminando el parpadeo entre frames de Godot.
        /// </summary>
        private static IntPtr ContainerWndProc(
            IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam)
        {
            switch (msg)
            {
                case WM_ERASEBKGND:
                    // Retornar 1 = "ya gestionado, no borres el fondo"
                    return new IntPtr(1);

                case WM_PAINT:
                    // No hacer nada: Godot (hijo) se encarga de pintar
                    return IntPtr.Zero;
            }

            return DefWindowProc(hWnd, msg, wParam, lParam);
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
        /// HwndHost reenvía WM_SIZE al contenedor; lo usamos para ajustar Godot.
        /// </summary>
        protected override IntPtr WndProc(
            IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            if (msg == WM_SIZE && _godotHwnd != IntPtr.Zero)
            {
                int w = (int)(lParam.ToInt64() & 0xFFFF);
                int h = (int)((lParam.ToInt64() >> 16) & 0xFFFF);
                if (w > 0 && h > 0)
                {
                    MoveWindow(_godotHwnd, 0, 0, w, h, false);
                    handled = false; // no bloquear el procesamiento estándar
                }
            }
            return base.WndProc(hwnd, msg, wParam, lParam, ref handled);
        }

        // ── API Pública ────────────────────────────────────────────────────

        /// <summary>
        /// Ancla la ventana de Godot dentro del contenedor.
        /// Llamar desde el Dispatcher una vez localizada la ventana.
        /// </summary>
        public void AttachGodotWindow(IntPtr godotHwnd, int widthPx, int heightPx)
        {
            if (godotHwnd == IntPtr.Zero)
                throw new ArgumentException("Handle de Godot inválido.");
            if (_containerHwnd == IntPtr.Zero)
                throw new InvalidOperationException("El contenedor no está inicializado.");

            _godotHwnd = godotHwnd;

            // 1. Reparentar: Godot → nuestro contenedor nativo
            SetParent(_godotHwnd, _containerHwnd);

            // 2. Estilo de hijo limpio: sin bordes, sin título, sin frame
            uint childStyle = WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS;
            SetWindowLong(_godotHwnd, GWL_STYLE, childStyle);

            // 3. Estilo extendido: no notificar al padre para reducir mensajes de WPF
            uint exStyle = (uint)GetWindowLong(_godotHwnd, GWL_EXSTYLE);
            exStyle &= ~WS_EX_TRANSPARENT;
            exStyle |= WS_EX_NOPARENTNOTIFY;
            SetWindowLong(_godotHwnd, GWL_EXSTYLE, exStyle);

            // 4. Ajustar tamaños
            MoveWindow(_containerHwnd, 0, 0, widthPx, heightPx, false);
            MoveWindow(_godotHwnd,     0, 0, widthPx, heightPx, true);
        }

        /// <summary>Redimensiona el contenedor y Godot en píxeles físicos.</summary>
        public void Resize(int widthPx, int heightPx)
        {
            if (_containerHwnd == IntPtr.Zero || widthPx < 1 || heightPx < 1) return;
            MoveWindow(_containerHwnd, 0, 0, widthPx, heightPx, false);
            if (_godotHwnd != IntPtr.Zero)
                MoveWindow(_godotHwnd, 0, 0, widthPx, heightPx, false);
        }

        /// <summary>
        /// Entrega el foco de teclado directamente a Godot.
        /// Windows enrutará todos los eventos de teclado a Godot sin intermediarios.
        /// </summary>
        public void FocusGodot()
        {
            if (_godotHwnd != IntPtr.Zero)
                SetFocus(_godotHwnd);
        }
    }
}
