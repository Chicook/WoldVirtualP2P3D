using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;

namespace Visor3D
{
    /// <summary>
    /// Host Win32 que incrusta una ventana hija (ej. Godot 4) dentro de WPF.
    /// Reutilizado como base técnica para la Fase 1 (motor 3D).
    /// </summary>
    public class GodotHwndHost : HwndHost
    {
        private readonly IntPtr _childHwnd;
        private IntPtr _hostHwnd = IntPtr.Zero;

        public GodotHwndHost(IntPtr childHwnd)
        {
            _childHwnd = childHwnd;
        }

        protected override HandleRef BuildWindowCore(HandleRef hwndParent)
        {
            _hostHwnd = CreateWindowEx(
                0,
                "static",
                "",
                WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN,
                0, 0,
                (int)Math.Max(1, this.ActualWidth),
                (int)Math.Max(1, this.ActualHeight),
                hwndParent.Handle,
                IntPtr.Zero,
                IntPtr.Zero,
                IntPtr.Zero
            );

            if (_hostHwnd == IntPtr.Zero)
            {
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            }

            SetParent(_childHwnd, _hostHwnd);

            int style = GetWindowLong(_childHwnd, GWL_STYLE);
            style = style & ~WS_CAPTION & ~WS_BORDER & ~WS_POPUP & ~WS_THICKFRAME;
            style = style | WS_CHILD;
            SetWindowLong(_childHwnd, GWL_STYLE, style);

            int exStyle = GetWindowLong(_childHwnd, GWL_EXSTYLE);
            exStyle = exStyle & ~WS_EX_DLGMODALFRAME & ~WS_EX_CLIENTEDGE & ~WS_EX_STATICEDGE & ~WS_EX_WINDOWEDGE;
            SetWindowLong(_childHwnd, GWL_EXSTYLE, exStyle);

            SetWindowPos(_childHwnd, IntPtr.Zero, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED);

            ShowWindow(_childHwnd, SW_SHOW);
            ResizeToActualPixels();

            return new HandleRef(this, _hostHwnd);
        }

        protected override void DestroyWindowCore(HandleRef hwnd)
        {
            if (_hostHwnd != IntPtr.Zero)
            {
                DestroyWindow(_hostHwnd);
                _hostHwnd = IntPtr.Zero;
            }
        }

        public void ResizeToActualPixels()
        {
            if (_hostHwnd == IntPtr.Zero || _childHwnd == IntPtr.Zero) return;

            var source = PresentationSource.FromVisual(this);
            double dpiX = 1.0;
            double dpiY = 1.0;
            if (source?.CompositionTarget != null)
            {
                var matrix = source.CompositionTarget.TransformToDevice;
                dpiX = matrix.M11;
                dpiY = matrix.M22;
            }

            int width = (int)Math.Max(1, this.ActualWidth * dpiX);
            int height = (int)Math.Max(1, this.ActualHeight * dpiY);

            MoveWindow(_hostHwnd, 0, 0, width, height, true);
            MoveWindow(_childHwnd, 0, 0, width, height, true);
        }

        protected override void OnRenderSizeChanged(SizeChangedInfo sizeInfo)
        {
            base.OnRenderSizeChanged(sizeInfo);
            ResizeToActualPixels();
        }

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
        private static extern int SetWindowLong(IntPtr hWnd, int newIndex, int newLong);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern int GetWindowLong(IntPtr hWnd, int index);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool SetWindowPos(IntPtr hWnd, IntPtr hInsertAfter, int X, int Y, int cx, int cy, uint flags);

        private const int GWL_STYLE = -16;
        private const int GWL_EXSTYLE = -20;

        private const int WS_VISIBLE = 0x10000000;
        private const int WS_CHILD = 0x40000000;
        private const int WS_POPUP = unchecked((int)0x80000000);
        private const int WS_BORDER = 0x00800000;
        private const int WS_DLGFRAME = 0x00400000;
        private const int WS_CAPTION = WS_BORDER | WS_DLGFRAME;
        private const int WS_THICKFRAME = 0x00040000;
        private const int WS_CLIPCHILDREN = 0x02000000;

        private const int WS_EX_DLGMODALFRAME = 0x00000001;
        private const int WS_EX_WINDOWEDGE = 0x00000100;
        private const int WS_EX_CLIENTEDGE = 0x00000200;
        private const int WS_EX_STATICEDGE = 0x00200000;

        private const int SW_SHOW = 5;

        private const uint SWP_NOSIZE = 0x0001;
        private const uint SWP_NOMOVE = 0x0002;
        private const uint SWP_NOZORDER = 0x0004;
        private const uint SWP_NOACTIVATE = 0x0010;
        private const uint SWP_FRAMECHANGED = 0x0020;
    }
}
